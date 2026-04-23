"""MCP server factory with lifespan management.

Creates a FastMCP server instance with typed AppContext, registers
all tools, resources, and prompts, and provides a serve() entry point.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
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

logger = structlog.get_logger("github_discovery.mcp.server")


@dataclass
class AppContext:
    """Typed application context for MCP server lifespan.

    Provides all services needed by MCP tools via ctx.request_context.lifespan_context.
    """

    settings: Settings
    session_manager: SessionManager


def get_app_context(ctx: Context[ServerSession, AppContext]) -> AppContext:
    """Extract typed AppContext from MCP Context."""
    return ctx.request_context.lifespan_context


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage MCP server lifecycle with type-safe context."""
    settings = Settings()
    logger.info("mcp_server_starting", transport=settings.mcp.transport)

    # Initialize session manager
    session_manager = SessionManager(settings.mcp.session_store_path)
    await session_manager.initialize()

    try:
        yield AppContext(
            settings=settings,
            session_manager=session_manager,
        )
    finally:
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
    _settings = settings or Settings()
    server = create_server(_settings)
    transport_args = get_transport_args(_settings.mcp)
    server.run(**transport_args)  # type: ignore[arg-type]
