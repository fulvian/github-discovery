"""CLI streaming progress display — Rich Progress + Live for long operations."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

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

    Shows a Rich Progress bar during discovery and a summary table
    with the top 5 candidates upon completion.
    """
    from github_discovery.discovery.orchestrator import DiscoveryOrchestrator
    from github_discovery.discovery.pool import PoolManager
    from github_discovery.discovery.types import DiscoveryQuery
    from github_discovery.models.enums import DiscoveryChannel

    console = get_progress_console()
    pool_mgr = PoolManager()
    orch = DiscoveryOrchestrator(settings, pool_mgr)

    with _create_progress() as progress:
        task = progress.add_task(
            f"[cyan]Discovering[/cyan] '{query}'",
            total=max_candidates,
        )

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

            total = result.total_candidates if hasattr(result, "total_candidates") else 0
            progress.update(task, completed=total)

            # Show results summary
            console.print()
            console.print(
                Panel(
                    f"[green]Discovered {total} candidates[/green]\n"
                    f"Pool ID: {result.pool_id if hasattr(result, 'pool_id') else 'N/A'}",
                    title="Discovery Complete",
                )
            )

            # Show top 5 table — load candidates from pool
            candidates = []
            pool = await pool_mgr.get_pool(result.pool_id)
            if pool is not None:
                candidates = pool.candidates
            if candidates:
                table = Table(title="Top 5 Candidates", show_lines=True)
                table.add_column("#", style="bold cyan", width=4)
                table.add_column("Repository", style="bold")
                table.add_column("Score", width=8)
                table.add_column("Language", width=12)
                table.add_column("Stars", justify="right")

                for i, c in enumerate(candidates[:5], 1):
                    full_name = c.full_name if hasattr(c, "full_name") else str(c)
                    score = f"{c.discovery_score:.2f}" if hasattr(c, "discovery_score") else "N/A"
                    lang = c.language or "" if hasattr(c, "language") else ""
                    stars = str(c.stars) if hasattr(c, "stars") else "N/A"
                    table.add_row(str(i), full_name, score, lang, stars)
                console.print(table)

            console.print()
            pool_id = result.pool_id if hasattr(result, "pool_id") else ""
            if pool_id:
                console.print(f"[dim]Next: ghdisc screen --pool-id {pool_id} --gate both[/dim]")

        finally:
            await pool_mgr.close()


async def display_screening_progress(
    settings: Any,
    pool_id: str,
    gate_level: str,
    min_gate1: float | None,
    min_gate2: float | None,
    session_id: str | None,
) -> None:
    """Display streaming progress for screening operation.

    Shows a Rich Progress bar during screening and a summary table
    with pass/fail counts per gate.
    """
    from github_discovery.cli.utils import exit_with_error
    from github_discovery.discovery.pool import PoolManager
    from github_discovery.models.enums import GateLevel
    from github_discovery.screening.gate1_metadata import Gate1MetadataScreener
    from github_discovery.screening.gate2_static import Gate2StaticScreener
    from github_discovery.screening.orchestrator import ScreeningOrchestrator
    from github_discovery.screening.types import ScreeningContext

    console = get_progress_console()
    pool_mgr = PoolManager()

    try:
        pool = await pool_mgr.get_pool(pool_id)
        if pool is None:
            exit_with_error(f"Pool not found: {pool_id}")
            return  # unreachable

        gate1 = Gate1MetadataScreener(rest_client=None, settings=settings)  # type: ignore[arg-type]
        gate2 = Gate2StaticScreener(rest_client=None, settings=settings, github_settings=settings)  # type: ignore[arg-type]
        orch = ScreeningOrchestrator(settings, gate1, gate2)

        context = ScreeningContext(
            candidates=pool.candidates,
            pool_id=pool_id,
            gate_level=GateLevel(gate_level),
            min_gate1_score=min_gate1 if min_gate1 is not None else 0.4,
            min_gate2_score=min_gate2 if min_gate2 is not None else 0.5,
            session_id=session_id,
        )

        with _create_progress() as progress:
            task = progress.add_task(
                "[cyan]Screening[/cyan] candidates",
                total=len(pool.candidates),
            )

            results = await orch.screen(context)
            progress.update(task, completed=len(results))

        # Count passes
        gate1_passed = sum(1 for r in results if r.gate1 and r.gate1.gate1_pass)
        gate2_passed = sum(1 for r in results if r.gate2 and r.gate2.gate2_pass)
        can_proceed = sum(1 for r in results if r.can_proceed_to_gate3)

        console.print()
        console.print(
            Panel(
                f"[green]Screened {len(results)} candidates[/green]\n"
                f"Gate 1 passed: {gate1_passed}/{len(results)}\n"
                f"Gate 2 passed: {gate2_passed}/{len(results)}\n"
                f"Can proceed to Gate 3: {can_proceed}",
                title="Screening Complete",
            )
        )
        console.print()
        if can_proceed > 0:
            console.print(f"[dim]Next: ghdisc deep-eval --pool-id {pool_id}[/dim]")

    finally:
        await pool_mgr.close()


async def display_assessment_progress(
    settings: Any,
    pool_id: str | None,
    repo_urls: list[str] | None,
    max_repos: int,
    budget_tokens: int | None,
    dimensions: list[str] | None,
    session_id: str | None,
) -> None:
    """Display streaming progress for deep assessment operation.

    Shows a Rich Progress bar during assessment and a summary table
    with overall scores and token usage.
    """
    from datetime import UTC, datetime

    from github_discovery.assessment.orchestrator import AssessmentOrchestrator
    from github_discovery.cli.utils import exit_with_error
    from github_discovery.discovery.pool import PoolManager
    from github_discovery.models.candidate import RepoCandidate
    from github_discovery.models.enums import CandidateStatus, DiscoveryChannel

    console = get_progress_console()
    pool_mgr = PoolManager()

    try:
        # Get candidates from pool or URLs
        candidates = []
        if pool_id:
            pool = await pool_mgr.get_pool(pool_id)
            if pool is None:
                exit_with_error(f"Pool not found: {pool_id}")
                return  # unreachable
            candidates = pool.candidates[:max_repos]
        elif repo_urls:
            for url in repo_urls:
                parts = url.rstrip("/").split("/")
                if len(parts) >= 2:
                    full_name = f"{parts[-2]}/{parts[-1]}"
                    now = datetime.now(tz=UTC)
                    candidates.append(
                        RepoCandidate(
                            full_name=full_name,
                            url=url,
                            html_url=url,
                            api_url=f"https://api.github.com/repos/{full_name}",
                            owner_login=parts[-2],
                            source_channel=DiscoveryChannel.SEARCH,
                            status=CandidateStatus.DISCOVERED,
                            created_at=now,
                            updated_at=now,
                        ),
                    )

        if not candidates:
            exit_with_error("No candidates to assess.")
            return  # unreachable

        # Build screening lookup from FeatureStore for hard gate enforcement
        from github_discovery.config import Settings as RealSettings
        from github_discovery.models.screening import (
            MetadataScreenResult,
            ScreeningResult,
            StaticScreenResult,
        )
        from github_discovery.scoring.feature_store import FeatureStore

        real_settings = settings if isinstance(settings, RealSettings) else RealSettings()
        store = FeatureStore(db_path=".ghdisc/features.db")
        await store.initialize()

        screening_lookup: dict[str, ScreeningResult] = {}
        for candidate in candidates:
            score_result = await store.get_latest(candidate.full_name)
            if score_result is not None:
                gate1_pass = score_result.gate1_total >= real_settings.screening.min_gate1_score
                gate2_pass = score_result.gate2_total >= real_settings.screening.min_gate2_score
                screening_lookup[candidate.full_name] = ScreeningResult(
                    full_name=candidate.full_name,
                    commit_sha=score_result.commit_sha,
                    gate1=MetadataScreenResult(
                        full_name=candidate.full_name,
                        gate1_total=score_result.gate1_total,
                        gate1_pass=gate1_pass,
                        threshold_used=real_settings.screening.min_gate1_score,
                    ),
                    gate2=StaticScreenResult(
                        full_name=candidate.full_name,
                        gate2_total=score_result.gate2_total,
                        gate2_pass=gate2_pass,
                        threshold_used=real_settings.screening.min_gate2_score,
                    ),
                )

        orch = AssessmentOrchestrator(real_settings)

        total_tokens = 0
        assessed = 0

        with _create_progress() as progress:
            task = progress.add_task(
                "[cyan]Assessing[/cyan] candidates (Gate 3)",
                total=len(candidates),
            )

            for candidate in candidates:
                screening = screening_lookup.get(candidate.full_name)
                try:
                    result = await orch.quick_assess(candidate, screening=screening)
                    assessed += 1
                    if result.token_usage:
                        total_tokens += result.token_usage.total_tokens
                except Exception:
                    assessed += 1  # count even failed attempts

                progress.update(task, completed=assessed)

                # Budget check before next candidate
                if budget_tokens and total_tokens >= budget_tokens:
                    console.print(
                        f"[yellow]Budget limit: {total_tokens}/{budget_tokens} tokens[/yellow]"
                    )
                    break

        console.print()
        console.print(
            Panel(
                f"[green]Assessed {assessed}/{len(candidates)} candidates[/green]\n"
                f"Total tokens used: {total_tokens}",
                title="Deep Assessment Complete",
            )
        )

    finally:
        await pool_mgr.close()
