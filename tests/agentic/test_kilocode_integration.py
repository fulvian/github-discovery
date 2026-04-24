"""Test MCP integration with Kilocode CLI configuration.

Tests the configuration and workflow patterns used by Kilocode CLI.
Validates the MCP composition config generation and the full agentic
workflow pattern from AGENTS.md §21.
"""

from __future__ import annotations

import json

import pytest
from mcp.client.session import ClientSession
from mcp.types import CallToolResult, TextContent

from github_discovery.config import GitHubSettings, Settings
from github_discovery.mcp.github_client import get_composition_config

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def _extract_text(result: CallToolResult) -> str:
    """Extract first text content from a CallToolResult."""
    for item in result.content:
        if isinstance(item, TextContent):
            return item.text
    return ""


class TestKilocodeIntegration:
    """Kilocode CLI MCP integration tests."""

    def test_mcp_config_generation(self) -> None:
        """get_composition_config('kilo') returns valid config."""
        settings = Settings(github=GitHubSettings(token="ghp_test"))  # noqa: S106
        config = get_composition_config(settings, "kilo")

        assert "github" in config
        assert "github-discovery" in config

        # GitHub server config
        gh_config = config["github"]
        assert gh_config["type"] == "remote"
        assert "headers" in gh_config
        assert gh_config["headers"]["X-MCP-Readonly"] == "true"

        # GitHub Discovery server config
        disc_config = config["github-discovery"]
        assert disc_config["type"] == "local"
        assert "command" in disc_config
        assert "environment" in disc_config
        assert "GHDISC_GITHUB_TOKEN" in disc_config["environment"]
        assert disc_config["environment"]["GHDISC_SESSION_BACKEND"] == "sqlite"

    async def test_server_starts_in_stdio_mode(self) -> None:
        """create_server produces a valid FastMCP server instance."""
        from github_discovery.mcp.server import create_server

        settings = Settings(github=GitHubSettings(token="ghp_test"))  # noqa: S106
        server = create_server(settings)

        assert server is not None
        assert server.name == "github-discovery"

    async def test_kilocode_workflow_simulation(
        self,
        mcp_client: ClientSession,
    ) -> None:
        """Full workflow: session → discover → screen → rank → explain."""
        # Step 1: Create session
        session_result = await mcp_client.call_tool(
            "create_session",
            arguments={"name": "kilo-workflow"},
        )
        session_text = _extract_text(session_result)
        session_data = json.loads(session_text)
        assert session_data["success"] is True
        session_id = session_data["data"]["session_id"]

        # Step 2: Discover
        discovery_result = await mcp_client.call_tool(
            "discover_repos",
            arguments={
                "query": "python testing framework",
                "max_candidates": 5,
                "session_id": session_id,
            },
        )
        assert isinstance(discovery_result, CallToolResult)
        assert len(discovery_result.content) > 0

        # Step 3: Screen (pool may not exist)
        screen_result = await mcp_client.call_tool(
            "screen_candidates",
            arguments={
                "pool_id": "nonexistent-kilo-pool",
                "gate_level": "both",
                "session_id": session_id,
            },
        )
        screen_text = _extract_text(screen_result)
        screen_data = json.loads(screen_text)
        assert screen_data["success"] is False  # Expected — no real data

        # Step 4: Rank (no scored results yet)
        rank_result = await mcp_client.call_tool(
            "rank_repos",
            arguments={
                "domain": "other",
                "session_id": session_id,
            },
        )
        rank_text = _extract_text(rank_result)
        rank_data = json.loads(rank_text)
        assert rank_data["success"] is False  # Expected — no scored data

        # Step 5: Explain (no scoring data)
        explain_result = await mcp_client.call_tool(
            "explain_repo",
            arguments={
                "repo_url": "https://github.com/psf/requests",
                "detail_level": "summary",
            },
        )
        explain_text = _extract_text(explain_result)
        explain_data = json.loads(explain_text)
        assert explain_data["success"] is False  # Expected — no scoring data

    async def test_tool_count_matches_spec(
        self,
        mcp_client: ClientSession,
    ) -> None:
        """16 tools available — matches AGENTS.md spec."""
        result = await mcp_client.list_tools()

        assert len(result.tools) == 16
        tool_names = {t.name for t in result.tools}
        expected_tools = {
            "discover_repos",
            "get_candidate_pool",
            "expand_seeds",
            "screen_candidates",
            "get_shortlist",
            "quick_screen",
            "deep_assess",
            "quick_assess",
            "get_assessment",
            "rank_repos",
            "explain_repo",
            "compare_repos",
            "create_session",
            "get_session",
            "list_sessions",
            "export_session",
        }
        assert tool_names == expected_tools

    async def test_prompt_skills_available(
        self,
        mcp_client: ClientSession,
    ) -> None:
        """All 5 prompt skills listed — matches AGENTS.md spec."""
        result = await mcp_client.list_prompts()

        assert len(result.prompts) == 5
        prompt_names = {p.name for p in result.prompts}
        expected_prompts = {
            "discover_underrated",
            "quick_quality_check",
            "compare_for_adoption",
            "domain_deep_dive",
            "security_audit",
        }
        assert prompt_names == expected_prompts
