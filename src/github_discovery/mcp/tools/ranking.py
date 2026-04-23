"""MCP ranking tools — rank_repos, explain_repo, compare_repos.

Tools for Layer D: scoring, ranking, and explainability.
Anti-star bias: stars are context only, never primary ranking signal.
Value Score = quality_score / log10(stars + 10) identifies hidden gems.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import structlog
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from github_discovery.mcp.config import should_register_tool
from github_discovery.mcp.output_format import format_tool_result
from github_discovery.mcp.server import AppContext, get_app_context
from github_discovery.models.enums import DomainType, ScoreDimension
from github_discovery.models.scoring import ScoreResult
from github_discovery.scoring.explainability import ExplainabilityGenerator
from github_discovery.scoring.feature_store import FeatureStore
from github_discovery.scoring.ranker import Ranker

if TYPE_CHECKING:
    from github_discovery.config import Settings

logger = structlog.get_logger("github_discovery.mcp.tools.ranking")

_MIN_COMPARE_REPOS = 2
_MAX_COMPARE_REPOS = 5
_MIN_OWNER_REPO_PARTS = 2


def _require_ctx(
    ctx: Context[ServerSession, AppContext] | None,
) -> Context[ServerSession, AppContext]:
    """Assert ctx is provided — FastMCP always passes it."""
    if ctx is None:
        msg = "Context is required but was not provided by MCP framework"
        raise RuntimeError(msg)
    return ctx


def register_ranking_tools(mcp: FastMCP, settings: Settings) -> None:
    """Register ranking MCP tools."""
    if should_register_tool("rank_repos", settings):

        @mcp.tool()
        async def rank_repos(
            domain: str = "other",
            min_confidence: float | None = None,
            min_value_score: float = 0.0,
            max_results: int | None = None,
            session_id: str | None = None,
            ctx: Context[ServerSession, AppContext] | None = None,
        ) -> dict[str, object]:
            """Rank repositories by anti-star bias value score.

            Ranks repos within a domain by value_score descending.
            Value Score = quality_score / log10(stars + 10) identifies
            hidden gems: high quality, low visibility.

            Args:
                domain: Domain type for intra-domain ranking (default: "other")
                min_confidence: Minimum confidence to include (default: from config)
                min_value_score: Minimum value_score to include (default: 0.0)
                max_results: Limit number of results (default: all)
                session_id: Optional session ID for workflow continuity
                ctx: MCP request context (injected by FastMCP)
            """
            real_ctx = _require_ctx(ctx)
            app_ctx = get_app_context(real_ctx)

            resolved_domain = DomainType(domain)

            # Load scored results from feature store
            score_results = await _load_scores_for_domain(
                app_ctx,
                resolved_domain,
            )

            if not score_results:
                return format_tool_result(
                    success=False,
                    error_message=(
                        f"No scored results found for domain '{domain}'. "
                        "Run screen_candidates and scoring first."
                    ),
                )

            # Rank using the Ranker
            ranker = Ranker(app_ctx.settings.scoring)
            ranking = ranker.rank(
                score_results,
                resolved_domain,
                min_confidence=min_confidence,
                min_value_score=min_value_score,
                max_results=max_results,
            )

            return format_tool_result(
                summary=(
                    f"Ranked {len(ranking.ranked_repos)}/"
                    f"{ranking.total_candidates} repos in "
                    f"{resolved_domain.value} domain, "
                    f"{len(ranking.hidden_gems)} hidden gems found"
                ),
                data={
                    "domain": resolved_domain.value,
                    "total_candidates": ranking.total_candidates,
                    "total_ranked": len(ranking.ranked_repos),
                    "hidden_gems_count": len(ranking.hidden_gems),
                    "top_10": [
                        {
                            "rank": r.rank,
                            "repo": r.full_name,
                            "quality_score": round(r.quality_score, 3),
                            "value_score": round(r.value_score, 3),
                            "stars": r.stars,
                        }
                        for r in ranking.ranked_repos[:10]
                    ],
                    "hidden_gems": [
                        {
                            "repo": r.full_name,
                            "quality_score": round(r.quality_score, 3),
                            "value_score": round(r.value_score, 3),
                            "stars": r.stars,
                        }
                        for r in ranking.hidden_gems[:5]
                    ],
                },
                references={
                    "explain": "explain_repo(repo_url='...')",
                    "compare": "compare_repos(repo_urls=['...', '...'])",
                },
                session_id=session_id,
            )

    if should_register_tool("explain_repo", settings):

        @mcp.tool()
        async def explain_repo(
            repo_url: str,
            detail_level: str = "summary",
            ctx: Context[ServerSession, AppContext] | None = None,
        ) -> dict[str, object]:
            """Explain why a repository scored the way it did.

            Generates an explainability report with strengths, weaknesses,
            recommendations, and hidden gem analysis.

            Args:
                repo_url: GitHub repository URL
                detail_level: "summary" (concise) or "full" (complete breakdown)
                ctx: MCP request context (injected by FastMCP)
            """
            real_ctx = _require_ctx(ctx)
            app_ctx = get_app_context(real_ctx)

            full_name = _parse_repo_url(repo_url)
            if not full_name:
                return format_tool_result(
                    success=False,
                    error_message=f"Invalid repository URL: {repo_url}",
                )

            # Try to load score result from feature store
            score_result = await _load_score_for_repo(app_ctx, full_name)

            if not score_result:
                return format_tool_result(
                    success=False,
                    error_message=(
                        f"No scoring result found for {full_name}. Run the scoring pipeline first."
                    ),
                )

            # Generate explainability report
            generator = ExplainabilityGenerator()
            report = generator.explain(
                score_result,
                detail_level=detail_level,
            )

            data: dict[str, object] = {
                "repo": report.full_name,
                "domain": report.domain.value,
                "overall_quality": round(report.overall_quality, 3),
                "value_score": round(report.value_score, 3),
                "hidden_gem": report.hidden_gem_indicator,
                "hidden_gem_reason": report.hidden_gem_reason,
                "strengths": report.strengths[:5],
                "weaknesses": report.weaknesses[:5],
                "star_context": report.star_context,
                "confidence": round(report.confidence, 3),
            }

            if detail_level == "full":
                data["recommendations"] = report.recommendations
                data["dimension_breakdown"] = report.dimension_breakdown
                data["compared_to_baseline"] = report.compared_to_star_baseline

            return format_tool_result(
                summary=(
                    f"{full_name}: quality={report.overall_quality:.2f}, "
                    f"value={report.value_score:.2f}, "
                    f"{'HIDDEN GEM' if report.hidden_gem_indicator else 'standard'}"
                ),
                data=data,
            )

    if should_register_tool("compare_repos", settings):

        @mcp.tool()
        async def compare_repos(
            repo_urls: list[str],
            ctx: Context[ServerSession, AppContext] | None = None,
        ) -> dict[str, object]:
            """Compare multiple repositories side-by-side.

            Generates comparison matrix for decision-making between
            alternatives. Shows quality, value score, strengths, and
            weaknesses for each repo.

            Args:
                repo_urls: List of GitHub repository URLs to compare (2-5)
                ctx: MCP request context (injected by FastMCP)
            """
            real_ctx = _require_ctx(ctx)
            app_ctx = get_app_context(real_ctx)

            if len(repo_urls) < _MIN_COMPARE_REPOS:
                return format_tool_result(
                    success=False,
                    error_message="Provide at least 2 repository URLs to compare",
                )
            if len(repo_urls) > _MAX_COMPARE_REPOS:
                return format_tool_result(
                    success=False,
                    error_message="Maximum 5 repositories can be compared at once",
                )

            # Load score results and generate reports
            generator = ExplainabilityGenerator()
            comparisons: list[dict[str, object]] = []

            for url in repo_urls:
                full_name = _parse_repo_url(url)
                if not full_name:
                    comparisons.append(
                        {
                            "repo": url,
                            "error": "Invalid URL",
                        }
                    )
                    continue

                score_result = await _load_score_for_repo(
                    app_ctx,
                    full_name,
                )
                if not score_result:
                    comparisons.append(
                        {
                            "repo": full_name,
                            "error": "No scoring result found",
                        }
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
                    }
                )

            # Determine winner
            scored = [c for c in comparisons if "quality_score" in c]
            winner = ""
            if scored:
                best = max(
                    scored,
                    key=lambda c: cast(float, c.get("value_score", 0.0)),
                )
                winner = str(best.get("repo", ""))

            return format_tool_result(
                summary=(f"Compared {len(repo_urls)} repos: best value_score is {winner}"),
                data={
                    "comparison": comparisons,
                    "recommendation": (
                        f"{winner} has the highest value score"
                        if winner
                        else "No repos could be compared"
                    ),
                },
            )


async def _load_scores_for_domain(
    app_ctx: AppContext,
    domain: DomainType,
) -> list[ScoreResult]:
    """Load scored results for a domain from the feature store.

    Queries the feature store SQLite database for all scores in a domain.
    """
    import json

    import aiosqlite

    # Use default in-memory store path convention
    store_path = ".ghdisc/features.db"

    results: list[ScoreResult] = []
    try:
        db = await aiosqlite.connect(store_path)
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM score_features WHERE domain = ?",
            (domain.value,),
        )
        rows = await cursor.fetchall()
        await db.close()

        for row in rows:
            dim_raw = json.loads(row["dimension_scores"])
            dimension_scores: dict[ScoreDimension, float] = {}
            for k, v in dim_raw.items():
                from contextlib import suppress

                with suppress(ValueError):
                    dimension_scores[ScoreDimension(k)] = v

            from datetime import datetime

            results.append(
                ScoreResult(
                    full_name=row["full_name"],
                    commit_sha=row["commit_sha"],
                    domain=DomainType(row["domain"]),
                    quality_score=row["quality_score"],
                    dimension_scores=dimension_scores,
                    confidence=row["confidence"],
                    stars=row["stars"],
                    gate1_total=row["gate1_total"],
                    gate2_total=row["gate2_total"],
                    gate3_available=bool(row["gate3_available"]),
                    scored_at=datetime.fromisoformat(row["scored_at"]),
                ),
            )
    except Exception:
        logger.debug("feature_store_not_available_for_domain_query")

    return results


async def _load_score_for_repo(
    app_ctx: AppContext,
    full_name: str,
) -> ScoreResult | None:
    """Load a scored result for a single repo from feature store."""
    store = FeatureStore()
    try:
        await store.initialize()
        # Try with empty commit_sha first (may not find without SHA)
        # Fall back to direct DB query
        import json

        import aiosqlite

        db_path = ".ghdisc/features.db"
        try:
            db = await aiosqlite.connect(db_path)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM score_features WHERE full_name = ? ORDER BY scored_at DESC LIMIT 1",
                (full_name,),
            )
            row = await cursor.fetchone()
            await db.close()

            if row is None:
                return None

            dim_raw = json.loads(row["dimension_scores"])
            dimension_scores: dict[ScoreDimension, float] = {}
            for k, v in dim_raw.items():
                from contextlib import suppress

                with suppress(ValueError):
                    dimension_scores[ScoreDimension(k)] = v

            from datetime import datetime

            return ScoreResult(
                full_name=row["full_name"],
                commit_sha=row["commit_sha"],
                domain=DomainType(row["domain"]),
                quality_score=row["quality_score"],
                dimension_scores=dimension_scores,
                confidence=row["confidence"],
                stars=row["stars"],
                gate1_total=row["gate1_total"],
                gate2_total=row["gate2_total"],
                gate3_available=bool(row["gate3_available"]),
                scored_at=datetime.fromisoformat(row["scored_at"]),
            )
        except Exception:
            return None
    finally:
        await store.close()


def _parse_repo_url(url: str) -> str:
    """Parse owner/repo from a GitHub URL."""
    url = url.rstrip("/")
    parts = url.split("/")
    if len(parts) >= _MIN_OWNER_REPO_PARTS:
        return f"{parts[-2]}/{parts[-1]}"
    return ""
