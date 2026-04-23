"""Tests for API error handlers."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from github_discovery.api.errors import register_error_handlers
from github_discovery.exceptions import (
    BudgetExceededError,
    DiscoveryError,
    HardGateViolationError,
)


def _create_test_app() -> FastAPI:
    """Create a minimal FastAPI app with error handlers and test routes."""
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/raise-domain")
    async def raise_domain_error():
        raise DiscoveryError("Discovery failed", context={"query": "test"})

    @app.get("/raise-hard-gate")
    async def raise_hard_gate_error():
        raise HardGateViolationError(
            "Gate blocked",
            repo_url="test/repo",
            gate_passed=1,
            gate_required=2,
        )

    @app.get("/raise-budget")
    async def raise_budget_error():
        raise BudgetExceededError(
            "Token budget exceeded",
            budget_type="daily",
            budget_limit=500000,
            budget_used=510000,
        )

    @app.get("/raise-generic")
    async def raise_generic_error():
        raise ValueError("Something unexpected")

    return app


@pytest.fixture
def error_client():
    """Create a TestClient for error handler testing."""
    app = _create_test_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_domain_error_returns_400(error_client: TestClient) -> None:
    """Domain errors should return 400."""
    response = error_client.get("/raise-domain")
    assert response.status_code == 400


def test_hard_gate_violation_returns_422(error_client: TestClient) -> None:
    """Hard gate violations should return 422."""
    response = error_client.get("/raise-hard-gate")
    assert response.status_code == 422


def test_budget_exceeded_returns_429(error_client: TestClient) -> None:
    """Budget exceeded should return 429."""
    response = error_client.get("/raise-budget")
    assert response.status_code == 429


def test_generic_error_returns_500(error_client: TestClient) -> None:
    """Generic exceptions should return 500."""
    response = error_client.get("/raise-generic")
    assert response.status_code == 500


def test_error_response_has_correct_shape(error_client: TestClient) -> None:
    """Error responses should have error, message, and optionally context."""
    response = error_client.get("/raise-domain")
    data = response.json()

    assert "error" in data
    assert "message" in data
    assert data["error"] == "DiscoveryError"
    assert "Discovery failed" in data["message"]
    assert "context" in data
    assert data["context"]["query"] == "test"


def test_generic_error_response_shape(error_client: TestClient) -> None:
    """Generic error responses should not leak internal details."""
    response = error_client.get("/raise-generic")
    data = response.json()

    assert data["error"] == "InternalServerError"
    assert data["message"] == "An unexpected error occurred"
