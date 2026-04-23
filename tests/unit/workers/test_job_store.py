"""Tests for SQLite-backed job store."""

from __future__ import annotations

import pytest

from github_discovery.workers.job_store import JobStore
from github_discovery.workers.types import Job, JobStatus, JobType


@pytest.fixture
async def store() -> JobStore:
    """Create an in-memory JobStore for testing."""
    s = JobStore(":memory:")
    await s.initialize()
    yield s
    await s.close()


async def test_create_and_get(store: JobStore) -> None:
    """Creating a job and retrieving it should return same data."""
    job = Job(job_type=JobType.DISCOVERY, input_data={"query": "python"})
    created = await store.create(job)
    retrieved = await store.get(created.job_id)

    assert retrieved is not None
    assert retrieved.job_id == created.job_id
    assert retrieved.job_type == JobType.DISCOVERY
    assert retrieved.status == JobStatus.PENDING
    assert retrieved.input_data == {"query": "python"}


async def test_get_nonexistent_returns_none(store: JobStore) -> None:
    """Getting a non-existent job should return None."""
    result = await store.get("nonexistent-id")
    assert result is None


async def test_update_status_running(store: JobStore) -> None:
    """Updating status to RUNNING should persist."""
    job = Job(job_type=JobType.SCREENING)
    created = await store.create(job)

    updated = await store.update_status(created.job_id, JobStatus.RUNNING)
    assert updated is not None
    assert updated.status == JobStatus.RUNNING


async def test_update_status_completed_with_result(store: JobStore) -> None:
    """Updating status to COMPLETED with result data should persist."""
    job = Job(job_type=JobType.DISCOVERY)
    created = await store.create(job)

    result_data = {"candidates": 42, "top_repo": "test/repo"}
    updated = await store.update_status(
        created.job_id,
        JobStatus.COMPLETED,
        result=result_data,
    )

    assert updated is not None
    assert updated.status == JobStatus.COMPLETED
    assert updated.result == result_data


async def test_update_status_failed_with_error(store: JobStore) -> None:
    """Updating status to FAILED with error message should persist."""
    job = Job(job_type=JobType.ASSESSMENT)
    created = await store.create(job)

    updated = await store.update_status(
        created.job_id,
        JobStatus.FAILED,
        error_message="LLM timeout",
    )

    assert updated is not None
    assert updated.status == JobStatus.FAILED
    assert updated.error_message == "LLM timeout"


async def test_list_all_jobs(store: JobStore) -> None:
    """Listing jobs should return all jobs ordered by created_at desc."""
    await store.create(Job(job_type=JobType.DISCOVERY))
    await store.create(Job(job_type=JobType.SCREENING))

    jobs = await store.list_jobs()
    assert len(jobs) == 2


async def test_list_jobs_by_type(store: JobStore) -> None:
    """Listing with type filter should return only matching jobs."""
    await store.create(Job(job_type=JobType.DISCOVERY))
    await store.create(Job(job_type=JobType.SCREENING))
    await store.create(Job(job_type=JobType.DISCOVERY))

    jobs = await store.list_jobs(job_type=JobType.DISCOVERY)
    assert len(jobs) == 2
    assert all(j.job_type == JobType.DISCOVERY for j in jobs)


async def test_list_jobs_by_status(store: JobStore) -> None:
    """Listing with status filter should return only matching jobs."""
    job1 = await store.create(Job(job_type=JobType.DISCOVERY))
    await store.create(Job(job_type=JobType.SCREENING))
    await store.update_status(job1.job_id, JobStatus.RUNNING)

    jobs = await store.list_jobs(status=JobStatus.RUNNING)
    assert len(jobs) == 1
    assert jobs[0].status == JobStatus.RUNNING


async def test_list_jobs_limit(store: JobStore) -> None:
    """Listing with limit should cap the number of results."""
    for _ in range(5):
        await store.create(Job(job_type=JobType.DISCOVERY))

    jobs = await store.list_jobs(limit=3)
    assert len(jobs) == 3


async def test_delete_existing(store: JobStore) -> None:
    """Deleting an existing job should return True."""
    job = await store.create(Job(job_type=JobType.DISCOVERY))
    deleted = await store.delete(job.job_id)
    assert deleted is True

    retrieved = await store.get(job.job_id)
    assert retrieved is None


async def test_delete_nonexistent_returns_false(store: JobStore) -> None:
    """Deleting a non-existent job should return False."""
    deleted = await store.delete("nonexistent-id")
    assert deleted is False


async def test_close_and_reuse() -> None:
    """Closing and re-initializing should still work."""
    store = JobStore(":memory:")
    await store.initialize()

    job = await store.create(Job(job_type=JobType.DISCOVERY))  # noqa: F841
    await store.close()

    # Re-initialize
    await store.initialize()
    # The in-memory DB is lost after close, so re-create
    job2 = await store.create(Job(job_type=JobType.SCREENING))
    retrieved = await store.get(job2.job_id)
    assert retrieved is not None
    assert retrieved.job_type == JobType.SCREENING
    await store.close()
