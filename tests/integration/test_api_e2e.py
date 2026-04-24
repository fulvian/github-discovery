"""API endpoint integration tests.

Tests FastAPI endpoints end-to-end using httpx.AsyncClient with ASGITransport.
Verifies HTTP layer: status codes, request/response models, error handling.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


class TestHealthEndpoints:
    """Test health and readiness endpoints."""

    async def test_health_endpoint(self, api_client: AsyncClient) -> None:
        """GET /health returns 200 with status ok."""
        response = await api_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    async def test_ready_endpoint(self, api_client: AsyncClient) -> None:
        """GET /ready returns 200 after lifespan initializes app state."""
        response = await api_client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"


class TestDiscoveryEndpoints:
    """Test discovery API endpoints."""

    async def test_discover_endpoint(self, api_client: AsyncClient) -> None:
        """POST /api/v1/discover starts a job and returns 202."""
        payload = {
            "query": "static analysis python",
            "channels": ["search"],
            "max_candidates": 50,
        }
        response = await api_client.post("/api/v1/discover", json=payload)
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

    async def test_discover_job_status_not_found(self, api_client: AsyncClient) -> None:
        """GET /api/v1/discover/{id} returns 404 for unknown job."""
        response = await api_client.get("/api/v1/discover/nonexistent-job-id")
        assert response.status_code == 404

    async def test_discover_job_status_after_create(self, api_client: AsyncClient) -> None:
        """GET /api/v1/discover/{id} returns status for created job."""
        payload = {"query": "test query"}
        create_response = await api_client.post("/api/v1/discover", json=payload)
        job_id = create_response.json()["job_id"]

        status_response = await api_client.get(f"/api/v1/discover/{job_id}")
        assert status_response.status_code == 200
        data = status_response.json()
        assert data["job_id"] == job_id

    async def test_discover_validates_empty_query(self, api_client: AsyncClient) -> None:
        """POST /api/v1/discover rejects empty query with 422."""
        payload = {"query": ""}
        response = await api_client.post("/api/v1/discover", json=payload)
        assert response.status_code == 422

    async def test_candidates_endpoint_missing_pool(self, api_client: AsyncClient) -> None:
        """GET /api/v1/candidates returns 404 for unknown pool."""
        response = await api_client.get(
            "/api/v1/candidates",
            params={"pool_id": "nonexistent-pool"},
        )
        assert response.status_code == 404


class TestScreeningEndpoints:
    """Test screening API endpoints."""

    async def test_screen_endpoint(self, api_client: AsyncClient) -> None:
        """POST /api/v1/screen starts a screening job."""
        payload = {"pool_id": "test-pool", "gate_level": "1"}
        response = await api_client.post("/api/v1/screen", json=payload)
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert data["pool_id"] == "test-pool"

    async def test_screen_job_status_not_found(self, api_client: AsyncClient) -> None:
        """GET /api/v1/screen/{id} returns 404 for unknown job."""
        response = await api_client.get("/api/v1/screen/nonexistent-job-id")
        assert response.status_code == 404

    async def test_shortlist_endpoint(self, api_client: AsyncClient) -> None:
        """GET /api/v1/shortlist returns results for a pool."""
        response = await api_client.get(
            "/api/v1/shortlist",
            params={"pool_id": "test-pool"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["pool_id"] == "test-pool"


class TestAssessmentEndpoints:
    """Test assessment API endpoints."""

    async def test_assess_endpoint_rejects_without_screening(
        self,
        api_client: AsyncClient,
    ) -> None:
        """POST /api/v1/assess rejects repos that haven't been screened (422)."""
        payload = {
            "repo_urls": ["https://github.com/test/repo"],
        }
        response = await api_client.post("/api/v1/assess", json=payload)
        # Without any completed screening jobs, should be rejected
        assert response.status_code == 422

    async def test_assess_job_status_not_found(self, api_client: AsyncClient) -> None:
        """GET /api/v1/assess/{id} returns 404 for unknown job."""
        response = await api_client.get("/api/v1/assess/nonexistent-job-id")
        assert response.status_code == 404


class TestRankingEndpoints:
    """Test ranking API endpoints."""

    async def test_rank_endpoint(self, api_client: AsyncClient) -> None:
        """GET /api/v1/rank returns ranked results (may be empty)."""
        response = await api_client.get("/api/v1/rank")
        assert response.status_code == 200
        data = response.json()
        assert "ranked_repos" in data
        assert "pagination" in data

    async def test_rank_endpoint_with_domain_filter(self, api_client: AsyncClient) -> None:
        """GET /api/v1/rank accepts domain filter parameter."""
        response = await api_client.get(
            "/api/v1/rank",
            params={"domain": "library"},
        )
        assert response.status_code == 200

    async def test_rank_specific_repo(self, api_client: AsyncClient) -> None:
        """GET /api/v1/rank/{repo} returns scoring for a specific repo."""
        response = await api_client.get("/api/v1/rank/test-org/test-repo")
        assert response.status_code == 200
        data = response.json()
        assert data["repo"] == "test-org/test-repo"

    async def test_explain_endpoint(self, api_client: AsyncClient) -> None:
        """GET /api/v1/explain/{repo} returns explainability report."""
        response = await api_client.get("/api/v1/explain/test-org/test-repo")
        assert response.status_code == 200
        data = response.json()
        assert data["repo"] == "test-org/test-repo"
        assert "detail_level" in data

    async def test_explain_endpoint_full_detail(self, api_client: AsyncClient) -> None:
        """GET /api/v1/explain/{repo} with detail_level=full."""
        response = await api_client.get(
            "/api/v1/explain/test-org/test-repo",
            params={"detail_level": "full"},
        )
        assert response.status_code == 200


class TestExportEndpoints:
    """Test export API endpoints."""

    async def test_export_json(self, api_client: AsyncClient) -> None:
        """POST /api/v1/export with format=json."""
        payload = {"session_id": "test-session", "format": "json"}
        response = await api_client.post("/api/v1/export", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "json"

    async def test_export_csv(self, api_client: AsyncClient) -> None:
        """POST /api/v1/export with format=csv."""
        payload = {"session_id": "test-session", "format": "csv"}
        response = await api_client.post("/api/v1/export", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "csv"

    async def test_export_markdown(self, api_client: AsyncClient) -> None:
        """POST /api/v1/export with format=markdown."""
        payload = {"session_id": "test-session", "format": "markdown"}
        response = await api_client.post("/api/v1/export", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "markdown"


class TestAPIErrorHandling:
    """Test API error handling."""

    async def test_404_for_unknown_routes(self, api_client: AsyncClient) -> None:
        """Unknown routes return 404."""
        response = await api_client.get("/api/v1/nonexistent")
        assert response.status_code == 404

    async def test_invalid_json_body(self, api_client: AsyncClient) -> None:
        """Invalid JSON body returns 422."""
        response = await api_client.post(
            "/api/v1/discover",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    async def test_method_not_allowed(self, api_client: AsyncClient) -> None:
        """Wrong HTTP method returns 405."""
        response = await api_client.delete("/api/v1/discover")
        assert response.status_code == 405


class TestAPIConcurrentRequests:
    """Test that concurrent API requests don't interfere."""

    async def test_concurrent_discover_jobs(self, api_client: AsyncClient) -> None:
        """Multiple concurrent discovery requests create separate jobs."""
        import asyncio

        payloads = [
            {"query": "test query concurrent"},
            {"query": "another query concurrent"},
            {"query": "third query concurrent"},
        ]

        tasks = [api_client.post("/api/v1/discover", json=payload) for payload in payloads]
        responses = await asyncio.gather(*tasks)

        job_ids = []
        for response in responses:
            assert response.status_code == 202
            job_ids.append(response.json()["job_id"])

        # All job IDs should be unique
        assert len(set(job_ids)) == len(job_ids)
