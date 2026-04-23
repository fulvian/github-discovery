"""Integration tests for MCP server startup, shutdown, and registration.

Verifies that the FastMCP server:
1. Creates successfully with all tools, resources, and prompts
2. Lists correct tool/resource/prompt counts
3. Has a functional lifespan cycle
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from github_discovery.config import Settings
from github_discovery.mcp.server import AppContext, create_server


class TestMCPServerCreation:
    """Test MCP server creation and registration."""

    def test_create_server_returns_fastmcp(self, settings: Settings) -> None:
        """create_server returns a configured FastMCP instance."""
        server = create_server(settings)
        assert server.name == "github-discovery"

    def test_server_registers_16_tools(self, settings: Settings) -> None:
        """Server registers exactly 16 MCP tools."""
        server = create_server(settings)
        tools = server._tool_manager._tools
        assert len(tools) == 16

    def test_server_registers_expected_tools(self, settings: Settings) -> None:
        """Server registers all expected tool names."""
        server = create_server(settings)
        tool_names = set(server._tool_manager._tools.keys())

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

    def test_server_registers_4_resource_templates(self, settings: Settings) -> None:
        """Server registers exactly 4 MCP resource templates."""
        server = create_server(settings)
        templates = server._resource_manager._templates
        assert len(templates) == 4

    def test_server_registers_5_prompts(self, settings: Settings) -> None:
        """Server registers exactly 5 MCP prompts."""
        server = create_server(settings)
        prompts = server._prompt_manager._prompts
        assert len(prompts) == 5

    def test_server_registers_expected_prompts(self, settings: Settings) -> None:
        """Server registers all expected prompt names."""
        server = create_server(settings)
        prompt_names = set(server._prompt_manager._prompts.keys())

        expected_prompts = {
            "discover_underrated",
            "quick_quality_check",
            "compare_for_adoption",
            "domain_deep_dive",
            "security_audit",
        }
        assert prompt_names == expected_prompts

    def test_tool_filtering_excludes_tools(self) -> None:
        """Server respects exclude_tools setting."""
        settings = Settings()
        settings.mcp.exclude_tools = ["deep_assess", "compare_repos"]

        server = create_server(settings)
        tool_names = set(server._tool_manager._tools.keys())

        assert "deep_assess" not in tool_names
        assert "compare_repos" not in tool_names
        assert len(tool_names) == 14

    def test_tool_filtering_by_toolset(self) -> None:
        """Server respects enabled_toolsets setting."""
        settings = Settings()
        settings.mcp.enabled_toolsets = ["discovery"]

        server = create_server(settings)
        tool_names = set(server._tool_manager._tools.keys())

        # Only discovery tools should be registered
        expected = {"discover_repos", "get_candidate_pool", "expand_seeds"}
        assert tool_names == expected


class TestMCPServerToolDescriptions:
    """Test that all registered tools have proper descriptions."""

    def test_all_tools_have_descriptions(self, settings: Settings) -> None:
        """Every registered tool has a non-empty description."""
        server = create_server(settings)
        for name, tool in server._tool_manager._tools.items():
            assert tool.description, f"Tool {name} has no description"

    def test_all_tools_have_parameters(self, settings: Settings) -> None:
        """Every registered tool has input schema with parameters."""
        server = create_server(settings)
        for name, tool in server._tool_manager._tools.items():
            schema = tool.parameters
            assert schema is not None, f"Tool {name} has no parameters schema"
            assert "properties" in schema, f"Tool {name} schema has no properties"


class TestMCPServerLifespan:
    """Test server lifespan management."""

    @pytest.mark.asyncio
    async def test_app_context_creation(self, settings: Settings) -> None:
        """app_lifespan creates AppContext with session_manager."""
        from unittest.mock import patch

        from mcp.server.fastmcp import FastMCP

        from github_discovery.mcp.server import app_lifespan

        mcp = FastMCP("test")

        # Use in-memory SQLite for testing
        from github_discovery.mcp.session import SessionManager

        real_sm = SessionManager(":memory:")

        with patch(
            "github_discovery.mcp.server.SessionManager",
            return_value=real_sm,
        ):
            async with app_lifespan(mcp) as ctx:
                assert isinstance(ctx, AppContext)
                assert ctx.settings is not None
                assert ctx.session_manager is real_sm

    @pytest.mark.asyncio
    async def test_app_context_session_manager_closed(
        self,
        settings: Settings,
    ) -> None:
        """Session manager is closed after lifespan exit."""
        from unittest.mock import patch

        from mcp.server.fastmcp import FastMCP

        from github_discovery.mcp.server import app_lifespan

        mcp = FastMCP("test")
        mock_sm = AsyncMock()

        with patch(
            "github_discovery.mcp.server.SessionManager",
            return_value=mock_sm,
        ):
            async with app_lifespan(mcp) as ctx:
                assert ctx.session_manager is mock_sm

            # After exiting the context, close should have been called
            mock_sm.close.assert_awaited_once()
