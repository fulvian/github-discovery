"""Discovery API routes — candidate discovery endpoints.

Provides endpoints to start discovery jobs, check their status,
and list candidates in a pool.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, status

from github_discovery.api.deps import get_job_store, get_pool_manager, get_queue
from github_discovery.models.api import DiscoveryQuery, DiscoveryResponse
from github_discovery.models.enums import DiscoveryChannel
from github_discovery.workers.types import Job, JobType

if TYPE_CHECKING:
    from github_discovery.discovery.pool import PoolManager
    from github_discovery.workers.job_store import JobStore
    from github_discovery.workers.queue import AsyncTaskQueue

router = APIRouter(tags=["discovery"])


@router.post(
    "/discover",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DiscoveryResponse,
)
async def start_discovery(
    request: DiscoveryQuery,
    job_store: JobStore = Depends(get_job_store),  # noqa: B008
    queue: AsyncTaskQueue = Depends(get_queue),  # noqa: B008
) -> DiscoveryResponse:
    """Start an asynchronous discovery job.

    Creates a background job to discover candidate repositories
    matching the given query and returns the job tracking info.
    """
    job = Job(
        job_type=JobType.DISCOVERY,
        input_data=request.model_dump(),
    )
    persisted = await queue.enqueue(job)
    return DiscoveryResponse(
        job_id=persisted.job_id,
        status="pending",
        session_id=request.session_id,
    )


@router.get(
    "/discover/{job_id}",
    response_model=DiscoveryResponse,
)
async def get_discovery_status(
    job_id: str,
    job_store: JobStore = Depends(get_job_store),  # noqa: B008
) -> DiscoveryResponse:
    """Get the status of a discovery job by its ID.

    Returns the current job status, and if completed, includes
    total candidates discovered and the pool ID.
    """
    job = await job_store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Discovery job {job_id} not found",
        )

    session_id_val = job.input_data.get("session_id")
    session_id: str | None = str(session_id_val) if session_id_val is not None else None

    response = DiscoveryResponse(
        job_id=job.job_id,
        status=job.status.value,
        session_id=session_id,
    )

    if job.result is not None:
        result_data: dict[str, object] = job.result
        response.total_candidates = int(result_data.get("total_candidates", 0))  # type: ignore[call-overload]
        pool_id_val = result_data.get("pool_id")
        response.pool_id = str(pool_id_val) if pool_id_val is not None else None
        raw_channels = result_data.get("channels_used", [])
        if isinstance(raw_channels, list):
            response.channels_used = [
                ch if isinstance(ch, DiscoveryChannel) else DiscoveryChannel(str(ch))
                for ch in raw_channels
            ]

    return response


@router.get("/candidates")
async def get_candidates(
    pool_id: str = Query(description="Candidate pool ID"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    pool_manager: PoolManager = Depends(get_pool_manager),  # noqa: B008
) -> dict[str, object]:
    """List candidates in a pool with pagination.

    Returns pool metadata and a summary of candidates. This endpoint
    is informational — detailed candidate data is available through
    the pool manager directly.
    """
    pool = await pool_manager.get_pool(pool_id)
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pool {pool_id} not found",
        )

    return {
        "pool_id": pool.pool_id,
        "query": pool.query,
        "total_candidates": len(pool.candidates),
        "page": page,
        "page_size": page_size,
    }
