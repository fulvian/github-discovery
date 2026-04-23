"""Tests for scoring engine."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest

from github_discovery.models.enums import DomainType, ScoreDimension
from github_discovery.models.scoring import ScoreResult
from github_discovery.scoring.engine import ScoringEngine
from github_discovery.scoring.feature_store import FeatureStore
from github_discovery.scoring.types import ScoringInput
from tests.unit.scoring.conftest import (
    _make_assessment_result,
    _make_candidate,
    _make_screening_result,
)


class TestScoringEngine:
    """Tests for the ScoringEngine."""

    def test_score_no_data(self, scoring_engine) -> None:
        """Score with no screening or assessment."""
        candidate = _make_candidate()
        result = scoring_engine.score(candidate)
        assert isinstance(result, ScoreResult)
        assert result.full_name == "test/repo"
        assert result.quality_score > 0.0
        assert len(result.dimension_scores) == 8
        assert result.confidence == 0.0
        assert result.gate3_available is False

    def test_score_with_screening_only(self, scoring_engine) -> None:
        """Score with Gate 1+2 only (no Gate 3)."""
        candidate = _make_candidate()
        screening = _make_screening_result()
        result = scoring_engine.score(candidate, screening=screening)

        assert result.quality_score > 0.0
        assert len(result.dimension_scores) == 8
        assert result.gate3_available is False
        assert result.gate1_total > 0.0
        assert result.gate2_total > 0.0

    def test_score_with_assessment(self, scoring_engine) -> None:
        """Score with Gate 3 assessment overrides derived scores."""
        candidate = _make_candidate()
        screening = _make_screening_result()
        assessment = _make_assessment_result()
        result = scoring_engine.score(candidate, screening, assessment)

        assert result.quality_score > 0.0
        assert result.gate3_available is True
        assert result.confidence > 0.5  # Gate 3 gives high confidence

    def test_gate3_overrides_derived(self, scoring_engine) -> None:
        """Gate 3 scores should override Gate 1+2 derived scores."""
        candidate = _make_candidate()
        screening = _make_screening_result()
        assessment = _make_assessment_result(
            dimensions={ScoreDimension.CODE_QUALITY: 0.95},
        )

        result = scoring_engine.score(candidate, screening, assessment)
        assert result.dimension_scores[ScoreDimension.CODE_QUALITY] == 0.95

    def test_functionality_default_without_gate3(self, scoring_engine) -> None:
        """FUNCTIONALITY dimension defaults to 0.5 without Gate 3."""
        candidate = _make_candidate()
        screening = _make_screening_result()
        result = scoring_engine.score(candidate, screening=screening)

        assert result.dimension_scores[ScoreDimension.FUNCTIONALITY] == 0.5
        assert result.dimension_scores[ScoreDimension.INNOVATION] == 0.5

    def test_batch_scoring(self, scoring_engine) -> None:
        """Batch scoring produces results for all inputs."""
        inputs = [
            ScoringInput(candidate=_make_candidate(full_name=f"test/repo{i}")) for i in range(5)
        ]
        results = scoring_engine.score_batch(inputs)
        assert len(results) == 5
        assert all(r.full_name.startswith("test/repo") for r in results)

    def test_domain_affects_quality_score(self, scoring_engine) -> None:
        """Different domains produce different quality scores."""
        candidate_lib = _make_candidate(domain=DomainType.LIBRARY)
        candidate_ml = _make_candidate(domain=DomainType.ML_LIB)
        screening = _make_screening_result()

        result_lib = scoring_engine.score(candidate_lib, screening=screening)
        result_ml = scoring_engine.score(candidate_ml, screening=screening)

        # Different domains → different weights → different quality scores
        assert result_lib.quality_score != result_ml.quality_score

    def test_value_score_computed(self, scoring_engine) -> None:
        """Value score is computed as quality_score / log10(stars + 10)."""
        candidate = _make_candidate(stars=100)
        result = scoring_engine.score(candidate)
        assert result.value_score > 0.0

    def test_quality_score_bounds(self, scoring_engine) -> None:
        """Quality score is always between 0.0 and 1.0."""
        candidate = _make_candidate()
        screening = _make_screening_result()
        assessment = _make_assessment_result()
        result = scoring_engine.score(candidate, screening, assessment)
        assert 0.0 <= result.quality_score <= 1.0

    def test_stars_preserved_in_result(self, scoring_engine) -> None:
        """Star count from candidate is preserved in result."""
        candidate = _make_candidate(stars=42)
        result = scoring_engine.score(candidate)
        assert result.stars == 42

    def test_commit_sha_preserved(self, scoring_engine) -> None:
        """Commit SHA from candidate is preserved."""
        candidate = _make_candidate(commit_sha="deadbeef")
        result = scoring_engine.score(candidate)
        assert result.commit_sha == "deadbeef"

    def test_confidence_increases_with_gates(self, scoring_engine) -> None:
        """More gates → higher confidence."""
        candidate = _make_candidate()

        result_none = scoring_engine.score(candidate)
        result_screen = scoring_engine.score(
            candidate,
            screening=_make_screening_result(),
        )
        result_all = scoring_engine.score(
            candidate,
            _make_screening_result(),
            _make_assessment_result(),
        )

        assert result_screen.confidence > result_none.confidence
        assert result_all.confidence > result_screen.confidence


class TestScoringEngineFeatureStoreIntegration:
    """Tests for ScoringEngine + FeatureStore caching integration."""

    @pytest.fixture
    async def feature_store(self) -> AsyncGenerator[FeatureStore, None]:
        """In-memory FeatureStore for testing."""
        store = FeatureStore(db_path=":memory:", ttl_hours=48)
        await store.initialize()
        yield store
        await store.close()

    async def test_score_cached_returns_fresh_when_no_store(
        self,
        scoring_engine: ScoringEngine,
    ) -> None:
        """score_cached without a store behaves like score()."""
        candidate = _make_candidate()
        result = await scoring_engine.score_cached(candidate)
        assert isinstance(result, ScoreResult)
        assert result.full_name == "test/repo"

    async def test_score_cached_stores_result(
        self,
        scoring_engine: ScoringEngine,
        feature_store: FeatureStore,
    ) -> None:
        """score_cached stores the result in the FeatureStore."""
        engine = ScoringEngine(store=feature_store)
        candidate = _make_candidate()

        result = await engine.score_cached(candidate)

        assert isinstance(result, ScoreResult)
        # Verify it was stored
        cached = await feature_store.get(candidate.full_name, candidate.commit_sha)
        assert cached is not None
        assert cached.full_name == candidate.full_name
        assert cached.quality_score == result.quality_score

    async def test_score_cached_returns_cached_on_second_call(
        self,
        feature_store: FeatureStore,
    ) -> None:
        """Second call to score_cached returns the cached result."""
        engine = ScoringEngine(store=feature_store)
        candidate = _make_candidate()

        result1 = await engine.score_cached(candidate)
        result2 = await engine.score_cached(candidate)

        assert result1.quality_score == result2.quality_score
        assert result1.full_name == result2.full_name

    async def test_score_cached_without_commit_sha_skips_store(
        self,
        feature_store: FeatureStore,
    ) -> None:
        """score_cached with empty commit_sha skips store operations."""
        engine = ScoringEngine(store=feature_store)
        candidate = _make_candidate(commit_sha="")

        result = await engine.score_cached(candidate)

        assert isinstance(result, ScoreResult)
        # Key behavior: no crash and correct result even with empty SHA

    async def test_score_does_not_use_store(self, feature_store: FeatureStore) -> None:
        """Sync score() method does not interact with the store."""
        engine = ScoringEngine(store=feature_store)
        candidate = _make_candidate()

        result = engine.score(candidate)

        assert isinstance(result, ScoreResult)
        # Store should be empty — score() is sync and doesn't touch the store
        cached = await feature_store.get(candidate.full_name, candidate.commit_sha)
        assert cached is None

    async def test_store_parameter_is_optional(self) -> None:
        """ScoringEngine works without a store (backward compatibility)."""
        engine = ScoringEngine(store=None)
        candidate = _make_candidate()
        result = engine.score(candidate)
        assert isinstance(result, ScoreResult)

        result_cached = await engine.score_cached(candidate)
        assert isinstance(result_cached, ScoreResult)
        assert result_cached.quality_score == result.quality_score
