"""CLI streaming progress display — Rich Progress + Live for long operations."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from github_discovery.cli.app import cli_state


def _create_progress() -> Progress:
    """Create a styled Rich Progress bar for CLI operations."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(elapsed_when_finished=True),
        TimeElapsedColumn(),
        console=Console(stderr=True, no_color=cli_state.no_color),
        transient=False,
    )


def get_progress_console() -> Console:
    """Get a Console suitable for progress display (stderr)."""
    return Console(stderr=True, no_color=cli_state.no_color)


async def display_discovery_progress(
    settings: Any,
    query: str,
    channels: list[str] | None,
    max_candidates: int,
    session_id: str | None,
    languages: list[str] | None,
) -> None:
    """Display streaming progress for discovery operation.

    Will be fully implemented in Wave B when the discover command is wired.
    """
    console = get_progress_console()
    console.print(f"[dim]Discovery progress for '{query}' — implementation coming in Wave B[/dim]")
    _ = settings, channels, max_candidates, session_id, languages


async def display_screening_progress(
    settings: Any,
    pool_id: str,
    gate_level: str,
    min_gate1: float | None,
    min_gate2: float | None,
    session_id: str | None,
) -> None:
    """Display streaming progress for screening operation."""
    # Will be implemented in Wave B
    _ = settings, pool_id, gate_level, min_gate1, min_gate2, session_id


async def display_assessment_progress(
    settings: Any,
    pool_id: str | None,
    repo_urls: list[str] | None,
    max_repos: int,
    budget_tokens: int | None,
    dimensions: list[str] | None,
    session_id: str | None,
) -> None:
    """Display streaming progress for deep assessment operation."""
    # Will be implemented in Wave C
    _ = settings, pool_id, repo_urls, max_repos, budget_tokens, dimensions, session_id
