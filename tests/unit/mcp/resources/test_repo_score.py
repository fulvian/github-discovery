"""Tests for MCP resource: repo://{owner}/{name}/score."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from github_discovery.config import Settings
from github_discovery.mcp.resources.repo_score import register_repo_score_resource


class TestRepoScoreResource:
    """Tests for repo score resource."""

    async def test_repo_score_returns_string(self) -> None:
        """Resource returns string content."""
        mcp = FastMCP("test")
        register_repo_score_resource(mcp, Settings())

        template = mcp._resource_manager._templates["repo://{owner}/{name}/score"]
        result = await template.fn(owner="python", name="cpython")

        assert isinstance(result, str)
        assert "python/cpython" in result

    async def test_repo_score_contains_explain_reference(self) -> None:
        """Resource references the explain_repo tool."""
        mcp = FastMCP("test")
        register_repo_score_resource(mcp, Settings())

        template = mcp._resource_manager._templates["repo://{owner}/{name}/score"]
        result = await template.fn(owner="owner", name="repo")

        assert "explain_repo" in result
