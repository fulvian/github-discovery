"""Tests for CI/CD detection and scoring."""

from __future__ import annotations

from datetime import UTC, datetime

from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel
from github_discovery.models.screening import CiCdScore
from github_discovery.screening.ci_cd import CiCdDetector
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


class TestCiCdDetector:
    """Tests for CiCdDetector."""

    def test_github_actions_detected(self) -> None:
        """GitHub Actions workflows detected → score 1.0."""
        ctx = _make_context(
            [
                ".github/workflows/ci.yml",
                ".github/workflows/release.yml",
                "src/main.py",
            ]
        )
        result = CiCdDetector().score(ctx)

        assert isinstance(result, CiCdScore)
        assert result.value == 1.0
        assert result.details["has_github_actions"] is True
        assert result.details["workflow_count"] == 2

    def test_travis_detected(self) -> None:
        """Travis CI config detected → score 0.7."""
        ctx = _make_context([".travis.yml", "README.md"])
        result = CiCdDetector().score(ctx)

        assert result.value == 0.7
        assert result.details["has_github_actions"] is False
        assert "travis" in result.details["ci_systems"]

    def test_no_ci(self) -> None:
        """No CI config → score 0.0."""
        ctx = _make_context(["README.md", "src/main.py"])
        result = CiCdDetector().score(ctx)

        assert result.value == 0.0
        assert result.details["has_github_actions"] is False
        assert result.details["workflow_count"] == 0
        assert result.details["ci_systems"] == ""

    def test_multiple_ci_systems(self) -> None:
        """Multiple CI systems → bonus +0.1, capped at 1.0."""
        ctx = _make_context(
            [
                ".github/workflows/ci.yml",
                ".travis.yml",
            ]
        )
        result = CiCdDetector().score(ctx)

        # GitHub Actions (1.0) + bonus for multiple (0.1) = capped 1.0
        assert result.value == 1.0
        assert len(result.details["ci_systems"].split(", ")) == 2

    def test_ci_details_list_systems(self) -> None:
        """Details correctly list detected CI systems."""
        ctx = _make_context(
            [
                ".github/workflows/test.yml",
                ".circleci/config.yml",
            ]
        )
        result = CiCdDetector().score(ctx)

        systems = result.details["ci_systems"]
        assert "github_actions" in systems
        assert "circleci" in systems

    def test_workflow_count(self) -> None:
        """Workflow count correctly tallies .yml/.yaml files."""
        ctx = _make_context(
            [
                ".github/workflows/ci.yml",
                ".github/workflows/release.yml",
                ".github/workflows/docs.yml",
                ".github/workflows/README.md",  # not a workflow
            ]
        )
        result = CiCdDetector().score(ctx)

        assert result.details["workflow_count"] == 3

    def test_circleci_detected(self) -> None:
        """CircleCI config detected → score 0.7."""
        ctx = _make_context([".circleci/config.yml"])
        result = CiCdDetector().score(ctx)

        assert result.value == 0.7
        assert "circleci" in result.details["ci_systems"]

    def test_gitlab_ci_detected(self) -> None:
        """GitLab CI config detected → score 0.7."""
        ctx = _make_context([".gitlab-ci.yml"])
        result = CiCdDetector().score(ctx)

        assert result.value == 0.7
        assert "gitlab_ci" in result.details["ci_systems"]

    def test_jenkins_detected(self) -> None:
        """Jenkinsfile detected → score 0.7."""
        ctx = _make_context(["Jenkinsfile"])
        result = CiCdDetector().score(ctx)

        assert result.value == 0.7
        assert "jenkins" in result.details["ci_systems"]

    def test_non_github_actions_multiple(self) -> None:
        """Two non-GitHub CI systems → 0.7 + 0.1 bonus."""
        ctx = _make_context([".travis.yml", "Jenkinsfile"])
        result = CiCdDetector().score(ctx)

        assert result.value == 0.8
