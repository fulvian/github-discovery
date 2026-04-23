"""Tests for MCP resource: rank://{domain}/top."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from github_discovery.config import Settings
from github_discovery.mcp.resources.domain_ranking import register_domain_ranking_resource


class TestDomainRankingResource:
    """Tests for domain ranking resource."""

    async def test_domain_ranking_returns_string(self) -> None:
        """Resource returns string content."""
        mcp = FastMCP("test")
        register_domain_ranking_resource(mcp, Settings())

        fn = mcp._resource_manager._templates["rank://{domain}/top"].fn
        result = await fn(domain="library")

        assert isinstance(result, str)
        assert "library" in result

    async def test_domain_ranking_contains_tool_reference(self) -> None:
        """Resource references the rank_repos tool."""
        mcp = FastMCP("test")
        register_domain_ranking_resource(mcp, Settings())

        fn = mcp._resource_manager._templates["rank://{domain}/top"].fn
        result = await fn(domain="cli")

        assert "rank_repos" in result
