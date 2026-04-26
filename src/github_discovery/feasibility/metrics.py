"""Evaluation metrics for feasibility validation.

Provides precision@k, NDCG, MRR, and other information retrieval
metrics to compare GitHub Discovery ranking against star-based ranking.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

from github_discovery.config import ScoringSettings as _ScoringSettings

if TYPE_CHECKING:
    from github_discovery.models.scoring import RankedRepo

logger = structlog.get_logger("github_discovery.feasibility.metrics")

# Hidden gem star threshold (single source of truth — T1.1)
_HIDDEN_GEM_STAR_THRESHOLD = _ScoringSettings().hidden_gem_star_threshold
_METRICS_TOP_K = 20


@dataclass
class PrecisionAtKResult:
    """Precision@k comparison between GD and star-based ranking.

    Attributes:
        k: The cutoff position.
        gd_precision: Precision of GD ranking at k.
        star_precision: Precision of star-based ranking at k.
        improvement: Relative improvement of GD over stars.
        gd_relevant: Relevant repo names from GD top-k.
        star_relevant: Relevant repo names from star top-k.
    """

    k: int
    gd_precision: float
    star_precision: float
    improvement: float
    gd_relevant: list[str] = field(default_factory=list)
    star_relevant: list[str] = field(default_factory=list)


@dataclass
class FullMetricsReport:
    """Complete metrics report comparing GD and star-based ranking.

    Attributes:
        precision_at_5: Precision@5 for GD ranking.
        precision_at_10: Precision@10 for GD ranking.
        precision_at_20: Precision@20 for GD ranking.
        ndcg_gd: NDCG@20 for GD ranking.
        ndcg_stars: NDCG@20 for star-based ranking.
        hidden_gem_recall: Recall of hidden gems in GD top-k.
        mrr_gd: Mean Reciprocal Rank for GD ranking.
        mrr_stars: Mean Reciprocal Rank for star-based ranking.
    """

    precision_at_5: float = 0.0
    precision_at_10: float = 0.0
    precision_at_20: float = 0.0
    ndcg_gd: float = 0.0
    ndcg_stars: float = 0.0
    hidden_gem_recall: float = 0.0
    mrr_gd: float = 0.0
    mrr_stars: float = 0.0


def compute_precision_at_k(
    ranked_repos: list[RankedRepo],
    ground_truth_good: set[str],
    *,
    k: int = 10,
) -> float:
    """Compute precision@k for a ranked list.

    Precision@k = |relevant intersection top-k| / k

    Args:
        ranked_repos: Ranked list of repositories.
        ground_truth_good: Set of repo full_names considered relevant.
        k: Cutoff position.

    Returns:
        Precision value in [0.0, 1.0].
    """
    if k <= 0 or not ranked_repos:
        return 0.0

    top_k = ranked_repos[:k]
    relevant_in_top_k = sum(1 for r in top_k if r.full_name in ground_truth_good)
    return relevant_in_top_k / k


def compute_ndcg(
    ranked_repos: list[RankedRepo],
    relevance_scores: dict[str, float],
    *,
    k: int = 20,
) -> float:
    """Compute Normalized Discounted Cumulative Gain at k.

    NDCG@k = DCG@k / IDCG@k
    DCG@k = sum(i=1..k) rel_i / log2(i + 1)
    IDCG@k = ideal DCG with relevance scores sorted descending.

    Args:
        ranked_repos: Ranked list of repositories.
        relevance_scores: Map of repo full_name to relevance score.
        k: Cutoff position.

    Returns:
        NDCG value in [0.0, 1.0].
    """
    if k <= 0 or not ranked_repos or not relevance_scores:
        return 0.0

    top_k = ranked_repos[:k]

    # Compute DCG@k
    dcg = 0.0
    for i, repo in enumerate(top_k):
        relevance = relevance_scores.get(repo.full_name, 0.0)
        if relevance > 0:
            dcg += relevance / math.log2(i + 2)

    # Compute IDCG@k (ideal ranking)
    ideal_scores = sorted(relevance_scores.values(), reverse=True)[:k]
    idcg = 0.0
    for i, relevance in enumerate(ideal_scores):
        if relevance > 0:
            idcg += relevance / math.log2(i + 2)

    if idcg <= 0.0:
        return 0.0

    return min(1.0, dcg / idcg)


def compute_mrr(
    ranked_repos: list[RankedRepo],
    ground_truth_good: set[str],
) -> float:
    """Compute Mean Reciprocal Rank.

    MRR = 1/|Q| * sum(1/rank_i) where rank_i is the rank of the first
    relevant result. For a single query, this is just 1/rank_first.

    Args:
        ranked_repos: Ranked list of repositories.
        ground_truth_good: Set of repo full_names considered relevant.

    Returns:
        Reciprocal rank value in [0.0, 1.0].
    """
    if not ranked_repos or not ground_truth_good:
        return 0.0

    for i, repo in enumerate(ranked_repos):
        if repo.full_name in ground_truth_good:
            return 1.0 / (i + 1)

    return 0.0


def compute_full_metrics(
    gd_ranked: list[RankedRepo],
    star_ranked: list[RankedRepo],
    ground_truth: set[str],
) -> FullMetricsReport:
    """Compute complete metrics report comparing GD and star-based rankings.

    Computes precision@k, NDCG, MRR, and hidden gem recall for
    both ranking approaches.

    Args:
        gd_ranked: Repos ranked by GitHub Discovery.
        star_ranked: Repos ranked by star count.
        ground_truth: Set of repo full_names considered relevant/good.

    Returns:
        FullMetricsReport with all computed metrics.
    """
    if not ground_truth:
        logger.warning("compute_full_metrics_empty_ground_truth")
        return FullMetricsReport()

    # Build relevance scores from ground truth (binary relevance)
    relevance_scores: dict[str, float] = {}
    for repo in gd_ranked:
        if repo.full_name in ground_truth:
            relevance_scores[repo.full_name] = 1.0
    for repo in star_ranked:
        if repo.full_name in ground_truth:
            relevance_scores.setdefault(repo.full_name, 1.0)

    # Compute precision@k for GD ranking
    p5_gd = compute_precision_at_k(gd_ranked, ground_truth, k=5)
    p10_gd = compute_precision_at_k(gd_ranked, ground_truth, k=10)
    p20_gd = compute_precision_at_k(gd_ranked, ground_truth, k=20)

    # Compute NDCG@20
    ndcg_gd = compute_ndcg(gd_ranked, relevance_scores, k=_METRICS_TOP_K)
    ndcg_stars = compute_ndcg(star_ranked, relevance_scores, k=_METRICS_TOP_K)

    # Compute MRR
    mrr_gd = compute_mrr(gd_ranked, ground_truth)
    mrr_stars = compute_mrr(star_ranked, ground_truth)

    # Compute hidden gem recall: fraction of ground truth repos
    # found in GD top-20 that have low stars
    low_star_good = {
        name
        for name in ground_truth
        if any(r.full_name == name and r.stars < _HIDDEN_GEM_STAR_THRESHOLD for r in gd_ranked)
    }
    if low_star_good:
        gd_top_k_names = {r.full_name for r in gd_ranked[:_METRICS_TOP_K]}
        hidden_gem_recall = len(low_star_good & gd_top_k_names) / len(low_star_good)
    else:
        hidden_gem_recall = 0.0

    return FullMetricsReport(
        precision_at_5=round(p5_gd, 4),
        precision_at_10=round(p10_gd, 4),
        precision_at_20=round(p20_gd, 4),
        ndcg_gd=round(ndcg_gd, 4),
        ndcg_stars=round(ndcg_stars, 4),
        hidden_gem_recall=round(hidden_gem_recall, 4),
        mrr_gd=round(mrr_gd, 4),
        mrr_stars=round(mrr_stars, 4),
    )
