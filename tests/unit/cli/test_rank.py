"""Tests for the rank CLI command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

runner = CliRunner()


def _mock_run_async(coro: object) -> None:
    """Side-effect for mocked run_async that closes the coroutine."""
    if hasattr(coro, "close"):
        coro.close()  # type: ignore[union-attr]


class TestRankCommand:
    """Tests for the rank command."""

    def test_rank_shows_help(self) -> None:
        """Rank --help should show usage info."""
        from github_discovery.cli.app import app

        result = runner.invoke(app, ["rank", "--help"])
        assert result.exit_code == 0
        assert "--domain" in result.output
        assert "--top" in result.output

    @patch("github_discovery.cli.utils.get_settings")
    def test_rank_no_domain_fails(self, mock_settings: MagicMock) -> None:
        """Rank without --domain should fail."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        result = runner.invoke(app, ["rank"])
        assert result.exit_code != 0

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_rank_with_domain_calls_async(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """Rank with valid domain should call run_async."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(app, ["rank", "--domain", "library"])
        assert mock_run_async.called

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_rank_top_option(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """--top option should be accepted."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(app, ["rank", "--domain", "library", "--top", "10"])
        assert mock_run_async.called

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_rank_output_format(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """--output json should be accepted."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(
            app,
            ["rank", "--domain", "library", "--output", "json"],
        )
        assert mock_run_async.called

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_rank_min_value_score(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """--min-value-score should be accepted."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(
            app,
            ["rank", "--domain", "library", "--min-value-score", "0.5"],
        )
        assert mock_run_async.called
