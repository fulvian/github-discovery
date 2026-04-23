"""Tests for rate limiter and rate limit middleware."""

from __future__ import annotations

import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from github_discovery.api.middleware import RateLimiter, rate_limit_middleware
from github_discovery.config import APISettings, Settings

# --- RateLimiter unit tests ---


class TestRateLimiter:
    """Token bucket rate limiter tests."""

    def test_rate_limiter_allows_under_limit(self) -> None:
        """Requests under the limit should be allowed."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert limiter.is_allowed("client-1") is True

    def test_rate_limiter_blocks_over_limit(self) -> None:
        """Requests exceeding the limit should be blocked."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            limiter.is_allowed("client-1")
        # 4th request should be blocked
        assert limiter.is_allowed("client-1") is False

    def test_rate_limiter_resets_after_window(self) -> None:
        """After the window expires, requests should be allowed again."""
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        limiter.is_allowed("client-1")
        limiter.is_allowed("client-1")
        assert limiter.is_allowed("client-1") is False

        # Wait for window to expire
        time.sleep(1.1)
        assert limiter.is_allowed("client-1") is True

    def test_rate_limiter_independent_per_key(self) -> None:
        """Different client keys should have independent limits."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.is_allowed("client-a")
        limiter.is_allowed("client-a")
        assert limiter.is_allowed("client-a") is False

        # client-b should still be allowed
        assert limiter.is_allowed("client-b") is True

    def test_rate_limiter_default_values(self) -> None:
        """Default constructor should create a 60-req/60s limiter."""
        limiter = RateLimiter()
        # Should allow 60 requests
        for _ in range(60):
            assert limiter.is_allowed("client-1") is True
        # 61st should be blocked
        assert limiter.is_allowed("client-1") is False


# --- rate_limit_middleware tests ---


def _make_test_app(rate_limit: int) -> FastAPI:
    """Create a minimal FastAPI app with rate_limit_middleware."""

    app = FastAPI()

    settings = Settings(
        api=APISettings(
            rate_limit_per_minute=rate_limit,
            job_store_path=":memory:",
        ),
    )

    # Set up app.state with settings and rate limiter
    app.state.settings = settings
    app.state.rate_limiter = RateLimiter(
        max_requests=settings.api.rate_limit_per_minute,
    )

    @app.get("/test")
    async def test_endpoint() -> dict[str, str]:
        return {"status": "ok"}

    app.middleware("http")(rate_limit_middleware)

    return app


class TestRateLimitMiddleware:
    """Tests for rate_limit_middleware integration."""

    def test_passes_when_disabled(self) -> None:
        """When rate_limit_per_minute is 0, all requests should pass."""
        app = _make_test_app(rate_limit=0)
        with TestClient(app) as client:
            for _ in range(10):
                resp = client.get("/test")
                assert resp.status_code == 200

    def test_returns_429_when_exceeded(self) -> None:
        """Requests exceeding the limit should get 429 responses."""
        app = _make_test_app(rate_limit=3)
        with TestClient(app) as client:
            # Use up the limit
            for _ in range(3):
                resp = client.get("/test")
                assert resp.status_code == 200

            # Next request should be rate limited
            resp = client.get("/test")
            assert resp.status_code == 429
            assert resp.json()["error"] == "RateLimitExceeded"

    def test_passes_when_under_limit(self) -> None:
        """Requests within the limit should pass normally."""
        app = _make_test_app(rate_limit=10)
        with TestClient(app) as client:
            resp = client.get("/test")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

    def test_rate_limit_uses_client_ip(self) -> None:
        """Rate limiting should be based on client IP."""
        app = _make_test_app(rate_limit=2)
        with TestClient(app) as client:
            # Use up limit for the default test client IP
            client.get("/test")
            client.get("/test")
            resp = client.get("/test")
            assert resp.status_code == 429
