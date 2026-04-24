"""Tests for the screen CLI command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

runner = CliRunner()


def _mock_run_async(coro: object) -> None:
    """Side-effect for mocked run_async that closes the coroutine."""
    if hasattr(coro, "close"):
        coro.close()  # type: ignore[union-attr]


class TestScreenCommand:
    """Tests for the screen command."""

    def test_screen_shows_help(self) -> None:
        """Screen --help should show usage info."""
        from github_discovery.cli.app import app

        result = runner.invoke(app, ["screen", "--help"])
        assert result.exit_code == 0
        assert "--pool-id" in result.output

    def test_screen_no_pool_id_fails(self) -> None:
        """Screen without --pool-id should fail."""
        from github_discovery.cli.app import app

        result = runner.invoke(app, ["screen"])
        assert result.exit_code != 0

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_screen_valid_gate_levels(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """All valid gate levels should be accepted."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        for gate in ["1", "2", "both"]:
            mock_run_async.reset_mock()
            runner.invoke(
                app,
                ["screen", "--pool-id", "test", "--gate", gate],
            )
            assert mock_run_async.called

    @patch("github_discovery.cli.utils.get_settings")
    def test_screen_invalid_gate_level(
        self,
        mock_settings: MagicMock,
    ) -> None:
        """Invalid gate level should produce error."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        result = runner.invoke(
            app,
            ["screen", "--pool-id", "test", "--gate", "invalid"],
        )
        assert result.exit_code != 0

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_screen_custom_thresholds(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """Custom gate thresholds should be accepted."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(
            app,
            [
                "screen",
                "--pool-id",
                "test",
                "--min-gate1",
                "0.6",
                "--min-gate2",
                "0.7",
            ],
        )
        assert mock_run_async.called
