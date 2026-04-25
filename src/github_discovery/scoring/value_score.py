"""Star-neutral value score and hidden gem detection.

Design principle: Stars tell you HOW MANY people validated quality,
not WHAT the quality is. Stars are metadata, not a scoring signal.

This module provides:
- Hidden gem detection: informational label (high quality + low stars)
- Star context strings: human-readable corroboration level
- Batch normalization: for optional cross-domain comparison

Stars are NEVER used to penalize or boost the quality_score.
The quality_score is a pure technical assessment from Gate 1+2+3.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from github_discovery.config import ScoringSettings

if TYPE_CHECKING:
    from github_discovery.models.enums import DomainType

logger = structlog.get_logger("github_discovery.scoring.value_score")

_VERY_LOW_STAR_THRESHOLD = 50
_HIGH_STAR_THRESHOLD = 5000


class ValueScoreCalculator:
    """Star-neutral value score and hidden gem detection.

    Stars are corroboration metadata, not a scoring signal:
    - 0 stars → "new/unknown" — quality assessment especially valuable
    - <50 stars → "unvalidated" — few users have checked
    - <500 stars → "emerging" — some validation
    - <5000 stars → "validated" — many users confirm quality
    - 5000+ stars → "widely adopted" — broad community validation

    None of these levels change the quality_score. They are informational only.
    """

    def __init__(self, settings: ScoringSettings | None = None) -> None:
        """Initialize ValueScoreCalculator with optional scoring settings."""
        self._settings = settings or ScoringSettings()
        self._hidden_gem_star_threshold = self._settings.hidden_gem_star_threshold
        self._hidden_gem_min_quality = self._settings.hidden_gem_min_quality

    def compute(self, quality_score: float, stars: int) -> float:
        """Compute value score — star-neutral (equals quality_score).

        This is kept for backward compatibility. The value_score now
        simply equals the quality_score. Stars are not considered.

        Args:
            quality_score: Domain-weighted composite (0.0-1.0).
            stars: Star count at scoring time (ignored).

        Returns:
            quality_score unchanged (star-neutral).
        """
        _ = stars  # explicitly unused — star-neutral design
        return max(quality_score, 0.0)

    def is_hidden_gem(
        self,
        quality_score: float,
        stars: int,
        value_score: float,
    ) -> tuple[bool, str]:
        """Determine if repo qualifies as a hidden gem.

        Hidden gem is an INFORMATIONAL LABEL, not a score modifier.
        It flags repos where quality exceeds visibility.

        Criteria:
        - stars < hidden_gem_star_threshold
        - quality_score >= hidden_gem_min_quality

        Args:
            quality_score: Domain-weighted quality.
            stars: Star count.
            value_score: Computed value score (unused, kept for API compat).

        Returns:
            Tuple of (is_gem, reason).
        """
        _ = value_score  # unused in star-neutral design

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

        return (
            True,
            f"High quality ({quality_score:.2f}) with low visibility ({stars} stars)",
        )

    def star_context(self, quality_score: float, stars: int, domain: DomainType) -> str:
        """Generate human-readable corroboration context string.

        Args:
            quality_score: Quality score of the repo.
            stars: Star count.
            domain: Domain type for context.

        Returns:
            Human-readable context string describing corroboration level.
        """
        if stars == 0:
            return "0 stars — new/unknown, quality assessment is the primary signal"
        if stars < _VERY_LOW_STAR_THRESHOLD:
            return f"{stars} stars — unvalidated: few users have tested this"
        if stars < self._hidden_gem_star_threshold:
            return (
                f"{stars} stars — emerging community interest. "
                f"Quality assessment complements limited user validation."
            )
        if stars < _HIGH_STAR_THRESHOLD:
            return (
                f"{stars:,} stars — validated by moderate community. "
                f"Quality score is corroborated by user adoption."
            )
        return (
            f"{stars:,} stars — widely adopted. "
            f"Quality score is strongly corroborated by broad usage."
        )

    def normalize_batch(
        self,
        scores: list[tuple[str, float, int]],
    ) -> list[tuple[str, float]]:
        """Normalize quality scores across a batch to 0.0-1.0 range.

        Note: Stars are NOT used in normalization. This is purely
        quality-based normalization for cross-domain comparison.

        Args:
            scores: List of (full_name, quality_score, stars).
                Stars are accepted for API compatibility but unused.

        Returns:
            List of (full_name, normalized_quality_score) in [0.0, 1.0].
        """
        if not scores:
            return []

        computed: list[tuple[str, float]] = []
        for full_name, quality, _stars in scores:
            computed.append((full_name, max(quality, 0.0)))

        max_q = max(q for _, q in computed)
        if max_q <= 0.0:
            return [(name, 0.0) for name, _ in computed]

        return [(name, q / max_q) for name, q in computed]
