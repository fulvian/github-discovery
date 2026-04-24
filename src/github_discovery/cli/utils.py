"""CLI utility helpers."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog
from rich.console import Console

from github_discovery.cli.app import cli_state

if TYPE_CHECKING:
    from collections.abc import Coroutine

logger = structlog.get_logger("github_discovery.cli")


def get_console() -> Console:
    """Get a Rich Console for stderr (diagnostics), respecting CLI state."""
    return Console(
        no_color=cli_state.no_color,
        stderr=True,
    )


def get_output_console() -> Console:
    """Get a Rich Console for stdout (data output)."""
    return Console(
        no_color=cli_state.no_color,
        stderr=False,
    )


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run an async coroutine from synchronous CLI context.

    Typer does not natively support async commands.
    This wrapper bridges the gap with asyncio.run().
    """
    return asyncio.run(coro)


def resolve_output_format(format_override: str | None) -> str:
    """Resolve output format: CLI flag > global option > default 'table'."""
    return format_override or cli_state.output_format or "table"


def get_settings() -> Any:
    """Load Settings with CLI-specified config file."""
    from github_discovery.config import Settings

    return Settings(_env_file=cli_state.config_file)  # type: ignore[call-arg]


def comma_separated_to_list(value: str) -> list[str]:
    """Parse a comma-separated string into a list of stripped strings."""
    return [s.strip() for s in value.split(",") if s.strip()]


def exit_with_error(message: str, code: int = 1) -> None:
    """Print error to stderr and exit with code."""
    console = get_console()
    console.print(f"[bold red]Error:[/bold red] {message}")
    raise SystemExit(code)
