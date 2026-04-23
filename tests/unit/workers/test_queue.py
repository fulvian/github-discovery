"""Tests for AsyncTaskQueue."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from github_discovery.workers.job_store import JobStore
from github_discovery.workers.queue import AsyncTaskQueue
from github_discovery.workers.types import Job, JobStatus, JobType


@pytest.fixture
async def store() -> JobStore:
    """Create an in-memory JobStore for testing."""
    s = JobStore(":memory:")
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
async def queue(store: JobStore) -> AsyncTaskQueue:
    """Create an AsyncTaskQueue backed by in-memory store."""
    return AsyncTaskQueue(store)


async def test_enqueue_creates_job_in_store(store: JobStore, queue: AsyncTaskQueue) -> None:
    """Enqueuing a job should persist it in the store."""
    job = Job(job_type=JobType.DISCOVERY, input_data={"query": "python"})
    await queue.enqueue(job)

    stored = await store.get(job.job_id)
    assert stored is not None
    assert stored.job_type == JobType.DISCOVERY
    assert stored.status == JobStatus.PENDING


async def test_enqueue_returns_job(store: JobStore, queue: AsyncTaskQueue) -> None:
    """Enqueue should return the persisted job."""
    job = Job(job_type=JobType.SCREENING)
    result = await queue.enqueue(job)

    assert result.job_id == job.job_id
    assert result.job_type == JobType.SCREENING


async def test_dequeue_returns_job(store: JobStore, queue: AsyncTaskQueue) -> None:
    """Dequeuing should return the next job from the queue."""
    job = Job(job_type=JobType.DISCOVERY, input_data={"q": "test"})
    await queue.enqueue(job)

    dequeued = await queue.dequeue(timeout=1.0)
    assert dequeued is not None
    assert dequeued.job_id == job.job_id
    assert dequeued.input_data == {"q": "test"}


async def test_dequeue_empty_returns_none(queue: AsyncTaskQueue) -> None:
    """Dequeuing from empty queue should return None after timeout."""
    result = await queue.dequeue(timeout=0.1)
    assert result is None


async def test_dequeue_timeout(queue: AsyncTaskQueue) -> None:
    """Dequeue should respect the timeout parameter."""
    import time  # noqa: PLC0415

    start = time.perf_counter()
    result = await queue.dequeue(timeout=0.2)
    elapsed = time.perf_counter() - start

    assert result is None
    assert elapsed >= 0.15  # Allow some tolerance


async def test_size_reflects_queue(queue: AsyncTaskQueue) -> None:
    """Size property should reflect items waiting in queue."""
    assert queue.size == 0

    await queue.enqueue(Job(job_type=JobType.DISCOVERY))
    assert queue.size == 1

    await queue.enqueue(Job(job_type=JobType.SCREENING))
    assert queue.size == 2

    await queue.dequeue(timeout=1.0)
    assert queue.size == 1


async def test_requeue_stale_finds_running_jobs(store: JobStore, queue: AsyncTaskQueue) -> None:
    """Requeue stale should find running jobs older than max_age."""
    # Create a job and set it to RUNNING with an old started_at
    job = Job(job_type=JobType.DISCOVERY)
    await queue.enqueue(job)

    # Drain the initial queue entry (from enqueue)
    await queue.dequeue(timeout=1.0)
    assert queue.size == 0

    # Manually set the job to RUNNING with a stale started_at
    old_time = datetime.now(UTC) - timedelta(hours=2)
    await store.update_status(job.job_id, JobStatus.RUNNING, started_at=old_time)

    # Requeue stale with 1 hour max age
    requeued = await queue.requeue_stale(max_age_seconds=3600)
    assert requeued == 1

    # Job should be back to PENDING
    updated = await store.get(job.job_id)
    assert updated is not None
    assert updated.status == JobStatus.PENDING

    # And it should be on the queue (1 requeued item)
    assert queue.size == 1


async def test_requeue_stale_ignores_recent_jobs(store: JobStore, queue: AsyncTaskQueue) -> None:
    """Requeue stale should ignore recently started running jobs."""
    job = Job(job_type=JobType.DISCOVERY)
    await queue.enqueue(job)

    # Set to RUNNING with a recent started_at
    recent_time = datetime.now(UTC) - timedelta(minutes=5)
    await store.update_status(job.job_id, JobStatus.RUNNING, started_at=recent_time)

    # Requeue stale with 1 hour max age — should find nothing
    requeued = await queue.requeue_stale(max_age_seconds=3600)
    assert requeued == 0

    # Job should still be RUNNING
    updated = await store.get(job.job_id)
    assert updated is not None
    assert updated.status == JobStatus.RUNNING
