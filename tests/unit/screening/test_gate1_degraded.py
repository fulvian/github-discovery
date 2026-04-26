"""Tests for Gate 1 degraded scoring when GitHub API errors occur."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from github_discovery.config import ScreeningSettings
from github_discovery.discovery.github_client import GitHubRestClient
from github_discovery.exceptions import GitHubAuthError, GitHubRateLimitError
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import CandidateStatus, DiscoveryChannel
from github_discovery.screening.gate1_metadata import Gate1MetadataScreener


def _make_candidate(
    full_name: str = "test/repo",
) -> RepoCandidate:
    """Create a sample RepoCandidate for testing."""
    from datetime import UTC, datetime

    return RepoCandidate(
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        html_url=f"https://github.com/{full_name}",
        api_url=f"https://api.github.com/repos/{full_name}",
        description="Test repository",
        language="Python",
        stars=100,
        forks_count=10,
        watchers_count=5,
        subscribers_count=3,
        open_issues_count=5,
        created_at=datetime(2023, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 6, 1, tzinfo=UTC),
        pushed_at=datetime(2024, 6, 1, tzinfo=UTC),
        owner_login=full_name.split("/", maxsplit=1)[0],
        source_channel=DiscoveryChannel.SEARCH,
        commit_sha="abc123",
        status=CandidateStatus.DISCOVERED,
    )


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock GitHubRestClient."""
    client = AsyncMock(spec=GitHubRestClient)
    return client


@pytest.fixture
def screener(mock_client: AsyncMock) -> Gate1MetadataScreener:
    """Create a Gate1MetadataScreener with mock client."""
    return Gate1MetadataScreener(
        rest_client=mock_client,
        settings=ScreeningSettings(),
    )


class TestGate1DegradedScoring:
    """Tests for degraded scoring when API errors occur."""

    async def test_degraded_count_zero_on_success(
        self,
        screener: Gate1MetadataScreener,
        mock_client: AsyncMock,
    ) -> None:
        """When all API calls succeed, degraded_count is 0."""
        mock_client.get_json = AsyncMock(return_value={})
        candidate = _make_candidate()

        result = await screener.screen(candidate)
        assert result.degraded_count == 0

    async def test_degraded_count_on_auth_error(
        self,
        screener: Gate1MetadataScreener,
        mock_client: AsyncMock,
    ) -> None:
        """GitHubAuthError increments degraded_count, does not crash."""
        mock_client.get_json = AsyncMock(
            side_effect=GitHubAuthError("unauthorized", status_code=401),
        )
        candidate = _make_candidate()

        result = await screener.screen(candidate)
        # All 7 API calls should degrade
        assert result.degraded_count > 0

    async def test_degraded_count_on_rate_limit_error(
        self,
        screener: Gate1MetadataScreener,
        mock_client: AsyncMock,
    ) -> None:
        """GitHubRateLimitError increments degraded_count, does not crash."""
        mock_client.get_json = AsyncMock(
            side_effect=GitHubRateLimitError(retry_after=60, status_code=429),
        )
        candidate = _make_candidate()

        result = await screener.screen(candidate)
        assert result.degraded_count > 0

    async def test_mixed_success_and_failure(
        self,
        screener: Gate1MetadataScreener,
        mock_client: AsyncMock,
    ) -> None:
        """Some calls succeed, some fail — partial degradation."""
        call_count = 0

        async def _alternating(*args: object, **kwargs: object) -> object:
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise GitHubAuthError("unauthorized", status_code=401)
            return {}

        mock_client.get_json = AsyncMock(side_effect=_alternating)
        candidate = _make_candidate()

        result = await screener.screen(candidate)
        assert result.degraded_count > 0
        assert result.degraded_count < 7  # Some succeeded

    async def test_result_has_degraded_count_field(self) -> None:
        """MetadataScreenResult has a degraded_count field with default 0."""
        from github_discovery.models.screening import MetadataScreenResult

        result = MetadataScreenResult(full_name="test/repo")
        assert result.degraded_count == 0
