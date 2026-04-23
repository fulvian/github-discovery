"""MCP discovery tools — discover_repos, get_candidate_pool, expand_seeds.

Tools for Layer A: candidate discovery across multiple channels.
Returns context-efficient results with pool IDs for downstream screening.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from github_discovery.discovery.types import DiscoveryQuery
from github_discovery.mcp.config import should_register_tool
from github_discovery.mcp.output_format import format_tool_result, truncate_for_context
from github_discovery.mcp.progress import report_discovery_progress
from github_discovery.mcp.server import AppContext, get_app_context
from github_discovery.models.enums import DiscoveryChannel
from github_discovery.models.session import SessionStatus

if TYPE_CHECKING:
    from github_discovery.config import Settings

logger = structlog.get_logger("github_discovery.mcp.tools.discovery")


def _require_ctx(
    ctx: Context[ServerSession, AppContext] | None,
) -> Context[ServerSession, AppContext]:
    """Assert ctx is provided — FastMCP always passes it."""
    if ctx is None:
        msg = "Context is required but was not provided by MCP framework"
        raise RuntimeError(msg)
    return ctx


def register_discovery_tools(mcp: FastMCP, settings: Settings) -> None:
    """Register discovery MCP tools."""
    if should_register_tool("discover_repos", settings):

        @mcp.tool()
        async def discover_repos(
            query: str,
            channels: list[str] | None = None,
            max_candidates: int = 50,
            session_id: str | None = None,
            ctx: Context[ServerSession, AppContext] | None = None,
        ) -> dict[str, object]:
            """Find candidate repositories matching a query across multiple channels.

            Returns a summary of discovered candidates with discovery_score.
            Use get_candidate_pool for detailed filtering and sorting.

            Args:
                query: Search query for repositories (e.g., "static analysis python")
                channels: Discovery channels to use (default: search, registry, curated)
                max_candidates: Maximum candidates to discover (default: 50)
                session_id: Optional session ID for workflow continuity
                ctx: MCP request context (injected by FastMCP)
            """
            real_ctx = _require_ctx(ctx)
            app_ctx = get_app_context(real_ctx)
            session = await app_ctx.session_manager.get_or_create(
                session_id,
                name="discovery",
            )

            # Resolve channels
            resolved_channels = None
            if channels:
                resolved_channels = [_resolve_channel(ch) for ch in channels]

            discovery_query = DiscoveryQuery(
                query=query,
                channels=resolved_channels,
                max_candidates=max_candidates,
                session_id=session.session_id,
            )

            # Use shared orchestrator from AppContext
            result = await app_ctx.discovery_orch.discover(discovery_query)

            # Update session
            session.pool_ids.append(result.pool_id)
            session.discovered_repo_count += result.total_candidates
            if session.status == SessionStatus.CREATED:
                session.status = SessionStatus.DISCOVERING
            await app_ctx.session_manager.update(session)

            # Progress notification
            await report_discovery_progress(
                real_ctx,
                result.total_candidates,
                max_candidates,
            )

            return format_tool_result(
                summary=(
                    f"Discovered {result.total_candidates} candidates "
                    f"across {len(result.channels_used)} channels"
                ),
                data={
                    "pool_id": result.pool_id,
                    "total_candidates": result.total_candidates,
                    "channels_used": [ch.value for ch in result.channels_used],
                    "duplicate_count": result.duplicate_count,
                    "elapsed_seconds": round(result.elapsed_seconds, 2),
                },
                references={
                    "pool": f"get_candidate_pool(pool_id='{result.pool_id}')",
                    "screen": (
                        f"screen_candidates(pool_id='{result.pool_id}', gate_level='both')"
                    ),
                },
                session_id=session.session_id,
            )

    if should_register_tool("get_candidate_pool", settings):

        @mcp.tool()
        async def get_candidate_pool(
            pool_id: str,
            sort_by: str = "discovery_score",
            limit: int = 20,
            offset: int = 0,
            ctx: Context[ServerSession, AppContext] | None = None,
        ) -> dict[str, object]:
            """Get candidates from a pool with filtering and sorting.

            Args:
                pool_id: Candidate pool ID from discover_repos
                sort_by: Sort field (discovery_score, name, stars)
                limit: Max candidates to return (default: 20)
                offset: Pagination offset
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
            total = len(candidates)

            # Sort before pagination
            if sort_by == "discovery_score":
                candidates.sort(key=lambda c: c.discovery_score, reverse=True)
            elif sort_by == "stars":
                candidates.sort(key=lambda c: c.stars, reverse=True)
            elif sort_by == "name":
                candidates.sort(key=lambda c: c.full_name)

            # Paginate after sorting
            page = candidates[offset : offset + limit]

            # Truncate for context efficiency
            candidate_summaries: list[dict[str, object]] = [
                {
                    "repo": c.full_name,
                    "discovery_score": round(c.discovery_score, 3),
                    "language": c.language,
                    "stars": c.stars,
                }
                for c in page
            ]
            truncated, was_truncated = truncate_for_context(candidate_summaries)

            return format_tool_result(
                summary=f"Pool {pool_id}: {total} candidates, showing {len(truncated)}",
                data={
                    "pool_id": pool_id,
                    "total_count": total,
                    "candidates": truncated,
                    "truncated": was_truncated,
                },
                detail_available_via=(f"get_candidate_pool(pool_id='{pool_id}', limit={total})"),
            )

    if should_register_tool("expand_seeds", settings):

        @mcp.tool()
        async def expand_seeds(
            seed_urls: list[str],
            expansion_strategy: str = "co_contributor",
            max_depth: int = 2,
            session_id: str | None = None,
            ctx: Context[ServerSession, AppContext] | None = None,
        ) -> dict[str, object]:
            """Expand from seed repository URLs to discover related repos.

            Uses seed expansion channel to find repos connected to the seeds
            via co-contributors, organization adjacency, or co-dependencies.

            Args:
                seed_urls: List of known repository URLs as starting points
                expansion_strategy: Strategy (co_contributor, org_adjacency, co_dependency)
                max_depth: Maximum expansion depth (default: 2)
                session_id: Optional session ID for workflow continuity
                ctx: MCP request context (injected by FastMCP)
            """
            real_ctx = _require_ctx(ctx)
            app_ctx = get_app_context(real_ctx)
            session = await app_ctx.session_manager.get_or_create(
                session_id,
                name="seed-expansion",
            )

            discovery_query = DiscoveryQuery(
                query="seed expansion",
                seed_urls=seed_urls,
                max_candidates=200,
                session_id=session.session_id,
            )

            # Use shared orchestrator from AppContext
            result = await app_ctx.discovery_orch.discover(discovery_query)

            session.pool_ids.append(result.pool_id)
            session.discovered_repo_count += result.total_candidates
            await app_ctx.session_manager.update(session)

            return format_tool_result(
                summary=(
                    f"Expanded {len(seed_urls)} seeds into {result.total_candidates} candidates"
                ),
                data={
                    "pool_id": result.pool_id,
                    "seed_count": len(seed_urls),
                    "total_candidates": result.total_candidates,
                    "strategy": expansion_strategy,
                    "channels_used": [ch.value for ch in result.channels_used],
                },
                references={
                    "pool": f"get_candidate_pool(pool_id='{result.pool_id}')",
                    "screen": (
                        f"screen_candidates(pool_id='{result.pool_id}', gate_level='both')"
                    ),
                },
                session_id=session.session_id,
            )


def _resolve_channel(channel_str: str) -> DiscoveryChannel:
    """Resolve a channel string to DiscoveryChannel enum."""
    aliases: dict[str, DiscoveryChannel] = {
        "curated": DiscoveryChannel.AWESOME_LIST,
    }
    if channel_str in aliases:
        return aliases[channel_str]
    return DiscoveryChannel(channel_str)
