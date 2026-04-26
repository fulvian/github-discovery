"""Tests for the db prune CLI command — T3.5."""

from __future__ import annotations

from typer.testing import CliRunner

from github_discovery.cli.app import app

runner = CliRunner()


class TestDbPruneCLI:
    """Tests for the 'ghdisc db prune' CLI command."""

    def test_db_prune_command_exists(self) -> None:
        """The db prune command is registered and shows help."""
        result = runner.invoke(app, ["db", "prune", "--help"])
        assert result.exit_code == 0
        assert "dry-run" in result.output.lower() or "--dry-run" in result.output

    def test_db_prune_dry_run(self) -> None:
        """db prune --dry-run runs without error."""
        result = runner.invoke(app, ["db", "prune", "--dry-run"])
        assert result.exit_code == 0
        assert "prune" in result.output.lower() or "would" in result.output.lower()

    def test_db_command_registered(self) -> None:
        """The db subcommand is registered."""
        result = runner.invoke(app, ["db", "--help"])
        assert result.exit_code == 0
        assert "prune" in result.output.lower()
