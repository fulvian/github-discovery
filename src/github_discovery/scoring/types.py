"""Scoring types and data structures for Layer D.

Internal types used by the scoring module. Public-facing models
(ScoreResult, RankedRepo, etc.) live in models/scoring.py.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from github_discovery.models.assessment import DeepAssessmentResult  # noqa: TC001
from github_discovery.models.candidate import RepoCandidate  # noqa: TC001
from github_discovery.models.enums import DomainType, ScoreDimension  # noqa: TC001
from github_discovery.models.scoring import DomainProfile, RankedRepo  # noqa: TC001
from github_discovery.models.screening import ScreeningResult  # noqa: TC001


class DimensionScoreInfo(BaseModel):
    """Internal representation of a dimension's score with metadata.

    Tracks not just the score value but also how it was derived,
    what confidence we have in it, and which signals contributed.
    """

    dimension: ScoreDimension = Field(description="Which evaluation dimension")
    value: float = Field(default=0.5, ge=0.0, le=1.0, description="Score value 0.0-1.0")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence in this score")
    source: str = Field(
        default="default_neutral",
        description="How the score was derived: gate3_llm, gate12_derived, default_neutral",
    )
    contributing_signals: list[str] = Field(
        default_factory=list,
        description="Which sub-scores contributed to this dimension score",
    )


class ScoringInput(BaseModel):
    """Complete input for scoring a single candidate.

    Bundles the candidate metadata with optional screening
    (Gate 1+2) and assessment (Gate 3) results.
    """

    candidate: RepoCandidate = Field(description="Repository metadata")
    screening: ScreeningResult | None = Field(
        default=None,
        description="Gate 1+2 screening result (optional)",
    )
    assessment: DeepAssessmentResult | None = Field(
        default=None,
        description="Gate 3 deep assessment (optional, only for top %)",
    )


class ScoringContext(BaseModel):
    """Context for a batch scoring operation.

    Groups multiple ScoringInput instances with optional overrides
    for domain and profile selection.
    """

    inputs: list[ScoringInput] = Field(description="Candidates to score")
    domain_override: DomainType | None = Field(
        default=None,
        description="Force all candidates to this domain",
    )
    profile_override: DomainProfile | None = Field(
        default=None,
        description="Force all candidates to use this profile",
    )
    session_id: str | None = Field(
        default=None,
        description="Session ID for cross-session workflows",
    )


class NormalizedScore(BaseModel):
    """Score normalized for cross-domain comparison.

    Normalizes quality_score relative to domain mean and standard
    deviation to enable fair cross-domain comparisons.
    """

    full_name: str = Field(description="Repository full name")
    domain: DomainType = Field(description="Repository domain type")
    original_quality: float = Field(description="Original quality score")
    normalized_quality: float = Field(description="Quality relative to domain mean")
    original_value_score: float = Field(description="Original value score")
    normalized_value_score: float = Field(description="Value score normalized")
    domain_mean: float = Field(description="Mean quality in this domain")
    domain_std: float = Field(description="Std deviation in this domain")


class CrossDomainComparison(BaseModel):
    """Result of a cross-domain comparison with warnings.

    Includes normalized scores, warnings about cross-domain
    comparison validity, and per-domain summary statistics.
    """

    results: list[NormalizedScore] = Field(description="Normalized results sorted by score")
    is_cross_domain: bool = Field(description="Whether results span multiple domains")
    warnings: list[str] = Field(default_factory=list, description="Warnings about comparison")
    domain_summaries: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Per-domain stats: {domain: {mean, std, count}}",
    )


class RankingResult(BaseModel):
    """Complete ranking result for a domain.

    Contains ranked repos, hidden gems, and metadata about
    the ranking operation.
    """

    domain: DomainType = Field(description="Domain for this ranking")
    ranked_repos: list[RankedRepo] = Field(
        default_factory=list,
        description="RankedRepo list for this domain",
    )
    total_candidates: int = Field(default=0, description="Total candidates considered")
    hidden_gems: list[RankedRepo] = Field(
        default_factory=list,
        description="Top value_score repos with low stars",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Ranking generation timestamp",
    )
    session_id: str | None = Field(
        default=None,
        description="Session ID if applicable",
    )


class FeatureStoreStats(BaseModel):
    """Statistics about the feature store."""

    total_entries: int = Field(default=0, description="Total cached entries")
    expired_entries: int = Field(default=0, description="Expired entries")
    domains: dict[str, int] = Field(
        default_factory=dict,
        description="Entry count per domain",
    )
    oldest_entry: datetime | None = Field(default=None, description="Oldest entry timestamp")
    newest_entry: datetime | None = Field(default=None, description="Newest entry timestamp")
