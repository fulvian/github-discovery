"""Test MCP integration with OpenCode configuration.

Tests OpenCode-specific workflow patterns: plan mode (lightweight)
and review mode (comparison). Validates the composition config
generation for OpenCode agent platforms.
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


class TestOpenCodeIntegration:
    """OpenCode MCP integration tests."""

    def test_mcp_config_generation(self) -> None:
        """get_composition_config('opencode') returns valid config."""
        settings = Settings(github=GitHubSettings(token="ghp_test"))  # noqa: S106
        config = get_composition_config(settings, "opencode")

        assert "github" in config
        assert "github-discovery" in config

        # OpenCode uses command/args format
        disc_config = config["github-discovery"]
        assert disc_config["command"] == "python"
        assert "args" in disc_config
        assert "serve" in disc_config["args"]
        assert "env" in disc_config

        # GitHub server uses npx
        gh_config = config["github"]
        assert gh_config["command"] == "npx"

    async def test_opencode_plan_mode_workflow(
        self,
        mcp_client: ClientSession,
    ) -> None:
        """Quick discovery + screening (no deep assessment).

        Plan mode is lightweight: discover and screen only,
        without expensive LLM assessment.
        """
        # Step 1: Create session
        session_result = await mcp_client.call_tool(
            "create_session",
            arguments={"name": "opencode-plan"},
        )
        session_text = _extract_text(session_result)
        session_data = json.loads(session_text)
        session_id = session_data["data"]["session_id"]

        # Step 2: Quick discover
        discovery = await mcp_client.call_tool(
            "discover_repos",
            arguments={
                "query": "rust cli tool",
                "max_candidates": 10,
                "session_id": session_id,
            },
        )
        assert isinstance(discovery, CallToolResult)
        assert len(discovery.content) > 0

        # Step 3: Quick screen a single repo
        quick_result = await mcp_client.call_tool(
            "quick_screen",
            arguments={
                "repo_url": "https://github.com/rust-lang/rustfmt",
                "gate_levels": "1",
            },
        )
        quick_text = _extract_text(quick_result)
        quick_data = json.loads(quick_text)
        # quick_screen may fail without real API, but protocol works
        assert "success" in quick_data

    async def test_opencode_review_mode_workflow(
        self,
        mcp_client: ClientSession,
    ) -> None:
        """Compare repos for decision-making.

        Review mode: screen + compare repos for adoption decision.
        """
        # Step 1: Create session
        session_result = await mcp_client.call_tool(
            "create_session",
            arguments={"name": "opencode-review"},
        )
        session_text = _extract_text(session_result)
        session_data = json.loads(session_text)
        _session_id = session_data["data"]["session_id"]

        # Step 2: Quick screen two repos
        await mcp_client.call_tool(
            "quick_screen",
            arguments={
                "repo_url": "https://github.com/astral-sh/ruff",
                "gate_levels": "1,2",
            },
        )
        await mcp_client.call_tool(
            "quick_screen",
            arguments={
                "repo_url": "https://github.com/psf/black",
                "gate_levels": "1,2",
            },
        )

        # Step 3: Compare repos (no scoring data, but protocol works)
        compare_result = await mcp_client.call_tool(
            "compare_repos",
            arguments={
                "repo_urls": [
                    "https://github.com/astral-sh/ruff",
                    "https://github.com/psf/black",
                ],
            },
        )
        compare_text = _extract_text(compare_result)
        compare_data = json.loads(compare_text)
        assert compare_data["success"] is True
        assert "comparison" in compare_data["data"]

    async def test_tools_support_comparison(
        self,
        mcp_client: ClientSession,
    ) -> None:
        """compare_repos tool available and callable."""
        # Verify compare_repos is in the tool list
        tools_result = await mcp_client.list_tools()
        tool_names = {t.name for t in tools_result.tools}
        assert "compare_repos" in tool_names

        # Call compare_repos with insufficient repos (1) — should error
        result = await mcp_client.call_tool(
            "compare_repos",
            arguments={
                "repo_urls": ["https://github.com/psf/requests"],
            },
        )
        text = _extract_text(result)
        data = json.loads(text)
        assert data["success"] is False
        assert "at least 2" in data.get("error_message", "").lower()
