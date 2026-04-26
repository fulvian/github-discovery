"""Intra-domain ranking engine.

Ranks repos within a single domain by quality_score (star-neutral).
Cross-domain comparison requires explicit normalization + warning.

Properties:
- Deterministic: same inputs → same ranking (alphabetical tie-breaking)
- Stable: small score changes → small rank changes
- Intra-domain: separate ranking per DomainType
- Star-neutral: stars are metadata, not a ranking signal
"""

from __future__ import annotations

import hashlib
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

    Ranks repos within a single domain by quality_score descending.
    Stars are metadata only — they never affect ranking order.
    Tie-breaking is deterministic: confidence descending, then full_name ascending.
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
        2. Sort by quality_score (descending), confidence (descending)
        3. Assign rank positions (1-based)
        4. Identify hidden gems (informational labels)
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
        """Deterministic sort key for ranking (star-neutral).

        Primary: quality_score (descending → negate)
        Secondary: confidence (descending → negate)
        Tertiary: seeded blake2b hash for deterministic tie-breaking (descending → negate)
        Quaternary: full_name (ascending → alphabetical)

        Stars are NOT part of the sort key — ranking is star-neutral.

        Uses hashlib.blake2b instead of built-in hash() for cross-process
        determinism (PEP 456: PYTHONHASHSEED randomizes built-in hash).
        """
        return (
            -result.quality_score,
            -result.confidence,
            -self._seeded_hash(result.full_name),
            result.full_name,
        )

    def _seeded_hash(self, full_name: str) -> int:
        """Deterministic hash using blake2b (cross-process reproducible).

        Unlike built-in hash(), this is independent of PYTHONHASHSEED
        and CPython version. blake2b is in stdlib since Python 3.6.
        """
        payload = f"{self._settings.ranking_seed}:{full_name}".encode()
        digest = hashlib.blake2b(payload, digest_size=8).digest()
        return int.from_bytes(digest, "big", signed=False)

    def _identify_hidden_gems(
        self,
        ranked: list[RankedRepo],
        domain: DomainType,
    ) -> list[RankedRepo]:
        """Identify hidden gems from ranked list (star-neutral).

        Hidden gem is an INFORMATIONAL LABEL — it does not affect ranking.
        It flags repos where quality exceeds visibility.

        Criteria:
        - stars < hidden_gem_star_threshold
        - quality_score >= hidden_gem_min_quality
        - quality_score in top 25% of domain (if enough repos)
        """
        if not ranked:
            return []

        threshold_stars = self._settings.hidden_gem_star_threshold
        min_quality = self._settings.hidden_gem_min_quality

        # Compute top 25% threshold for quality_score
        all_qs = [r.quality_score for r in ranked]
        if len(all_qs) >= _MIN_REPOS_FOR_TOP_PERCENTILE:
            sorted_qs = sorted(all_qs, reverse=True)
            top_25_idx = max(1, len(sorted_qs) // 4)
            top_25_q = sorted_qs[top_25_idx - 1]
        else:
            top_25_q = 0.0  # With few repos, don't filter by quality percentile

        gems: list[RankedRepo] = []
        for repo in ranked:
            if (
                repo.stars < threshold_stars
                and repo.quality_score >= min_quality
                and repo.quality_score >= top_25_q
            ):
                is_gem, _ = self._value_calc.is_hidden_gem(
                    repo.quality_score,
                    repo.stars,
                    repo.quality_score,  # value_score = quality_score in star-neutral design
                )
                if is_gem:
                    gems.append(repo)

        return gems
