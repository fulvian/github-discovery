"""Shared fixtures for integration tests.

Provides settings, API client, and frozen test data fixtures
used across all integration test modules.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from github_discovery.config import APISettings, GitHubSettings, Settings
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel, DomainType


@pytest.fixture
def integration_settings(tmp_path: Path) -> Settings:
    """Settings with temp databases and test token for integration tests."""
    job_db = str(tmp_path / "jobs.db")
    return Settings(
        github=GitHubSettings(token="ghp_test_integration"),  # noqa: S106
        api=APISettings(job_store_path=job_db),
    )


@pytest.fixture
async def api_client(integration_settings: Settings) -> AsyncClient:
    """httpx AsyncClient wired to the FastAPI app via ASGITransport.

    Manually runs the lifespan so app.state attributes are available,
    then yields the client, and finally shuts down the lifespan.
    """
    from github_discovery.api.app import create_app

    with patch(
        "github_discovery.assessment.orchestrator.RepomixAdapter",
    ):
        app = create_app(integration_settings)

        # Run lifespan manually to set up app.state before requests
        lifespan_cm = app.router.lifespan_context(app)
        await lifespan_cm.__aenter__()

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                yield client
        finally:
            await lifespan_cm.__aexit__(None, None, None)


@pytest.fixture
def sample_repos_frozen() -> list[RepoCandidate]:
    """Load frozen repo candidates from tests/fixtures/sample_repos.json."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_repos.json"
    data = json.loads(fixture_path.read_text())
    return [RepoCandidate.model_validate(r) for r in data["repos"]]


def _make_candidate(
    full_name: str = "test-org/test-repo",
    *,
    stars: int = 100,
    language: str | None = "Python",
    domain: DomainType = DomainType.LIBRARY,
    source_channel: DiscoveryChannel = DiscoveryChannel.SEARCH,
    discovery_score: float = 0.8,
    commit_sha: str = "a" * 40,
) -> RepoCandidate:
    """Helper to create a RepoCandidate with sensible defaults."""
    from datetime import UTC, datetime

    return RepoCandidate(
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        html_url=f"https://github.com/{full_name}",
        api_url=f"https://api.github.com/repos/{full_name}",
        description="A test repository for integration testing",
        language=language,
        domain=domain,
        stars=stars,
        forks_count=stars // 10,
        open_issues_count=5,
        created_at=datetime(2022, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        pushed_at=datetime(2026, 1, 1, tzinfo=UTC),
        license_info={"spdx_id": "MIT", "name": "MIT License"},
        owner_login=full_name.split("/", maxsplit=1)[0],
        source_channel=source_channel,
        discovery_score=discovery_score,
        commit_sha=commit_sha,
    )
