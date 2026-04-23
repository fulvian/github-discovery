"""Tests for MCP screening tools — screen_candidates, get_shortlist, quick_screen."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

from github_discovery.config import Settings
from github_discovery.mcp.server import AppContext
from github_discovery.models.session import SessionState


class TestScreenCandidatesTool:
    """Tests for the screen_candidates MCP tool."""

    async def test_screen_candidates_happy_path(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        mock_pool_manager: tuple,
        mock_screening_orchestrator: AsyncMock,
    ) -> None:
        """screen_candidates returns screening summary."""
        mock_pm, pool_id = mock_pool_manager
        session = SessionState(name="screening")
        mock_session_manager.get_or_create = AsyncMock(return_value=session)
        mock_session_manager.update = AsyncMock()

        app_ctx = AppContext(settings=settings, session_manager=mock_session_manager)
        mock_ctx = AsyncMock()
        mock_ctx.request_context.lifespan_context = app_ctx

        with (
            patch("github_discovery.mcp.tools.screening.PoolManager", return_value=mock_pm),
            patch(
                "github_discovery.mcp.tools.screening._run_screening",
                return_value=await mock_screening_orchestrator.screen(AsyncMock()),
            ),
        ):
            from github_discovery.mcp.server import create_server

            server = create_server(settings)
            tool_fn = server._tool_manager._tools["screen_candidates"].fn

            result = await tool_fn(
                pool_id=pool_id,
                gate_level="both",
                ctx=mock_ctx,
            )

        assert result["success"] is True
        assert result["data"]["total_screened"] == 2
        assert result["data"]["gate1_passed"] == 1
        assert result["data"]["gate2_passed"] == 1
        assert result["session_id"] == session.session_id

    async def test_screen_candidates_pool_not_found(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
    ) -> None:
        """screen_candidates returns error for missing pool."""
        mock_pm = AsyncMock()
        mock_pm.get_pool = AsyncMock(return_value=None)
        mock_pm.close = AsyncMock()

        session = SessionState(name="screening")
        mock_session_manager.get_or_create = AsyncMock(return_value=session)

        app_ctx = AppContext(settings=settings, session_manager=mock_session_manager)
        mock_ctx = AsyncMock()
        mock_ctx.request_context.lifespan_context = app_ctx

        with patch("github_discovery.mcp.tools.screening.PoolManager", return_value=mock_pm):
            from github_discovery.mcp.server import create_server

            server = create_server(settings)
            tool_fn = server._tool_manager._tools["screen_candidates"].fn

            result = await tool_fn(pool_id="nonexistent", ctx=mock_ctx)

        assert result["success"] is False
        assert "not found" in result["error_message"]

    async def test_screen_candidates_empty_pool(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
    ) -> None:
        """screen_candidates returns error for empty pool."""
        from github_discovery.models.candidate import CandidatePool

        empty_pool = CandidatePool(pool_id=str(uuid4()), candidates=[])
        mock_pm = AsyncMock()
        mock_pm.get_pool = AsyncMock(return_value=empty_pool)
        mock_pm.close = AsyncMock()

        session = SessionState(name="screening")
        mock_session_manager.get_or_create = AsyncMock(return_value=session)

        app_ctx = AppContext(settings=settings, session_manager=mock_session_manager)
        mock_ctx = AsyncMock()
        mock_ctx.request_context.lifespan_context = app_ctx

        with patch("github_discovery.mcp.tools.screening.PoolManager", return_value=mock_pm):
            from github_discovery.mcp.server import create_server

            server = create_server(settings)
            tool_fn = server._tool_manager._tools["screen_candidates"].fn

            result = await tool_fn(pool_id=empty_pool.pool_id, ctx=mock_ctx)

        assert result["success"] is False
        assert "empty" in result["error_message"]


class TestGetShortlistTool:
    """Tests for the get_shortlist MCP tool."""

    async def test_get_shortlist_happy_path(
        self,
        settings: Settings,
        mock_pool_manager: tuple,
    ) -> None:
        """get_shortlist returns filtered candidates."""
        mock_pm, pool_id = mock_pool_manager

        with patch("github_discovery.mcp.tools.screening.PoolManager", return_value=mock_pm):
            from github_discovery.mcp.server import create_server

            server = create_server(settings)
            tool_fn = server._tool_manager._tools["get_shortlist"].fn

            result = await tool_fn(pool_id=pool_id, min_score=0.5, ctx=AsyncMock())

        assert result["success"] is True
        assert result["data"]["total"] == 2

    async def test_get_shortlist_pool_not_found(
        self,
        settings: Settings,
    ) -> None:
        """get_shortlist returns error for missing pool."""
        mock_pm = AsyncMock()
        mock_pm.get_pool = AsyncMock(return_value=None)
        mock_pm.close = AsyncMock()

        with patch("github_discovery.mcp.tools.screening.PoolManager", return_value=mock_pm):
            from github_discovery.mcp.server import create_server

            server = create_server(settings)
            tool_fn = server._tool_manager._tools["get_shortlist"].fn

            result = await tool_fn(pool_id="nonexistent", ctx=AsyncMock())

        assert result["success"] is False


class TestQuickScreenTool:
    """Tests for the quick_screen MCP tool."""

    async def test_quick_screen_happy_path(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        mock_screening_orchestrator: AsyncMock,
    ) -> None:
        """quick_screen returns result for single repo."""
        app_ctx = AppContext(settings=settings, session_manager=mock_session_manager)
        mock_ctx = AsyncMock()
        mock_ctx.request_context.lifespan_context = app_ctx

        with patch(
            "github_discovery.mcp.tools.screening._quick_screen_single",
            return_value=await mock_screening_orchestrator.quick_screen(AsyncMock()),
        ):
            from github_discovery.mcp.server import create_server

            server = create_server(settings)
            tool_fn = server._tool_manager._tools["quick_screen"].fn

            result = await tool_fn(
                repo_url="https://github.com/owner/repo-1",
                gate_levels="1",
                ctx=mock_ctx,
            )

        assert result["success"] is True
        assert result["data"]["repo"] == "owner/repo-1"

    async def test_quick_screen_invalid_url(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
    ) -> None:
        """quick_screen returns error for invalid URL."""
        app_ctx = AppContext(settings=settings, session_manager=mock_session_manager)
        mock_ctx = AsyncMock()
        mock_ctx.request_context.lifespan_context = app_ctx

        from github_discovery.mcp.server import create_server

        server = create_server(settings)
        tool_fn = server._tool_manager._tools["quick_screen"].fn

        result = await tool_fn(repo_url="invalid", gate_levels="1", ctx=mock_ctx)

        # Even with a short URL, _parse_repo_url will try to extract parts
        # "invalid" has 1 part which is < 2, so full_name will be ""
        assert result["success"] is False
        assert "Invalid" in result["error_message"]
