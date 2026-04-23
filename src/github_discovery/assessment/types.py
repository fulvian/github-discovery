"""Shared types for the assessment package.

Defines RepoContent (packed repo for LLM), AssessmentContext
(pool-level context for batch assessment), and related types
for the Gate 3 deep assessment pipeline.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from github_discovery.models.candidate import RepoCandidate  # noqa: TC001
from github_discovery.models.enums import ScoreDimension
from github_discovery.models.screening import ScreeningResult  # noqa: TC001


class RepoContent(BaseModel):
    """Packed repository content ready for LLM assessment.

    Produced by RepomixAdapter from a GitHub repo URL.
    Contains the packed code content and metadata about
    the packing process (token count, file count, compression).
    """

    full_name: str = Field(description="Repository full name (owner/repo)")
    content: str = Field(default="", description="Packed repo content for LLM")
    total_files: int = Field(default=0, ge=0, description="Number of files packed")
    total_tokens: int = Field(default=0, ge=0, description="Token count of packed content")
    total_chars: int = Field(default=0, ge=0, description="Character count of packed content")
    compressed: bool = Field(
        default=False,
        description="Whether interface-mode compression was applied",
    )
    truncated: bool = Field(
        default=False,
        description="Whether content was truncated to fit token budget",
    )
    clone_url: str = Field(default="", description="URL used for cloning/packing")


class HeuristicScores(BaseModel):
    """Non-LLM heuristic scores computed from repo content.

    Provides baseline scores and fallback when LLM assessment
    fails or is skipped. These are cheap to compute (zero LLM cost).
    """

    full_name: str = Field(description="Repository full name (owner/repo)")
    file_count: int = Field(default=0, ge=0, description="Total files in packed content")
    has_tests: bool = Field(default=False, description="Whether test files were detected")
    has_ci: bool = Field(default=False, description="Whether CI config was detected")
    has_docs: bool = Field(default=False, description="Whether documentation was detected")
    has_security_policy: bool = Field(
        default=False,
        description="Whether security policy files were detected",
    )
    language_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Language → file count distribution",
    )
    structure_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Heuristic directory structure quality (0.0-1.0)",
    )
    size_category: str = Field(
        default="medium",
        description="Repo size category: tiny, small, medium, large, huge",
    )


class AssessmentContext(BaseModel):
    """Full context for an assessment operation on a pool.

    Used by the assessment orchestrator to coordinate Gate 3
    deep assessment across multiple candidates.
    """

    candidates: list[RepoCandidate] = Field(
        default_factory=list,
        description="Candidates to assess (must have passed Gate 1+2)",
    )
    screening_results: dict[str, ScreeningResult] = Field(
        default_factory=dict,
        description="Screening results keyed by full_name",
    )
    dimensions: list[ScoreDimension] = Field(
        default_factory=lambda: list(ScoreDimension),
        description="Dimensions to assess (default: all 8)",
    )
    gate3_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum Gate 3 score to pass",
    )
    session_id: str | None = Field(
        default=None,
        description="Optional session ID for cross-session workflows",
    )
    batch_mode: bool = Field(
        default=True,
        description="Whether to assess all dimensions in one LLM call",
    )


class LLMDimensionOutput(BaseModel):
    """Pydantic model for structured LLM output per dimension.

    Used as response_model with instructor for type-safe
    structured output from LLM calls.
    """

    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Assessment score (0.0-1.0)",
    )
    explanation: str = Field(
        default="",
        description="Explanation of the assessment score",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Specific observations supporting the score",
    )
    confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Assessment confidence level",
    )


class LLMBatchOutput(BaseModel):
    """Pydantic model for batch LLM output across all dimensions.

    Used as response_model with instructor for single-call
    assessment of all 8 dimensions.
    """

    dimensions: dict[str, LLMDimensionOutput] = Field(
        default_factory=dict,
        description="Per-dimension scores keyed by dimension name",
    )
    overall_explanation: str = Field(
        default="",
        description="Summary explanation of overall quality",
    )
