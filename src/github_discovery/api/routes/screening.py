"""Screening API routes — quality screening endpoints.

Provides endpoints to start screening jobs, check their status,
and retrieve shortlisted candidates that passed Gate 1+2.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, status

from github_discovery.api.deps import get_job_store, get_queue
from github_discovery.models.api import ScreeningRequest, ScreeningResponse
from github_discovery.workers.types import Job, JobStatus, JobType

if TYPE_CHECKING:
    from github_discovery.workers.job_store import JobStore
    from github_discovery.workers.queue import AsyncTaskQueue

router = APIRouter(tags=["screening"])


@router.post(
    "/screen",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ScreeningResponse,
)
async def start_screening(
    request: ScreeningRequest,
    job_store: JobStore = Depends(get_job_store),  # noqa: B008
    queue: AsyncTaskQueue = Depends(get_queue),  # noqa: B008
) -> ScreeningResponse:
    """Start an asynchronous screening job.

    Creates a background job to screen candidates in a pool through
    Gate 1 (metadata) and optionally Gate 2 (static/security).
    """
    job = Job(
        job_type=JobType.SCREENING,
        input_data=request.model_dump(),
    )
    persisted = await queue.enqueue(job)
    return ScreeningResponse(
        job_id=persisted.job_id,
        status="pending",
        pool_id=request.pool_id,
        gate_level=request.gate_level,
        session_id=request.session_id,
    )


@router.get(
    "/screen/{job_id}",
    response_model=ScreeningResponse,
)
async def get_screening_status(
    job_id: str,
    job_store: JobStore = Depends(get_job_store),  # noqa: B008
) -> ScreeningResponse:
    """Get the status of a screening job by its ID.

    Returns the current job status, and if completed, includes
    counts of screened, passed, and failed candidates.
    """
    job = await job_store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Screening job {job_id} not found",
        )

    response = ScreeningResponse(
        job_id=job.job_id,
        status=job.status.value,
        pool_id=job.input_data.get("pool_id", ""),  # type: ignore[arg-type]
        gate_level=job.input_data.get("gate_level", "1"),  # type: ignore[arg-type]
        session_id=job.input_data.get("session_id"),  # type: ignore[arg-type]
    )

    if job.result is not None:
        result: dict[str, object] = job.result
        response.total_screened = int(result.get("total_screened", 0))  # type: ignore[call-overload]
        response.passed = int(result.get("passed", 0))  # type: ignore[call-overload]
        response.failed = int(result.get("failed", 0))  # type: ignore[call-overload]

    return response


@router.get("/shortlist")
async def get_shortlist(
    pool_id: str = Query(description="Candidate pool ID"),
    min_score: float = Query(default=0.5, ge=0.0, le=1.0, description="Minimum gate score"),
    limit: int = Query(default=50, ge=1, le=500, description="Max results"),
    job_store: JobStore = Depends(get_job_store),  # noqa: B008
) -> dict[str, object]:
    """Get shortlisted candidates that passed Gate 1+2 screening.

    Lists completed screening jobs for the given pool and returns
    summary information about shortlisted candidates.
    """
    jobs = await job_store.list_jobs(
        job_type=JobType.SCREENING,
        status=JobStatus.COMPLETED,
        limit=100,
    )

    pool_jobs = [
        j for j in jobs if j.input_data.get("pool_id") == pool_id and j.result is not None
    ]

    return {
        "pool_id": pool_id,
        "min_score": min_score,
        "matching_jobs": len(pool_jobs),
        "limit": limit,
    }
