"""GitHub Discovery MCP server module.

Primary interface for agent integration (Blueprint §21).
"""

from __future__ import annotations

from github_discovery.mcp.server import create_server, serve

__all__ = ["create_server", "serve"]
