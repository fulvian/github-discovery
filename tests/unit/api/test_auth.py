"""Tests for API key authentication."""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from github_discovery.api.auth import verify_api_key
from github_discovery.config import APISettings, Settings


def _make_auth_app(api_key: str) -> FastAPI:
    """Create a minimal FastAPI app with auth dependency for testing.

    Args:
        api_key: Set the configured API key. Empty string disables auth.
    """
    app = FastAPI()

    settings = Settings(
        api=APISettings(
            api_key=api_key,
            job_store_path=":memory:",
        ),
    )
    app.state.settings = settings

    @app.get("/protected")
    async def protected(_user: None = Depends(verify_api_key)) -> dict[str, str]:
        return {"status": "ok"}

    return app


class TestVerifyApiKey:
    """Tests for API key authentication."""

    def test_auth_skipped_when_no_key_configured(self) -> None:
        """When no API key is configured, all requests should pass."""
        app = _make_auth_app(api_key="")
        with TestClient(app) as client:
            resp = client.get("/protected")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

    def test_auth_succeeds_with_valid_key(self) -> None:
        """Valid API key in header should authenticate successfully."""
        app = _make_auth_app(api_key="test-secret-key")
        with TestClient(app) as client:
            resp = client.get(
                "/protected",
                headers={"X-API-Key": "test-secret-key"},
            )
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

    def test_auth_fails_with_invalid_key(self) -> None:
        """Wrong API key should return 401."""
        app = _make_auth_app(api_key="correct-key")
        with TestClient(app) as client:
            resp = client.get(
                "/protected",
                headers={"X-API-Key": "wrong-key"},
            )
            assert resp.status_code == 401
            assert resp.json()["detail"] == "Invalid API key"

    def test_auth_fails_with_missing_key_when_required(self) -> None:
        """Missing API key header should return 401 when auth is configured."""
        app = _make_auth_app(api_key="required-key")
        with TestClient(app) as client:
            resp = client.get("/protected")
            assert resp.status_code == 401

    def test_auth_case_sensitive(self) -> None:
        """API key comparison should be case-sensitive."""
        app = _make_auth_app(api_key="SecretKey")
        with TestClient(app) as client:
            resp = client.get(
                "/protected",
                headers={"X-API-Key": "secretkey"},
            )
            assert resp.status_code == 401
