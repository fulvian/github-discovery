"""Async task queue wrapping asyncio.Queue with persistent JobStore backing.

Provides enqueue/dequeue with database persistence and stale-job
recovery for worker resiliency.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from github_discovery.workers.job_store import JobStore  # noqa: TC001

if TYPE_CHECKING:
    from github_discovery.workers.types import Job

logger = structlog.get_logger("github_discovery.workers.queue")


class AsyncTaskQueue:
    """Async task queue backed by a persistent JobStore.

    Enqueued job IDs are placed on an in-memory asyncio.Queue for
    fast dispatch. Dequeue loads the full Job from the store. Stale
    running jobs can be recovered via ``requeue_stale()``.
    """

    def __init__(self, job_store: JobStore) -> None:
        """Initialize with a JobStore for persistence.

        Args:
            job_store: Persistent job storage backend.
        """
        self._store = job_store
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    async def enqueue(self, job: Job) -> Job:
        """Persist a job and place its ID on the queue.

        Args:
            job: Job to enqueue.

        Returns:
            The persisted Job.
        """
        persisted = await self._store.create(job)
        await self._queue.put(job.job_id)
        logger.debug(
            "job_enqueued",
            job_id=job.job_id,
            job_type=job.job_type.value,
        )
        return persisted

    async def dequeue(self, timeout: float = 1.0) -> Job | None:
        """Retrieve the next job from the queue.

        Args:
            timeout: Max seconds to wait for a job.

        Returns:
            Job if available, None on timeout.
        """
        try:
            job_id = await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except TimeoutError:
            return None

        job = await self._store.get(job_id)
        if job is None:
            logger.warning("dequeue_job_missing", job_id=job_id)
        return job

    async def requeue_stale(self, max_age_seconds: int = 3600) -> int:
        """Requeue running jobs older than the specified age.

        Finds all RUNNING jobs whose started_at is more than
        ``max_age_seconds`` ago, resets them to PENDING, and places
        them back on the queue.

        Args:
            max_age_seconds: Maximum allowed age for running jobs.

        Returns:
            Number of jobs requeued.
        """
        from github_discovery.workers.types import JobStatus  # noqa: PLC0415

        running_jobs = await self._store.list_jobs(status=JobStatus.RUNNING, limit=1000)
        now = datetime.now(UTC)
        requeued = 0

        for job in running_jobs:
            if job.started_at is None:
                continue
            age = (now - job.started_at).total_seconds()
            if age > max_age_seconds:
                await self._store.update_status(
                    job.job_id,
                    JobStatus.PENDING,
                    started_at=None,
                )
                await self._queue.put(job.job_id)
                requeued += 1
                logger.info(
                    "stale_job_requeued",
                    job_id=job.job_id,
                    age_seconds=age,
                )

        if requeued > 0:
            logger.info("requeue_stale_complete", requeued=requeued)

        return requeued

    @property
    def size(self) -> int:
        """Current number of items waiting in the queue."""
        return self._queue.qsize()
