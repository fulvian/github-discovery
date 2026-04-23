"""Tests for the FastAPI application factory."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    """Health endpoint should return 200 with status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_ready(client: TestClient) -> None:
    """Readiness endpoint should return 200 when app is initialized."""
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"


def test_app_has_cors_middleware(client: TestClient) -> None:
    """App should allow CORS preflight requests."""
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    # CORS middleware should respond (may be 200 or 204)
    assert response.status_code in (200, 204)
    assert "access-control-allow-origin" in response.headers


def test_health_has_request_id_header(client: TestClient) -> None:
    """Responses should include X-Request-ID header."""
    response = client.get("/health")
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0


def test_health_has_process_time_header(client: TestClient) -> None:
    """Responses should include X-Process-Time header."""
    response = client.get("/health")
    assert "x-process-time" in response.headers
    process_time = float(response.headers["x-process-time"])
    assert process_time >= 0


def test_custom_request_id_is_preserved(client: TestClient) -> None:
    """Custom X-Request-ID should be preserved in response."""
    custom_id = "my-custom-request-id-123"
    response = client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.headers["x-request-id"] == custom_id
