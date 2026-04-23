"""MCP transport configuration.

Supports:
- stdio: Default for Kilocode CLI, OpenCode, Claude Code local integration
- streamable-http: Recommended for production deployment (MCP SDK v1.x)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from github_discovery.config import MCPSettings

logger = structlog.get_logger("github_discovery.mcp.transport")


def get_transport_args(settings: MCPSettings) -> dict[str, object]:
    """Get transport arguments for mcp.run().

    Returns:
        Dict of keyword arguments for FastMCP.run()
    """
    if settings.transport == "stdio":
        return {"transport": "stdio"}
    elif settings.transport == "http":
        return {
            "transport": "streamable-http",
            "host": settings.host,
            "port": settings.port,
            "streamable_http_path": settings.streamable_http_path,
            "stateless_http": settings.stateless_http,
            "json_response": settings.json_response,
        }
    else:
        msg = f"Unknown MCP transport: {settings.transport}"
        raise ValueError(msg)
