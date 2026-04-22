"""Repository candidate models for the discovery pipeline.

RepoCandidate is the central model that flows through all gates:
Gate 0 (discovery) → Gate 1 (metadata screening) → Gate 2 (static/security)
→ Gate 3 (deep assessment) → Layer D (scoring/ranking).

Stars are context only, never a primary scoring signal (Blueprint §3).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from github_discovery.models.enums import CandidateStatus, DiscoveryChannel, DomainType

_ACTIVE_THRESHOLD_DAYS = 365


class RepoCandidate(BaseModel):
    """A GitHub repository candidate for quality evaluation.

    Fields are derived from GitHub REST API repository endpoint.
    Stars are included as context only — they must never be used
    as a primary ranking signal (Blueprint §3, §15).

    This model is immutable after creation: pipeline stages add
    results via separate models (MetadataScreenResult, etc.)
    linked by `full_name` and `commit_sha`.
    """

    # --- Identity ---
    full_name: str = Field(
        description="Repository full name (owner/repo)",
        examples=["python/cpython", "pallets/flask"],
    )
    url: str = Field(
        description="GitHub repository URL",
        examples=["https://github.com/python/cpython"],
    )
    html_url: str = Field(
        description="GitHub HTML URL",
        examples=["https://github.com/python/cpython"],
    )
    api_url: str = Field(
        description="GitHub API URL for this repository",
        examples=["https://api.github.com/repos/python/cpython"],
    )

    # --- Description & Classification ---
    description: str = Field(
        default="",
        description="Repository description",
    )
    language: str | None = Field(
        default=None,
        description="Primary programming language",
        examples=["Python", "TypeScript", "Rust"],
    )
    languages: dict[str, int] = Field(
        default_factory=dict,
        description="Language breakdown {name: bytes_of_code}",
    )
    topics: list[str] = Field(
        default_factory=list,
        description="Repository topics/tags",
    )
    domain: DomainType = Field(
        default=DomainType.OTHER,
        description="Inferred domain type for domain-specific scoring",
    )

    # --- Context Signals (NOT primary ranking criteria) ---
    stars: int = Field(
        default=0,
        ge=0,
        description="Star count (CONTEXT ONLY — never primary signal)",
    )
    forks_count: int = Field(
        default=0,
        ge=0,
        description="Fork count (context signal)",
    )
    watchers_count: int = Field(
        default=0,
        ge=0,
        description="Watcher count (context signal)",
    )
    subscribers_count: int = Field(
        default=0,
        ge=0,
        description="Subscriber count (context signal)",
    )

    # --- Activity Signals ---
    open_issues_count: int = Field(
        default=0,
        ge=0,
        description="Number of open issues",
    )
    created_at: datetime = Field(
        description="Repository creation timestamp",
    )
    updated_at: datetime = Field(
        description="Last update timestamp",
    )
    pushed_at: datetime | None = Field(
        default=None,
        description="Last push timestamp",
    )

    # --- Repository Metadata ---
    license_info: dict[str, object] | None = Field(
        default=None,
        description="License information from GitHub API (spdx_id, name, url)",
    )
    default_branch: str = Field(
        default="main",
        description="Default branch name",
    )
    size_kb: int = Field(
        default=0,
        ge=0,
        description="Repository size in kilobytes",
    )
    archived: bool = Field(
        default=False,
        description="Whether the repository is archived",
    )
    disabled: bool = Field(
        default=False,
        description="Whether the repository is disabled",
    )
    is_fork: bool = Field(
        default=False,
        description="Whether this is a fork",
    )
    is_template: bool = Field(
        default=False,
        description="Whether this is a template repository",
    )
    has_issues: bool = Field(
        default=True,
        description="Whether issues are enabled",
    )
    has_wiki: bool = Field(
        default=True,
        description="Whether wiki is enabled",
    )
    has_pages: bool = Field(
        default=False,
        description="Whether GitHub Pages is enabled",
    )
    has_discussions: bool = Field(
        default=False,
        description="Whether discussions are enabled",
    )

    # --- Organization / Owner ---
    owner_login: str = Field(
        description="Repository owner login",
    )
    owner_type: str = Field(
        default="User",
        description="Owner type (User or Organization)",
    )

    # --- Pipeline State ---
    source_channel: DiscoveryChannel = Field(
        description="Discovery channel that found this candidate",
    )
    discovery_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Preliminary score from discovery (Gate 0)",
    )
    discovered_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when this candidate was discovered",
    )
    commit_sha: str = Field(
        default="",
        description="Latest commit SHA (for dedup and caching)",
    )
    status: CandidateStatus = Field(
        default=CandidateStatus.DISCOVERED,
        description="Current pipeline status of this candidate",
    )

    @property
    def owner_name(self) -> str:
        """Extract owner from full_name."""
        return self.full_name.split("/")[0] if "/" in self.full_name else self.full_name

    @property
    def repo_name(self) -> str:
        """Extract repo name from full_name."""
        return self.full_name.split("/")[1] if "/" in self.full_name else self.full_name

    @property
    def is_archived_or_disabled(self) -> bool:
        """Check if repo should be excluded from evaluation."""
        return self.archived or self.disabled

    @property
    def is_active(self) -> bool:
        """Check if repo has recent activity (within last 365 days)."""
        if self.pushed_at is None:
            return False
        now = datetime.now(UTC)
        delta = (now - self.pushed_at).days
        return delta <= _ACTIVE_THRESHOLD_DAYS


class CandidatePool(BaseModel):
    """A pool of discovered repository candidates.

    Created by the discovery orchestrator (Phase 2), consumed
    by screening (Phase 3) and assessment (Phase 4).
    """

    pool_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique pool identifier",
    )
    query: str = Field(
        default="",
        description="Original discovery query",
    )
    channels_used: list[DiscoveryChannel] = Field(
        default_factory=list,
        description="Discovery channels that contributed to this pool",
    )
    candidates: list[RepoCandidate] = Field(
        default_factory=list,
        description="Pool of discovered candidates",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Pool creation timestamp",
    )
    session_id: str | None = Field(
        default=None,
        description="Associated session ID for cross-session workflows",
    )

    @property
    def total_count(self) -> int:
        """Total number of candidates in pool."""
        return len(self.candidates)

    @property
    def unique_full_names(self) -> set[str]:
        """Unique repository full names in pool."""
        return {c.full_name for c in self.candidates}

    @property
    def domain_distribution(self) -> dict[str, int]:
        """Count of candidates per domain type."""
        distribution: dict[str, int] = {}
        for c in self.candidates:
            key = c.domain.value
            distribution[key] = distribution.get(key, 0) + 1
        return distribution
