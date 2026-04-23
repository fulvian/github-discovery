"""Tests for MCP progress notification helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock

from github_discovery.mcp.progress import (
    report_assessment_progress,
    report_discovery_progress,
    report_screening_progress,
)


class TestReportDiscoveryProgress:
    """Tests for report_discovery_progress."""

    async def test_report_discovery_progress_without_ctx(self) -> None:
        """No-op when ctx is None."""
        # Should not raise
        await report_discovery_progress(None, 10, 100)

    async def test_report_discovery_progress_with_ctx(self) -> None:
        """Calls ctx.report_progress with current, total, and message."""
        mock_ctx = AsyncMock()
        await report_discovery_progress(mock_ctx, 42, 100)
        mock_ctx.report_progress.assert_called_once_with(42, 100, "Discovering repositories")

    async def test_report_discovery_progress_with_channel(self) -> None:
        """Channel parameter appears in progress message."""
        mock_ctx = AsyncMock()
        await report_discovery_progress(mock_ctx, 10, 50, channel="search")
        mock_ctx.report_progress.assert_called_once_with(10, 50, "Discovering via search")


class TestReportScreeningProgress:
    """Tests for report_screening_progress."""

    async def test_report_screening_progress_without_ctx(self) -> None:
        """No-op when ctx is None."""
        await report_screening_progress(None, 5, 20)

    async def test_report_screening_progress_with_ctx(self) -> None:
        """Calls ctx.report_progress with gate_level message."""
        mock_ctx = AsyncMock()
        await report_screening_progress(mock_ctx, 15, 30, gate_level="both")
        mock_ctx.report_progress.assert_called_once_with(15, 30, "Screening gate both")


class TestReportAssessmentProgress:
    """Tests for report_assessment_progress."""

    async def test_report_assessment_progress_without_ctx(self) -> None:
        """No-op when ctx is None."""
        await report_assessment_progress(None, 3, 10)

    async def test_report_assessment_progress_with_ctx(self) -> None:
        """Calls ctx.report_progress with token and budget info."""
        mock_ctx = AsyncMock()
        await report_assessment_progress(mock_ctx, 5, 10, tokens_used=5000, budget_remaining=45000)
        mock_ctx.report_progress.assert_called_once()
        call_args = mock_ctx.report_progress.call_args
        assert call_args[0][0] == 5  # current
        assert call_args[0][1] == 10  # total
        assert "tokens: 5000" in call_args[0][2]  # message
        assert "budget remaining: 45000" in call_args[0][2]  # message

    async def test_report_assessment_progress_no_extras(self) -> None:
        """Progress message without token/budget details."""
        mock_ctx = AsyncMock()
        await report_assessment_progress(mock_ctx, 1, 5)
        call_args = mock_ctx.report_progress.call_args
        assert call_args[0][0] == 1
        assert call_args[0][1] == 5
        assert "Assessing 1/5" in call_args[0][2]
