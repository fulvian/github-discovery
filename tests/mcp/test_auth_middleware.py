"""Tests for MCP API key authentication middleware (Wave J4).

Verifies that:
1. Requests without Bearer token are rejected when API keys configured
2. Requests with invalid token are rejected (403)
3. Requests with valid token succeed
4. /health endpoint bypasses auth
5. No-op middleware when no API keys configured
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from github_discovery.mcp.server import _build_auth_middleware


class TestAuthMiddleware:
    """Test API key authentication middleware."""

    def test_noop_middleware_when_no_keys(self) -> None:
        """Returns no-op middleware when no API keys configured."""
        MiddlewareClass = _build_auth_middleware([])
        assert MiddlewareClass is not None

    def test_auth_middleware_rejects_missing_token(self) -> None:
        """Middleware rejects requests without Bearer token."""
        MiddlewareClass = _build_auth_middleware(["secret-key-123"])
        assert MiddlewareClass is not None

        from starlette.requests import Request
        from starlette.responses import JSONResponse

        # Create a mock request without auth header
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/mcp",
            "headers": [],
        }

        async def _call_next(request):
            return JSONResponse({"ok": True})

        import asyncio

        async def _test():
            middleware = MiddlewareClass(AsyncMock())
            request = Request(scope)
            response = await middleware.dispatch(request, _call_next)
            assert response.status_code == 401

        asyncio.run(_test())

    def test_auth_middleware_allows_health(self) -> None:
        """Middleware allows /health endpoint without auth."""
        MiddlewareClass = _build_auth_middleware(["secret-key-123"])
        assert MiddlewareClass is not None

        from starlette.requests import Request
        from starlette.responses import JSONResponse

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "headers": [],
        }

        async def _call_next(request):
            return JSONResponse({"ok": True})

        import asyncio

        async def _test():
            middleware = MiddlewareClass(AsyncMock())
            request = Request(scope)
            response = await middleware.dispatch(request, _call_next)
            assert response.status_code == 200

        asyncio.run(_test())

    def test_auth_middleware_rejects_invalid_key(self) -> None:
        """Middleware rejects invalid API key with 403."""
        MiddlewareClass = _build_auth_middleware(["valid-key"])
        assert MiddlewareClass is not None

        from starlette.requests import Request
        from starlette.responses import JSONResponse

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/mcp",
            "headers": [
                (b"authorization", b"Bearer invalid-key"),
            ],
        }

        async def _call_next(request):
            return JSONResponse({"ok": True})

        import asyncio

        async def _test():
            middleware = MiddlewareClass(AsyncMock())
            request = Request(scope)
            response = await middleware.dispatch(request, _call_next)
            assert response.status_code == 403

        asyncio.run(_test())

    def test_auth_middleware_allows_valid_key(self) -> None:
        """Middleware allows requests with valid Bearer token."""
        MiddlewareClass = _build_auth_middleware(["valid-key"])
        assert MiddlewareClass is not None

        from starlette.requests import Request
        from starlette.responses import JSONResponse

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/mcp",
            "headers": [
                (b"authorization", b"Bearer valid-key"),
            ],
        }

        async def _call_next(request):
            return JSONResponse({"ok": True})

        import asyncio

        async def _test():
            middleware = MiddlewareClass(AsyncMock())
            request = Request(scope)
            response = await middleware.dispatch(request, _call_next)
            assert response.status_code == 200

        asyncio.run(_test())
