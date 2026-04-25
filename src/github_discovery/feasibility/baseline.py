"""Star-based baseline scorer for comparison with GitHub Discovery ranking.

Provides star-based and metadata-based ranking baselines and comparison
metrics to validate that GitHub Discovery finds technically superior
repos compared to popularity-based approaches.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from github_discovery.models.candidate import RepoCandidate
    from github_discovery.models.enums import DomainType
    from github_discovery.models.scoring import RankedRepo
    from github_discovery.models.screening import ScreeningResult

logger = structlog.get_logger("github_discovery.feasibility.baseline")

_MIN_COMMON_ITEMS = 2
_MIN_WILCOXON_SAMPLES = 5
_LARGE_Z_THRESHOLD = 6.0
_HIGH_QUALITY_THRESHOLD = 0.7
_MODERATE_VALUE_THRESHOLD = 0.5
_STRONG_DIM_THRESHOLD = 0.6
_LOW_QUALITY_THRESHOLD = 0.4
_WEAK_DIM_THRESHOLD = 0.4
_GEM_RANK_THRESHOLD = 50


@dataclass
class HiddenGem:
    """A repository identified as a hidden gem by GD but not by star ranking.

    Attributes:
        full_name: Repository full name (owner/repo).
        quality_score: GD quality score.
        value_score: GD value score (star-neutral: equals quality_score).
        gd_rank: Rank in GD ranking.
        star_rank: Rank in star-based ranking.
        stars: Star count.
        quality_evidence: Evidence supporting the quality assessment.
    """

    full_name: str
    quality_score: float
    value_score: float
    gd_rank: int
    star_rank: int
    stars: int
    quality_evidence: list[str] = field(default_factory=list)


@dataclass
class OverhypedRepo:
    """A repository ranked high by stars but low by GD quality.

    Attributes:
        full_name: Repository full name (owner/repo).
        quality_score: GD quality score.
        star_rank: Rank in star-based ranking.
        gd_rank: Rank in GD ranking.
        stars: Star count.
        quality_concerns: Specific quality concerns identified.
    """

    full_name: str
    quality_score: float
    star_rank: int
    gd_rank: int
    stars: int
    quality_concerns: list[str] = field(default_factory=list)


@dataclass
class BaselineComparison:
    """Comparison between metadata-based and star-based rankings.

    Attributes:
        metadata_top_10: Top 10 repo names by metadata ranking.
        star_top_10: Top 10 repo names by star ranking.
        overlap_count: Number of repos in both top-10 lists.
        hidden_gems_metadata: Repos in metadata top-10 but not star top-10.
        overhyped_by_stars: Repos in star top-10 but not metadata top-10.
        correlation_coefficient: Spearman rank correlation between rankings.
    """

    metadata_top_10: list[str]
    star_top_10: list[str]
    overlap_count: int
    hidden_gems_metadata: list[str]
    overhyped_by_stars: list[str]
    correlation_coefficient: float


@dataclass
class DetailedComparison:
    """Detailed comparison between GD and star-based rankings.

    Attributes:
        overlap_at_5: Overlap count in top-5.
        overlap_at_10: Overlap count in top-10.
        overlap_at_20: Overlap count in top-20.
        hidden_gems: Repos GD ranks much higher than stars.
        overhyped_repos: Repos stars rank much higher than GD.
        domain_comparisons: Per-domain BaselineComparison results.
        wilcoxon_p_value: Wilcoxon signed-rank test p-value (approximate).
    """

    overlap_at_5: int
    overlap_at_10: int
    overlap_at_20: int
    hidden_gems: list[HiddenGem]
    overhyped_repos: list[OverhypedRepo]
    domain_comparisons: dict[str, BaselineComparison]
    wilcoxon_p_value: float


def compute_star_ranking(
    candidates: list[RepoCandidate],
    *,
    domain: DomainType | None = None,
    max_results: int = 100,
) -> list[RankedRepo]:
    """Rank candidates by star count (descending).

    Creates a minimal ScoreResult for each candidate with
    quality_score set to 0.0 (unknown). Stars are the sole
    ranking signal for the baseline.

    Args:
        candidates: Repository candidates to rank.
        domain: Optional domain filter.
        max_results: Maximum results to return.

    Returns:
        List of RankedRepo sorted by stars descending.
    """
    from github_discovery.models.scoring import RankedRepo, ScoreResult  # noqa: PLC0415

    filtered = candidates
    if domain is not None:
        filtered = [c for c in candidates if c.domain == domain]

    sorted_candidates = sorted(filtered, key=lambda c: c.stars, reverse=True)
    sorted_candidates = sorted_candidates[:max_results]

    ranked: list[RankedRepo] = []
    for i, candidate in enumerate(sorted_candidates, start=1):
        score_result = ScoreResult(
            full_name=candidate.full_name,
            commit_sha=candidate.commit_sha,
            domain=candidate.domain,
            quality_score=0.0,
            stars=candidate.stars,
        )
        ranked.append(
            RankedRepo(
                rank=i,
                full_name=candidate.full_name,
                domain=candidate.domain,
                score_result=score_result,
            ),
        )

    return ranked


def compute_metadata_ranking(
    candidates: list[RepoCandidate],
    screening_results: dict[str, ScreeningResult],
    *,
    domain: DomainType | None = None,
    max_results: int = 100,
) -> list[RankedRepo]:
    """Rank candidates by metadata (Gate 1) score only.

    Uses the composite Gate 1 score as the ranking signal.
    This is a lightweight baseline that doesn't require LLM assessment.

    Args:
        candidates: Repository candidates to rank.
        screening_results: Screening results keyed by full_name.
        domain: Optional domain filter.
        max_results: Maximum results to return.

    Returns:
        List of RankedRepo sorted by Gate 1 score descending.
    """
    from github_discovery.models.scoring import RankedRepo, ScoreResult  # noqa: PLC0415

    filtered = candidates
    if domain is not None:
        filtered = [c for c in candidates if c.domain == domain]

    scored: list[tuple[float, RepoCandidate]] = []
    for candidate in filtered:
        screening = screening_results.get(candidate.full_name)
        meta_score = 0.0
        if screening is not None and screening.gate1 is not None:
            meta_score = screening.gate1.gate1_total
        scored.append((meta_score, candidate))

    scored.sort(key=lambda x: x[0], reverse=True)
    scored = scored[:max_results]

    ranked: list[RankedRepo] = []
    for i, (meta_score, candidate) in enumerate(scored, start=1):
        score_result = ScoreResult(
            full_name=candidate.full_name,
            commit_sha=candidate.commit_sha,
            domain=candidate.domain,
            quality_score=meta_score,
            gate1_total=meta_score,
            stars=candidate.stars,
        )
        ranked.append(
            RankedRepo(
                rank=i,
                full_name=candidate.full_name,
                domain=candidate.domain,
                score_result=score_result,
            ),
        )

    return ranked


def compare_rankings(
    metadata_ranked: list[RankedRepo],
    star_ranked: list[RankedRepo],
    *,
    top_k: int = 10,
) -> BaselineComparison:
    """Compare metadata-based and star-based rankings.

    Computes overlap, hidden gems, and rank correlation
    between the two ranking approaches.

    Args:
        metadata_ranked: Repos ranked by metadata quality.
        star_ranked: Repos ranked by star count.
        top_k: Number of top results to compare.

    Returns:
        BaselineComparison with overlap and correlation metrics.
    """
    meta_top = [r.full_name for r in metadata_ranked[:top_k]]
    star_top = [r.full_name for r in star_ranked[:top_k]]

    meta_set = set(meta_top)
    star_set = set(star_top)

    overlap = meta_set & star_set
    hidden_gems = [name for name in meta_top if name not in star_set]
    overhyped = [name for name in star_top if name not in meta_set]

    correlation = _spearman_correlation(metadata_ranked, star_ranked)

    return BaselineComparison(
        metadata_top_10=meta_top,
        star_top_10=star_top,
        overlap_count=len(overlap),
        hidden_gems_metadata=hidden_gems,
        overhyped_by_stars=overhyped,
        correlation_coefficient=correlation,
    )


def compute_detailed_comparison(
    gd_ranked: list[RankedRepo],
    star_ranked: list[RankedRepo],
    candidates: list[RepoCandidate],
) -> DetailedComparison:
    """Compute detailed comparison between GD and star-based rankings.

    Provides overlap at multiple k values, identifies hidden gems
    and overhyped repos, and computes per-domain comparisons.

    Args:
        gd_ranked: Repos ranked by GitHub Discovery.
        star_ranked: Repos ranked by star count.
        candidates: Original candidate list with metadata.

    Returns:
        DetailedComparison with comprehensive comparison metrics.
    """
    overlap_at_5 = _count_overlap(gd_ranked, star_ranked, k=5)
    overlap_at_10 = _count_overlap(gd_ranked, star_ranked, k=10)
    overlap_at_20 = _count_overlap(gd_ranked, star_ranked, k=20)

    gd_rank_map = {r.full_name: r.rank for r in gd_ranked}
    star_rank_map = {r.full_name: r.rank for r in star_ranked}
    candidate_map = {c.full_name: c for c in candidates}

    hidden_gems = _find_hidden_gems(gd_ranked, star_rank_map, candidate_map)
    overhyped = _find_overhyped(star_ranked, gd_rank_map, candidate_map)

    domain_comparisons = _compute_domain_comparisons(gd_ranked, star_ranked)

    wilcoxon_p = _approximate_wilcoxon_p(gd_ranked, star_rank_map)

    return DetailedComparison(
        overlap_at_5=overlap_at_5,
        overlap_at_10=overlap_at_10,
        overlap_at_20=overlap_at_20,
        hidden_gems=hidden_gems,
        overhyped_repos=overhyped,
        domain_comparisons=domain_comparisons,
        wilcoxon_p_value=wilcoxon_p,
    )


def _count_overlap(
    ranking_a: list[RankedRepo],
    ranking_b: list[RankedRepo],
    *,
    k: int,
) -> int:
    """Count overlap between two rankings at position k."""
    set_a = {r.full_name for r in ranking_a[:k]}
    set_b = {r.full_name for r in ranking_b[:k]}
    return len(set_a & set_b)


def _find_hidden_gems(
    gd_ranked: list[RankedRepo],
    star_rank_map: dict[str, int],
    candidate_map: dict[str, RepoCandidate],
) -> list[HiddenGem]:
    """Find repos that GD ranks significantly higher than stars."""
    gems: list[HiddenGem] = []
    for repo in gd_ranked:
        if repo.rank > _GEM_RANK_THRESHOLD:
            continue

        star_rank = star_rank_map.get(repo.full_name)
        if star_rank is None or star_rank > repo.rank * 2:
            candidate = candidate_map.get(repo.full_name)
            stars = candidate.stars if candidate else repo.stars
            gems.append(
                HiddenGem(
                    full_name=repo.full_name,
                    quality_score=repo.quality_score,
                    value_score=repo.value_score,
                    gd_rank=repo.rank,
                    star_rank=star_rank or len(star_rank_map) + 1,
                    stars=stars,
                    quality_evidence=_build_quality_evidence(repo),
                ),
            )

    return gems


def _find_overhyped(
    star_ranked: list[RankedRepo],
    gd_rank_map: dict[str, int],
    candidate_map: dict[str, RepoCandidate],
) -> list[OverhypedRepo]:
    """Find repos that stars rank significantly higher than GD."""
    overhyped: list[OverhypedRepo] = []
    for repo in star_ranked:
        if repo.rank > _GEM_RANK_THRESHOLD:
            continue

        gd_rank = gd_rank_map.get(repo.full_name)
        if gd_rank is not None and gd_rank > repo.rank * 2:
            candidate = candidate_map.get(repo.full_name)
            stars = candidate.stars if candidate else repo.stars
            overhyped.append(
                OverhypedRepo(
                    full_name=repo.full_name,
                    quality_score=repo.quality_score,
                    star_rank=repo.rank,
                    gd_rank=gd_rank,
                    stars=stars,
                    quality_concerns=_build_quality_concerns(repo),
                ),
            )

    return overhyped


def _compute_domain_comparisons(
    gd_ranked: list[RankedRepo],
    star_ranked: list[RankedRepo],
) -> dict[str, BaselineComparison]:
    """Compute per-domain BaselineComparison."""
    gd_by_domain: dict[str, list[RankedRepo]] = {}
    for repo in gd_ranked:
        gd_by_domain.setdefault(repo.domain.value, []).append(repo)

    star_by_domain: dict[str, list[RankedRepo]] = {}
    for repo in star_ranked:
        star_by_domain.setdefault(repo.domain.value, []).append(repo)

    all_domains = set(gd_by_domain.keys()) | set(star_by_domain.keys())
    comparisons: dict[str, BaselineComparison] = {}

    for domain in all_domains:
        gd_domain = sorted(gd_by_domain.get(domain, []), key=lambda r: r.rank)
        star_domain = sorted(star_by_domain.get(domain, []), key=lambda r: r.rank)

        comparisons[domain] = compare_rankings(
            gd_domain,
            star_domain,
            top_k=5,
        )

    return comparisons


def _spearman_correlation(
    ranking_a: list[RankedRepo],
    ranking_b: list[RankedRepo],
) -> float:
    """Compute Spearman rank correlation between two rankings.

    Uses manual implementation (no scipy dependency).
    Computes Pearson correlation on re-ranked items, which is
    equivalent to Spearman for tied-rank data.
    """
    rank_a = {r.full_name: r.rank for r in ranking_a}
    rank_b = {r.full_name: r.rank for r in ranking_b}

    common = set(rank_a.keys()) & set(rank_b.keys())
    n = len(common)

    if n < _MIN_COMMON_ITEMS:
        return 0.0

    # Re-rank common items to handle gaps
    a_ranks = {name: i + 1 for i, name in enumerate(sorted(common, key=lambda x: rank_a[x]))}
    b_ranks = {name: i + 1 for i, name in enumerate(sorted(common, key=lambda x: rank_b[x]))}

    # Pearson correlation: r = (n*Sxy - Sx*Sy) / sqrt((n*Sx2-Sx^2)*(n*Sy2-Sy^2))
    sum_x = sum(a_ranks[name] for name in common)
    sum_y = sum(b_ranks[name] for name in common)
    sum_xy = sum(a_ranks[name] * b_ranks[name] for name in common)
    sum_x2 = sum(a_ranks[name] ** 2 for name in common)
    sum_y2 = sum(b_ranks[name] ** 2 for name in common)

    numerator = n * sum_xy - sum_x * sum_y
    denominator_sq = (n * sum_x2 - sum_x**2) * (n * sum_y2 - sum_y**2)

    if denominator_sq <= 0:
        return 0.0

    return numerator / math.sqrt(denominator_sq)


def _approximate_wilcoxon_p(
    gd_ranked: list[RankedRepo],
    star_rank_map: dict[str, int],
) -> float:
    """Approximate Wilcoxon signed-rank test p-value.

    Uses the normal approximation for the signed-rank statistic.
    This is NOT a rigorous statistical test -- it provides a rough
    indicator of whether the rankings differ significantly.
    """
    differences: list[float] = []
    for repo in gd_ranked:
        star_rank = star_rank_map.get(repo.full_name)
        if star_rank is not None:
            differences.append(float(repo.rank - star_rank))

    # Standard Wilcoxon: exclude ties (zero differences) before ranking
    differences = [d for d in differences if d != 0.0]
    n = len(differences)
    if n < _MIN_WILCOXON_SAMPLES:
        return 1.0

    abs_diffs = sorted(enumerate(differences), key=lambda x: abs(x[1]))

    signed_ranks: list[float] = [0.0] * n
    for rank_idx, (orig_idx, diff) in enumerate(abs_diffs, start=1):
        if diff != 0:
            signed_ranks[orig_idx] = float(rank_idx) if diff > 0 else float(-rank_idx)

    w_stat = sum(signed_ranks)

    variance = n * (n + 1) * (2 * n + 1) / 6.0
    if variance <= 0:
        return 1.0

    z_score = abs(w_stat) / math.sqrt(variance)

    if z_score > _LARGE_Z_THRESHOLD:
        return 0.0

    return min(1.0, max(0.0, 2.0 * _normal_survival(z_score)))


def _normal_survival(z: float) -> float:
    """Approximate P(Z > z) for standard normal using rational approximation.

    Uses Abramowitz and Stegun approximation 26.2.18.
    """
    if z < 0:
        z = -z

    b0 = 0.2316419
    b1 = 0.319381530
    b2 = -0.356563782
    b3 = 1.781477937
    b4 = -1.821255978
    b5 = 1.330274429

    t = 1.0 / (1.0 + b0 * z)
    t2 = t * t
    t3 = t2 * t
    t4 = t3 * t
    t5 = t4 * t

    pdf = (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * z * z)
    return pdf * (b1 * t + b2 * t2 + b3 * t3 + b4 * t4 + b5 * t5)


def _build_quality_evidence(repo: RankedRepo) -> list[str]:
    """Build quality evidence strings for a hidden gem."""
    evidence: list[str] = []
    if repo.quality_score >= _HIGH_QUALITY_THRESHOLD:
        evidence.append(f"High quality score: {repo.quality_score:.2f}")
    if repo.value_score >= _MODERATE_VALUE_THRESHOLD:
        evidence.append(f"High value score: {repo.value_score:.2f}")

    dim_scores = repo.score_result.dimension_scores
    top_dims = sorted(dim_scores.items(), key=lambda x: x[1], reverse=True)[:3]
    for dim, score in top_dims:
        if score >= _STRONG_DIM_THRESHOLD:
            evidence.append(f"Strong {dim.value}: {score:.2f}")

    return evidence


def _build_quality_concerns(repo: RankedRepo) -> list[str]:
    """Build quality concern strings for an overhyped repo."""
    concerns: list[str] = []
    if repo.quality_score < _LOW_QUALITY_THRESHOLD:
        concerns.append(f"Low quality score: {repo.quality_score:.2f}")

    dim_scores = repo.score_result.dimension_scores
    weak_dims = sorted(dim_scores.items(), key=lambda x: x[1])[:3]
    for dim, score in weak_dims:
        if score < _WEAK_DIM_THRESHOLD:
            concerns.append(f"Weak {dim.value}: {score:.2f}")

    if not concerns:
        concerns.append("Quality below GD ranking expectations")

    return concerns
