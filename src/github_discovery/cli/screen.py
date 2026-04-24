"""CLI command: ghdisc screen — screen candidates through quality gates."""

from __future__ import annotations

from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    """Register the screen command on the main app."""

    @app.command(
        name="screen",
        help="Screen candidates through quality gates (Gate 1+2).",
        rich_help_panel="Pipeline",
    )
    def screen(
        pool_id: Annotated[
            str,
            typer.Option("--pool-id", "-p", help="Candidate pool ID from discover"),
        ],
        gate: Annotated[
            str,
            typer.Option("--gate", "-g", help="Gate level: 1, 2, or both"),
        ] = "both",
        min_gate1_score: Annotated[
            float | None,
            typer.Option("--min-gate1", help="Override minimum Gate 1 score"),
        ] = None,
        min_gate2_score: Annotated[
            float | None,
            typer.Option("--min-gate2", help="Override minimum Gate 2 score"),
        ] = None,
        session_id: Annotated[
            str | None,
            typer.Option("--session-id", "-s", help="Session ID for workflow continuity"),
        ] = None,
        output: Annotated[
            str | None,
            typer.Option("--output", "-o", help="Output format: json|table|markdown|yaml"),
        ] = None,
        stream: Annotated[
            bool,
            typer.Option("--stream/--no-stream", help="Show streaming progress"),
        ] = True,
    ) -> None:
        """Screen candidates through quality gates (Gate 1+2)."""
        from github_discovery.cli.utils import (
            exit_with_error,
            get_settings,
            resolve_output_format,
            run_async,
        )

        settings = get_settings()
        fmt = resolve_output_format(output)

        gate_map = {"1": "METADATA", "2": "STATIC_SECURITY", "both": "BOTH"}
        gate_level_raw = gate_map.get(gate.lower())
        if gate_level_raw is None:
            exit_with_error(f"Invalid gate level: {gate}. Use 1, 2, or both.")
            return  # unreachable: exit_with_error raises SystemExit

        run_async(
            _screen_pool(
                settings,
                pool_id,
                gate_level_raw,
                min_gate1_score,
                min_gate2_score,
                session_id,
                fmt,
            ),
        )


async def _screen_pool(
    settings: object,
    pool_id: str,
    gate_level: str,
    min_gate1: float | None,
    min_gate2: float | None,
    session_id: str | None,
    fmt: str,
) -> None:
    """Run screening on a candidate pool."""
    from github_discovery.cli.formatters import format_output
    from github_discovery.cli.utils import exit_with_error, get_output_console
    from github_discovery.discovery.pool import PoolManager
    from github_discovery.models.enums import GateLevel
    from github_discovery.screening.gate1_metadata import Gate1MetadataScreener
    from github_discovery.screening.gate2_static import Gate2StaticScreener
    from github_discovery.screening.orchestrator import ScreeningOrchestrator
    from github_discovery.screening.types import ScreeningContext

    pool_mgr = PoolManager()
    try:
        pool = await pool_mgr.get_pool(pool_id)
        if pool is None:
            exit_with_error(f"Pool not found: {pool_id}")
            return  # unreachable: exit_with_error raises SystemExit

        gate1 = Gate1MetadataScreener(
            rest_client=None,  # type: ignore[arg-type]
            settings=settings,  # type: ignore[arg-type]
        )
        gate2 = Gate2StaticScreener(
            rest_client=None,  # type: ignore[arg-type]
            settings=settings,  # type: ignore[arg-type]
            github_settings=settings,  # type: ignore[arg-type]
        )
        orch = ScreeningOrchestrator(settings, gate1, gate2)  # type: ignore[arg-type]

        context = ScreeningContext(
            candidates=pool.candidates,
            pool_id=pool_id,
            gate_level=GateLevel(gate_level),
            min_gate1_score=min_gate1 if min_gate1 is not None else 0.4,
            min_gate2_score=min_gate2 if min_gate2 is not None else 0.5,
            session_id=session_id,
        )

        results = await orch.screen(context)

        # Convert results to display format
        display_data = [
            {
                "full_name": r.full_name,
                "gate1_passed": r.gate1.gate1_pass if r.gate1 else False,
                "gate1_score": r.gate1.gate1_total if r.gate1 else 0.0,
                "gate2_passed": r.gate2.gate2_pass if r.gate2 else False,
                "gate2_score": r.gate2.gate2_total if r.gate2 else 0.0,
                "can_proceed_to_gate3": r.can_proceed_to_gate3,
            }
            for r in results
        ]

        formatted = format_output(
            data={"results": display_data, "pool_id": pool_id, "total": len(results)},
            fmt=fmt,
            output_type="screening",
        )
        out_console = get_output_console()
        out_console.print(formatted)

    except SystemExit:
        raise
    except Exception as e:
        exit_with_error(f"Screening failed: {e}")
    finally:
        await pool_mgr.close()
