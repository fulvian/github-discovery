"""Discovery worker — wraps DiscoveryOrchestrator for background job processing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from github_discovery.discovery.types import DiscoveryQuery
from github_discovery.workers.base_worker import BaseWorker
from github_discovery.workers.types import Job, WorkerResult

if TYPE_CHECKING:
    from github_discovery.discovery.orchestrator import DiscoveryOrchestrator
    from github_discovery.workers.job_store import JobStore

logger = structlog.get_logger("github_discovery.workers.discovery_worker")


class DiscoveryWorker(BaseWorker):
    """Worker that executes discovery pipeline jobs.

    Deserializes job input_data into a DiscoveryQuery, delegates to
    the DiscoveryOrchestrator, and returns the discovery result data.
    """

    def __init__(
        self,
        job_store: JobStore,
        orchestrator: DiscoveryOrchestrator,
    ) -> None:
        """Initialize with job store and discovery orchestrator."""
        super().__init__(job_store)
        self._orchestrator = orchestrator

    async def process(self, job: Job) -> WorkerResult:
        """Process a discovery job.

        Args:
            job: Job with input_data containing DiscoveryQuery fields.

        Returns:
            WorkerResult with pool_id, total_candidates, channels_used.
        """
        try:
            query = DiscoveryQuery.model_validate(job.input_data)
        except Exception as e:
            return WorkerResult(
                success=False,
                error=f"Invalid discovery query: {e}",
            )

        try:
            result = await self._orchestrator.discover(query)
            return WorkerResult(
                success=True,
                data=result.model_dump(),
            )
        except Exception as e:
            logger.error(
                "discovery_worker_error",
                job_id=job.job_id,
                error=str(e),
            )
            return WorkerResult(
                success=False,
                error=f"Discovery failed: {e}",
            )
