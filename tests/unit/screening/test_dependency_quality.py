"""Tests for dependency management quality scorer."""

from __future__ import annotations

from github_discovery.models.candidate import RepoCandidate
from github_discovery.screening.dependency_quality import DependencyQualityScorer
from github_discovery.screening.types import RepoContext


class TestDependencyQuality:
    """Tests for DependencyQualityScorer."""

    def test_python_lockfile_detected(self, sample_candidate: RepoCandidate) -> None:
        """Python lockfile (poetry.lock) is detected and scored."""
        ctx = RepoContext(
            candidate=sample_candidate,
            repo_contents=["pyproject.toml", "poetry.lock", "README.md"],
        )
        scorer = DependencyQualityScorer()
        result = scorer.score(ctx)

        assert result.details["has_lockfile"] is True
        assert "poetry.lock" in result.details["lockfiles_found"]
        assert result.value > 0.0

    def test_javascript_lockfile_detected(self, sample_candidate: RepoCandidate) -> None:
        """JavaScript lockfile (package-lock.json) is detected and scored."""
        js_candidate = sample_candidate.model_copy(update={"language": "JavaScript"})
        ctx = RepoContext(
            candidate=js_candidate,
            repo_contents=["package.json", "package-lock.json", "README.md"],
        )
        scorer = DependencyQualityScorer()
        result = scorer.score(ctx)

        assert result.details["has_lockfile"] is True
        assert "package-lock.json" in result.details["lockfiles_found"]
        assert result.value > 0.0

    def test_dependabot_config_detected(self, sample_repo_context: RepoContext) -> None:
        """Dependabot configuration file is detected."""
        scorer = DependencyQualityScorer()
        result = scorer.score(sample_repo_context)

        assert result.details["has_dependabot"] is True
        assert result.value > 0.0

    def test_renovate_config_detected(self, sample_candidate: RepoCandidate) -> None:
        """Renovate configuration file is detected."""
        ctx = RepoContext(
            candidate=sample_candidate,
            repo_contents=["renovate.json", "package.json"],
        )
        scorer = DependencyQualityScorer()
        result = scorer.score(ctx)

        assert result.details["has_renovate"] is True
        assert result.value > 0.0

    def test_no_dependency_management(self, sample_candidate: RepoCandidate) -> None:
        """No dependency management signals produces low score."""
        ctx = RepoContext(
            candidate=sample_candidate,
            repo_contents=["README.md", "main.py"],
        )
        scorer = DependencyQualityScorer()
        result = scorer.score(ctx)

        assert result.details["has_lockfile"] is False
        assert result.details["has_dependabot"] is False
        assert result.details["has_renovate"] is False
        assert result.value == 0.0

    def test_multi_ecosystem_lockfiles(self, sample_candidate: RepoCandidate) -> None:
        """Lockfiles from multiple ecosystems get a bonus."""
        ctx = RepoContext(
            candidate=sample_candidate,
            repo_contents=[
                "pyproject.toml",
                "poetry.lock",
                "package.json",
                "package-lock.json",
                ".github/dependabot.yml",
            ],
        )
        scorer = DependencyQualityScorer()
        result = scorer.score(ctx)

        assert result.details["has_lockfile"] is True
        assert len(result.details["lockfiles_found"]) >= 2
        assert result.details["multi_ecosystem"] is True
        # Multi-ecosystem + lockfile + dependabot should cap at 1.0
        assert result.value <= 1.0

    def test_details_report_signals(self, sample_repo_context: RepoContext) -> None:
        """Score details contain all expected signal keys."""
        scorer = DependencyQualityScorer()
        result = scorer.score(sample_repo_context)

        assert "has_lockfile" in result.details
        assert "lockfiles_found" in result.details
        assert "has_dependabot" in result.details
        assert "has_renovate" in result.details
        assert "multi_ecosystem" in result.details
        assert isinstance(result.details["lockfiles_found"], str)
