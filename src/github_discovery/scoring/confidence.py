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

if TYPE_CHECKING:
    from github_discovery.models.assessment import DeepAssessmentResult
    from github_discovery.models.enums import ScoreDimension
    from github_discovery.models.screening import ScreeningResult
    from github_discovery.scoring.types import DimensionScoreInfo

logger = structlog.get_logger("github_discovery.scoring.confidence")

# Confidence ranges per source
_SOURCE_CONFIDENCE: dict[str, float] = {
    "gate3_llm": 0.8,
    "gate12_derived": 0.4,
    "default_neutral": 0.0,
}

# Gate coverage bonus levels
_GATE_COVERAGE_BONUS = {
    "gate1_only": 0.0,
    "gate1_gate2": 0.05,
    "gate1_gate2_gate3": 0.10,
}


class ConfidenceCalculator:
    """Confidence score calculator for scoring results.

    Computes an overall confidence for a ScoreResult based on
    per-dimension confidences and gate coverage.

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
    ) -> float:
        """Compute overall confidence for a scoring result.

        Returns weighted average of dimension confidences,
        with bonus for complete gate coverage.

        Args:
            dimension_infos: Per-dimension score metadata.
            screening: Gate 1+2 results (if available).
            assessment: Gate 3 results (if available).

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

        avg_confidence = sum(dim_confidences) / len(dim_confidences)
        bonus = self.gate_coverage_bonus(screening, assessment)
        total = avg_confidence + bonus

        return max(0.0, min(1.0, total))

    def compute_dimension_confidence(
        self,
        dimension: ScoreDimension,
        source: str,
        screening: ScreeningResult | None,
        assessment: DeepAssessmentResult | None,
    ) -> float:
        """Compute confidence for a single dimension.

        Source-based confidence:
        - "gate3_llm": use LLM-reported confidence (typically 0.6-0.9)
        - "gate12_derived": 0.3-0.5 (indirect signal)
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
