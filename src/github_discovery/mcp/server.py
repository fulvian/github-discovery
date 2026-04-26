"""MCP server factory with lifespan management.

Creates a FastMCP server instance with typed AppContext, registers
all tools, resources, and prompts, and provides a serve() entry point.

All services are initialized once during lifespan startup and shared
across all MCP tool invocations (Blueprint §21.3).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from mcp.server.fastmcp import FastMCP

from github_discovery.config import Settings
from github_discovery.mcp.session import SessionManager
from github_discovery.mcp.transport import get_transport_args

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from mcp.server.fastmcp import Context
    from mcp.server.session import ServerSession

    from github_discovery.assessment.orchestrator import AssessmentOrchestrator
    from github_discovery.discovery.orchestrator import DiscoveryOrchestrator
    from github_discovery.discovery.pool import PoolManager
    from github_discovery.scoring.engine import ScoringEngine
    from github_discovery.scoring.feature_store import FeatureStore
    from github_discovery.scoring.ranker import Ranker
    from github_discovery.screening.orchestrator import ScreeningOrchestrator

logger = structlog.get_logger("github_discovery.mcp.server")


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
    # Track resources that need cleanup
    _rest_client: object = field(default=None, repr=False)


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

    # Initialize pool manager (file-based SQLite for persistence across calls)
    pool_manager = PoolManager(str(data_dir / "pools.db"))
    await pool_manager.initialize()

    # Initialize orchestrators
    rest_client = GitHubRestClient(settings.github)
    discovery_orch = DiscoveryOrchestrator(settings, pool_manager)
    gate1_screener = Gate1MetadataScreener(rest_client, settings.screening)
    gate2_screener = Gate2StaticScreener(rest_client, settings.screening, settings.github)
    screening_orch = ScreeningOrchestrator(settings, gate1_screener, gate2_screener)
    assessment_orch = AssessmentOrchestrator(settings)

    # Initialize scoring
    scoring_engine = ScoringEngine(settings.scoring)
    ranker = Ranker(settings.scoring)
    feature_store = FeatureStore(
        db_path=str(data_dir / "features.db"),
        ttl_hours=settings.scoring.feature_store_ttl_hours,
    )
    await feature_store.initialize()

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
        await feature_store.close()
        await pool_manager.close()
        await assessment_orch.close()
        await rest_client.close()
        await session_manager.close()
        logger.info("mcp_server_stopped")


def create_server(settings: Settings | None = None) -> FastMCP:
    """Create and configure the FastMCP server instance.

    Args:
        settings: Optional settings override. If None, loads from env.

    Returns:
        Configured FastMCP server with all tools, resources, and prompts registered.
    """
    _settings = settings or Settings()

    mcp = FastMCP(
        "github-discovery",
        json_response=_settings.mcp.json_response,
        lifespan=app_lifespan,
    )

    # Register tools, resources, and prompts
    from github_discovery.mcp.prompts import register_all_prompts
    from github_discovery.mcp.resources import register_all_resources
    from github_discovery.mcp.tools import register_all_tools

    register_all_tools(mcp, _settings)
    register_all_resources(mcp, _settings)
    register_all_prompts(mcp)

    return mcp


def serve(settings: Settings | None = None) -> None:
    """Start the MCP server with configured transport.

    Entry point for CLI: ``python -m github_discovery.mcp serve``
    """
    from github_discovery.logging import configure_logging

    _settings = settings or Settings()
    configure_logging(
        log_level=_settings.log_level,
        debug=_settings.debug,
    )
    server = create_server(_settings)
    transport_args = get_transport_args(_settings.mcp)
    server.run(**transport_args)  # type: ignore[arg-type]
