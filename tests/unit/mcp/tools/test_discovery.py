"""Tests for MCP discovery tools — discover_repos, get_candidate_pool, expand_seeds."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from github_discovery.config import Settings


class TestDiscoverReposTool:
    """Tests for the discover_repos MCP tool."""

    async def test_discover_repos_happy_path(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        mock_discovery_orchestrator: tuple,
        make_app_ctx,
    ) -> None:
        """discover_repos returns formatted result with pool_id."""
        from github_discovery.models.session import SessionState

        mock_orch, _pool_id = mock_discovery_orchestrator
        session = SessionState(name="discovery")
        mock_session_manager.get_or_create = AsyncMock(return_value=session)
        mock_session_manager.update = AsyncMock()

        app_ctx = make_app_ctx(settings, mock_session_manager, mock_discovery_orch=mock_orch)

        mock_ctx = AsyncMock()
        mock_ctx.request_context.lifespan_context = app_ctx

        with (
            patch(
                "github_discovery.discovery.orchestrator.DiscoveryOrchestrator",
                return_value=mock_orch,
            ),
            patch("github_discovery.discovery.pool.PoolManager", return_value=AsyncMock()),
        ):
            from github_discovery.mcp.server import create_server

            server = create_server(settings)
            tool_fn = server._tool_manager._tools["discover_repos"].fn

            result = await tool_fn(
                query="static analysis python",
                max_candidates=50,
                ctx=mock_ctx,
            )

        assert result["success"] is True
        assert "pool_id" in result["data"]
        assert result["data"]["total_candidates"] == 42
        assert result["session_id"] == session.session_id

    async def test_discover_repos_session_propagation(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        mock_discovery_orchestrator: tuple,
        make_app_ctx,
    ) -> None:
        """discover_repos uses provided session_id."""
        from github_discovery.models.session import SessionState

        mock_orch, _ = mock_discovery_orchestrator
        existing_session = SessionState(name="existing")
        mock_session_manager.get_or_create = AsyncMock(return_value=existing_session)
        mock_session_manager.update = AsyncMock()

        app_ctx = make_app_ctx(settings, mock_session_manager, mock_discovery_orch=mock_orch)
        mock_ctx = AsyncMock()
        mock_ctx.request_context.lifespan_context = app_ctx

        with (
            patch(
                "github_discovery.discovery.orchestrator.DiscoveryOrchestrator",
                return_value=mock_orch,
            ),
            patch("github_discovery.discovery.pool.PoolManager", return_value=AsyncMock()),
        ):
            from github_discovery.mcp.server import create_server

            server = create_server(settings)
            tool_fn = server._tool_manager._tools["discover_repos"].fn

            result = await tool_fn(
                query="test",
                session_id="existing-session-id",
                ctx=mock_ctx,
            )

        mock_session_manager.get_or_create.assert_called_once_with(
            "existing-session-id",
            name="discovery",
        )
        assert result["session_id"] == existing_session.session_id


class TestGetCandidatePoolTool:
    """Tests for the get_candidate_pool MCP tool."""

    async def test_get_candidate_pool_happy_path(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        mock_pool_manager: tuple,
        make_app_ctx,
    ) -> None:
        """get_candidate_pool returns candidates from pool."""
        mock_pm, pool_id = mock_pool_manager

        app_ctx = make_app_ctx(settings, mock_session_manager, mock_pool_manager=mock_pm)
        mock_ctx = AsyncMock()
        mock_ctx.request_context.lifespan_context = app_ctx

        from github_discovery.mcp.server import create_server

        server = create_server(settings)
        tool_fn = server._tool_manager._tools["get_candidate_pool"].fn

        result = await tool_fn(pool_id=pool_id, ctx=mock_ctx)

        assert result["success"] is True
        assert result["data"]["total_count"] == 2
        assert result["data"]["pool_id"] == pool_id

    async def test_get_candidate_pool_not_found(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        make_app_ctx,
    ) -> None:
        """get_candidate_pool returns error for missing pool."""
        mock_pm = AsyncMock()
        mock_pm.get_pool = AsyncMock(return_value=None)
        mock_pm.close = AsyncMock()

        app_ctx = make_app_ctx(settings, mock_session_manager, mock_pool_manager=mock_pm)
        mock_ctx = AsyncMock()
        mock_ctx.request_context.lifespan_context = app_ctx

        from github_discovery.mcp.server import create_server

        server = create_server(settings)
        tool_fn = server._tool_manager._tools["get_candidate_pool"].fn

        result = await tool_fn(pool_id="nonexistent", ctx=mock_ctx)

        assert result["success"] is False
        assert "not found" in result["error_message"]


class TestExpandSeedsTool:
    """Tests for the expand_seeds MCP tool."""

    async def test_expand_seeds_happy_path(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        mock_discovery_orchestrator: tuple,
        make_app_ctx,
    ) -> None:
        """expand_seeds returns formatted result."""
        from github_discovery.models.session import SessionState

        mock_orch, _ = mock_discovery_orchestrator
        session = SessionState(name="seed-expansion")
        mock_session_manager.get_or_create = AsyncMock(return_value=session)
        mock_session_manager.update = AsyncMock()

        app_ctx = make_app_ctx(settings, mock_session_manager, mock_discovery_orch=mock_orch)
        mock_ctx = AsyncMock()
        mock_ctx.request_context.lifespan_context = app_ctx

        with (
            patch(
                "github_discovery.discovery.orchestrator.DiscoveryOrchestrator",
                return_value=mock_orch,
            ),
            patch("github_discovery.discovery.pool.PoolManager", return_value=AsyncMock()),
        ):
            from github_discovery.mcp.server import create_server

            server = create_server(settings)
            tool_fn = server._tool_manager._tools["expand_seeds"].fn

            result = await tool_fn(
                seed_urls=["https://github.com/owner/seed-repo"],
                ctx=mock_ctx,
            )

        assert result["success"] is True
        assert "pool_id" in result["data"]
        assert result["data"]["seed_count"] == 1
