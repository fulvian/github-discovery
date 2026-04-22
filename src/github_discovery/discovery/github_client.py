"""Async client for GitHub REST API.

Provides rate limit awareness, retry with backoff, conditional
requests (ETag), and rigorous Link-header pagination. Uses
httpx.AsyncClient under the hood for connection pooling and HTTP/2.
"""

from __future__ import annotations

import contextlib
import re
from collections.abc import Generator  # noqa: TC003
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from github_discovery.config import GitHubSettings  # noqa: TC001
from github_discovery.exceptions import RateLimitError

logger = structlog.get_logger("github_discovery.discovery.github_client")

# GitHub API version header
_GITHUB_API_VERSION = "2022-11-28"
_GITHUB_ACCEPT = "application/vnd.github+json"

# Default thresholds
_RATE_LIMIT_LOW_WATERMARK = 50  # Stop making requests when remaining < this
_SEARCH_RATE_LIMIT_LOW_WATERMARK = 5
_DEFAULT_PER_PAGE = 100
_DEFAULT_MAX_PAGES = 10
_RETRY_BACKOFF_BASE = 1.0  # seconds
_RETRY_MAX_ATTEMPTS = 3

# HTTP status codes
_HTTP_FORBIDDEN = 403
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

    def _check_rate_limit(self, *, is_search: bool = False) -> None:
        """Raise RateLimitError if remaining is below watermark."""
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
            raise RateLimitError(
                f"GitHub API rate limit near exhaustion "
                f"(remaining={remaining}, watermark={watermark})",
                reset_at=reset_at,
                remaining=remaining,
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
        """Send an authenticated GET request.

        Args:
            url: Full URL or path relative to base_url.
            params: Optional query parameters.
            etag: If provided, adds If-None-Match header for conditional request.
            is_search: Whether this is a search endpoint (uses stricter rate limit).

        Returns:
            httpx Response. Check status_code == _HTTP_NOT_MODIFIED for conditional miss.

        Raises:
            RateLimitError: If rate limit is below watermark before request.
        """
        self._check_rate_limit(is_search=is_search)

        headers: dict[str, str] = {}
        if etag is not None:
            headers["If-None-Match"] = f'"{etag}"'

        if not url.startswith("http"):
            url = f"{self._base_url}{url}"

        response = await self._client.get(url, params=params, headers=headers)

        if response.status_code == _HTTP_FORBIDDEN and "rate limit" in response.text.lower():
            raise RateLimitError(
                "GitHub API rate limit exceeded",
                reset_at=self._core_reset_at.isoformat() if self._core_reset_at else None,
                remaining=0,
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
    ) -> dict[str, Any] | None:
        """GET request returning parsed JSON. Returns None for 304."""
        response = await self.get(url, params=params, etag=etag)
        if response.status_code == _HTTP_NOT_MODIFIED:
            return None
        return dict(response.json())

    async def get_all_pages(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        max_pages: int = _DEFAULT_MAX_PAGES,
        per_page: int = _DEFAULT_PER_PAGE,
    ) -> list[dict[str, Any]]:
        """Paginate through all pages using Link header.

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

            self._check_rate_limit()

            # Only pass params for the first page (subsequent pages use full URLs)
            request_params = merged_params if page_num == 0 else None

            response = await self._client.get(current_url, params=request_params)

            if response.status_code == _HTTP_FORBIDDEN and "rate limit" in response.text.lower():
                raise RateLimitError(
                    "GitHub API rate limit exceeded during pagination",
                    reset_at=self._core_reset_at.isoformat() if self._core_reset_at else None,
                    remaining=0,
                )

            response.raise_for_status()
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
            RateLimitError: If search rate limit is near exhaustion.
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
            self._check_rate_limit(is_search=True)
            params["page"] = page_num + 1

            response = await self._client.get(url, params=params)

            if response.status_code == _HTTP_FORBIDDEN and "rate limit" in response.text.lower():
                raise RateLimitError(
                    "GitHub search rate limit exceeded",
                    reset_at=(
                        self._search_reset_at.isoformat() if self._search_reset_at else None
                    ),
                    remaining=0,
                )

            response.raise_for_status()
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

    async def __aenter__(self) -> GitHubRestClient:
        """Enter async context."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context, closing the client."""
        await self.close()
