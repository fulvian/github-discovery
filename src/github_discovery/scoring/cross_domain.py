"""Cross-domain comparison guard.

Prevents unfair cross-domain comparisons by emitting warnings
and normalizing scores when repos from different domains are compared.

Different domains have different quality baselines, star expectations,
and weight profiles. Direct comparison is misleading.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from github_discovery.config import ScoringSettings
from github_discovery.scoring.types import CrossDomainComparison, NormalizedScore

if TYPE_CHECKING:
    from github_discovery.models.enums import DomainType
    from github_discovery.models.scoring import ScoreResult

logger = structlog.get_logger("github_discovery.scoring.cross_domain")


_MIN_STD = 0.001
_MIN_DOMAIN_SIZE = 3
_NEAR_UNIFORM_STD = 0.05


class CrossDomainGuard:
    """Guard against unfair cross-domain comparisons.

    When cross-domain comparison is requested:
    1. Emit warning with explanation
    2. Normalize scores relative to domain mean
    3. Return results with explicit domain labels
    """

    def __init__(self, settings: ScoringSettings | None = None) -> None:
        """Initialize CrossDomainGuard with optional scoring settings."""
        self._settings = settings or ScoringSettings()

    def compare(
        self,
        results: list[ScoreResult],
    ) -> CrossDomainComparison:
        """Compare repos potentially across domains.

        If all repos are same domain → direct comparison (no warning).
        If mixed domains → normalized comparison with warning.

        Z-score normalization is skipped for domains with fewer than
        3 repos or where the standard deviation is below 0.05 (near-uniform).

        Args:
            results: ScoreResults to compare.

        Returns:
            CrossDomainComparison with warnings and normalized scores.
        """
        if not results:
            return CrossDomainComparison(
                results=[],
                is_cross_domain=False,
                warnings=["No results to compare"],
            )

        domains = {r.domain for r in results}
        is_cross_domain = len(domains) > 1

        warnings: list[str] = []
        if is_cross_domain and self._settings.cross_domain_warning:
            warnings.append(self._generate_warning(domains))

        # Compute domain summaries
        domain_summaries = self._compute_domain_summaries(results)

        # Determine if we should skip z-score normalization
        skip_domains = self._get_skip_domains(domain_summaries)
        if skip_domains and is_cross_domain and self._settings.cross_domain_warning:
            skipped_names = ", ".join(sorted(skip_domains))
            warnings.append(
                f"Z-score normalization skipped for domain(s) [{skipped_names}]: "
                "fewer than 3 repos or near-uniform scores (std < 0.05)."
            )

        # Normalize scores
        normalized = self._normalize_scores(results, domain_summaries, skip_domains)

        # Sort by normalized value_score descending
        normalized.sort(key=lambda n: (-n.normalized_value_score, n.full_name))

        # Compute confidence: fraction of domains that were normalized
        total_domains = len(domain_summaries)
        normalized_domains = total_domains - len(skip_domains)
        confidence = normalized_domains / total_domains if total_domains > 0 else 0.0

        return CrossDomainComparison(
            results=normalized,
            is_cross_domain=is_cross_domain,
            warnings=warnings,
            domain_summaries=domain_summaries,
            cross_domain_confidence=confidence,
        )

    def _normalize_scores(
        self,
        results: list[ScoreResult],
        domain_summaries: dict[str, dict[str, float]],
        skip_domains: set[str] | None = None,
    ) -> list[NormalizedScore]:
        """Normalize scores relative to domain mean.

        For each domain:
        1. If domain is in skip_domains → use original quality (no z-score)
        2. Otherwise: normalized = (quality_score - domain_mean) / domain_std + 0.5

        This centers each domain around 0.5 with relative positioning.
        """
        normalized: list[NormalizedScore] = []
        _skip = skip_domains or set()

        for r in results:
            domain_key = r.domain.value
            stats = domain_summaries.get(domain_key, {})
            mean = stats.get("mean", 0.5)
            std = stats.get("std", 0.1)

            if domain_key in _skip:
                # Skip z-score — use original quality score directly
                norm_quality = max(0.0, min(1.0, r.quality_score))
                norm_vs = max(0.0, min(1.0, r.value_score))
            else:
                # Avoid division by zero
                safe_std = std if std > _MIN_STD else 0.1

                norm_quality = (r.quality_score - mean) / safe_std + 0.5
                norm_quality = max(0.0, min(1.0, norm_quality))

                # Normalize value_score similarly
                vs_mean = stats.get("vs_mean", 0.2)
                vs_std = stats.get("vs_std", 0.05)
                safe_vs_std = vs_std if vs_std > _MIN_STD else 0.05

                norm_vs = (r.value_score - vs_mean) / safe_vs_std + 0.5
                norm_vs = max(0.0, min(1.0, norm_vs))

            normalized.append(
                NormalizedScore(
                    full_name=r.full_name,
                    domain=r.domain,
                    original_quality=r.quality_score,
                    normalized_quality=norm_quality,
                    original_value_score=r.value_score,
                    normalized_value_score=norm_vs,
                    domain_mean=mean,
                    domain_std=std,
                ),
            )

        return normalized

    @staticmethod
    def _get_skip_domains(
        domain_summaries: dict[str, dict[str, float]],
    ) -> set[str]:
        """Identify domains where z-score normalization should be skipped.

        Skip when:
        - Domain has fewer than 3 repos (N < 3)
        - Domain has near-uniform scores (std < 0.05)
        """
        skip: set[str] = set()
        for domain_key, stats in domain_summaries.items():
            count = int(stats.get("count", 0))
            std = stats.get("std", 0.0)
            if count < _MIN_DOMAIN_SIZE or std < _NEAR_UNIFORM_STD:
                skip.add(domain_key)
        return skip

    def _compute_domain_summaries(
        self,
        results: list[ScoreResult],
    ) -> dict[str, dict[str, float]]:
        """Compute per-domain statistics.

        Returns dict: {domain_value: {mean, std, count, vs_mean, vs_std}}
        """
        domain_data: dict[str, list[ScoreResult]] = {}
        for r in results:
            key = r.domain.value
            if key not in domain_data:
                domain_data[key] = []
            domain_data[key].append(r)

        summaries: dict[str, dict[str, float]] = {}
        for domain_key, domain_results in domain_data.items():
            qualities = [r.quality_score for r in domain_results]
            value_scores = [r.value_score for r in domain_results]

            n = len(qualities)
            mean_q = sum(qualities) / n
            mean_vs = sum(value_scores) / n

            std_q = (sum((q - mean_q) ** 2 for q in qualities) / n) ** 0.5 if n > 0 else 0.0
            std_vs = (sum((v - mean_vs) ** 2 for v in value_scores) / n) ** 0.5 if n > 0 else 0.0

            summaries[domain_key] = {
                "mean": mean_q,
                "std": std_q,
                "count": float(n),
                "vs_mean": mean_vs,
                "vs_std": std_vs,
            }

        return summaries

    def _generate_warning(
        self,
        domains: set[DomainType],
    ) -> str:
        """Generate human-readable warning about cross-domain comparison."""
        domain_names = ", ".join(d.value for d in sorted(domains))
        return (
            f"Cross-domain comparison detected: [{domain_names}]. "
            "Different domains have different quality baselines and scoring weights. "
            "Scores have been normalized relative to domain mean for fair comparison. "
            "Interpret results with caution."
        )
