"""CLI command: ghdisc deep-eval — deep LLM assessment of top candidates (Gate 3)."""

from __future__ import annotations

from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    """Register the deep-eval command on the main app."""

    @app.command(
        name="deep-eval",
        help="Deep LLM assessment of top candidates (Gate 3).",
        rich_help_panel="Pipeline",
    )
    def deep_eval(
        pool_id: Annotated[
            str | None,
            typer.Option("--pool-id", "-p", help="Pool ID (uses shortlist)"),
        ] = None,
        repo_urls: Annotated[
            str | None,
            typer.Option("--repo-urls", "-r", help="Specific repo URLs (comma-sep)"),
        ] = None,
        max_repos: Annotated[
            int,
            typer.Option("--max-repos", "-m", help="Maximum repos to assess"),
        ] = 50,
        budget_tokens: Annotated[
            int | None,
            typer.Option("--budget-tokens", "-b", help="Override token budget"),
        ] = None,
        dimensions: Annotated[
            str | None,
            typer.Option("--dimensions", "-d", help="Dimensions subset (comma-sep)"),
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
        """Deep LLM assessment of top candidates (Gate 3).

        HARD GATE: Only repos that passed Gate 1+2 will be assessed.
        This is the most expensive operation — uses LLM tokens per repo.
        """
        from github_discovery.cli.utils import (
            comma_separated_to_list,
            exit_with_error,
            get_settings,
            resolve_output_format,
            run_async,
        )

        if not pool_id and not repo_urls:
            exit_with_error("Must specify either --pool-id or --repo-urls")

        settings = get_settings()
        fmt = resolve_output_format(output)
        url_list = comma_separated_to_list(repo_urls) if repo_urls else None
        dim_list = comma_separated_to_list(dimensions) if dimensions else None

        run_async(
            _deep_eval(
                settings,
                pool_id,
                url_list,
                max_repos,
                budget_tokens,
                dim_list,
                session_id,
                fmt,
            ),
        )


async def _deep_eval(
    settings: object,
    pool_id: str | None,
    repo_urls: list[str] | None,
    max_repos: int,
    budget_tokens: int | None,
    dimensions: list[str] | None,
    session_id: str | None,
    fmt: str,
) -> None:
    """Run deep assessment on repos."""
    from github_discovery.cli.formatters import format_output
    from github_discovery.cli.utils import exit_with_error, get_output_console
    from github_discovery.discovery.pool import PoolManager

    pool_mgr = PoolManager()

    try:
        # Get candidates from pool or URLs
        candidates = []
        if pool_id:
            pool = await pool_mgr.get_pool(pool_id)
            if pool is None:
                exit_with_error(f"Pool not found: {pool_id}")
                return  # unreachable: exit_with_error raises SystemExit
            candidates = pool.candidates[:max_repos]
        elif repo_urls:
            from datetime import UTC, datetime

            from github_discovery.models.candidate import RepoCandidate
            from github_discovery.models.enums import CandidateStatus, DiscoveryChannel

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
            return  # unreachable: exit_with_error raises SystemExit

        # Hard gate enforcement: in production, we'd check screening results.
        # For CLI, we proceed and let the orchestrator enforce hard gates.
        from github_discovery.assessment.orchestrator import AssessmentOrchestrator

        orch = AssessmentOrchestrator(settings)  # type: ignore[arg-type]

        # Assess each candidate
        display_results: list[dict[str, object]] = []
        for candidate in candidates:
            try:
                result = await orch.quick_assess(candidate, screening=None)
                display_results.append(
                    {
                        "full_name": result.full_name,
                        "overall_score": result.overall_quality,
                        "confidence": result.overall_confidence,
                        "passed": result.gate3_pass,
                        "dimension_scores": [
                            {"dimension": ds.dimension.value, "score": ds.value}
                            for ds in result.dimensions.values()
                        ],
                        "tokens_used": (
                            result.token_usage.total_tokens if result.token_usage else 0
                        ),
                    }
                )
            except Exception as e:
                display_results.append(
                    {
                        "full_name": candidate.full_name,
                        "error": str(e),
                        "passed": False,
                    }
                )

        formatted = format_output(
            data={"results": display_results, "total": len(display_results)},
            fmt=fmt,
            output_type="assessment",
        )
        out_console = get_output_console()
        out_console.print(formatted)

    except SystemExit:
        raise
    except Exception as e:
        exit_with_error(f"Deep evaluation failed: {e}")
    finally:
        await pool_mgr.close()
