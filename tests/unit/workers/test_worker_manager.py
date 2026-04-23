"""Tests for WorkerManager."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from github_discovery.discovery.types import DiscoveryResult
from github_discovery.workers.types import Job, JobType
from github_discovery.workers.worker_manager import WorkerManager


@pytest.fixture
def mock_queue() -> AsyncMock:
    """Create a mock AsyncTaskQueue."""
    q = AsyncMock()
    q.dequeue = AsyncMock()
    q.enqueue = AsyncMock()
    q.requeue_stale = AsyncMock(return_value=0)
    return q


@pytest.fixture
def mock_store() -> AsyncMock:
    """Create a mock JobStore."""
    store = AsyncMock()
    store.update_status = AsyncMock()
    return store


@pytest.fixture
def mock_discovery_orch() -> AsyncMock:
    """Create a mock DiscoveryOrchestrator."""
    return AsyncMock()


@pytest.fixture
def mock_screening_orch() -> AsyncMock:
    """Create a mock ScreeningOrchestrator."""
    return AsyncMock()


async def test_start_creates_worker_tasks(
    mock_queue: AsyncMock,
    mock_store: AsyncMock,
    mock_discovery_orch: AsyncMock,
) -> None:
    """start() should create worker tasks for each orchestrator."""
    manager = WorkerManager(
        queue=mock_queue,
        job_store=mock_store,
        discovery_orch=mock_discovery_orch,
        workers_per_type=2,
    )
    await manager.start()

    assert len(manager._tasks) == 2  # 2 workers for discovery type
    assert manager.active_workers == 2
    await manager.stop()


async def test_stop_cancels_tasks(
    mock_queue: AsyncMock,
    mock_store: AsyncMock,
    mock_discovery_orch: AsyncMock,
) -> None:
    """stop() should cancel all worker tasks."""
    manager = WorkerManager(
        queue=mock_queue,
        job_store=mock_store,
        discovery_orch=mock_discovery_orch,
        workers_per_type=1,
    )
    await manager.start()
    assert manager.active_workers == 1

    await manager.stop()
    assert manager.active_workers == 0
    assert len(manager._tasks) == 0


async def test_worker_loop_processes_job(
    mock_queue: AsyncMock,
    mock_store: AsyncMock,
    mock_discovery_orch: AsyncMock,
) -> None:
    """Worker loop should dequeue a job and execute the worker."""
    job = Job(job_type=JobType.DISCOVERY, input_data={"query": "test"})

    # Return the job first, then None for all subsequent calls
    call_count = 0

    async def _dequeue(timeout: float = 1.0) -> Job | None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return job
        await asyncio.sleep(0.05)
        return None

    mock_queue.dequeue = _dequeue
    mock_store.update_status = AsyncMock(return_value=job)

    mock_discovery_orch.discover = AsyncMock(
        return_value=DiscoveryResult(pool_id="pool-1", total_candidates=5),
    )

    manager = WorkerManager(
        queue=mock_queue,
        job_store=mock_store,
        discovery_orch=mock_discovery_orch,
        workers_per_type=1,
    )

    await manager.start()
    # Give the worker loop time to process the job
    await asyncio.sleep(0.3)
    await manager.stop()

    # The orchestrator should have been called
    mock_discovery_orch.discover.assert_called_once()


async def test_active_workers_count(
    mock_queue: AsyncMock,
    mock_store: AsyncMock,
    mock_discovery_orch: AsyncMock,
    mock_screening_orch: AsyncMock,
) -> None:
    """active_workers should reflect running task count."""
    manager = WorkerManager(
        queue=mock_queue,
        job_store=mock_store,
        discovery_orch=mock_discovery_orch,
        screening_orch=mock_screening_orch,
        workers_per_type=1,
    )
    await manager.start()

    # 2 types * 1 worker = 2 active workers
    assert manager.active_workers == 2

    await manager.stop()
    assert manager.active_workers == 0


async def test_is_running_property(
    mock_queue: AsyncMock,
    mock_store: AsyncMock,
    mock_discovery_orch: AsyncMock,
) -> None:
    """is_running should be True when tasks are active."""
    manager = WorkerManager(
        queue=mock_queue,
        job_store=mock_store,
        discovery_orch=mock_discovery_orch,
    )

    assert manager.is_running is False

    await manager.start()
    assert manager.is_running is True

    await manager.stop()
    assert manager.is_running is False


async def test_worker_manager_with_none_orchestrators(
    mock_queue: AsyncMock,
    mock_store: AsyncMock,
) -> None:
    """Manager should only create workers for provided orchestrators."""
    manager = WorkerManager(
        queue=mock_queue,
        job_store=mock_store,
        discovery_orch=None,
        screening_orch=None,
        assessment_orch=None,
    )

    assert len(manager._workers) == 0
    await manager.start()
    assert len(manager._tasks) == 0
    await manager.stop()


async def test_start_requeues_stale_jobs(
    mock_queue: AsyncMock,
    mock_store: AsyncMock,
    mock_discovery_orch: AsyncMock,
) -> None:
    """start() should call requeue_stale() on the queue."""
    mock_queue.requeue_stale.return_value = 3

    manager = WorkerManager(
        queue=mock_queue,
        job_store=mock_store,
        discovery_orch=mock_discovery_orch,
    )
    await manager.start()

    mock_queue.requeue_stale.assert_called_once()
    await manager.stop()


async def test_worker_loop_requeues_wrong_type(
    mock_queue: AsyncMock,
    mock_store: AsyncMock,
    mock_discovery_orch: AsyncMock,
) -> None:
    """Worker loop should re-enqueue jobs of the wrong type."""
    wrong_job = Job(job_type=JobType.SCREENING, input_data={})
    call_count = 0

    async def _dequeue(timeout: float = 1.0) -> Job | None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return wrong_job
        await asyncio.sleep(0.05)
        return None

    mock_queue.dequeue = _dequeue

    manager = WorkerManager(
        queue=mock_queue,
        job_store=mock_store,
        discovery_orch=mock_discovery_orch,
    )

    await manager.start()
    await asyncio.sleep(0.3)
    await manager.stop()

    # The wrong-type job should have been re-enqueued
    mock_queue.enqueue.assert_called_once_with(wrong_job)
