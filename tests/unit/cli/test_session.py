"""Tests for the session CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

runner = CliRunner()


def _mock_run_async(coro: object) -> None:
    """Side-effect for mocked run_async that closes the coroutine."""
    if hasattr(coro, "close"):
        coro.close()  # type: ignore[union-attr]


class TestSessionCreateCommand:
    """Tests for session create."""

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_session_create_no_name(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """Session create without name should work."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(app, ["session", "create"])
        assert mock_run_async.called

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_session_create_with_name(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """Session create with name argument should work."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(app, ["session", "create", "my-session"])
        assert mock_run_async.called


class TestSessionListCommand:
    """Tests for session list."""

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_session_list_default(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """Session list without options should work."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(app, ["session", "list"])
        assert mock_run_async.called

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_session_list_with_status(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """Session list --status should be accepted."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(app, ["session", "list", "--status", "completed"])
        assert mock_run_async.called

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_session_list_with_limit(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """Session list --limit should be accepted."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(app, ["session", "list", "--limit", "20"])
        assert mock_run_async.called


class TestSessionResumeCommand:
    """Tests for session resume."""

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_session_resume(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """Session resume with session_id should work."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(app, ["session", "resume", "abc-123"])
        assert mock_run_async.called


class TestSessionShowCommand:
    """Tests for session show."""

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_session_show(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """Session show with session_id should work."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(app, ["session", "show", "abc-123"])
        assert mock_run_async.called

    @patch("github_discovery.cli.utils.run_async", side_effect=_mock_run_async)
    @patch("github_discovery.cli.utils.get_settings")
    def test_session_show_json_output(
        self,
        mock_settings: MagicMock,
        mock_run_async: MagicMock,
    ) -> None:
        """Session show --output json should be accepted."""
        mock_settings.return_value = MagicMock()

        from github_discovery.cli.app import app

        runner.invoke(app, ["session", "show", "abc-123", "--output", "json"])
        assert mock_run_async.called
