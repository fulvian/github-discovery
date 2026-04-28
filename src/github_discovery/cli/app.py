"""GitHub Discovery CLI — Typer app factory with global options and command registration."""

from __future__ import annotations

import logging
from typing import Annotated

import typer

from github_discovery import __version__

app = typer.Typer(
    name="ghdisc",
    help="GitHub Discovery — MCP-native agentic discovery engine",
    no_args_is_help=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Sub-Typer groups
mcp_app = typer.Typer(
    name="mcp",
    help="MCP server commands",
    no_args_is_help=True,
)
session_app = typer.Typer(
    name="session",
    help="Session management for agentic workflows",
    no_args_is_help=True,
)


class _CliState:
    """Shared CLI state populated from global options."""

    verbose: bool = False
    config_file: str = ".env"
    output_format: str = "table"
    log_level: str = "INFO"
    no_color: bool = False


cli_state = _CliState()


@app.callback()
def main_callback(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose output"),
    ] = False,
    config_file: Annotated[
        str,
        typer.Option("--config-file", help="Path to .env config file"),
    ] = ".env",
    output_format: Annotated[
        str,
        typer.Option(
            "--output-format",
            "-o",
            help="Default output format: json|table|markdown|yaml",
        ),
    ] = "table",
    log_level: Annotated[
        str,
        typer.Option("--log-level", help="Log level: DEBUG|INFO|WARNING|ERROR"),
    ] = "INFO",
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable colored output"),
    ] = False,
) -> None:
    """GitHub Discovery — MCP-native agentic discovery engine.

    Find high-quality GitHub repositories independent of popularity (stars).

    Use [bold green]ghdisc discover[/bold green] to start finding repos,
    or [bold green]ghdisc mcp serve[/bold green] to start the MCP server.
    """
    cli_state.verbose = verbose
    cli_state.config_file = config_file
    cli_state.output_format = output_format
    cli_state.log_level = log_level
    cli_state.no_color = no_color

    # Effective log level: WARNING by default (quiet CLI), DEBUG with --verbose,
    # or whatever the user explicitly sets with --log-level.
    effective_level = log_level
    if log_level == "INFO" and not verbose:
        effective_level = "WARNING"
    elif verbose and log_level == "INFO":
        effective_level = "DEBUG"

    logging.getLogger("github_discovery").setLevel(
        getattr(logging, effective_level.upper(), logging.WARNING),
    )


@app.command()
def version() -> None:
    """Show the current version."""
    typer.echo(f"github-discovery {__version__}")


# Register sub-groups
app.add_typer(mcp_app, name="mcp")
app.add_typer(session_app, name="session")


def _register_commands() -> None:
    """Register all CLI commands via lazy imports."""
    from github_discovery.cli.compare import register as reg_compare
    from github_discovery.cli.db import register as reg_db
    from github_discovery.cli.deep_eval import register as reg_deep_eval
    from github_discovery.cli.discover import register as reg_discover
    from github_discovery.cli.doctor import register as reg_doctor
    from github_discovery.cli.explain import register as reg_explain
    from github_discovery.cli.export import register as reg_export
    from github_discovery.cli.mcp_config import register as reg_mcp_config
    from github_discovery.cli.mcp_serve import register as reg_mcp_serve
    from github_discovery.cli.profiles import register as reg_profiles
    from github_discovery.cli.rank import register as reg_rank
    from github_discovery.cli.screen import register as reg_screen
    from github_discovery.cli.session import register as reg_session

    reg_discover(app)
    reg_screen(app)
    reg_deep_eval(app)
    reg_rank(app)
    reg_explain(app)
    reg_compare(app)
    reg_export(app)
    reg_db(app)
    reg_profiles(app)
    reg_session(session_app)
    reg_mcp_serve(mcp_app)
    reg_mcp_config(mcp_app)
    reg_doctor(app)


_register_commands()

if __name__ == "__main__":
    app()
