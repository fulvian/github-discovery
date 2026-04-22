"""API request/response models for the REST interface (Phase 6).

These models define the FastAPI request bodies and response wrappers.
They are compatible with FastAPI's automatic OpenAPI schema generation.

Note: The MCP interface uses its own tool parameter schemas (see mcp_spec.py).
API is a secondary consumer of the same core services (Blueprint §21.1).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field

from github_discovery.models.enums import DiscoveryChannel, DomainType, GateLevel
from github_discovery.models.scoring import RankedRepo  # noqa: TC001

# --- Pagination ---


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")


class PaginatedResponse(BaseModel):
    """Paginated response wrapper for list endpoints."""

    total_count: int = Field(ge=0, description="Total items across all pages")
    page: int = Field(ge=1, description="Current page number")
    page_size: int = Field(ge=1, description="Items per page")
    total_pages: int = Field(ge=0, description="Total number of pages")
    has_next: bool = Field(description="Whether a next page exists")
    has_prev: bool = Field(description="Whether a previous page exists")


# --- Discovery ---


class DiscoveryQuery(BaseModel):
    """Request to discover candidate repositories."""

    query: str = Field(min_length=1, description="Search query string")
    channels: list[DiscoveryChannel] = Field(
        default_factory=lambda: [DiscoveryChannel.SEARCH, DiscoveryChannel.REGISTRY],
        description="Discovery channels to use",
    )
    max_candidates: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum candidates to discover",
    )
    domain: DomainType | None = Field(
        default=None,
        description="Preferred domain filter",
    )
    session_id: str | None = Field(
        default=None,
        description="Attach to an existing session",
    )
    languages: list[str] = Field(
        default_factory=list,
        description="Filter by programming languages",
    )


class DiscoveryResponse(BaseModel):
    """Response from a discovery request."""

    job_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique job identifier for tracking",
    )
    status: str = Field(
        default="pending",
        description="Job status: pending, running, completed, failed",
    )
    pool_id: str | None = Field(default=None, description="Pool ID once discovery completes")
    total_candidates: int = Field(default=0, ge=0)
    channels_used: list[DiscoveryChannel] = Field(default_factory=list)
    session_id: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# --- Screening ---


class ScreeningRequest(BaseModel):
    """Request to screen a pool of candidates."""

    pool_id: str = Field(description="Candidate pool to screen")
    gate_level: GateLevel = Field(
        default=GateLevel.METADATA,
        description="Gate level: '1' (metadata), '2' (static), or run both",
    )
    min_gate1_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Override minimum Gate 1 score",
    )
    min_gate2_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Override minimum Gate 2 score",
    )
    session_id: str | None = Field(default=None)


class ScreeningResponse(BaseModel):
    """Response from a screening request."""

    job_id: str = Field(default_factory=lambda: str(uuid4()))
    status: str = Field(default="pending")
    pool_id: str
    gate_level: GateLevel
    total_screened: int = Field(default=0, ge=0)
    passed: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    session_id: str | None = Field(default=None)


# --- Assessment ---


class AssessmentRequest(BaseModel):
    """Request to deep-assess specific repositories.

    Hard gate (Blueprint §16.5): Only repos that passed Gate 1+2
    can be assessed. The API will reject requests for unqualified repos.
    """

    repo_urls: list[str] = Field(
        min_length=1,
        max_length=50,
        description="Repository URLs to assess (max 50)",
    )
    dimensions: list[str] = Field(
        default_factory=list,
        description="Specific dimensions to assess (empty = all 8)",
    )
    budget_tokens: int | None = Field(
        default=None,
        ge=1000,
        description="Override token budget for this assessment",
    )
    session_id: str | None = Field(default=None)


class AssessmentResponse(BaseModel):
    """Response from a deep assessment request."""

    job_id: str = Field(default_factory=lambda: str(uuid4()))
    status: str = Field(default="pending")
    total_repos: int = Field(default=0, ge=0)
    assessed: int = Field(default=0, ge=0)
    rejected_hard_gate: int = Field(
        default=0,
        ge=0,
        description="Repos rejected by hard gate (Gate 1+2 not passed)",
    )
    tokens_used: int = Field(default=0, ge=0)
    session_id: str | None = Field(default=None)


# --- Ranking ---


class RankingQuery(BaseModel):
    """Request to get ranked results."""

    domain: DomainType | None = Field(
        default=None,
        description="Filter by domain (required for meaningful ranking)",
    )
    min_confidence: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold",
    )
    min_value_score: float = Field(
        default=0.0,
        ge=0.0,
        description="Minimum value score (anti-star bias)",
    )
    max_results: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum results to return",
    )
    session_id: str | None = Field(default=None)
    pagination: PaginationParams = Field(default_factory=PaginationParams)


class RankingResponse(BaseModel):
    """Response with ranked repositories."""

    ranked_repos: list[RankedRepo] = Field(default_factory=list)
    pagination: PaginatedResponse
    domain: DomainType | None = Field(default=None)
    session_id: str | None = Field(default=None)


# --- Export ---


class ExportFormat(StrEnum):
    """Supported export formats."""

    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


class ExportRequest(BaseModel):
    """Request to export session results."""

    session_id: str = Field(description="Session to export")
    format: ExportFormat = Field(default=ExportFormat.JSON, description="Output format")
    domain: DomainType | None = Field(default=None, description="Filter by domain")
    include_details: bool = Field(
        default=False,
        description="Include full dimension breakdown and evidence",
    )


class ExportResponse(BaseModel):
    """Response from an export request."""

    download_url: str | None = Field(
        default=None,
        description="URL to download exported file",
    )
    format: ExportFormat
    total_repos: int = Field(default=0, ge=0)
    content: str | None = Field(
        default=None,
        description="Inline content (for small exports)",
    )
