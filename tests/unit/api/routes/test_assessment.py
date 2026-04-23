"""Tests for the assessment API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from github_discovery.workers.types import JobStatus
from tests.unit.api.routes.conftest import make_assessment_job


def test_start_assessment_returns_202(client: TestClient) -> None:
    """POST /api/v1/assess should return 202 Accepted."""
    response = client.post(
        "/api/v1/assess",
        json={"repo_urls": ["https://github.com/test/repo"]},
    )
    assert response.status_code == 202


def test_start_assessment_returns_job_id(client: TestClient) -> None:
    """POST /api/v1/assess should return a job_id in the response."""
    response = client.post(
        "/api/v1/assess",
        json={"repo_urls": ["https://github.com/test/repo"]},
    )
    data = response.json()
    assert "job_id" in data
    assert isinstance(data["job_id"], str)
    assert len(data["job_id"]) > 0
    assert data["status"] == "pending"
    assert data["total_repos"] == 1


def test_get_assessment_status_pending(
    client: TestClient,
    mock_job_store: AsyncMock,
) -> None:
    """GET /api/v1/assess/{job_id} should return pending job status."""
    job = make_assessment_job(status=JobStatus.PENDING)
    mock_job_store.get = AsyncMock(return_value=job)

    response = client.get(f"/api/v1/assess/{job.job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job.job_id
    assert data["status"] == "pending"


def test_get_assessment_status_completed(
    client: TestClient,
    mock_job_store: AsyncMock,
) -> None:
    """GET /api/v1/assess/{job_id} should return completed job with results."""
    job = make_assessment_job(
        job_id="assess-done-1",
        status=JobStatus.COMPLETED,
        result={
            "total_repos": 5,
            "assessed": 4,
            "rejected_hard_gate": 1,
            "tokens_used": 15000,
        },
    )
    mock_job_store.get = AsyncMock(return_value=job)

    response = client.get("/api/v1/assess/assess-done-1")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["total_repos"] == 5
    assert data["assessed"] == 4
    assert data["rejected_hard_gate"] == 1
    assert data["tokens_used"] == 15000


def test_get_assessment_status_not_found(client: TestClient) -> None:
    """GET /api/v1/assess/{job_id} should return 404 for unknown job."""
    response = client.get("/api/v1/assess/nonexistent-job")
    assert response.status_code == 404


def test_start_assessment_with_dimensions(client: TestClient) -> None:
    """POST /api/v1/assess should accept dimensions parameter."""
    response = client.post(
        "/api/v1/assess",
        json={
            "repo_urls": ["https://github.com/test/repo"],
            "dimensions": ["code_quality", "testing"],
        },
    )
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "pending"


def test_start_assessment_with_budget(client: TestClient) -> None:
    """POST /api/v1/assess should accept budget_tokens parameter."""
    response = client.post(
        "/api/v1/assess",
        json={
            "repo_urls": ["https://github.com/test/repo"],
            "budget_tokens": 50000,
            "session_id": "session-budget",
        },
    )
    assert response.status_code == 202
    data = response.json()
    assert data["session_id"] == "session-budget"
