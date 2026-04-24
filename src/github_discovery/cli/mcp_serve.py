"""CLI command: ghdisc mcp serve."""

from __future__ import annotations

from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    """Register MCP serve command on the given Typer app."""

    @app.command(name="serve")
    def serve(
        transport: Annotated[
            str,
            typer.Option("--transport", "-t", help="Transport: stdio or http"),
        ] = "stdio",
        host: Annotated[
            str,
            typer.Option("--host", help="Host for HTTP transport"),
        ] = "127.0.0.1",
        port: Annotated[
            int,
            typer.Option("--port", "-p", help="Port for HTTP transport"),
        ] = 8080,
    ) -> None:
        """Start the MCP server with the specified transport."""
        from github_discovery.cli.utils import get_settings

        settings = get_settings()
        settings.mcp.transport = transport
        if host != "127.0.0.1":
            settings.mcp.host = host
        if port != 8080:
            settings.mcp.port = port

        from github_discovery.mcp.server import serve as mcp_serve

        mcp_serve(settings)
