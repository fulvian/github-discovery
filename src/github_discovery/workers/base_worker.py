"""Base worker abstract class for background job processing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from github_discovery.workers.types import Job, JobStatus, WorkerResult

if TYPE_CHECKING:
    from github_discovery.workers.job_store import JobStore

logger = structlog.get_logger("github_discovery.workers.base_worker")


class BaseWorker(ABC):
    """Abstract base worker for processing background jobs."""

    def __init__(self, job_store: JobStore) -> None:
        """Initialize with a job store for status tracking."""
        self._store = job_store

    @abstractmethod
    async def process(self, job: Job) -> WorkerResult:
        """Process a job and return the result."""
        ...

    async def execute(self, job: Job) -> None:
        """Execute job with status tracking.

        Updates job status to RUNNING, calls process(), then
        updates to COMPLETED or FAILED based on result.
        """
        await self._store.update_status(
            job.job_id,
            JobStatus.RUNNING,
            started_at=datetime.now(UTC).isoformat(),
        )
        try:
            result = await self.process(job)
            if result.success:
                await self._store.update_status(
                    job.job_id,
                    JobStatus.COMPLETED,
                    result=result.data,
                    completed_at=datetime.now(UTC).isoformat(),
                )
                logger.info(
                    "job_completed",
                    job_id=job.job_id,
                    job_type=job.job_type,
                )
            else:
                await self._store.update_status(
                    job.job_id,
                    JobStatus.FAILED,
                    error_message=result.error or "Unknown error",
                    completed_at=datetime.now(UTC).isoformat(),
                )
                logger.warning(
                    "job_failed",
                    job_id=job.job_id,
                    job_type=job.job_type,
                    error=result.error,
                )
        except Exception as e:
            await self._store.update_status(
                job.job_id,
                JobStatus.FAILED,
                error_message=str(e),
                completed_at=datetime.now(UTC).isoformat(),
            )
            logger.error(
                "job_exception",
                job_id=job.job_id,
                job_type=job.job_type,
                error=str(e),
            )
