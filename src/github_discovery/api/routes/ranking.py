"""Ranking API routes — scoring, ranking, and explainability endpoints.

Provides synchronous endpoints for ranked results, per-repo scoring
details, and explainability reports. These call ScoringEngine and
Ranker directly (no job queue).

NOTE: Full integration requires completed scoring pipeline data from
previous discovery → screening → assessment jobs. For Phase 6, the
endpoints return stub responses with proper request/response models.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from github_discovery.api.deps import get_job_store, get_scoring_engine
from github_discovery.models.enums import DomainType  # noqa: TC001

if TYPE_CHECKING:
    from github_discovery.scoring.engine import ScoringEngine
    from github_discovery.workers.job_store import JobStore

router = APIRouter(tags=["ranking"])


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
    job_store: JobStore = Depends(get_job_store),  # noqa: B008
    scoring_engine: ScoringEngine = Depends(get_scoring_engine),  # noqa: B008
) -> dict[str, object]:
    """Get ranked repository results with anti-star bias.

    Returns repositories ranked by value score (quality / log10(stars + 10)).
    Full integration requires completed scoring pipeline data from
    previous jobs. Returns a stub response until end-to-end data
    flow is complete.
    """
    return {
        "message": (
            "Full integration requires completed scoring pipeline "
            "(discover → screen → assess → score → rank)"
        ),
        "domain": domain.value if domain else None,
        "min_confidence": min_confidence,
        "min_value_score": min_value_score,
        "max_results": max_results,
        "session_id": session_id,
        "page": page,
        "page_size": page_size,
        "ranked_repos": [],
        "pagination": {
            "total_count": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
            "has_next": False,
            "has_prev": False,
        },
    }


@router.get("/rank/{repo:path}")
async def get_repo_detail(
    repo: str,
    job_store: JobStore = Depends(get_job_store),  # noqa: B008
) -> dict[str, object]:
    """Get detailed scoring for a single repository.

    Path parameter captures `owner/repo` format. Returns stub
    response until scoring pipeline is fully integrated.
    """
    return {
        "message": "Full integration requires completed scoring pipeline",
        "repo": repo,
        "scoring": None,
    }


@router.get("/explain/{repo:path}")
async def explain_repo(
    repo: str,
    detail_level: str = Query(default="summary", description="Detail level: summary or full"),
    scoring_engine: ScoringEngine = Depends(get_scoring_engine),  # noqa: B008
) -> dict[str, object]:
    """Generate an explainability report for a repository.

    Path parameter captures `owner/repo` format. The report explains
    why a repo scored high or low across all dimensions. Returns
    stub response until scoring pipeline is fully integrated.
    """
    return {
        "message": "Full integration requires completed scoring pipeline",
        "repo": repo,
        "detail_level": detail_level,
        "report": None,
    }
