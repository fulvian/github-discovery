"""Custom exception hierarchy for GitHub Discovery.

Never raise bare Exception — always use the appropriate domain exception
with context (repo URL, dimension, gate level, etc.).
"""

from __future__ import annotations


class GitHubDiscoveryError(Exception):
    """Base exception for all GitHub Discovery errors."""

    def __init__(self, message: str, *, context: dict[str, object] | None = None) -> None:
        """Initialize with message and optional context dict."""
        self.context = context or {}
        super().__init__(message)

    def __str__(self) -> str:
        """Return string representation with context."""
        parts = [super().__str__()]
        if self.context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f" [{ctx_str}]")
        return "".join(parts)


# --- Domain Exceptions ---


class ConfigurationError(GitHubDiscoveryError):
    """Raised when configuration is invalid or missing."""


class DiscoveryError(GitHubDiscoveryError):
    """Raised when candidate discovery fails."""


class ScreeningError(GitHubDiscoveryError):
    """Raised when quality screening fails."""

    def __init__(
        self,
        message: str,
        *,
        gate_level: int | None = None,
        repo_url: str | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        """Initialize with gate level and repo URL context."""
        ctx = context or {}
        if gate_level is not None:
            ctx["gate_level"] = gate_level
        if repo_url is not None:
            ctx["repo_url"] = repo_url
        super().__init__(message, context=ctx)
        self.gate_level = gate_level
        self.repo_url = repo_url


class AssessmentError(GitHubDiscoveryError):
    """Raised when deep technical assessment fails."""

    def __init__(
        self,
        message: str,
        *,
        repo_url: str | None = None,
        dimension: str | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        """Initialize with repo URL and dimension context."""
        ctx = context or {}
        if repo_url is not None:
            ctx["repo_url"] = repo_url
        if dimension is not None:
            ctx["dimension"] = dimension
        super().__init__(message, context=ctx)
        self.repo_url = repo_url
        self.dimension = dimension


class ScoringError(GitHubDiscoveryError):
    """Raised when scoring or ranking fails."""

    def __init__(
        self,
        message: str,
        *,
        domain: str | None = None,
        repo_url: str | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        """Initialize with domain and repo URL context."""
        ctx = context or {}
        if domain is not None:
            ctx["domain"] = domain
        if repo_url is not None:
            ctx["repo_url"] = repo_url
        super().__init__(message, context=ctx)
        self.domain = domain
        self.repo_url = repo_url


class SessionError(GitHubDiscoveryError):
    """Raised when session management fails."""


class MCPError(GitHubDiscoveryError):
    """Raised when MCP tool execution fails."""


class RateLimitError(GitHubDiscoveryError):
    """Raised when GitHub API rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        *,
        reset_at: str | None = None,
        remaining: int | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        """Initialize with rate limit context."""
        ctx = context or {}
        if reset_at is not None:
            ctx["reset_at"] = reset_at
        if remaining is not None:
            ctx["remaining"] = remaining
        super().__init__(message, context=ctx)
        self.reset_at = reset_at
        self.remaining = remaining


class BudgetExceededError(GitHubDiscoveryError):
    """Raised when LLM token budget is exceeded."""

    def __init__(
        self,
        message: str,
        *,
        budget_type: str | None = None,
        budget_limit: int | None = None,
        budget_used: int | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        """Initialize with budget context."""
        ctx = context or {}
        if budget_type is not None:
            ctx["budget_type"] = budget_type
        if budget_limit is not None:
            ctx["budget_limit"] = budget_limit
        if budget_used is not None:
            ctx["budget_used"] = budget_used
        super().__init__(message, context=ctx)
        self.budget_type = budget_type
        self.budget_limit = budget_limit
        self.budget_used = budget_used


class HardGateViolationError(GitHubDiscoveryError):
    """Raised when hard gate enforcement prevents Gate 3 without Gate 1+2 pass."""

    def __init__(
        self,
        message: str,
        *,
        repo_url: str | None = None,
        gate_passed: int | None = None,
        gate_required: int | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        """Initialize with gate violation context."""
        ctx = context or {}
        if repo_url is not None:
            ctx["repo_url"] = repo_url
        if gate_passed is not None:
            ctx["gate_passed"] = gate_passed
        if gate_required is not None:
            ctx["gate_required"] = gate_required
        super().__init__(message, context=ctx)
        self.repo_url = repo_url
        self.gate_passed = gate_passed
        self.gate_required = gate_required


# --- GitHub API Fetch Errors ---


class GitHubFetchError(GitHubDiscoveryError):
    """Base for all GitHub API fetch errors."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        """Initialize with HTTP status code and URL context."""
        ctx = context or {}
        if status_code is not None:
            ctx["status_code"] = status_code
        if url is not None:
            ctx["url"] = url
        super().__init__(message, context=ctx)
        self.status_code = status_code
        self.url = url


class GitHubAuthError(GitHubFetchError):
    """Authentication failure (401/403)."""


class GitHubRateLimitError(GitHubFetchError):
    """Rate limit exceeded (429/403)."""

    def __init__(
        self,
        message: str = "rate limited",
        *,
        retry_after: int | None = None,
        status_code: int | None = None,
        url: str | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        """Initialize with retry_after from Retry-After header."""
        ctx = context or {}
        if retry_after is not None:
            ctx["retry_after"] = retry_after
        super().__init__(
            message,
            status_code=status_code,
            url=url,
            context=ctx,
        )
        self.retry_after = retry_after


class GitHubServerError(GitHubFetchError):
    """Server error (5xx)."""
