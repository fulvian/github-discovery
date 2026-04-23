"""Tests for AssessmentWorker."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from github_discovery.models.assessment import DeepAssessmentResult
from github_discovery.workers.assessment_worker import AssessmentWorker
from github_discovery.workers.types import Job, JobType


def _candidate_dict(name: str) -> dict[str, object]:
    """Create a minimal RepoCandidate dict for test input_data."""
    return {
        "full_name": name,
        "url": f"https://github.com/{name}",
        "html_url": f"https://github.com/{name}",
        "api_url": f"https://api.github.com/repos/{name}",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        "owner_login": name.split("/", maxsplit=1)[0],
        "source_channel": "search",
    }


@pytest.fixture
def mock_store() -> AsyncMock:
    """Create a mock JobStore."""
    return AsyncMock()


@pytest.fixture
def mock_orchestrator() -> AsyncMock:
    """Create a mock AssessmentOrchestrator."""
    orch = AsyncMock()
    orch.assess = AsyncMock()
    return orch


@pytest.fixture
def worker(mock_store: AsyncMock, mock_orchestrator: AsyncMock) -> AssessmentWorker:
    """Create an AssessmentWorker with mock dependencies."""
    return AssessmentWorker(mock_store, mock_orchestrator)


async def test_assessment_worker_processes_job(
    worker: AssessmentWorker,
    mock_orchestrator: AsyncMock,
) -> None:
    """AssessmentWorker should call orchestrator.assess() and return result."""
    fake_result = DeepAssessmentResult(
        full_name="test/repo1",
        gate3_pass=True,
        overall_quality=0.8,
    )
    mock_orchestrator.assess.return_value = [fake_result]

    job = Job(
        job_type=JobType.ASSESSMENT,
        input_data={
            "candidates": [_candidate_dict("test/repo1")],
        },
    )
    result = await worker.process(job)

    assert result.success is True
    mock_orchestrator.assess.assert_called_once()


async def test_assessment_worker_returns_summary(
    worker: AssessmentWorker,
    mock_orchestrator: AsyncMock,
) -> None:
    """AssessmentWorker should return total_assessed, gate3_passed, from_cache."""
    mock_orchestrator.assess.return_value = [
        DeepAssessmentResult(full_name="test/repo1", gate3_pass=True, cached=False),
        DeepAssessmentResult(full_name="test/repo2", gate3_pass=False, cached=True),
        DeepAssessmentResult(full_name="test/repo3", gate3_pass=True, cached=True),
    ]

    job = Job(
        job_type=JobType.ASSESSMENT,
        input_data={
            "candidates": [_candidate_dict("test/repo1")],
        },
    )
    result = await worker.process(job)

    assert result.success is True
    assert result.data["total_assessed"] == 3
    assert result.data["gate3_passed"] == 2
    assert result.data["from_cache"] == 2


async def test_assessment_worker_empty_candidates_fails(
    worker: AssessmentWorker,
    mock_orchestrator: AsyncMock,
) -> None:
    """Empty candidates list should return a failed WorkerResult."""
    job = Job(
        job_type=JobType.ASSESSMENT,
        input_data={
            "candidates": [],
        },
    )
    result = await worker.process(job)

    assert result.success is False
    assert "No candidates" in result.error
    mock_orchestrator.assess.assert_not_called()


async def test_assessment_worker_handles_exception(
    worker: AssessmentWorker,
    mock_orchestrator: AsyncMock,
) -> None:
    """Orchestrator exception should return a failed WorkerResult."""
    mock_orchestrator.assess.side_effect = RuntimeError("LLM error")

    job = Job(
        job_type=JobType.ASSESSMENT,
        input_data={
            "candidates": [_candidate_dict("test/repo1")],
        },
    )
    result = await worker.process(job)

    assert result.success is False
    assert "Assessment failed" in result.error


async def test_assessment_worker_invalid_input(
    worker: AssessmentWorker,
    mock_orchestrator: AsyncMock,
) -> None:
    """Invalid input_data with no candidates should return a failed WorkerResult."""
    job = Job(
        job_type=JobType.ASSESSMENT,
        input_data={"not_a_field": "bad"},
    )
    result = await worker.process(job)

    assert result.success is False
    assert result.error is not None


async def test_assessment_worker_returns_results_data(
    worker: AssessmentWorker,
    mock_orchestrator: AsyncMock,
) -> None:
    """AssessmentWorker result data should include serialized results."""
    fake_result = DeepAssessmentResult(
        full_name="test/repo1",
        gate3_pass=True,
        overall_quality=0.85,
    )
    mock_orchestrator.assess.return_value = [fake_result]

    job = Job(
        job_type=JobType.ASSESSMENT,
        input_data={
            "candidates": [_candidate_dict("test/repo1")],
        },
    )
    result = await worker.process(job)

    assert result.success is True
    assert "results" in result.data
    results_list = result.data["results"]
    assert isinstance(results_list, list)
    assert len(results_list) == 1
