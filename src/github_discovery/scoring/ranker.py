"""Intra-domain ranking engine.

Ranks repos within a single domain by value_score.
Cross-domain comparison requires explicit normalization + warning.

Properties:
- Deterministic: same inputs → same ranking (alphabetical tie-breaking)
- Stable: small score changes → small rank changes
- Intra-domain: separate ranking per DomainType
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from github_discovery.config import ScoringSettings
from github_discovery.models.scoring import RankedRepo, ScoreResult
from github_discovery.scoring.types import RankingResult
from github_discovery.scoring.value_score import ValueScoreCalculator

if TYPE_CHECKING:
    from github_discovery.models.enums import DomainType

logger = structlog.get_logger("github_discovery.scoring.ranker")

_MIN_REPOS_FOR_TOP_PERCENTILE = 4


class Ranker:
    """Intra-domain ranking engine.

    Ranks repos within a single domain by value_score descending.
    Tie-breaking is deterministic: quality_score descending, then full_name ascending.
    """

    def __init__(self, settings: ScoringSettings | None = None) -> None:
        """Initialize Ranker with optional scoring settings."""
        self._settings = settings or ScoringSettings()
        self._value_calc = ValueScoreCalculator(self._settings)

    def rank(
        self,
        results: list[ScoreResult],
        domain: DomainType,
        *,
        min_confidence: float | None = None,
        min_value_score: float = 0.0,
        max_results: int | None = None,
    ) -> RankingResult:
        """Rank repos within a domain.

        Steps:
        1. Filter by domain, min_confidence, min_value_score
        2. Sort by value_score (descending)
        3. Assign rank positions (1-based)
        4. Identify hidden gems
        5. Return RankingResult

        Args:
            results: Scored repos to rank.
            domain: Domain to rank within.
            min_confidence: Minimum confidence to include (default from settings).
            min_value_score: Minimum value_score to include.
            max_results: Limit results (None = all).

        Returns:
            RankingResult with ranked repos and hidden gems.
        """
        confidence_threshold = (
            min_confidence if min_confidence is not None else self._settings.min_confidence
        )

        # Filter
        filtered = [
            r
            for r in results
            if r.domain == domain
            and r.confidence >= confidence_threshold
            and r.value_score >= min_value_score
        ]

        # Sort deterministically
        sorted_results = sorted(filtered, key=self._sort_key)

        # Apply max_results limit
        if max_results is not None:
            sorted_results = sorted_results[:max_results]

        # Assign ranks
        ranked_repos: list[RankedRepo] = []
        for i, result in enumerate(sorted_results, start=1):
            ranked_repos.append(
                RankedRepo(
                    rank=i,
                    full_name=result.full_name,
                    domain=domain,
                    score_result=result,
                ),
            )

        # Identify hidden gems
        hidden_gems = self._identify_hidden_gems(ranked_repos, domain)

        return RankingResult(
            domain=domain,
            ranked_repos=ranked_repos,
            total_candidates=len(results),
            hidden_gems=hidden_gems,
            generated_at=datetime.now(UTC),
        )

    def rank_multi_domain(
        self,
        results: list[ScoreResult],
        *,
        min_confidence: float | None = None,
    ) -> dict[DomainType, RankingResult]:
        """Rank repos across all domains (separate rankings).

        Returns a dict of RankingResult keyed by DomainType.
        Each domain has its own independent ranking.
        """
        domains: set[DomainType] = {r.domain for r in results}
        ranking_map: dict[DomainType, RankingResult] = {}

        for domain in domains:
            ranking_map[domain] = self.rank(
                results,
                domain,
                min_confidence=min_confidence,
            )

        return ranking_map

    def _sort_key(self, result: ScoreResult) -> tuple[float, float, int, str]:
        """Deterministic sort key for ranking.

        Primary: value_score (descending → negate)
        Secondary: quality_score (descending → negate)
        Tertiary: seeded hash for deterministic tie-breaking (descending → negate)
        Quaternary: full_name (ascending → alphabetical)

        The seeded hash ensures that repos with identical value_score and
        quality_score are ordered consistently based on ``ranking_seed``,
        but differently across different seeds. This is more useful than
        pure alphabetical for producing varied rankings when experimenting
        with different seed values.
        """
        seeded_hash = hash((self._settings.ranking_seed, result.full_name))
        return (-result.value_score, -result.quality_score, -seeded_hash, result.full_name)

    def _identify_hidden_gems(
        self,
        ranked: list[RankedRepo],
        domain: DomainType,
    ) -> list[RankedRepo]:
        """Identify hidden gems from ranked list.

        Hidden gem criteria:
        - stars < hidden_gem_star_threshold
        - quality_score >= hidden_gem_min_quality
        - value_score in top 25% of domain (if enough repos)
        """
        if not ranked:
            return []

        threshold_stars = self._settings.hidden_gem_star_threshold
        min_quality = self._settings.hidden_gem_min_quality

        # Compute top 25% threshold for value_score
        all_vs = [r.value_score for r in ranked]
        if len(all_vs) >= _MIN_REPOS_FOR_TOP_PERCENTILE:
            sorted_vs = sorted(all_vs, reverse=True)
            top_25_idx = max(1, len(sorted_vs) // 4)
            top_25_vs = sorted_vs[top_25_idx - 1]
        else:
            top_25_vs = 0.0  # With few repos, don't filter by value_score

        gems: list[RankedRepo] = []
        for repo in ranked:
            if (
                repo.stars < threshold_stars
                and repo.quality_score >= min_quality
                and repo.value_score >= top_25_vs
            ):
                is_gem, _ = self._value_calc.is_hidden_gem(
                    repo.quality_score,
                    repo.stars,
                    repo.value_score,
                )
                if is_gem:
                    gems.append(repo)

        return gems
