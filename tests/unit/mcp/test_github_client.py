"""Tests for GitHub MCP Server composition configuration."""

from __future__ import annotations

import pytest

from github_discovery.config import Settings
from github_discovery.mcp.github_client import (
    DELEGATED_TOOLS,
    DISCOVERY_TOOLS,
    get_composition_config,
)


class TestGetCompositionConfig:
    """Tests for get_composition_config function."""

    def test_get_composition_config_kilo(self, settings: Settings) -> None:
        """Kilo config has both github and github-discovery servers."""
        config = get_composition_config(settings, target="kilo")
        assert "github" in config
        assert "github-discovery" in config
        assert config["github"]["type"] == "remote"
        assert config["github-discovery"]["type"] == "local"

    def test_get_composition_config_opencode(self, settings: Settings) -> None:
        """OpenCode config has both servers."""
        config = get_composition_config(settings, target="opencode")
        assert "github" in config
        assert "github-discovery" in config

    def test_get_composition_config_claude(self, settings: Settings) -> None:
        """Claude config has only github-discovery server."""
        config = get_composition_config(settings, target="claude")
        assert "github-discovery" in config
        # Claude config does not include the GitHub MCP server
        assert "github" not in config

    def test_get_composition_config_invalid_target(self, settings: Settings) -> None:
        """Invalid target raises ValueError."""
        with pytest.raises(ValueError, match="Unknown target"):
            get_composition_config(settings, target="cursor")

    def test_kilo_config_has_readonly_header(self, settings: Settings) -> None:
        """Kilo config includes read-only header."""
        config = get_composition_config(settings, target="kilo")
        github_config = config["github"]
        assert isinstance(github_config, dict)
        headers = github_config.get("headers", {})
        assert headers.get("X-MCP-Readonly") == "true"


class TestToolLists:
    """Tests for DELEGATED_TOOLS and DISCOVERY_TOOLS."""

    def test_delegated_tools_list(self) -> None:
        """DELEGATED_TOOLS contains standard GitHub operations."""
        assert "list_repos" in DELEGATED_TOOLS
        assert "get_repo" in DELEGATED_TOOLS
        assert "read_file" in DELEGATED_TOOLS
        assert "create_issue" in DELEGATED_TOOLS
        assert len(DELEGATED_TOOLS) == 10

    def test_discovery_tools_list(self) -> None:
        """DISCOVERY_TOOLS contains GitHub Discovery MCP tools."""
        assert "discover_repos" in DISCOVERY_TOOLS
        assert "rank_repos" in DISCOVERY_TOOLS
        assert "explain_repo" in DISCOVERY_TOOLS
        assert "create_session" in DISCOVERY_TOOLS
        assert len(DISCOVERY_TOOLS) == 16

    def test_no_overlap_between_delegated_and_discovery(self) -> None:
        """DELEGATED_TOOLS and DISCOVERY_TOOLS have no overlap."""
        delegated_set = set(DELEGATED_TOOLS)
        discovery_set = set(DISCOVERY_TOOLS)
        assert delegated_set.isdisjoint(discovery_set)
