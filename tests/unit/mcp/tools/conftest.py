"""Shared test fixtures for MCP tool tests.

Provides mock orchestrators and services that tools depend on,
so tool functions can be tested in isolation without real I/O.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


@pytest.fixture
def mock_pool_manager():
    """Create a mock PoolManager with a sample pool."""
    from github_discovery.models.candidate import CandidatePool, RepoCandidate
    from github_discovery.models.enums import DiscoveryChannel

    pool_id = str(uuid4())

    now = datetime.now(UTC)
    candidates = [
        RepoCandidate(
            full_name="owner/repo-1",
            url="https://github.com/owner/repo-1",
            html_url="https://github.com/owner/repo-1",
            api_url="https://api.github.com/repos/owner/repo-1",
            owner_login="owner",
            source_channel=DiscoveryChannel.SEARCH,
            discovery_score=0.85,
            stars=100,
            language="Python",
            created_at=now,
            updated_at=now,
        ),
        RepoCandidate(
            full_name="owner/repo-2",
            url="https://github.com/owner/repo-2",
            html_url="https://github.com/owner/repo-2",
            api_url="https://api.github.com/repos/owner/repo-2",
            owner_login="owner",
            source_channel=DiscoveryChannel.SEARCH,
            discovery_score=0.6,
            stars=50,
            language="Rust",
            created_at=now,
            updated_at=now,
        ),
    ]

    pool = CandidatePool(
        pool_id=pool_id,
        query="test query",
        candidates=candidates,
    )

    mock = AsyncMock()
    mock.get_pool = AsyncMock(return_value=pool)
    mock.close = AsyncMock()
    return mock, pool_id


@pytest.fixture
def mock_discovery_orchestrator():
    """Create a mock DiscoveryOrchestrator that returns a sample DiscoveryResult."""
    from github_discovery.discovery.types import DiscoveryResult
    from github_discovery.models.enums import DiscoveryChannel

    pool_id = str(uuid4())
    result = DiscoveryResult(
        pool_id=pool_id,
        total_candidates=42,
        channels_used=[DiscoveryChannel.SEARCH, DiscoveryChannel.REGISTRY],
        duplicate_count=3,
        elapsed_seconds=1.5,
    )

    mock = AsyncMock()
    mock.discover = AsyncMock(return_value=result)
    return mock, pool_id


@pytest.fixture
def mock_screening_orchestrator():
    """Create a mock ScreeningOrchestrator that returns sample ScreeningResults."""
    from github_discovery.models.screening import (
        MetadataScreenResult,
        ScreeningResult,
        StaticScreenResult,
    )

    results = [
        ScreeningResult(
            full_name="owner/repo-1",
            gate1=MetadataScreenResult(
                full_name="owner/repo-1",
                gate1_total=0.7,
                gate1_pass=True,
            ),
            gate2=StaticScreenResult(
                full_name="owner/repo-1",
                gate2_total=0.6,
                gate2_pass=True,
            ),
        ),
        ScreeningResult(
            full_name="owner/repo-2",
            gate1=MetadataScreenResult(
                full_name="owner/repo-2",
                gate1_total=0.3,
                gate1_pass=False,
            ),
            gate2=StaticScreenResult(
                full_name="owner/repo-2",
                gate2_total=0.4,
                gate2_pass=False,
            ),
        ),
    ]

    mock = AsyncMock()
    mock.screen = AsyncMock(return_value=results)
    mock.quick_screen = AsyncMock(return_value=results[0])
    return mock


@pytest.fixture
def mock_assessment_orchestrator():
    """Create a mock AssessmentOrchestrator."""
    from github_discovery.models.assessment import DeepAssessmentResult, DimensionScore
    from github_discovery.models.enums import ScoreDimension

    results = [
        DeepAssessmentResult(
            full_name="owner/repo-1",
            commit_sha="abc123",
            overall_quality=0.82,
            overall_confidence=0.78,
            gate3_pass=True,
            dimensions={
                ScoreDimension.CODE_QUALITY: DimensionScore(
                    dimension=ScoreDimension.CODE_QUALITY,
                    value=0.85,
                    explanation="Good code",
                ),
                ScoreDimension.TESTING: DimensionScore(
                    dimension=ScoreDimension.TESTING,
                    value=0.8,
                    explanation="Well tested",
                ),
            },
            cached=False,
        ),
    ]

    mock = AsyncMock()
    mock.assess = AsyncMock(return_value=results)
    mock.quick_assess = AsyncMock(return_value=results[0])
    mock.close = AsyncMock()
    mock.cache_size = 5
    return mock


@pytest.fixture
def mock_ranker():
    """Create a mock Ranker."""
    from github_discovery.models.enums import DomainType
    from github_discovery.models.scoring import RankedRepo, ScoreResult

    score_result = ScoreResult(
        full_name="owner/repo-1",
        commit_sha="abc123",
        domain=DomainType.OTHER,
        quality_score=0.82,
        confidence=0.78,
        stars=100,
        gate1_total=0.7,
        gate2_total=0.6,
        gate3_available=True,
    )

    ranked_repo = RankedRepo(
        rank=1,
        full_name="owner/repo-1",
        domain=DomainType.OTHER,
        score_result=score_result,
    )

    ranking = MagicMock()
    ranking.ranked_repos = [ranked_repo]
    ranking.total_candidates = 10
    ranking.hidden_gems = [ranked_repo]

    mock = MagicMock()
    mock.rank = MagicMock(return_value=ranking)
    return mock
