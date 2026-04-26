"""MCP assessment tools — deep_assess, quick_assess, get_assessment.

Tools for Layer C: deep LLM-based assessment (Gate 3).
Hard gate enforced: no Gate 3 without Gate 1 + Gate 2 pass.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from github_discovery.assessment.types import AssessmentContext
from github_discovery.mcp.config import should_register_tool
from github_discovery.mcp.output_format import format_tool_result
from github_discovery.mcp.progress import report_assessment_progress
from github_discovery.mcp.server import AppContext, get_app_context
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import (
    DiscoveryChannel,
    GateLevel,
    ScoreDimension,
)
from github_discovery.models.session import SessionStatus
from github_discovery.screening.types import ScreeningContext

if TYPE_CHECKING:
    from github_discovery.config import Settings
    from github_discovery.models.screening import ScreeningResult

logger = structlog.get_logger("github_discovery.mcp.tools.assessment")


def _require_ctx(
    ctx: Context[ServerSession, AppContext] | None,
) -> Context[ServerSession, AppContext]:
    """Assert ctx is provided — FastMCP always passes it."""
    if ctx is None:
        msg = "Context is required but was not provided by MCP framework"
        raise RuntimeError(msg)
    return ctx


def register_assessment_tools(mcp: FastMCP, settings: Settings) -> None:
    """Register assessment MCP tools."""
    if should_register_tool("deep_assess", settings):

        @mcp.tool()
        async def deep_assess(
            repo_urls: list[str],
            dimensions: list[str] | None = None,
            gate3_threshold: float = 0.6,
            session_id: str | None = None,
            ctx: Context[ServerSession, AppContext] | None = None,
        ) -> dict[str, object]:
            """Deep LLM assessment of top candidates (Gate 3).

            Hard gate enforced: candidates must have passed Gate 1 + Gate 2
            before deep assessment (Blueprint §16.5). This is the expensive
            LLM-based evaluation — use only on top percentile candidates.

            Args:
                repo_urls: List of GitHub repository URLs to assess
                dimensions: Subset of dimensions to assess (default: all 8)
                gate3_threshold: Minimum Gate 3 score to pass (default: 0.6)
                session_id: Optional session ID for workflow continuity
                ctx: MCP request context (injected by FastMCP)
            """
            real_ctx = _require_ctx(ctx)
            app_ctx = get_app_context(real_ctx)
            session = await app_ctx.session_manager.get_or_create(session_id)

            # Resolve dimensions
            resolved_dims = _resolve_dimensions(dimensions)

            # Build candidates from URLs with real metadata enrichment
            candidates = await _build_candidates_with_metadata(
                app_ctx,
                repo_urls,
            )

            if not candidates:
                return format_tool_result(
                    success=False,
                    error_message="No valid repository URLs provided",
                )

            # Screen candidates first (hard gate enforcement)
            # Use Gate 1 only (metadata) for fast batch check — Gate 3
            # will do its own deep analysis via repomix. Running Gate 2
            # (clone + gitleaks/scc) for every repo here would double
            # the clone overhead and cause timeouts on batch operations.
            screening_results = await _screen_for_hard_gate(
                app_ctx,
                candidates,
                gate_level=GateLevel.METADATA,
            )

            # Filter to only candidates that passed hard gate
            # Since deep_assess uses Gate 1 only for speed, check gate1_pass
            # directly rather than can_proceed_to_gate3 (which requires Gate 2).
            eligible = [
                full_name
                for full_name, sr in screening_results.items()
                if sr.gate1 is not None and sr.gate1.gate1_pass
            ]
            eligible_candidates = [c for c in candidates if c.full_name in eligible]

            if not eligible_candidates:
                return format_tool_result(
                    success=False,
                    error_message=(
                        "No candidates passed Gate 1+2 hard gate. "
                        "Screen candidates first using screen_candidates."
                    ),
                )

            # Run deep assessment using shared orchestrator
            assess_orch = app_ctx.assessment_orch
            assess_ctx = AssessmentContext(
                candidates=eligible_candidates,
                screening_results=screening_results,
                dimensions=resolved_dims,
                gate3_threshold=gate3_threshold,
                session_id=session.session_id,
            )

            results = await assess_orch.assess(assess_ctx)

            # Update session
            session.assessed_repo_count += len(results)
            if session.status in (
                SessionStatus.CREATED,
                SessionStatus.DISCOVERING,
                SessionStatus.SCREENING,
            ):
                session.status = SessionStatus.ASSESSING
            await app_ctx.session_manager.update(session)

            # Progress notification
            await report_assessment_progress(
                real_ctx,
                len(results),
                len(candidates),
            )

            # Summary
            gate3_passed = sum(1 for r in results if r.gate3_pass)

            return format_tool_result(
                summary=(
                    f"Assessed {len(results)}/{len(candidates)} candidates: "
                    f"{gate3_passed} passed Gate 3 "
                    f"(threshold={gate3_threshold})"
                ),
                data={
                    "total_assessed": len(results),
                    "total_requested": len(candidates),
                    "gate3_passed": gate3_passed,
                    "gate3_threshold": gate3_threshold,
                    "hard_gate_blocked": (len(candidates) - len(eligible_candidates)),
                    "results_summary": [
                        {
                            "repo": r.full_name,
                            "overall_quality": round(r.overall_quality, 3),
                            "gate3_pass": r.gate3_pass,
                            "confidence": round(r.overall_confidence, 3),
                            "cached": r.cached,
                        }
                        for r in results[:10]
                    ],
                },
                references={
                    "rank": (f"rank_repos(session_id='{session.session_id}')"),
                    "explain": "explain_repo(repo_url='...')",
                },
                session_id=session.session_id,
            )

    if should_register_tool("quick_assess", settings):

        @mcp.tool()
        async def quick_assess(
            repo_url: str,
            dimensions: list[str] | None = None,
            ctx: Context[ServerSession, AppContext] | None = None,
        ) -> dict[str, object]:
            """Quick LLM assessment on a single repository.

            Subset dimension assessment for targeted evaluation.
            Useful for ad-hoc checks on specific repos.

            Args:
                repo_url: GitHub repository URL
                dimensions: Subset of dimensions to assess (default: all 8)
                ctx: MCP request context (injected by FastMCP)
            """
            real_ctx = _require_ctx(ctx)
            app_ctx = get_app_context(real_ctx)

            full_name = _parse_repo_url(repo_url)
            if not full_name:
                return format_tool_result(
                    success=False,
                    error_message=f"Invalid repository URL: {repo_url}",
                )

            # Build candidate with enriched metadata
            candidates = await _build_candidates_with_metadata(
                app_ctx,
                [repo_url],
            )
            if not candidates:
                return format_tool_result(
                    success=False,
                    error_message=f"Could not build candidate for {repo_url}",
                )
            candidate = candidates[0]

            # Run screening first (hard gate enforcement)
            # Gate 1+2 is required before Gate 3 (Blueprint §16.5)
            screening_results = await _screen_for_hard_gate(
                app_ctx,
                [candidate],
            )
            screening = screening_results.get(full_name)

            if screening is None or not screening.can_proceed_to_gate3:
                gate1_pass = screening.gate1.gate1_pass if screening and screening.gate1 else False
                gate2_pass = screening.gate2.gate2_pass if screening and screening.gate2 else False
                return format_tool_result(
                    success=False,
                    error_message=(
                        f"Gate 1+2 hard gate blocked assessment for {full_name}. "
                        f"Gate1={'pass' if gate1_pass else 'fail'}, "
                        f"Gate2={'pass' if gate2_pass else 'fail'}. "
                        f"Use screen_candidates or quick_screen first for details."
                    ),
                )

            resolved_dims = _resolve_dimensions(dimensions)

            result = await app_ctx.assessment_orch.quick_assess(
                candidate,
                screening=screening,
                dimensions=resolved_dims,
            )

            return format_tool_result(
                summary=(
                    f"Quick assess for {full_name}: "
                    f"quality={result.overall_quality:.2f}, "
                    f"pass={result.gate3_pass}"
                ),
                data={
                    "repo": full_name,
                    "overall_quality": round(result.overall_quality, 3),
                    "gate3_pass": result.gate3_pass,
                    "confidence": round(result.overall_confidence, 3),
                    "dimensions_assessed": result.dimensions_assessed,
                    "dimension_scores": {
                        dim.value: round(ds.value, 3) for dim, ds in result.dimensions.items()
                    },
                    "cached": result.cached,
                },
            )

    if should_register_tool("get_assessment", settings):

        @mcp.tool()
        async def get_assessment(
            repo_url: str,
            ctx: Context[ServerSession, AppContext] | None = None,
        ) -> dict[str, object]:
            """Retrieve cached assessment result for a repository.

            Checks the assessment cache for a previously computed result.
            Returns cache status and metadata.

            Args:
                repo_url: GitHub repository URL
                ctx: MCP request context (injected by FastMCP)
            """
            real_ctx = _require_ctx(ctx)
            app_ctx = get_app_context(real_ctx)

            full_name = _parse_repo_url(repo_url)
            if not full_name:
                return format_tool_result(
                    success=False,
                    error_message=f"Invalid repository URL: {repo_url}",
                )

            cache_size = app_ctx.assessment_orch.cache_size

            return format_tool_result(
                summary=(
                    f"Assessment cache check for {full_name}: cache has {cache_size} entries"
                ),
                data={
                    "repo": full_name,
                    "cache_size": cache_size,
                    "note": (
                        "Assessment results are cached per commit SHA. "
                        "Use deep_assess or quick_assess to populate cache."
                    ),
                },
            )


async def _build_candidates_with_metadata(
    app_ctx: AppContext,
    repo_urls: list[str],
) -> list[RepoCandidate]:
    """Build RepoCandidates from URLs, enriching with GitHub API metadata.

    Fetches real metadata (stars, description, language, commit_sha) from
    the GitHub REST API. Falls back to minimal candidates on API failure.

    Args:
        app_ctx: Application context with GitHub client access.
        repo_urls: List of GitHub repository URLs.

    Returns:
        List of RepoCandidates with enriched metadata.
    """
    now = datetime.now(UTC)
    candidates: list[RepoCandidate] = []

    for url in repo_urls:
        full_name = _parse_repo_url(url)
        if not full_name:
            continue

        owner = full_name.split("/")[0]

        # Attempt to fetch real metadata from GitHub API
        candidate = await _enrich_from_github_api(
            app_ctx,
            full_name=full_name,
            url=url,
            owner=owner,
            now=now,
        )
        candidates.append(candidate)

    return candidates


async def _enrich_from_github_api(
    app_ctx: AppContext,
    *,
    full_name: str,
    url: str,
    owner: str,
    now: datetime,
) -> RepoCandidate:
    """Fetch repo metadata from GitHub API and build a RepoCandidate.

    Falls back to a minimal candidate if the API call fails.

    Args:
        app_ctx: Application context.
        full_name: owner/repo string.
        url: Original URL.
        owner: Owner login.
        now: Current UTC datetime.

    Returns:
        RepoCandidate with enriched metadata or minimal fallback.
    """
    try:
        # Use the discovery orchestrator's REST client for GitHub API access
        rest_client = app_ctx.discovery_orch._rest_client
        repo_data = await rest_client.get_json(f"/repos/{full_name}")

        if isinstance(repo_data, dict):
            return RepoCandidate(
                full_name=full_name,
                url=url,
                html_url=url,
                api_url=f"https://api.github.com/repos/{full_name}",
                owner_login=repo_data.get("owner", {}).get("login", owner),
                description=repo_data.get("description", ""),
                stars=repo_data.get("stargazers_count", 0),
                language=repo_data.get("language"),
                forks_count=repo_data.get("forks_count", 0),
                open_issues_count=repo_data.get("open_issues_count", 0),
                commit_sha=(repo_data.get("default_branch", {}).get("sha", "")),
                created_at=repo_data.get("created_at", now),
                updated_at=repo_data.get("updated_at", now),
                pushed_at=repo_data.get("pushed_at", now),
                source_channel=DiscoveryChannel.SEARCH,
                archived=repo_data.get("archived", False),
                is_fork=repo_data.get("fork", False),
            )
    except Exception as exc:
        logger.debug(
            "metadata_enrichment_failed",
            full_name=full_name,
            error=str(exc),
        )

    # Fallback: minimal candidate with no metadata
    return RepoCandidate(
        full_name=full_name,
        url=url,
        html_url=url,
        api_url=f"https://api.github.com/repos/{full_name}",
        owner_login=owner,
        source_channel=DiscoveryChannel.SEARCH,
        created_at=now,
        updated_at=now,
    )


async def _screen_for_hard_gate(
    app_ctx: AppContext,
    candidates: list[RepoCandidate],
    *,
    gate_level: GateLevel = GateLevel.STATIC_SECURITY,
) -> dict[str, ScreeningResult]:
    """Screen candidates for hard gate enforcement before Gate 3.

    Uses the shared ScreeningOrchestrator from AppContext.
    Defaults to Gate 1+2 (STATIC_SECURITY) for full hard gate check.
    For batch operations, callers can pass GateLevel.METADATA (Gate 1 only)
    to avoid redundant cloning — Gate 3 will clone via repomix anyway.

    Args:
        app_ctx: Application context with screening orchestrator.
        candidates: Candidates to screen.
        gate_level: Which gate level to screen at.

    Returns:
        Dict of ScreeningResult keyed by full_name.
    """
    screen_ctx = ScreeningContext(
        pool_id="deep-assess-hard-gate",
        candidates=candidates,
        gate_level=gate_level,
    )
    results: list[ScreeningResult] = await app_ctx.screening_orch.screen(screen_ctx)
    return {r.full_name: r for r in results}


def _resolve_dimensions(
    dimensions: list[str] | None,
) -> list[ScoreDimension]:
    """Resolve dimension strings to ScoreDimension enums."""
    if not dimensions:
        return list(ScoreDimension)
    return [ScoreDimension(d) for d in dimensions]


_MIN_OWNER_REPO_PARTS = 2


def _parse_repo_url(url: str) -> str:
    """Parse owner/repo from a GitHub URL."""
    url = url.rstrip("/")
    parts = url.split("/")
    if len(parts) >= _MIN_OWNER_REPO_PARTS:
        return f"{parts[-2]}/{parts[-1]}"
    return ""
