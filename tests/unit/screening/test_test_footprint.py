"""Tests for test footprint analyzer."""

from __future__ import annotations

from datetime import UTC, datetime

from github_discovery.models import screening as screening_models
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel
from github_discovery.screening.test_footprint import TestFootprintAnalyzer
from github_discovery.screening.types import RepoContext


def _make_context(contents: list[str]) -> RepoContext:
    """Helper to build a RepoContext with given contents."""
    candidate = RepoCandidate(
        full_name="test/repo",
        url="https://github.com/test/repo",
        html_url="https://github.com/test/repo",
        api_url="https://api.github.com/repos/test/repo",
        owner_login="test",
        created_at=datetime(2023, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        source_channel=DiscoveryChannel.SEARCH,
    )
    return RepoContext(candidate=candidate, repo_contents=contents)


class TestTestFootprintAnalyzer:
    """Tests for TestFootprintAnalyzer."""

    def test_test_dir_detected(self) -> None:
        """Test directory presence detected."""
        ctx = _make_context(
            [
                "src/main.py",
                "tests/test_main.py",
                "tests/__init__.py",
            ]
        )
        result = TestFootprintAnalyzer().score(ctx)

        assert isinstance(result, screening_models.TestFootprintScore)
        assert result.details["has_test_dir"] is True

    def test_pytest_config_detected(self) -> None:
        """pytest.ini detected as test framework."""
        ctx = _make_context(
            [
                "pytest.ini",
                "tests/test_main.py",
            ]
        )
        result = TestFootprintAnalyzer().score(ctx)

        assert "pytest" in result.details["test_frameworks"]

    def test_no_test_infrastructure(self) -> None:
        """No test infrastructure → score 0.0."""
        ctx = _make_context(
            [
                "src/main.py",
                "README.md",
                "LICENSE",
            ]
        )
        result = TestFootprintAnalyzer().score(ctx)

        assert result.value == 0.0
        assert result.details["has_test_dir"] is False
        assert result.details["test_frameworks"] == []

    def test_test_file_ratio_calculated(self) -> None:
        """Test file ratio correctly calculated."""
        ctx = _make_context(
            [
                "src/main.py",
                "src/utils.py",
                "tests/test_main.py",
                "tests/test_utils.py",
            ]
        )
        result = TestFootprintAnalyzer().score(ctx)

        # 2 test files / 4 total = 0.5
        assert result.details["test_file_ratio"] == 0.5

    def test_jest_config_detected(self) -> None:
        """jest.config.js detected as test framework."""
        ctx = _make_context(
            [
                "jest.config.js",
                "src/index.ts",
                "__tests__/main.test.ts",
            ]
        )
        result = TestFootprintAnalyzer().score(ctx)

        assert "jest" in result.details["test_frameworks"]
        assert result.details["has_test_dir"] is True

    def test_details_report_signals(self) -> None:
        """Details dict contains all expected signals."""
        ctx = _make_context(
            [
                "tests/conftest.py",
                "tests/test_main.py",
                "tests/test_utils.py",
                "src/main.py",
                "pytest.ini",
            ]
        )
        result = TestFootprintAnalyzer().score(ctx)

        assert "has_test_dir" in result.details
        assert "test_frameworks" in result.details
        assert "test_file_ratio" in result.details
        assert "has_conftest" in result.details

        assert result.details["has_test_dir"] is True
        assert result.details["has_conftest"] is True
        assert "pytest" in result.details["test_frameworks"]

    def test_full_score(self) -> None:
        """All signals present → score 1.0."""
        ctx = _make_context(
            [
                "tests/test_a.py",
                "tests/test_b.py",
                "tests/test_c.py",
                "tests/conftest.py",
                "pytest.ini",
                "src/a.py",
            ]
        )
        result = TestFootprintAnalyzer().score(ctx)

        # test_dir=0.3, test_config=0.3, ratio>0.1=0.2, ratio>0.3=0.2 → 1.0
        assert result.value == 1.0

    def test_spec_dir_detected(self) -> None:
        """'spec' directory detected as test directory."""
        ctx = _make_context(
            [
                "spec/app_spec.rb",
                "lib/app.rb",
            ]
        )
        result = TestFootprintAnalyzer().score(ctx)

        assert result.details["has_test_dir"] is True

    def test_vitest_detected(self) -> None:
        """vitest.config.ts detected as framework."""
        ctx = _make_context(
            [
                "vitest.config.ts",
                "__tests__/main.test.ts",
            ]
        )
        result = TestFootprintAnalyzer().score(ctx)

        assert "vitest" in result.details["test_frameworks"]

    def test_pyproject_toml_pytest_heuristic(self) -> None:
        """pyproject.toml + test dir → pytest inferred."""
        ctx = _make_context(
            [
                "pyproject.toml",
                "tests/test_main.py",
            ]
        )
        result = TestFootprintAnalyzer().score(ctx)

        assert "pytest" in result.details["test_frameworks"]
