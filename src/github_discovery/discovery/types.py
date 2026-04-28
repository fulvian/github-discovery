"""Shared types for the discovery engine.

Defines request/response models used across discovery channels
and the orchestrator. These types avoid circular imports between
modules in the discovery package.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from github_discovery.models.candidate import RepoCandidate  # noqa: TC001
from github_discovery.models.enums import DiscoveryChannel, DomainType  # noqa: TC001


class DiscoveryQuery(BaseModel):
    """Input for a discovery pipeline query."""

    query: str = Field(
        description="Search term or topic to discover repositories for",
        examples=["static analysis python", "web framework rust"],
    )
    channels: list[DiscoveryChannel] | None = Field(
        default=None,
        description="Override discovery channels (None = use defaults from config)",
    )
    max_candidates: int = Field(
        default=500,
        ge=1,
        le=10000,
        description="Maximum number of candidates to return",
    )
    language: str | None = Field(
        default=None,
        description="Filter by programming language",
        examples=["python", "typescript"],
    )
    topics: list[str] | None = Field(
        default=None,
        description="Filter by GitHub topics",
        examples=[["testing", "static-analysis"]],
    )
    domain_hint: DomainType | None = Field(
        default=None,
        description="Hint for domain classification (pre-rank filtering)",
    )
    session_id: str | None = Field(
        default=None,
        description="Agentic session ID for cross-session continuity",
    )
    seed_urls: list[str] | None = Field(
        default=None,
        description="Seed repository URLs for expansion channels",
    )
    auto_seed: bool = Field(
        default=False,
        description=(
            "When True and seed_urls is empty, "
            "auto-discover seed repos from query (Wave H6)"
        ),
    )


class ChannelResult(BaseModel):
    """Result from a single discovery channel."""

    channel: DiscoveryChannel = Field(
        description="Which channel produced these results",
    )
    candidates: list[RepoCandidate] = Field(
        default_factory=list,
        description="Discovered repository candidates",
    )
    total_found: int = Field(
        default=0,
        ge=0,
        description="Total available results (may be > returned candidates)",
    )
    has_more: bool = Field(
        default=False,
        description="Whether more paginated results exist",
    )
    rate_limit_remaining: int | None = Field(
        default=None,
        description="API rate limit remaining after this query",
    )
    elapsed_seconds: float = Field(
        default=0.0,
        ge=0.0,
        description="Time spent on this channel in seconds",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Errors encountered during channel execution (Wave H7)",
    )


class DiscoveryResult(BaseModel):
    """Aggregated result from the discovery orchestrator."""

    pool_id: str = Field(
        description="UUID of the persisted candidate pool",
    )
    total_candidates: int = Field(
        default=0,
        ge=0,
        description="Total unique candidates after deduplication",
    )
    candidates_by_channel: dict[str, int] = Field(
        default_factory=dict,
        description="Candidate count per channel (before dedup)",
    )
    channels_used: list[DiscoveryChannel] = Field(
        default_factory=list,
        description="Channels that were actually invoked",
    )
    duplicate_count: int = Field(
        default=0,
        ge=0,
        description="Candidates found by multiple channels (removed by dedup)",
    )
    elapsed_seconds: float = Field(
        default=0.0,
        ge=0.0,
        description="Total discovery pipeline time in seconds",
    )
    session_id: str | None = Field(
        default=None,
        description="Agentic session ID if provided in query",
    )
    errors_per_channel: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Errors encountered per channel (Wave H7)",
    )
