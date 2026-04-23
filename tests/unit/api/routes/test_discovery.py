"""Tests for the discovery API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from github_discovery.models.candidate import CandidatePool
from github_discovery.workers.types import JobStatus
from tests.unit.api.routes.conftest import make_discovery_job


def test_start_discovery_returns_202(client: TestClient) -> None:
    """POST /api/v1/discover should return 202 Accepted."""
    response = client.post(
        "/api/v1/discover",
        json={"query": "static analysis python"},
    )
    assert response.status_code == 202


def test_start_discovery_returns_job_id(client: TestClient) -> None:
    """POST /api/v1/discover should return a job_id in the response."""
    response = client.post(
        "/api/v1/discover",
        json={"query": "static analysis python"},
    )
    data = response.json()
    assert "job_id" in data
    assert isinstance(data["job_id"], str)
    assert len(data["job_id"]) > 0
    assert data["status"] == "pending"


def test_get_discovery_status_pending(
    client: TestClient,
    mock_job_store: AsyncMock,
) -> None:
    """GET /api/v1/discover/{job_id} should return pending job status."""
    job = make_discovery_job(status=JobStatus.PENDING)
    mock_job_store.get = AsyncMock(return_value=job)

    response = client.get(f"/api/v1/discover/{job.job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job.job_id
    assert data["status"] == "pending"


def test_get_discovery_status_completed(
    client: TestClient,
    mock_job_store: AsyncMock,
) -> None:
    """GET /api/v1/discover/{job_id} should return completed job with results."""
    job = make_discovery_job(
        job_id="completed-job-1",
        status=JobStatus.COMPLETED,
        result={
            "total_candidates": 42,
            "pool_id": "pool-xyz",
            "channels_used": ["search"],
        },
    )
    mock_job_store.get = AsyncMock(return_value=job)

    response = client.get("/api/v1/discover/completed-job-1")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["total_candidates"] == 42
    assert data["pool_id"] == "pool-xyz"


def test_get_discovery_status_not_found(client: TestClient) -> None:
    """GET /api/v1/discover/{job_id} should return 404 for unknown job."""
    response = client.get("/api/v1/discover/nonexistent-job")
    assert response.status_code == 404


def test_get_candidates_with_pool_id(
    client: TestClient,
    mock_pool_manager: AsyncMock,
) -> None:
    """GET /api/v1/candidates should return pool info when pool exists."""
    pool = CandidatePool(
        pool_id="pool-abc",
        query="test query",
        candidates=[],
    )
    mock_pool_manager.get_pool = AsyncMock(return_value=pool)

    response = client.get("/api/v1/candidates", params={"pool_id": "pool-abc"})
    assert response.status_code == 200
    data = response.json()
    assert data["pool_id"] == "pool-abc"
    assert data["total_candidates"] == 0


def test_get_candidates_missing_pool_id(client: TestClient) -> None:
    """GET /api/v1/candidates without pool_id should return 422 (validation error)."""
    response = client.get("/api/v1/candidates")
    assert response.status_code == 422


def test_get_candidates_pool_not_found(client: TestClient) -> None:
    """GET /api/v1/candidates with nonexistent pool should return 404."""
    response = client.get(
        "/api/v1/candidates",
        params={"pool_id": "nonexistent-pool"},
    )
    assert response.status_code == 404


def test_start_discovery_with_all_params(client: TestClient) -> None:
    """POST /api/v1/discover should accept all DiscoveryQuery fields."""
    response = client.post(
        "/api/v1/discover",
        json={
            "query": "python testing framework",
            "channels": ["search", "registry"],
            "max_candidates": 200,
            "domain": "test_tool",
            "session_id": "session-xyz",
            "languages": ["python", "rust"],
        },
    )
    assert response.status_code == 202
    data = response.json()
    assert data["session_id"] == "session-xyz"
