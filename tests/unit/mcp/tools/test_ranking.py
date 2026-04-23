"""Tests for MCP ranking tools — rank_repos, explain_repo, compare_repos."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from github_discovery.config import Settings
from github_discovery.models.enums import DomainType
from github_discovery.models.scoring import (
    ExplainabilityReport,
    ScoreResult,
)


class TestRankReposTool:
    """Tests for the rank_repos MCP tool."""

    async def test_rank_repos_happy_path(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        mock_ranker: MagicMock,
        make_app_ctx,
    ) -> None:
        """rank_repos returns ranked results."""
        mock_score_results = [
            ScoreResult(
                full_name="owner/repo-1",
                commit_sha="abc123",
                domain=DomainType.OTHER,
                quality_score=0.82,
                confidence=0.78,
                stars=100,
            ),
        ]

        # Feature store mock that returns the score results
        mock_feature_store = AsyncMock()
        mock_feature_store.get_by_domain = AsyncMock(return_value=mock_score_results)

        app_ctx = make_app_ctx(
            settings,
            mock_session_manager,
            mock_ranker=mock_ranker,
            mock_feature_store=mock_feature_store,
        )
        mock_ctx = AsyncMock()
        mock_ctx.request_context.lifespan_context = app_ctx

        from github_discovery.mcp.server import create_server

        server = create_server(settings)
        tool_fn = server._tool_manager._tools["rank_repos"].fn

        result = await tool_fn(
            domain="other",
            session_id="test-session",
            ctx=mock_ctx,
        )

        assert result["success"] is True
        assert result["data"]["domain"] == "other"
        assert result["data"]["total_candidates"] == 10

    async def test_rank_repos_no_scores(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        make_app_ctx,
    ) -> None:
        """rank_repos returns error when no scores found."""
        mock_feature_store = AsyncMock()
        mock_feature_store.get_by_domain = AsyncMock(return_value=[])

        app_ctx = make_app_ctx(
            settings,
            mock_session_manager,
            mock_feature_store=mock_feature_store,
        )
        mock_ctx = AsyncMock()
        mock_ctx.request_context.lifespan_context = app_ctx

        from github_discovery.mcp.server import create_server

        server = create_server(settings)
        tool_fn = server._tool_manager._tools["rank_repos"].fn

        result = await tool_fn(domain="other", ctx=mock_ctx)

        assert result["success"] is False
        assert "No scored results" in result["error_message"]


class TestExplainRepoTool:
    """Tests for the explain_repo MCP tool."""

    async def test_explain_repo_happy_path(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        make_app_ctx,
    ) -> None:
        """explain_repo returns explainability report."""
        mock_score = ScoreResult(
            full_name="owner/repo-1",
            commit_sha="abc123",
            domain=DomainType.OTHER,
            quality_score=0.82,
            confidence=0.78,
            stars=100,
        )
        mock_report = ExplainabilityReport(
            full_name="owner/repo-1",
            domain=DomainType.OTHER,
            overall_quality=0.82,
            value_score=0.45,
            strengths=["Well tested", "Good docs"],
            weaknesses=["Missing CI"],
            hidden_gem_indicator=True,
            hidden_gem_reason="High quality with low stars",
            star_context="100 stars",
            confidence=0.78,
        )

        with (
            patch(
                "github_discovery.mcp.tools.ranking._load_score_for_repo",
                return_value=mock_score,
            ),
            patch(
                "github_discovery.mcp.tools.ranking.ExplainabilityGenerator",
            ) as mock_gen_cls,
        ):
            mock_gen = MagicMock()
            mock_gen.explain = MagicMock(return_value=mock_report)
            mock_gen_cls.return_value = mock_gen

            app_ctx = make_app_ctx(settings, mock_session_manager)
            mock_ctx = AsyncMock()
            mock_ctx.request_context.lifespan_context = app_ctx

            from github_discovery.mcp.server import create_server

            server = create_server(settings)
            tool_fn = server._tool_manager._tools["explain_repo"].fn

            result = await tool_fn(
                repo_url="https://github.com/owner/repo-1",
                detail_level="summary",
                ctx=mock_ctx,
            )

        assert result["success"] is True
        assert result["data"]["repo"] == "owner/repo-1"
        assert result["data"]["hidden_gem"] is True

    async def test_explain_repo_no_score(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        make_app_ctx,
    ) -> None:
        """explain_repo returns error when no score found."""
        app_ctx = make_app_ctx(settings, mock_session_manager)
        mock_ctx = AsyncMock()
        mock_ctx.request_context.lifespan_context = app_ctx

        with patch(
            "github_discovery.mcp.tools.ranking._load_score_for_repo",
            return_value=None,
        ):
            from github_discovery.mcp.server import create_server

            server = create_server(settings)
            tool_fn = server._tool_manager._tools["explain_repo"].fn

            result = await tool_fn(
                repo_url="https://github.com/owner/repo-1",
                ctx=mock_ctx,
            )

        assert result["success"] is False
        assert "No scoring result" in result["error_message"]


class TestCompareReposTool:
    """Tests for the compare_repos MCP tool."""

    async def test_compare_repos_happy_path(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        make_app_ctx,
    ) -> None:
        """compare_repos returns side-by-side comparison."""
        mock_score = ScoreResult(
            full_name="owner/repo-1",
            commit_sha="abc",
            domain=DomainType.OTHER,
            quality_score=0.8,
            confidence=0.7,
            stars=100,
        )
        mock_report = ExplainabilityReport(
            full_name="owner/repo-1",
            domain=DomainType.OTHER,
            overall_quality=0.8,
            value_score=0.4,
            strengths=["Good"],
            weaknesses=["None"],
            confidence=0.7,
        )

        with (
            patch(
                "github_discovery.mcp.tools.ranking._load_score_for_repo",
                return_value=mock_score,
            ),
            patch(
                "github_discovery.mcp.tools.ranking.ExplainabilityGenerator",
            ) as mock_gen_cls,
        ):
            mock_gen = MagicMock()
            mock_gen.explain = MagicMock(return_value=mock_report)
            mock_gen_cls.return_value = mock_gen

            app_ctx = make_app_ctx(settings, mock_session_manager)
            mock_ctx = AsyncMock()
            mock_ctx.request_context.lifespan_context = app_ctx

            from github_discovery.mcp.server import create_server

            server = create_server(settings)
            tool_fn = server._tool_manager._tools["compare_repos"].fn

            result = await tool_fn(
                repo_urls=[
                    "https://github.com/owner/repo-1",
                    "https://github.com/owner/repo-2",
                ],
                ctx=mock_ctx,
            )

        assert result["success"] is True
        assert "comparison" in result["data"]

    async def test_compare_repos_too_few(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        make_app_ctx,
    ) -> None:
        """compare_repos returns error with fewer than 2 repos."""
        app_ctx = make_app_ctx(settings, mock_session_manager)
        mock_ctx = AsyncMock()
        mock_ctx.request_context.lifespan_context = app_ctx

        from github_discovery.mcp.server import create_server

        server = create_server(settings)
        tool_fn = server._tool_manager._tools["compare_repos"].fn

        result = await tool_fn(
            repo_urls=["https://github.com/owner/repo-1"],
            ctx=mock_ctx,
        )

        assert result["success"] is False
        assert "at least 2" in result["error_message"].lower()

    async def test_compare_repos_too_many(
        self,
        settings: Settings,
        mock_session_manager: AsyncMock,
        make_app_ctx,
    ) -> None:
        """compare_repos returns error with more than 5 repos."""
        app_ctx = make_app_ctx(settings, mock_session_manager)
        mock_ctx = AsyncMock()
        mock_ctx.request_context.lifespan_context = app_ctx

        from github_discovery.mcp.server import create_server

        server = create_server(settings)
        tool_fn = server._tool_manager._tools["compare_repos"].fn

        result = await tool_fn(
            repo_urls=[f"https://github.com/owner/repo-{i}" for i in range(6)],
            ctx=mock_ctx,
        )

        assert result["success"] is False
        assert "Maximum 5" in result["error_message"]
