"""CLI command: ghdisc rank — rank repositories using star-neutral scoring.

Supports two modes:

1. **FeatureStore mode** (default): reads previously scored repos from
   the persistent FeatureStore. Requires ``discover → screen → rank``.
2. **Pool mode** (``--pool-id``): scores and ranks candidates from a pool
   on-the-fly. Useful for quick one-shot ``discover → rank`` workflows.
"""

from __future__ import annotations

from typing import Annotated

import typer

from github_discovery.models.enums import DomainType


def register(app: typer.Typer) -> None:
    """Register the rank command on the main app."""

    @app.command(
        name="rank",
        help="Rank repositories using star-neutral quality scoring.",
        rich_help_panel="Pipeline",
    )
    def rank(
        domain: Annotated[
            str | None,
            typer.Option(
                "--domain",
                "-d",
                help="Domain for ranking (e.g., library, cli, ml_lib). "
                "Auto-detected per repo if not specified.",
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
            typer.Option("--min-value-score", help="Minimum quality score threshold"),
        ] = 0.0,
        pool_id: Annotated[
            str | None,
            typer.Option(
                "--pool-id",
                "-p",
                help="Pool ID to rank directly (scores on-the-fly from pool data).",
            ),
        ] = None,
        session_id: Annotated[
            str | None,
            typer.Option("--session-id", "-s", help="Session ID for workflow continuity"),
        ] = None,
        output: Annotated[
            str | None,
            typer.Option("--output", "-o", help="Output format: json|table|markdown|yaml"),
        ] = None,
    ) -> None:
        """Rank repositories using star-neutral quality scoring."""
        from github_discovery.cli.utils import (
            get_settings,
            resolve_output_format,
            run_async,
        )

        settings = get_settings()
        fmt = resolve_output_format(output)

        domain_type = _resolve_domain(domain) if domain is not None else None

        run_async(
            _rank_repos(
                settings,
                domain_type,
                top,
                min_confidence,
                min_value_score,
                pool_id,
                session_id,
                fmt,
            ),
        )


async def _rank_repos(
    settings: object,
    domain: DomainType | None,
    top: int,
    min_confidence: float,
    min_value_score: float,
    pool_id: str | None,
    session_id: str | None,
    fmt: str,
) -> None:
    """Run ranking — either from FeatureStore or from pool on-the-fly."""
    from github_discovery.config import Settings
    from github_discovery.scoring.ranker import Ranker

    _ = session_id  # kept for future use

    real_settings = settings if isinstance(settings, Settings) else Settings()
    ranker = Ranker()

    if pool_id is not None:
        # Pool mode: score on-the-fly from pool data
        await _rank_from_pool(
            real_settings,
            ranker,
            domain,
            top,
            min_confidence,
            min_value_score,
            pool_id,
            fmt,
        )
    else:
        # FeatureStore mode: read pre-computed scores
        await _rank_from_store(
            ranker,
            domain,
            top,
            min_confidence,
            min_value_score,
            fmt,
        )


async def _rank_from_store(
    ranker: object,
    domain: DomainType | None,
    top: int,
    min_confidence: float,
    min_value_score: float,
    fmt: str,
) -> None:
    """Rank from FeatureStore (requires previous screen command)."""
    from github_discovery.cli.utils import exit_with_error
    from github_discovery.scoring.feature_store import FeatureStore
    from github_discovery.scoring.ranker import Ranker

    _ranker = ranker if isinstance(ranker, Ranker) else Ranker()

    if domain is None:
        exit_with_error(
            "--domain is required when using FeatureStore mode. "
            "Alternatively, use --pool-id to rank directly from a pool.",
        )
        return  # unreachable

    store = FeatureStore(db_path=".ghdisc/features.db")
    try:
        await store.initialize()
        all_features = await store.get_by_domain(domain)
    except Exception as e:
        exit_with_error(
            f"Failed to load scored repos for domain '{domain.value}': {e}. "
            "Run discover + screen first, or use --pool-id.",
        )
        return  # unreachable

    if not all_features:
        exit_with_error(
            f"No scored repos found for domain '{domain.value}'. "
            "Run discover + screen first, or use --pool-id to rank a pool directly.",
        )
        return  # unreachable

    result = _ranker.rank(
        results=all_features,
        domain=domain,
        min_confidence=min_confidence,
        min_value_score=min_value_score,
        max_results=top,
    )

    _print_ranking(result, fmt)
    await store.close()


async def _rank_from_pool(
    settings: object,
    ranker: object,
    domain: DomainType | None,
    top: int,
    min_confidence: float,
    min_value_score: float,
    pool_id: str,
    fmt: str,
) -> None:
    """Score and rank candidates from a pool on-the-fly.

    Reads candidates from PoolManager, computes scores via ScoringEngine,
    persists to FeatureStore, and ranks.
    """
    import structlog

    from github_discovery.cli.utils import exit_with_error
    from github_discovery.config import Settings
    from github_discovery.discovery.pool import PoolManager
    from github_discovery.scoring.engine import ScoringEngine
    from github_discovery.scoring.feature_store import FeatureStore
    from github_discovery.scoring.ranker import Ranker

    logger = structlog.get_logger("github_discovery.cli.rank")
    real_settings = settings if isinstance(settings, Settings) else Settings()
    _ranker = ranker if isinstance(ranker, Ranker) else Ranker()

    pool_mgr = PoolManager()
    store = FeatureStore(db_path=".ghdisc/features.db")
    scoring_engine = ScoringEngine(settings=real_settings.scoring, store=store)

    try:
        await store.initialize()

        pool = await pool_mgr.get_pool(pool_id)
        if pool is None:
            exit_with_error(f"Pool not found: {pool_id}")
            return  # unreachable

        if not pool.candidates:
            exit_with_error(f"Pool {pool_id} has no candidates.")
            return  # unreachable

        # Score each candidate — prefer cached FeatureStore results,
        # then try reconstructing screening from FeatureStore gate scores,
        # finally fall back to discovery-metadata-only scoring.
        from github_discovery.models.screening import (
            MetadataScreenResult,
            ScreeningResult,
            StaticScreenResult,
        )

        results = []
        for candidate in pool.candidates:
            # Check if already scored in FeatureStore (by commit_sha)
            if candidate.commit_sha:
                cached = await store.get(candidate.full_name, candidate.commit_sha)
                if cached is not None:
                    results.append(cached)
                    continue

            # Try to get latest score (may include Gate 3 data from deep-eval)
            latest_score = await store.get_latest(candidate.full_name)
            if latest_score is not None and latest_score.quality_score > 0:
                # Already scored (Gate 1+2 or Gate 3) — use cached result directly
                results.append(latest_score)
                continue

            # Reconstruct screening from FeatureStore gate scores
            screening: ScreeningResult | None = None
            if latest_score is not None:
                gate1_pass = latest_score.gate1_total >= real_settings.screening.min_gate1_score
                gate2_pass = latest_score.gate2_total >= real_settings.screening.min_gate2_score
                screening = ScreeningResult(
                    full_name=candidate.full_name,
                    commit_sha=latest_score.commit_sha,
                    gate1=MetadataScreenResult(
                        full_name=candidate.full_name,
                        gate1_total=latest_score.gate1_total,
                        gate1_pass=gate1_pass,
                        threshold_used=real_settings.screening.min_gate1_score,
                    ),
                    gate2=StaticScreenResult(
                        full_name=candidate.full_name,
                        gate2_total=latest_score.gate2_total,
                        gate2_pass=gate2_pass,
                        threshold_used=real_settings.screening.min_gate2_score,
                    ),
                )

            score_result = scoring_engine.score(
                candidate=candidate,
                screening=screening,
                assessment=None,
            )
            await store.put(score_result)
            results.append(score_result)

        logger.info(
            "rank_pool_scored",
            pool_id=pool_id,
            candidates=len(pool.candidates),
            scored=len(results),
        )

        # Determine domain
        effective_domain = domain
        if effective_domain is None:
            # Auto-detect: use the most common domain in the pool
            domain_counts: dict[str, int] = {}
            for r in results:
                key = r.domain.value
                domain_counts[key] = domain_counts.get(key, 0) + 1
            if domain_counts:
                best_domain_str = max(domain_counts, key=lambda k: domain_counts[k])
                effective_domain = DomainType(best_domain_str)
                logger.info(
                    "rank_domain_auto_detected",
                    domain=effective_domain.value,
                    count=domain_counts[best_domain_str],
                    total=len(results),
                )

        if effective_domain is None:
            exit_with_error("Could not auto-detect domain. Use --domain to specify.")
            return  # unreachable

        # Filter to the target domain
        domain_results = [r for r in results if r.domain == effective_domain]
        if not domain_results:
            # Fall back to all results if domain filter is too strict
            logger.info("rank_domain_no_match", domain=effective_domain.value, fallback="all")
            domain_results = results

        ranking = _ranker.rank(
            results=domain_results,
            domain=effective_domain,
            min_confidence=min_confidence,
            min_value_score=min_value_score,
            max_results=top,
        )

        _print_ranking(ranking, fmt)

    except SystemExit:
        raise
    except Exception as e:
        exit_with_error(f"Ranking failed: {e}")
    finally:
        await store.close()
        await pool_mgr.close()


def _print_ranking(result: object, fmt: str) -> None:
    """Format and print ranking result."""
    from github_discovery.cli.formatters import format_output
    from github_discovery.cli.utils import get_output_console
    from github_discovery.scoring.types import RankingResult

    ranking = result if isinstance(result, RankingResult) else None
    if ranking is None:
        return

    display_data = {
        "domain": ranking.domain.value,
        "total_candidates": ranking.total_candidates,
        "ranked_repos": [
            {
                "rank": i + 1,
                "full_name": repo.full_name,
                "quality_score": round(repo.quality_score, 4),
                "value_score": round(repo.value_score, 4),
                "confidence": round(repo.score_result.confidence, 4),
                "stars": repo.stars,
                "corroboration_level": repo.score_result.corroboration_level,
            }
            for i, repo in enumerate(ranking.ranked_repos)
        ],
        "hidden_gems": [
            {
                "full_name": repo.full_name,
                "quality_score": round(repo.quality_score, 4),
                "stars": repo.stars,
                "corroboration_level": repo.score_result.corroboration_level,
            }
            for repo in ranking.hidden_gems
        ],
    }

    formatted = format_output(
        data=display_data,
        fmt=fmt,
        output_type="ranking",
    )
    out_console = get_output_console()
    out_console.print(formatted)


def _resolve_domain(domain: str) -> DomainType | None:
    """Resolve a domain string to a DomainType, returning None if invalid."""
    try:
        return DomainType(domain)
    except ValueError:
        return None
