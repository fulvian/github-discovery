"""Tests for CLI app factory and global callback."""

from __future__ import annotations

from typer.testing import CliRunner

runner = CliRunner()


class TestAppFactory:
    """Tests for the Typer app creation and configuration."""

    def test_app_has_name_ghdisc(self) -> None:
        """App name should be 'ghdisc'."""
        from github_discovery.cli.app import app

        assert app.info.name == "ghdisc"

    def test_app_no_args_shows_help(self) -> None:
        """Running with no args should show help (exit code 2 from Typer)."""
        from github_discovery.cli.app import app

        result = runner.invoke(app, [])
        assert result.exit_code == 2
        assert "GitHub Discovery" in result.output

    def test_version_command(self) -> None:
        """Version command should show version string."""
        from github_discovery.cli.app import app

        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "github-discovery" in result.output

    def test_help_shows_subcommands(self) -> None:
        """Help should list mcp and session subgroups."""
        from github_discovery.cli.app import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "mcp" in result.output
        assert "session" in result.output

    def test_help_flag_short(self) -> None:
        """Short -h flag should show help."""
        from github_discovery.cli.app import app

        result = runner.invoke(app, ["-h"])
        assert result.exit_code == 0
        assert "GitHub Discovery" in result.output


class TestGlobalCallback:
    """Tests for the global @app.callback() options."""

    def test_verbose_flag_sets_state(self, reset_cli_state: None) -> None:
        """--verbose flag should set cli_state.verbose to True."""
        from github_discovery.cli.app import app, cli_state

        assert cli_state.verbose is False
        runner.invoke(app, ["--verbose", "version"])
        assert cli_state.verbose is True

    def test_output_format_option(self, reset_cli_state: None) -> None:
        """--output-format should set cli_state.output_format."""
        from github_discovery.cli.app import app, cli_state

        runner.invoke(app, ["--output-format", "json", "version"])
        assert cli_state.output_format == "json"

    def test_no_color_flag(self, reset_cli_state: None) -> None:
        """--no-color should set cli_state.no_color to True."""
        from github_discovery.cli.app import app, cli_state

        runner.invoke(app, ["--no-color", "version"])
        assert cli_state.no_color is True
