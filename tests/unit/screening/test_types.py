"""Tests for screening shared types."""

from __future__ import annotations

from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import GateLevel
from github_discovery.screening.types import RepoContext, ScreeningContext, SubprocessResult


class TestRepoContext:
    """Tests for RepoContext model."""

    def test_create_with_defaults(self, sample_candidate: RepoCandidate) -> None:
        """RepoContext can be created with just a candidate."""
        ctx = RepoContext(candidate=sample_candidate)
        assert ctx.candidate.full_name == "test-org/test-repo"
        assert ctx.repo_metadata == {}
        assert ctx.repo_contents == []
        assert ctx.recent_releases == []
        assert ctx.recent_commits == []
        assert ctx.recent_issues == []
        assert ctx.recent_prs == []
        assert ctx.languages == {}
        assert ctx.topics == []

    def test_create_full(self, sample_repo_context: RepoContext) -> None:
        """RepoContext can be created with all fields populated."""
        assert sample_repo_context.candidate.full_name == "test-org/test-repo"
        assert len(sample_repo_context.repo_contents) > 0
        assert len(sample_repo_context.recent_releases) == 10
        assert len(sample_repo_context.recent_commits) == 30
        assert len(sample_repo_context.recent_issues) == 30
        assert len(sample_repo_context.recent_prs) == 30
        assert "Python" in sample_repo_context.languages

    def test_model_dump_json_roundtrip(self, sample_repo_context: RepoContext) -> None:
        """RepoContext survives JSON serialization round-trip."""
        json_str = sample_repo_context.model_dump_json()
        restored = RepoContext.model_validate_json(json_str)
        assert restored.candidate.full_name == sample_repo_context.candidate.full_name
        assert len(restored.recent_releases) == len(sample_repo_context.recent_releases)


class TestScreeningContext:
    """Tests for ScreeningContext model."""

    def test_create_with_defaults(self) -> None:
        """ScreeningContext can be created with minimal args."""
        ctx = ScreeningContext(pool_id="pool-123")
        assert ctx.pool_id == "pool-123"
        assert ctx.candidates == []
        assert ctx.gate_level == GateLevel.METADATA
        assert ctx.min_gate1_score == 0.4
        assert ctx.min_gate2_score == 0.5
        assert ctx.session_id is None

    def test_custom_thresholds(self) -> None:
        """ScreeningContext respects custom thresholds."""
        ctx = ScreeningContext(
            pool_id="pool-123",
            min_gate1_score=0.6,
            min_gate2_score=0.7,
            gate_level=GateLevel.STATIC_SECURITY,
        )
        assert ctx.min_gate1_score == 0.6
        assert ctx.min_gate2_score == 0.7
        assert ctx.gate_level == GateLevel.STATIC_SECURITY


class TestSubprocessResult:
    """Tests for SubprocessResult model."""

    def test_success_result(self) -> None:
        """SubprocessResult for a successful execution."""
        result = SubprocessResult(returncode=0, stdout="hello", stderr="")
        assert result.returncode == 0
        assert result.stdout == "hello"
        assert result.stderr == ""
        assert result.timed_out is False

    def test_failure_result(self) -> None:
        """SubprocessResult for a failed execution."""
        result = SubprocessResult(returncode=1, stdout="", stderr="error occurred")
        assert result.returncode == 1
        assert result.stderr == "error occurred"

    def test_timeout_result(self) -> None:
        """SubprocessResult for a timed out execution."""
        result = SubprocessResult(
            returncode=-1,
            stdout="",
            stderr="Command timed out after 60s",
            timed_out=True,
        )
        assert result.timed_out is True
        assert result.returncode == -1

    def test_not_found_result(self) -> None:
        """SubprocessResult for command not found."""
        result = SubprocessResult(
            returncode=-1,
            stdout="",
            stderr="Command not found: gitleaks",
        )
        assert result.returncode == -1
