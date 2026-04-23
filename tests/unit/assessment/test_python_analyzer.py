"""Tests for PythonAnalyzer — language-specific ruff-based analysis."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github_discovery.assessment.lang_analyzers.python_analyzer import (
    PythonAnalyzer,
    _interpolate_score,
)
from github_discovery.models.enums import ScoreDimension

_CLONE_DIR = "/fake/test-repo"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ruff_issue(
    filename: str = "src/main.py",
    code: str = "E501",
    message: str = "line too long",
) -> dict[str, Any]:
    return {"filename": filename, "code": code, "message": message}


def _mock_process(
    returncode: int = 0,
    stdout: bytes = b"",
    stderr: bytes = b"",
) -> AsyncMock:
    """Create an async-mock subprocess that behaves like ``Process``."""
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.wait = AsyncMock(return_value=None)
    proc.kill = MagicMock()
    return proc


# ---------------------------------------------------------------------------
# Interpolation unit tests
# ---------------------------------------------------------------------------


class TestInterpolateScore:
    """Verify the density-to-score interpolation logic."""

    def test_zero_density(self) -> None:
        assert _interpolate_score(0.0) == 1.0

    def test_exact_breakpoint_0_01(self) -> None:
        assert _interpolate_score(0.01) == pytest.approx(0.8)

    def test_exact_breakpoint_0_05(self) -> None:
        assert _interpolate_score(0.05) == pytest.approx(0.5)

    def test_exact_breakpoint_0_1(self) -> None:
        assert _interpolate_score(0.1) == pytest.approx(0.2)

    def test_above_max_density(self) -> None:
        assert _interpolate_score(0.5) == pytest.approx(0.2)

    def test_midpoint_interpolation(self) -> None:
        # Midpoint between (0.0, 1.0) and (0.01, 0.8) → 0.005 → 0.9
        assert _interpolate_score(0.005) == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# Analyzer tests
# ---------------------------------------------------------------------------


class TestPythonAnalyzer:
    """Integration-style tests using mocked subprocesses."""

    @pytest.fixture()
    def analyzer(self) -> PythonAnalyzer:
        return PythonAnalyzer()

    def test_language(self, analyzer: PythonAnalyzer) -> None:
        assert analyzer.language() == "python"

    async def test_analyze_clean_repo(self, analyzer: PythonAnalyzer) -> None:
        """Zero ruff issues → score 1.0."""
        version_proc = _mock_process(returncode=0)
        ruff_proc = _mock_process(
            returncode=0,
            stdout=b"[]",
        )
        loc_proc = _mock_process(returncode=0, stdout=b"500\n")

        with patch(
            "asyncio.create_subprocess_exec", side_effect=[version_proc, ruff_proc, loc_proc]
        ):
            result = await analyzer.analyze(_CLONE_DIR)

        assert result is not None
        assert result.value == 1.0
        assert result.dimension == ScoreDimension.CODE_QUALITY
        assert result.assessment_method == "ruff_heuristic"
        assert result.confidence == 0.6

    async def test_analyze_issues_found(self, analyzer: PythonAnalyzer) -> None:
        """Some ruff issues → score < 1.0."""
        issues = [_make_ruff_issue() for _ in range(5)]
        version_proc = _mock_process(returncode=0)
        ruff_proc = _mock_process(
            returncode=1,
            stdout=json.dumps(issues).encode(),
        )
        loc_proc = _mock_process(returncode=0, stdout=b"1000\n")

        with patch(
            "asyncio.create_subprocess_exec", side_effect=[version_proc, ruff_proc, loc_proc]
        ):
            result = await analyzer.analyze(_CLONE_DIR)

        assert result is not None
        assert result.value < 1.0
        assert len(result.evidence) == 5
        assert "E501" in result.evidence[0]

    async def test_analyze_ruff_not_installed(self, analyzer: PythonAnalyzer) -> None:
        """FileNotFoundError when checking ruff → None."""
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError,
        ):
            result = await analyzer.analyze(_CLONE_DIR)

        assert result is None

    async def test_analyze_ruff_timeout(self, analyzer: PythonAnalyzer) -> None:
        """Ruff exceeds timeout → None."""
        version_proc = _mock_process(returncode=0)

        async def _hang(*args: Any, **kwargs: Any) -> AsyncMock:
            proc = _mock_process()
            # Make communicate raise TimeoutError via wait_for
            proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=[version_proc, await _hang()]):
            result = await analyzer.analyze(_CLONE_DIR)

        # The ruff call itself hangs, but wait_for wraps it
        assert result is None

    async def test_score_based_on_density(self, analyzer: PythonAnalyzer) -> None:
        """Many issues per LOC → score around 0.2."""
        issues = [_make_ruff_issue(filename=f"src/{i}.py") for i in range(100)]
        version_proc = _mock_process(returncode=0)
        ruff_proc = _mock_process(
            returncode=1,
            stdout=json.dumps(issues).encode(),
        )
        # Only 200 LOC → density = 100/200 = 0.5 → score 0.2
        loc_proc = _mock_process(returncode=0, stdout=b"200\n")

        with patch(
            "asyncio.create_subprocess_exec", side_effect=[version_proc, ruff_proc, loc_proc]
        ):
            result = await analyzer.analyze(_CLONE_DIR)

        assert result is not None
        assert result.value == pytest.approx(0.2)
        assert "100 issue(s)" in result.explanation

    async def test_analyze_evidence_capped_at_10(self, analyzer: PythonAnalyzer) -> None:
        """Evidence list should be capped at 10 items."""
        issues = [_make_ruff_issue(filename=f"src/{i}.py") for i in range(20)]
        version_proc = _mock_process(returncode=0)
        ruff_proc = _mock_process(
            returncode=1,
            stdout=json.dumps(issues).encode(),
        )
        loc_proc = _mock_process(returncode=0, stdout=b"5000\n")

        with patch(
            "asyncio.create_subprocess_exec", side_effect=[version_proc, ruff_proc, loc_proc]
        ):
            result = await analyzer.analyze(_CLONE_DIR)

        assert result is not None
        assert len(result.evidence) == 10

    async def test_analyze_empty_stdout(self, analyzer: PythonAnalyzer) -> None:
        """Empty ruff output (no JSON) → clean result."""
        version_proc = _mock_process(returncode=0)
        ruff_proc = _mock_process(returncode=0, stdout=b"")
        loc_proc = _mock_process(returncode=0, stdout=b"300\n")

        with patch(
            "asyncio.create_subprocess_exec", side_effect=[version_proc, ruff_proc, loc_proc]
        ):
            result = await analyzer.analyze(_CLONE_DIR)

        assert result is not None
        assert result.value == 1.0

    async def test_analyze_loc_count_fails(self, analyzer: PythonAnalyzer) -> None:
        """LOC count returns 0 → density treated as 0 → score 1.0."""
        version_proc = _mock_process(returncode=0)
        ruff_proc = _mock_process(returncode=0, stdout=b"[]")
        loc_proc = _mock_process(returncode=1, stdout=b"")

        with patch(
            "asyncio.create_subprocess_exec", side_effect=[version_proc, ruff_proc, loc_proc]
        ):
            result = await analyzer.analyze(_CLONE_DIR)

        assert result is not None
        assert result.value == 1.0
