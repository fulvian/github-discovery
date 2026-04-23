"""MCP tool registration dispatcher.

Registers all enabled tools with the FastMCP server instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from github_discovery.config import Settings


def register_all_tools(mcp: FastMCP, settings: Settings) -> None:
    """Register all enabled MCP tools.

    Respects enabled_toolsets and exclude_tools from MCPSettings.
    Each tool module registers its own tools via register_*_tools().
    """
    from github_discovery.mcp.config import should_register_tool
    from github_discovery.mcp.tools.assessment import register_assessment_tools
    from github_discovery.mcp.tools.discovery import register_discovery_tools
    from github_discovery.mcp.tools.ranking import register_ranking_tools
    from github_discovery.mcp.tools.screening import register_screening_tools
    from github_discovery.mcp.tools.session import register_session_tools

    register_discovery_tools(mcp, settings)
    register_screening_tools(mcp, settings)
    register_assessment_tools(mcp, settings)
    register_ranking_tools(mcp, settings)
    register_session_tools(mcp, settings)
