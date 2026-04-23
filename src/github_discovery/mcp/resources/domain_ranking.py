"""MCP resource: rank://{domain}/top.

Returns top-ranked repos for a domain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from github_discovery.config import Settings


def register_domain_ranking_resource(mcp: FastMCP, settings: Settings) -> None:
    """Register domain ranking resource."""

    @mcp.resource("rank://{domain}/top")
    async def get_domain_top_ranking(domain: str) -> str:
        """Get top-ranked repos for a domain.

        URI pattern: rank://library/top
        """
        return (
            f"Top repos for domain '{domain}'.\n"
            f"Use rank_repos(domain='{domain}') for detailed ranking data."
        )
