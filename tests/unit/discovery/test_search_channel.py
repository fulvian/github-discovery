"""Tests for the SearchChannel discovery channel.

Tests cover query building, result mapping, max_candidates enforcement,
empty results, and incomplete results warning.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from github_discovery.config import DiscoverySettings, GitHubSettings, Settings
from github_discovery.discovery.github_client import GitHubRestClient
from github_discovery.discovery.search_channel import SearchChannel
from github_discovery.discovery.types import ChannelResult, DiscoveryQuery
from github_discovery.models.enums import DiscoveryChannel, DomainType

# --- Fixtures ---


@pytest.fixture
def rest_client(github_settings: GitHubSettings) -> GitHubRestClient:
    """Create a GitHubRestClient for testing."""
    return GitHubRestClient(github_settings)


@pytest.fixture
def search_channel(rest_client: GitHubRestClient) -> SearchChannel:
    """Create a SearchChannel instance for testing."""
    return SearchChannel(rest_client)


# --- build_query tests ---


class TestBuildQuery:
    """Tests for SearchChannel.build_query()."""

    def test_build_query_basic(self, search_channel: SearchChannel) -> None:
        """Basic keyword-only query includes keyword and default qualifiers."""
        query = DiscoveryQuery(query="python testing")
        result = search_channel.build_query(query)

        assert "python testing" in result
        assert "archived:false" in result
        assert "is:public" in result
        assert "pushed:>" in result

    def test_build_query_with_language_filter(
        self,
        search_channel: SearchChannel,
    ) -> None:
        """Query with language filter includes language: qualifier."""
        query = DiscoveryQuery(query="web framework", language="python")
        result = search_channel.build_query(query)

        assert "language:python" in result
        assert "web framework" in result

    def test_build_query_with_topics(
        self,
        search_channel: SearchChannel,
    ) -> None:
        """Query with topics includes topic: qualifiers for each topic."""
        query = DiscoveryQuery(query="testing", topics=["testing", "web"])
        result = search_channel.build_query(query)

        assert "topic:testing" in result
        assert "topic:web" in result
        assert "testing" in result

    def test_build_query_excludes_archived(
        self,
        search_channel: SearchChannel,
    ) -> None:
        """Query always includes archived:false qualifier."""
        query = DiscoveryQuery(query="python")
        result = search_channel.build_query(query)

        assert "archived:false" in result

    def test_build_query_excludes_inactive(
        self,
        search_channel: SearchChannel,
    ) -> None:
        """Query always includes pushed:> qualifier with ~6-month cutoff date."""
        query = DiscoveryQuery(query="python")
        result = search_channel.build_query(query)

        assert "pushed:>" in result

        # Extract date from pushed:>YYYY-MM-DD qualifier
        pushed_parts = [p for p in result.split() if p.startswith("pushed:>")]
        assert len(pushed_parts) == 1
        date_str = pushed_parts[0].split(">")[1]
        cutoff_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
        expected_cutoff = datetime.now(UTC) - timedelta(days=180)
        # Allow 2-day tolerance for test execution timing
        assert abs((cutoff_date - expected_cutoff).total_seconds()) <= 172800

    def test_build_query_public_only(
        self,
        search_channel: SearchChannel,
    ) -> None:
        """Query always includes is:public qualifier."""
        query = DiscoveryQuery(query="python")
        result = search_channel.build_query(query)

        assert "is:public" in result

    def test_build_query_uses_domain_aware_activity_threshold(
        self,
        search_channel: SearchChannel,
    ) -> None:
        """LANG_TOOL domain hint uses 365d activity threshold (not 180d)."""
        query = DiscoveryQuery(query="python", domain_hint=DomainType.LANG_TOOL)
        result = search_channel.build_query(query)

        pushed_parts = [p for p in result.split() if p.startswith("pushed:>")]
        assert len(pushed_parts) == 1
        date_str = pushed_parts[0].split(">")[1]
        cutoff_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
        expected_cutoff = datetime.now(UTC) - timedelta(days=365)
        assert abs((cutoff_date - expected_cutoff).total_seconds()) <= 172800

    def test_build_query_config_override_highest_priority(
        self,
        rest_client: GitHubRestClient,
    ) -> None:
        """Config activity_days override takes priority over domain hint."""
        settings = Settings(
            github=GitHubSettings(token="test_token"),  # noqa: S106
            discovery=DiscoverySettings(activity_days=60),
        )
        channel = SearchChannel(rest_client, settings=settings)
        query = DiscoveryQuery(query="python", domain_hint=DomainType.LANG_TOOL)
        result = channel.build_query(query)

        pushed_parts = [p for p in result.split() if p.startswith("pushed:>")]
        assert len(pushed_parts) == 1
        date_str = pushed_parts[0].split(">")[1]
        cutoff_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
        expected_cutoff = datetime.now(UTC) - timedelta(days=60)
        assert abs((cutoff_date - expected_cutoff).total_seconds()) <= 172800


# --- search tests ---


class TestSearch:
    """Tests for SearchChannel.search()."""

    async def test_search_returns_channel_result(
        self,
        search_channel: SearchChannel,
        rest_client: GitHubRestClient,
        sample_search_response: dict[str, object],
    ) -> None:
        """Search returns a ChannelResult with correct channel type."""
        items = sample_search_response["items"]
        assert isinstance(items, list)
        rest_client.search = AsyncMock(return_value=(items, 3))

        query = DiscoveryQuery(query="python web framework")
        result = await search_channel.search(query)

        assert isinstance(result, ChannelResult)
        assert result.channel == DiscoveryChannel.SEARCH
        assert len(result.candidates) == 3
        assert result.total_found == 3

    async def test_search_maps_to_repo_candidate(
        self,
        search_channel: SearchChannel,
        rest_client: GitHubRestClient,
        sample_search_response: dict[str, object],
    ) -> None:
        """Search correctly maps API items to RepoCandidate fields."""
        items = sample_search_response["items"]
        assert isinstance(items, list)
        rest_client.search = AsyncMock(return_value=(items, 3))

        query = DiscoveryQuery(query="python web framework")
        result = await search_channel.search(query)

        flask = result.candidates[0]
        assert flask.full_name == "pallets/flask"
        assert flask.html_url == "https://github.com/pallets/flask"
        assert flask.api_url == "https://api.github.com/repos/pallets/flask"
        assert flask.language == "Python"
        assert flask.stars == 67000
        assert flask.forks_count == 16000
        assert flask.open_issues_count == 10
        assert flask.size_kb == 5000
        assert flask.default_branch == "main"
        assert flask.archived is False
        assert flask.disabled is False
        assert flask.owner_login == "pallets"
        assert flask.source_channel == DiscoveryChannel.SEARCH
        assert flask.description == "The Python micro framework"
        assert "python" in flask.topics
        assert "flask" in flask.topics
        assert flask.license_info is not None
        assert flask.license_info.get("spdx_id") == "BSD-3-Clause"
        assert 0.0 <= flask.discovery_score <= 1.0

    async def test_search_respects_max_candidates(
        self,
        search_channel: SearchChannel,
        rest_client: GitHubRestClient,
        sample_search_response: dict[str, object],
    ) -> None:
        """Search truncates results to max_candidates."""
        items = sample_search_response["items"]
        assert isinstance(items, list)
        rest_client.search = AsyncMock(return_value=(items, 100))

        query = DiscoveryQuery(query="python", max_candidates=2)
        result = await search_channel.search(query)

        assert len(result.candidates) == 2
        assert result.total_found == 100
        assert result.has_more is True

    async def test_search_empty_results(
        self,
        search_channel: SearchChannel,
        rest_client: GitHubRestClient,
    ) -> None:
        """Search with no results returns empty ChannelResult."""
        rest_client.search = AsyncMock(return_value=([], 0))

        query = DiscoveryQuery(query="nonexistent-xyz-abc-123")
        result = await search_channel.search(query)

        assert isinstance(result, ChannelResult)
        assert result.channel == DiscoveryChannel.SEARCH
        assert len(result.candidates) == 0
        assert result.total_found == 0
        assert result.has_more is False

    async def test_search_incomplete_results_warning(
        self,
        search_channel: SearchChannel,
        rest_client: GitHubRestClient,
        sample_search_response: dict[str, object],
    ) -> None:
        """When total_count >> returned items, channel logs a warning."""
        items = sample_search_response["items"]
        assert isinstance(items, list)
        # Return 1 item but total_count=10000 (incomplete)
        rest_client.search = AsyncMock(
            return_value=([items[0]], 10000),
        )

        query = DiscoveryQuery(query="python web framework")
        with patch(
            "github_discovery.discovery.search_channel.logger",
        ) as mock_logger:
            result = await search_channel.search(query)

        mock_logger.warning.assert_called_once()
        call_kwargs = mock_logger.warning.call_args
        assert call_kwargs[0][0] == "search_results_potentially_incomplete"
        assert result.total_found == 10000
