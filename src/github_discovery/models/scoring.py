"""Scoring, ranking, and explainability models (Layer D).

Layer D produces the final ranked output with anti-star bias
(Stars are context only — never primary ranking signal).

Key formulas:
- ValueScore = quality_score / log10(stars + 10)  (Blueprint §5)
- Ranking is intra-domain: no unfair cross-domain comparison
- Explainability: every score is explainable per feature and dimension
"""

from __future__ import annotations

from datetime import UTC, datetime
from math import log10

from pydantic import BaseModel, Field, computed_field

from github_discovery.models.enums import DomainType, ScoreDimension

# --- Constants ---
_WEIGHT_TOLERANCE = 0.01

# --- Domain Profile ---


class DomainProfile(BaseModel):
    """Domain-specific weight profile for scoring.

    Each domain has different quality expectations and weight profiles
    (Blueprint §10). For example, CLI tools weight testing higher,
    while ML libraries weight innovation higher.

    dimension_weights must sum to 1.0 (validated at runtime).
    gate_thresholds define minimum scores per gate for this domain.
    """

    domain_type: DomainType = Field(description="Which domain this profile covers")
    display_name: str = Field(description="Human-readable domain name")
    description: str = Field(default="", description="What this domain covers")

    dimension_weights: dict[ScoreDimension, float] = Field(
        description="Per-dimension weights (must sum to 1.0)",
    )
    gate_thresholds: dict[str, float] = Field(
        default_factory=lambda: {"gate1": 0.4, "gate2": 0.5, "gate3": 0.6},
        description="Minimum pass scores per gate for this domain",
    )
    star_baseline: float = Field(
        default=1000.0,
        description="Expected star count for an 'established' project in this domain",
    )
    preferred_channels: list[str] = Field(
        default_factory=list,
        description="Discovery channels preferred for this domain",
    )

    def validate_weights(self) -> bool:
        """Check that dimension weights sum to approximately 1.0."""
        total = sum(self.dimension_weights.values())
        return abs(total - 1.0) < _WEIGHT_TOLERANCE


# --- Scoring ---


class ScoreResult(BaseModel):
    """Composite scoring result for a repository.

    Combines Gate 1 + Gate 2 + Gate 3 results into a final
    multi-dimensional quality score with confidence tracking.
    """

    full_name: str = Field(description="Repository full name (owner/repo)")
    commit_sha: str = Field(default="", description="Commit SHA at scoring time")
    domain: DomainType = Field(
        default=DomainType.OTHER,
        description="Domain type used for weighting",
    )

    quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Domain-weighted composite quality score",
    )
    dimension_scores: dict[ScoreDimension, float] = Field(
        default_factory=dict,
        description="Per-dimension score values (0.0-1.0)",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence in the scoring result",
    )

    stars: int = Field(
        default=0,
        ge=0,
        description="Star count at scoring time (for ValueScore computation)",
    )

    gate1_total: float = Field(default=0.0, ge=0.0, le=1.0)
    gate2_total: float = Field(default=0.0, ge=0.0, le=1.0)
    gate3_available: bool = Field(
        default=False,
        description="Whether Gate 3 deep assessment was performed",
    )

    scored_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Scoring timestamp",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def value_score(self) -> float:
        """Anti-star bias Value Score.

        Formula: quality_score / log10(stars + 10)

        Repos with high quality and low stars get high value scores.
        Repos with high quality and high stars get moderate value scores.
        This identifies hidden gems that star-based ranking misses.

        Reference: Blueprint §5, §15 — anti-popularity debiasing.
        """
        if self.quality_score <= 0.0:
            return 0.0
        return self.quality_score / log10(self.stars + 10)


class RankedRepo(BaseModel):
    """A repository with its ranking position and scores.

    Ranking is intra-domain: positions are relative to other repos
    in the same DomainType. Cross-domain comparison requires
    explicit normalization and a warning.
    """

    rank: int = Field(ge=1, description="Ranking position within domain")
    full_name: str = Field(description="Repository full name (owner/repo)")
    domain: DomainType = Field(description="Domain type for this ranking")
    score_result: ScoreResult = Field(description="Complete scoring result")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def value_score(self) -> float:
        """Convenience access to value score."""
        return self.score_result.value_score

    @computed_field  # type: ignore[prop-decorator]
    @property
    def quality_score(self) -> float:
        """Convenience access to quality score."""
        return self.score_result.quality_score

    @computed_field  # type: ignore[prop-decorator]
    @property
    def stars(self) -> int:
        """Convenience access to star count."""
        return self.score_result.stars


class ExplainabilityReport(BaseModel):
    """Explainability report for a repository's scoring.

    Every score must be explainable per feature and dimension (Blueprint §3).
    Reports provide both human-readable explanations and machine-readable
    feature breakdowns for transparency.
    """

    full_name: str = Field(description="Repository full name (owner/repo)")
    domain: DomainType = Field(description="Domain type")
    overall_quality: float = Field(ge=0.0, le=1.0, description="Overall quality score")
    value_score: float = Field(ge=0.0, description="Anti-star bias value score")

    dimension_breakdown: dict[str, dict[str, object]] = Field(
        default_factory=dict,
        description="Per-dimension breakdown: {dimension: {score, weight, explanation, evidence}}",
    )

    strengths: list[str] = Field(
        default_factory=list,
        description="Key strengths identified (top 3-5 features)",
    )
    weaknesses: list[str] = Field(
        default_factory=list,
        description="Key weaknesses identified (top 3-5)",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recommendations for improvement",
    )

    star_context: str = Field(
        default="",
        description=(
            "Star count context (e.g., '42 stars — low visibility for this quality level')"
        ),
    )
    hidden_gem_indicator: bool = Field(
        default=False,
        description="Whether this repo is identified as a hidden gem",
    )
    hidden_gem_reason: str = Field(
        default="",
        description="Why this repo is/isn't a hidden gem",
    )

    compared_to_star_baseline: str = Field(
        default="",
        description="How this repo compares to star-based ranking expectation",
    )

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence in the assessment",
    )

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Report generation timestamp",
    )


# --- Predefined Domain Profiles ---


LIBRARY_PROFILE = DomainProfile(
    domain_type=DomainType.LIBRARY,
    display_name="Library",
    description="General-purpose libraries",
    dimension_weights={
        ScoreDimension.CODE_QUALITY: 0.20,
        ScoreDimension.ARCHITECTURE: 0.15,
        ScoreDimension.TESTING: 0.15,
        ScoreDimension.DOCUMENTATION: 0.15,
        ScoreDimension.MAINTENANCE: 0.15,
        ScoreDimension.SECURITY: 0.10,
        ScoreDimension.FUNCTIONALITY: 0.05,
        ScoreDimension.INNOVATION: 0.05,
    },
    star_baseline=500.0,
    preferred_channels=["search", "registry", "awesome_list"],
)

CLI_PROFILE = DomainProfile(
    domain_type=DomainType.CLI,
    display_name="CLI Tool",
    description="Command-line tools",
    dimension_weights={
        ScoreDimension.CODE_QUALITY: 0.15,
        ScoreDimension.ARCHITECTURE: 0.10,
        ScoreDimension.TESTING: 0.20,
        ScoreDimension.DOCUMENTATION: 0.10,
        ScoreDimension.MAINTENANCE: 0.20,
        ScoreDimension.SECURITY: 0.10,
        ScoreDimension.FUNCTIONALITY: 0.10,
        ScoreDimension.INNOVATION: 0.05,
    },
    star_baseline=300.0,
    preferred_channels=["search", "registry", "awesome_list"],
)

DEVOPS_PROFILE = DomainProfile(
    domain_type=DomainType.DEVOPS_TOOL,
    display_name="DevOps Tool",
    description="DevOps and infrastructure tools",
    dimension_weights={
        ScoreDimension.CODE_QUALITY: 0.15,
        ScoreDimension.ARCHITECTURE: 0.15,
        ScoreDimension.TESTING: 0.20,
        ScoreDimension.DOCUMENTATION: 0.10,
        ScoreDimension.MAINTENANCE: 0.15,
        ScoreDimension.SECURITY: 0.15,
        ScoreDimension.FUNCTIONALITY: 0.05,
        ScoreDimension.INNOVATION: 0.05,
    },
    star_baseline=2000.0,
    preferred_channels=["search", "dependency", "registry"],
)

DEFAULT_PROFILE = DomainProfile(
    domain_type=DomainType.OTHER,
    display_name="Other",
    description="Default profile for uncategorized repositories",
    dimension_weights={
        ScoreDimension.CODE_QUALITY: 0.20,
        ScoreDimension.ARCHITECTURE: 0.15,
        ScoreDimension.TESTING: 0.15,
        ScoreDimension.DOCUMENTATION: 0.10,
        ScoreDimension.MAINTENANCE: 0.15,
        ScoreDimension.SECURITY: 0.10,
        ScoreDimension.FUNCTIONALITY: 0.10,
        ScoreDimension.INNOVATION: 0.05,
    },
    star_baseline=1000.0,
)

DOMAIN_PROFILES: dict[DomainType, DomainProfile] = {
    DomainType.LIBRARY: LIBRARY_PROFILE,
    DomainType.CLI: CLI_PROFILE,
    DomainType.DEVOPS_TOOL: DEVOPS_PROFILE,
    # All other domains use DEFAULT_PROFILE
}


def get_domain_profile(domain: DomainType) -> DomainProfile:
    """Get the scoring profile for a domain type.

    Returns the domain-specific profile if defined,
    otherwise returns the default profile.
    """
    return DOMAIN_PROFILES.get(domain, DEFAULT_PROFILE)
