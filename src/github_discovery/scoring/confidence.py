"""Confidence score calculator for scoring results.

Confidence reflects how reliable the scoring result is, based on:
- Data completeness: how many dimensions have actual data vs defaults
- Signal quality: Gate 3 LLM (high) vs Gate 1+2 derived (medium) vs default (low)
- Assessment depth: which gates were completed

Reference: Blueprint §7 — confidence indicators per dimension.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from github_discovery.models.enums import ScoreDimension

if TYPE_CHECKING:
    from github_discovery.models.assessment import DeepAssessmentResult
    from github_discovery.models.scoring import DomainProfile
    from github_discovery.models.screening import ScreeningResult
    from github_discovery.scoring.types import DimensionScoreInfo

logger = structlog.get_logger("github_discovery.scoring.confidence")

# Confidence ranges per source (fallback when no dimension-specific value)
_SOURCE_CONFIDENCE: dict[str, float] = {
    "gate3_llm": 0.8,
    "gate12_derived": 0.4,
    "default_neutral": 0.0,
}

# Per-dimension confidence when derived from Gate 1+2 (T2.3).
# Dimensions with empty _DERIVATION_MAP get 0.0 (not derivable).
# Higher values indicate stronger causal link between sub-scores and dimension.
_DIMENSION_CONFIDENCE_FROM_GATE12: dict[ScoreDimension, float] = {
    ScoreDimension.TESTING: 0.55,  # strong mapping (test_footprint direct)
    ScoreDimension.MAINTENANCE: 0.50,  # multiple contributing sub-scores
    ScoreDimension.SECURITY: 0.50,  # well-structured mapping
    ScoreDimension.DOCUMENTATION: 0.40,  # hygiene + release_discipline
    ScoreDimension.CODE_QUALITY: 0.40,  # revised mapping (complexity + test)
    ScoreDimension.ARCHITECTURE: 0.0,  # empty derivation map (T2.1)
    ScoreDimension.FUNCTIONALITY: 0.0,  # not derivable from metadata
    ScoreDimension.INNOVATION: 0.0,  # not derivable from metadata
}

# Gate coverage bonus levels
_GATE_COVERAGE_BONUS = {
    "gate1_only": 0.0,
    "gate1_gate2": 0.05,
    "gate1_gate2_gate3": 0.10,
}


# Minimum profile weight to be considered "critical" for the
# missing-dimension penalty. Dimensions with weight ≥ this
# threshold that have confidence 0.0 trigger a penalty.
_CRITICAL_WEIGHT_THRESHOLD = 0.15


class ConfidenceCalculator:
    """Confidence score calculator for scoring results.

    Computes an overall confidence for a ScoreResult based on
    per-dimension confidences weighted by profile dimension weights,
    with bonus for complete gate coverage and penalty for missing
    critical dimensions.

    Expected ranges:
    - No data at all: 0.00
    - Solo Gate 1: 0.25-0.40
    - Gate 1+2, no Gate 3: 0.35-0.55
    - Gate 1+2+3 (partial dims): 0.50-0.70
    - Gate 1+2+3 (all 8 dims): 0.65-0.90
    """

    def compute(
        self,
        dimension_infos: dict[ScoreDimension, DimensionScoreInfo],
        screening: ScreeningResult | None = None,
        assessment: DeepAssessmentResult | None = None,
        profile: DomainProfile | None = None,
    ) -> float:
        """Compute overall confidence for a scoring result.

        Returns weighted average of dimension confidences (using
        profile weights), with bonus for complete gate coverage
        and penalty for missing critical dimensions.

        Args:
            dimension_infos: Per-dimension score metadata.
            screening: Gate 1+2 results (if available).
            assessment: Gate 3 results (if available).
            profile: Domain profile for weight-aware confidence.

        Returns:
            Overall confidence (0.0-1.0).
        """
        if not dimension_infos:
            return 0.0

        dim_confidences = [
            self.compute_dimension_confidence(
                info.dimension,
                info.source,
                screening,
                assessment,
            )
            for info in dimension_infos.values()
        ]

        if profile is not None:
            # Weighted average using profile weights (T2.2)
            weighted_conf_sum = 0.0
            weight_sum = 0.0
            for info, per_dim in zip(
                dimension_infos.values(),
                dim_confidences,
                strict=False,
            ):
                w = profile.dimension_weights.get(info.dimension, 0.0)
                weighted_conf_sum += w * per_dim
                weight_sum += w
            avg_confidence = weighted_conf_sum / weight_sum if weight_sum > 0 else 0.0
        else:
            # Fallback: unweighted average (backward compatibility)
            avg_confidence = sum(dim_confidences) / len(dim_confidences)

        bonus = self.gate_coverage_bonus(screening, assessment)
        penalty = self._missing_critical_penalty(dimension_infos, profile)
        total = avg_confidence + bonus - penalty

        return max(0.0, min(1.0, total))

    @staticmethod
    def _missing_critical_penalty(
        dimension_infos: dict[ScoreDimension, DimensionScoreInfo],
        profile: DomainProfile | None,
    ) -> float:
        """Penalty for dimensions with high profile weight but zero confidence.

        If any dimension with profile weight ≥ 0.15 has confidence ≤ 0.0,
        apply a 0.10 penalty to overall confidence.
        """
        if profile is None:
            return 0.0
        for dim, info in dimension_infos.items():
            w = profile.dimension_weights.get(dim, 0.0)
            if w >= _CRITICAL_WEIGHT_THRESHOLD and info.confidence <= 0.0:
                return 0.10
        return 0.0

    def compute_dimension_confidence(
        self,
        dimension: ScoreDimension,
        source: str,
        screening: ScreeningResult | None,
        assessment: DeepAssessmentResult | None,
    ) -> float:
        """Compute confidence for a single dimension.

        Source-based confidence with per-dimension tuning:
        - "gate3_llm": use LLM-reported confidence (typically 0.6-0.9)
        - "gate12_derived": per-dimension value from _DIMENSION_CONFIDENCE_FROM_GATE12
        - "default_neutral": 0.0 (no data)

        Args:
            dimension: The score dimension.
            source: How the score was derived.
            screening: Gate 1+2 results.
            assessment: Gate 3 results.

        Returns:
            Confidence for this dimension (0.0-1.0).
        """
        if source == "gate3_llm" and assessment is not None:
            dim_score = assessment.get_dimension_score(dimension)
            if dim_score is not None and dim_score.confidence > 0.0:
                return dim_score.confidence
            return _SOURCE_CONFIDENCE["gate3_llm"]

        if source == "gate12_derived":
            return _DIMENSION_CONFIDENCE_FROM_GATE12.get(dimension, 0.4)

        return _SOURCE_CONFIDENCE.get(source, 0.0)

    def gate_coverage_bonus(
        self,
        screening: ScreeningResult | None,
        assessment: DeepAssessmentResult | None,
    ) -> float:
        """Bonus for having completed more gates.

        - Gate 1 only: +0.0
        - Gate 1+2: +0.05
        - Gate 1+2+3: +0.10

        Args:
            screening: Gate 1+2 results.
            assessment: Gate 3 results.

        Returns:
            Bonus value (0.0, 0.05, or 0.10).
        """
        has_gate1 = screening is not None and screening.gate1 is not None
        has_gate2 = screening is not None and screening.gate2 is not None
        has_assessment = assessment is not None

        if has_gate1 and has_gate2 and has_assessment:
            return _GATE_COVERAGE_BONUS["gate1_gate2_gate3"]
        if has_gate1 and has_gate2:
            return _GATE_COVERAGE_BONUS["gate1_gate2"]
        return _GATE_COVERAGE_BONUS["gate1_only"]
