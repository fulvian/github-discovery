"""CLI command: ghdisc compare — side-by-side comparison of scored repositories."""

from __future__ import annotations

from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    """Register the compare command on the main app."""

    @app.command(
        name="compare",
        help="Compare multiple repositories side-by-side.",
        rich_help_panel="Pipeline",
    )
    def compare(
        repo_urls: Annotated[
            str,
            typer.Argument(
                help="Comma-separated GitHub repository URLs (2-5 repos)",
            ),
        ],
        output: Annotated[
            str | None,
            typer.Option("--output", "-o", help="Output format: json|table|markdown|yaml"),
        ] = None,
    ) -> None:
        """Compare multiple repositories side-by-side for adoption decisions.

        Shows quality score, value score, strengths, weaknesses, and hidden
        gem indicator for each repo. Requires repos to have been scored.

        Blueprint §21.3 (Layer D): compare_repos for agent decision-making.
        """
        from github_discovery.cli.utils import (
            comma_separated_to_list,
            get_settings,
            resolve_output_format,
            run_async,
        )

        settings = get_settings()
        fmt = resolve_output_format(output)
        url_list = comma_separated_to_list(repo_urls)

        if len(url_list) < 2:
            typer.echo("Error: Provide at least 2 repository URLs to compare.", err=True)
            raise typer.Exit(code=1)
        if len(url_list) > 5:
            typer.echo("Error: Maximum 5 repositories can be compared at once.", err=True)
            raise typer.Exit(code=1)

        run_async(
            _compare(
                settings,
                url_list,
                fmt,
            ),
        )


async def _compare(
    settings: object,
    repo_urls: list[str],
    fmt: str,
) -> None:
    """Compare multiple repos side-by-side."""
    from github_discovery.cli.formatters import format_output
    from github_discovery.cli.utils import exit_with_error, get_output_console
    from github_discovery.scoring.explainability import ExplainabilityGenerator
    from github_discovery.scoring.feature_store import FeatureStore

    generator = ExplainabilityGenerator()
    store = FeatureStore(db_path=".ghdisc/features.db")

    try:
        await store.initialize()

        comparisons: list[dict[str, object]] = []
        for url in repo_urls:
            parts = url.rstrip("/").split("/")
            if len(parts) < 2:
                comparisons.append({"repo": url, "error": "Invalid URL"})
                continue

            full_name = f"{parts[-2]}/{parts[-1]}"
            score_result = await store.get_latest(full_name)
            if score_result is None:
                comparisons.append(
                    {
                        "repo": full_name,
                        "error": "No scoring result found — run screen first",
                    },
                )
                continue

            report = generator.explain(
                score_result,
                detail_level="summary",
            )
            comparisons.append(
                {
                    "repo": full_name,
                    "domain": report.domain.value,
                    "quality_score": round(report.overall_quality, 3),
                    "value_score": round(report.value_score, 3),
                    "confidence": round(report.confidence, 3),
                    "stars": score_result.stars,
                    "hidden_gem": report.hidden_gem_indicator,
                    "top_strengths": report.strengths[:3],
                    "top_weaknesses": report.weaknesses[:3],
                },
            )

        # Determine winner (highest quality_score — star-neutral)
        valid = [c for c in comparisons if "error" not in c]
        winner = ""
        if valid:
            best = max(valid, key=lambda c: float(c.get("quality_score", 0)))  # type: ignore[arg-type]
            winner = str(best.get("repo", ""))

        formatted = format_output(
            data={
                "comparisons": comparisons,
                "total": len(comparisons),
                "winner": winner,
            },
            fmt=fmt,
            output_type="comparison",
        )
        out_console = get_output_console()
        out_console.print(formatted)

    except SystemExit:
        raise
    except Exception as e:
        exit_with_error(f"Comparison failed: {e}")
    finally:
        await store.close()
