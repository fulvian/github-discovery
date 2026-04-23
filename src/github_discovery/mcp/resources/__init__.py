"""MCP resource registration dispatcher.

Registers all MCP resources with the FastMCP server instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from github_discovery.config import Settings


def register_all_resources(mcp: FastMCP, settings: Settings) -> None:
    """Register all MCP resources.

    Resources are URI-addressable data sources for MCP clients.
    """
    from github_discovery.mcp.resources.domain_ranking import (
        register_domain_ranking_resource,
    )
    from github_discovery.mcp.resources.pool_candidates import (
        register_pool_candidates_resource,
    )
    from github_discovery.mcp.resources.repo_score import (
        register_repo_score_resource,
    )
    from github_discovery.mcp.resources.session_status import (
        register_session_status_resource,
    )

    register_repo_score_resource(mcp, settings)
    register_pool_candidates_resource(mcp, settings)
    register_domain_ranking_resource(mcp, settings)
    register_session_status_resource(mcp, settings)
