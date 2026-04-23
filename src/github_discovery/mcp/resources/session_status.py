"""MCP resource: session://{session_id}/status.

Returns session state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from github_discovery.config import Settings


def register_session_status_resource(mcp: FastMCP, settings: Settings) -> None:
    """Register session status resource."""

    @mcp.resource("session://{session_id}/status")
    async def get_session_status_resource(session_id: str) -> str:
        """Get session state.

        URI pattern: session://session-uuid/status
        """
        return (
            f"Session {session_id} status.\n"
            f"Use get_session(session_id='{session_id}') for detailed session data."
        )
