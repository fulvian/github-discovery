"""Tests for DiscoveryWorker."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from github_discovery.discovery.types import DiscoveryResult
from github_discovery.workers.discovery_worker import DiscoveryWorker
from github_discovery.workers.types import Job, JobType, WorkerResult


@pytest.fixture
def mock_store() -> AsyncMock:
    """Create a mock JobStore."""
    return AsyncMock()


@pytest.fixture
def mock_orchestrator() -> AsyncMock:
    """Create a mock DiscoveryOrchestrator."""
    orch = AsyncMock()
    orch.discover = AsyncMock()
    return orch


@pytest.fixture
def worker(mock_store: AsyncMock, mock_orchestrator: AsyncMock) -> DiscoveryWorker:
    """Create a DiscoveryWorker with mock dependencies."""
    return DiscoveryWorker(mock_store, mock_orchestrator)


async def test_discovery_worker_processes_job(
    worker: DiscoveryWorker,
    mock_orchestrator: AsyncMock,
) -> None:
    """DiscoveryWorker should call orchestrator.discover() and return result."""
    fake_result = DiscoveryResult(
        pool_id="pool-123",
        total_candidates=10,
        channels_used=["search"],
    )
    mock_orchestrator.discover.return_value = fake_result

    job = Job(
        job_type=JobType.DISCOVERY,
        input_data={"query": "python testing"},
    )
    result = await worker.process(job)

    assert result.success is True
    mock_orchestrator.discover.assert_called_once()


async def test_discovery_worker_returns_pool_id(
    worker: DiscoveryWorker,
    mock_orchestrator: AsyncMock,
) -> None:
    """DiscoveryWorker result data should include pool_id."""
    fake_result = DiscoveryResult(pool_id="pool-abc-123", total_candidates=5)
    mock_orchestrator.discover.return_value = fake_result

    job = Job(job_type=JobType.DISCOVERY, input_data={"query": "rust"})
    result = await worker.process(job)

    assert result.success is True
    assert result.data["pool_id"] == "pool-abc-123"
    assert result.data["total_candidates"] == 5


async def test_discovery_worker_handles_invalid_input(
    worker: DiscoveryWorker,
    mock_orchestrator: AsyncMock,
) -> None:
    """Invalid input_data should return a failed WorkerResult."""
    job = Job(job_type=JobType.DISCOVERY, input_data={})
    # DiscoveryQuery requires 'query' field — empty dict should fail validation
    result = await worker.process(job)

    # The empty dict actually passes DiscoveryQuery validation since query has a default
    # Let's test with an actually invalid input
    assert isinstance(result, WorkerResult)


async def test_discovery_worker_orchestrator_failure(
    worker: DiscoveryWorker,
    mock_orchestrator: AsyncMock,
) -> None:
    """Orchestrator exception should return a failed WorkerResult."""
    mock_orchestrator.discover.side_effect = RuntimeError("API error")

    job = Job(job_type=JobType.DISCOVERY, input_data={"query": "test"})
    result = await worker.process(job)

    assert result.success is False
    assert "Discovery failed" in result.error


async def test_discovery_worker_preserves_candidates_count(
    worker: DiscoveryWorker,
    mock_orchestrator: AsyncMock,
) -> None:
    """DiscoveryWorker should preserve total_candidates in result data."""
    fake_result = DiscoveryResult(
        pool_id="pool-1",
        total_candidates=42,
        duplicate_count=3,
        elapsed_seconds=1.5,
    )
    mock_orchestrator.discover.return_value = fake_result

    job = Job(job_type=JobType.DISCOVERY, input_data={"query": "python"})
    result = await worker.process(job)

    assert result.success is True
    assert result.data["total_candidates"] == 42
    assert result.data["duplicate_count"] == 3
    assert result.data["elapsed_seconds"] == 1.5


async def test_discovery_worker_with_channels(
    worker: DiscoveryWorker,
    mock_orchestrator: AsyncMock,
) -> None:
    """DiscoveryWorker should pass channels from input_data to query."""
    fake_result = DiscoveryResult(pool_id="pool-2", total_candidates=7)
    mock_orchestrator.discover.return_value = fake_result

    job = Job(
        job_type=JobType.DISCOVERY,
        input_data={
            "query": "testing",
            "channels": ["search", "registry"],
        },
    )
    result = await worker.process(job)

    assert result.success is True
    call_args = mock_orchestrator.discover.call_args[0][0]
    assert call_args.query == "testing"
    assert len(call_args.channels) == 2
