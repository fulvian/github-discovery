"""Tests for the export CLI command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

runner = CliRunner()


def _mock_run_async(coro: object) -> None:
    """Side-effect for mocked run_async that closes the coroutine."""
    if hasattr(coro, "close"):
        coro.close()  # type: ignore[union-attr]


class TestExportCommand:
    """Tests for the export command."""

    def test_export_shows_help(self) -> None:
        """export --help should show usage."""
        from github_discovery.cli.app import app

        result = runner.invoke(app, ["export", "--help"])
        assert result.exit_code == 0
        assert "--session-id" in result.output
        assert "--format" in result.output

    @patch("github_discovery.cli.utils.get_settings")
    def test_export_no_source_fails(self, mock_settings: MagicMock) -> None:
        """Without session-id or pool-id, should fail."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        result = runner.invoke(app, ["export"])
        assert result.exit_code != 0

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_export_session_json(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """Export with session-id and json format should work."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(app, ["export", "--session-id", "abc", "--format", "json"])
        assert mock_run_async.called

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_export_pool_csv(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """Export with pool-id and csv format should work."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(app, ["export", "--pool-id", "pool1", "--format", "csv"])
        assert mock_run_async.called

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_export_markdown(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """Export with markdown format should work."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(app, ["export", "--session-id", "abc", "--format", "markdown"])
        assert mock_run_async.called

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_export_output_file(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """--output with file path should work."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(
            app,
            ["export", "--session-id", "abc", "--output", "./test_export.json"],
        )
        assert mock_run_async.called

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_export_include_details(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """--include-details should be accepted."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(
            app,
            ["export", "--session-id", "abc", "--include-details"],
        )
        assert mock_run_async.called

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_export_domain_filter(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """--domain filter should be accepted."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(
            app,
            ["export", "--session-id", "abc", "--domain", "library"],
        )
        assert mock_run_async.called
