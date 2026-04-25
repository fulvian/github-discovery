"""Tests for GitHubRestClient — Task 2.1."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pytest_httpx import HTTPXMock

from github_discovery.config import GitHubSettings
from github_discovery.discovery.github_client import GitHubRestClient

# --- Fixtures ---


@pytest.fixture
def client(github_settings: GitHubSettings) -> GitHubRestClient:
    """Create a GitHubRestClient with test settings."""
    return GitHubRestClient(github_settings)


@pytest.fixture
def rate_limit_headers_ok() -> dict[str, str]:
    """Rate limit headers indicating healthy limits."""
    return {
        "x-ratelimit-remaining": "4990",
        "x-ratelimit-limit": "5000",
        "x-ratelimit-reset": "1700000000",
    }


@pytest.fixture
def rate_limit_headers_low() -> dict[str, str]:
    """Rate limit headers indicating near-exhaustion."""
    return {
        "x-ratelimit-remaining": "5",
        "x-ratelimit-limit": "5000",
        "x-ratelimit-reset": "1700001000",
    }


# --- Tests ---


class TestBearerAuth:
    """Tests for Bearer token authentication."""

    async def test_bearer_auth_header(
        self,
        httpx_mock: HTTPXMock,
        github_settings: GitHubSettings,
    ) -> None:
        """Authorization header should contain Bearer token."""
        httpx_mock.add_response(
            url="https://api.github.com/test",
            json={"ok": True},
        )

        async with GitHubRestClient(github_settings) as c:
            await c.get("/test")

        request = httpx_mock.get_requests()[-1]
        assert request.headers["Authorization"] == "Bearer ghp_test_token_12345"

    async def test_github_api_version_header(
        self,
        httpx_mock: HTTPXMock,
        github_settings: GitHubSettings,
    ) -> None:
        """X-GitHub-Api-Version header should be set."""
        httpx_mock.add_response(
            url="https://api.github.com/test",
            json={"ok": True},
        )

        async with GitHubRestClient(github_settings) as c:
            await c.get("/test")

        request = httpx_mock.get_requests()[-1]
        assert request.headers["X-GitHub-Api-Version"] == "2022-11-28"

    async def test_accept_header(
        self,
        httpx_mock: HTTPXMock,
        github_settings: GitHubSettings,
    ) -> None:
        """Accept header should be the GitHub JSON media type."""
        httpx_mock.add_response(
            url="https://api.github.com/test",
            json={"ok": True},
        )

        async with GitHubRestClient(github_settings) as c:
            await c.get("/test")

        request = httpx_mock.get_requests()[-1]
        assert "application/vnd.github+json" in request.headers["Accept"]


class TestRateLimitTracking:
    """Tests for rate limit tracking via event hooks."""

    async def test_rate_limit_tracking(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubRestClient,
        rate_limit_headers_ok: dict[str, str],
    ) -> None:
        """Rate limit properties should be updated from response headers."""
        httpx_mock.add_response(
            url="https://api.github.com/test",
            json={"ok": True},
            headers=rate_limit_headers_ok,
        )

        async with client:
            await client.get("/test")
            assert client.rate_limit_remaining == 4990

    async def test_rate_limit_waits_and_retries(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubRestClient,
        rate_limit_headers_low: dict[str, str],
    ) -> None:
        """When remaining < watermark, client waits then retries successfully.

        The new behavior: instead of raising RateLimitError immediately,
        the client waits with exponential backoff and retries.
        """
        # First request sets low remaining
        httpx_mock.add_response(
            url="https://api.github.com/first",
            json={"ok": True},
            headers=rate_limit_headers_low,
        )
        # Second request (after retry) succeeds
        httpx_mock.add_response(
            url="https://api.github.com/second",
            json={"ok": True},
            headers=rate_limit_headers_low,
        )

        # Mock asyncio.sleep to skip the backoff wait
        with patch(
            "github_discovery.discovery.github_client.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            async with client:
                await client.get("/first")
                # Now remaining=5 < watermark=10 → waits then retries
                result = await client.get("/second")
                assert result.status_code == 200


class TestConditionalRequests:
    """Tests for conditional requests using ETag."""

    async def test_conditional_request_etag(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubRestClient,
        rate_limit_headers_ok: dict[str, str],
    ) -> None:
        """If-None-Match header should be sent when etag is provided."""
        httpx_mock.add_response(
            url="https://api.github.com/repos/python/cpython",
            json={"full_name": "python/cpython"},
            headers=rate_limit_headers_ok,
        )

        async with client:
            await client.get("/repos/python/cpython", etag="abc123etag")

        request = httpx_mock.get_requests()[-1]
        assert request.headers["If-None-Match"] == '"abc123etag"'

    async def test_conditional_request_304(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubRestClient,
        rate_limit_headers_ok: dict[str, str],
    ) -> None:
        """304 response should be handled gracefully (not raise)."""
        httpx_mock.add_response(
            url="https://api.github.com/repos/python/cpython",
            status_code=304,
            headers=rate_limit_headers_ok,
        )

        async with client:
            response = await client.get("/repos/python/cpython", etag="abc123etag")
            assert response.status_code == 304

    async def test_get_json_returns_none_on_304(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubRestClient,
        rate_limit_headers_ok: dict[str, str],
    ) -> None:
        """get_json should return None for 304 responses."""
        httpx_mock.add_response(
            url="https://api.github.com/repos/python/cpython",
            status_code=304,
            headers=rate_limit_headers_ok,
        )

        async with client:
            result = await client.get_json("/repos/python/cpython", etag="abc123etag")
            assert result is None


class TestPagination:
    """Tests for Link-header pagination."""

    async def test_pagination_single_page(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubRestClient,
        rate_limit_headers_ok: dict[str, str],
    ) -> None:
        """Single page (no Link header) should return all items."""
        # Match any request to this base URL (with or without params)
        httpx_mock.add_response(
            url="https://api.github.com/repos/python/cpython/issues?per_page=100",
            json=[{"id": 1}, {"id": 2}],
            headers=rate_limit_headers_ok,
        )

        async with client:
            items = await client.get_all_pages("/repos/python/cpython/issues")
            assert len(items) == 2

    async def test_pagination_multiple_pages(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubRestClient,
        rate_limit_headers_ok: dict[str, str],
    ) -> None:
        """Multiple pages should follow Link header."""
        # Page 1
        httpx_mock.add_response(
            url="https://api.github.com/repos/python/cpython/issues?per_page=2",
            json=[{"id": 1}, {"id": 2}],
            headers={
                **rate_limit_headers_ok,
                "link": '<https://api.github.com/repos/python/cpython/issues?per_page=2&page=2>; rel="next"',  # noqa: E501
            },
        )
        # Page 2 (no next link)
        httpx_mock.add_response(
            url="https://api.github.com/repos/python/cpython/issues?per_page=2&page=2",
            json=[{"id": 3}],
            headers=rate_limit_headers_ok,
        )

        async with client:
            items = await client.get_all_pages(
                "/repos/python/cpython/issues",
                per_page=2,
            )
            assert len(items) == 3

    async def test_pagination_max_pages_limit(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubRestClient,
        rate_limit_headers_ok: dict[str, str],
    ) -> None:
        """Should stop at max_pages even if more pages exist."""
        # Register responses that are reusable
        httpx_mock.add_response(
            url="https://api.github.com/test?per_page=100",
            json=[{"id": 1}],
            headers={
                **rate_limit_headers_ok,
                "link": '<https://api.github.com/test?per_page=100&page=2>; rel="next"',
            },
        )
        httpx_mock.add_response(
            url="https://api.github.com/test?per_page=100&page=2",
            json=[{"id": 2}],
            headers={
                **rate_limit_headers_ok,
                "link": '<https://api.github.com/test?per_page=100&page=3>; rel="next"',
            },
        )

        async with client:
            items = await client.get_all_pages("/test", max_pages=2)
            # Should only fetch 2 pages
            assert len(items) == 2


class TestSearch:
    """Tests for search API endpoints."""

    async def test_search_returns_items_and_total(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubRestClient,
        rate_limit_headers_ok: dict[str, str],
    ) -> None:
        """Search should return (items, total_count) tuple."""
        # Register response without URL matching — will match any request
        httpx_mock.add_response(
            json={
                "total_count": 2,
                "incomplete_results": False,
                "items": [
                    {"full_name": "user/repo1", "score": 5.0},
                    {"full_name": "user/repo2", "score": 3.0},
                ],
            },
            headers=rate_limit_headers_ok,
        )

        async with client:
            items, total = await client.search(
                "/search/repositories",
                "python web framework",
                sort="updated",
                max_pages=1,
            )
            assert total == 2
            assert len(items) == 2
            assert items[0]["full_name"] == "user/repo1"

    async def test_search_waits_and_retries(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubRestClient,
    ) -> None:
        """Search should wait and retry when search rate limit is low.

        The new behavior: client waits with backoff and retries instead
        of raising immediately.
        """
        # First search: search remaining=2 (< watermark=3)
        httpx_mock.add_response(
            json={
                "total_count": 1,
                "items": [{"full_name": "user/repo1"}],
            },
            headers={
                "x-ratelimit-remaining": "2",
                "x-ratelimit-limit": "30",
                "x-ratelimit-reset": "1700001000",
            },
        )
        # Second search (after retry) succeeds
        httpx_mock.add_response(
            json={
                "total_count": 1,
                "items": [{"full_name": "user/repo2"}],
            },
            headers={
                "x-ratelimit-remaining": "2",
                "x-ratelimit-limit": "30",
                "x-ratelimit-reset": "1700001000",
            },
        )

        # Mock asyncio.sleep to skip the backoff wait
        with patch(
            "github_discovery.discovery.github_client.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            async with client:
                # First search works
                items, _ = await client.search(
                    "/search/repositories",
                    "test",
                    max_pages=1,
                )
                assert len(items) == 1

                # Second search: remaining=2 < watermark=3 → waits then retries
                items2, _ = await client.search(
                    "/search/repositories",
                    "test2",
                    max_pages=1,
                )
                assert len(items2) == 1


class TestCheckRateLimit:
    """Tests for check_rate_limit endpoint."""

    async def test_check_rate_limit(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubRestClient,
    ) -> None:
        """check_rate_limit should parse /rate_limit response."""
        httpx_mock.add_response(
            url="https://api.github.com/rate_limit",
            json={
                "resources": {
                    "core": {"limit": 5000, "remaining": 4990, "reset": 1700000000},
                    "search": {"limit": 30, "remaining": 28, "reset": 1700000060},
                },
            },
        )

        async with client:
            result = await client.check_rate_limit()
            assert result["core_remaining"] == 4990
            assert result["search_remaining"] == 28


class TestContextManager:
    """Tests for async context manager pattern."""

    async def test_context_manager(
        self,
        github_settings: GitHubSettings,
    ) -> None:
        """Client should work as async context manager."""
        async with GitHubRestClient(github_settings) as c:
            assert c.rate_limit_remaining is None  # No requests yet


class Test403RateLimitResponse:
    """Tests for 403 rate limit response handling."""

    async def test_403_rate_limit_retries_and_succeeds(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubRestClient,
        rate_limit_headers_ok: dict[str, str],
    ) -> None:
        """403 rate limit response should trigger retry with backoff.

        The new behavior: on 403 rate limit, client waits with exponential
        backoff and retries. All retries exhausted → RateLimitError.
        """
        # First request: 403 rate limit
        httpx_mock.add_response(
            url="https://api.github.com/test",
            status_code=403,
            json={"message": "API rate limit exceeded"},
            headers=rate_limit_headers_ok,
        )
        # Second request (after retry): succeeds
        httpx_mock.add_response(
            url="https://api.github.com/test",
            json={"ok": True},
            headers=rate_limit_headers_ok,
        )

        # Mock asyncio.sleep to skip the backoff wait
        with patch(
            "github_discovery.discovery.github_client.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            async with client:
                result = await client.get("/test")
                assert result.status_code == 200
