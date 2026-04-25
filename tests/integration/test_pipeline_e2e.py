"""End-to-end pipeline integration tests.

Validates the complete pipeline: discovery → screening → assessment → scoring → ranking.
Uses frozen test data and mocked external APIs to test INTEGRATION between components.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github_discovery.config import GitHubSettings, Settings
from github_discovery.discovery.orchestrator import DiscoveryOrchestrator
from github_discovery.discovery.pool import PoolManager
from github_discovery.discovery.types import ChannelResult, DiscoveryQuery
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import (
    DiscoveryChannel,
    DomainType,
    GateLevel,
    ScoreDimension,
)
from github_discovery.models.screening import (
    MetadataScreenResult,
    ScreeningResult,
    StaticScreenResult,
)
from github_discovery.scoring.engine import ScoringEngine
from github_discovery.scoring.feature_store import FeatureStore
from github_discovery.scoring.ranker import Ranker
from github_discovery.screening.orchestrator import ScreeningOrchestrator
from github_discovery.screening.types import ScreeningContext
from tests.integration.conftest import _make_candidate

pytestmark = pytest.mark.integration


class TestDiscoveryIntegration:
    """Integration tests for the discovery layer."""

    async def test_discovery_produces_candidates(self) -> None:
        """DiscoveryOrchestrator produces candidates from channel results."""
        settings = Settings(github=GitHubSettings(token="ghp_test"))  # noqa: S106
        pool_mgr = PoolManager(":memory:")

        orch = DiscoveryOrchestrator(settings, pool_mgr)

        sample = _make_candidate("test-org/discovered-repo")

        with patch.object(orch, "_run_channels") as mock_run:
            mock_run.return_value = [
                ChannelResult(channel=DiscoveryChannel.SEARCH, candidates=[sample]),
            ]
            query = DiscoveryQuery(query="test query", max_candidates=100)
            result = await orch.discover(query)

            assert result.total_candidates == 1
            assert result.pool_id  # non-empty
            assert "search" in result.candidates_by_channel
            assert result.candidates_by_channel["search"] == 1

        await pool_mgr.close()

    async def test_discovery_deduplicates_across_channels(self) -> None:
        """Candidates found by multiple channels are deduplicated."""
        settings = Settings(github=GitHubSettings(token="ghp_test"))  # noqa: S106
        pool_mgr = PoolManager(":memory:")

        orch = DiscoveryOrchestrator(settings, pool_mgr)

        candidate_a = _make_candidate("org/dup-repo", source_channel=DiscoveryChannel.SEARCH)
        candidate_b = _make_candidate(
            "org/dup-repo",
            source_channel=DiscoveryChannel.CODE_SEARCH,
            discovery_score=0.9,
        )

        with patch.object(orch, "_run_channels") as mock_run:
            mock_run.return_value = [
                ChannelResult(channel=DiscoveryChannel.SEARCH, candidates=[candidate_a]),
                ChannelResult(
                    channel=DiscoveryChannel.CODE_SEARCH,
                    candidates=[candidate_b],
                ),
            ]
            query = DiscoveryQuery(query="test query", max_candidates=100)
            result = await orch.discover(query)

            assert result.total_candidates == 1
            assert result.duplicate_count == 1

        await pool_mgr.close()

    async def test_discovery_respects_max_candidates(self) -> None:
        """Discovery truncates results to max_candidates."""
        settings = Settings(github=GitHubSettings(token="ghp_test"))  # noqa: S106
        pool_mgr = PoolManager(":memory:")

        orch = DiscoveryOrchestrator(settings, pool_mgr)

        candidates = [_make_candidate(f"org/repo-{i}") for i in range(10)]

        with patch.object(orch, "_run_channels") as mock_run:
            mock_run.return_value = [
                ChannelResult(channel=DiscoveryChannel.SEARCH, candidates=candidates),
            ]
            query = DiscoveryQuery(query="test query", max_candidates=3)
            result = await orch.discover(query)

            assert result.total_candidates == 3

        await pool_mgr.close()


class TestScreeningIntegration:
    """Integration tests for the screening layer (Gate 1 + Gate 2)."""

    async def test_screening_filters_candidates(self) -> None:
        """ScreeningOrchestrator filters candidates by Gate 1+2 thresholds."""
        settings = Settings(github=GitHubSettings(token="ghp_test"))  # noqa: S106

        # Create mock screeners
        mock_gate1 = AsyncMock()
        mock_gate2 = AsyncMock()

        passing_candidate = _make_candidate("org/pass-repo")
        failing_candidate = _make_candidate("org/fail-repo")

        # Gate 1: both pass
        mock_gate1.screen.side_effect = [
            MetadataScreenResult(
                full_name="org/pass-repo",
                gate1_total=0.8,
                gate1_pass=True,
            ),
            MetadataScreenResult(
                full_name="org/fail-repo",
                gate1_total=0.2,
                gate1_pass=False,
            ),
        ]

        screening_orch = ScreeningOrchestrator(settings, mock_gate1, mock_gate2)

        context = ScreeningContext(
            pool_id="test-pool",
            candidates=[passing_candidate, failing_candidate],
            gate_level=GateLevel.METADATA,
        )

        results = await screening_orch.screen(context)

        assert len(results) == 2
        passed = [r for r in results if r.gate1 and r.gate1.gate1_pass]
        failed = [r for r in results if r.gate1 and not r.gate1.gate1_pass]
        assert len(passed) == 1
        assert len(failed) == 1
        assert passed[0].full_name == "org/pass-repo"

    async def test_screening_gate2_only_if_gate1_passed(self) -> None:
        """Gate 2 is only executed for candidates that passed Gate 1."""
        settings = Settings(github=GitHubSettings(token="ghp_test"))  # noqa: S106

        mock_gate1 = AsyncMock()
        mock_gate2 = AsyncMock()

        candidate = _make_candidate("org/test-repo")

        # Gate 1 fails
        mock_gate1.screen.return_value = MetadataScreenResult(
            full_name="org/test-repo",
            gate1_total=0.2,
            gate1_pass=False,
        )

        screening_orch = ScreeningOrchestrator(settings, mock_gate1, mock_gate2)

        context = ScreeningContext(
            pool_id="test-pool",
            candidates=[candidate],
            gate_level=GateLevel.STATIC_SECURITY,
        )

        results = await screening_orch.screen(context)

        # Gate 2 should NOT have been called because Gate 1 failed
        mock_gate2.screen.assert_not_called()
        assert results[0].gate2 is None


class TestScoringIntegration:
    """Integration tests for the scoring engine (Layer D)."""

    async def test_scoring_computes_quality(self) -> None:
        """ScoringEngine computes quality scores from screening results."""
        from github_discovery.models.screening import (
            CiCdScore,
            DependencyQualityScore,
            HygieneScore,
            MaintenanceScore,
            ReleaseDisciplineScore,
            ReviewPracticeScore,
            TestFootprintScore,
        )

        engine = ScoringEngine()

        candidate = _make_candidate("org/quality-repo", stars=500)
        screening = ScreeningResult(
            full_name="org/quality-repo",
            gate1=MetadataScreenResult(
                full_name="org/quality-repo",
                hygiene=HygieneScore(value=0.8),
                maintenance=MaintenanceScore(value=0.7),
                release_discipline=ReleaseDisciplineScore(value=0.6),
                review_practice=ReviewPracticeScore(value=0.7),
                test_footprint=TestFootprintScore(value=0.8),
                ci_cd=CiCdScore(value=0.7),
                dependency_quality=DependencyQualityScore(value=0.6),
                gate1_total=0.75,
                gate1_pass=True,
            ),
            gate2=StaticScreenResult(
                full_name="org/quality-repo",
                gate2_total=0.65,
                gate2_pass=True,
            ),
        )

        result = engine.score(candidate, screening)

        assert 0.0 <= result.quality_score <= 1.0
        assert result.confidence >= 0.0
        assert len(result.dimension_scores) == len(ScoreDimension)
        assert result.stars == 500

    async def test_scoring_with_feature_store(self) -> None:
        """ScoringEngine integrates with FeatureStore for caching."""
        store = FeatureStore(":memory:")
        await store.initialize()
        engine = ScoringEngine(store=store)

        candidate = _make_candidate("org/cached-repo", commit_sha="abc123")

        result = await engine.score_cached(candidate)
        assert result is not None

        # Second call should hit cache
        cached = await engine.score_cached(candidate)
        assert cached is not None
        assert cached.full_name == "org/cached-repo"

        await store.close()


class TestRankingIntegration:
    """Integration tests for the ranking engine."""

    def test_ranking_star_neutral(self) -> None:
        """Ranker applies star-neutral scoring: hidden gems can rank higher than popular repos."""
        from github_discovery.models.scoring import ScoreResult

        ranker = Ranker()

        # Popular repo with moderate quality
        popular = ScoreResult(
            full_name="org/popular",
            domain=DomainType.LIBRARY,
            quality_score=0.6,
            confidence=0.5,
            stars=50000,
        )
        # Hidden gem with excellent quality
        hidden_gem = ScoreResult(
            full_name="org/hidden-gem",
            domain=DomainType.LIBRARY,
            quality_score=0.9,
            confidence=0.5,
            stars=42,
        )

        ranking = ranker.rank([popular, hidden_gem], DomainType.LIBRARY)

        assert len(ranking.ranked_repos) == 2
        # Hidden gem should rank #1 due to higher value_score
        assert ranking.ranked_repos[0].full_name == "org/hidden-gem"

    def test_ranking_identifies_hidden_gems(self) -> None:
        """Ranker identifies repos meeting hidden gem criteria."""
        from github_discovery.models.scoring import ScoreResult

        ranker = Ranker()

        results = [
            ScoreResult(
                full_name=f"org/repo-{i}",
                domain=DomainType.LIBRARY,
                quality_score=0.85,
                confidence=0.5,
                stars=30,
            )
            for i in range(6)
        ]

        ranking = ranker.rank(results, DomainType.LIBRARY)
        assert len(ranking.hidden_gems) > 0
        for gem in ranking.hidden_gems:
            assert gem.quality_score >= 0.7
            assert gem.stars < 500


class TestFullPipelineGateEnforcement:
    """Test that the full pipeline enforces hard gates correctly."""

    def test_no_gate3_without_gate1_and_gate2(self) -> None:
        """ScreeningResult.can_proceed_to_gate3 is False when gates not passed."""
        # No screening at all
        result_none = ScreeningResult(full_name="org/repo")
        assert not result_none.can_proceed_to_gate3

        # Gate 1 passed, Gate 2 not run
        result_g1 = ScreeningResult(
            full_name="org/repo",
            gate1=MetadataScreenResult(
                full_name="org/repo",
                gate1_total=0.8,
                gate1_pass=True,
            ),
        )
        assert not result_g1.can_proceed_to_gate3

        # Gate 1 passed, Gate 2 passed
        result_both = ScreeningResult(
            full_name="org/repo",
            gate1=MetadataScreenResult(
                full_name="org/repo",
                gate1_total=0.8,
                gate1_pass=True,
            ),
            gate2=StaticScreenResult(
                full_name="org/repo",
                gate2_total=0.7,
                gate2_pass=True,
            ),
        )
        assert result_both.can_proceed_to_gate3

    async def test_assessment_rejects_without_screening(self) -> None:
        """AssessmentOrchestrator rejects candidates that haven't passed Gate 1+2."""
        from github_discovery.assessment.orchestrator import AssessmentOrchestrator
        from github_discovery.exceptions import HardGateViolationError

        settings = Settings()
        orch = AssessmentOrchestrator(settings)

        candidate = _make_candidate("org/unscreened-repo")
        screening = ScreeningResult(full_name="org/unscreened-repo")

        with pytest.raises(HardGateViolationError):
            await orch._assess_candidate(
                candidate,
                screening,
                context=MagicMock(),
            )

        await orch.close()


class TestPipelinePreservesMetadata:
    """Test that metadata is preserved through all pipeline stages."""

    async def test_metadata_preserved_through_scoring(self) -> None:
        """Repo metadata (full_name, stars, domain) preserved through scoring."""
        engine = ScoringEngine()

        candidate = _make_candidate(
            "org/metadata-test",
            stars=1234,
            domain=DomainType.CLI,
        )

        result = engine.score(candidate)

        assert result.full_name == "org/metadata-test"
        assert result.stars == 1234
        assert result.domain == DomainType.CLI


class TestPipelineWithFrozenData:
    """Test pipeline components with frozen fixture data."""

    def test_scoring_with_frozen_data(self, sample_repos_frozen: list[RepoCandidate]) -> None:
        """ScoringEngine handles frozen fixture data correctly."""
        engine = ScoringEngine()

        # Score first 5 frozen repos
        for candidate in sample_repos_frozen[:5]:
            result = engine.score(candidate)
            assert 0.0 <= result.quality_score <= 1.0
            assert result.full_name == candidate.full_name

    def test_ranking_with_frozen_data(self, sample_repos_frozen: list[RepoCandidate]) -> None:
        """Ranker handles frozen fixture data correctly."""
        engine = ScoringEngine()
        ranker = Ranker()

        results = [engine.score(c) for c in sample_repos_frozen[:10]]

        # Rank within each domain represented
        domains = {r.domain for r in results}
        for domain in domains:
            domain_results = [r for r in results if r.domain == domain]
            ranking = ranker.rank(
                domain_results,
                domain,
                min_confidence=0.0,  # Allow zero-confidence scores
            )
            assert len(ranking.ranked_repos) == len(domain_results)


class TestPipelineExportIntegration:
    """Test pipeline results can be exported in different formats."""

    async def test_export_json_via_feature_store(self) -> None:
        """Scored results stored in FeatureStore can be serialized to JSON."""
        import json

        store = FeatureStore(":memory:")
        await store.initialize()
        engine = ScoringEngine(store=store)

        candidate = _make_candidate("org/export-test")
        result = await engine.score_cached(candidate)

        # Verify the result can be serialized to JSON
        serialized = result.model_dump_json()
        parsed = json.loads(serialized)
        assert parsed["full_name"] == "org/export-test"

        await store.close()
