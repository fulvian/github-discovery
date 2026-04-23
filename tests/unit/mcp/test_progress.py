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
        """Calls ctx.report_progress when ctx is provided."""
        mock_ctx = AsyncMock()
        await report_discovery_progress(mock_ctx, 42, 100)
        mock_ctx.report_progress.assert_called_once_with(42, 100)

    async def test_report_discovery_progress_with_channel(self) -> None:
        """Channel parameter does not affect the call."""
        mock_ctx = AsyncMock()
        await report_discovery_progress(mock_ctx, 10, 50, channel="search")
        mock_ctx.report_progress.assert_called_once_with(10, 50)


class TestReportScreeningProgress:
    """Tests for report_screening_progress."""

    async def test_report_screening_progress_without_ctx(self) -> None:
        """No-op when ctx is None."""
        await report_screening_progress(None, 5, 20)

    async def test_report_screening_progress_with_ctx(self) -> None:
        """Calls ctx.report_progress when ctx is provided."""
        mock_ctx = AsyncMock()
        await report_screening_progress(mock_ctx, 15, 30, gate_level="both")
        mock_ctx.report_progress.assert_called_once_with(15, 30)


class TestReportAssessmentProgress:
    """Tests for report_assessment_progress."""

    async def test_report_assessment_progress_without_ctx(self) -> None:
        """No-op when ctx is None."""
        await report_assessment_progress(None, 3, 10)

    async def test_report_assessment_progress_with_ctx(self) -> None:
        """Calls ctx.report_progress when ctx is provided."""
        mock_ctx = AsyncMock()
        await report_assessment_progress(mock_ctx, 5, 10, tokens_used=5000, budget_remaining=45000)
        mock_ctx.report_progress.assert_called_once_with(5, 10)
