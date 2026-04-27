"""Assessment orchestrator — coordinates the Gate 3 deep assessment pipeline.

Flow: Hard Gate Check → Cache Check → Budget Check → Repomix Pack →
Heuristic Scoring → LLM Assessment → Result Composition → Cache Store

Hard rule (Blueprint §16.5): no candidate reaches Gate 3 without
passing both Gate 1 + Gate 2 (enforced by hard gate check).
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import structlog

from github_discovery.assessment.budget_controller import BudgetController
from github_discovery.assessment.heuristics import HeuristicAnalyzer
from github_discovery.assessment.llm_provider import LLMProvider
from github_discovery.assessment.prompts import get_prompt
from github_discovery.assessment.repomix_adapter import RepomixAdapter
from github_discovery.assessment.result_parser import ResultParser
from github_discovery.assessment.types import AssessmentContext, HeuristicScores
from github_discovery.exceptions import (
    AssessmentError,
    HardGateViolationError,
)
from github_discovery.models.assessment import (
    DeepAssessmentResult,
    DimensionScore,
    TokenUsage,
)
from github_discovery.models.enums import ScoreDimension

if TYPE_CHECKING:
    from github_discovery.config import Settings
    from github_discovery.models.candidate import RepoCandidate
    from github_discovery.models.screening import ScreeningResult

logger = structlog.get_logger(__name__)

_MAX_CONCURRENT = 3  # Conservative concurrency for LLM calls


class AssessmentOrchestrator:
    """Coordinates the Gate 3 deep assessment pipeline.

    For each candidate:
    1. Hard gate check: verify Gate 1 + Gate 2 passed
    2. Cache check: skip if already assessed (same commit SHA)
    3. Budget check: verify token budget allows assessment
    4. Repomix pack: download and pack repo content
    5. Heuristic scoring: compute non-LLM baseline
    6. LLM assessment: structured evaluation across dimensions
    7. Result composition: merge LLM + heuristic scores
    8. Budget recording: track token usage
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize with application settings.

        Args:
            settings: Application settings with assessment configuration.
        """
        self._settings = settings
        self._assessment_settings = settings.assessment

        self._repomix = RepomixAdapter(
            max_tokens=self._assessment_settings.repomix_max_tokens,
            compression=self._assessment_settings.repomix_compression,
        )
        self._heuristic = HeuristicAnalyzer()
        self._parser = ResultParser()
        self._budget = BudgetController(
            max_tokens_per_repo=self._assessment_settings.max_tokens_per_repo,
            daily_soft_limit=self._assessment_settings.daily_soft_limit,
        )
        self._provider: LLMProvider | None = None
        self._cache: dict[str, tuple[DeepAssessmentResult, float]] = {}
        self._cache_ttl_seconds: float = self._assessment_settings.cache_ttl_hours * 3600.0

    async def _ensure_provider(self) -> LLMProvider:
        """Lazily initialize the LLM provider."""
        if self._provider is None:
            self._provider = LLMProvider(
                api_key=self._assessment_settings.nanogpt_api_key,
                base_url=self._assessment_settings.effective_base_url,
                model=self._assessment_settings.llm_model,
                temperature=self._assessment_settings.llm_temperature,
                max_retries=self._assessment_settings.llm_max_retries,
                fallback_model=self._assessment_settings.llm_fallback_model,
            )
        return self._provider

    async def assess(
        self,
        context: AssessmentContext,
    ) -> list[DeepAssessmentResult]:
        """Assess a pool of candidates through Gate 3.

        Args:
            context: Assessment context with candidates and screening results.

        Returns:
            List of DeepAssessmentResult for each candidate.
        """
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

        async def _assess_one(candidate: RepoCandidate) -> DeepAssessmentResult:
            async with semaphore:
                screening = context.screening_results.get(candidate.full_name)
                return await self._assess_candidate(
                    candidate,
                    screening,
                    context=context,
                )

        tasks = [_assess_one(c) for c in context.candidates]
        results = list(await asyncio.gather(*tasks))

        logger.info(
            "assessment_batch_complete",
            total=len(results),
            gate3_passed=sum(1 for r in results if r.gate3_pass),
            from_cache=sum(1 for r in results if r.cached),
        )

        return results

    async def quick_assess(
        self,
        candidate: RepoCandidate,
        screening: ScreeningResult | None = None,
        *,
        dimensions: list[ScoreDimension] | None = None,
    ) -> DeepAssessmentResult:
        """Quick assess a single repo without full pool context.

        Used by MCP tool quick_assess for single-repo assessment.
        Requires only Gate 1 (metadata) — no clone needed. This makes
        the "quick" assessment actually quick.

        Args:
            candidate: Repo to assess.
            screening: Optional screening results.
            dimensions: Optional subset of dimensions.

        Returns:
            DeepAssessmentResult for the repository.
        """
        context = AssessmentContext(
            candidates=[candidate],
            screening_results={candidate.full_name: screening} if screening else {},
            dimensions=dimensions or list(ScoreDimension),
            gate3_threshold=self._assessment_settings.gate3_threshold,
        )
        result = await self._assess_candidate(
            candidate,
            screening,
            context=context,
            required_gates=1,
        )
        return result

    async def _assess_candidate(
        self,
        candidate: RepoCandidate,
        screening: ScreeningResult | None,
        *,
        context: AssessmentContext,
        required_gates: int = 2,
    ) -> DeepAssessmentResult:
        """Assess a single candidate through the full Gate 3 pipeline.

        Args:
            candidate: Repo to assess.
            screening: Optional screening results.
            context: Assessment context.
            required_gates: Number of gates required (1=Gate 1 only, 2=Gate 1+2).
        """
        full_name = candidate.full_name
        log = logger.bind(full_name=full_name)
        start_time = time.monotonic()

        # Step 1: Hard gate check
        self._check_hard_gate(full_name, screening, required_gates=required_gates)

        # Step 2: Cache check
        cache_key = f"{full_name}:{candidate.commit_sha}"
        if cache_key in self._cache:
            cached_result, cached_at = self._cache[cache_key]
            if time.monotonic() - cached_at < self._cache_ttl_seconds:
                log.info("assessment_cache_hit")
                data = cached_result.model_dump()
                data["cached"] = True
                return DeepAssessmentResult(**data)
            # TTL expired — evict stale entry
            del self._cache[cache_key]
            log.debug("assessment_cache_expired", cache_key=cache_key)

        # Step 3: Soft daily limit check (monitoring only, never blocks)
        self._budget.check_daily_soft_limit(full_name)

        try:
            # Step 3b: Pre-pack budget check using repomix_max_tokens estimate
            self._budget.check_repo_budget(
                full_name,
                self._assessment_settings.repomix_max_tokens,
            )

            # Step 4: Repomix pack
            repo_content = await self._repomix.pack(
                candidate.html_url,
                full_name,
            )
            self._budget.check_repo_budget(full_name, repo_content.total_tokens)

            # Step 5: Heuristic scoring
            heuristic_scores = self._heuristic.analyze(repo_content)

            # Step 6: LLM assessment
            provider = await self._ensure_provider()

            if context.batch_mode:
                result = await self._assess_batch(
                    provider,
                    candidate,
                    repo_content.content,
                    heuristic_scores,
                    context,
                )
            else:
                result = await self._assess_per_dimension(
                    provider,
                    candidate,
                    repo_content.content,
                    heuristic_scores,
                    context,
                )

            # Step 7: Record timing
            duration = time.monotonic() - start_time
            result.assessment_duration_seconds = duration

            # Step 8: Record budget
            if result.token_usage:
                self._budget.record_usage(
                    result.token_usage,
                    full_name=full_name,
                )

            # Cache the result with current timestamp
            self._cache[cache_key] = (result, time.monotonic())

            log.info(
                "assessment_complete",
                overall_quality=result.overall_quality,
                gate3_pass=result.gate3_pass,
                dimensions=len(result.dimensions),
                duration_seconds=duration,
            )

            return result

        except AssessmentError:
            raise
        except Exception as exc:
            log.error("assessment_failed", error=str(exc))
            raise AssessmentError(
                f"Gate 3 assessment failed for {full_name}: {exc}",
                repo_url=candidate.html_url,
            ) from exc

    async def _assess_batch(
        self,
        provider: LLMProvider,
        candidate: RepoCandidate,
        repo_content: str,
        heuristic_scores: HeuristicScores,
        context: AssessmentContext,
    ) -> DeepAssessmentResult:
        """Assess all dimensions in a single batch LLM call."""
        # Build combined system prompt
        prompts = [get_prompt(d) for d in context.dimensions]
        combined_prompt = "\n\n---\n\n".join(prompts)

        try:
            batch_output = await provider.assess_batch(
                context.dimensions,
                combined_prompt,
                repo_content,
            )
        except AssessmentError:
            logger.warning(
                "batch_assessment_failed_using_heuristic_fallback",
                full_name=candidate.full_name,
            )
            return self._parser.create_heuristic_fallback(
                heuristic_scores,
                candidate.full_name,
                candidate.commit_sha,
                gate3_threshold=context.gate3_threshold,
            )

        return self._parser.parse_batch(
            batch_output,
            candidate.full_name,
            candidate.commit_sha,
            token_usage=provider.last_token_usage,
            heuristic_scores=heuristic_scores,
            gate3_threshold=context.gate3_threshold,
        )

    async def _assess_per_dimension(
        self,
        provider: LLMProvider,
        candidate: RepoCandidate,
        repo_content: str,
        heuristic_scores: HeuristicScores,
        context: AssessmentContext,
    ) -> DeepAssessmentResult:
        """Assess dimensions individually (fallback when batch fails)."""
        dimension_scores: dict[ScoreDimension, DimensionScore] = {}
        total_prompt_tokens = 0
        total_completion_tokens = 0

        for dimension in context.dimensions:
            prompt = get_prompt(dimension)
            try:
                llm_output = await provider.assess_dimension(
                    dimension,
                    prompt,
                    repo_content,
                )
                dimension_scores[dimension] = self._parser.parse_dimension(
                    dimension,
                    llm_output,
                    candidate.full_name,
                    candidate.commit_sha,
                )
            except AssessmentError:
                logger.warning(
                    "dimension_assessment_failed",
                    dimension=dimension.value,
                    full_name=candidate.full_name,
                )

            # Accumulate token usage
            if provider.last_token_usage:
                total_prompt_tokens += provider.last_token_usage.prompt_tokens
                total_completion_tokens += provider.last_token_usage.completion_tokens

        aggregate_usage = TokenUsage(
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            total_tokens=total_prompt_tokens + total_completion_tokens,
            model_used=self._assessment_settings.llm_model,
            provider="nanogpt",
        )

        return self._parser.compose_from_dimensions(
            dimension_scores,
            candidate.full_name,
            candidate.commit_sha,
            overall_explanation="Assessed per-dimension (individual LLM calls)",
            token_usage=aggregate_usage,
            heuristic_scores=heuristic_scores,
            gate3_threshold=context.gate3_threshold,
        )

    def _check_hard_gate(
        self,
        full_name: str,
        screening: ScreeningResult | None,
        *,
        required_gates: int = 2,
    ) -> None:
        """Verify required gates passed before Gate 3.

        Hard rule (Blueprint §16.5): no deep-scan LLM below
        Gate 1+2 threshold for batch assess. For quick_assess,
        only Gate 1 is required (no clone overhead).

        Args:
            full_name: Repository full name.
            screening: Screening result (may be None).
            required_gates: 1 = Gate 1 only, 2 = Gate 1+2 (default).
        """
        gate_passed = 0
        if screening is not None:
            if screening.gate2 is not None and screening.gate2.gate2_pass:
                gate_passed = 2
            elif screening.gate1 is not None and screening.gate1.gate1_pass:
                gate_passed = 1

        if gate_passed < required_gates:
            raise HardGateViolationError(
                f"Gate 3 blocked for {full_name}: "
                f"Gate {required_gates} must pass before deep assessment",
                repo_url=full_name,
                gate_passed=gate_passed,
                gate_required=required_gates,
            )

    @property
    def budget_controller(self) -> BudgetController:
        """Access the budget controller for status queries."""
        return self._budget

    @property
    def cache_size(self) -> int:
        """Number of cached assessment results."""
        return len(self._cache)

    async def close(self) -> None:
        """Close resources (LLM provider)."""
        if self._provider is not None:
            await self._provider.close()
            self._provider = None
