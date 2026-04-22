"""Tests for MCP server placeholder."""

from __future__ import annotations

from github_discovery.mcp.server import create_server


class TestMCPServer:
    """Test MCP server placeholder."""

    def test_create_server_returns_object(self) -> None:
        """create_server returns an object (placeholder)."""
        server = create_server()
        assert server is not None
