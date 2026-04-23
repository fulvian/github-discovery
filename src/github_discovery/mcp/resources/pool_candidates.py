"""MCP resource: pool://{pool_id}/candidates.

Returns candidates in a discovery pool.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from github_discovery.config import Settings


def register_pool_candidates_resource(mcp: FastMCP, settings: Settings) -> None:
    """Register pool candidates resource."""

    @mcp.resource("pool://{pool_id}/candidates")
    async def get_pool_candidates_resource(pool_id: str) -> str:
        """Get candidates in a pool.

        URI pattern: pool://pool-uuid/candidates
        """
        return (
            f"Candidates for pool {pool_id}.\n"
            f"Use get_candidate_pool(pool_id='{pool_id}') for detailed data."
        )
