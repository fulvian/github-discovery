"""Tests for the CodeSearchChannel discovery channel.

Tests cover quality signal patterns, search result mapping from code
search response format (repository sub-objects), deduplication across
multiple signal patterns, max_candidates enforcement, language filtering,
empty results, and rate limit strictness (max_pages=1).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from github_discovery.config import GitHubSettings
from github_discovery.discovery.code_search_channel import (
    QUALITY_SIGNAL_PATTERNS,
    CodeSearchChannel,
)
from github_discovery.discovery.github_client import GitHubRestClient
from github_discovery.discovery.types import ChannelResult, DiscoveryQuery
from github_discovery.models.enums import DiscoveryChannel

# --- Fixtures ---


@pytest.fixture
def rest_client(github_settings: GitHubSettings) -> GitHubRestClient:
    """Create a GitHubRestClient for testing."""
    return GitHubRestClient(github_settings)


@pytest.fixture
def code_search_channel(rest_client: GitHubRestClient) -> CodeSearchChannel:
    """Create a CodeSearchChannel instance for testing."""
    return CodeSearchChannel(rest_client)


@pytest.fixture
def code_search_response_dedup() -> dict[str, object]:
    """Code search response where same repo appears in multiple patterns."""
    return {
        "total_count": 2,
        "incomplete_results": False,
        "items": [
            {
                "name": "conftest.py",
                "path": "tests/conftest.py",
                "sha": "abc123",
                "url": "https://api.github.com/repos/user/repo1/contents/tests/conftest.py",
                "html_url": "https://github.com/user/repo1/blob/main/tests/conftest.py",
                "repository": {
                    "full_name": "user/repo1",
                    "url": "https://api.github.com/repos/user/repo1",
                    "html_url": "https://github.com/user/repo1",
                },
                "score": 1.0,
            },
            {
                "name": "conftest.py",
                "path": "tests/conftest.py",
                "sha": "def789",
                "url": "https://api.github.com/repos/user/repo1/contents/tests/conftest.py",
                "html_url": "https://github.com/user/repo1/blob/main/tests/conftest.py",
                "repository": {
                    "full_name": "user/repo1",
                    "url": "https://api.github.com/repos/user/repo1",
                    "html_url": "https://github.com/user/repo1",
                },
                "score": 0.9,
            },
        ],
    }


@pytest.fixture
def code_search_many_results() -> dict[str, object]:
    """Code search response with many items for max_candidates testing."""
    items = []
    for i in range(10):
        items.append(
            {
                "name": "conftest.py",
                "path": "tests/conftest.py",
                "sha": f"sha{i}",
                "url": f"https://api.github.com/repos/user/repo{i}/contents/tests/conftest.py",
                "html_url": f"https://github.com/user/repo{i}/blob/main/tests/conftest.py",
                "repository": {
                    "full_name": f"user/repo{i}",
                    "url": f"https://api.github.com/repos/user/repo{i}",
                    "html_url": f"https://github.com/user/repo{i}",
                },
                "score": 1.0 - i * 0.05,
            }
        )
    return {
        "total_count": 50,
        "incomplete_results": False,
        "items": items,
    }


# --- Quality signal patterns tests ---


class TestQualitySignalPatterns:
    """Tests for QUALITY_SIGNAL_PATTERNS constant."""

    def test_quality_signal_patterns_defined(self) -> None:
        """Verify patterns cover 4 categories: testing, ci_cd, security, documentation."""
        expected_categories = {"testing", "ci_cd", "security", "documentation"}
        assert set(QUALITY_SIGNAL_PATTERNS.keys()) == expected_categories

    def test_quality_signal_patterns_non_empty(self) -> None:
        """Each category should have at least one pattern."""
        for category, patterns in QUALITY_SIGNAL_PATTERNS.items():
            assert len(patterns) > 0, f"Category {category} has no patterns"


# --- search tests ---


class TestSearch:
    """Tests for CodeSearchChannel.search()."""

    async def test_search_returns_channel_result(
        self,
        code_search_channel: CodeSearchChannel,
        rest_client: GitHubRestClient,
        sample_code_search_response: dict[str, object],
    ) -> None:
        """Search returns a ChannelResult with CODE_SEARCH channel type."""
        items = sample_code_search_response["items"]
        assert isinstance(items, list)
        # search() makes 2 API calls: keywords-only + keywords+signals
        rest_client.search = AsyncMock(return_value=(items, 2))

        query = DiscoveryQuery(query="testing framework")
        result = await code_search_channel.search(query)

        assert isinstance(result, ChannelResult)
        assert result.channel == DiscoveryChannel.CODE_SEARCH
        assert len(result.candidates) == 2
        # total_found accumulates across both calls (2 + 2 = 4)
        assert result.total_found == 4

    async def test_search_maps_repository_from_code_result(
        self,
        code_search_channel: CodeSearchChannel,
        rest_client: GitHubRestClient,
        sample_code_search_response: dict[str, object],
    ) -> None:
        """Verify mapping from code search result repository sub-object."""
        items = sample_code_search_response["items"]
        assert isinstance(items, list)
        rest_client.search = AsyncMock(return_value=(items, 2))

        query = DiscoveryQuery(query="testing")
        result = await code_search_channel.search(query)

        candidate = result.candidates[0]
        assert candidate.full_name == "user/repo1"
        assert candidate.html_url == "https://github.com/user/repo1"
        assert candidate.api_url == "https://api.github.com/repos/user/repo1"
        assert candidate.source_channel == DiscoveryChannel.CODE_SEARCH
        assert candidate.owner_login == "user"

    async def test_search_dedup_same_repo(
        self,
        code_search_channel: CodeSearchChannel,
        rest_client: GitHubRestClient,
        code_search_response_dedup: dict[str, object],
    ) -> None:
        """Same repo from 2 patterns yields 1 candidate."""
        items = code_search_response_dedup["items"]
        assert isinstance(items, list)
        rest_client.search = AsyncMock(return_value=(items, 2))

        query = DiscoveryQuery(query="testing")
        result = await code_search_channel.search(query)

        full_names = [c.full_name for c in result.candidates]
        assert full_names.count("user/repo1") == 1
        assert len(result.candidates) == 1

    async def test_search_respects_max_candidates(
        self,
        code_search_channel: CodeSearchChannel,
        rest_client: GitHubRestClient,
        code_search_many_results: dict[str, object],
    ) -> None:
        """Mock many results — stops at max_candidates limit."""
        items = code_search_many_results["items"]
        assert isinstance(items, list)
        rest_client.search = AsyncMock(return_value=(items, 50))

        query = DiscoveryQuery(query="testing", max_candidates=3)
        result = await code_search_channel.search(query)

        assert len(result.candidates) == 3
        assert result.total_found == 50
        assert result.has_more is True

    async def test_search_handles_empty_results(
        self,
        code_search_channel: CodeSearchChannel,
        rest_client: GitHubRestClient,
    ) -> None:
        """Mock empty response — empty ChannelResult."""
        rest_client.search = AsyncMock(return_value=([], 0))

        query = DiscoveryQuery(query="nonexistent-xyz-abc-123")
        result = await code_search_channel.search(query)

        assert isinstance(result, ChannelResult)
        assert result.channel == DiscoveryChannel.CODE_SEARCH
        assert len(result.candidates) == 0
        assert result.total_found == 0
        assert result.has_more is False

    async def test_rate_limit_strict(
        self,
        code_search_channel: CodeSearchChannel,
        rest_client: GitHubRestClient,
        sample_code_search_response: dict[str, object],
    ) -> None:
        """Verify search uses max_pages=1 (code search rate limit: 10 req/min)."""
        items = sample_code_search_response["items"]
        assert isinstance(items, list)
        rest_client.search = AsyncMock(return_value=(items, 2))

        query = DiscoveryQuery(query="testing")
        await code_search_channel.search(query)

        # search() makes 2 calls (keywords + signal), both with max_pages=1
        assert rest_client.search.call_count == 2
        for call in rest_client.search.call_args_list:
            max_pages = call.kwargs.get("max_pages") or call[1].get("max_pages")
            assert max_pages == 1, f"Expected max_pages=1, got {max_pages}"


# --- search_quality_signals tests ---


class TestSearchQualitySignals:
    """Tests for CodeSearchChannel.search_quality_signals()."""

    async def test_search_quality_signals_by_language(
        self,
        code_search_channel: CodeSearchChannel,
        rest_client: GitHubRestClient,
        sample_code_search_response: dict[str, object],
    ) -> None:
        """Filters by language qualifier in quality signal queries."""
        items = sample_code_search_response["items"]
        assert isinstance(items, list)
        rest_client.search = AsyncMock(return_value=(items, 2))

        await code_search_channel.search_quality_signals(language="python")

        # Verify language qualifier was included in queries
        assert rest_client.search.call_count > 0
        for call in rest_client.search.call_args_list:
            query_arg = call.kwargs.get("query") or call[1].get("query", "")
            assert "language:python" in query_arg

    async def test_search_quality_signals_filters_by_signals(
        self,
        code_search_channel: CodeSearchChannel,
        rest_client: GitHubRestClient,
        sample_code_search_response: dict[str, object],
    ) -> None:
        """Only queries the specified signal categories."""
        items = sample_code_search_response["items"]
        assert isinstance(items, list)
        rest_client.search = AsyncMock(return_value=(items, 2))

        result = await code_search_channel.search_quality_signals(
            signals=["testing"],
        )

        # Should only call search for the "testing" category
        assert rest_client.search.call_count == 1
        assert result.channel == DiscoveryChannel.CODE_SEARCH

    async def test_search_quality_signals_empty(
        self,
        code_search_channel: CodeSearchChannel,
        rest_client: GitHubRestClient,
    ) -> None:
        """Empty results from all patterns → empty ChannelResult."""
        rest_client.search = AsyncMock(return_value=([], 0))

        result = await code_search_channel.search_quality_signals()

        assert isinstance(result, ChannelResult)
        assert len(result.candidates) == 0
        assert result.total_found == 0

    async def test_search_quality_signals_dedup_across_categories(
        self,
        code_search_channel: CodeSearchChannel,
        rest_client: GitHubRestClient,
    ) -> None:
        """Same repo found via multiple signal categories appears once."""
        # Same repo in every category result
        same_repo_items = [
            {
                "name": "conftest.py",
                "path": "tests/conftest.py",
                "sha": "abc123",
                "url": "https://api.github.com/repos/org/project/contents/tests/conftest.py",
                "html_url": "https://github.com/org/project/blob/main/tests/conftest.py",
                "repository": {
                    "full_name": "org/project",
                    "url": "https://api.github.com/repos/org/project",
                    "html_url": "https://github.com/org/project",
                },
                "score": 1.0,
            },
        ]
        rest_client.search = AsyncMock(return_value=(same_repo_items, 1))

        result = await code_search_channel.search_quality_signals()

        full_names = [c.full_name for c in result.candidates]
        assert full_names.count("org/project") == 1

    async def test_search_quality_signals_rate_limit_strict(
        self,
        code_search_channel: CodeSearchChannel,
        rest_client: GitHubRestClient,
        sample_code_search_response: dict[str, object],
    ) -> None:
        """Each quality signal query uses max_pages=1."""
        items = sample_code_search_response["items"]
        assert isinstance(items, list)
        rest_client.search = AsyncMock(return_value=(items, 2))

        await code_search_channel.search_quality_signals()

        for call in rest_client.search.call_args_list:
            max_pages = call.kwargs.get("max_pages") or call[1].get("max_pages")
            assert max_pages == 1, f"Expected max_pages=1, got {max_pages}"
