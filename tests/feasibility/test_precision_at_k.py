"""Precision and information retrieval metrics tests.

Tests precision@k, NDCG, MRR, and full metrics report computation.
"""

from __future__ import annotations

import pytest

from github_discovery.feasibility.metrics import (
    FullMetricsReport,
    compute_full_metrics,
    compute_mrr,
    compute_ndcg,
    compute_precision_at_k,
)
from github_discovery.models.enums import DomainType
from github_discovery.models.scoring import RankedRepo, ScoreResult

pytestmark = pytest.mark.integration


def _make_ranked_repo(
    full_name: str,
    rank: int,
    quality: float = 0.5,
    stars: int = 100,
    domain: DomainType = DomainType.LIBRARY,
) -> RankedRepo:
    """Create a test RankedRepo."""
    score = ScoreResult(
        full_name=full_name,
        quality_score=quality,
        stars=stars,
        domain=domain,
    )
    return RankedRepo(
        rank=rank,
        full_name=full_name,
        domain=domain,
        score_result=score,
    )


def test_precision_at_k_perfect() -> None:
    """All top-K are relevant → precision 1.0."""
    ranked = [
        _make_ranked_repo("good/repo1", rank=1),
        _make_ranked_repo("good/repo2", rank=2),
        _make_ranked_repo("good/repo3", rank=3),
    ]
    ground_truth = {"good/repo1", "good/repo2", "good/repo3"}

    result = compute_precision_at_k(ranked, ground_truth, k=3)

    assert result == 1.0


def test_precision_at_k_half() -> None:
    """Half relevant → precision 0.5."""
    ranked = [
        _make_ranked_repo("good/repo1", rank=1),
        _make_ranked_repo("bad/repo2", rank=2),
        _make_ranked_repo("good/repo3", rank=3),
        _make_ranked_repo("bad/repo4", rank=4),
    ]
    ground_truth = {"good/repo1", "good/repo3"}

    result = compute_precision_at_k(ranked, ground_truth, k=4)

    assert result == 0.5


def test_precision_at_k_none() -> None:
    """None relevant → precision 0.0."""
    ranked = [
        _make_ranked_repo("bad/repo1", rank=1),
        _make_ranked_repo("bad/repo2", rank=2),
    ]
    ground_truth = {"good/repo1"}

    result = compute_precision_at_k(ranked, ground_truth, k=2)

    assert result == 0.0


def test_precision_at_k_empty() -> None:
    """Empty list → precision 0.0."""
    result = compute_precision_at_k([], set(), k=5)
    assert result == 0.0


def test_ndcg_perfect_ranking() -> None:
    """Perfect ranking → NDCG 1.0."""
    ranked = [
        _make_ranked_repo("a/high", rank=1),
        _make_ranked_repo("b/med", rank=2),
        _make_ranked_repo("c/low", rank=3),
    ]
    relevance = {"a/high": 3.0, "b/med": 2.0, "c/low": 1.0}

    result = compute_ndcg(ranked, relevance, k=3)

    assert result == 1.0


def test_ndcg_worst_ranking() -> None:
    """Worst ranking (reversed) → low NDCG score."""
    ranked = [
        _make_ranked_repo("c/low", rank=1),
        _make_ranked_repo("b/med", rank=2),
        _make_ranked_repo("a/high", rank=3),
    ]
    relevance = {"a/high": 3.0, "b/med": 2.0, "c/low": 1.0}

    result = compute_ndcg(ranked, relevance, k=3)

    # Reversed order should have NDCG < 1.0
    assert 0.0 < result < 1.0


def test_mrr_first_position() -> None:
    """First relevant at position 1 → MRR 1.0."""
    ranked = [
        _make_ranked_repo("good/repo1", rank=1),
        _make_ranked_repo("other/repo2", rank=2),
    ]
    ground_truth = {"good/repo1"}

    result = compute_mrr(ranked, ground_truth)

    assert result == 1.0


def test_mrr_no_relevant() -> None:
    """No relevant results → MRR 0.0."""
    ranked = [
        _make_ranked_repo("bad/repo1", rank=1),
        _make_ranked_repo("bad/repo2", rank=2),
    ]
    ground_truth = {"good/repo1"}

    result = compute_mrr(ranked, ground_truth)

    assert result == 0.0


def test_full_metrics_report() -> None:
    """FullMetricsReport computed correctly from two rankings."""
    gd_ranked = [
        _make_ranked_repo("gem/lib-a", rank=1, quality=0.9, stars=30),
        _make_ranked_repo("gem/lib-b", rank=2, quality=0.85, stars=50),
        _make_ranked_repo("pop/lib-c", rank=3, quality=0.8, stars=5000),
        _make_ranked_repo("pop/lib-d", rank=4, quality=0.75, stars=3000),
        _make_ranked_repo("ok/lib-e", rank=5, quality=0.7, stars=200),
    ]
    star_ranked = [
        _make_ranked_repo("pop/lib-c", rank=1, quality=0.0, stars=5000),
        _make_ranked_repo("pop/lib-d", rank=2, quality=0.0, stars=3000),
        _make_ranked_repo("ok/lib-e", rank=3, quality=0.0, stars=200),
        _make_ranked_repo("gem/lib-a", rank=4, quality=0.0, stars=30),
        _make_ranked_repo("gem/lib-b", rank=5, quality=0.0, stars=50),
    ]
    ground_truth = {"gem/lib-a", "gem/lib-b", "ok/lib-e"}

    report = compute_full_metrics(gd_ranked, star_ranked, ground_truth)

    assert isinstance(report, FullMetricsReport)
    # GD ranking has 3/5 relevant in top-5 → precision_at_5 = 0.6
    assert report.precision_at_5 == 0.6
    # GD has 3/5 relevant in top-5 → precision_at_5 = 0.6
    assert report.ndcg_gd > 0.0
    assert 0.0 <= report.ndcg_gd <= 1.0
    assert 0.0 <= report.mrr_gd <= 1.0
    assert 0.0 <= report.mrr_stars <= 1.0
    assert 0.0 <= report.hidden_gem_recall <= 1.0
