"""Tests for Gate 1 — Metadata screening engine."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from github_discovery.config import ScreeningSettings
from github_discovery.discovery.github_client import GitHubRestClient
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel, DomainType
from github_discovery.models.screening import MetadataScreenResult
from github_discovery.screening.gate1_metadata import Gate1MetadataScreener


def _make_candidate(
    full_name: str = "test-org/test-repo",
    archived: bool = False,
    disabled: bool = False,
    language: str | None = "Python",
) -> RepoCandidate:
    """Build a test RepoCandidate."""
    return RepoCandidate(
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        html_url=f"https://github.com/{full_name}",
        api_url=f"https://api.github.com/repos/{full_name}",
        description="Test repo",
        language=language,
        topics=["testing"],
        domain=DomainType.LIBRARY,
        stars=100,
        created_at=datetime(2023, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        pushed_at=datetime(2026, 4, 1, tzinfo=UTC),
        license_info={"spdx_id": "MIT", "name": "MIT License"},
        owner_login=full_name.split("/", maxsplit=1)[0],
        archived=archived,
        disabled=disabled,
        source_channel=DiscoveryChannel.SEARCH,
        commit_sha="abc123",
    )


def _make_mock_client() -> AsyncMock:
    """Build a mock GitHubRestClient returning rich data."""
    client = AsyncMock(spec=GitHubRestClient)

    _RESPONSES: dict[str, object] = {
        "/contents": [
            {"name": "README.md"},
            {"name": "LICENSE"},
            {"name": "pyproject.toml"},
            {"name": "tests"},
        ],
        "/releases": [{"tag_name": "v1.0.0", "name": "Release 1.0"}],
        "/commits": [{"sha": "abc123", "commit": {"message": "init"}}],
        "/issues": [{"number": 1, "state": "closed"}],
        "/pulls": [{"number": 1, "state": "closed", "merged_at": "2026-01-01"}],
        "/languages": {"Python": 45000},
    }

    async def _get_json(
        url: str,
        *,
        params: dict[str, str | int] | None = None,
    ) -> object:
        return next((v for k, v in _RESPONSES.items() if k in url), {})

    client.get_json = AsyncMock(side_effect=_get_json)
    return client


@pytest.fixture
def mock_client() -> AsyncMock:
    """Provide a mock GitHubRestClient."""
    return _make_mock_client()


@pytest.fixture
def screener(mock_client: AsyncMock) -> Gate1MetadataScreener:
    """Provide a Gate1MetadataScreener with mock client."""
    return Gate1MetadataScreener(
        rest_client=mock_client,
        settings=ScreeningSettings(),
    )


class TestGate1MetadataScreener:
    """Tests for Gate1MetadataScreener."""

    async def test_screen_returns_metadata_result(
        self,
        screener: Gate1MetadataScreener,
    ) -> None:
        """screen() returns a MetadataScreenResult."""
        candidate = _make_candidate()
        result = await screener.screen(candidate)

        assert isinstance(result, MetadataScreenResult)
        assert result.full_name == "test-org/test-repo"
        assert result.commit_sha == "abc123"

    async def test_screen_computes_gate1_total(
        self,
        screener: Gate1MetadataScreener,
    ) -> None:
        """screen() computes gate1_total from sub-scores."""
        candidate = _make_candidate()
        result = await screener.screen(candidate)

        # gate1_total should be computed and non-negative
        assert result.gate1_total >= 0.0
        assert result.gate1_total <= 1.0

    async def test_screen_applies_threshold_pass(
        self,
        screener: Gate1MetadataScreener,
    ) -> None:
        """screen() passes with high scores above threshold."""
        candidate = _make_candidate()
        result = await screener.screen(candidate, threshold=0.01)

        assert result.gate1_pass is True
        assert result.gate1_total >= 0.01

    async def test_screen_applies_threshold_fail(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """screen() fails with very high threshold."""
        # Override get_json to return empty data → low scores
        mock_client.get_json = AsyncMock(return_value=None)
        screener = Gate1MetadataScreener(
            rest_client=mock_client,
            settings=ScreeningSettings(),
        )
        candidate = _make_candidate()
        result = await screener.screen(candidate, threshold=0.99)

        assert result.gate1_pass is False
        assert result.threshold_used == 0.99

    async def test_screen_custom_threshold(
        self,
        screener: Gate1MetadataScreener,
    ) -> None:
        """screen() uses custom threshold when provided."""
        candidate = _make_candidate()
        result = await screener.screen(candidate, threshold=0.1)

        assert result.threshold_used == 0.1

    async def test_screen_archived_repo_auto_fail(
        self,
        screener: Gate1MetadataScreener,
    ) -> None:
        """Archived repos auto-fail with gate1_total=0.0."""
        candidate = _make_candidate(archived=True)
        result = await screener.screen(candidate)

        assert result.gate1_total == 0.0
        assert result.gate1_pass is False

    async def test_screen_error_isolation(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """Error in one checker does not prevent others from scoring."""
        screener = Gate1MetadataScreener(
            rest_client=mock_client,
            settings=ScreeningSettings(),
        )

        # Make one checker raise an error
        original_score = screener._hygiene.score
        call_count = 0

        def failing_score(ctx: object) -> object:
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                msg = "Simulated checker failure"
                raise RuntimeError(msg)
            return original_score(ctx)

        screener._hygiene.score = failing_score  # type: ignore[assignment]

        candidate = _make_candidate()
        result = await screener.screen(candidate)

        # Result should still be produced (not raise)
        assert isinstance(result, MetadataScreenResult)
        # The failing checker should have value=0.0 from error isolation
        assert result.hygiene.value == 0.0
        assert result.hygiene.confidence == 0.0
        # Other checkers should still have computed values
        assert result.maintenance.value >= 0.0

    async def test_screen_batch_concurrent(
        self,
        screener: Gate1MetadataScreener,
    ) -> None:
        """screen_batch() screens multiple candidates concurrently."""
        candidates = [_make_candidate(f"org/repo-{i}") for i in range(5)]
        results = await screener.screen_batch(candidates)

        assert len(results) == 5
        for i, result in enumerate(results):
            assert isinstance(result, MetadataScreenResult)
            assert result.full_name == f"org/repo-{i}"
