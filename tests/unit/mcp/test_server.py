"""Tests for MCP server creation, AppContext, and lifespan management."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from mcp.server.fastmcp import FastMCP

from github_discovery.config import Settings
from github_discovery.mcp.server import AppContext, create_server, get_app_context


class TestCreateServer:
    """Tests for create_server factory function."""

    def test_create_server_returns_fastmcp_instance(self, settings: Settings) -> None:
        """create_server returns a FastMCP instance."""
        server = create_server(settings)
        assert isinstance(server, FastMCP)

    def test_server_has_correct_name(self, settings: Settings) -> None:
        """Server is named 'github-discovery'."""
        server = create_server(settings)
        assert server.name == "github-discovery"

    def test_create_server_registers_all_tools(self, settings: Settings) -> None:
        """Server registers all 16 MCP tools."""
        server = create_server(settings)
        # FastMCP stores tools internally; we check via the tool manager
        tool_names = list(server._tool_manager._tools.keys())
        expected_tools = [
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
        ]
        for tool_name in expected_tools:
            assert tool_name in tool_names, f"Tool '{tool_name}' not registered"

    def test_create_server_with_none_settings(self) -> None:
        """create_server with None settings uses defaults."""
        server = create_server(None)
        assert isinstance(server, FastMCP)
        assert server.name == "github-discovery"

    def test_create_server_with_explicit_settings(self, settings: Settings) -> None:
        """create_server uses provided settings."""
        server = create_server(settings)
        assert isinstance(server, FastMCP)


class TestAppContext:
    """Tests for AppContext dataclass."""

    def test_app_context_dataclass_fields(self) -> None:
        """AppContext has settings and session_manager fields."""
        mock_sm = AsyncMock()
        settings = Settings()
        ctx = AppContext(settings=settings, session_manager=mock_sm)
        assert ctx.settings is settings
        assert ctx.session_manager is mock_sm

    def test_app_context_stores_settings_correctly(self) -> None:
        """AppContext preserves the exact Settings instance."""
        settings = Settings()
        mock_sm = AsyncMock()
        ctx = AppContext(settings=settings, session_manager=mock_sm)
        assert ctx.settings.app_name == "github-discovery"


class TestGetAppContext:
    """Tests for get_app_context helper."""

    def test_get_app_context_extracts_from_request(self) -> None:
        """get_app_context returns lifespan_context from request."""
        mock_sm = AsyncMock()
        settings = Settings()
        expected = AppContext(settings=settings, session_manager=mock_sm)

        mock_request_context = MagicMock()
        mock_request_context.lifespan_context = expected

        mock_ctx = MagicMock()
        mock_ctx.request_context = mock_request_context

        result = get_app_context(mock_ctx)
        assert result is expected
        assert result.settings is settings
