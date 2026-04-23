"""Tests for the ranking API routes."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_rank_returns_200(client: TestClient) -> None:
    """GET /api/v1/rank should return 200 with stub response."""
    response = client.get("/api/v1/rank")
    assert response.status_code == 200


def test_rank_with_domain_filter(client: TestClient) -> None:
    """GET /api/v1/rank should accept domain filter parameter."""
    response = client.get("/api/v1/rank", params={"domain": "library"})
    assert response.status_code == 200
    data = response.json()
    assert data["domain"] == "library"


def test_rank_with_custom_params(client: TestClient) -> None:
    """GET /api/v1/rank should accept custom scoring parameters."""
    response = client.get(
        "/api/v1/rank",
        params={
            "domain": "cli",
            "min_confidence": 0.5,
            "min_value_score": 0.1,
            "max_results": 10,
            "session_id": "sess-123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["domain"] == "cli"
    assert data["min_confidence"] == 0.5
    assert data["min_value_score"] == 0.1
    assert data["max_results"] == 10
    assert data["session_id"] == "sess-123"


def test_get_repo_detail(client: TestClient) -> None:
    """GET /api/v1/rank/{owner}/{repo} should return stub response."""
    response = client.get("/api/v1/rank/owner/repo")
    assert response.status_code == 200
    data = response.json()
    assert data["repo"] == "owner/repo"
    assert data["scoring"] is None


def test_get_repo_detail_with_nesting(client: TestClient) -> None:
    """GET /api/v1/rank/{repo:path} should handle nested org/repo paths."""
    response = client.get("/api/v1/rank/my-org/my-awesome-repo")
    assert response.status_code == 200
    data = response.json()
    assert data["repo"] == "my-org/my-awesome-repo"


def test_explain_repo(client: TestClient) -> None:
    """GET /api/v1/explain/{owner}/{repo} should return stub response."""
    response = client.get("/api/v1/explain/owner/repo")
    assert response.status_code == 200
    data = response.json()
    assert data["repo"] == "owner/repo"
    assert data["report"] is None
    assert data["detail_level"] == "summary"


def test_explain_repo_with_detail_level(client: TestClient) -> None:
    """GET /api/v1/explain/{repo} should accept detail_level parameter."""
    response = client.get(
        "/api/v1/explain/owner/repo",
        params={"detail_level": "full"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["detail_level"] == "full"


def test_rank_pagination(client: TestClient) -> None:
    """GET /api/v1/rank should accept pagination parameters."""
    response = client.get(
        "/api/v1/rank",
        params={"page": 2, "page_size": 10},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 2
    assert data["page_size"] == 10
    assert data["pagination"]["page"] == 2
    assert data["pagination"]["page_size"] == 10
