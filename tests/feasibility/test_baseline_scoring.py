"""Baseline scoring and comparison tests.

Tests star-based ranking, metadata ranking, overlap detection,
hidden gem identification, and overhyped repo detection.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from github_discovery.feasibility.baseline import (
    BaselineComparison,
    DetailedComparison,
    HiddenGem,
    OverhypedRepo,
    compare_rankings,
    compute_detailed_comparison,
    compute_metadata_ranking,
    compute_star_ranking,
)
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import CandidateStatus, DiscoveryChannel, DomainType
from github_discovery.models.scoring import RankedRepo, ScoreResult
from github_discovery.models.screening import (
    MetadataScreenResult,
    ScreeningResult,
)

pytestmark = pytest.mark.integration


def _make_candidate(
    full_name: str,
    *,
    stars: int = 100,
    domain: DomainType = DomainType.LIBRARY,
    description: str = "Test repo",
) -> RepoCandidate:
    """Create a test RepoCandidate with sensible defaults."""
    return RepoCandidate(
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        html_url=f"https://github.com/{full_name}",
        api_url=f"https://api.github.com/repos/{full_name}",
        description=description,
        language="Python",
        domain=domain,
        stars=stars,
        forks_count=stars // 10,
        watchers_count=stars,
        subscribers_count=max(1, stars // 100),
        open_issues_count=5,
        created_at=datetime(2022, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 3, 1, tzinfo=UTC),
        pushed_at=datetime(2026, 2, 28, tzinfo=UTC),
        license_info={"spdx_id": "MIT"},
        owner_login=full_name.split("/", maxsplit=1)[0],
        source_channel=DiscoveryChannel.SEARCH,
        commit_sha=f"sha_{full_name}",
        status=CandidateStatus.DISCOVERED,
    )


def _make_ranked_repo(
    full_name: str,
    rank: int,
    quality: float,
    stars: int,
    domain: DomainType = DomainType.LIBRARY,
) -> RankedRepo:
    """Create a test RankedRepo with a ScoreResult."""
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


def test_compute_star_ranking_basic() -> None:
    """Star ranking sorts candidates by stars descending."""
    candidates = [
        _make_candidate("a/low-star", stars=50),
        _make_candidate("b/high-star", stars=5000),
        _make_candidate("c/med-star", stars=500),
    ]

    ranked = compute_star_ranking(candidates)

    assert len(ranked) == 3
    assert ranked[0].full_name == "b/high-star"
    assert ranked[1].full_name == "c/med-star"
    assert ranked[2].full_name == "a/low-star"
    # Ranks are 1-based
    assert ranked[0].rank == 1
    assert ranked[1].rank == 2
    assert ranked[2].rank == 3


def test_compute_star_ranking_empty() -> None:
    """Empty list returns empty ranking."""
    ranked = compute_star_ranking([])
    assert ranked == []


def test_compute_star_ranking_domain_filter() -> None:
    """Domain filter restricts results to matching domain."""
    candidates = [
        _make_candidate("a/py-lib", stars=1000, domain=DomainType.LIBRARY),
        _make_candidate("b/cli-tool", stars=500, domain=DomainType.CLI),
        _make_candidate("c/py-lib2", stars=800, domain=DomainType.LIBRARY),
    ]

    ranked = compute_star_ranking(candidates, domain=DomainType.LIBRARY)

    assert len(ranked) == 2
    names = {r.full_name for r in ranked}
    assert names == {"a/py-lib", "c/py-lib2"}


def test_compute_metadata_ranking() -> None:
    """Metadata ranking sorts by Gate 1 score descending."""
    candidates = [
        _make_candidate("a/low-meta", stars=1000),
        _make_candidate("b/high-meta", stars=50),
        _make_candidate("c/med-meta", stars=500),
    ]

    screening_results = {
        "a/low-meta": ScreeningResult(
            full_name="a/low-meta",
            gate1=MetadataScreenResult(
                full_name="a/low-meta",
                gate1_total=0.3,
                gate1_pass=False,
            ),
        ),
        "b/high-meta": ScreeningResult(
            full_name="b/high-meta",
            gate1=MetadataScreenResult(
                full_name="b/high-meta",
                gate1_total=0.9,
                gate1_pass=True,
            ),
        ),
        "c/med-meta": ScreeningResult(
            full_name="c/med-meta",
            gate1=MetadataScreenResult(
                full_name="c/med-meta",
                gate1_total=0.6,
                gate1_pass=True,
            ),
        ),
    }

    ranked = compute_metadata_ranking(candidates, screening_results)

    assert len(ranked) == 3
    assert ranked[0].full_name == "b/high-meta"
    assert ranked[1].full_name == "c/med-meta"
    assert ranked[2].full_name == "a/low-meta"


def test_compare_rankings_overlap() -> None:
    """Overlap detection between metadata and star rankings."""
    meta_ranked = [
        _make_ranked_repo("a/repo1", rank=1, quality=0.9, stars=50),
        _make_ranked_repo("b/repo2", rank=2, quality=0.8, stars=100),
        _make_ranked_repo("c/repo3", rank=3, quality=0.7, stars=500),
    ]
    star_ranked = [
        _make_ranked_repo("c/repo3", rank=1, quality=0.0, stars=500),
        _make_ranked_repo("b/repo2", rank=2, quality=0.0, stars=100),
        _make_ranked_repo("d/repo4", rank=3, quality=0.0, stars=30),
    ]

    comparison = compare_rankings(meta_ranked, star_ranked, top_k=3)

    assert isinstance(comparison, BaselineComparison)
    assert comparison.overlap_count == 2  # repo2 and repo3 overlap
    assert "d/repo4" in comparison.overhyped_by_stars
    assert "a/repo1" in comparison.hidden_gems_metadata


def test_compare_rankings_no_overlap() -> None:
    """Completely different lists produce zero overlap."""
    meta_ranked = [
        _make_ranked_repo("a/repo1", rank=1, quality=0.9, stars=10),
        _make_ranked_repo("b/repo2", rank=2, quality=0.8, stars=20),
    ]
    star_ranked = [
        _make_ranked_repo("c/repo3", rank=1, quality=0.0, stars=5000),
        _make_ranked_repo("d/repo4", rank=2, quality=0.0, stars=3000),
    ]

    comparison = compare_rankings(meta_ranked, star_ranked, top_k=2)

    assert comparison.overlap_count == 0


def test_hidden_gem_identification() -> None:
    """HiddenGem objects created correctly for high-quality low-star repos."""
    gem = HiddenGem(
        full_name="hidden/gem-lib",
        quality_score=0.85,
        value_score=0.45,
        gd_rank=3,
        star_rank=95,
        stars=42,
        quality_evidence=["High quality score: 0.85"],
    )

    assert gem.full_name == "hidden/gem-lib"
    assert gem.quality_score == 0.85
    assert gem.gd_rank < gem.star_rank
    assert gem.stars < 100


def test_overhyped_identification() -> None:
    """OverhypedRepo objects created correctly for high-star low-quality repos."""
    repo = OverhypedRepo(
        full_name="overhyped/trending",
        quality_score=0.32,
        star_rank=1,
        gd_rank=85,
        stars=15000,
        quality_concerns=["Low quality score: 0.32"],
    )

    assert repo.full_name == "overhyped/trending"
    assert repo.quality_score < 0.5
    assert repo.gd_rank > repo.star_rank
    assert repo.stars > 1000


def test_detailed_comparison_structure() -> None:
    """DetailedComparison has all required fields."""
    gd_ranked = [
        _make_ranked_repo("a/gem", rank=1, quality=0.9, stars=30),
        _make_ranked_repo("b/popular", rank=2, quality=0.8, stars=5000),
        _make_ranked_repo("c/ok", rank=3, quality=0.7, stars=200),
    ]
    star_ranked = [
        _make_ranked_repo("b/popular", rank=1, quality=0.0, stars=5000),
        _make_ranked_repo("c/ok", rank=2, quality=0.0, stars=200),
        _make_ranked_repo("d/viral", rank=3, quality=0.0, stars=8000),
    ]
    candidates = [
        _make_candidate("a/gem", stars=30),
        _make_candidate("b/popular", stars=5000),
        _make_candidate("c/ok", stars=200),
        _make_candidate("d/viral", stars=8000),
    ]

    result = compute_detailed_comparison(gd_ranked, star_ranked, candidates)

    assert isinstance(result, DetailedComparison)
    assert isinstance(result.overlap_at_5, int)
    assert isinstance(result.overlap_at_10, int)
    assert isinstance(result.overlap_at_20, int)
    assert isinstance(result.hidden_gems, list)
    assert isinstance(result.overhyped_repos, list)
    assert isinstance(result.domain_comparisons, dict)
    assert isinstance(result.wilcoxon_p_value, float)
    # Overlap should be >= 2 (b/popular and c/ok are in both rankings)
    assert result.overlap_at_20 >= 2
