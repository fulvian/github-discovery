"""Tests for MCP session tools — create_session, get_session, list_sessions, export_session."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from github_discovery.config import Settings
from github_discovery.mcp.server import AppContext
from github_discovery.models.session import SessionState, SessionStatus


@pytest.fixture
def app_ctx(settings: Settings, mock_session_manager: AsyncMock, make_app_ctx) -> AppContext:
    """Create AppContext with mock session manager."""
    return make_app_ctx(settings, mock_session_manager)


@pytest.fixture
def mock_ctx(app_ctx: AppContext) -> AsyncMock:
    """Create a mock MCP Context with app_ctx."""
    ctx = AsyncMock()
    ctx.request_context.lifespan_context = app_ctx
    return ctx


class TestCreateSessionTool:
    """Tests for the create_session MCP tool."""

    async def test_create_session_happy_path(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        mock_ctx: AsyncMock,
    ) -> None:
        """create_session returns new session info."""
        session = SessionState(name="test-session")
        mock_session_manager.create = AsyncMock(return_value=session)

        from github_discovery.mcp.server import create_server

        server = create_server(settings)
        tool_fn = server._tool_manager._tools["create_session"].fn

        result = await tool_fn(name="test-session", ctx=mock_ctx)

        assert result["success"] is True
        assert result["data"]["name"] == "test-session"
        assert result["session_id"] == session.session_id

    async def test_create_session_with_config_overrides(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        mock_ctx: AsyncMock,
    ) -> None:
        """create_session passes config overrides."""
        session = SessionState(name="custom")
        mock_session_manager.create = AsyncMock(return_value=session)

        from github_discovery.mcp.server import create_server

        server = create_server(settings)
        tool_fn = server._tool_manager._tools["create_session"].fn

        result = await tool_fn(
            name="custom",
            min_gate1_score=0.6,
            max_tokens_per_repo=30000,
            ctx=mock_ctx,
        )

        assert result["success"] is True
        mock_session_manager.create.assert_called_once()
        call_kwargs = mock_session_manager.create.call_args
        config_arg = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
        assert config_arg.min_gate1_score == 0.6
        assert config_arg.max_tokens_per_repo == 30000


class TestGetSessionTool:
    """Tests for the get_session MCP tool."""

    async def test_get_session_existing(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        mock_ctx: AsyncMock,
    ) -> None:
        """get_session returns session details."""
        session = SessionState(
            name="found-session",
            discovered_repo_count=42,
            screened_repo_count=20,
        )
        mock_session_manager.get = AsyncMock(return_value=session)

        from github_discovery.mcp.server import create_server

        server = create_server(settings)
        tool_fn = server._tool_manager._tools["get_session"].fn

        result = await tool_fn(session_id=session.session_id, ctx=mock_ctx)

        assert result["success"] is True
        assert "session_id" in result["data"]

    async def test_get_session_not_found(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        mock_ctx: AsyncMock,
    ) -> None:
        """get_session returns error for missing session."""
        mock_session_manager.get = AsyncMock(return_value=None)

        from github_discovery.mcp.server import create_server

        server = create_server(settings)
        tool_fn = server._tool_manager._tools["get_session"].fn

        result = await tool_fn(session_id="nonexistent", ctx=mock_ctx)

        assert result["success"] is False
        assert "not found" in result["error_message"]


class TestListSessionsTool:
    """Tests for the list_sessions MCP tool."""

    async def test_list_sessions_happy_path(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        mock_ctx: AsyncMock,
    ) -> None:
        """list_sessions returns list of sessions."""
        sessions = [
            SessionState(name="s1"),
            SessionState(name="s2"),
        ]
        mock_session_manager.list_sessions = AsyncMock(return_value=sessions)

        from github_discovery.mcp.server import create_server

        server = create_server(settings)
        tool_fn = server._tool_manager._tools["list_sessions"].fn

        result = await tool_fn(ctx=mock_ctx)

        assert result["success"] is True
        assert result["data"]["total"] == 2
        assert len(result["data"]["sessions"]) == 2

    async def test_list_sessions_with_status_filter(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        mock_ctx: AsyncMock,
    ) -> None:
        """list_sessions filters by status."""
        active_session = SessionState(name="active", status=SessionStatus.DISCOVERING)
        mock_session_manager.list_sessions = AsyncMock(return_value=[active_session])

        from github_discovery.mcp.server import create_server

        server = create_server(settings)
        tool_fn = server._tool_manager._tools["list_sessions"].fn

        result = await tool_fn(status="discovering", ctx=mock_ctx)

        assert result["success"] is True
        assert result["data"]["total"] == 1

    async def test_list_sessions_invalid_status(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        mock_ctx: AsyncMock,
    ) -> None:
        """list_sessions returns error for invalid status."""
        from github_discovery.mcp.server import create_server

        server = create_server(settings)
        tool_fn = server._tool_manager._tools["list_sessions"].fn

        result = await tool_fn(status="invalid_status", ctx=mock_ctx)

        assert result["success"] is False
        assert "Invalid status" in result["error_message"]


class TestExportSessionTool:
    """Tests for the export_session MCP tool."""

    async def test_export_session_json_format(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        mock_ctx: AsyncMock,
    ) -> None:
        """export_session returns JSON export."""
        session = SessionState(name="export-me", discovered_repo_count=10)
        mock_session_manager.get = AsyncMock(return_value=session)

        from github_discovery.mcp.server import create_server

        server = create_server(settings)
        tool_fn = server._tool_manager._tools["export_session"].fn

        result = await tool_fn(
            session_id=session.session_id,
            export_format="json",
            ctx=mock_ctx,
        )

        assert result["success"] is True
        assert "session_id" in result["data"]

    async def test_export_session_not_found(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        mock_ctx: AsyncMock,
    ) -> None:
        """export_session returns error for missing session."""
        mock_session_manager.get = AsyncMock(return_value=None)

        from github_discovery.mcp.server import create_server

        server = create_server(settings)
        tool_fn = server._tool_manager._tools["export_session"].fn

        result = await tool_fn(session_id="nonexistent", ctx=mock_ctx)

        assert result["success"] is False
        assert "not found" in result["error_message"]

    async def test_export_session_summary_format(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        mock_ctx: AsyncMock,
    ) -> None:
        """export_session returns summary format."""
        session = SessionState(name="summary-me")
        mock_session_manager.get = AsyncMock(return_value=session)

        from github_discovery.mcp.server import create_server

        server = create_server(settings)
        tool_fn = server._tool_manager._tools["export_session"].fn

        result = await tool_fn(
            session_id=session.session_id,
            export_format="summary",
            ctx=mock_ctx,
        )

        assert result["success"] is True
