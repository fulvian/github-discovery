"""Scoring, ranking, and explainability models (Layer D).

Layer D produces the final ranked output with star-neutral ranking
(Stars are metadata only — never a primary ranking signal, never a penalty).

Key design principles:
- quality_score = pure technical assessment (Gate 1+2+3), no star consideration
- confidence = gate coverage + dimension assessment reliability
- Stars = corroboration metadata: more stars = more validation, but no score change
- Hidden gem = informational label (high quality + low stars), NOT a score modifier
- Ranking = quality_score DESC, confidence DESC (star-neutral)
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field, computed_field

from github_discovery.models.enums import DomainType, ScoreDimension

# --- Constants ---
_WEIGHT_TOLERANCE = 0.01

# Star corroboration thresholds (stars tell HOW MANY validated, not WHAT the quality is)
_CORROBORATION_UNVALIDATED = 50
_CORROBORATION_EMERGING = 500
_CORROBORATION_VALIDATED = 5000
# Hidden gem thresholds removed from model layer (T1.1).
# Single source of truth: config.py ScoringSettings (hidden_gem_star_threshold,
# hidden_gem_min_quality). ValueScoreCalculator.is_hidden_gem() is canonical.

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
    derivation_map: dict[str, list[list[float | str]]] | None = Field(
        default=None,
        description=(
            "Per-domain override for Gate 1+2 → dimension derivation mapping. "
            "Format: {dimension_name: [[sub_score_name, weight], ...]}. "
            "None = use default _DERIVATION_MAP from engine.py (T5.1)."
        ),
    )
    star_baseline: float = Field(
        default=1000.0,
        description="Expected star count for an 'established' project in this domain",
    )
    preferred_channels: list[str] = Field(
        default_factory=list,
        description="Discovery channels preferred for this domain",
    )
    activity_threshold_days: int = Field(
        default=180,
        description=(
            "Inactivity threshold in days for this domain. "
            "Repos with no push activity beyond this limit are excluded "
            "from search results. Domain-specific: SECURITY_TOOL=90, "
            "LANG_TOOL=365, default=180. (Wave H1)"
        ),
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
        description="Star count at scoring time (metadata, not used in quality scoring)",
    )

    gate1_total: float = Field(default=0.0, ge=0.0, le=1.0)
    gate2_total: float = Field(default=0.0, ge=0.0, le=1.0)
    gate3_available: bool = Field(
        default=False,
        description="Whether Gate 3 deep assessment was performed",
    )
    degraded: bool | None = Field(
        default=None,
        description=(
            "Whether Gate 3 assessment used heuristic fallbacks for any dimension "
            "(indicates degraded quality due to LLM failures or content truncation). "
            "None if no deep assessment was performed."
        ),
    )

    coverage: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description=(
            "Fraction of profile weight backed by real data (vs neutral defaults). "
            "Coverage 1.0 = all dimensions scored; 0.6 = only 60% of weight has real data."
        ),
    )
    raw_quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Quality score before low-coverage damping (for explainability)",
    )

    scored_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Scoring timestamp",
    )

    # --- Star-neutral corroboration ---

    @computed_field  # type: ignore[prop-decorator]
    @property
    def corroboration_level(self) -> str:
        """How many users have validated this repo's quality.

        Stars tell you HOW MANY people validated quality, not WHAT the quality is.
        This is informational metadata — it never changes the quality_score.
        """
        if self.stars == 0:
            return "new"
        if self.stars < _CORROBORATION_UNVALIDATED:
            return "unvalidated"
        if self.stars < _CORROBORATION_EMERGING:
            return "emerging"
        if self.stars < _CORROBORATION_VALIDATED:
            return "validated"
        return "widely_adopted"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_hidden_gem(self) -> bool:
        """Whether this repo is a hidden gem (high quality, low visibility).

        .. deprecated:: 0.2.0
            This computed_field couples a data model to business logic and
            configuration. For programmatic access, use
            ``ValueScoreCalculator.is_hidden_gem()`` instead, which accepts
            explicit thresholds.

            This field will be removed in v0.3.0. The canonical source for
            the hidden gem label is ``ValueScoreCalculator`` — this property
            exists solely for backward compatibility with MCP tools, API
            routes, and CLI output that read ``ScoreResult.is_hidden_gem``.

        This is an INFORMATIONAL LABEL — it does not affect ranking.

        Uses default ScoringSettings thresholds for backward compatibility.
        For programmatic use with custom thresholds, call
        ValueScoreCalculator.is_hidden_gem() directly.
        """
        # Lazy import to avoid circular dependency (PLC0415 suppressed)
        from github_discovery.config import ScoringSettings  # noqa: PLC0415

        settings = ScoringSettings()
        return (
            self.quality_score >= settings.hidden_gem_min_quality
            and self.stars < settings.hidden_gem_star_threshold
        )

    # --- Backward-compatible value_score (now equals quality_score) ---

    @computed_field  # type: ignore[prop-decorator]
    @property
    def value_score(self) -> float:
        """Star-neutral value score (equals quality_score).

        Previously: quality_score / log10(stars + 10) — penalized popular repos.
        Now: simply equals quality_score — stars are metadata only.

        Kept as computed_field for backward compatibility with existing
        CLI output, MCP tools, and stored FeatureStore data.
        """
        return self.quality_score


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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_hidden_gem(self) -> bool:
        """Convenience access to hidden gem label.

        .. deprecated:: 0.2.0
            See ``ScoreResult.is_hidden_gem`` for deprecation details.
            Will be removed in v0.3.0.
        """
        return self.score_result.is_hidden_gem


class ExplainabilityReport(BaseModel):
    """Explainability report for a repository's scoring.

    Every score must be explainable per feature and dimension (Blueprint §3).
    Reports provide both human-readable explanations and machine-readable
    feature breakdowns for transparency.
    """

    full_name: str = Field(description="Repository full name (owner/repo)")
    domain: DomainType = Field(description="Domain type")
    overall_quality: float = Field(ge=0.0, le=1.0, description="Overall quality score")
    value_score: float = Field(
        ge=0.0, description="Star-neutral value score (equals quality_score)"
    )

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
    gate_thresholds={"gate1": 0.5, "gate2": 0.6, "gate3": 0.6},
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
    gate_thresholds={"gate1": 0.4, "gate2": 0.5, "gate3": 0.6},
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
    gate_thresholds={"gate1": 0.5, "gate2": 0.6, "gate3": 0.6},
    star_baseline=2000.0,
    preferred_channels=["search", "dependency", "registry"],
)

BACKEND_PROFILE = DomainProfile(
    domain_type=DomainType.BACKEND,
    display_name="Backend Service",
    description="Backend services and server-side applications",
    dimension_weights={
        ScoreDimension.CODE_QUALITY: 0.15,
        ScoreDimension.ARCHITECTURE: 0.20,
        ScoreDimension.TESTING: 0.15,
        ScoreDimension.DOCUMENTATION: 0.10,
        ScoreDimension.MAINTENANCE: 0.15,
        ScoreDimension.SECURITY: 0.15,
        ScoreDimension.FUNCTIONALITY: 0.05,
        ScoreDimension.INNOVATION: 0.05,
    },
    gate_thresholds={"gate1": 0.5, "gate2": 0.6, "gate3": 0.6},
    star_baseline=1500.0,
    preferred_channels=["search", "registry", "dependency"],
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
    DomainType.BACKEND: BACKEND_PROFILE,
    # All other domains use DEFAULT_PROFILE
}


def get_domain_profile(domain: DomainType) -> DomainProfile:
    """Get the scoring profile for a domain type.

    Returns the domain-specific profile if defined,
    otherwise returns the default profile.
    """
    return DOMAIN_PROFILES.get(domain, DEFAULT_PROFILE)
