"""CLI command: ghdisc explain — explainability report for a scored repository."""

from __future__ import annotations

from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    """Register the explain command on the main app."""

    @app.command(
        name="explain",
        help="Explain why a repository scored the way it did.",
        rich_help_panel="Pipeline",
    )
    def explain(
        repo_url: Annotated[
            str,
            typer.Argument(help="GitHub repository URL (e.g., https://github.com/owner/repo)"),
        ],
        detail_level: Annotated[
            str,
            typer.Option(
                "--detail",
                "-d",
                help="Detail level: summary or full",
            ),
        ] = "summary",
        output: Annotated[
            str | None,
            typer.Option("--output", "-o", help="Output format: json|table|markdown|yaml"),
        ] = None,
    ) -> None:
        """Generate an explainability report for a scored repository.

        Shows strengths, weaknesses, recommendations, hidden gem indicator,
        and star context. Requires the repo to have been scored (run
        discover → screen → rank first).

        Blueprint §3 (Explainability): every score must be explainable per feature.
        """
        from github_discovery.cli.utils import (
            get_settings,
            resolve_output_format,
            run_async,
        )

        settings = get_settings()
        fmt = resolve_output_format(output)

        run_async(
            _explain(
                settings,
                repo_url,
                detail_level,
                fmt,
            ),
        )


async def _explain(
    settings: object,
    repo_url: str,
    detail_level: str,
    fmt: str,
) -> None:
    """Generate explainability report for a repo."""
    from github_discovery.cli.formatters import format_output
    from github_discovery.cli.utils import exit_with_error, get_output_console
    from github_discovery.scoring.explainability import ExplainabilityGenerator
    from github_discovery.scoring.feature_store import FeatureStore

    # Parse repo URL → full_name
    parts = repo_url.rstrip("/").split("/")
    if len(parts) < 2:
        exit_with_error(f"Invalid repository URL: {repo_url}")
        return  # unreachable
    full_name = f"{parts[-2]}/{parts[-1]}"

    store = FeatureStore(db_path=".ghdisc/features.db")
    try:
        await store.initialize()

        score_result = await store.get_latest(full_name)
        if score_result is None:
            exit_with_error(
                f"No scoring result found for {full_name}. "
                "Run the scoring pipeline first: discover → screen → rank.",
            )
            return  # unreachable

        generator = ExplainabilityGenerator()
        report = generator.explain(
            score_result,
            detail_level=detail_level,
        )

        # Build output data
        data: dict[str, object] = {
            "repo": report.full_name,
            "domain": report.domain.value,
            "overall_quality": round(report.overall_quality, 3),
            "value_score": round(report.value_score, 3),
            "confidence": round(report.confidence, 3),
            "stars": score_result.stars,
            "hidden_gem": report.hidden_gem_indicator,
            "hidden_gem_reason": report.hidden_gem_reason,
            "star_context": report.star_context,
            "strengths": report.strengths[:5],
            "weaknesses": report.weaknesses[:5],
        }

        if detail_level == "full":
            data["recommendations"] = report.recommendations
            data["dimension_breakdown"] = report.dimension_breakdown
            data["compared_to_star_baseline"] = report.compared_to_star_baseline
            data["gate1_total"] = score_result.gate1_total
            data["gate2_total"] = score_result.gate2_total
            data["gate3_available"] = score_result.gate3_available

        formatted = format_output(
            data=data,
            fmt=fmt,
            output_type="explainability",
        )
        out_console = get_output_console()
        out_console.print(formatted)

    except SystemExit:
        raise
    except Exception as e:
        exit_with_error(f"Explainability report failed: {e}")
    finally:
        await store.close()
