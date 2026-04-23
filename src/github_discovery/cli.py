"""GitHub Discovery CLI entry point.

Provides ``ghdisc`` CLI with version, MCP server control, and config generation.

Usage::

    python -m github_discovery --help
    python -m github_discovery version
    python -m github_discovery mcp serve --transport stdio
    python -m github_discovery mcp init-config --target kilo
"""

from __future__ import annotations

import json
import sys

import typer

from github_discovery import __version__

app = typer.Typer(
    name="ghdisc",
    help="GitHub Discovery — MCP-native agentic discovery engine",
    no_args_is_help=True,
)

mcp_app = typer.Typer(
    name="mcp",
    help="MCP server commands",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Show the current version."""
    typer.echo(f"github-discovery {__version__}")


@mcp_app.command()
def serve(
    transport: str = typer.Option(
        "stdio",
        "--transport",
        "-t",
        help="Transport protocol: stdio or http",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        "-h",
        help="Host for HTTP transport",
    ),
    port: int = typer.Option(
        8080,
        "--port",
        "-p",
        help="Port for HTTP transport",
    ),
) -> None:
    """Start the MCP server with the specified transport.

    The server exposes 16 tools, 4 resources, and 5 prompts for
    agentic repository discovery workflows.
    """
    from github_discovery.config import Settings

    settings = Settings()
    # Override transport settings from CLI flags
    settings.mcp.transport = transport
    if host != "127.0.0.1":
        settings.mcp.host = host
    if port != 8080:
        settings.mcp.port = port

    from github_discovery.mcp.server import serve as mcp_serve

    mcp_serve(settings)


@mcp_app.command()
def init_config(
    target: str = typer.Option(
        "kilo",
        "--target",
        "-t",
        help="Target platform: kilo, opencode, claude",
    ),
    output: str = typer.Option(
        "-",
        "--output",
        "-o",
        help="Output file path (use - for stdout)",
    ),
) -> None:
    """Generate MCP client configuration for agent integration.

    Produces a JSON configuration that composes GitHub Discovery with
    the GitHub MCP Server for the specified agent platform.
    """
    from github_discovery.config import Settings
    from github_discovery.mcp.github_client import get_composition_config

    settings = Settings()

    try:
        config = get_composition_config(settings, target=target)
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from e

    # Wrap in "mcp" key for Kilocode / OpenCode format
    full_config: dict[str, object] = {"mcp": config}
    config_str = json.dumps(full_config, indent=2)

    if output == "-":
        sys.stdout.write(config_str)
        sys.stdout.write("\n")
    else:
        from pathlib import Path

        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(config_str + "\n")
        typer.echo(f"Configuration written to {path}")


app.add_typer(mcp_app, name="mcp")

if __name__ == "__main__":
    app()
