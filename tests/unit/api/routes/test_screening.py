"""Tests for the screening API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from github_discovery.workers.types import JobStatus
from tests.unit.api.routes.conftest import make_screening_job


def test_start_screening_returns_202(client: TestClient) -> None:
    """POST /api/v1/screen should return 202 Accepted."""
    response = client.post(
        "/api/v1/screen",
        json={"pool_id": "pool-abc"},
    )
    assert response.status_code == 202


def test_start_screening_returns_job_id(client: TestClient) -> None:
    """POST /api/v1/screen should return a job_id in the response."""
    response = client.post(
        "/api/v1/screen",
        json={"pool_id": "pool-abc"},
    )
    data = response.json()
    assert "job_id" in data
    assert isinstance(data["job_id"], str)
    assert len(data["job_id"]) > 0
    assert data["status"] == "pending"
    assert data["pool_id"] == "pool-abc"


def test_get_screening_status_pending(
    client: TestClient,
    mock_job_store: AsyncMock,
) -> None:
    """GET /api/v1/screen/{job_id} should return pending job status."""
    job = make_screening_job(status=JobStatus.PENDING)
    mock_job_store.get = AsyncMock(return_value=job)

    response = client.get(f"/api/v1/screen/{job.job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job.job_id
    assert data["status"] == "pending"


def test_get_screening_status_completed(
    client: TestClient,
    mock_job_store: AsyncMock,
) -> None:
    """GET /api/v1/screen/{job_id} should return completed job with results."""
    job = make_screening_job(
        job_id="screen-done-1",
        status=JobStatus.COMPLETED,
        result={
            "total_screened": 100,
            "passed": 30,
            "failed": 70,
        },
    )
    mock_job_store.get = AsyncMock(return_value=job)

    response = client.get("/api/v1/screen/screen-done-1")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["total_screened"] == 100
    assert data["passed"] == 30
    assert data["failed"] == 70


def test_get_screening_status_not_found(client: TestClient) -> None:
    """GET /api/v1/screen/{job_id} should return 404 for unknown job."""
    response = client.get("/api/v1/screen/nonexistent-job")
    assert response.status_code == 404


def test_get_shortlist_with_pool_id(client: TestClient) -> None:
    """GET /api/v1/shortlist should return results with pool_id filter."""
    response = client.get(
        "/api/v1/shortlist",
        params={"pool_id": "pool-abc"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["pool_id"] == "pool-abc"


def test_get_shortlist_with_min_score(client: TestClient) -> None:
    """GET /api/v1/shortlist should accept min_score parameter."""
    response = client.get(
        "/api/v1/shortlist",
        params={"pool_id": "pool-abc", "min_score": 0.7},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["min_score"] == 0.7


def test_start_screening_with_gate_level(client: TestClient) -> None:
    """POST /api/v1/screen should accept gate_level parameter."""
    response = client.post(
        "/api/v1/screen",
        json={"pool_id": "pool-abc", "gate_level": "2"},
    )
    assert response.status_code == 202
    data = response.json()
    assert data["gate_level"] == "2"


def test_start_screening_with_custom_thresholds(client: TestClient) -> None:
    """POST /api/v1/screen should accept custom gate thresholds."""
    response = client.post(
        "/api/v1/screen",
        json={
            "pool_id": "pool-abc",
            "gate_level": "1",
            "min_gate1_score": 0.6,
            "min_gate2_score": 0.7,
            "session_id": "session-123",
        },
    )
    assert response.status_code == 202
    data = response.json()
    assert data["gate_level"] == "1"
    assert data["session_id"] == "session-123"
