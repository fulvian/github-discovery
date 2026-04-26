"""MCP session tools — create_session, get_session, list_sessions, export_session.

Tools for session management: cross-session progressive deepening
(Blueprint §21.4). Agents create sessions, discover candidates, screen
them, and resume in later sessions without losing state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from github_discovery.mcp.config import should_register_tool
from github_discovery.mcp.output_format import format_tool_result
from github_discovery.mcp.server import AppContext, get_app_context
from github_discovery.models.agent import DiscoverySession
from github_discovery.models.session import SessionConfig, SessionStatus

if TYPE_CHECKING:
    from github_discovery.config import Settings

logger = structlog.get_logger("github_discovery.mcp.tools.session")


def _require_ctx(
    ctx: Context[ServerSession, AppContext] | None,
) -> Context[ServerSession, AppContext]:
    """Assert ctx is provided — FastMCP always passes it."""
    if ctx is None:
        msg = "Context is required but was not provided by MCP framework"
        raise RuntimeError(msg)
    return ctx


def register_session_tools(mcp: FastMCP, settings: Settings) -> None:
    """Register session MCP tools."""
    if should_register_tool("create_session", settings):

        @mcp.tool()
        async def create_session(
            name: str = "",
            min_gate1_score: float | None = None,
            min_gate2_score: float | None = None,
            max_tokens_per_repo: int | None = None,
            ctx: Context[ServerSession, AppContext] | None = None,
        ) -> dict[str, object]:
            """Create a new discovery session for workflow continuity.

            Sessions enable cross-invocation state tracking: discover candidates,
            screen them, assess, and rank across multiple tool calls.

            Args:
                name: Human-readable session name (e.g., "ml-framework-search")
                min_gate1_score: Override Gate 1 threshold for this session
                min_gate2_score: Override Gate 2 threshold for this session
                max_tokens_per_repo: Override LLM token budget per repo
                ctx: MCP request context (injected by FastMCP)
            """
            real_ctx = _require_ctx(ctx)
            app_ctx = get_app_context(real_ctx)

            # Build session config from overrides
            config = SessionConfig()
            if min_gate1_score is not None:
                config.min_gate1_score = min_gate1_score
            if min_gate2_score is not None:
                config.min_gate2_score = min_gate2_score
            if max_tokens_per_repo is not None:
                config.max_tokens_per_repo = max_tokens_per_repo

            session = await app_ctx.session_manager.create(
                name=name,
                config=config,
            )

            return format_tool_result(
                summary=(f"Created session '{session.name}' ({session.session_id[:8]}...)"),
                data={
                    "session_id": session.session_id,
                    "name": session.name,
                    "status": session.status.value,
                    "config": {
                        "min_gate1_score": session.config.min_gate1_score,
                        "min_gate2_score": session.config.min_gate2_score,
                        "max_tokens_per_repo": session.config.max_tokens_per_repo,
                    },
                },
                references={
                    "discover": (
                        f"discover_repos(query='...', session_id='{session.session_id}')"
                    ),
                    "get": (f"get_session(session_id='{session.session_id}')"),
                },
                session_id=session.session_id,
            )

    if should_register_tool("get_session", settings):

        @mcp.tool()
        async def get_session(
            session_id: str,
            ctx: Context[ServerSession, AppContext] | None = None,
        ) -> dict[str, object]:
            """Get session state and progress summary.

            Returns the session's current status, pool references, screening
            progress, assessment results, and token budget usage.

            Args:
                session_id: Session ID to retrieve
                ctx: MCP request context (injected by FastMCP)
            """
            real_ctx = _require_ctx(ctx)
            app_ctx = get_app_context(real_ctx)

            session = await app_ctx.session_manager.get(session_id)
            if not session:
                return format_tool_result(
                    success=False,
                    error_message=f"Session {session_id} not found",
                )

            # Build DiscoverySession for MCP result
            discovery_session = _build_discovery_session(session)

            # Use to_mcp_result for context-efficient output
            mcp_result = discovery_session.to_mcp_result()
            return mcp_result.model_dump()

    if should_register_tool("list_sessions", settings):

        @mcp.tool()
        async def list_sessions(
            status: str | None = None,
            limit: int = 10,
            ctx: Context[ServerSession, AppContext] | None = None,
        ) -> dict[str, object]:
            """List discovery sessions with optional status filter.

            Args:
                status: Filter by status (created, discovering, screening,
                    assessing, ranking, completed)
                limit: Max sessions to return (default: 10)
                ctx: MCP request context (injected by FastMCP)
            """
            real_ctx = _require_ctx(ctx)
            app_ctx = get_app_context(real_ctx)

            resolved_status: SessionStatus | None = None
            if status:
                try:
                    resolved_status = SessionStatus(status)
                except ValueError:
                    return format_tool_result(
                        success=False,
                        error_message=(
                            f"Invalid status '{status}'. "
                            f"Valid values: {[s.value for s in SessionStatus]}"
                        ),
                    )

            sessions = await app_ctx.session_manager.list_sessions(
                status=resolved_status,
                limit=limit,
            )

            return format_tool_result(
                summary=f"Found {len(sessions)} sessions",
                data={
                    "total": len(sessions),
                    "sessions": [
                        {
                            "session_id": s.session_id,
                            "name": s.name,
                            "status": s.status.value,
                            "discovered": s.discovered_repo_count,
                            "screened": s.screened_repo_count,
                            "assessed": s.assessed_repo_count,
                            "pools": len(s.pool_ids),
                            "created_at": s.created_at.isoformat(),
                            "updated_at": s.updated_at.isoformat(),
                        }
                        for s in sessions
                    ],
                },
            )

    if should_register_tool("export_session", settings):

        @mcp.tool()
        async def export_session(
            session_id: str,
            export_format: str = "json",
            ctx: Context[ServerSession, AppContext] | None = None,
        ) -> dict[str, object]:
            """Export session results in specified format.

            Exports the session's complete state including pool references,
            screening results, assessment data, and ranking outcomes.

            Args:
                session_id: Session ID to export
                export_format: Export format — "json", "summary" (default: "json")
                ctx: MCP request context (injected by FastMCP)
            """
            real_ctx = _require_ctx(ctx)
            app_ctx = get_app_context(real_ctx)

            session = await app_ctx.session_manager.get(session_id)
            if not session:
                return format_tool_result(
                    success=False,
                    error_message=f"Session {session_id} not found",
                )

            if export_format == "json":
                export_data = session.model_dump(mode="json")
                # Serialize datetime fields
                export_data["created_at"] = session.created_at.isoformat()
                export_data["updated_at"] = session.updated_at.isoformat()

                return format_tool_result(
                    summary=(f"Exported session '{session.name}' ({len(export_data)} fields)"),
                    data=export_data,
                    session_id=session_id,
                )

            # Summary format
            discovery_session = _build_discovery_session(session)
            mcp_result = discovery_session.to_mcp_result()

            return format_tool_result(
                summary=mcp_result.summary,
                data=mcp_result.data,
                session_id=session_id,
            )


def _build_discovery_session(session: object) -> DiscoverySession:
    """Build a DiscoverySession from a SessionState.

    Maps the persistent SessionState to the agentic DiscoverySession
    model for MCP output.
    """
    from github_discovery.models.session import SessionState

    assert isinstance(session, SessionState)
    return DiscoverySession(
        session_id=session.session_id,
        name=session.name,
        pool_ids=session.pool_ids,
        total_discovered=session.discovered_repo_count,
        total_screened=session.screened_repo_count,
        total_assessed=session.assessed_repo_count,
        tokens_budget=session.config.daily_soft_limit,
        status=session.status.value,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )
