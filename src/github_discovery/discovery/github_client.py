"""Async client for GitHub REST API.

Provides rate limit awareness, retry with backoff, conditional
requests (ETag), and rigorous Link-header pagination. Uses
httpx.AsyncClient under the hood for connection pooling and HTTP/2.
"""

from __future__ import annotations

import asyncio
import contextlib
import random
import re
from collections.abc import Awaitable, Callable, Generator  # noqa: TC003
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from github_discovery.config import GitHubSettings  # noqa: TC001
from github_discovery.exceptions import (
    GitHubAuthError,
    GitHubFetchError,
    GitHubRateLimitError,
    GitHubServerError,
    RateLimitError,
)

logger = structlog.get_logger("github_discovery.discovery.github_client")

# GitHub API version header
_GITHUB_API_VERSION = "2022-11-28"
_GITHUB_ACCEPT = "application/vnd.github+json"

# Default thresholds
_RATE_LIMIT_LOW_WATERMARK = 10  # Wait when remaining < this (was 50 — too aggressive)
_SEARCH_RATE_LIMIT_LOW_WATERMARK = 3
_DEFAULT_PER_PAGE = 100
_DEFAULT_MAX_PAGES = 10
_RETRY_BACKOFF_BASE = 1.0  # seconds
_RETRY_MAX_ATTEMPTS = 5  # Increased from 3
_RETRY_MAX_WAIT = 60.0  # Max seconds to wait between retries
_JITTER_FACTOR = 0.5  # Random jitter: ±50% of wait time

# HTTP status codes
_HTTP_OK_MIN = 200
_HTTP_OK_MAX = 300
_HTTP_UNAUTHORIZED = 401
_HTTP_FORBIDDEN = 403
_HTTP_TOO_MANY_REQUESTS = 429
_HTTP_SERVER_ERROR_MIN = 500
_HTTP_NOT_MODIFIED = 304

# Regex to parse Link header
_LINK_NEXT_RE = re.compile(r'<([^>]+)>;\s*rel="next"')


class _BearerAuth(httpx.Auth):
    """httpx Auth that adds Bearer token to every request."""

    def __init__(self, token: str) -> None:
        """Store the bearer token."""
        self._token = token

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        """Add Authorization header and yield the request."""
        request.headers["Authorization"] = f"Bearer {self._token}"
        yield request


class GitHubRestClient:
    """Async client for GitHub REST API with rate limit awareness.

    Features:
    - Bearer token authentication via httpx.Auth
    - Automatic transport-level retries (AsyncHTTPTransport)
    - Rate limit tracking via response event hooks
    - Conditional requests (If-None-Match / ETag)
    - Link-header pagination with safety limits
    - Separate rate limit awareness for search endpoints (30/min)
      and code search endpoints (10/min)
    """

    def __init__(self, settings: GitHubSettings) -> None:
        """Initialize the client with GitHub settings."""
        self._settings = settings
        self._base_url = settings.api_base_url.rstrip("/")

        # Rate limit state
        self._core_remaining: int | None = None
        self._core_reset_at: datetime | None = None
        self._search_remaining: int | None = None
        self._search_reset_at: datetime | None = None

        auth = _BearerAuth(settings.token) if settings.token else None
        transport = httpx.AsyncHTTPTransport(retries=3)

        self._client = httpx.AsyncClient(
            auth=auth,
            transport=transport,
            headers={
                "Accept": _GITHUB_ACCEPT,
                "X-GitHub-Api-Version": _GITHUB_API_VERSION,
            },
            timeout=settings.request_timeout,
            event_hooks={
                "response": [self._track_rate_limits],
            },
        )

    # --- Rate limit tracking ---

    async def _track_rate_limits(self, response: httpx.Response) -> None:
        """Event hook: extract rate limit headers from every response."""
        remaining = response.headers.get("x-ratelimit-remaining")
        reset = response.headers.get("x-ratelimit-reset")

        if remaining is not None:
            self._core_remaining = int(remaining)
        if reset is not None:
            with contextlib.suppress(ValueError, OSError):
                self._core_reset_at = datetime.fromtimestamp(int(reset), tz=UTC)

        # Detect search vs core by URL path
        url_path = str(response.url.path)
        if "/search/" in url_path:
            if remaining is not None:
                self._search_remaining = int(remaining)
            if reset is not None:
                with contextlib.suppress(ValueError, OSError):
                    self._search_reset_at = datetime.fromtimestamp(int(reset), tz=UTC)

    async def _await_if_rate_limited(self, *, is_search: bool = False) -> None:
        """Async wait if rate limit is near exhaustion.

        Instead of raising, this method waits until the rate limit resets
        or until a safe number of requests is available. Uses exponential
        backoff with jitter to avoid thundering herd.
        """
        if is_search:
            remaining = self._search_remaining
            reset_at = self._search_reset_at
            watermark = _SEARCH_RATE_LIMIT_LOW_WATERMARK
        else:
            remaining = self._core_remaining
            reset_at = self._core_reset_at
            watermark = _RATE_LIMIT_LOW_WATERMARK

        if remaining is None:
            # Never checked — assume we're fine
            return

        if remaining >= watermark:
            return

        # Rate limit is low. Determine the wait time.
        wait_seconds: float

        if reset_at is not None:
            # GitHub told us when it resets — wait until then
            now = datetime.now(tz=UTC)
            if reset_at > now:
                wait_seconds = (reset_at - now).total_seconds()
                logger.info(
                    "github_rate_limit_low_awaiting_reset",
                    remaining=remaining,
                    reset_at=reset_at.isoformat(),
                    wait_seconds=wait_seconds,
                    is_search=is_search,
                )
                await asyncio.sleep(min(wait_seconds, _RETRY_MAX_WAIT))
        else:
            # No reset time known — use exponential backoff
            wait_seconds = _RETRY_BACKOFF_BASE
            logger.info(
                "github_rate_limit_low_using_backoff",
                remaining=remaining,
                wait_seconds=wait_seconds,
                is_search=is_search,
            )
            await asyncio.sleep(wait_seconds)

    def _check_rate_limit(self, *, is_search: bool = False) -> bool:
        """Check if rate limit is low (for synchronous pre-request guard).

        Returns True if safe to proceed, False if rate limited.
        Use _await_if_rate_limited() for async waiting behavior.
        """
        if is_search:
            remaining = self._search_remaining
            watermark = _SEARCH_RATE_LIMIT_LOW_WATERMARK
        else:
            remaining = self._core_remaining
            watermark = _RATE_LIMIT_LOW_WATERMARK

        if remaining is not None and remaining < watermark:
            reset_at = (
                self._search_reset_at.isoformat()
                if is_search and self._search_reset_at
                else self._core_reset_at.isoformat()
                if self._core_reset_at
                else "unknown"
            )
            logger.warning(
                "github_rate_limit_low",
                remaining=remaining,
                watermark=watermark,
                reset_at=reset_at,
                is_search=is_search,
            )
            return False
        return True

    async def _retry_on_rate_limit(
        self,
        request_fn: Callable[[], Awaitable[httpx.Response]],
        *,
        is_search: bool = False,
        max_attempts: int = _RETRY_MAX_ATTEMPTS,
    ) -> httpx.Response:
        """Execute a request with exponential backoff retry on rate limit.

        On 403 with rate limit error, waits with exponential backoff and retries.
        On success or non-rate-limit errors, returns/re-raises immediately.
        """
        last_exception: Exception | None = None

        for attempt in range(max_attempts):
            try:
                # Proactive wait if rate limit is low before making request
                await self._await_if_rate_limited(is_search=is_search)

                response = await request_fn()

                # Track rate limits from response (even successful ones)
                await self._track_rate_limits(response)

                # Check if this is a rate limit error
                if (
                    response.status_code == _HTTP_FORBIDDEN
                    and "rate limit" in response.text.lower()
                ):
                    # Extract reset time from response headers
                    reset_header = response.headers.get("x-ratelimit-reset")
                    if reset_header:
                        with contextlib.suppress(ValueError, OSError):
                            reset_ts = datetime.fromtimestamp(int(reset_header), tz=UTC)
                            if is_search:
                                self._search_reset_at = reset_ts
                            else:
                                self._core_reset_at = reset_ts

                    # Calculate backoff with jitter
                    backoff = min(_RETRY_BACKOFF_BASE * (2**attempt), _RETRY_MAX_WAIT)
                    jitter = backoff * _JITTER_FACTOR
                    wait_time = max(1.0, backoff + random.uniform(-jitter, jitter))  # noqa: S311

                    logger.warning(
                        "github_rate_limit_403_retry",
                        attempt=attempt + 1,
                        max_attempts=max_attempts,
                        wait_seconds=wait_time,
                        is_search=is_search,
                    )
                    await asyncio.sleep(wait_time)
                    continue

                return response

            except RateLimitError as e:
                backoff = min(_RETRY_BACKOFF_BASE * (2**attempt), _RETRY_MAX_WAIT)
                jitter = backoff * _JITTER_FACTOR
                wait_time = max(1.0, backoff + random.uniform(-jitter, jitter))  # noqa: S311

                logger.warning(
                    "github_rate_limit_error_retry",
                    attempt=attempt + 1,
                    max_attempts=max_attempts,
                    wait_seconds=wait_time,
                    error=str(e),
                    is_search=is_search,
                )
                await asyncio.sleep(wait_time)
            except httpx.HTTPStatusError:
                # Non-403 HTTP errors — don't retry, just re-raise
                raise

        # All retries exhausted
        if last_exception:
            raise last_exception
        raise RateLimitError(
            "GitHub API rate limit: all retries exhausted",
            reset_at=(
                self._search_reset_at.isoformat()
                if is_search and self._search_reset_at
                else self._core_reset_at.isoformat()
                if self._core_reset_at
                else None
            ),
            remaining=0,
        )

    # --- Public API ---

    @property
    def rate_limit_remaining(self) -> int | None:
        """Core API rate limit remaining."""
        return self._core_remaining

    @property
    def rate_limit_reset_at(self) -> datetime | None:
        """Core API rate limit reset time."""
        return self._core_reset_at

    @property
    def search_rate_limit_remaining(self) -> int | None:
        """Search API rate limit remaining."""
        return self._search_remaining

    @property
    def client(self) -> httpx.AsyncClient:
        """Access the underlying httpx client for custom requests."""
        return self._client

    async def get(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        etag: str | None = None,
        is_search: bool = False,
    ) -> httpx.Response:
        """Send an authenticated GET request with automatic rate limit retry.

        Uses exponential backoff with jitter on 403 rate limit errors.
        Proactively waits when rate limit is low before making requests.

        Args:
            url: Full URL or path relative to base_url.
            params: Optional query parameters.
            etag: If provided, adds If-None-Match header for conditional request.
            is_search: Whether this is a search endpoint (uses stricter rate limit).

        Returns:
            httpx Response. Check status_code == _HTTP_NOT_MODIFIED for conditional miss.

        Raises:
            RateLimitError: Only if all retries are exhausted.
        """
        headers: dict[str, str] = {}
        if etag is not None:
            headers["If-None-Match"] = f'"{etag}"'

        if not url.startswith("http"):
            url = f"{self._base_url}{url}"

        response = await self._tenacity_fetch(
            url,
            params=params,
            headers=headers or None,
            is_search=is_search,
        )

        # 304 Not Modified is a valid response for conditional requests
        if response.status_code != _HTTP_NOT_MODIFIED:
            response.raise_for_status()
        return response

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        etag: str | None = None,
    ) -> dict[str, Any] | list[Any] | None:
        """GET request returning parsed JSON. Returns None for 304.

        Returns the raw parsed JSON (dict or list).
        GitHub API endpoints return both dicts (single resource)
        and lists (collections) depending on the endpoint.
        """
        response = await self.get(url, params=params, etag=etag)
        if response.status_code == _HTTP_NOT_MODIFIED:
            return None
        return response.json()  # type: ignore[no-any-return]

    async def get_all_pages(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        max_pages: int = _DEFAULT_MAX_PAGES,
        per_page: int = _DEFAULT_PER_PAGE,
    ) -> list[dict[str, Any]]:
        """Paginate through all pages using Link header.

        Each page request is retried with exponential backoff on rate limit.
        Proactively waits when rate limit is low before fetching each page.

        Args:
            url: Starting URL (relative or absolute).
            params: Query parameters (per_page added automatically).
            max_pages: Safety limit on number of pages.
            per_page: Results per page (max 100 for GitHub).

        Returns:
            List of all items across pages.
        """
        all_items: list[dict[str, Any]] = []
        merged_params = dict(params or {})
        merged_params["per_page"] = per_page

        current_url: str | None = url if url.startswith("http") else f"{self._base_url}{url}"

        for page_num in range(max_pages):
            if current_url is None:
                break

            # Only pass params for the first page (subsequent pages use full URLs)
            request_params = merged_params if page_num == 0 else None

            # Capture current values to avoid closure capturing loop variables (B023)
            _current_url: str = current_url

            response = await self._tenacity_fetch(
                _current_url,
                params=request_params,
            )
            data = response.json()

            # GitHub list endpoints return arrays
            if isinstance(data, list):
                all_items.extend(data)
            else:
                # Some endpoints return objects with items
                all_items.append(data)

            # Parse Link header for next page
            link_header = response.headers.get("link", "")
            next_match = _LINK_NEXT_RE.search(link_header)
            if next_match:
                current_url = next_match.group(1)
                merged_params = {}  # next URL already has params
            else:
                break

            logger.debug(
                "paginated_page_fetched",
                page=page_num + 1,
                items_in_page=len(data) if isinstance(data, list) else 1,
                total_so_far=len(all_items),
            )

        return all_items

    async def search(
        self,
        endpoint: str,
        query: str,
        *,
        sort: str | None = None,
        order: str = "desc",
        max_pages: int = 5,
        per_page: int = 100,
    ) -> tuple[list[dict[str, Any]], int]:
        """Execute a GitHub search API call with pagination.

        Each page request is retried with exponential backoff on rate limit.
        Proactively waits when search rate limit is low before each request.

        Args:
            endpoint: Search endpoint path (/search/repositories or /search/code).
            query: GitHub search query string (with qualifiers).
            sort: Sort field (stars, forks, updated, indexed).
            order: Sort direction (asc, desc).
            max_pages: Maximum pages to fetch.
            per_page: Results per page.

        Returns:
            Tuple of (items, total_count).

        Raises:
            RateLimitError: Only if all retries are exhausted.
        """
        all_items: list[dict[str, Any]] = []
        total_count = 0

        params: dict[str, str | int] = {
            "q": query,
            "per_page": per_page,
        }
        if sort is not None:
            params["sort"] = sort
            params["order"] = order

        url = endpoint if endpoint.startswith("http") else f"{self._base_url}{endpoint}"

        for page_num in range(max_pages):
            params["page"] = page_num + 1

            # Capture loop variables to avoid closure capturing by reference (B023)
            _url = url
            _params = dict(params)

            response = await self._tenacity_fetch(
                _url,
                params=_params,
                is_search=True,
            )
            data = response.json()

            total_count = data.get("total_count", 0)
            items = data.get("items", [])

            if not items:
                break

            all_items.extend(items)

            if data.get("incomplete_results"):
                logger.warning(
                    "search_results_incomplete",
                    endpoint=endpoint,
                    total_count=total_count,
                )

            # Stop if we have enough or there are no more
            if len(all_items) >= total_count:
                break

        return all_items, total_count

    async def check_rate_limit(self) -> dict[str, int]:
        """GET /rate_limit — does not count against limits."""
        url = f"{self._base_url}/rate_limit"
        response = await self._client.get(url)
        response.raise_for_status()
        data = response.json()

        resources = data.get("resources", {})
        core = resources.get("core", {})
        search = resources.get("search", {})

        self._core_remaining = core.get("remaining")
        self._search_remaining = search.get("remaining")

        return {
            "core_remaining": core.get("remaining", 0),
            "core_limit": core.get("limit", 0),
            "search_remaining": search.get("remaining", 0),
            "search_limit": search.get("limit", 0),
        }

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()

    @staticmethod
    def _map_status_error(response: httpx.Response) -> GitHubFetchError | None:  # noqa: PLR0911
        """Map HTTP status code to typed exception.

        Returns a typed exception for non-2xx status codes, or None for 2xx.
        """
        if _HTTP_OK_MIN <= response.status_code < _HTTP_OK_MAX:
            return None
        if response.status_code == _HTTP_NOT_MODIFIED:
            return None
        if response.status_code == _HTTP_UNAUTHORIZED:
            return GitHubAuthError(
                f"Authentication failed: {response.text[:200]}",
                status_code=_HTTP_UNAUTHORIZED,
                url=str(response.url),
            )
        if response.status_code == _HTTP_FORBIDDEN:
            retry_after = response.headers.get("Retry-After")
            retry_after_int: int | None = None
            if retry_after is not None:
                with contextlib.suppress(ValueError):
                    retry_after_int = int(retry_after)
            if "rate limit" in response.text.lower() or retry_after is not None:
                return GitHubRateLimitError(
                    f"Rate limited: {response.text[:200]}",
                    retry_after=retry_after_int,
                    status_code=_HTTP_FORBIDDEN,
                    url=str(response.url),
                )
            return GitHubAuthError(
                f"Forbidden: {response.text[:200]}",
                status_code=_HTTP_FORBIDDEN,
                url=str(response.url),
            )
        if response.status_code == _HTTP_TOO_MANY_REQUESTS:
            retry_after = response.headers.get("Retry-After")
            retry_after_int_429: int | None = None
            if retry_after is not None:
                with contextlib.suppress(ValueError):
                    retry_after_int_429 = int(retry_after)
            return GitHubRateLimitError(
                f"Too many requests: {response.text[:200]}",
                retry_after=retry_after_int_429,
                status_code=_HTTP_TOO_MANY_REQUESTS,
                url=str(response.url),
            )
        if response.status_code >= _HTTP_SERVER_ERROR_MIN:
            return GitHubServerError(
                f"Server error {response.status_code}: {response.text[:200]}",
                status_code=response.status_code,
                url=str(response.url),
            )
        return GitHubFetchError(
            f"HTTP {response.status_code}: {response.text[:200]}",
            status_code=response.status_code,
            url=str(response.url),
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=30),
        retry=retry_if_exception_type((GitHubRateLimitError, GitHubServerError)),
        reraise=True,
    )
    async def _tenacity_fetch(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
        is_search: bool = False,
    ) -> httpx.Response:
        """Fetch with tenacity retry on rate limit and server errors.

        Maps HTTP status codes to typed exceptions before raising,
        so tenacity only retries on retryable error types.
        """
        await self._await_if_rate_limited(is_search=is_search)
        response = await self._client.get(url, params=params, headers=headers)
        await self._track_rate_limits(response)

        typed_error = self._map_status_error(response)
        if typed_error is not None:
            if (
                isinstance(typed_error, GitHubRateLimitError)
                and typed_error.retry_after is not None
            ):
                await asyncio.sleep(max(1, min(typed_error.retry_after, int(_RETRY_MAX_WAIT))))
            raise typed_error
        return response

    async def __aenter__(self) -> GitHubRestClient:
        """Enter async context."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context, closing the client."""
        await self.close()
