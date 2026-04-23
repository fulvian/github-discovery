"""Assessment API routes — deep LLM assessment endpoints.

Provides endpoints to start deep assessment jobs and check their
status. Hard gate enforcement (Gate 1+2 pass required) happens in
the worker, not the route.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status

from github_discovery.api.deps import get_job_store, get_queue
from github_discovery.models.api import AssessmentRequest, AssessmentResponse
from github_discovery.workers.types import Job, JobType

if TYPE_CHECKING:
    from github_discovery.workers.job_store import JobStore
    from github_discovery.workers.queue import AsyncTaskQueue

router = APIRouter(tags=["assessment"])


@router.post(
    "/assess",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AssessmentResponse,
)
async def start_assessment(
    request: AssessmentRequest,
    job_store: JobStore = Depends(get_job_store),  # noqa: B008
    queue: AsyncTaskQueue = Depends(get_queue),  # noqa: B008
) -> AssessmentResponse:
    """Start an asynchronous deep assessment job.

    Creates a background job to perform deep LLM assessment on
    the specified repositories. Hard gate enforcement (Gate 1+2
    pass required) happens in the worker, not this route.
    """
    job = Job(
        job_type=JobType.ASSESSMENT,
        input_data=request.model_dump(),
    )
    persisted = await queue.enqueue(job)
    return AssessmentResponse(
        job_id=persisted.job_id,
        status="pending",
        total_repos=len(request.repo_urls),
        session_id=request.session_id,
    )


@router.get(
    "/assess/{job_id}",
    response_model=AssessmentResponse,
)
async def get_assessment_status(
    job_id: str,
    job_store: JobStore = Depends(get_job_store),  # noqa: B008
) -> AssessmentResponse:
    """Get the status of an assessment job by its ID.

    Returns the current job status, and if completed, includes
    counts of assessed repos, rejections, and tokens consumed.
    """
    job = await job_store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment job {job_id} not found",
        )

    response = AssessmentResponse(
        job_id=job.job_id,
        status=job.status.value,
        session_id=job.input_data.get("session_id"),  # type: ignore[arg-type]
    )

    if job.result is not None:
        result: dict[str, object] = job.result
        response.total_repos = int(result.get("total_repos", 0))  # type: ignore[call-overload]
        response.assessed = int(result.get("assessed", 0))  # type: ignore[call-overload]
        response.rejected_hard_gate = int(result.get("rejected_hard_gate", 0))  # type: ignore[call-overload]
        response.tokens_used = int(result.get("tokens_used", 0))  # type: ignore[call-overload]

    return response
