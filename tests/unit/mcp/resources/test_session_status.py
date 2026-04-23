"""Tests for MCP resource: session://{session_id}/status."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from github_discovery.config import Settings
from github_discovery.mcp.resources.session_status import register_session_status_resource


class TestSessionStatusResource:
    """Tests for session status resource."""

    async def test_session_status_returns_string(self) -> None:
        """Resource returns string content."""
        mcp = FastMCP("test")
        register_session_status_resource(mcp, Settings())

        fn = mcp._resource_manager._templates["session://{session_id}/status"].fn
        result = await fn(session_id="test-session-123")

        assert isinstance(result, str)
        assert "test-session-123" in result

    async def test_session_status_contains_tool_reference(self) -> None:
        """Resource references the get_session tool."""
        mcp = FastMCP("test")
        register_session_status_resource(mcp, Settings())

        fn = mcp._resource_manager._templates["session://{session_id}/status"].fn
        result = await fn(session_id="abc")

        assert "get_session" in result
