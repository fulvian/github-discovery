"""Tests for the deep-eval CLI command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

runner = CliRunner()


def _mock_run_async(coro: object) -> None:
    """Side-effect for mocked run_async that closes the coroutine."""
    if hasattr(coro, "close"):
        coro.close()  # type: ignore[union-attr]


class TestDeepEvalCommand:
    """Tests for the deep-eval command."""

    def test_deep_eval_shows_help(self) -> None:
        """deep-eval --help should show usage."""
        from github_discovery.cli.app import app

        result = runner.invoke(app, ["deep-eval", "--help"])
        assert result.exit_code == 0
        assert "--pool-id" in result.output
        assert "--repo-urls" in result.output

    @patch("github_discovery.cli.utils.get_settings")
    def test_deep_eval_no_source_fails(self, mock_settings: MagicMock) -> None:
        """Without pool-id or repo-urls, should fail."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        result = runner.invoke(app, ["deep-eval"])
        assert result.exit_code != 0

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_deep_eval_with_pool_id(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """--pool-id should be accepted."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(app, ["deep-eval", "--pool-id", "test-pool"])
        assert mock_run_async.called

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_deep_eval_with_repo_urls(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """--repo-urls should be accepted."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(
            app,
            ["deep-eval", "--repo-urls", "https://github.com/o/r1,https://github.com/o/r2"],
        )
        assert mock_run_async.called

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_deep_eval_max_repos(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """--max-repos should be accepted."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(app, ["deep-eval", "--pool-id", "p", "--max-repos", "10"])
        assert mock_run_async.called

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_deep_eval_budget_tokens(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """--budget-tokens should be accepted."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(app, ["deep-eval", "--pool-id", "p", "--budget-tokens", "100000"])
        assert mock_run_async.called

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_deep_eval_dimensions(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """--dimensions should be accepted."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(
            app,
            ["deep-eval", "--pool-id", "p", "--dimensions", "code_quality,testing"],
        )
        assert mock_run_async.called

    def test_deep_eval_help_shows_hard_gate(self) -> None:
        """Help should mention hard gate enforcement."""
        from github_discovery.cli.app import app

        result = runner.invoke(app, ["deep-eval", "--help"])
        assert result.exit_code == 0
        assert "Gate" in result.output
