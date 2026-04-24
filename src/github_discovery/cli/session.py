"""CLI commands: ghdisc session create/list/resume/show."""

from __future__ import annotations

from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    """Register session management commands on the session sub-app."""

    @app.command(name="create")
    def create(
        name: Annotated[
            str,
            typer.Argument(help="Human-readable session name"),
        ] = "",
    ) -> None:
        """Create a new discovery session."""
        from github_discovery.cli.utils import get_settings, run_async

        settings = get_settings()
        run_async(_create_session(settings, name))

    @app.command(name="list")
    def list_sessions(
        status: Annotated[
            str | None,
            typer.Option(
                "--status",
                help="Filter by status: created, screening, assessing, completed",
            ),
        ] = None,
        limit: Annotated[
            int,
            typer.Option("--limit", "-n", help="Max sessions to show"),
        ] = 10,
    ) -> None:
        """List active or completed sessions."""
        from github_discovery.cli.utils import get_settings, run_async

        settings = get_settings()
        run_async(_list_sessions(settings, status, limit))

    @app.command(name="resume")
    def resume(
        session_id: Annotated[
            str,
            typer.Argument(help="Session ID to resume"),
        ],
    ) -> None:
        """Resume an existing session and show its state."""
        from github_discovery.cli.utils import get_settings, run_async

        settings = get_settings()
        run_async(_resume_session(settings, session_id))

    @app.command(name="show")
    def show(
        session_id: Annotated[
            str,
            typer.Argument(help="Session ID to inspect"),
        ],
        output: Annotated[
            str | None,
            typer.Option("--output", "-o", help="Output format: json|table|markdown"),
        ] = None,
    ) -> None:
        """Show detailed session state."""
        from github_discovery.cli.utils import get_settings, resolve_output_format, run_async

        settings = get_settings()
        fmt = resolve_output_format(output)
        run_async(_show_session(settings, session_id, fmt))


async def _create_session(settings: object, name: str) -> None:
    """Create a new session."""
    from github_discovery.cli.utils import get_console
    from github_discovery.mcp.session import SessionManager

    db_path = (
        settings.mcp.session_store_path if hasattr(settings, "mcp") else ".ghdisc/sessions.db"
    )
    mgr = SessionManager(str(db_path))
    await mgr.initialize()
    try:
        session = await mgr.create(name=name)
        console = get_console()
        console.print(f"[green]Created session:[/green] {session.session_id}")
        console.print(f"  Name: {session.name or '(unnamed)'}")
        console.print(f"  Use --session-id {session.session_id} with other commands")
    finally:
        await mgr.close()


async def _list_sessions(settings: object, status: str | None, limit: int) -> None:
    """List sessions."""
    from github_discovery.cli.formatters import format_output
    from github_discovery.cli.utils import get_console, get_output_console
    from github_discovery.mcp.session import SessionManager
    from github_discovery.models.session import SessionStatus

    db_path = (
        settings.mcp.session_store_path if hasattr(settings, "mcp") else ".ghdisc/sessions.db"
    )
    mgr = SessionManager(str(db_path))
    await mgr.initialize()
    try:
        status_filter = SessionStatus(status) if status else None
        sessions = await mgr.list_sessions(status=status_filter, limit=limit)

        if not sessions:
            console = get_console()
            console.print("[dim]No sessions found.[/dim]")
            return

        session_data = [s.model_dump(mode="json") for s in sessions]
        formatted = format_output(session_data, "table", "session_list")
        out_console = get_output_console()
        out_console.print(formatted)
    finally:
        await mgr.close()


async def _resume_session(settings: object, session_id: str) -> None:
    """Resume a session and suggest next steps."""
    from github_discovery.cli.utils import exit_with_error, get_console
    from github_discovery.mcp.session import SessionManager
    from github_discovery.models.session import SessionStatus

    db_path = (
        settings.mcp.session_store_path if hasattr(settings, "mcp") else ".ghdisc/sessions.db"
    )
    mgr = SessionManager(str(db_path))
    await mgr.initialize()
    try:
        session = await mgr.get(session_id)
        if session is None:
            exit_with_error(f"Session not found: {session_id}")
            return  # unreachable: exit_with_error raises SystemExit

        console = get_console()
        console.print(f"[bold]Session: {session.name or session.session_id}[/bold]")
        console.print(f"  Status: {session.status}")
        console.print(f"  Discovered: {session.discovered_repo_count}")
        console.print(f"  Screened: {session.screened_repo_count}")
        console.print(f"  Assessed: {session.assessed_repo_count}")
        console.print()

        # Suggest next step based on status
        next_steps: dict[str, str] = {
            SessionStatus.CREATED: "ghdisc discover --session-id {sid}",
            SessionStatus.DISCOVERING: "ghdisc screen --session-id {sid}",
            SessionStatus.SCREENING: "ghdisc deep-eval --session-id {sid}",
            SessionStatus.ASSESSING: "ghdisc rank --session-id {sid}",
            SessionStatus.RANKING: "ghdisc export --session-id {sid}",
            SessionStatus.COMPLETED: "ghdisc export --session-id {sid} --format json",
        }
        suggestion = next_steps.get(
            session.status,
            "ghdisc session show {sid}",
        ).replace("{sid}", session.session_id)
        console.print(f"[cyan]Next step:[/cyan] {suggestion}")
    finally:
        await mgr.close()


async def _show_session(settings: object, session_id: str, fmt: str) -> None:
    """Show detailed session state."""
    from github_discovery.cli.formatters import format_output
    from github_discovery.cli.utils import exit_with_error, get_output_console
    from github_discovery.mcp.session import SessionManager

    db_path = (
        settings.mcp.session_store_path if hasattr(settings, "mcp") else ".ghdisc/sessions.db"
    )
    mgr = SessionManager(str(db_path))
    await mgr.initialize()
    try:
        session = await mgr.get(session_id)
        if session is None:
            exit_with_error(f"Session not found: {session_id}")
            return  # unreachable: exit_with_error raises SystemExit

        formatted = format_output(session.model_dump(mode="json"), fmt, "session")
        out_console = get_output_console()
        out_console.print(formatted)
    finally:
        await mgr.close()
