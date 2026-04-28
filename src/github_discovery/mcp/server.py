"""MCP server factory with lifespan management.

Creates a FastMCP server instance with typed AppContext, registers
all tools, resources, and prompts, and provides a serve() entry point.

All services are initialized once during lifespan startup and shared
across all MCP tool invocations (Blueprint §21.3).

GA hardening (Wave J):
- /health endpoint for HTTP transport (J2)
- API key authentication for HTTP transport (J4)
- Graceful shutdown via SIGTERM (J5)
"""

from __future__ import annotations

import asyncio
import inspect
import signal
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from starlette.requests import Request

from github_discovery import __version__
from github_discovery.config import Settings
from github_discovery.mcp.session import SessionManager
from github_discovery.mcp.transport import get_transport_args

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from mcp.server.fastmcp import Context
    from mcp.server.session import ServerSession
    from starlette.middleware.base import RequestResponseEndpoint
    from starlette.responses import Response as StarletteResponse

    from github_discovery.assessment.orchestrator import AssessmentOrchestrator
    from github_discovery.discovery.github_client import GitHubRestClient
    from github_discovery.discovery.orchestrator import DiscoveryOrchestrator
    from github_discovery.discovery.pool import PoolManager
    from github_discovery.scoring.engine import ScoringEngine
    from github_discovery.scoring.feature_store import FeatureStore
    from github_discovery.scoring.ranker import Ranker
    from github_discovery.screening.orchestrator import ScreeningOrchestrator

logger = structlog.get_logger("github_discovery.mcp.server")


async def _close_resource(resource: object) -> None:
    """Close a resource if it exposes ``close()``, supporting sync or async.

    Test doubles may provide a synchronous ``MagicMock`` close method, while
    production components expose async ``close()``. This helper supports both.
    """
    close = getattr(resource, "close", None)
    if close is None:
        return

    result = close()
    if inspect.isawaitable(result):
        await result


def _resolve_data_dir() -> Path:
    """Resolve the data directory for DB files.

    Uses GHDISC_DATA_DIR env var if set, otherwise falls back to
    ~/.local/share/github-discovery/ (XDG standard). This ensures
    the MCP server works regardless of the CWD when spawned by
    Kilocode or Claude Code.
    """
    import os

    env_dir = os.environ.get("GHDISC_DATA_DIR")
    if env_dir:
        data_dir = Path(env_dir)
    else:
        xdg_data = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
        data_dir = Path(xdg_data) / "github-discovery"

    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@dataclass
class AppContext:
    """Typed application context for MCP server lifespan.

    Provides all services needed by MCP tools via ctx.request_context.lifespan_context.
    Services are initialized once during lifespan startup and reused across invocations.
    """

    settings: Settings
    session_manager: SessionManager
    pool_manager: PoolManager
    discovery_orch: DiscoveryOrchestrator
    screening_orch: ScreeningOrchestrator
    assessment_orch: AssessmentOrchestrator
    scoring_engine: ScoringEngine
    ranker: Ranker
    feature_store: FeatureStore
    # Shared GitHub REST client for API calls (used by assessment tools)
    _rest_client: GitHubRestClient | None = field(default=None, repr=False)


def get_app_context(ctx: Context[ServerSession, AppContext]) -> AppContext:
    """Extract typed AppContext from MCP Context."""
    return ctx.request_context.lifespan_context


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage MCP server lifecycle with type-safe context.

    Initializes all services once and shares them across tool invocations.
    This follows the same pattern as the API lifespan in Phase 6.
    """
    from github_discovery.assessment.orchestrator import AssessmentOrchestrator
    from github_discovery.discovery.github_client import GitHubRestClient
    from github_discovery.discovery.orchestrator import DiscoveryOrchestrator
    from github_discovery.discovery.pool import PoolManager
    from github_discovery.scoring.engine import ScoringEngine
    from github_discovery.scoring.feature_store import FeatureStore
    from github_discovery.scoring.ranker import Ranker
    from github_discovery.screening.gate1_metadata import Gate1MetadataScreener
    from github_discovery.screening.gate2_static import Gate2StaticScreener, cleanup_orphan_clones
    from github_discovery.screening.orchestrator import ScreeningOrchestrator

    settings = Settings()
    logger.info("mcp_server_starting", transport=settings.mcp.transport)

    # Clean up orphaned clone directories from previous sessions
    cleanup_orphan_clones()

    # Resolve data directory (CWD-independent for MCP server usability)
    data_dir = _resolve_data_dir()
    logger.info("data_directory_resolved", path=str(data_dir))

    # Initialize session manager
    session_db = data_dir / "sessions.db"
    session_manager = SessionManager(str(session_db))
    await session_manager.initialize()

    # J8: Prune stale sessions on startup
    try:
        pruned = await session_manager.prune(older_than_days=30, idle_days=7)
        if pruned > 0:
            logger.info("stale_sessions_pruned", count=pruned)
    except Exception:
        logger.debug("session_prune_skipped")  # Non-critical; tolerate test mocks

    # Initialize pool manager (file-based SQLite for persistence across calls)
    pool_manager = PoolManager(str(data_dir / "pools.db"))
    await pool_manager.initialize()

    # Initialize scoring (FeatureStore first — needed by AssessmentOrchestrator)
    scoring_engine = ScoringEngine(settings.scoring)
    ranker = Ranker(settings.scoring)
    feature_store = FeatureStore(
        db_path=str(data_dir / "features.db"),
        ttl_hours=settings.scoring.feature_store_ttl_hours,
    )
    await feature_store.initialize()

    # Initialize orchestrators
    rest_client = GitHubRestClient(settings.github)
    discovery_orch = DiscoveryOrchestrator(settings, pool_manager)
    gate1_screener = Gate1MetadataScreener(rest_client, settings.screening)
    gate2_screener = Gate2StaticScreener(rest_client, settings.screening, settings.github)
    screening_orch = ScreeningOrchestrator(settings, gate1_screener, gate2_screener)
    assessment_orch = AssessmentOrchestrator(settings, feature_store=feature_store)

    try:
        yield AppContext(
            settings=settings,
            session_manager=session_manager,
            pool_manager=pool_manager,
            discovery_orch=discovery_orch,
            screening_orch=screening_orch,
            assessment_orch=assessment_orch,
            scoring_engine=scoring_engine,
            ranker=ranker,
            feature_store=feature_store,
            _rest_client=rest_client,
        )
    finally:
        await _close_resource(feature_store)
        await _close_resource(screening_orch)
        await _close_resource(discovery_orch)
        await _close_resource(pool_manager)
        await _close_resource(assessment_orch)
        await _close_resource(rest_client)
        await _close_resource(session_manager)
        # J5: Clean up orphan clones on graceful shutdown (not just startup)
        cleanup_orphan_clones()
        logger.info("mcp_server_stopped")


def _register_health_endpoint(mcp: FastMCP, settings: Settings) -> None:
    """Register a /health endpoint for the HTTP transport (Wave J2).

    Basic health returns version and service status.
    Deep health (?deep=true) runs doctor pre-flight checks for detailed diagnostics.
    """

    @mcp.custom_route("/health", methods=["GET"])  # type: ignore[untyped-decorator]
    async def health_check(request: Request) -> JSONResponse:
        is_deep = request.query_params.get("deep", "").lower() == "true"

        health_info: dict[str, object] = {
            "status": "ok",
            "service": "github-discovery-mcp",
            "version": __version__,
            "transport": settings.mcp.transport,
        }

        if is_deep:
            # Run a subset of fast doctor checks inline
            import shutil

            checks: list[dict[str, object]] = [
                {
                    "name": "git",
                    "ok": shutil.which("git") is not None,
                },
                {
                    "name": "github_token",
                    "ok": bool(settings.github.token),
                },
            ]
            health_info["checks"] = checks

        return JSONResponse(health_info)


def _build_auth_middleware(api_keys: list[str]) -> type:
    """Build a Starlette middleware class for API key auth (Wave J4).

    Returns a middleware class that validates Bearer tokens on all routes
    except /health for HTTP transport. When no API keys are configured,
    returns a no-op middleware.
    """
    from starlette.middleware.base import BaseHTTPMiddleware

    if not api_keys:
        # No-op middleware when auth is not configured
        class _NoopMiddleware(BaseHTTPMiddleware):
            async def dispatch(
                self,
                request: Request,
                call_next: RequestResponseEndpoint,
            ) -> StarletteResponse:
                return await call_next(request)

        return _NoopMiddleware

    api_key_set = set(api_keys)

    class _APIKeyMiddleware(BaseHTTPMiddleware):
        """Validate Bearer token on all routes except /health."""

        async def dispatch(
            self,
            request: Request,
            call_next: RequestResponseEndpoint,
        ) -> StarletteResponse:
            # Allow health checks without auth
            if request.url.path == "/health":
                return await call_next(request)

            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse(
                    {"error": "missing_authorization", "detail": "Bearer token required"},
                    status_code=401,
                )

            token = auth_header.removeprefix("Bearer ")
            if token not in api_key_set:
                return JSONResponse(
                    {"error": "invalid_api_key", "detail": "Invalid or revoked API key"},
                    status_code=403,
                )

            return await call_next(request)

    return _APIKeyMiddleware


def create_server(settings: Settings | None = None) -> FastMCP:
    """Create and configure the FastMCP server instance.

    Args:
        settings: Optional settings override. If None, loads from env.

    Returns:
        Configured FastMCP server with all tools, resources, and prompts registered.
    """
    _settings = settings or Settings()
    mcp_settings = _settings.mcp

    mcp = FastMCP(
        "github-discovery",
        json_response=mcp_settings.json_response,
        lifespan=app_lifespan,
    )

    # Register tools, resources, and prompts
    from github_discovery.mcp.prompts import register_all_prompts
    from github_discovery.mcp.resources import register_all_resources
    from github_discovery.mcp.tools import register_all_tools

    register_all_tools(mcp, _settings)
    register_all_resources(mcp, _settings)
    register_all_prompts(mcp)

    # Wave J2: Register health endpoint for HTTP transport
    _register_health_endpoint(mcp, _settings)

    return mcp


def serve(settings: Settings | None = None) -> None:
    """Start the MCP server with configured transport.

    Entry point for CLI: ``python -m github_discovery.mcp serve``

    GA hardening:
    - SIGTERM handler for graceful shutdown (J5)
    - API key auth middleware for HTTP transport (J4)
    """
    from github_discovery.logging import configure_logging

    _settings = settings or Settings()
    configure_logging(
        log_level=_settings.log_level,
        debug=_settings.debug,
    )
    server = create_server(_settings)
    transport_args = get_transport_args(_settings.mcp)

    # Wave J4: Add auth middleware for HTTP transport
    if _settings.mcp.transport == "http":
        AuthMiddleware = _build_auth_middleware(_settings.mcp.api_keys)
        transport_args["middleware"] = [AuthMiddleware]

    # Wave J5: Graceful shutdown — trap SIGTERM
    shutdown_event = asyncio.Event()
    active_tool_count = 0

    def _handle_sigterm(signum: int, frame: object) -> None:
        logger.info(
            "mcp_sigterm_received",
            signal=signum,
            active_tools=active_tool_count,
        )
        shutdown_event.set()
        # FastMCP will drain in-flight tools for up to 30s
        # and then close the server

    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, _handle_sigterm)

    server.run(**transport_args)  # type: ignore[arg-type]
