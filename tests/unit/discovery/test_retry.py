"""Tests for tenacity retry on GitHub API fetch errors — T3.2."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pytest_httpx import HTTPXMock

from github_discovery.config import GitHubSettings
from github_discovery.discovery.github_client import GitHubRestClient
from github_discovery.exceptions import (
    GitHubAuthError,
    GitHubRateLimitError,
    GitHubServerError,
)


@pytest.fixture
def github_settings() -> GitHubSettings:
    """GitHub settings with test token."""
    return GitHubSettings(
        token="ghp_test_token_12345",  # noqa: S106
        api_base_url="https://api.github.com",
        request_timeout=10,
    )


@pytest.fixture
def client(github_settings: GitHubSettings) -> GitHubRestClient:
    """Create a GitHubRestClient with test settings."""
    return GitHubRestClient(github_settings)


class TestTenacityRetry:
    """Tests for tenacity retry behavior on fetch errors."""

    async def test_429_retries_then_succeeds(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubRestClient,
    ) -> None:
        """429 twice then 200 → fetch returns success after 2 retries."""
        # First two requests: 429
        httpx_mock.add_response(
            url="https://api.github.com/repos/test/repo",
            status_code=429,
            json={"message": "rate limit exceeded"},
            headers={"Retry-After": "1"},
        )
        httpx_mock.add_response(
            url="https://api.github.com/repos/test/repo",
            status_code=429,
            json={"message": "rate limit exceeded"},
            headers={"Retry-After": "1"},
        )
        # Third request: success
        httpx_mock.add_response(
            url="https://api.github.com/repos/test/repo",
            json={"full_name": "test/repo"},
        )

        # Patch sleep to speed up test
        with patch("asyncio.sleep", new_callable=AsyncMock):
            async with client:
                response = await client._tenacity_fetch(
                    "https://api.github.com/repos/test/repo",
                )
                assert response.status_code == 200
                assert response.json()["full_name"] == "test/repo"

    async def test_503_retries_then_succeeds(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubRestClient,
    ) -> None:
        """503 once then 200 → fetch returns success after 1 retry."""
        httpx_mock.add_response(
            url="https://api.github.com/repos/test/repo",
            status_code=503,
            json={"message": "service unavailable"},
        )
        httpx_mock.add_response(
            url="https://api.github.com/repos/test/repo",
            json={"full_name": "test/repo"},
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            async with client:
                response = await client._tenacity_fetch(
                    "https://api.github.com/repos/test/repo",
                )
                assert response.status_code == 200

    async def test_401_does_not_retry(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubRestClient,
    ) -> None:
        """401 → GitHubAuthError raised immediately, no retry."""
        httpx_mock.add_response(
            url="https://api.github.com/repos/test/repo",
            status_code=401,
            json={"message": "bad credentials"},
        )

        async with client:
            with pytest.raises(GitHubAuthError):
                await client._tenacity_fetch(
                    "https://api.github.com/repos/test/repo",
                )
        # Verify only one request was made (no retries)
        requests = httpx_mock.get_requests()
        assert len(requests) == 1

    async def test_429_exhausts_retries(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubRestClient,
    ) -> None:
        """429 three times → GitHubRateLimitError after exhausting retries."""
        for _ in range(3):
            httpx_mock.add_response(
                url="https://api.github.com/repos/test/repo",
                status_code=429,
                json={"message": "rate limit exceeded"},
                headers={"Retry-After": "1"},
            )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            async with client:
                with pytest.raises(GitHubRateLimitError):
                    await client._tenacity_fetch(
                        "https://api.github.com/repos/test/repo",
                    )


class TestMapStatusError:
    """Tests for _map_status_error static method."""

    def test_2xx_returns_none(self, client: GitHubRestClient) -> None:
        """2xx responses return None (no error)."""
        response = httpx.Response(200, request=httpx.Request("GET", "http://test"))
        assert client._map_status_error(response) is None

    def test_401_maps_to_auth_error(self, client: GitHubRestClient) -> None:
        """401 maps to GitHubAuthError."""
        response = httpx.Response(
            401,
            json={"message": "bad credentials"},
            request=httpx.Request("GET", "https://api.github.com/test"),
        )
        error = client._map_status_error(response)
        assert isinstance(error, GitHubAuthError)
        assert error.status_code == 401

    def test_403_rate_limit_maps_to_rate_limit_error(self, client: GitHubRestClient) -> None:
        """403 with rate limit text maps to GitHubRateLimitError."""
        response = httpx.Response(
            403,
            text="API rate limit exceeded",
            request=httpx.Request("GET", "https://api.github.com/test"),
            headers={"Retry-After": "60"},
        )
        error = client._map_status_error(response)
        assert isinstance(error, GitHubRateLimitError)
        assert error.retry_after == 60
        assert error.status_code == 403

    def test_403_non_rate_limit_maps_to_auth_error(self, client: GitHubRestClient) -> None:
        """403 without rate limit text maps to GitHubAuthError."""
        response = httpx.Response(
            403,
            text="forbidden",
            request=httpx.Request("GET", "https://api.github.com/test"),
        )
        error = client._map_status_error(response)
        assert isinstance(error, GitHubAuthError)
        assert error.status_code == 403

    def test_429_maps_to_rate_limit_error(self, client: GitHubRestClient) -> None:
        """429 maps to GitHubRateLimitError."""
        response = httpx.Response(
            429,
            text="too many requests",
            request=httpx.Request("GET", "https://api.github.com/test"),
            headers={"Retry-After": "30"},
        )
        error = client._map_status_error(response)
        assert isinstance(error, GitHubRateLimitError)
        assert error.retry_after == 30
        assert error.status_code == 429

    def test_500_maps_to_server_error(self, client: GitHubRestClient) -> None:
        """500 maps to GitHubServerError."""
        response = httpx.Response(
            500,
            text="internal server error",
            request=httpx.Request("GET", "https://api.github.com/test"),
        )
        error = client._map_status_error(response)
        assert isinstance(error, GitHubServerError)
        assert error.status_code == 500

    def test_503_maps_to_server_error(self, client: GitHubRestClient) -> None:
        """503 maps to GitHubServerError."""
        response = httpx.Response(
            503,
            text="service unavailable",
            request=httpx.Request("GET", "https://api.github.com/test"),
        )
        error = client._map_status_error(response)
        assert isinstance(error, GitHubServerError)
        assert error.status_code == 503

    def test_404_maps_to_fetch_error(self, client: GitHubRestClient) -> None:
        """404 maps to generic GitHubFetchError."""
        response = httpx.Response(
            404,
            text="not found",
            request=httpx.Request("GET", "https://api.github.com/test"),
        )
        error = client._map_status_error(response)
        assert isinstance(error, GitHubAuthError) is False
        assert isinstance(error, GitHubRateLimitError) is False
        assert isinstance(error, GitHubServerError) is False
        assert error.status_code == 404
