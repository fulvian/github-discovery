"""Tests for CLI progress display helpers."""

from __future__ import annotations

from rich.progress import Progress

from github_discovery.cli.progress_display import _create_progress, get_progress_console


class TestCreateProgress:
    """Tests for _create_progress factory."""

    def test_returns_progress_instance(self) -> None:
        progress = _create_progress()
        assert isinstance(progress, Progress)

    def test_progress_has_columns(self) -> None:
        """Progress should have spinner, text, bar, and time columns."""
        progress = _create_progress()
        # Rich Progress.columns contains the configured columns
        assert len(progress.columns) >= 4


class TestGetProgressConsole:
    """Tests for get_progress_console."""

    def test_returns_console(self) -> None:
        console = get_progress_console()
        assert console is not None

    def test_console_is_stderr(self) -> None:
        console = get_progress_console()
        assert console.stderr is True
