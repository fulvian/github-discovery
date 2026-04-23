"""Tests for code complexity metrics via scc subprocess."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel, DomainType
from github_discovery.models.screening import ComplexityScore
from github_discovery.screening.complexity import ComplexityAnalyzer
from github_discovery.screening.types import SubprocessResult


def _make_candidate(languages: dict[str, int] | None = None) -> RepoCandidate:
    """Build a test RepoCandidate."""
    return RepoCandidate(
        full_name="test-org/test-repo",
        url="https://github.com/test-org/test-repo",
        html_url="https://github.com/test-org/test-repo",
        api_url="https://api.github.com/repos/test-org/test-repo",
        description="Test repo",
        language="Python",
        languages=languages or {"Python": 45000},
        domain=DomainType.LIBRARY,
        stars=100,
        created_at=datetime(2023, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        owner_login="test-org",
        source_channel=DiscoveryChannel.SEARCH,
    )


def _scc_output(total_code: int, n_files: int = 100, complexity: float = 500.0) -> str:
    """Build scc JSON output with specified LOC count."""
    return json.dumps(
        {
            "Python": {
                "Name": "Python",
                "Code": total_code,
                "Comment": 1000,
                "Blank": 500,
                "Complexity": complexity,
                "Files": n_files,
                "Lines": total_code + 1500,
            },
        }
    )


def _scc_multi_language_output() -> str:
    """Build scc JSON output with 6+ languages."""
    data = {}
    for lang in ["Python", "JavaScript", "TypeScript", "Go", "Rust", "Ruby"]:
        data[lang] = {
            "Name": lang,
            "Code": 5000,
            "Comment": 500,
            "Blank": 200,
            "Complexity": 100,
            "Files": 20,
            "Lines": 5700,
        }
    return json.dumps(data)


def _make_runner(stdout: str, returncode: int = 0, stderr: str = "") -> AsyncMock:
    """Build a mock SubprocessRunner."""
    runner = AsyncMock()
    runner.run = AsyncMock(
        return_value=SubprocessResult(returncode=returncode, stdout=stdout, stderr=stderr),
    )
    return runner


class TestComplexityAnalyzer:
    """Tests for ComplexityAnalyzer."""

    async def test_small_project(self) -> None:
        """scc with 5K LOC → value=0.7."""
        runner = _make_runner(_scc_output(5000))
        analyzer = ComplexityAnalyzer(subprocess_runner=runner)

        result = await analyzer.score(_make_candidate(), clone_dir="/tmp/repo")  # noqa: S108

        assert isinstance(result, ComplexityScore)
        assert result.value == 0.7
        assert result.confidence == 1.0

    async def test_medium_project(self) -> None:
        """scc with 50K LOC → value=1.0."""
        runner = _make_runner(_scc_output(50000))
        analyzer = ComplexityAnalyzer(subprocess_runner=runner)

        result = await analyzer.score(_make_candidate(), clone_dir="/tmp/repo")  # noqa: S108

        assert result.value == 1.0

    async def test_large_project(self) -> None:
        """scc with 200K LOC → value=0.8."""
        runner = _make_runner(_scc_output(200000))
        analyzer = ComplexityAnalyzer(subprocess_runner=runner)

        result = await analyzer.score(_make_candidate(), clone_dir="/tmp/repo")  # noqa: S108

        assert result.value == 0.8

    async def test_scc_not_available(self) -> None:
        """FileNotFoundError → fallback with confidence=0.3."""
        runner = _make_runner(
            stdout="",
            returncode=-1,
            stderr="Command not found: scc",
        )
        analyzer = ComplexityAnalyzer(subprocess_runner=runner)

        result = await analyzer.score(_make_candidate(), clone_dir="/tmp/repo")  # noqa: S108

        assert result.value == 0.5
        assert result.confidence == 0.3
        assert result.details.get("source") == "fallback"

    async def test_no_clone_available(self) -> None:
        """No clone_dir → fallback score."""
        analyzer = ComplexityAnalyzer(subprocess_runner=AsyncMock())

        result = await analyzer.score(_make_candidate(), clone_dir=None)

        assert result.value == 0.5
        assert result.confidence == 0.3

    async def test_multi_language(self) -> None:
        """6 languages → fragmentation penalty applied."""
        runner = _make_runner(_scc_multi_language_output())
        analyzer = ComplexityAnalyzer(subprocess_runner=runner)

        result = await analyzer.score(_make_candidate(), clone_dir="/tmp/repo")  # noqa: S108

        # 30K LOC → would be 0.7 (<10K), but total is 30000 (Python alone 5000
        # but the test data has 6 langs with 5000 each = 30000 LOC)
        # 30000 is between 10K and 100K → value=1.0, minus fragmentation = 0.9
        # Actually, total LOC = 6 * 5000 = 30000 → between 10K and 100K → 1.0
        # 6 languages > 5 → penalty 0.1 → 0.9
        assert result.value == 0.9

    async def test_json_parsing(self) -> None:
        """Verify scc output parsing extracts correct values."""
        runner = _make_runner(_scc_output(12000, n_files=85, complexity=450.0))
        analyzer = ComplexityAnalyzer(subprocess_runner=runner)

        result = await analyzer.score(_make_candidate(), clone_dir="/tmp/repo")  # noqa: S108

        assert result.details["total_loc"] == 12000
        assert result.details["file_count"] == 85
        assert result.details["avg_complexity"] == pytest.approx(450.0 / 85)
        assert result.details["source"] == "scc"

    async def test_details_report_metrics(self) -> None:
        """Details include total_loc, languages, file_count, source."""
        runner = _make_runner(_scc_output(50000))
        analyzer = ComplexityAnalyzer(subprocess_runner=runner)

        result = await analyzer.score(_make_candidate(), clone_dir="/tmp/repo")  # noqa: S108

        assert "total_loc" in result.details
        assert "languages" in result.details
        assert "file_count" in result.details
        assert result.details["source"] == "scc"

    async def test_no_runner_no_clone(self) -> None:
        """No runner and no clone → fallback score."""
        analyzer = ComplexityAnalyzer()

        result = await analyzer.score(_make_candidate())

        assert result.value == 0.5
        assert result.confidence == 0.3
