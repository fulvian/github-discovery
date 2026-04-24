"""CLI command: ghdisc discover — discover candidate repositories."""

from __future__ import annotations

from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    """Register the discover command on the main app."""

    @app.command(
        name="discover",
        help="Discover candidate repositories matching a query.",
        rich_help_panel="Pipeline",
    )
    def discover(
        query: Annotated[
            str,
            typer.Argument(help="Search query for repositories"),
        ],
        channels: Annotated[
            str | None,
            typer.Option(
                "--channels",
                "-c",
                help="Discovery channels (comma-sep: search,code_search,dependency,registry,...)",
            ),
        ] = None,
        max_candidates: Annotated[
            int,
            typer.Option("--max", "-m", help="Maximum candidates to discover"),
        ] = 100,
        session_id: Annotated[
            str | None,
            typer.Option("--session-id", "-s", help="Session ID for workflow continuity"),
        ] = None,
        output: Annotated[
            str | None,
            typer.Option("--output", "-o", help="Output format: json|table|markdown|yaml"),
        ] = None,
        languages: Annotated[
            str | None,
            typer.Option("--languages", "-l", help="Filter by languages (comma-sep)"),
        ] = None,
        stream: Annotated[
            bool,
            typer.Option("--stream/--no-stream", help="Show streaming progress"),
        ] = True,
    ) -> None:
        """Discover candidate repositories matching a query."""
        from github_discovery.cli.utils import (
            comma_separated_to_list,
            get_settings,
            resolve_output_format,
            run_async,
        )

        settings = get_settings()
        channel_list = comma_separated_to_list(channels) if channels else None
        lang_list = comma_separated_to_list(languages) if languages else None
        fmt = resolve_output_format(output)

        if stream:
            run_async(
                _discover_streaming(
                    settings,
                    query,
                    channel_list,
                    max_candidates,
                    session_id,
                    lang_list,
                ),
            )
        else:
            run_async(
                _discover_direct(
                    settings,
                    query,
                    channel_list,
                    max_candidates,
                    session_id,
                    lang_list,
                    fmt,
                ),
            )


async def _discover_streaming(
    settings: object,
    query: str,
    channels: list[str] | None,
    max_candidates: int,
    session_id: str | None,
    languages: list[str] | None,
) -> None:
    """Run discovery with streaming progress display."""
    from github_discovery.cli.progress_display import display_discovery_progress

    await display_discovery_progress(
        settings=settings,
        query=query,
        channels=channels,
        max_candidates=max_candidates,
        session_id=session_id,
        languages=languages,
    )


async def _discover_direct(
    settings: object,
    query: str,
    channels: list[str] | None,
    max_candidates: int,
    session_id: str | None,
    languages: list[str] | None,
    fmt: str,
) -> None:
    """Run discovery without streaming, format and print result."""
    from github_discovery.cli.formatters import format_output
    from github_discovery.cli.utils import exit_with_error, get_output_console
    from github_discovery.discovery.orchestrator import DiscoveryOrchestrator
    from github_discovery.discovery.pool import PoolManager
    from github_discovery.discovery.types import DiscoveryQuery
    from github_discovery.models.enums import DiscoveryChannel

    pool_mgr = PoolManager()
    orch = DiscoveryOrchestrator(settings, pool_mgr)  # type: ignore[arg-type]

    try:
        resolved_channels = None
        if channels:
            resolved_channels = [DiscoveryChannel(ch.strip()) for ch in channels if ch.strip()]

        dq = DiscoveryQuery(
            query=query,
            channels=resolved_channels,
            max_candidates=max_candidates,
            language=languages[0] if languages else None,
            session_id=session_id,
        )

        result = await orch.discover(dq)
        formatted = format_output(
            data=result,
            fmt=fmt,
            output_type="discovery",
        )
        out_console = get_output_console()
        out_console.print(formatted)

    except Exception as e:
        exit_with_error(f"Discovery failed: {e}")
    finally:
        await pool_mgr.close()
