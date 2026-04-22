"""Tests for custom exception hierarchy."""

from __future__ import annotations

from github_discovery.exceptions import (
    AssessmentError,
    BudgetExceededError,
    ConfigurationError,
    GitHubDiscoveryError,
    HardGateViolationError,
    MCPError,
    RateLimitError,
    ScoringError,
    ScreeningError,
    SessionError,
)


class TestExceptionHierarchy:
    """Test exception hierarchy and context."""

    def test_base_exception_with_context(self) -> None:
        """Base exception includes context in string representation."""
        exc = GitHubDiscoveryError("test error", context={"key": "value"})
        assert "test error" in str(exc)
        assert "key=value" in str(exc)

    def test_base_exception_without_context(self) -> None:
        """Base exception works without context."""
        exc = GitHubDiscoveryError("test error")
        assert "test error" in str(exc)

    def test_screening_error_gate_context(self) -> None:
        """ScreeningError includes gate level and repo URL."""
        exc = ScreeningError(
            "Gate 1 failed",
            gate_level=1,
            repo_url="https://github.com/user/repo",
        )
        assert exc.gate_level == 1
        assert exc.repo_url == "https://github.com/user/repo"
        assert "gate_level=1" in str(exc)

    def test_hard_gate_violation(self) -> None:
        """HardGateViolationError captures gate violation context."""
        exc = HardGateViolationError(
            "Cannot proceed to Gate 3",
            repo_url="https://github.com/user/repo",
            gate_passed=1,
            gate_required=2,
        )
        assert exc.gate_passed == 1
        assert exc.gate_required == 2
        assert "gate_passed=1" in str(exc)

    def test_budget_exceeded_error(self) -> None:
        """BudgetExceededError captures budget context."""
        exc = BudgetExceededError(
            "Token budget exceeded",
            budget_type="daily",
            budget_limit=500000,
            budget_used=510000,
        )
        assert exc.budget_type == "daily"
        assert exc.budget_limit == 500000

    def test_inheritance_chain(self) -> None:
        """All domain exceptions inherit from GitHubDiscoveryError."""
        assert issubclass(ConfigurationError, GitHubDiscoveryError)
        assert issubclass(ScreeningError, GitHubDiscoveryError)
        assert issubclass(AssessmentError, GitHubDiscoveryError)
        assert issubclass(ScoringError, GitHubDiscoveryError)
        assert issubclass(RateLimitError, GitHubDiscoveryError)
        assert issubclass(HardGateViolationError, GitHubDiscoveryError)
        assert issubclass(SessionError, GitHubDiscoveryError)
        assert issubclass(MCPError, GitHubDiscoveryError)

    def test_assessment_error_with_dimension(self) -> None:
        """AssessmentError includes repo_url and dimension."""
        exc = AssessmentError(
            "Assessment failed",
            repo_url="https://github.com/user/repo",
            dimension="code_quality",
        )
        assert exc.repo_url == "https://github.com/user/repo"
        assert exc.dimension == "code_quality"
        assert "dimension=code_quality" in str(exc)

    def test_scoring_error_with_domain(self) -> None:
        """ScoringError includes domain and repo_url."""
        exc = ScoringError(
            "Ranking failed",
            domain="library",
            repo_url="https://github.com/user/repo",
        )
        assert exc.domain == "library"

    def test_rate_limit_error(self) -> None:
        """RateLimitError captures reset_at and remaining."""
        exc = RateLimitError(
            "Rate limit exceeded",
            reset_at="2026-04-22T15:00:00Z",
            remaining=0,
        )
        assert exc.reset_at == "2026-04-22T15:00:00Z"
        assert exc.remaining == 0
