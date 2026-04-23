"""Ranking API routes — scoring, ranking, and explainability endpoints.

Provides synchronous endpoints for ranked results, per-repo scoring
details, and explainability reports. These call Ranker and FeatureStore
directly (no job queue).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from github_discovery.api.deps import get_ranker, get_scoring_engine
from github_discovery.models.enums import DomainType
from github_discovery.scoring.explainability import ExplainabilityGenerator

if TYPE_CHECKING:
    from github_discovery.scoring.engine import ScoringEngine
    from github_discovery.scoring.feature_store import FeatureStore
    from github_discovery.scoring.ranker import Ranker

router = APIRouter(tags=["ranking"])


def _get_feature_store(scoring_engine: ScoringEngine) -> FeatureStore | None:
    """Extract the FeatureStore from ScoringEngine, if configured."""
    return scoring_engine.feature_store


@router.get("/rank")
async def get_ranked_results(
    domain: DomainType | None = Query(default=None, description="Filter by domain"),  # noqa: B008
    min_confidence: float = Query(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold",
    ),
    min_value_score: float = Query(
        default=0.0,
        ge=0.0,
        description="Minimum value score (anti-star bias)",
    ),
    max_results: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum results to return",
    ),
    session_id: str | None = Query(default=None, description="Session filter"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    ranker: Ranker = Depends(get_ranker),  # noqa: B008
    scoring_engine: ScoringEngine = Depends(get_scoring_engine),  # noqa: B008
) -> dict[str, object]:
    """Get ranked repository results with anti-star bias.

    Returns repositories ranked by value score (quality / log10(stars + 10)).
    Loads scored results from the feature store and ranks them within
    the specified domain.
    """
    feature_store = _get_feature_store(scoring_engine)

    if feature_store is None:
        return {
            "domain": (domain or DomainType.OTHER).value,
            "ranked_repos": [],
            "pagination": {
                "total_count": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0,
                "has_next": False,
                "has_prev": False,
            },
            "message": "Feature store not configured",
        }
    assert feature_store is not None  # noqa: S101 - type narrowing after early return

    # Determine domain to query
    resolved_domain = domain or DomainType.OTHER

    # Load scored results from feature store
    score_results = await feature_store.get_by_domain(resolved_domain)

    # Rank using the Ranker
    ranking = ranker.rank(
        score_results,
        resolved_domain,
        min_confidence=min_confidence,
        min_value_score=min_value_score,
        max_results=max_results,
    )

    # Paginate
    total = len(ranking.ranked_repos)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = ranking.ranked_repos[start:end]
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    ranked_data = [
        {
            "rank": r.rank,
            "repo": r.full_name,
            "quality_score": round(r.quality_score, 3),
            "value_score": round(r.value_score, 3),
            "stars": r.stars,
            "confidence": round(r.score_result.confidence, 3),
        }
        for r in page_items
    ]

    return {
        "domain": resolved_domain.value,
        "min_confidence": min_confidence,
        "min_value_score": min_value_score,
        "max_results": max_results,
        "session_id": session_id,
        "page": page,
        "page_size": page_size,
        "ranked_repos": ranked_data,
        "hidden_gems": [
            {
                "repo": r.full_name,
                "quality_score": round(r.quality_score, 3),
                "value_score": round(r.value_score, 3),
                "stars": r.stars,
            }
            for r in ranking.hidden_gems[:5]
        ],
        "pagination": {
            "total_count": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }


@router.get("/rank/{repo:path}")
async def get_repo_detail(
    repo: str,
    scoring_engine: ScoringEngine = Depends(get_scoring_engine),  # noqa: B008
) -> dict[str, object]:
    """Get detailed scoring for a single repository.

    Path parameter captures `owner/repo` format. Returns the latest
    score result from the feature store.
    """
    feature_store = _get_feature_store(scoring_engine)
    if feature_store is None:
        return {
            "repo": repo,
            "scoring": None,
            "message": "Feature store not configured",
        }
    assert feature_store is not None  # noqa: S101 - type narrowing after early return
    score_result = await feature_store.get_latest(repo)

    if score_result is None:
        return {
            "repo": repo,
            "scoring": None,
            "message": (
                f"No scoring result found for {repo}. "
                "Run the full pipeline (discover → screen → assess → score) first."
            ),
        }

    return {
        "repo": repo,
        "scoring": {
            "quality_score": round(score_result.quality_score, 3),
            "value_score": round(score_result.value_score, 3),
            "confidence": round(score_result.confidence, 3),
            "stars": score_result.stars,
            "domain": score_result.domain.value,
            "gate1_total": round(score_result.gate1_total, 3),
            "gate2_total": round(score_result.gate2_total, 3),
            "gate3_available": score_result.gate3_available,
            "dimension_scores": {
                dim.value: round(val, 3) for dim, val in score_result.dimension_scores.items()
            },
            "scored_at": score_result.scored_at.isoformat(),
        },
    }


@router.get("/explain/{repo:path}")
async def explain_repo(
    repo: str,
    detail_level: str = Query(default="summary", description="Detail level: summary or full"),
    scoring_engine: ScoringEngine = Depends(get_scoring_engine),  # noqa: B008
) -> dict[str, object]:
    """Generate an explainability report for a repository.

    Path parameter captures `owner/repo` format. The report explains
    why a repo scored high or low across all dimensions.
    """
    feature_store = _get_feature_store(scoring_engine)
    if feature_store is None:
        return {
            "repo": repo,
            "detail_level": detail_level,
            "report": None,
            "message": "Feature store not configured",
        }
    assert feature_store is not None  # noqa: S101 - type narrowing after early return
    score_result = await feature_store.get_latest(repo)

    if score_result is None:
        return {
            "repo": repo,
            "detail_level": detail_level,
            "report": None,
            "message": (
                f"No scoring result found for {repo}. "
                "Run the full pipeline (discover → screen → assess → score) first."
            ),
        }

    generator = ExplainabilityGenerator()
    report = generator.explain(score_result, detail_level=detail_level)

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

    return {
        "repo": repo,
        "detail_level": detail_level,
        "report": data,
    }
