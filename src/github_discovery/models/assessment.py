"""Deep assessment models for Gate 3 (LLM-based evaluation).

Gate 3 is the expensive deep assessment — only for top percentile
candidates that passed Gate 1 + Gate 2. Uses LLM structured output
across 8 evaluation dimensions (Blueprint §7).

Budget control (Blueprint §16.5):
- Maximum token budget per day and per repo
- Timeout and early-stop on repos too large
- Mandatory caching by commit SHA
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from github_discovery.models.enums import ScoreDimension


class DimensionScore(BaseModel):
    """Score for a single evaluation dimension.

    Each dimension has a value (0.0-1.0), an explanation of the
    score, supporting evidence (specific observations from the code),
    and a confidence indicator for the assessment quality.
    """

    dimension: ScoreDimension = Field(description="Which evaluation dimension")
    value: float = Field(ge=0.0, le=1.0, description="Score value 0.0-1.0")
    explanation: str = Field(
        default="",
        description="LLM-generated explanation of the score",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Specific observations supporting the score",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Assessment confidence (higher = more reliable)",
    )
    assessment_method: str = Field(
        default="llm",
        description="How this score was derived: llm, heuristic, static_analysis",
    )


class TokenUsage(BaseModel):
    """Token usage tracking for LLM budget control."""

    prompt_tokens: int = Field(default=0, ge=0, description="Prompt tokens consumed")
    completion_tokens: int = Field(default=0, ge=0, description="Completion tokens consumed")
    total_tokens: int = Field(default=0, ge=0, description="Total tokens consumed")
    model_used: str = Field(default="", description="LLM model identifier")
    provider: str = Field(default="", description="LLM provider name")


class DeepAssessmentResult(BaseModel):
    """Gate 3 — Deep technical assessment result.

    Contains dimension scores for all 8 evaluation dimensions (Blueprint §7),
    plus overall assessment metadata including explanation, confidence,
    and token usage for budget tracking.

    Hard gate enforcement: this result should only exist for candidates
    that passed Gate 1 + Gate 2 (enforced by the assessment orchestrator).
    """

    full_name: str = Field(description="Repository full name (owner/repo)")
    commit_sha: str = Field(default="", description="Commit SHA at assessment time")

    dimensions: dict[ScoreDimension, DimensionScore] = Field(
        default_factory=dict,
        description="Per-dimension scores (keyed by ScoreDimension enum)",
    )

    overall_quality: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Weighted composite quality score across all dimensions",
    )
    overall_explanation: str = Field(
        default="",
        description="Summary explanation of overall quality assessment",
    )
    overall_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall assessment confidence (lowest dimension confidence)",
    )

    gate3_pass: bool = Field(
        default=False,
        description="Whether candidate passed Gate 3 quality threshold",
    )
    gate3_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Threshold applied for Gate 3 pass/fail",
    )

    token_usage: TokenUsage = Field(
        default_factory=TokenUsage,
        description="Token budget tracking for this assessment",
    )
    assessed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Assessment completion timestamp",
    )
    assessment_duration_seconds: float = Field(
        default=0.0,
        ge=0.0,
        description="Duration of the assessment in seconds",
    )
    cached: bool = Field(
        default=False,
        description="Whether this result was loaded from cache (dedup by SHA)",
    )

    @property
    def dimensions_assessed(self) -> int:
        """Number of dimensions with actual scores."""
        return len(self.dimensions)

    @property
    def expected_dimensions(self) -> int:
        """Expected number of dimensions (Blueprint §7: 8)."""
        return len(ScoreDimension)

    @property
    def completeness_ratio(self) -> float:
        """Ratio of assessed dimensions to expected dimensions."""
        if self.expected_dimensions == 0:
            return 0.0
        return self.dimensions_assessed / self.expected_dimensions

    def get_dimension_score(self, dimension: ScoreDimension) -> DimensionScore | None:
        """Get score for a specific dimension."""
        return self.dimensions.get(dimension)

    def compute_overall_confidence(self) -> float:
        """Compute overall confidence as minimum of dimension confidences."""
        if not self.dimensions:
            return 0.0
        return min(ds.confidence for ds in self.dimensions.values())
