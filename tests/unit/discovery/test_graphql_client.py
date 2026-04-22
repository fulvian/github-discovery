"""Tests for GitHubGraphQLClient — Task 2.2."""

from __future__ import annotations

import json

import pytest
from pytest_httpx import HTTPXMock

from github_discovery.config import GitHubSettings
from github_discovery.discovery.graphql_client import GitHubGraphQLClient
from github_discovery.exceptions import DiscoveryError, RateLimitError

# --- Constants ---

_GRAPHQL_URL = "https://api.github.com/graphql"

# --- Fixtures ---


@pytest.fixture
def client(github_settings: GitHubSettings) -> GitHubGraphQLClient:
    """Create a GitHubGraphQLClient with test settings."""
    return GitHubGraphQLClient(github_settings)


# --- Helper ---


def _graphql_response(
    data: dict[str, object] | None = None,
    errors: list[dict[str, object]] | None = None,
    rate_limit: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    """Build a GraphQL JSON response envelope."""
    resp: dict[str, object] = {}
    if data is not None:
        resp["data"] = data
    if errors is not None:
        resp["errors"] = errors
    if rate_limit is not None:
        resp["rateLimit"] = rate_limit
    return resp


# --- Tests ---


class TestExecute:
    """Tests for the execute() method."""

    async def test_execute_simple_query(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubGraphQLClient,
    ) -> None:
        """execute() should return the data dict from a GraphQL response."""
        httpx_mock.add_response(
            url=_GRAPHQL_URL,
            json=_graphql_response(data={"viewer": {"login": "octocat"}}),
        )

        async with client:
            result = await client.execute("{ viewer { login } }")

        assert result == {"viewer": {"login": "octocat"}}

    async def test_execute_with_variables(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubGraphQLClient,
    ) -> None:
        """execute() should pass variables in the request body."""
        httpx_mock.add_response(
            url=_GRAPHQL_URL,
            json=_graphql_response(
                data={"repository": {"name": "flask"}},
            ),
        )

        async with client:
            result = await client.execute(
                "query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) { name } }",  # noqa: E501
                variables={"owner": "pallets", "name": "flask"},
            )

        assert result == {"repository": {"name": "flask"}}

        # Verify variables were sent in the POST body
        request = httpx_mock.get_request()
        body = json.loads(request.content.decode())
        assert body["variables"] == {"owner": "pallets", "name": "flask"}
        assert body["query"].startswith("query(")

    async def test_execute_handles_errors(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubGraphQLClient,
    ) -> None:
        """execute() should raise DiscoveryError on GraphQL errors."""
        httpx_mock.add_response(
            url=_GRAPHQL_URL,
            json=_graphql_response(
                errors=[
                    {"message": "Field 'xyz' doesn't exist", "type": "INVALID_FIELD"},
                ],
            ),
        )

        async with client:
            with pytest.raises(DiscoveryError, match="Field 'xyz' doesn't exist"):
                await client.execute("{ xyz }")

    async def test_execute_sends_auth_header(
        self,
        httpx_mock: HTTPXMock,
        github_settings: GitHubSettings,
    ) -> None:
        """execute() should send Authorization: Bearer header."""
        httpx_mock.add_response(
            url=_GRAPHQL_URL,
            json=_graphql_response(data={"viewer": {"login": "test"}}),
        )

        async with GitHubGraphQLClient(github_settings) as c:
            await c.execute("{ viewer { login } }")

        request = httpx_mock.get_request()
        assert request.headers["Authorization"] == "Bearer ghp_test_token_12345"

    async def test_execute_sends_github_headers(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubGraphQLClient,
    ) -> None:
        """execute() should send GitHub API version and Accept headers."""
        httpx_mock.add_response(
            url=_GRAPHQL_URL,
            json=_graphql_response(data={"viewer": {"login": "test"}}),
        )

        async with client:
            await client.execute("{ viewer { login } }")

        request = httpx_mock.get_request()
        assert request.headers["X-GitHub-Api-Version"] == "2022-11-28"
        assert "application/vnd.github+json" in request.headers["Accept"]


class TestPaginate:
    """Tests for the paginate() method."""

    @staticmethod
    def _page(
        nodes: list[dict[str, object]],
        has_next_page: bool,
        end_cursor: str | None,
    ) -> dict[str, object]:
        """Build a single GraphQL connection page."""
        return {
            "nodes": nodes,
            "pageInfo": {
                "hasNextPage": has_next_page,
                "endCursor": end_cursor,
            },
        }

    async def test_paginate_single_page(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubGraphQLClient,
    ) -> None:
        """paginate() with hasNextPage=false should return nodes from one page."""
        httpx_mock.add_response(
            url=_GRAPHQL_URL,
            json=_graphql_response(
                data={
                    "search": self._page(
                        nodes=[{"name": "repo1"}, {"name": "repo2"}],
                        has_next_page=False,
                        end_cursor=None,
                    ),
                },
            ),
        )

        async with client:
            result = await client.paginate(
                "query($first: Int!, $after: String) { search(query: 'test', first: $first, after: $after, type: REPOSITORY) { nodes { name } pageInfo { hasNextPage endCursor } } }",  # noqa: E501
                connection_path="search",
            )

        assert result == [{"name": "repo1"}, {"name": "repo2"}]

    async def test_paginate_multiple_pages(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubGraphQLClient,
    ) -> None:
        """paginate() should follow cursors across 3 pages."""
        # Page 1
        httpx_mock.add_response(
            url=_GRAPHQL_URL,
            json=_graphql_response(
                data={
                    "search": self._page(
                        nodes=[{"name": "repo1"}],
                        has_next_page=True,
                        end_cursor="cursor1",
                    ),
                },
            ),
        )
        # Page 2
        httpx_mock.add_response(
            url=_GRAPHQL_URL,
            json=_graphql_response(
                data={
                    "search": self._page(
                        nodes=[{"name": "repo2"}],
                        has_next_page=True,
                        end_cursor="cursor2",
                    ),
                },
            ),
        )
        # Page 3
        httpx_mock.add_response(
            url=_GRAPHQL_URL,
            json=_graphql_response(
                data={
                    "search": self._page(
                        nodes=[{"name": "repo3"}],
                        has_next_page=False,
                        end_cursor=None,
                    ),
                },
            ),
        )

        async with client:
            result = await client.paginate(
                "query($first: Int!, $after: String) { search(query: 'test', first: $first, after: $after, type: REPOSITORY) { nodes { name } pageInfo { hasNextPage endCursor } } }",  # noqa: E501
                connection_path="search",
            )

        assert len(result) == 3
        assert result[0]["name"] == "repo1"
        assert result[1]["name"] == "repo2"
        assert result[2]["name"] == "repo3"

    async def test_paginate_max_pages_limit(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubGraphQLClient,
    ) -> None:
        """paginate() should stop at max_pages even if more pages exist."""
        # Register a single reusable response that always returns hasNextPage=true
        httpx_mock.add_response(
            url=_GRAPHQL_URL,
            json=_graphql_response(
                data={
                    "search": self._page(
                        nodes=[{"name": "repo"}],
                        has_next_page=True,
                        end_cursor="cursor_next",
                    ),
                },
            ),
            is_reusable=True,
        )

        async with client:
            result = await client.paginate(
                "query($first: Int!, $after: String) { search(query: 'test', first: $first, after: $after, type: REPOSITORY) { nodes { name } pageInfo { hasNextPage endCursor } } }",  # noqa: E501
                connection_path="search",
                max_pages=3,
            )

        # Should stop after 3 pages
        assert len(result) == 3
        assert len(httpx_mock.get_requests()) == 3

    async def test_paginate_injects_first_and_after(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubGraphQLClient,
    ) -> None:
        """paginate() should inject first and after variables automatically."""
        httpx_mock.add_response(
            url=_GRAPHQL_URL,
            json=_graphql_response(
                data={
                    "search": self._page(
                        nodes=[{"name": "repo1"}],
                        has_next_page=True,
                        end_cursor="cursor1",
                    ),
                },
            ),
        )
        httpx_mock.add_response(
            url=_GRAPHQL_URL,
            json=_graphql_response(
                data={
                    "search": self._page(
                        nodes=[{"name": "repo2"}],
                        has_next_page=False,
                        end_cursor=None,
                    ),
                },
            ),
        )

        async with client:
            await client.paginate(
                "query($first: Int!, $after: String) { search(first: $first, after: $after) { nodes { name } pageInfo { hasNextPage endCursor } } }",  # noqa: E501
                connection_path="search",
                page_size=50,
            )

        requests = httpx_mock.get_requests()
        # First request: first=50, after=None
        body1 = json.loads(requests[0].content.decode())
        assert body1["variables"]["first"] == 50
        assert body1["variables"]["after"] is None

        # Second request: first=50, after="cursor1"
        body2 = json.loads(requests[1].content.decode())
        assert body2["variables"]["first"] == 50
        assert body2["variables"]["after"] == "cursor1"


class TestCostMonitoring:
    """Tests for rateLimit cost monitoring in responses."""

    async def test_cost_monitoring(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubGraphQLClient,
    ) -> None:
        """execute() should log cost info when rateLimit is in the response."""
        httpx_mock.add_response(
            url=_GRAPHQL_URL,
            json={
                "data": {"viewer": {"login": "octocat"}},
                "rateLimit": {
                    "cost": 1,
                    "remaining": 4999,
                    "resetAt": "2024-12-01T00:00:00Z",
                },
            },
        )

        async with client:
            result = await client.execute("{ viewer { login } }")

        assert result == {"viewer": {"login": "octocat"}}
        # Verify the cost was tracked internally
        assert client.rate_limit_remaining == 4999


class TestRateLimitEnforcement:
    """Tests for pre-request rate limit checking."""

    async def test_rate_limit_blocks_request(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubGraphQLClient,
    ) -> None:
        """execute() should raise RateLimitError when remaining is low."""
        # First request sets low remaining
        httpx_mock.add_response(
            url=_GRAPHQL_URL,
            json={
                "data": {"viewer": {"login": "octocat"}},
                "rateLimit": {
                    "cost": 1,
                    "remaining": 2,
                    "resetAt": "2024-12-01T00:00:00Z",
                },
            },
        )

        async with client:
            # First request works and sets low remaining
            await client.execute("{ viewer { login } }")

            # Second request should fail due to low remaining
            with pytest.raises(RateLimitError) as exc_info:
                await client.execute("{ viewer { login } }")
            assert exc_info.value.remaining == 2


class TestContextManager:
    """Tests for async context manager pattern."""

    async def test_context_manager(
        self,
        github_settings: GitHubSettings,
    ) -> None:
        """Client should work as async context manager."""
        async with GitHubGraphQLClient(github_settings) as c:
            assert c.rate_limit_remaining is None

    async def test_context_manager_closes_client(
        self,
        httpx_mock: HTTPXMock,
        client: GitHubGraphQLClient,
    ) -> None:
        """Exiting context manager should close the underlying client."""
        httpx_mock.add_response(
            url=_GRAPHQL_URL,
            json=_graphql_response(data={"viewer": {"login": "test"}}),
        )

        await client.__aenter__()
        await client.execute("{ viewer { login } }")
        await client.__aexit__(None, None, None)

        # After close, the underlying client should be closed
        assert client._client.is_closed
