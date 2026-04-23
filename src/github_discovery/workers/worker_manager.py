"""Worker manager — manages lifecycle of background worker tasks."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from github_discovery.workers.assessment_worker import AssessmentWorker
from github_discovery.workers.discovery_worker import DiscoveryWorker
from github_discovery.workers.screening_worker import ScreeningWorker
from github_discovery.workers.types import JobType

if TYPE_CHECKING:
    from github_discovery.assessment.orchestrator import AssessmentOrchestrator
    from github_discovery.discovery.orchestrator import DiscoveryOrchestrator
    from github_discovery.screening.orchestrator import ScreeningOrchestrator
    from github_discovery.workers.base_worker import BaseWorker
    from github_discovery.workers.job_store import JobStore
    from github_discovery.workers.queue import AsyncTaskQueue

logger = structlog.get_logger("github_discovery.workers.worker_manager")


class WorkerManager:
    """Manages lifecycle of background worker tasks.

    Creates typed worker instances for each provided orchestrator,
    starts worker loops that dequeue and process jobs, and provides
    graceful shutdown via task cancellation.
    """

    def __init__(
        self,
        queue: AsyncTaskQueue,
        job_store: JobStore,
        discovery_orch: DiscoveryOrchestrator | None = None,
        screening_orch: ScreeningOrchestrator | None = None,
        assessment_orch: AssessmentOrchestrator | None = None,
        workers_per_type: int = 1,
    ) -> None:
        """Initialize with queue, store, and optional orchestrators."""
        self._queue = queue
        self._store = job_store
        self._workers_per_type = workers_per_type
        self._tasks: list[asyncio.Task[None]] = []
        self._workers: dict[JobType, BaseWorker] = {}

        if discovery_orch is not None:
            self._workers[JobType.DISCOVERY] = DiscoveryWorker(job_store, discovery_orch)
        if screening_orch is not None:
            self._workers[JobType.SCREENING] = ScreeningWorker(job_store, screening_orch)
        if assessment_orch is not None:
            self._workers[JobType.ASSESSMENT] = AssessmentWorker(job_store, assessment_orch)

    async def start(self) -> None:
        """Start worker tasks. Requeues stale jobs first."""
        await self._queue.requeue_stale()
        for i in range(self._workers_per_type):
            for job_type, _worker in self._workers.items():
                name = f"worker-{job_type.value}-{i}"
                task = asyncio.create_task(
                    self._worker_loop(name, job_type),
                    name=name,
                )
                self._tasks.append(task)
        logger.info(
            "workers_started",
            worker_count=len(self._tasks),
            worker_types=[jt.value for jt in self._workers],
        )

    async def stop(self) -> None:
        """Cancel all worker tasks gracefully."""
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("workers_stopped")

    async def _worker_loop(self, worker_name: str, job_type: JobType) -> None:
        """Main worker loop: dequeue -> get worker -> execute."""
        logger.info("worker_started", worker_name=worker_name)
        while True:
            try:
                job = await self._queue.dequeue(timeout=1.0)
                if job is None:
                    continue
                if job.job_type != job_type:
                    # Re-enqueue if wrong type (shouldn't happen with typed queues)
                    await self._queue.enqueue(job)
                    continue
                worker = self._workers.get(job.job_type)
                if worker is not None:
                    await worker.execute(job)
                else:
                    logger.error("no_worker_for_type", job_type=job.job_type)
            except asyncio.CancelledError:
                logger.info("worker_cancelled", worker_name=worker_name)
                raise
            except Exception as e:
                logger.error("worker_loop_error", worker_name=worker_name, error=str(e))

    @property
    def active_workers(self) -> int:
        """Number of active worker tasks."""
        return sum(1 for t in self._tasks if not t.done())

    @property
    def is_running(self) -> bool:
        """Whether the manager has active workers."""
        return len(self._tasks) > 0 and all(not t.done() for t in self._tasks)
