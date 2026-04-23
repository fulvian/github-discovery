"""Tests for AssessmentOrchestrator — Gate 3 pipeline coordinator.

Tests hard gate enforcement, cache behavior, quick_assess,
and the full assessment pipeline with mocked dependencies.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from github_discovery.assessment.orchestrator import AssessmentOrchestrator
from github_discovery.assessment.types import (
    AssessmentContext,
    HeuristicScores,
    LLMBatchOutput,
    LLMDimensionOutput,
    RepoContent,
)
from github_discovery.config import Settings
from github_discovery.exceptions import (
    AssessmentError,
    HardGateViolationError,
)
from github_discovery.models.assessment import DeepAssessmentResult, TokenUsage
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel, ScoreDimension
from github_discovery.models.screening import (
    HygieneScore,
    MetadataScreenResult,
    ScreeningResult,
    StaticScreenResult,
)


def _make_candidate(
    full_name: str = "test/repo",
    commit_sha: str = "abc123",
) -> RepoCandidate:
    """Create a test RepoCandidate."""
    return RepoCandidate(
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        html_url=f"https://github.com/{full_name}",
        api_url=f"https://api.github.com/repos/{full_name}",
        description="Test repo",
        language="Python",
        stars=50,
        owner_login="test",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-06-01T00:00:00Z",
        pushed_at="2024-06-01T00:00:00Z",
        source_channel=DiscoveryChannel.SEARCH,
        commit_sha=commit_sha,
    )


def _make_screening_passed(
    full_name: str = "test/repo",
    commit_sha: str = "abc123",
) -> ScreeningResult:
    """Create a ScreeningResult that passes both gates."""
    return ScreeningResult(
        full_name=full_name,
        commit_sha=commit_sha,
        gate1=MetadataScreenResult(
            full_name=full_name,
            hygiene=HygieneScore(value=0.7),
            gate1_total=0.6,
            gate1_pass=True,
        ),
        gate2=StaticScreenResult(
            full_name=full_name,
            gate2_total=0.6,
            gate2_pass=True,
        ),
    )


def _make_repo_content(full_name: str = "test/repo") -> RepoContent:
    """Create a test RepoContent."""
    return RepoContent(
        full_name=full_name,
        content="src/main.py\ndef hello(): pass\ntests/test_main.py\n",
        total_files=10,
        total_tokens=500,
        total_chars=2000,
        compressed=True,
        clone_url=f"https://github.com/{full_name}",
    )


def _make_heuristic_scores(full_name: str = "test/repo") -> HeuristicScores:
    """Create test HeuristicScores."""
    return HeuristicScores(
        full_name=full_name,
        file_count=10,
        has_tests=True,
        has_ci=True,
        has_docs=True,
        structure_score=0.7,
    )


def _make_orchestrator() -> AssessmentOrchestrator:
    """Create an AssessmentOrchestrator with default settings."""
    settings = Settings()
    return AssessmentOrchestrator(settings)


class TestCheckHardGate:
    """Tests for AssessmentOrchestrator._check_hard_gate."""

    def test_raises_without_screening(self) -> None:
        """_check_hard_gate raises HardGateViolationError when screening is None."""
        orchestrator = _make_orchestrator()

        with pytest.raises(HardGateViolationError) as exc_info:
            orchestrator._check_hard_gate("test/repo", None)

        assert "Gate 3 blocked" in str(exc_info.value)

    def test_raises_with_failed_screening(self) -> None:
        """_check_hard_gate raises with failed Gate 1."""
        orchestrator = _make_orchestrator()
        failed_screening = ScreeningResult(
            full_name="test/repo",
            commit_sha="abc",
            gate1=MetadataScreenResult(
                full_name="test/repo",
                gate1_total=0.2,
                gate1_pass=False,
            ),
        )

        with pytest.raises(HardGateViolationError):
            orchestrator._check_hard_gate("test/repo", failed_screening)

    def test_raises_with_gate1_passed_gate2_missing(self) -> None:
        """_check_hard_gate raises when Gate 1 passes but Gate 2 is missing."""
        orchestrator = _make_orchestrator()
        partial_screening = ScreeningResult(
            full_name="test/repo",
            commit_sha="abc",
            gate1=MetadataScreenResult(
                full_name="test/repo",
                gate1_total=0.6,
                gate1_pass=True,
            ),
            # gate2 is None
        )

        with pytest.raises(HardGateViolationError):
            orchestrator._check_hard_gate("test/repo", partial_screening)

    def test_passes_with_both_gates_passed(self) -> None:
        """_check_hard_gate passes when both gates are passed."""
        orchestrator = _make_orchestrator()
        screening = _make_screening_passed()

        # Should not raise
        orchestrator._check_hard_gate("test/repo", screening)

    def test_raises_with_gate2_failed(self) -> None:
        """_check_hard_gate raises when Gate 2 fails."""
        orchestrator = _make_orchestrator()
        screening = ScreeningResult(
            full_name="test/repo",
            commit_sha="abc",
            gate1=MetadataScreenResult(
                full_name="test/repo",
                gate1_total=0.6,
                gate1_pass=True,
            ),
            gate2=StaticScreenResult(
                full_name="test/repo",
                gate2_total=0.3,
                gate2_pass=False,
            ),
        )

        with pytest.raises(HardGateViolationError):
            orchestrator._check_hard_gate("test/repo", screening)


class TestCacheBehavior:
    """Tests for cache hit behavior in _assess_candidate."""

    async def test_cache_hit_returns_cached_result(self) -> None:
        """Cached result is returned when same repo+SHA is re-assessed."""
        orchestrator = _make_orchestrator()
        candidate = _make_candidate()
        screening = _make_screening_passed()

        # Pre-populate cache with a result (cached=False in cache)
        cached_result = DeepAssessmentResult(
            full_name="test/repo",
            commit_sha="abc123",
            overall_quality=0.85,
            gate3_pass=True,
        )
        cache_key = "test/repo:abc123"
        orchestrator._cache[cache_key] = (cached_result, time.monotonic())

        context = AssessmentContext(
            candidates=[candidate],
            screening_results={"test/repo": screening},
        )

        # _assess_candidate should return cached result with cached=True
        result = await orchestrator._assess_candidate(
            candidate,
            screening,
            context=context,
        )

        assert result.cached is True
        assert result.overall_quality == 0.85

    async def test_cache_miss_proceeds_to_assessment(self) -> None:
        """Non-cached repo proceeds to full assessment pipeline."""
        orchestrator = _make_orchestrator()
        candidate = _make_candidate()
        screening = _make_screening_passed()

        repo_content = _make_repo_content()
        heuristic_scores = _make_heuristic_scores()

        # Mock the repomix pack
        orchestrator._repomix.pack = AsyncMock(return_value=repo_content)  # type: ignore[assignment]
        # Mock the heuristic analyzer
        orchestrator._heuristic.analyze = MagicMock(return_value=heuristic_scores)  # type: ignore[assignment]
        # Mock the LLM provider
        mock_provider = AsyncMock()

        batch_output = LLMBatchOutput(
            dimensions={
                dim.value: LLMDimensionOutput(score=0.7, confidence=0.8) for dim in ScoreDimension
            },
            overall_explanation="Decent repo.",
        )
        mock_provider.assess_batch = AsyncMock(return_value=batch_output)
        mock_provider.last_token_usage = TokenUsage(total_tokens=1000)

        orchestrator._provider = mock_provider

        context = AssessmentContext(
            candidates=[candidate],
            screening_results={"test/repo": screening},
        )

        result = await orchestrator._assess_candidate(
            candidate,
            screening,
            context=context,
        )

        assert result.cached is False
        assert result.full_name == "test/repo"
        assert len(result.dimensions) == 8

    async def test_cache_key_includes_commit_sha(self) -> None:
        """Cache uses full_name:commit_sha as key."""
        orchestrator = _make_orchestrator()
        candidate_v1 = _make_candidate(commit_sha="sha1")
        _candidate_v2 = _make_candidate(commit_sha="sha2")
        screening = _make_screening_passed()

        repo_content = _make_repo_content()
        heuristic_scores = _make_heuristic_scores()

        orchestrator._repomix.pack = AsyncMock(return_value=repo_content)  # type: ignore[assignment]
        orchestrator._heuristic.analyze = MagicMock(return_value=heuristic_scores)  # type: ignore[assignment]

        mock_provider = AsyncMock()
        mock_provider.assess_batch = AsyncMock(
            return_value=LLMBatchOutput(
                dimensions={dim.value: LLMDimensionOutput(score=0.7) for dim in ScoreDimension},
            ),
        )
        mock_provider.last_token_usage = None
        orchestrator._provider = mock_provider

        context = AssessmentContext(
            candidates=[candidate_v1],
            screening_results={"test/repo": screening},
        )

        # Assess first version
        await orchestrator._assess_candidate(candidate_v1, screening, context=context)

        # Check cache has sha1 key
        assert "test/repo:sha1" in orchestrator._cache
        assert orchestrator.cache_size == 1


class TestQuickAssess:
    """Tests for AssessmentOrchestrator.quick_assess."""

    async def test_quick_assess_single_repo(self) -> None:
        """quick_assess assesses a single repo."""
        orchestrator = _make_orchestrator()
        candidate = _make_candidate()
        screening = _make_screening_passed()

        repo_content = _make_repo_content()
        heuristic_scores = _make_heuristic_scores()

        orchestrator._repomix.pack = AsyncMock(return_value=repo_content)  # type: ignore[assignment]
        orchestrator._heuristic.analyze = MagicMock(return_value=heuristic_scores)  # type: ignore[assignment]

        mock_provider = AsyncMock()
        mock_provider.assess_batch = AsyncMock(
            return_value=LLMBatchOutput(
                dimensions={
                    dim.value: LLMDimensionOutput(score=0.7, confidence=0.8)
                    for dim in ScoreDimension
                },
                overall_explanation="Adequate quality.",
            ),
        )
        mock_provider.last_token_usage = TokenUsage(total_tokens=500)
        orchestrator._provider = mock_provider

        result = await orchestrator.quick_assess(candidate, screening)

        assert isinstance(result, DeepAssessmentResult)
        assert result.full_name == "test/repo"
        assert len(result.dimensions) == 8

    async def test_quick_assess_without_screening_raises(self) -> None:
        """quick_assess raises HardGateViolationError without screening."""
        orchestrator = _make_orchestrator()
        candidate = _make_candidate()

        with pytest.raises(HardGateViolationError):
            await orchestrator.quick_assess(candidate)

    async def test_quick_assess_with_custom_dimensions(self) -> None:
        """quick_assess respects custom dimensions parameter."""
        orchestrator = _make_orchestrator()
        candidate = _make_candidate()
        screening = _make_screening_passed()

        repo_content = _make_repo_content()
        heuristic_scores = _make_heuristic_scores()

        orchestrator._repomix.pack = AsyncMock(return_value=repo_content)  # type: ignore[assignment]
        orchestrator._heuristic.analyze = MagicMock(return_value=heuristic_scores)  # type: ignore[assignment]

        mock_provider = AsyncMock()
        # Batch mode is True by default — mock assess_batch for subset dimensions
        mock_provider.assess_batch = AsyncMock(
            return_value=LLMBatchOutput(
                dimensions={
                    ScoreDimension.CODE_QUALITY.value: LLMDimensionOutput(
                        score=0.8,
                        confidence=0.7,
                    ),
                },
                overall_explanation="Good code quality.",
            ),
        )
        mock_provider.last_token_usage = TokenUsage(total_tokens=200)
        orchestrator._provider = mock_provider

        result = await orchestrator.quick_assess(
            candidate,
            screening,
            dimensions=[ScoreDimension.CODE_QUALITY],
        )

        assert isinstance(result, DeepAssessmentResult)


class TestAssess:
    """Tests for AssessmentOrchestrator.assess — batch processing."""

    async def test_assess_empty_candidates(self) -> None:
        """assess with no candidates returns empty list."""
        orchestrator = _make_orchestrator()
        context = AssessmentContext(candidates=[])

        results = await orchestrator.assess(context)

        assert results == []

    async def test_assess_single_candidate(self) -> None:
        """assess processes a single candidate."""
        orchestrator = _make_orchestrator()
        candidate = _make_candidate()
        screening = _make_screening_passed()

        repo_content = _make_repo_content()
        heuristic_scores = _make_heuristic_scores()

        orchestrator._repomix.pack = AsyncMock(return_value=repo_content)  # type: ignore[assignment]
        orchestrator._heuristic.analyze = MagicMock(return_value=heuristic_scores)  # type: ignore[assignment]

        mock_provider = AsyncMock()
        mock_provider.assess_batch = AsyncMock(
            return_value=LLMBatchOutput(
                dimensions={dim.value: LLMDimensionOutput(score=0.7) for dim in ScoreDimension},
            ),
        )
        mock_provider.last_token_usage = None
        orchestrator._provider = mock_provider

        context = AssessmentContext(
            candidates=[candidate],
            screening_results={"test/repo": screening},
        )

        results = await orchestrator.assess(context)

        assert len(results) == 1
        assert results[0].full_name == "test/repo"

    async def test_assess_fails_candidate_without_screening(self) -> None:
        """assess raises HardGateViolationError for candidates without screening."""
        orchestrator = _make_orchestrator()
        candidate = _make_candidate()

        context = AssessmentContext(
            candidates=[candidate],
            screening_results={},  # No screening result
        )

        with pytest.raises(HardGateViolationError):
            await orchestrator.assess(context)


class TestAssessCandidate:
    """Tests for _assess_candidate — the core pipeline."""

    async def test_full_pipeline_batch_mode(self) -> None:
        """_assess_candidate runs full pipeline in batch mode."""
        orchestrator = _make_orchestrator()
        candidate = _make_candidate()
        screening = _make_screening_passed()

        repo_content = _make_repo_content()
        heuristic_scores = _make_heuristic_scores()

        orchestrator._repomix.pack = AsyncMock(return_value=repo_content)  # type: ignore[assignment]
        orchestrator._heuristic.analyze = MagicMock(return_value=heuristic_scores)  # type: ignore[assignment]

        mock_provider = AsyncMock()
        batch_output = LLMBatchOutput(
            dimensions={
                dim.value: LLMDimensionOutput(score=0.75, confidence=0.8) for dim in ScoreDimension
            },
            overall_explanation="Good quality repo.",
        )
        mock_provider.assess_batch = AsyncMock(return_value=batch_output)
        mock_provider.last_token_usage = TokenUsage(
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
        )
        orchestrator._provider = mock_provider

        context = AssessmentContext(
            candidates=[candidate],
            screening_results={"test/repo": screening},
        )

        result = await orchestrator._assess_candidate(
            candidate,
            screening,
            context=context,
        )

        assert result.full_name == "test/repo"
        assert result.commit_sha == "abc123"
        assert len(result.dimensions) == 8
        assert result.token_usage.total_tokens == 1500
        assert result.assessment_duration_seconds > 0
        assert result.gate3_pass is True

    async def test_fallback_to_heuristic_on_llm_failure(self) -> None:
        """_assess_candidate falls back to heuristics when LLM fails."""
        orchestrator = _make_orchestrator()
        candidate = _make_candidate()
        screening = _make_screening_passed()

        repo_content = _make_repo_content()
        heuristic_scores = _make_heuristic_scores()

        orchestrator._repomix.pack = AsyncMock(return_value=repo_content)  # type: ignore[assignment]
        orchestrator._heuristic.analyze = MagicMock(return_value=heuristic_scores)  # type: ignore[assignment]

        mock_provider = AsyncMock()
        mock_provider.assess_batch = AsyncMock(
            side_effect=AssessmentError("LLM failed"),
        )
        orchestrator._provider = mock_provider

        context = AssessmentContext(
            candidates=[candidate],
            screening_results={"test/repo": screening},
        )

        result = await orchestrator._assess_candidate(
            candidate,
            screening,
            context=context,
        )

        # Should get heuristic fallback
        assert len(result.dimensions) == 8
        assert result.overall_confidence == 0.3

    async def test_budget_recorded_after_assessment(self) -> None:
        """_assess_candidate records token usage in budget controller."""
        orchestrator = _make_orchestrator()
        candidate = _make_candidate()
        screening = _make_screening_passed()

        repo_content = _make_repo_content()
        heuristic_scores = _make_heuristic_scores()

        orchestrator._repomix.pack = AsyncMock(return_value=repo_content)  # type: ignore[assignment]
        orchestrator._heuristic.analyze = MagicMock(return_value=heuristic_scores)  # type: ignore[assignment]

        mock_provider = AsyncMock()
        mock_provider.assess_batch = AsyncMock(
            return_value=LLMBatchOutput(
                dimensions={dim.value: LLMDimensionOutput(score=0.7) for dim in ScoreDimension},
            ),
        )
        mock_provider.last_token_usage = TokenUsage(total_tokens=1500)
        orchestrator._provider = mock_provider

        context = AssessmentContext(
            candidates=[candidate],
            screening_results={"test/repo": screening},
        )

        await orchestrator._assess_candidate(candidate, screening, context=context)

        assert orchestrator.budget_controller.daily_tokens_used == 1500
        assert orchestrator.budget_controller._repo_usage.get("test/repo") == 1500


class TestOrchestratorProperties:
    """Tests for AssessmentOrchestrator properties."""

    def test_budget_controller_property(self) -> None:
        """budget_controller returns the internal BudgetController."""
        orchestrator = _make_orchestrator()
        from github_discovery.assessment.budget_controller import BudgetController

        assert isinstance(orchestrator.budget_controller, BudgetController)

    def test_cache_size_initially_zero(self) -> None:
        """cache_size is 0 before any assessments."""
        orchestrator = _make_orchestrator()
        assert orchestrator.cache_size == 0

    async def test_close_without_provider(self) -> None:
        """close() is safe when provider hasn't been initialized."""
        orchestrator = _make_orchestrator()
        await orchestrator.close()
        # No error

    async def test_close_with_provider(self) -> None:
        """close() closes the LLM provider when initialized."""
        orchestrator = _make_orchestrator()
        mock_provider = AsyncMock()
        orchestrator._provider = mock_provider

        await orchestrator.close()

        mock_provider.close.assert_awaited_once()


class TestCacheTTL:
    """Tests for cache TTL enforcement."""

    async def test_expired_cache_entry_not_returned(self) -> None:
        """An expired cache entry is evicted and not returned."""
        orchestrator = _make_orchestrator()
        candidate = _make_candidate()
        screening = _make_screening_passed()

        # Pre-populate cache with an expired entry
        cached_result = DeepAssessmentResult(
            full_name="test/repo",
            commit_sha="abc123",
            overall_quality=0.85,
            gate3_pass=True,
        )
        cache_key = "test/repo:abc123"
        # Set timestamp far in the past (beyond default 24h TTL)
        expired_time = time.monotonic() - (25 * 3600)
        orchestrator._cache[cache_key] = (cached_result, expired_time)

        repo_content = _make_repo_content()
        heuristic_scores = _make_heuristic_scores()
        orchestrator._repomix.pack = AsyncMock(return_value=repo_content)  # type: ignore[assignment]
        orchestrator._heuristic.analyze = MagicMock(return_value=heuristic_scores)  # type: ignore[assignment]

        mock_provider = AsyncMock()
        mock_provider.assess_batch = AsyncMock(
            return_value=LLMBatchOutput(
                dimensions={
                    dim.value: LLMDimensionOutput(score=0.7, confidence=0.8)
                    for dim in ScoreDimension
                },
                overall_explanation="Fresh assessment.",
            ),
        )
        mock_provider.last_token_usage = TokenUsage(total_tokens=500)
        orchestrator._provider = mock_provider

        context = AssessmentContext(
            candidates=[candidate],
            screening_results={"test/repo": screening},
        )

        result = await orchestrator._assess_candidate(
            candidate,
            screening,
            context=context,
        )

        # Should NOT be cached — expired entry was evicted
        assert result.cached is False
        # The expired entry should have been removed
        assert cache_key not in orchestrator._cache or (
            orchestrator._cache[cache_key][1] > expired_time
        )

    async def test_fresh_cache_entry_returned(self) -> None:
        """A fresh cache entry (within TTL) is returned as cached."""
        orchestrator = _make_orchestrator()
        candidate = _make_candidate()
        screening = _make_screening_passed()

        cached_result = DeepAssessmentResult(
            full_name="test/repo",
            commit_sha="abc123",
            overall_quality=0.85,
            gate3_pass=True,
        )
        cache_key = "test/repo:abc123"
        # Set timestamp to now (within TTL)
        orchestrator._cache[cache_key] = (cached_result, time.monotonic())

        context = AssessmentContext(
            candidates=[candidate],
            screening_results={"test/repo": screening},
        )

        result = await orchestrator._assess_candidate(
            candidate,
            screening,
            context=context,
        )

        assert result.cached is True
        assert result.overall_quality == 0.85

    def test_cache_ttl_uses_settings(self) -> None:
        """Cache TTL is initialized from assessment settings."""
        orchestrator = _make_orchestrator()
        # Default is 24 hours = 86400 seconds
        assert orchestrator._cache_ttl_seconds == 86400.0
