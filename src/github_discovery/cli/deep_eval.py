"""CLI command: ghdisc deep-eval — deep LLM assessment of top candidates (Gate 3)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

if TYPE_CHECKING:
    from github_discovery.config import Settings
    from github_discovery.discovery.pool import PoolManager
    from github_discovery.models.candidate import RepoCandidate
    from github_discovery.models.screening import ScreeningResult
    from github_discovery.scoring.feature_store import FeatureStore


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


async def _resolve_candidates_async(
    pool_id: str | None,
    repo_urls: list[str] | None,
    max_repos: int,
) -> tuple[list[RepoCandidate], PoolManager]:
    """Resolve candidates from pool ID or repo URLs."""
    from github_discovery.cli.utils import exit_with_error
    from github_discovery.discovery.pool import PoolManager

    pool_mgr = PoolManager()
    candidates: list[RepoCandidate] = []

    if pool_id:
        pool = await pool_mgr.get_pool(pool_id)
        if pool is None:
            exit_with_error(f"Pool not found: {pool_id}")
            return [], pool_mgr  # unreachable
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

    return candidates[:max_repos], pool_mgr


async def _build_screening_lookup(
    candidates: list[RepoCandidate],
    real_settings: Settings,
    store: FeatureStore,
) -> dict[str, ScreeningResult]:
    """Build screening results lookup from FeatureStore for hard gate enforcement."""
    from github_discovery.models.screening import (
        MetadataScreenResult,
        ScreeningResult,
        StaticScreenResult,
    )

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

    return screening_lookup


async def _run_assessments(
    candidates: list[RepoCandidate],
    screening_lookup: dict[str, ScreeningResult],
    real_settings: Settings,
    store: FeatureStore,
) -> list[dict[str, object]]:
    """Run deep assessment on each candidate with screening gate enforcement.

    After each assessment, re-scores the candidate via ScoringEngine with the
    Gate 3 result and persists the updated ScoreResult to FeatureStore. This
    ensures subsequent ``rank`` and ``explain`` commands use Gate 3 data.
    """
    from github_discovery.assessment.orchestrator import AssessmentOrchestrator
    from github_discovery.scoring.engine import ScoringEngine

    orch = AssessmentOrchestrator(real_settings)
    scoring_engine = ScoringEngine(settings=real_settings.scoring, store=store)
    display_results: list[dict[str, object]] = []

    for candidate in candidates:
        screening = screening_lookup.get(candidate.full_name)
        try:
            result = await orch.quick_assess(candidate, screening=screening)

            # Re-score with Gate 3 assessment and persist to FeatureStore
            score_result = scoring_engine.score(
                candidate=candidate,
                screening=screening,
                assessment=result,
            )
            await store.put(score_result)

            display_results.append(
                {
                    "full_name": result.full_name,
                    "overall_score": result.overall_quality,
                    "confidence": result.overall_confidence,
                    "passed": result.gate3_pass,
                    "gate3_persisted": True,
                    "dimension_scores": [
                        {"dimension": ds.dimension.value, "score": ds.value}
                        for ds in result.dimensions.values()
                    ],
                    "tokens_used": (result.token_usage.total_tokens if result.token_usage else 0),
                }
            )
        except Exception as e:
            display_results.append(
                {
                    "full_name": candidate.full_name,
                    "error": str(e),
                    "passed": False,
                    "gate3_persisted": False,
                }
            )

    return display_results


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
    from github_discovery.config import Settings
    from github_discovery.scoring.feature_store import FeatureStore

    real_settings = settings if isinstance(settings, Settings) else Settings()

    candidates, pool_mgr = await _resolve_candidates_async(
        pool_id,
        repo_urls,
        max_repos,
    )

    if not candidates:
        exit_with_error("No candidates to assess.")
        return  # unreachable

    store = FeatureStore(db_path=".ghdisc/features.db")
    try:
        await store.initialize()

        screening_lookup = await _build_screening_lookup(
            candidates,
            real_settings,
            store,
        )
        display_results = await _run_assessments(
            candidates,
            screening_lookup,
            real_settings,
            store,
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
        await store.close()
