"""Tests for MCP resource: pool://{pool_id}/candidates."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from github_discovery.config import Settings
from github_discovery.mcp.resources.pool_candidates import register_pool_candidates_resource


class TestPoolCandidatesResource:
    """Tests for pool candidates resource."""

    async def test_pool_candidates_returns_string(self) -> None:
        """Resource returns string content."""
        mcp = FastMCP("test")
        register_pool_candidates_resource(mcp, Settings())

        template = mcp._resource_manager._templates["pool://{pool_id}/candidates"]
        result = await template.fn(pool_id="test-pool-id")

        assert isinstance(result, str)
        assert "test-pool-id" in result

    async def test_pool_candidates_contains_tool_reference(self) -> None:
        """Resource references the get_candidate_pool tool."""
        mcp = FastMCP("test")
        register_pool_candidates_resource(mcp, Settings())

        template = mcp._resource_manager._templates["pool://{pool_id}/candidates"]
        result = await template.fn(pool_id="abc")

        assert "get_candidate_pool" in result
