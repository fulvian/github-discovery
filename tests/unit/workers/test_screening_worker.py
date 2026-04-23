"""Tests for ScreeningWorker."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from github_discovery.models.screening import (
    MetadataScreenResult,
    ScreeningResult,
    StaticScreenResult,
)
from github_discovery.workers.screening_worker import ScreeningWorker
from github_discovery.workers.types import Job, JobType


@pytest.fixture
def mock_store() -> AsyncMock:
    """Create a mock JobStore."""
    return AsyncMock()


@pytest.fixture
def mock_orchestrator() -> AsyncMock:
    """Create a mock ScreeningOrchestrator."""
    orch = AsyncMock()
    orch.screen = AsyncMock()
    return orch


@pytest.fixture
def worker(mock_store: AsyncMock, mock_orchestrator: AsyncMock) -> ScreeningWorker:
    """Create a ScreeningWorker with mock dependencies."""
    return ScreeningWorker(mock_store, mock_orchestrator)


def _make_screening_result(
    full_name: str,
    gate1_pass: bool = True,
    gate2_pass: bool | None = None,
) -> ScreeningResult:
    """Create a ScreeningResult with specified pass/fail status."""
    gate1 = MetadataScreenResult(
        full_name=full_name,
        gate1_pass=gate1_pass,
        gate1_total=0.8 if gate1_pass else 0.2,
    )
    gate2: StaticScreenResult | None = None
    if gate2_pass is not None:
        gate2 = StaticScreenResult(
            full_name=full_name,
            gate2_pass=gate2_pass,
            gate2_total=0.7 if gate2_pass else 0.3,
        )
    return ScreeningResult(full_name=full_name, gate1=gate1, gate2=gate2)


async def test_screening_worker_processes_job(
    worker: ScreeningWorker,
    mock_orchestrator: AsyncMock,
) -> None:
    """ScreeningWorker should call orchestrator.screen() and return result."""
    mock_orchestrator.screen.return_value = [
        _make_screening_result("test/repo1", gate1_pass=True, gate2_pass=True),
    ]

    job = Job(
        job_type=JobType.SCREENING,
        input_data={
            "pool_id": "pool-1",
            "candidates": [],
            "gate_level": "1",
        },
    )
    result = await worker.process(job)

    assert result.success is True
    mock_orchestrator.screen.assert_called_once()


async def test_screening_worker_counts_passed_failed(
    worker: ScreeningWorker,
    mock_orchestrator: AsyncMock,
) -> None:
    """ScreeningWorker should correctly count passed and failed results."""
    mock_orchestrator.screen.return_value = [
        _make_screening_result("test/pass1", gate1_pass=True, gate2_pass=True),
        _make_screening_result("test/fail1", gate1_pass=False),
        _make_screening_result("test/pass2", gate1_pass=True, gate2_pass=True),
        _make_screening_result("test/gate2fail", gate1_pass=True, gate2_pass=False),
    ]

    job = Job(
        job_type=JobType.SCREENING,
        input_data={"pool_id": "pool-1", "candidates": [], "gate_level": "2"},
    )
    result = await worker.process(job)

    assert result.success is True
    assert result.data["total_screened"] == 4
    # "passed" = gate1_pass=True AND (gate2 is None OR gate2_pass=True)
    # test/pass1: gate1=T, gate2=T → pass
    # test/fail1: gate1=F → fail
    # test/pass2: gate1=T, gate2=T → pass
    # test/gate2fail: gate1=T, gate2=F → fail (gate2 exists and not pass)
    assert result.data["passed"] == 2
    assert result.data["failed"] == 2


async def test_screening_worker_with_empty_candidates(
    worker: ScreeningWorker,
    mock_orchestrator: AsyncMock,
) -> None:
    """ScreeningWorker should handle empty candidate list."""
    mock_orchestrator.screen.return_value = []

    job = Job(
        job_type=JobType.SCREENING,
        input_data={"pool_id": "pool-1", "candidates": [], "gate_level": "1"},
    )
    result = await worker.process(job)

    assert result.success is True
    assert result.data["total_screened"] == 0
    assert result.data["passed"] == 0
    assert result.data["failed"] == 0


async def test_screening_worker_failure(
    worker: ScreeningWorker,
    mock_orchestrator: AsyncMock,
) -> None:
    """Orchestrator exception should return a failed WorkerResult."""
    mock_orchestrator.screen.side_effect = RuntimeError("Screening error")

    job = Job(
        job_type=JobType.SCREENING,
        input_data={"pool_id": "pool-1", "candidates": [], "gate_level": "1"},
    )
    result = await worker.process(job)

    assert result.success is False
    assert "Screening failed" in result.error


async def test_screening_worker_invalid_input(
    worker: ScreeningWorker,
    mock_orchestrator: AsyncMock,
) -> None:
    """Invalid input_data should return a failed WorkerResult."""
    job = Job(
        job_type=JobType.SCREENING,
        input_data={"invalid_field": 123},
    )
    result = await worker.process(job)

    assert result.success is False
    assert "Invalid screening context" in result.error


async def test_screening_worker_returns_results_data(
    worker: ScreeningWorker,
    mock_orchestrator: AsyncMock,
) -> None:
    """ScreeningWorker result data should include serialized screening results."""
    mock_orchestrator.screen.return_value = [
        _make_screening_result("test/repo1", gate1_pass=True),
    ]

    job = Job(
        job_type=JobType.SCREENING,
        input_data={"pool_id": "pool-1", "candidates": [], "gate_level": "1"},
    )
    result = await worker.process(job)

    assert result.success is True
    assert "results" in result.data
    assert len(result.data["results"]) == 1
