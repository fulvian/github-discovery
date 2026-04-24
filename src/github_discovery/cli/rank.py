"""CLI command: ghdisc rank — rank repositories using anti-star bias scoring."""

from __future__ import annotations

from typing import Annotated

import typer

from github_discovery.models.enums import DomainType


def register(app: typer.Typer) -> None:
    """Register the rank command on the main app."""

    @app.command(
        name="rank",
        help="Rank repositories using anti-star bias scoring.",
        rich_help_panel="Pipeline",
    )
    def rank(
        domain: Annotated[
            str | None,
            typer.Option(
                "--domain",
                "-d",
                help="Domain for ranking (e.g., library, cli, ml_lib)",
            ),
        ] = None,
        top: Annotated[
            int,
            typer.Option("--top", "-t", help="Number of top repos to show"),
        ] = 20,
        min_confidence: Annotated[
            float,
            typer.Option("--min-confidence", help="Minimum confidence threshold"),
        ] = 0.3,
        min_value_score: Annotated[
            float,
            typer.Option("--min-value-score", help="Minimum value score (anti-star bias)"),
        ] = 0.0,
        session_id: Annotated[
            str | None,
            typer.Option("--session-id", "-s", help="Session ID for workflow continuity"),
        ] = None,
        output: Annotated[
            str | None,
            typer.Option("--output", "-o", help="Output format: json|table|markdown|yaml"),
        ] = None,
    ) -> None:
        """Rank repositories using anti-star bias scoring."""
        from github_discovery.cli.utils import (
            exit_with_error,
            get_settings,
            resolve_output_format,
            run_async,
        )

        settings = get_settings()
        fmt = resolve_output_format(output)

        if domain is None:
            exit_with_error("--domain is required for ranking.")
            return  # unreachable: exit_with_error raises SystemExit

        run_async(
            _rank_repos(
                settings,
                domain,
                top,
                min_confidence,
                min_value_score,
                session_id,
                fmt,
            ),
        )


async def _rank_repos(
    settings: object,
    domain: str,
    top: int,
    min_confidence: float,
    min_value_score: float,
    session_id: str | None,
    fmt: str,
) -> None:
    """Run ranking for a domain."""
    from github_discovery.cli.formatters import format_output
    from github_discovery.cli.utils import exit_with_error, get_output_console
    from github_discovery.models.enums import DomainType
    from github_discovery.scoring.feature_store import FeatureStore
    from github_discovery.scoring.ranker import Ranker

    _ = settings  # kept for future use (e.g., settings-based defaults)
    _ = session_id  # kept for future use (e.g., session-scoped ranking)

    domain_type = _resolve_domain(domain)
    if domain_type is None:
        valid = [d.value for d in DomainType]
        exit_with_error(f"Invalid domain: {domain}. Valid: {', '.join(valid)}")
        return  # unreachable: exit_with_error raises SystemExit

    ranker = Ranker()

    # Load scored repos from FeatureStore
    store = FeatureStore()
    try:
        await store.initialize()
        all_features = await store.get_by_domain(domain_type)
    except Exception as e:
        exit_with_error(
            f"Failed to load scored repos for domain '{domain}': {e}. "
            "Run discover + screen + deep-eval first.",
        )
        return  # unreachable: exit_with_error raises SystemExit

    if not all_features:
        exit_with_error(
            f"No scored repos found for domain '{domain}'. "
            "Run discover + screen + deep-eval first.",
        )
        return  # unreachable: exit_with_error raises SystemExit

    result = ranker.rank(
        results=all_features,
        domain=domain_type,
        min_confidence=min_confidence,
        min_value_score=min_value_score,
        max_results=top,
    )

    formatted = format_output(
        data=result,
        fmt=fmt,
        output_type="ranking",
    )
    out_console = get_output_console()
    out_console.print(formatted)
    await store.close()


def _resolve_domain(domain: str) -> DomainType | None:
    """Resolve a domain string to a DomainType, returning None if invalid."""
    try:
        return DomainType(domain)
    except ValueError:
        return None
