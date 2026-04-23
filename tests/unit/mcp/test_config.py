"""Tests for MCP tool filtering configuration."""

from __future__ import annotations

from github_discovery.config import MCPSettings, Settings
from github_discovery.mcp.config import (
    ALL_TOOLS,
    TOOLSET_MAP,
    get_enabled_tools,
    should_register_tool,
)


class TestGetEnabledTools:
    """Tests for get_enabled_tools function."""

    def test_get_enabled_tools_default_returns_16(self, settings: Settings) -> None:
        """Default configuration enables all 16 tools."""
        enabled = get_enabled_tools(settings)
        assert len(enabled) == 16
        assert set(enabled) == set(ALL_TOOLS)

    def test_get_enabled_tools_with_exclusion(self) -> None:
        """Excluded tools are filtered out."""
        settings = Settings(
            mcp=MCPSettings(exclude_tools=["deep_assess", "quick_assess"]),
        )
        enabled = get_enabled_tools(settings)
        assert "deep_assess" not in enabled
        assert "quick_assess" not in enabled
        # Other tools should still be present
        assert "discover_repos" in enabled

    def test_get_enabled_tools_specific_toolsets(self) -> None:
        """Only tools from specified toolsets are enabled."""
        settings = Settings(
            mcp=MCPSettings(enabled_toolsets=["discovery", "session"]),
        )
        enabled = get_enabled_tools(settings)
        discovery_tools = {"discover_repos", "get_candidate_pool", "expand_seeds"}
        session_tools = {"create_session", "get_session", "list_sessions", "export_session"}
        assert set(enabled) == discovery_tools | session_tools

    def test_get_enabled_tools_exclusion_and_toolsets(self) -> None:
        """Exclusion works with specific toolsets."""
        settings = Settings(
            mcp=MCPSettings(
                enabled_toolsets=["discovery"],
                exclude_tools=["expand_seeds"],
            ),
        )
        enabled = get_enabled_tools(settings)
        assert "expand_seeds" not in enabled
        assert "discover_repos" in enabled
        assert "get_candidate_pool" in enabled


class TestShouldRegisterTool:
    """Tests for should_register_tool function."""

    def test_should_register_tool_true(self, settings: Settings) -> None:
        """Returns True for an enabled tool."""
        assert should_register_tool("discover_repos", settings) is True

    def test_should_register_tool_false(self) -> None:
        """Returns False for an excluded tool."""
        settings = Settings(
            mcp=MCPSettings(exclude_tools=["discover_repos"]),
        )
        assert should_register_tool("discover_repos", settings) is False

    def test_should_register_tool_unknown(self) -> None:
        """Returns False for a tool not in any toolset."""
        settings = Settings()
        assert should_register_tool("nonexistent_tool", settings) is False


class TestToolsetMap:
    """Tests for TOOLSET_MAP completeness."""

    def test_toolset_map_completeness(self) -> None:
        """All tools in ALL_TOOLS appear in TOOLSET_MAP values."""
        all_mapped_tools: set[str] = set()
        for tools in TOOLSET_MAP.values():
            all_mapped_tools.update(tools)
        assert set(ALL_TOOLS) == all_mapped_tools

    def test_all_tools_in_toolset_map(self) -> None:
        """Every tool in ALL_TOOLS is in at least one toolset."""
        for tool in ALL_TOOLS:
            found = any(tool in tools for tools in TOOLSET_MAP.values())
            assert found, f"Tool '{tool}' not found in any toolset"

    def test_toolset_map_has_five_categories(self) -> None:
        """TOOLSET_MAP has exactly 5 toolset categories."""
        assert len(TOOLSET_MAP) == 5
        assert set(TOOLSET_MAP.keys()) == {
            "discovery",
            "screening",
            "assessment",
            "ranking",
            "session",
        }
