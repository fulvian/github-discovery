"""MCP resource: repo://{owner}/{name}/score.

Returns the computed score for a specific repository.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from github_discovery.config import Settings


def register_repo_score_resource(mcp: FastMCP, settings: Settings) -> None:
    """Register repo score resource."""

    @mcp.resource("repo://{owner}/{name}/score")
    async def get_repo_score(owner: str, name: str) -> str:
        """Get the score for a specific repository.

        URI pattern: repo://owner/repo-name/score
        """
        full_name = f"{owner}/{name}"
        # Note: In a real MCP server with lifespan, resources would need
        # access to services via the server context. For now, return a
        # reference that the client can use with the explain_repo tool.
        return (
            f"Score for {full_name}: Use the explain_repo tool for detailed scoring.\n"
            f"  explain_repo(repo_url='https://github.com/{full_name}', detail_level='full')"
        )
