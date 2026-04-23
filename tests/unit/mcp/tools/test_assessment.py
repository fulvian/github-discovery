"""Tests for MCP assessment tools — deep_assess, quick_assess, get_assessment."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from github_discovery.config import Settings
from github_discovery.mcp.server import AppContext
from github_discovery.models.screening import (
    MetadataScreenResult,
    ScreeningResult,
    StaticScreenResult,
)
from github_discovery.models.session import SessionState


class TestDeepAssessTool:
    """Tests for the deep_assess MCP tool."""

    async def test_deep_assess_happy_path(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        mock_assessment_orchestrator: AsyncMock,
    ) -> None:
        """deep_assess returns assessment results for eligible candidates."""
        session = SessionState(name="assess")
        mock_session_manager.get_or_create = AsyncMock(return_value=session)
        mock_session_manager.update = AsyncMock()

        app_ctx = AppContext(settings=settings, session_manager=mock_session_manager)
        mock_ctx = AsyncMock()
        mock_ctx.request_context.lifespan_context = app_ctx

        # Mock hard gate screening to return passed results
        screening_results = {
            "owner/repo-1": ScreeningResult(
                full_name="owner/repo-1",
                gate1=MetadataScreenResult(
                    full_name="owner/repo-1",
                    gate1_total=0.7,
                    gate1_pass=True,
                ),
                gate2=StaticScreenResult(
                    full_name="owner/repo-1",
                    gate2_total=0.6,
                    gate2_pass=True,
                ),
            ),
        }

        with (
            patch(
                "github_discovery.mcp.tools.assessment._screen_for_hard_gate",
                return_value=screening_results,
            ),
            patch(
                "github_discovery.assessment.orchestrator.AssessmentOrchestrator",
                return_value=mock_assessment_orchestrator,
            ),
        ):
            from github_discovery.mcp.server import create_server

            server = create_server(settings)
            tool_fn = server._tool_manager._tools["deep_assess"].fn

            result = await tool_fn(
                repo_urls=["https://github.com/owner/repo-1"],
                session_id=session.session_id,
                ctx=mock_ctx,
            )

        assert result["success"] is True
        assert result["data"]["total_assessed"] == 1

    async def test_deep_assess_hard_gate_blocks(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
    ) -> None:
        """deep_assess returns error when no candidates pass hard gate."""
        session = SessionState(name="assess")
        mock_session_manager.get_or_create = AsyncMock(return_value=session)

        app_ctx = AppContext(settings=settings, session_manager=mock_session_manager)
        mock_ctx = AsyncMock()
        mock_ctx.request_context.lifespan_context = app_ctx

        # All candidates fail hard gate
        screening_results = {
            "owner/repo-1": ScreeningResult(
                full_name="owner/repo-1",
                gate1=MetadataScreenResult(
                    full_name="owner/repo-1",
                    gate1_total=0.3,
                    gate1_pass=False,
                ),
                gate2=StaticScreenResult(
                    full_name="owner/repo-1",
                    gate2_total=0.2,
                    gate2_pass=False,
                ),
            ),
        }

        with patch(
            "github_discovery.mcp.tools.assessment._screen_for_hard_gate",
            return_value=screening_results,
        ):
            from github_discovery.mcp.server import create_server

            server = create_server(settings)
            tool_fn = server._tool_manager._tools["deep_assess"].fn

            result = await tool_fn(
                repo_urls=["https://github.com/owner/repo-1"],
                ctx=mock_ctx,
            )

        assert result["success"] is False
        assert "hard gate" in result["error_message"].lower()

    async def test_deep_assess_invalid_urls(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
    ) -> None:
        """deep_assess returns error for empty valid URLs."""
        session = SessionState(name="assess")
        mock_session_manager.get_or_create = AsyncMock(return_value=session)

        app_ctx = AppContext(settings=settings, session_manager=mock_session_manager)
        mock_ctx = AsyncMock()
        mock_ctx.request_context.lifespan_context = app_ctx

        from github_discovery.mcp.server import create_server

        server = create_server(settings)
        tool_fn = server._tool_manager._tools["deep_assess"].fn

        # "x" is too short to parse as owner/repo
        result = await tool_fn(repo_urls=["x"], ctx=mock_ctx)

        assert result["success"] is False
        assert "No valid" in result["error_message"]


class TestQuickAssessTool:
    """Tests for the quick_assess MCP tool."""

    async def test_quick_assess_happy_path(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        mock_assessment_orchestrator: AsyncMock,
    ) -> None:
        """quick_assess returns assessment for single repo."""
        app_ctx = AppContext(settings=settings, session_manager=mock_session_manager)
        mock_ctx = AsyncMock()
        mock_ctx.request_context.lifespan_context = app_ctx

        with patch(
            "github_discovery.assessment.orchestrator.AssessmentOrchestrator",
            return_value=mock_assessment_orchestrator,
        ):
            from github_discovery.mcp.server import create_server

            server = create_server(settings)
            tool_fn = server._tool_manager._tools["quick_assess"].fn

            result = await tool_fn(
                repo_url="https://github.com/owner/repo-1",
                ctx=mock_ctx,
            )

        assert result["success"] is True
        assert result["data"]["repo"] == "owner/repo-1"
        assert "overall_quality" in result["data"]


class TestGetAssessmentTool:
    """Tests for the get_assessment MCP tool."""

    async def test_get_assessment_returns_cache_info(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        mock_assessment_orchestrator: AsyncMock,
    ) -> None:
        """get_assessment returns cache size info."""
        app_ctx = AppContext(settings=settings, session_manager=mock_session_manager)
        mock_ctx = AsyncMock()
        mock_ctx.request_context.lifespan_context = app_ctx

        with patch(
            "github_discovery.assessment.orchestrator.AssessmentOrchestrator",
            return_value=mock_assessment_orchestrator,
        ):
            from github_discovery.mcp.server import create_server

            server = create_server(settings)
            tool_fn = server._tool_manager._tools["get_assessment"].fn

            result = await tool_fn(
                repo_url="https://github.com/owner/repo-1",
                ctx=mock_ctx,
            )

        assert result["success"] is True
        assert result["data"]["cache_size"] == 5
