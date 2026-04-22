"""Async client for GitHub GraphQL API.

Provides cursor-based pagination, query cost management,
and rate limit awareness. Uses httpx.AsyncClient under the
hood for connection pooling and HTTP/2.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import structlog

from github_discovery.exceptions import DiscoveryError, RateLimitError

if TYPE_CHECKING:
    from collections.abc import Generator

    from github_discovery.config import GitHubSettings

logger = structlog.get_logger("github_discovery.discovery.graphql_client")

# GitHub API version header
_GITHUB_API_VERSION = "2022-11-28"
_GITHUB_ACCEPT = "application/vnd.github+json"

# Rate limit threshold — stop making requests when remaining < this
_RATE_LIMIT_LOW_WATERMARK = 50


class _BearerAuth(httpx.Auth):
    """httpx Auth that adds Bearer token to every request."""

    def __init__(self, token: str) -> None:
        """Store the bearer token."""
        self._token = token

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        """Add Authorization header and yield the request."""
        request.headers["Authorization"] = f"Bearer {self._token}"
        yield request


class GitHubGraphQLClient:
    """GraphQL client for GitHub API with cursor-based pagination and cost management.

    Features:
    - Bearer token authentication via httpx.Auth
    - Automatic cost monitoring from rateLimit response fields
    - Cursor-based pagination over GraphQL connections
    - Pre-request rate limit enforcement
    - Structured logging via structlog
    """

    def __init__(self, settings: GitHubSettings) -> None:
        """Initialize the client with GitHub settings."""
        self._settings = settings
        self._graphql_url = settings.graphql_url

        # Rate limit state (tracked from rateLimit fields in responses)
        self._remaining: int | None = None
        self._reset_at: str | None = None

        auth = _BearerAuth(settings.token) if settings.token else None

        self._client = httpx.AsyncClient(
            auth=auth,
            headers={
                "Accept": _GITHUB_ACCEPT,
                "X-GitHub-Api-Version": _GITHUB_API_VERSION,
            },
            timeout=settings.request_timeout,
        )

    # --- Rate limit tracking ---

    @property
    def rate_limit_remaining(self) -> int | None:
        """GraphQL rate limit remaining (from rateLimit response field)."""
        return self._remaining

    @property
    def rate_limit_reset_at(self) -> str | None:
        """GraphQL rate limit reset time."""
        return self._reset_at

    def _check_rate_limit(self) -> None:
        """Raise RateLimitError if remaining is below watermark."""
        if self._remaining is not None and self._remaining < _RATE_LIMIT_LOW_WATERMARK:
            raise RateLimitError(
                f"GraphQL rate limit near exhaustion "
                f"(remaining={self._remaining}, watermark={_RATE_LIMIT_LOW_WATERMARK})",
                reset_at=self._reset_at,
                remaining=self._remaining,
            )

    def _process_rate_limit(self, data: dict[str, object]) -> None:
        """Extract and log rateLimit info from GraphQL response data."""
        rate_limit = data.get("rateLimit")
        if not isinstance(rate_limit, dict):
            return

        cost = rate_limit.get("cost")
        remaining = rate_limit.get("remaining")
        reset_at = rate_limit.get("resetAt")

        if isinstance(remaining, int):
            self._remaining = remaining
        if isinstance(reset_at, str):
            self._reset_at = reset_at

        logger.debug(
            "graphql_rate_limit",
            cost=cost,
            remaining=remaining,
            reset_at=reset_at,
        )

    # --- Public API ---

    async def execute(
        self,
        query: str,
        variables: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Execute a GraphQL query and return the data.

        Args:
            query: GraphQL query string.
            variables: Optional variables for the query.

        Returns:
            The ``data`` dict from the GraphQL response.

        Raises:
            DiscoveryError: If the response contains GraphQL errors.
            RateLimitError: If rate limit is near exhaustion before request.
        """
        self._check_rate_limit()

        body: dict[str, object] = {"query": query}
        if variables is not None:
            body["variables"] = variables

        response = await self._client.post(self._graphql_url, json=body)
        response.raise_for_status()

        result: dict[str, object] = response.json()

        # Check for GraphQL errors
        errors = result.get("errors")
        if isinstance(errors, list) and errors:
            error_details = "; ".join(
                str(e.get("message", "")) for e in errors if isinstance(e, dict)
            )
            raise DiscoveryError(
                f"GraphQL query failed: {error_details}",
                context={"query": query[:200], "error_count": len(errors)},
            )

        # Process rate limit info if present
        data = result.get("data")
        if isinstance(data, dict):
            self._process_rate_limit(data)
        # rateLimit may also be at the top level (outside data)
        self._process_rate_limit(result)

        # Return data portion
        if isinstance(data, dict):
            return data

        # Edge case: response with no data key
        return result

    async def paginate(
        self,
        query: str,
        *,
        variables: dict[str, object] | None = None,
        page_size: int = 100,
        max_pages: int = 10,
        connection_path: str = "data",
    ) -> list[dict[str, object]]:
        """Cursor-based pagination over a GraphQL connection.

        Automatically follows ``pageInfo.hasNextPage`` / ``endCursor``.
        The query MUST include ``$first`` and ``$after`` variables, plus
        ``pageInfo { hasNextPage endCursor }`` in the connection.

        Args:
            query: GraphQL query string with ``$first`` and ``$after`` variables.
            variables: Additional variables for the query.
            page_size: Number of items per page (max 100).
            max_pages: Safety limit on pages.
            connection_path: Dot-separated path to the connection within
                the response ``data`` dict.

        Returns:
            List of all node dicts collected across pages.
        """
        all_nodes: list[dict[str, object]] = []
        cursor: str | None = None

        for page_num in range(max_pages):
            # Build variables: merge caller variables with pagination ones
            merged_vars: dict[str, object] = dict(variables or {})
            merged_vars["first"] = page_size
            merged_vars["after"] = cursor

            data = await self.execute(query, variables=merged_vars)

            # Navigate to the connection using connection_path
            connection = self._resolve_connection(data, connection_path)

            if connection is None:
                logger.warning(
                    "graphql_connection_not_found",
                    connection_path=connection_path,
                    page=page_num,
                    data_keys=list(data.keys()),
                )
                break

            # Extract nodes
            nodes = connection.get("nodes")
            if isinstance(nodes, list):
                all_nodes.extend(nodes)

            # Check pageInfo for next page
            page_info = connection.get("pageInfo")
            if not isinstance(page_info, dict):
                logger.warning(
                    "graphql_page_info_missing",
                    connection_path=connection_path,
                    page=page_num,
                )
                break

            has_next = page_info.get("hasNextPage")
            end_cursor = page_info.get("endCursor")

            if not has_next:
                break

            cursor = end_cursor if isinstance(end_cursor, str) else None

            logger.debug(
                "graphql_page_fetched",
                page=page_num + 1,
                nodes_in_page=len(nodes) if isinstance(nodes, list) else 0,
                total_so_far=len(all_nodes),
                has_next_page=True,
            )

        return all_nodes

    @staticmethod
    def _resolve_connection(
        data: dict[str, object],
        path: str,
    ) -> dict[str, object] | None:
        """Navigate a dot-separated path within the data dict.

        Args:
            data: The response data dict.
            path: Dot-separated key path (e.g. "search" or "repository.topics").

        Returns:
            The dict at the end of the path, or None if not found.
        """
        current: object = data
        for key in path.split("."):
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current if isinstance(current, dict) else None

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()

    async def __aenter__(self) -> GitHubGraphQLClient:
        """Enter async context."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context, closing the client."""
        await self.close()
