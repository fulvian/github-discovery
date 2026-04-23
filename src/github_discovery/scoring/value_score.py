"""Anti-star bias Value Score calculation.

Formula: ValueScore = quality_score / log10(star_count + 10)

This identifies hidden gems: repos with high quality but low visibility.
Reference: Blueprint §5, §15 — anti-popularity debiasing.
"""

from __future__ import annotations

from math import log10
from typing import TYPE_CHECKING

import structlog

from github_discovery.config import ScoringSettings

if TYPE_CHECKING:
    from github_discovery.models.enums import DomainType

logger = structlog.get_logger("github_discovery.scoring.value_score")

_VERY_LOW_STAR_THRESHOLD = 50
_HIGH_STAR_THRESHOLD = 5000


class ValueScoreCalculator:
    """Anti-star bias Value Score calculation.

    The value score highlights repos where quality exceeds
    popularity: high quality_score + low stars = high value_score.

    This is the core anti-star-bias mechanism (Blueprint §15):
    stars are context only, never a primary ranking signal.
    """

    _STAR_OFFSET = 10
    _MAX_VALUE_SCORE = 1.0

    def __init__(self, settings: ScoringSettings | None = None) -> None:
        """Initialize ValueScoreCalculator with optional scoring settings."""
        self._settings = settings or ScoringSettings()
        self._hidden_gem_star_threshold = self._settings.hidden_gem_star_threshold
        self._hidden_gem_min_quality = self._settings.hidden_gem_min_quality

    def compute(self, quality_score: float, stars: int) -> float:
        """Compute Value Score with edge-case handling.

        Args:
            quality_score: Domain-weighted composite (0.0-1.0).
            stars: Star count at scoring time.

        Returns:
            Value score (0.0+). Higher = more undervalued.
        """
        if quality_score <= 0.0:
            return 0.0
        denominator = log10(stars + self._STAR_OFFSET)
        if denominator <= 0.0:
            return min(quality_score, self._MAX_VALUE_SCORE)
        return quality_score / denominator

    def is_hidden_gem(
        self,
        quality_score: float,
        stars: int,
        value_score: float,
    ) -> tuple[bool, str]:
        """Determine if repo qualifies as a hidden gem.

        Hidden gem criteria:
        - stars < hidden_gem_star_threshold
        - quality_score >= hidden_gem_min_quality
        - value_score is meaningful (> 0)

        Args:
            quality_score: Domain-weighted quality.
            stars: Star count.
            value_score: Computed value score.

        Returns:
            Tuple of (is_gem, reason).
        """
        if quality_score < self._hidden_gem_min_quality:
            return (
                False,
                f"Quality {quality_score:.2f} below threshold {self._hidden_gem_min_quality:.2f}",
            )
        if stars >= self._hidden_gem_star_threshold:
            return (
                False,
                f"Stars ({stars}) at or above threshold ({self._hidden_gem_star_threshold})",
            )
        if value_score <= 0.0:
            return (False, "Value score is zero or negative")

        return (
            True,
            f"High quality ({quality_score:.2f}) with low visibility ({stars} stars)",
        )

    def star_context(self, quality_score: float, stars: int, domain: DomainType) -> str:
        """Generate human-readable star context string.

        Args:
            quality_score: Quality score of the repo.
            stars: Star count.
            domain: Domain type for context.

        Returns:
            Human-readable context string.
        """
        if stars == 0:
            return "0 stars — new/unknown, quality assessment valuable"
        if stars < _VERY_LOW_STAR_THRESHOLD:
            return f"{stars} stars — very low visibility for this quality level"
        if stars < self._hidden_gem_star_threshold:
            return (
                f"{stars} stars — low to moderate visibility. "
                f"Quality suggests it deserves wider adoption."
            )
        if stars < _HIGH_STAR_THRESHOLD:
            return f"{stars:,} stars — moderate visibility. Quality consistent with adoption."
        return f"{stars:,} stars — high visibility. Quality should be proportionally assessed."

    def normalize_batch(
        self,
        scores: list[tuple[str, float, int]],
    ) -> list[tuple[str, float]]:
        """Normalize value scores across a batch to 0.0-1.0 range.

        Useful for cross-domain comparison where absolute value_score
        may vary significantly between domains.

        Args:
            scores: List of (full_name, quality_score, stars).

        Returns:
            List of (full_name, normalized_value_score) in [0.0, 1.0].
        """
        if not scores:
            return []

        computed: list[tuple[str, float]] = []
        for full_name, quality, stars in scores:
            vs = self.compute(quality, stars)
            computed.append((full_name, vs))

        max_vs = max(vs for _, vs in computed)
        if max_vs <= 0.0:
            return [(name, 0.0) for name, _ in computed]

        return [(name, vs / max_vs) for name, vs in computed]
