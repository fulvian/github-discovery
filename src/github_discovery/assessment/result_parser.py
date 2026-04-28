"""LLM response parser for Gate 3 deep assessment.

Converts raw LLM structured output (LLMDimensionOutput / LLMBatchOutput)
into the canonical DeepAssessmentResult model. Handles partial/failed
dimensions gracefully — one dimension failure doesn't prevent others.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from github_discovery.assessment.types import HeuristicFallback, HeuristicScores
from github_discovery.models.assessment import (
    DeepAssessmentResult,
    DimensionScore,
    TokenUsage,
)
from github_discovery.models.enums import DomainType, ScoreDimension
from github_discovery.models.scoring import get_domain_profile

if TYPE_CHECKING:
    from github_discovery.assessment.types import (
        HeuristicScores,
        LLMBatchOutput,
        LLMDimensionOutput,
    )

logger = structlog.get_logger(__name__)

# Minimum number of dimensions required for a valid assessment.
_MIN_DIMENSIONS_FOR_VALID = 4


class ResultParser:
    """Parses LLM structured output into DeepAssessmentResult.

    Handles:
    - Single dimension output (LLMDimensionOutput)
    - Batch output (LLMBatchOutput) across all dimensions
    - Heuristic fallback for failed/missing dimensions
    - Partial results (some dimensions may be missing)
    """

    def parse_batch(
        self,
        batch_output: LLMBatchOutput,
        full_name: str,
        commit_sha: str,
        *,
        token_usage: TokenUsage | None = None,
        heuristic_scores: HeuristicScores | None = None,
        gate3_threshold: float = 0.6,
    ) -> DeepAssessmentResult:
        """Parse batch LLM output into a complete assessment result.

        Args:
            batch_output: Structured output from batch LLM call.
            full_name: Repository full name.
            commit_sha: Commit SHA at assessment time.
            token_usage: Token usage from the LLM call.
            heuristic_scores: Heuristic fallback for missing dimensions.
            gate3_threshold: Threshold for Gate 3 pass/fail.

        Returns:
            DeepAssessmentResult with all parsed dimension scores.
        """
        dimensions: dict[ScoreDimension, DimensionScore] = {}

        for dim_name, llm_output in batch_output.dimensions.items():
            dimension = self._parse_dimension_name(dim_name)
            if dimension is None:
                logger.warning(
                    "unknown_dimension_in_output",
                    dimension_name=dim_name,
                    full_name=full_name,
                )
                continue

            dimensions[dimension] = DimensionScore(
                dimension=dimension,
                value=llm_output.score,
                explanation=llm_output.explanation,
                evidence=llm_output.evidence,
                confidence=llm_output.confidence,
                assessment_method="llm",
            )

        # Fill missing dimensions with heuristic fallback
        if heuristic_scores is not None:
            dimensions = self._fill_missing_with_heuristics(
                dimensions,
                heuristic_scores,
            )

        overall_quality = self._compute_overall_quality(dimensions)
        overall_confidence = self._compute_overall_confidence(dimensions)

        result = DeepAssessmentResult(
            full_name=full_name,
            commit_sha=commit_sha,
            dimensions=dimensions,
            overall_quality=overall_quality,
            overall_explanation=batch_output.overall_explanation,
            overall_confidence=overall_confidence,
            gate3_pass=overall_quality >= gate3_threshold,
            gate3_threshold=gate3_threshold,
            token_usage=token_usage or TokenUsage(),
        )

        logger.info(
            "batch_result_parsed",
            full_name=full_name,
            dimensions_scored=len(dimensions),
            overall_quality=overall_quality,
            gate3_pass=result.gate3_pass,
        )

        return result

    def parse_dimension(
        self,
        dimension: ScoreDimension,
        llm_output: LLMDimensionOutput,
        full_name: str,
        commit_sha: str,
        *,
        token_usage: TokenUsage | None = None,
        gate3_threshold: float = 0.6,
    ) -> DimensionScore:
        """Parse a single dimension LLM output.

        Args:
            dimension: Which dimension was assessed.
            llm_output: Structured output from per-dimension LLM call.
            full_name: Repository full name (for logging).
            commit_sha: Commit SHA (for logging).
            token_usage: Token usage (unused for single dimension).
            gate3_threshold: Threshold (unused for single dimension).

        Returns:
            DimensionScore with the parsed assessment.
        """
        return DimensionScore(
            dimension=dimension,
            value=llm_output.score,
            explanation=llm_output.explanation,
            evidence=llm_output.evidence,
            confidence=llm_output.confidence,
            assessment_method="llm",
        )

    def compose_from_dimensions(
        self,
        dimension_scores: dict[ScoreDimension, DimensionScore],
        full_name: str,
        commit_sha: str,
        *,
        overall_explanation: str = "",
        token_usage: TokenUsage | None = None,
        heuristic_scores: HeuristicScores | None = None,
        gate3_threshold: float = 0.6,
    ) -> DeepAssessmentResult:
        """Compose a full assessment result from individual dimension scores.

        Used when dimensions were assessed individually (not batch).

        Args:
            dimension_scores: Per-dimension scores from individual calls.
            full_name: Repository full name.
            commit_sha: Commit SHA at assessment time.
            overall_explanation: Summary explanation.
            token_usage: Aggregate token usage.
            heuristic_scores: Heuristic fallback for missing dimensions.
            gate3_threshold: Threshold for Gate 3 pass/fail.

        Returns:
            DeepAssessmentResult composed from individual dimensions.
        """
        # Fill missing dimensions with heuristic fallback
        dimensions = dict(dimension_scores)
        if heuristic_scores is not None:
            dimensions = self._fill_missing_with_heuristics(
                dimensions,
                heuristic_scores,
            )

        overall_quality = self._compute_overall_quality(dimensions)
        overall_confidence = self._compute_overall_confidence(dimensions)

        return DeepAssessmentResult(
            full_name=full_name,
            commit_sha=commit_sha,
            dimensions=dimensions,
            overall_quality=overall_quality,
            overall_explanation=overall_explanation,
            overall_confidence=overall_confidence,
            gate3_pass=overall_quality >= gate3_threshold,
            gate3_threshold=gate3_threshold,
            token_usage=token_usage or TokenUsage(),
        )

    def create_heuristic_fallback(
        self,
        heuristic_scores: HeuristicScores,
        full_name: str,
        commit_sha: str,
        *,
        gate3_threshold: float = 0.6,
    ) -> DeepAssessmentResult:
        """Create a heuristic-only assessment result as fallback.

        Used when LLM assessment completely fails (budget exceeded,
        API error, etc.). All dimensions are scored via heuristics
        with low confidence.

        Args:
            heuristic_scores: Heuristic analysis results.
            full_name: Repository full name.
            commit_sha: Commit SHA.
            gate3_threshold: Threshold for Gate 3 pass/fail.

        Returns:
            DeepAssessmentResult with heuristic-only scores.
        """
        base_score = heuristic_scores.structure_score

        # Map heuristic signals to approximate dimension scores
        heuristic_map: dict[ScoreDimension, float] = {
            ScoreDimension.CODE_QUALITY: base_score * 0.8,
            ScoreDimension.ARCHITECTURE: base_score * 0.7,
            ScoreDimension.TESTING: 0.6 if heuristic_scores.has_tests else 0.2,
            ScoreDimension.DOCUMENTATION: 0.6 if heuristic_scores.has_docs else 0.2,
            ScoreDimension.MAINTENANCE: base_score * 0.75,
            ScoreDimension.SECURITY: (0.5 if heuristic_scores.has_security_policy else 0.2),
            ScoreDimension.FUNCTIONALITY: base_score * 0.7,
            ScoreDimension.INNOVATION: 0.5,  # Cannot assess without LLM
        }

        # TC3: Use HeuristicFallback (cap ≤ 0.25) for confidence, not literal 0.3
        _HEURISTIC_CONFIDENCE_CAP = HeuristicFallback.confidence_cap()  # ≤ 0.25

        dimensions: dict[ScoreDimension, DimensionScore] = {}
        for dim, score in heuristic_map.items():
            dimensions[dim] = DimensionScore(
                dimension=dim,
                value=min(max(score, 0.0), 1.0),
                explanation="Heuristic fallback (LLM assessment unavailable)",
                evidence=[],
                confidence=_HEURISTIC_CONFIDENCE_CAP,
                assessment_method="heuristic",
            )

        overall_quality = self._compute_overall_quality(dimensions)

        logger.info(
            "heuristic_fallback_created",
            full_name=full_name,
            overall_quality=overall_quality,
            dimensions=len(dimensions),
        )

        return DeepAssessmentResult(
            full_name=full_name,
            commit_sha=commit_sha,
            dimensions=dimensions,
            overall_quality=overall_quality,
            overall_explanation="Assessment based on heuristic analysis only (LLM unavailable)",
            overall_confidence=_HEURISTIC_CONFIDENCE_CAP,
            degraded=True,  # All dimensions use heuristic fallback
            gate3_pass=overall_quality >= gate3_threshold,
            gate3_threshold=gate3_threshold,
        )

    def _fill_missing_with_heuristics(
        self,
        dimensions: dict[ScoreDimension, DimensionScore],
        heuristic_scores: HeuristicScores,
    ) -> dict[ScoreDimension, DimensionScore]:
        """Fill missing dimensions with heuristic-based scores."""
        result = dict(dimensions)
        base_score = heuristic_scores.structure_score

        # TC3: Use HeuristicFallback confidence cap (≤ 0.25), not literal 0.3
        _HF_CAP = HeuristicFallback.confidence_cap()

        heuristic_defaults: dict[ScoreDimension, tuple[float, str]] = {
            ScoreDimension.CODE_QUALITY: (
                base_score * 0.8,
                "No LLM assessment; heuristic estimate",
            ),
            ScoreDimension.ARCHITECTURE: (
                base_score * 0.7,
                "No LLM assessment; heuristic estimate",
            ),
            ScoreDimension.TESTING: (
                0.6 if heuristic_scores.has_tests else 0.2,
                "Based on test infrastructure detection",
            ),
            ScoreDimension.DOCUMENTATION: (
                0.6 if heuristic_scores.has_docs else 0.2,
                "Based on documentation file detection",
            ),
            ScoreDimension.MAINTENANCE: (
                base_score * 0.75,
                "No LLM assessment; heuristic estimate",
            ),
            ScoreDimension.SECURITY: (
                0.5 if heuristic_scores.has_security_policy else 0.2,
                "Based on security file detection",
            ),
            ScoreDimension.FUNCTIONALITY: (
                base_score * 0.7,
                "No LLM assessment; heuristic estimate",
            ),
            ScoreDimension.INNOVATION: (0.5, "Cannot assess without LLM"),
        }

        for dim, (score, explanation) in heuristic_defaults.items():
            if dim not in result:
                result[dim] = DimensionScore(
                    dimension=dim,
                    value=min(max(score, 0.0), 1.0),
                    explanation=explanation,
                    evidence=[],
                    confidence=_HF_CAP,
                    assessment_method="heuristic",
                )

        return result

    def _compute_overall_quality(
        self,
        dimensions: dict[ScoreDimension, DimensionScore],
    ) -> float:
        """Compute domain-weighted composite quality score.

        Uses DEFAULT_PROFILE weights for assessment phase.
        Scoring layer (Layer D) will apply domain-specific weights.
        """
        profile = get_domain_profile(DomainType.OTHER)
        total_weight = 0.0
        weighted_sum = 0.0

        for dim, dim_score in dimensions.items():
            weight = profile.dimension_weights.get(dim, 0.0)
            if weight > 0:
                weighted_sum += dim_score.value * weight
                total_weight += weight

        if total_weight == 0:
            return 0.0
        return weighted_sum / total_weight

    def _compute_overall_confidence(
        self,
        dimensions: dict[ScoreDimension, DimensionScore],
    ) -> float:
        """Compute overall confidence as weighted average of dimension confidences.

        TC4: Uses profile-based weighting (DEFAULT_PROFILE for assessment phase),
        not min(). A single heuristic fallback (conf≈0.2, low weight) won't
        defl ate overall confidence if the other 7 dimensions are LLM-based (conf≈0.7).
        """
        if not dimensions:
            return 0.0
        profile = get_domain_profile(DomainType.OTHER)
        weighted_sum = 0.0
        weight_sum = 0.0
        for dim, ds in dimensions.items():
            w = profile.dimension_weights.get(dim, 0.0)
            weighted_sum += ds.confidence * w
            weight_sum += w
        if weight_sum <= 0:
            return 0.0
        return weighted_sum / weight_sum

    def _parse_dimension_name(self, name: str) -> ScoreDimension | None:
        """Parse a dimension name string to ScoreDimension enum.

        Handles various formats from LLM output:
        - "code_quality", "Code Quality", "CODE_QUALITY"
        """
        # Normalize: lowercase, replace spaces/special chars with underscores
        normalized = name.lower().strip().replace(" ", "_").replace("-", "_")
        try:
            return ScoreDimension(normalized)
        except ValueError:
            # Try matching by value
            for dim in ScoreDimension:
                if dim.value == normalized:
                    return dim
            return None
