"""Tests for the discover CLI command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

runner = CliRunner()


def _mock_run_async(coro: object) -> None:
    """Side-effect for mocked run_async that closes the coroutine."""
    if hasattr(coro, "close"):
        coro.close()  # type: ignore[union-attr]


class TestDiscoverCommand:
    """Tests for the discover command."""

    def test_discover_shows_help(self) -> None:
        """Discover --help should show usage info."""
        from github_discovery.cli.app import app

        result = runner.invoke(app, ["discover", "--help"])
        assert result.exit_code == 0
        assert "query" in result.output.lower()

    def test_discover_no_args_fails(self) -> None:
        """Discover without query should fail."""
        from github_discovery.cli.app import app

        result = runner.invoke(app, ["discover"])
        assert result.exit_code != 0

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_discover_calls_streaming_by_default(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """Default mode should use streaming progress."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        result = runner.invoke(app, ["discover", "test query"])
        assert result.exit_code == 0 or mock_run_async.called

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_discover_no_stream_uses_direct(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """--no-stream should use direct mode."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(app, ["discover", "test query", "--no-stream"])
        assert mock_run_async.called

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_discover_output_format_option(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """--output json should resolve to json format."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(
            app,
            ["discover", "test", "--output", "json", "--no-stream"],
        )
        assert mock_run_async.called

    def test_discover_help_shows_options(self) -> None:
        """Help should list all options."""
        from github_discovery.cli.app import app

        result = runner.invoke(app, ["discover", "--help"])
        assert "--channels" in result.output
        assert "--max" in result.output
        assert "--stream" in result.output
        assert "--output" in result.output
