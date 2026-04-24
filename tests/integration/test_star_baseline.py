"""Star-based baseline comparison integration tests.

Compares GitHub Discovery ranking with simple star-based ranking
to validate the anti-star bias value proposition.
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
    compute_star_ranking,
)
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel, DomainType
from github_discovery.models.scoring import RankedRepo, ScoreResult

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIXED_DT = datetime(2025, 1, 1, tzinfo=UTC)


def _make_candidate(
    full_name: str,
    stars: int = 0,
    domain: DomainType = DomainType.LIBRARY,
) -> RepoCandidate:
    """Create a minimal RepoCandidate for testing."""
    owner = full_name.split("/", maxsplit=1)[0] if "/" in full_name else full_name
    return RepoCandidate(
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        html_url=f"https://github.com/{full_name}",
        api_url=f"https://api.github.com/repos/{full_name}",
        owner_login=owner,
        source_channel=DiscoveryChannel.SEARCH,
        stars=stars,
        domain=domain,
        created_at=_FIXED_DT,
        updated_at=_FIXED_DT,
    )


def _make_ranked(
    full_name: str,
    rank: int,
    quality: float,
    stars: int,
    domain: DomainType = DomainType.LIBRARY,
) -> RankedRepo:
    """Create a RankedRepo for testing."""
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


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------


def _gd_ranked() -> list[RankedRepo]:
    """GitHub Discovery ranking (quality-first)."""
    return [
        _make_ranked("hidden/gem-lib", 1, 0.85, 42),
        _make_ranked("quality/cli-tool", 2, 0.80, 150),
        _make_ranked("solid/data-pipeline", 3, 0.75, 30),
        _make_ranked("popular/framework", 4, 0.70, 5000),
        _make_ranked("mature/library", 5, 0.65, 10000),
        _make_ranked("new/promising", 6, 0.60, 5),
        _make_ranked("niche/security", 7, 0.55, 80),
        _make_ranked("big/monorepo", 8, 0.50, 50000),
        _make_ranked("rust/perf-lib", 9, 0.45, 200),
        _make_ranked("go/devops-tool", 10, 0.40, 3000),
    ]


def _star_ranked() -> list[RankedRepo]:
    """Star-based ranking (popularity-first)."""
    return [
        _make_ranked("big/monorepo", 1, 0.50, 50000),
        _make_ranked("mature/library", 2, 0.65, 10000),
        _make_ranked("popular/framework", 3, 0.70, 5000),
        _make_ranked("go/devops-tool", 4, 0.40, 3000),
        _make_ranked("rust/perf-lib", 5, 0.45, 200),
        _make_ranked("quality/cli-tool", 6, 0.80, 150),
        _make_ranked("niche/security", 7, 0.55, 80),
        _make_ranked("hidden/gem-lib", 8, 0.85, 42),
        _make_ranked("solid/data-pipeline", 9, 0.75, 30),
        _make_ranked("new/promising", 10, 0.60, 5),
    ]


def _candidates_for_detailed() -> list[RepoCandidate]:
    """Candidate list matching the shared test repos."""
    names_stars = [
        ("hidden/gem-lib", 42),
        ("quality/cli-tool", 150),
        ("solid/data-pipeline", 30),
        ("popular/framework", 5000),
        ("mature/library", 10000),
        ("new/promising", 5),
        ("niche/security", 80),
        ("big/monorepo", 50000),
        ("rust/perf-lib", 200),
        ("go/devops-tool", 3000),
    ]
    return [_make_candidate(name, stars=stars) for name, stars in names_stars]


# ===========================================================================
# Tests — compute_star_ranking
# ===========================================================================


class TestComputeStarRanking:
    """Tests for compute_star_ranking."""

    @staticmethod
    def test_star_ranking_orders_by_stars() -> None:
        """compute_star_ranking sorts candidates by stars descending."""
        candidates = [
            _make_candidate("low/repo", stars=10),
            _make_candidate("high/repo", stars=5000),
            _make_candidate("mid/repo", stars=500),
        ]
        result = compute_star_ranking(candidates)

        names = [r.full_name for r in result]
        assert names == ["high/repo", "mid/repo", "low/repo"]

        # Ranks are sequential starting from 1
        assert [r.rank for r in result] == [1, 2, 3]

    @staticmethod
    def test_star_ranking_empty_input() -> None:
        """Empty candidates list produces empty result."""
        result = compute_star_ranking([])
        assert result == []

    @staticmethod
    def test_star_ranking_max_results() -> None:
        """compute_star_ranking respects max_results parameter."""
        candidates = [_make_candidate(f"repo/{i}", stars=i * 100) for i in range(1, 21)]
        result = compute_star_ranking(candidates, max_results=5)

        assert len(result) == 5
        # Highest-starred repos should be kept
        assert result[0].full_name == "repo/20"
        assert result[4].full_name == "repo/16"


# ===========================================================================
# Tests — compare_rankings
# ===========================================================================


class TestCompareRankings:
    """Tests for compare_rankings."""

    @staticmethod
    def test_compare_rankings_overlap() -> None:
        """When both lists share repos, overlap_count > 0."""
        gd = _gd_ranked()
        star = _star_ranked()

        comparison = compare_rankings(gd, star, top_k=10)

        # All 10 repos appear in both rankings
        assert comparison.overlap_count == 10

    @staticmethod
    def test_compare_rankings_no_overlap() -> None:
        """Completely different lists produce overlap_count == 0."""
        list_a = [_make_ranked("a/repo-1", 1, 0.9, 100)]
        list_b = [_make_ranked("b/repo-2", 1, 0.8, 200)]

        comparison = compare_rankings(list_a, list_b, top_k=10)

        assert comparison.overlap_count == 0
        assert comparison.hidden_gems_metadata == ["a/repo-1"]
        assert comparison.overhyped_by_stars == ["b/repo-2"]

    @staticmethod
    def test_compare_rankings_identifies_hidden_gems() -> None:
        """Repos with high quality but low star rank appear as hidden gems.

        In the test data, hidden/gem-lib has gd_rank=1 and star_rank=8.
        Since star_rank (8) > gd_rank * 2 (2), it qualifies as hidden gem
        in the detailed comparison.
        """
        gd = _gd_ranked()
        star = _star_ranked()
        candidates = _candidates_for_detailed()

        detailed = compute_detailed_comparison(gd, star, candidates)

        gem_names = {g.full_name for g in detailed.hidden_gems}
        # hidden/gem-lib: gd_rank=1, star_rank=8 → 8 > 1*2 → gem
        assert "hidden/gem-lib" in gem_names
        # quality/cli-tool: gd_rank=2, star_rank=6 → 6 > 2*2 → gem
        assert "quality/cli-tool" in gem_names

    @staticmethod
    def test_compare_rankings_identifies_overhyped() -> None:
        """Repos with low quality but high star rank appear as overhyped.

        In the test data, big/monorepo has star_rank=1 and gd_rank=8.
        Since gd_rank (8) > star_rank * 2 (2), it qualifies as overhyped.
        """
        gd = _gd_ranked()
        star = _star_ranked()
        candidates = _candidates_for_detailed()

        detailed = compute_detailed_comparison(gd, star, candidates)

        overhyped_names = {o.full_name for o in detailed.overhyped_repos}
        # big/monorepo: star_rank=1, gd_rank=8 → 8 > 1*2 → overhyped
        assert "big/monorepo" in overhyped_names
        # go/devops-tool: star_rank=4, gd_rank=10 → 10 > 4*2 → overhyped
        assert "go/devops-tool" in overhyped_names

    @staticmethod
    def test_compare_rankings_correlation() -> None:
        """Correlation coefficient is bounded in [-1, 1]."""
        gd = _gd_ranked()
        star = _star_ranked()

        comparison = compare_rankings(gd, star, top_k=10)

        assert -1.0 <= comparison.correlation_coefficient <= 1.0

        # With our test data the rankings differ substantially,
        # so the correlation should be moderate (not close to 1.0)
        assert comparison.correlation_coefficient < 0.9


# ===========================================================================
# Tests — compute_detailed_comparison
# ===========================================================================


class TestDetailedComparison:
    """Tests for compute_detailed_comparison."""

    @staticmethod
    def test_detailed_comparison_structure() -> None:
        """DetailedComparison has all expected fields populated."""
        gd = _gd_ranked()
        star = _star_ranked()
        candidates = _candidates_for_detailed()

        result = compute_detailed_comparison(gd, star, candidates)

        assert isinstance(result, DetailedComparison)
        # Overlap counts at different k values
        assert 0 <= result.overlap_at_5 <= 5
        assert 0 <= result.overlap_at_10 <= 10
        assert 0 <= result.overlap_at_20 <= 20
        # Hidden gems and overhyped repos are lists
        assert isinstance(result.hidden_gems, list)
        assert isinstance(result.overhyped_repos, list)
        # All items have correct types
        for gem in result.hidden_gems:
            assert isinstance(gem, HiddenGem)
            assert gem.full_name  # non-empty
            assert gem.gd_rank >= 1
        for repo in result.overhyped_repos:
            assert isinstance(repo, OverhypedRepo)
            assert repo.full_name  # non-empty
            assert repo.star_rank >= 1
        # Wilcoxon p-value is in [0, 1]
        assert 0.0 <= result.wilcoxon_p_value <= 1.0

    @staticmethod
    def test_detailed_comparison_per_domain() -> None:
        """domain_comparisons dict is populated with per-domain results."""
        # Create rankings with mixed domains
        gd_mixed = [
            _make_ranked("a/lib", 1, 0.9, 100, DomainType.LIBRARY),
            _make_ranked("b/cli", 2, 0.8, 50, DomainType.CLI),
            _make_ranked("c/lib", 3, 0.7, 200, DomainType.LIBRARY),
        ]
        star_mixed = [
            _make_ranked("c/lib", 1, 0.7, 200, DomainType.LIBRARY),
            _make_ranked("a/lib", 2, 0.9, 100, DomainType.LIBRARY),
            _make_ranked("b/cli", 3, 0.8, 50, DomainType.CLI),
        ]
        candidates_mixed = [
            _make_candidate("a/lib", stars=100, domain=DomainType.LIBRARY),
            _make_candidate("b/cli", stars=50, domain=DomainType.CLI),
            _make_candidate("c/lib", stars=200, domain=DomainType.LIBRARY),
        ]

        result = compute_detailed_comparison(gd_mixed, star_mixed, candidates_mixed)

        assert isinstance(result.domain_comparisons, dict)
        # Both domains should be present
        assert "library" in result.domain_comparisons
        assert "cli" in result.domain_comparisons

        for _domain_key, comparison in result.domain_comparisons.items():
            assert isinstance(comparison, BaselineComparison)
            assert isinstance(comparison.correlation_coefficient, float)
