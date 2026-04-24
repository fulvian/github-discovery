"""CLI command: ghdisc export — export session results."""

# ruff: noqa: A002 (format shadows builtin — matches typer CLI convention)
# ruff: noqa: PLR0912, PLR0915 (export routing has many branches by design)

from __future__ import annotations

import sys
from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    """Register the export command on the main app."""

    @app.command(
        name="export",
        help="Export session results in JSON, CSV, or Markdown format.",
        rich_help_panel="Pipeline",
    )
    def export_cmd(
        session_id: Annotated[
            str | None,
            typer.Option("--session-id", "-s", help="Session to export"),
        ] = None,
        pool_id: Annotated[
            str | None,
            typer.Option("--pool-id", "-p", help="Pool to export (alternative to session)"),
        ] = None,
        format: Annotated[
            str,
            typer.Option("--format", "-f", help="Export format: json|csv|markdown"),
        ] = "json",
        output: Annotated[
            str,
            typer.Option("--output", "-o", help="Output file path (default: stdout)"),
        ] = "-",
        domain: Annotated[
            str | None,
            typer.Option("--domain", "-d", help="Filter by domain"),
        ] = None,
        include_details: Annotated[
            bool,
            typer.Option(
                "--include-details/--no-include-details",
                help="Include full dimension breakdown",
            ),
        ] = False,
    ) -> None:
        """Export session results in JSON, CSV, or Markdown format."""
        from github_discovery.cli.utils import (
            exit_with_error,
            get_settings,
            run_async,
        )

        if not session_id and not pool_id:
            exit_with_error("Must specify either --session-id or --pool-id")

        settings = get_settings()
        run_async(
            _export(settings, session_id, pool_id, format, output, domain, include_details),
        )


async def _export(
    settings: object,
    session_id: str | None,
    pool_id: str | None,
    format: str,
    output_path: str,
    domain: str | None,
    include_details: bool,
) -> None:
    """Export data to file or stdout."""
    import json
    from pathlib import Path

    from github_discovery.cli.formatters import format_csv, format_output
    from github_discovery.cli.utils import exit_with_error
    from github_discovery.discovery.pool import PoolManager

    pool_mgr = PoolManager()

    try:
        # Collect data
        data: dict[str, object] | list[object] = {}
        if session_id:
            from github_discovery.mcp.session import SessionManager

            db_path = (
                settings.mcp.session_store_path
                if hasattr(settings, "mcp")
                else ".ghdisc/sessions.db"
            )
            mgr = SessionManager(str(db_path))
            await mgr.initialize()
            try:
                session = await mgr.get(session_id)
                if session is None:
                    exit_with_error(f"Session not found: {session_id}")
                    return  # unreachable: exit_with_error raises SystemExit
                data = session.model_dump(mode="json")
            finally:
                await mgr.close()
        elif pool_id:
            pool = await pool_mgr.get_pool(pool_id)
            if pool is None:
                exit_with_error(f"Pool not found: {pool_id}")
                return  # unreachable: exit_with_error raises SystemExit
            data = {
                "pool_id": pool.pool_id,
                "query": pool.query,
                "candidates": [c.model_dump(mode="json") for c in pool.candidates],
                "total_count": pool.total_count,
            }

        # Format and write
        if format == "json":
            content = json.dumps(data, indent=2, default=str)
        elif format == "csv":
            candidates = data.get("candidates", []) if isinstance(data, dict) else []
            if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict):
                content = format_csv(candidates)
            else:
                content = ""
        elif format == "markdown":
            content = format_output(data, "markdown", "export")
        else:
            exit_with_error(f"Unknown export format: {format}")
            return  # unreachable: exit_with_error raises SystemExit

        # Write output
        if output_path == "-":
            sys.stdout.write(str(content))
            if not str(content).endswith("\n"):
                sys.stdout.write("\n")
        else:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            text = str(content)
            path.write_text(text + ("\n" if not text.endswith("\n") else ""))

    except SystemExit:
        raise
    except Exception as e:
        exit_with_error(f"Export failed: {e}")
    finally:
        await pool_mgr.close()
