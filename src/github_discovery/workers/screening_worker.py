"""Screening worker — wraps ScreeningOrchestrator for background job processing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from github_discovery.screening.types import ScreeningContext
from github_discovery.workers.base_worker import BaseWorker
from github_discovery.workers.types import Job, WorkerResult

if TYPE_CHECKING:
    from github_discovery.screening.orchestrator import ScreeningOrchestrator
    from github_discovery.workers.job_store import JobStore

logger = structlog.get_logger("github_discovery.workers.screening_worker")


class ScreeningWorker(BaseWorker):
    """Worker that executes screening pipeline jobs.

    Deserializes job input_data into a ScreeningContext, delegates to
    the ScreeningOrchestrator, and returns screening summary data.
    """

    def __init__(
        self,
        job_store: JobStore,
        orchestrator: ScreeningOrchestrator,
    ) -> None:
        """Initialize with job store and screening orchestrator."""
        super().__init__(job_store)
        self._orchestrator = orchestrator

    async def process(self, job: Job) -> WorkerResult:
        """Process a screening job.

        Args:
            job: Job with input_data containing ScreeningContext fields.

        Returns:
            WorkerResult with total_screened, passed, failed counts.
        """
        try:
            context = ScreeningContext.model_validate(job.input_data)
        except Exception as e:
            return WorkerResult(
                success=False,
                error=f"Invalid screening context: {e}",
            )

        try:
            results = await self._orchestrator.screen(context)

            passed = sum(
                1
                for r in results
                if r.gate1 is not None
                and r.gate1.gate1_pass
                and (r.gate2 is None or r.gate2.gate2_pass)
            )
            failed = len(results) - passed

            return WorkerResult(
                success=True,
                data={
                    "total_screened": len(results),
                    "passed": passed,
                    "failed": failed,
                    "results": [r.model_dump() for r in results],
                },
            )
        except Exception as e:
            logger.error(
                "screening_worker_error",
                job_id=job.job_id,
                error=str(e),
            )
            return WorkerResult(
                success=False,
                error=f"Screening failed: {e}",
            )
