"""Tests for OpenSSF Scorecard API integration."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel, DomainType
from github_discovery.models.screening import SecurityHygieneScore
from github_discovery.screening.scorecard_adapter import ScorecardAdapter


def _make_candidate(language: str | None = "Python") -> RepoCandidate:
    """Build a test RepoCandidate."""
    return RepoCandidate(
        full_name="test-org/test-repo",
        url="https://github.com/test-org/test-repo",
        html_url="https://github.com/test-org/test-repo",
        api_url="https://api.github.com/repos/test-org/test-repo",
        description="Test repo",
        language=language,
        domain=DomainType.LIBRARY,
        stars=100,
        created_at=datetime(2023, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        owner_login="test-org",
        source_channel=DiscoveryChannel.SEARCH,
    )


class TestScorecardAdapter:
    """Tests for ScorecardAdapter."""

    async def test_score_from_api(self, httpx_mock: pytest.httpx.HTTPXMock) -> None:
        """Mock scorecard response with score 8.5 → value 0.85."""
        httpx_mock.add_response(
            url="https://api.scorecard.dev/projects/github.com/test-org/test-repo",
            json={
                "score": 8.5,
                "checks": [
                    {"name": "Branch-Protection", "score": 9},
                    {"name": "Token-Permissions", "score": 8},
                ],
            },
        )

        adapter = ScorecardAdapter()
        result = await adapter.score(_make_candidate())

        assert isinstance(result, SecurityHygieneScore)
        assert abs(result.value - 0.85) < 0.01
        assert result.confidence == 1.0
        await adapter.close()

    async def test_score_normalization(self, httpx_mock: pytest.httpx.HTTPXMock) -> None:
        """Score 10 → value 1.0, score 0 → value 0.0."""
        # Test score 10 → 1.0
        httpx_mock.add_response(
            url="https://api.scorecard.dev/projects/github.com/test-org/test-repo",
            json={"score": 10, "checks": []},
        )

        adapter = ScorecardAdapter()
        result = await adapter.score(_make_candidate())
        assert result.value == 1.0
        await adapter.close()

        # Test score 0 → 0.0
        httpx_mock.add_response(
            url="https://api.scorecard.dev/projects/github.com/test-org/test-repo",
            json={"score": 0, "checks": []},
        )

        adapter2 = ScorecardAdapter()
        result2 = await adapter2.score(_make_candidate())
        assert result2.value == 0.0
        await adapter2.close()

    async def test_repo_not_scored(self, httpx_mock: pytest.httpx.HTTPXMock) -> None:
        """Mock 404 → value=0.3 (aligned with gate2 fallback), confidence=0.0."""
        httpx_mock.add_response(
            url="https://api.scorecard.dev/projects/github.com/test-org/test-repo",
            status_code=404,
        )

        adapter = ScorecardAdapter()
        result = await adapter.score(_make_candidate())

        assert result.value == 0.5  # TB2 unified fallback: neutral
        assert result.confidence == 0.0
        assert "not scored" in result.notes[0].lower()
        await adapter.close()

    async def test_api_timeout(self, httpx_mock: pytest.httpx.HTTPXMock) -> None:
        """Mock timeout → value=0.3 (aligned with gate2 fallback), confidence=0.0."""
        httpx_mock.add_exception(
            httpx.TimeoutException("timeout"),
            url="https://api.scorecard.dev/projects/github.com/test-org/test-repo",
        )

        adapter = ScorecardAdapter()
        result = await adapter.score(_make_candidate())

        assert result.value == 0.5  # TB2 unified fallback: neutral
        assert result.confidence == 0.0
        assert "timed out" in result.notes[0].lower()
        await adapter.close()

    async def test_details_contain_checks(self, httpx_mock: pytest.httpx.HTTPXMock) -> None:
        """Details dict includes individual check scores."""
        httpx_mock.add_response(
            url="https://api.scorecard.dev/projects/github.com/test-org/test-repo",
            json={
                "score": 7.5,
                "checks": [
                    {"name": "Branch-Protection", "score": 9},
                    {"name": "Token-Permissions", "score": 6},
                ],
            },
        )

        adapter = ScorecardAdapter()
        result = await adapter.score(_make_candidate())

        assert "scorecard_score" in result.details
        assert result.details["Branch-Protection"] == 9
        assert result.details["Token-Permissions"] == 6
        await adapter.close()

    async def test_score_with_zero(self, httpx_mock: pytest.httpx.HTTPXMock) -> None:
        """Score 0 with checks → value=0.0, confidence=1.0."""
        httpx_mock.add_response(
            url="https://api.scorecard.dev/projects/github.com/test-org/test-repo",
            json={
                "score": 0,
                "checks": [
                    {"name": "Branch-Protection", "score": 0},
                ],
            },
        )

        adapter = ScorecardAdapter()
        result = await adapter.score(_make_candidate())

        assert result.value == 0.0
        assert result.confidence == 1.0
        await adapter.close()
