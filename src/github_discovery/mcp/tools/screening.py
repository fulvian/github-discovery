"""MCP screening tools — screen_candidates, get_shortlist, quick_screen.

Tools for Layer B: lightweight quality screening at Gate 1 (metadata)
and Gate 2 (static/security). Agent-driven policy: thresholds are
tool parameters, not hardcoded constants.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from github_discovery.mcp.config import should_register_tool
from github_discovery.mcp.output_format import format_tool_result
from github_discovery.mcp.progress import report_screening_progress
from github_discovery.mcp.server import AppContext, get_app_context
from github_discovery.models.enums import DiscoveryChannel, GateLevel
from github_discovery.models.session import SessionStatus
from github_discovery.screening.types import ScreeningContext

if TYPE_CHECKING:
    from github_discovery.config import Settings
    from github_discovery.models.screening import ScreeningResult

logger = structlog.get_logger("github_discovery.mcp.tools.screening")

_MIN_OWNER_REPO_PARTS = 2


def _require_ctx(
    ctx: Context[ServerSession, AppContext] | None,
) -> Context[ServerSession, AppContext]:
    """Assert ctx is provided — FastMCP always passes it."""
    if ctx is None:
        msg = "Context is required but was not provided by MCP framework"
        raise RuntimeError(msg)
    return ctx


def register_screening_tools(mcp: FastMCP, settings: Settings) -> None:
    """Register screening MCP tools."""
    if should_register_tool("screen_candidates", settings):

        @mcp.tool()
        async def screen_candidates(
            pool_id: str,
            gate_level: str = "both",
            min_gate1_score: float | None = None,
            min_gate2_score: float | None = None,
            max_candidates: int = 0,
            session_id: str | None = None,
            ctx: Context[ServerSession, AppContext] | None = None,
        ) -> dict[str, object]:
            """Screen candidate repositories at specified gate level(s).

            Progressive deepening: run Gate 1, Gate 2, or both. Agent decides
            thresholds and depth.

            IMPORTANT: For large pools (>20 candidates), set max_candidates to
            process in batches. The MCP transport has a request timeout, so
            screening 50 repos in a single call will timeout. Use multiple
            calls with max_candidates=10 each, combined with session_id for
            progressive deepening.

            Args:
                pool_id: Candidate pool ID to screen
                gate_level: Screening level — "1", "2", or "both" (default: "both")
                min_gate1_score: Override Gate 1 threshold (default: from config)
                min_gate2_score: Override Gate 2 threshold (default: from config)
                max_candidates: Max repos per call (0=all, default: 0).
                    Set to 10-15 for large pools to avoid MCP timeouts.
                session_id: Optional session ID for workflow continuity
                ctx: MCP request context (injected by FastMCP)
            """
            real_ctx = _require_ctx(ctx)
            app_ctx = get_app_context(real_ctx)
            session = await app_ctx.session_manager.get_or_create(session_id)

            # Resolve pool from shared PoolManager
            pool = await app_ctx.pool_manager.get_pool(pool_id)

            if not pool:
                return format_tool_result(
                    success=False,
                    error_message=(f"Pool {pool_id} not found. Run discover_repos first."),
                )

            candidates = list(pool.candidates)
            if not candidates:
                return format_tool_result(
                    success=False,
                    error_message=(f"Pool {pool_id} is empty. No candidates to screen."),
                )

            # Batch processing: if max_candidates > 0, take only that many
            # to avoid MCP transport timeouts on large pools.
            total_in_pool = len(candidates)
            if max_candidates > 0 and len(candidates) > max_candidates:
                candidates = candidates[:max_candidates]
                logger.info(
                    "screening_batched",
                    pool_id=pool_id,
                    total_in_pool=total_in_pool,
                    batch_size=len(candidates),
                )

            # Resolve gate level
            resolved_gate = _resolve_gate_level(gate_level)

            # Build screening context (agent-driven policy)
            screen_ctx = ScreeningContext(
                pool_id=pool_id,
                candidates=candidates,
                gate_level=resolved_gate,
                min_gate1_score=(
                    min_gate1_score
                    if min_gate1_score is not None
                    else app_ctx.settings.screening.min_gate1_score
                ),
                min_gate2_score=(
                    min_gate2_score
                    if min_gate2_score is not None
                    else app_ctx.settings.screening.min_gate2_score
                ),
                session_id=session.session_id,
            )

            # Run screening via shared orchestrator
            results = await app_ctx.screening_orch.screen(screen_ctx)

            # Compute summary
            gate1_passed = sum(1 for r in results if r.gate1 and r.gate1.gate1_pass)
            gate2_passed = sum(1 for r in results if r.gate2 and r.gate2.gate2_pass)

            # Update session
            session.screened_repo_count += len(results)
            if session.status in (
                SessionStatus.CREATED,
                SessionStatus.DISCOVERING,
            ):
                session.status = SessionStatus.SCREENING
            await app_ctx.session_manager.update(session)

            # Progress notification
            await report_screening_progress(
                real_ctx,
                len(results),
                len(results),
                gate_level,
            )

            # Top 5 shortlist summary
            passed = [r for r in results if r.gate2 and r.gate2.gate2_pass]
            if not passed:
                passed = [r for r in results if r.gate1 and r.gate1.gate1_pass]
            top_5 = sorted(passed, key=_composite_score, reverse=True)[:5]

            return format_tool_result(
                summary=(
                    f"Screened {len(results)} candidates: "
                    f"{gate1_passed} passed Gate 1, "
                    f"{gate2_passed} passed Gate 2"
                ),
                data={
                    "pool_id": pool_id,
                    "total_screened": len(results),
                    "gate1_passed": gate1_passed,
                    "gate2_passed": gate2_passed,
                    "gate_level": gate_level,
                    "shortlist_top_5": [
                        {
                            "repo": r.full_name,
                            "gate1_pass": (r.gate1.gate1_pass if r.gate1 else False),
                            "gate1_score": (round(r.gate1.gate1_total, 3) if r.gate1 else None),
                            "gate2_pass": (r.gate2.gate2_pass if r.gate2 else False),
                            "gate2_score": (round(r.gate2.gate2_total, 3) if r.gate2 else None),
                        }
                        for r in top_5
                    ],
                },
                references={
                    "shortlist": f"get_shortlist(pool_id='{pool_id}')",
                    "assess": (f"deep_assess(repo_urls=[...], session_id='{session.session_id}')"),
                },
                session_id=session.session_id,
            )

    if should_register_tool("get_shortlist", settings):

        @mcp.tool()
        async def get_shortlist(
            pool_id: str,
            min_score: float = 0.5,
            domain: str | None = None,
            limit: int = 20,
            ctx: Context[ServerSession, AppContext] | None = None,
        ) -> dict[str, object]:
            """Get shortlisted candidates that passed screening.

            Returns candidates with discovery_score >= min_score, optionally
            filtered by domain. For post-screening shortlist retrieval.

            Args:
                pool_id: Candidate pool ID
                min_score: Minimum discovery score (default: 0.5)
                domain: Filter by domain type (e.g., "library", "cli")
                limit: Max results to return (default: 20)
                ctx: MCP request context (injected by FastMCP)
            """
            real_ctx = _require_ctx(ctx)
            app_ctx = get_app_context(real_ctx)

            pool = await app_ctx.pool_manager.get_pool(pool_id)

            if not pool:
                return format_tool_result(
                    success=False,
                    error_message=f"Pool {pool_id} not found",
                )

            candidates = list(pool.candidates)

            # Filter by discovery_score as proxy for composite score
            filtered = [c for c in candidates if c.discovery_score >= min_score]
            if domain:
                filtered = [c for c in filtered if c.domain and c.domain.value == domain]
            filtered = sorted(filtered, key=lambda c: c.discovery_score, reverse=True)[:limit]

            return format_tool_result(
                summary=(f"Shortlist: {len(filtered)} candidates from pool {pool_id}"),
                data={
                    "pool_id": pool_id,
                    "total": len(filtered),
                    "candidates": [
                        {
                            "repo": c.full_name,
                            "discovery_score": round(c.discovery_score, 3),
                            "domain": c.domain.value if c.domain else None,
                            "stars": c.stars,
                            "language": c.language,
                        }
                        for c in filtered
                    ],
                },
            )

    if should_register_tool("quick_screen", settings):

        @mcp.tool()
        async def quick_screen(
            repo_url: str,
            gate_levels: str = "1",
            ctx: Context[ServerSession, AppContext] | None = None,
        ) -> dict[str, object]:
            """Quick quality check on a single repository.

            Fast screening without pool context. Useful for ad-hoc checks
            on specific repositories.

            Args:
                repo_url: GitHub repository URL (e.g., "https://github.com/owner/repo")
                gate_levels: Which gates to run — "1" or "1,2" (default: "1")
                ctx: MCP request context (injected by FastMCP)
            """
            real_ctx = _require_ctx(ctx)
            app_ctx = get_app_context(real_ctx)

            # Parse repo URL to get full_name
            full_name = _parse_repo_url(repo_url)
            if not full_name:
                return format_tool_result(
                    success=False,
                    error_message=f"Invalid repository URL: {repo_url}",
                )

            # Build a minimal candidate for screening
            from datetime import UTC, datetime

            from github_discovery.models.candidate import RepoCandidate

            owner = full_name.split("/")[0]
            now = datetime.now(UTC)
            candidate = RepoCandidate(
                full_name=full_name,
                url=repo_url,
                html_url=repo_url,
                api_url=f"https://api.github.com/repos/{full_name}",
                owner_login=owner,
                source_channel=DiscoveryChannel.SEARCH,
                created_at=now,
                updated_at=now,
            )

            # Run quick screen via shared screening orchestrator
            result = await app_ctx.screening_orch.quick_screen(
                candidate,
                gate_levels=gate_levels,
            )

            return format_tool_result(
                summary=(
                    f"Quick screen for {full_name}: "
                    f"Gate1={'pass' if result.gate1 and result.gate1.gate1_pass else 'fail'}"
                    + (
                        f", Gate2={'pass' if result.gate2 and result.gate2.gate2_pass else 'fail'}"
                        if result.gate2
                        else ""
                    )
                ),
                data={
                    "repo": full_name,
                    "gate1_pass": (result.gate1.gate1_pass if result.gate1 else False),
                    "gate1_score": (round(result.gate1.gate1_total, 3) if result.gate1 else None),
                    "gate2_pass": (result.gate2.gate2_pass if result.gate2 else None),
                    "gate2_score": (round(result.gate2.gate2_total, 3) if result.gate2 else None),
                },
            )


def _resolve_gate_level(level: str) -> GateLevel:
    """Resolve gate level string to GateLevel enum.

    "1" → Gate 1 only (METADATA)
    "2" → Gate 2 only (STATIC_SECURITY) — orchestrator skips Gate 1 if not requested
    "both" → both gates — STATIC_SECURITY triggers both since Gate 2 requires Gate 1 pass
    """
    if level == "1":
        return GateLevel.METADATA
    elif level == "2":
        return GateLevel.STATIC_SECURITY
    # "both" → run both gates. The orchestrator always runs Gate 1 first,
    # and only runs Gate 2 if Gate 1 passed. Using STATIC_SECURITY covers both.
    return GateLevel.STATIC_SECURITY


def _composite_score(result: ScreeningResult) -> float:
    """Compute a composite score from a screening result."""
    score = 0.0
    if result.gate1:
        score += result.gate1.gate1_total * 0.5
    if result.gate2:
        score += result.gate2.gate2_total * 0.5
    return score


def _parse_repo_url(url: str) -> str:
    """Parse owner/repo from a GitHub URL."""
    url = url.rstrip("/")
    parts = url.split("/")
    if len(parts) >= _MIN_OWNER_REPO_PARTS:
        return f"{parts[-2]}/{parts[-1]}"
    return ""
