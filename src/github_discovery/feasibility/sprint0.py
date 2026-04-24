"""Sprint 0 pipeline runner for feasibility validation.

Runs the full GitHub Discovery pipeline (discovery → screening →
assessment → scoring → ranking) and collects metrics to validate
that the system finds technically superior repos vs star-based ranking.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

from github_discovery.models.enums import DomainType, GateLevel

if TYPE_CHECKING:
    from github_discovery.config import Settings
    from github_discovery.models.assessment import DeepAssessmentResult
    from github_discovery.models.candidate import RepoCandidate
    from github_discovery.models.scoring import RankedRepo, ScoreResult
    from github_discovery.models.screening import ScreeningResult

logger = structlog.get_logger("github_discovery.feasibility.sprint0")

_HIDDEN_GEM_MAX_STARS = 100
_HIDDEN_GEM_MIN_QUALITY = 0.7


@dataclass
class Sprint0Config:
    """Configuration for a Sprint 0 feasibility run.

    Attributes:
        max_candidates: Maximum candidates to discover per query.
        queries: Search queries for discovery.
        domains: Domain types to evaluate.
        gate1_threshold: Minimum Gate 1 score to pass.
        gate2_threshold: Minimum Gate 2 score to pass.
        deep_assess_percentile: Fraction of top-screened candidates for Gate 3.
        llm_budget_tokens: Maximum LLM token budget for the run.
        seed: Random seed for deterministic selection.
    """

    max_candidates: int = 500
    queries: list[str] = field(
        default_factory=lambda: [
            "static analysis python",
            "web framework rust",
            "machine learning library",
            "data pipeline tool",
            "cli tool golang",
        ],
    )
    domains: list[DomainType] = field(
        default_factory=lambda: [
            DomainType.LIBRARY,
            DomainType.CLI,
            DomainType.ML_LIB,
            DomainType.DATA_TOOL,
            DomainType.WEB_FRAMEWORK,
        ],
    )
    gate1_threshold: float = 0.4
    gate2_threshold: float = 0.3
    deep_assess_percentile: float = 0.15
    llm_budget_tokens: int = 500_000
    seed: int = 42


@dataclass
class Sprint0Result:
    """Result of a Sprint 0 feasibility run.

    Attributes:
        total_discovered: Total candidates discovered.
        gate1_passed: Candidates that passed Gate 1.
        gate2_passed: Candidates that passed Gate 2.
        gate3_assessed: Candidates that went through Gate 3.
        ranked_repos: Final ranked repos across all domains.
        hidden_gems: Repos identified as hidden gems.
        domain_distribution: Candidate count per domain.
        pipeline_duration_seconds: Total wall-clock time.
        llm_tokens_used: Total LLM tokens consumed.
    """

    total_discovered: int = 0
    gate1_passed: int = 0
    gate2_passed: int = 0
    gate3_assessed: int = 0
    ranked_repos: list[RankedRepo] = field(default_factory=list)
    hidden_gems: list[RankedRepo] = field(default_factory=list)
    domain_distribution: dict[str, int] = field(default_factory=dict)
    pipeline_duration_seconds: float = 0.0
    llm_tokens_used: int = 0


async def run_sprint0(
    settings: Settings,
    config: Sprint0Config,
    *,
    candidates: list[RepoCandidate] | None = None,
) -> Sprint0Result:
    """Run the Sprint 0 feasibility pipeline.

    Orchestrates the full discovery → screening → assessment →
    scoring → ranking pipeline and collects metrics.

    Args:
        settings: Application settings for pipeline components.
        config: Sprint 0 configuration (thresholds, queries, etc.).
        candidates: Pre-discovered candidates. If provided, discovery
            is skipped and these candidates are used directly.

    Returns:
        Sprint0Result with pipeline metrics and ranked repos.
    """
    start_time = time.monotonic()
    random.seed(config.seed)

    # --- Step 1: Discovery (or use provided candidates) ---
    all_candidates = candidates
    if all_candidates is None:
        all_candidates = await _run_discovery(settings, config)

    total_discovered = len(all_candidates)
    logger.info("sprint0_discovery_complete", total_discovered=total_discovered)

    if not all_candidates:
        elapsed = time.monotonic() - start_time
        return Sprint0Result(
            total_discovered=0,
            pipeline_duration_seconds=elapsed,
        )

    # Compute domain distribution
    domain_distribution = _compute_domain_distribution(all_candidates)

    # --- Step 2: Screening (Gate 1 + Gate 2) ---
    screening_results = await _run_screening(settings, config, all_candidates)

    gate1_passed = sum(1 for r in screening_results.values() if r.gate1 and r.gate1.gate1_pass)
    gate2_passed = sum(
        1
        for r in screening_results.values()
        if r.gate1 and r.gate1.gate1_pass and r.gate2 and r.gate2.gate2_pass
    )

    logger.info(
        "sprint0_screening_complete",
        gate1_passed=gate1_passed,
        gate2_passed=gate2_passed,
    )

    # --- Step 3: Select top percentile for Gate 3 ---
    gate2_passed_candidates = [
        c
        for c in all_candidates
        if c.full_name in screening_results and screening_results[c.full_name].can_proceed_to_gate3
    ]

    top_candidates = _select_top_percentile(
        gate2_passed_candidates,
        screening_results,
        config.deep_assess_percentile,
    )

    # --- Step 4: Deep Assessment (Gate 3) ---
    llm_tokens_used = 0
    assessment_results: dict[str, DeepAssessmentResult] = {}

    if top_candidates:
        assessment_results, llm_tokens_used = await _run_assessment(
            settings,
            config,
            top_candidates,
            screening_results,
        )

    gate3_assessed = len(top_candidates)

    logger.info(
        "sprint0_assessment_complete",
        gate3_assessed=gate3_assessed,
        llm_tokens_used=llm_tokens_used,
    )

    # --- Step 5: Scoring ---
    score_results = _run_scoring(
        settings,
        all_candidates,
        screening_results,
        assessment_results,
    )

    # --- Step 6: Ranking ---
    ranked_repos = _run_ranking(settings, score_results)

    # --- Step 7: Identify hidden gems ---
    hidden_gems = [
        r
        for r in ranked_repos
        if r.quality_score >= _HIDDEN_GEM_MIN_QUALITY and r.stars < _HIDDEN_GEM_MAX_STARS
    ]

    elapsed = time.monotonic() - start_time
    logger.info(
        "sprint0_complete",
        total_discovered=total_discovered,
        ranked=len(ranked_repos),
        hidden_gems=len(hidden_gems),
        elapsed_seconds=round(elapsed, 2),
    )

    return Sprint0Result(
        total_discovered=total_discovered,
        gate1_passed=gate1_passed,
        gate2_passed=gate2_passed,
        gate3_assessed=gate3_assessed,
        ranked_repos=ranked_repos,
        hidden_gems=hidden_gems,
        domain_distribution=domain_distribution,
        pipeline_duration_seconds=elapsed,
        llm_tokens_used=llm_tokens_used,
    )


async def _run_discovery(
    settings: Settings,
    config: Sprint0Config,
) -> list[RepoCandidate]:
    """Run discovery across all configured queries.

    Uses DiscoveryOrchestrator to discover candidates for each query,
    then deduplicates by full_name.
    """
    from github_discovery.discovery.orchestrator import DiscoveryOrchestrator  # noqa: PLC0415
    from github_discovery.discovery.pool import PoolManager  # noqa: PLC0415
    from github_discovery.discovery.types import DiscoveryQuery  # noqa: PLC0415

    pool_manager = PoolManager()
    orchestrator = DiscoveryOrchestrator(settings, pool_manager)

    seen_names: set[str] = set()
    all_candidates: list[RepoCandidate] = []

    for query_str in config.queries:
        query = DiscoveryQuery(
            query=query_str,
            max_candidates=config.max_candidates,
        )
        try:
            result = await orchestrator.discover(query)
            pool = await pool_manager.get_pool(result.pool_id)
            if pool is not None:
                for candidate in pool.candidates:
                    if candidate.full_name not in seen_names:
                        seen_names.add(candidate.full_name)
                        all_candidates.append(candidate)
        except Exception:
            logger.warning(
                "sprint0_discovery_query_failed",
                query=query_str,
            )

    return all_candidates


async def _run_screening(
    settings: Settings,
    config: Sprint0Config,
    candidates: list[RepoCandidate],
) -> dict[str, ScreeningResult]:
    """Run Gate 1 + Gate 2 screening on all candidates.

    Returns a dict mapping full_name to ScreeningResult.
    """
    from github_discovery.discovery.github_client import GitHubRestClient  # noqa: PLC0415
    from github_discovery.screening.gate1_metadata import Gate1MetadataScreener  # noqa: PLC0415
    from github_discovery.screening.gate2_static import Gate2StaticScreener  # noqa: PLC0415
    from github_discovery.screening.orchestrator import ScreeningOrchestrator  # noqa: PLC0415
    from github_discovery.screening.types import ScreeningContext  # noqa: PLC0415

    rest_client = GitHubRestClient(settings.github)
    gate1_screener = Gate1MetadataScreener(rest_client, settings.screening)
    gate2_screener = Gate2StaticScreener(
        rest_client,
        settings.screening,
        settings.github,
    )
    orchestrator = ScreeningOrchestrator(settings, gate1_screener, gate2_screener)

    context = ScreeningContext(
        pool_id="sprint0",
        candidates=candidates,
        gate_level=GateLevel.STATIC_SECURITY,
        min_gate1_score=config.gate1_threshold,
        min_gate2_score=config.gate2_threshold,
    )

    results = await orchestrator.screen(context)
    return {r.full_name: r for r in results}


def _select_top_percentile(
    candidates: list[RepoCandidate],
    screening_results: dict[str, ScreeningResult],
    percentile: float,
) -> list[RepoCandidate]:
    """Select top percentile of candidates by Gate 1+2 composite score.

    Sorts candidates by composite gate score (gate1_total + gate2_total)
    and returns the top percentile fraction.
    """
    if not candidates or percentile <= 0.0:
        return []

    scored: list[tuple[float, RepoCandidate]] = []
    for candidate in candidates:
        result = screening_results.get(candidate.full_name)
        if result is not None:
            gate1 = result.gate1.gate1_total if result.gate1 else 0.0
            gate2 = result.gate2.gate2_total if result.gate2 else 0.0
            scored.append((gate1 + gate2, candidate))
        else:
            scored.append((0.0, candidate))

    scored.sort(key=lambda x: x[0], reverse=True)

    count = max(1, int(len(scored) * percentile))
    return [c for _, c in scored[:count]]


async def _run_assessment(
    settings: Settings,
    config: Sprint0Config,
    candidates: list[RepoCandidate],
    screening_results: dict[str, ScreeningResult],
) -> tuple[dict[str, DeepAssessmentResult], int]:
    """Run Gate 3 deep assessment on selected candidates.

    Returns assessment results and total LLM tokens used.
    """
    from github_discovery.assessment.orchestrator import AssessmentOrchestrator  # noqa: PLC0415
    from github_discovery.assessment.types import AssessmentContext  # noqa: PLC0415

    orchestrator = AssessmentOrchestrator(settings)

    context = AssessmentContext(
        candidates=candidates,
        screening_results=screening_results,
    )

    total_tokens = 0
    # Pre-truncate candidate list to enforce hard budget constraint.
    # Estimate ~5000 tokens per candidate (conservative average for LLM assessment).
    _TOKENS_PER_CANDIDATE_ESTIMATE = 5_000
    max_assessable = min(
        len(candidates),
        config.llm_budget_tokens // _TOKENS_PER_CANDIDATE_ESTIMATE,
    )
    if max_assessable < len(candidates):
        logger.warning(
            "sprint0_budget_limited_candidates",
            original_count=len(candidates),
            assessable_count=max_assessable,
            budget=config.llm_budget_tokens,
        )
        context.candidates = candidates[:max_assessable]

    results_list = await orchestrator.assess(context)
    results_map: dict[str, DeepAssessmentResult] = {}

    for result in results_list:
        results_map[result.full_name] = result
        total_tokens += result.token_usage.total_tokens

        if total_tokens >= config.llm_budget_tokens:
            logger.warning(
                "sprint0_llm_budget_exceeded",
                tokens_used=total_tokens,
                budget=config.llm_budget_tokens,
            )
            break

    await orchestrator.close()
    return results_map, total_tokens


def _run_scoring(
    settings: Settings,
    candidates: list[RepoCandidate],
    screening_results: dict[str, ScreeningResult],
    assessment_results: dict[str, DeepAssessmentResult],
) -> list[ScoreResult]:
    """Score all candidates using ScoringEngine.

    Returns a list of ScoreResult for all candidates.
    """
    from github_discovery.scoring.engine import ScoringEngine  # noqa: PLC0415

    engine = ScoringEngine(settings.scoring)
    results: list[ScoreResult] = []

    for candidate in candidates:
        screening = screening_results.get(candidate.full_name)
        assessment = assessment_results.get(candidate.full_name)
        result = engine.score(candidate, screening, assessment)
        results.append(result)

    return results


def _run_ranking(
    settings: Settings,
    score_results: list[ScoreResult],
) -> list[RankedRepo]:
    """Rank scored candidates across all domains.

    Returns a flat list of RankedRepo sorted by value_score.
    """
    from github_discovery.scoring.ranker import Ranker  # noqa: PLC0415

    ranker = Ranker(settings.scoring)

    all_ranked: list[RankedRepo] = []
    domains: set[DomainType] = {r.domain for r in score_results}

    for domain in domains:
        domain_results = [r for r in score_results if r.domain == domain]
        if not domain_results:
            continue
        ranking = ranker.rank(domain_results, domain)
        all_ranked.extend(ranking.ranked_repos)

    all_ranked.sort(key=lambda r: r.value_score, reverse=True)

    return all_ranked


def _compute_domain_distribution(
    candidates: list[RepoCandidate],
) -> dict[str, int]:
    """Compute domain distribution from candidate list."""
    distribution: dict[str, int] = {}
    for candidate in candidates:
        key = candidate.domain.value
        distribution[key] = distribution.get(key, 0) + 1
    return distribution
