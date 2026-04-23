"""Tests for BaseWorker abstract class."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from github_discovery.workers.base_worker import BaseWorker
from github_discovery.workers.types import Job, JobStatus, JobType, WorkerResult

if TYPE_CHECKING:
    from github_discovery.workers.job_store import JobStore


class _FakeWorker(BaseWorker):
    """Concrete test worker for BaseWorker tests."""

    def __init__(
        self,
        job_store: JobStore,
        *,
        result: WorkerResult | None = None,
        side_effect: Exception | None = None,
    ) -> None:
        super().__init__(job_store)
        self._result = result or WorkerResult(success=True, data={"key": "value"})
        self._side_effect = side_effect
        self.process_called_with: Job | None = None

    async def process(self, job: Job) -> WorkerResult:
        self.process_called_with = job
        if self._side_effect:
            raise self._side_effect
        return self._result


@pytest.fixture
async def job_store() -> AsyncMock:
    """Create a mock JobStore."""
    store = AsyncMock()
    store.update_status = AsyncMock(
        return_value=Job(
            job_type=JobType.DISCOVERY,
            status=JobStatus.RUNNING,
        )
    )
    return store


async def test_execute_success(job_store: AsyncMock) -> None:
    """Successful process() should update status to COMPLETED with result data."""
    worker = _FakeWorker(job_store, result=WorkerResult(success=True, data={"pool_id": "abc"}))
    job = Job(job_type=JobType.DISCOVERY, input_data={"query": "test"})

    await worker.execute(job)

    # First call: RUNNING, second call: COMPLETED
    assert job_store.update_status.call_count == 2
    running_call = job_store.update_status.call_args_list[0]
    completed_call = job_store.update_status.call_args_list[1]

    assert running_call[0][0] == job.job_id
    assert running_call[0][1] == JobStatus.RUNNING

    assert completed_call[0][0] == job.job_id
    assert completed_call[0][1] == JobStatus.COMPLETED
    assert completed_call[1]["result"] == {"pool_id": "abc"}


async def test_execute_failure_result(job_store: AsyncMock) -> None:
    """Worker returning unsuccessful result should update status to FAILED."""
    worker = _FakeWorker(
        job_store,
        result=WorkerResult(success=False, error="bad input"),
    )
    job = Job(job_type=JobType.DISCOVERY, input_data={"query": "test"})

    await worker.execute(job)

    assert job_store.update_status.call_count == 2
    failed_call = job_store.update_status.call_args_list[1]
    assert failed_call[0][1] == JobStatus.FAILED
    assert failed_call[1]["error_message"] == "bad input"


async def test_execute_exception(job_store: AsyncMock) -> None:
    """Worker raising an exception should update status to FAILED with message."""
    worker = _FakeWorker(
        job_store,
        side_effect=RuntimeError("boom"),
    )
    job = Job(job_type=JobType.DISCOVERY, input_data={"query": "test"})

    await worker.execute(job)

    assert job_store.update_status.call_count == 2
    failed_call = job_store.update_status.call_args_list[1]
    assert failed_call[0][1] == JobStatus.FAILED
    assert failed_call[1]["error_message"] == "boom"


async def test_process_called_with_correct_job(job_store: AsyncMock) -> None:
    """process() should receive the exact job passed to execute()."""
    worker = _FakeWorker(job_store)
    job = Job(job_type=JobType.DISCOVERY, input_data={"query": "test"})

    await worker.execute(job)

    assert worker.process_called_with is not None
    assert worker.process_called_with.job_id == job.job_id


async def test_execute_sets_started_at(job_store: AsyncMock) -> None:
    """Running status update should include started_at timestamp."""
    worker = _FakeWorker(job_store)
    job = Job(job_type=JobType.DISCOVERY)

    await worker.execute(job)

    running_call = job_store.update_status.call_args_list[0]
    assert "started_at" in running_call[1]


async def test_execute_sets_completed_at_on_success(job_store: AsyncMock) -> None:
    """Completed status update should include completed_at timestamp."""
    worker = _FakeWorker(job_store)
    job = Job(job_type=JobType.DISCOVERY)

    await worker.execute(job)

    completed_call = job_store.update_status.call_args_list[1]
    assert "completed_at" in completed_call[1]
