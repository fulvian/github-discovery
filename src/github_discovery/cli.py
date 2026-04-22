"""GitHub Discovery CLI entry point (placeholder for Phase 8)."""

from __future__ import annotations

import typer

from github_discovery import __version__

app = typer.Typer(
    name="ghdisc",
    help="GitHub Discovery — MCP-native agentic discovery engine",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Show the current version."""
    typer.echo(f"github-discovery {__version__}")


if __name__ == "__main__":
    app()
