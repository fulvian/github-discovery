"""HTTP middleware for request tracing, timing, and rate limiting.

Adds X-Request-ID and X-Process-Time headers to every response,
and enforces per-client rate limits when configured.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import TYPE_CHECKING

import structlog
from starlette.requests import Request  # noqa: TC002
from starlette.responses import JSONResponse, Response

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = structlog.get_logger("github_discovery.api.middleware")


class RateLimiter:
    """Token bucket rate limiter per client key.

    Tracks request timestamps per key and enforces a maximum number
    of requests within a sliding time window.
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60) -> None:
        """Initialize rate limiter with request limit and time window."""
        self._max = max_requests
        self._window = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        """Check if a request from the given key is allowed.

        Sliding window: removes timestamps older than the window,
        then checks if the count is under the limit.

        Args:
            key: Client identifier (typically IP address).

        Returns:
            True if the request is allowed, False if rate limited.
        """
        now = time.monotonic()
        self._requests[key] = [t for t in self._requests[key] if now - t < self._window]
        if len(self._requests[key]) >= self._max:
            return False
        self._requests[key].append(now)
        return True


async def request_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Add or generate a request ID and attach it to the response.

    Reads the X-Request-ID header from the incoming request or
    generates a new UUID4. Stores it in ``request.state.request_id``
    and adds it to the response headers.
    """
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


async def timing_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Measure request processing time and add X-Process-Time header.

    Uses ``time.perf_counter()`` for high-resolution timing. The
    value is formatted to 4 decimal places (milliseconds).
    """
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    response.headers["X-Process-Time"] = f"{elapsed:.4f}"
    return response


async def rate_limit_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Rate limit middleware — skips if rate_limit_per_minute is 0.

    Uses the RateLimiter stored on ``app.state.rate_limiter`` and
    the settings on ``app.state.settings`` to determine limits.
    """
    settings = request.app.state.settings
    if not settings.api.rate_limit_per_minute:
        return await call_next(request)

    limiter: RateLimiter = request.app.state.rate_limiter
    client_ip = request.client.host if request.client else "unknown"

    if not limiter.is_allowed(client_ip):
        return JSONResponse(
            status_code=429,
            content={"error": "RateLimitExceeded", "message": "Too many requests"},
        )
    return await call_next(request)
