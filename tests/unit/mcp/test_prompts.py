"""Tests for MCP prompt registration and content."""

from __future__ import annotations

import pytest
from mcp.server.fastmcp import FastMCP

from github_discovery.mcp.prompts import register_all_prompts


class TestPromptRegistration:
    """Tests for prompt registration."""

    def test_register_all_prompts(self) -> None:
        """register_all_prompts registers 5 prompts without error."""
        mcp = FastMCP("test-prompts")
        register_all_prompts(mcp)
        # FastMCP stores prompts in _prompt_manager
        prompt_names = list(mcp._prompt_manager._prompts.keys())
        assert len(prompt_names) == 5

    def test_all_prompt_names_registered(self) -> None:
        """All 5 prompt skill names are registered."""
        mcp = FastMCP("test-prompts")
        register_all_prompts(mcp)
        prompt_names = set(mcp._prompt_manager._prompts.keys())
        expected = {
            "discover_underrated",
            "quick_quality_check",
            "compare_for_adoption",
            "domain_deep_dive",
            "security_audit",
        }
        assert expected == prompt_names


class TestPromptContent:
    """Tests for prompt skill content."""

    @pytest.fixture
    def registered_mcp(self) -> FastMCP:
        """MCP server with all prompts registered."""
        mcp = FastMCP("test-prompts")
        register_all_prompts(mcp)
        return mcp

    async def test_discover_underrated_content(self, registered_mcp: FastMCP) -> None:
        """discover_underrated prompt contains progressive deepening steps."""
        fn = registered_mcp._prompt_manager._prompts["discover_underrated"].fn
        result = fn(query="python static analysis", domain="library")
        assert "discover_repos" in result
        assert "screen_candidates" in result
        assert "deep_assess" in result
        assert "rank_repos" in result
        assert "explain_repo" in result
        assert "python static analysis" in result

    async def test_quick_quality_check_content(self, registered_mcp: FastMCP) -> None:
        """quick_quality_check prompt contains screening steps."""
        fn = registered_mcp._prompt_manager._prompts["quick_quality_check"].fn
        result = fn(repo_url="https://github.com/owner/repo")
        assert "quick_screen" in result
        assert "owner/repo" in result

    async def test_compare_for_adoption_content(self, registered_mcp: FastMCP) -> None:
        """compare_for_adoption prompt contains comparison steps."""
        fn = registered_mcp._prompt_manager._prompts["compare_for_adoption"].fn
        result = fn(repo_urls="repo1, repo2")
        assert "compare_repos" in result
        assert "repo1, repo2" in result

    async def test_domain_deep_dive_content(self, registered_mcp: FastMCP) -> None:
        """domain_deep_dive prompt contains exploration steps."""
        fn = registered_mcp._prompt_manager._prompts["domain_deep_dive"].fn
        result = fn(domain="web_framework", query="fastapi")
        assert "web_framework" in result
        assert "discover_repos" in result

    async def test_security_audit_content(self, registered_mcp: FastMCP) -> None:
        """security_audit prompt contains security assessment steps."""
        fn = registered_mcp._prompt_manager._prompts["security_audit"].fn
        result = fn(repo_urls="owner/repo1, owner/repo2")
        assert "security" in result.lower()
