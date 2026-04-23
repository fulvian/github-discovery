"""Assessment worker — wraps AssessmentOrchestrator for background job processing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from github_discovery.assessment.types import AssessmentContext
from github_discovery.workers.base_worker import BaseWorker
from github_discovery.workers.types import Job, WorkerResult

if TYPE_CHECKING:
    from github_discovery.assessment.orchestrator import AssessmentOrchestrator
    from github_discovery.workers.job_store import JobStore

logger = structlog.get_logger("github_discovery.workers.assessment_worker")


class AssessmentWorker(BaseWorker):
    """Worker that executes deep assessment pipeline jobs.

    Deserializes job input_data into an AssessmentContext, delegates to
    the AssessmentOrchestrator, and returns assessment summary data.
    """

    def __init__(
        self,
        job_store: JobStore,
        orchestrator: AssessmentOrchestrator,
    ) -> None:
        """Initialize with job store and assessment orchestrator."""
        super().__init__(job_store)
        self._orchestrator = orchestrator

    async def process(self, job: Job) -> WorkerResult:
        """Process an assessment job.

        Args:
            job: Job with input_data containing AssessmentContext fields.

        Returns:
            WorkerResult with total_assessed, gate3_passed, from_cache counts.
        """
        try:
            context = AssessmentContext.model_validate(job.input_data)
        except Exception as e:
            return WorkerResult(
                success=False,
                error=f"Invalid assessment context: {e}",
            )

        if not context.candidates:
            return WorkerResult(
                success=False,
                error="No candidates provided for assessment",
            )

        try:
            results = await self._orchestrator.assess(context)

            gate3_passed = sum(1 for r in results if r.gate3_pass)
            from_cache = sum(1 for r in results if r.cached)

            return WorkerResult(
                success=True,
                data={
                    "total_assessed": len(results),
                    "gate3_passed": gate3_passed,
                    "from_cache": from_cache,
                    "results": [r.model_dump() for r in results],
                },
            )
        except Exception as e:
            logger.error(
                "assessment_worker_error",
                job_id=job.job_id,
                error=str(e),
            )
            return WorkerResult(
                success=False,
                error=f"Assessment failed: {e}",
            )
