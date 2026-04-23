"""Tests for intra-domain ranking engine."""

from __future__ import annotations

from github_discovery.config import ScoringSettings
from github_discovery.models.enums import DomainType
from github_discovery.scoring.ranker import Ranker
from tests.unit.scoring.conftest import _make_score_result


class TestRanker:
    """Tests for the Ranker."""

    def test_basic_ranking(self, ranker) -> None:
        """Basic ranking sorts by value_score descending."""
        results = [
            _make_score_result(full_name="repo/low", quality_score=0.5, stars=1000),
            _make_score_result(full_name="repo/high", quality_score=0.9, stars=10),
            _make_score_result(full_name="repo/mid", quality_score=0.7, stars=100),
        ]
        ranking = ranker.rank(results, DomainType.LIBRARY, min_confidence=0.0)
        assert len(ranking.ranked_repos) == 3
        assert ranking.ranked_repos[0].full_name == "repo/high"
        assert ranking.ranked_repos[0].rank == 1

    def test_deterministic_ordering(self, ranker) -> None:
        """Same inputs → same ranking (stability test)."""
        results = [
            _make_score_result(full_name=f"repo/{i}", quality_score=0.5 + i * 0.05)
            for i in range(10)
        ]
        ranking1 = ranker.rank(results, DomainType.LIBRARY, min_confidence=0.0)
        ranking2 = ranker.rank(results, DomainType.LIBRARY, min_confidence=0.0)
        names1 = [r.full_name for r in ranking1.ranked_repos]
        names2 = [r.full_name for r in ranking2.ranked_repos]
        assert names1 == names2

    def test_tiebreaking(self, ranker) -> None:
        """Same value_score → tie-break by quality_score, then full_name."""
        results = [
            _make_score_result(full_name="aaa/repo", quality_score=0.8, stars=100, confidence=0.5),
            _make_score_result(full_name="bbb/repo", quality_score=0.7, stars=100, confidence=0.5),
        ]
        ranking = ranker.rank(results, DomainType.LIBRARY, min_confidence=0.0)
        assert ranking.ranked_repos[0].quality_score >= ranking.ranked_repos[1].quality_score

    def test_min_confidence_filter(self, ranker) -> None:
        """Results below min_confidence are filtered out."""
        results = [
            _make_score_result(full_name="repo/low_conf", confidence=0.1),
            _make_score_result(full_name="repo/high_conf", confidence=0.9),
        ]
        ranking = ranker.rank(results, DomainType.LIBRARY, min_confidence=0.5)
        assert len(ranking.ranked_repos) == 1
        assert ranking.ranked_repos[0].full_name == "repo/high_conf"

    def test_domain_filtering(self, ranker) -> None:
        """Only repos matching the requested domain are included."""
        results = [
            _make_score_result(full_name="repo/lib", domain=DomainType.LIBRARY),
            _make_score_result(full_name="repo/cli", domain=DomainType.CLI),
        ]
        ranking = ranker.rank(results, DomainType.LIBRARY, min_confidence=0.0)
        assert len(ranking.ranked_repos) == 1
        assert ranking.ranked_repos[0].full_name == "repo/lib"

    def test_max_results_limit(self, ranker) -> None:
        """max_results limits the number of ranked repos."""
        results = [
            _make_score_result(full_name=f"repo/{i}", quality_score=0.5 + i * 0.01)
            for i in range(20)
        ]
        ranking = ranker.rank(results, DomainType.LIBRARY, min_confidence=0.0, max_results=5)
        assert len(ranking.ranked_repos) == 5

    def test_total_candidates_count(self, ranker) -> None:
        """total_candidates counts all input results, not just ranked."""
        results = [
            _make_score_result(full_name=f"repo/{i}", domain=DomainType.LIBRARY) for i in range(10)
        ]
        results.append(_make_score_result(full_name="repo/cli", domain=DomainType.CLI))
        ranking = ranker.rank(results, DomainType.LIBRARY, min_confidence=0.0)
        assert ranking.total_candidates == 11

    def test_hidden_gem_detection(self) -> None:
        """Hidden gems are identified: high quality, low stars."""
        settings = ScoringSettings(
            hidden_gem_star_threshold=500,
            hidden_gem_min_quality=0.7,
        )
        ranker = Ranker(settings)
        results = [
            _make_score_result(
                full_name="hidden/gem",
                quality_score=0.9,
                stars=50,
                confidence=0.8,
            ),
            _make_score_result(
                full_name="popular/repo",
                quality_score=0.6,
                stars=5000,
                confidence=0.8,
            ),
        ]
        ranking = ranker.rank(results, DomainType.LIBRARY, min_confidence=0.0)
        gem_names = [g.full_name for g in ranking.hidden_gems]
        assert "hidden/gem" in gem_names
        assert "popular/repo" not in gem_names

    def test_rank_multi_domain(self, ranker) -> None:
        """rank_multi_domain produces separate rankings per domain."""
        results = [
            _make_score_result(full_name="lib/a", domain=DomainType.LIBRARY),
            _make_score_result(full_name="lib/b", domain=DomainType.LIBRARY),
            _make_score_result(full_name="cli/a", domain=DomainType.CLI),
        ]
        rankings = ranker.rank_multi_domain(results, min_confidence=0.0)
        assert DomainType.LIBRARY in rankings
        assert DomainType.CLI in rankings
        assert len(rankings[DomainType.LIBRARY].ranked_repos) == 2
        assert len(rankings[DomainType.CLI].ranked_repos) == 1

    def test_empty_input(self, ranker) -> None:
        """Empty input produces empty ranking."""
        ranking = ranker.rank([], DomainType.LIBRARY, min_confidence=0.0)
        assert len(ranking.ranked_repos) == 0
        assert ranking.total_candidates == 0

    def test_rank_positions_are_sequential(self, ranker) -> None:
        """Rank positions are 1-based and sequential."""
        results = [
            _make_score_result(full_name=f"repo/{i}", quality_score=0.5 + i * 0.01)
            for i in range(5)
        ]
        ranking = ranker.rank(results, DomainType.LIBRARY, min_confidence=0.0)
        ranks = [r.rank for r in ranking.ranked_repos]
        assert ranks == [1, 2, 3, 4, 5]

    def test_min_value_score_filter(self, ranker) -> None:
        """Results below min_value_score are filtered."""
        results = [
            _make_score_result(full_name="repo/low", quality_score=0.1, stars=10000),
            _make_score_result(full_name="repo/high", quality_score=0.9, stars=10),
        ]
        ranking = ranker.rank(
            results,
            DomainType.LIBRARY,
            min_confidence=0.0,
            min_value_score=0.3,
        )
        # repo/low has very low value_score, repo/high has high
        assert all(r.value_score >= 0.3 for r in ranking.ranked_repos)

    def test_anti_star_bias_ranking(self) -> None:
        """Hidden gem (50 stars, quality 0.9) ranks above popular mediocre (5000 stars, 0.5)."""
        ranker = Ranker()
        results = [
            _make_score_result(
                full_name="popular/mediocre",
                quality_score=0.5,
                stars=5000,
                confidence=0.7,
            ),
            _make_score_result(
                full_name="hidden/gem",
                quality_score=0.9,
                stars=50,
                confidence=0.7,
            ),
        ]
        ranking = ranker.rank(results, DomainType.LIBRARY, min_confidence=0.0)
        assert ranking.ranked_repos[0].full_name == "hidden/gem"
