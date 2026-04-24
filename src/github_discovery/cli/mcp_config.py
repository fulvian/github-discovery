"""CLI command: ghdisc mcp init-config."""

from __future__ import annotations

import json
import sys
from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    """Register MCP init-config command on the given Typer app."""

    @app.command(name="init-config")
    def init_config(
        target: Annotated[
            str,
            typer.Option("--target", "-t", help="Target: kilo, opencode, claude"),
        ] = "kilo",
        output: Annotated[
            str,
            typer.Option("--output", "-o", help="Output file path (- for stdout)"),
        ] = "-",
    ) -> None:
        """Generate MCP client configuration for agent integration."""
        from github_discovery.config import Settings
        from github_discovery.mcp.github_client import get_composition_config

        settings = Settings()

        try:
            config = get_composition_config(settings, target=target)
        except ValueError as e:
            typer.echo(f"Error: {e}", err=True)
            raise SystemExit(1) from e

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
