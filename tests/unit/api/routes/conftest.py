"""Shared test fixtures for API route tests.

Creates a FastAPI test app with dependency overrides for mock services
(job store, queue, pool manager, scoring engine).
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from github_discovery.api.app import create_app
from github_discovery.api.deps import (
    get_job_store,
    get_pool_manager,
    get_queue,
    get_ranker,
    get_scoring_engine,
)
from github_discovery.config import APISettings, Settings
from github_discovery.workers.types import Job, JobStatus, JobType


@pytest.fixture
def mock_job_store() -> AsyncMock:
    """Create a mock JobStore with standard async methods."""
    store = AsyncMock()
    store.get = AsyncMock(return_value=None)
    store.create = AsyncMock()
    store.list_jobs = AsyncMock(return_value=[])
    return store


@pytest.fixture
def mock_queue() -> AsyncMock:
    """Create a mock AsyncTaskQueue that returns the enqueued job."""

    async def _enqueue(job: Job) -> Job:
        return job

    queue = AsyncMock()
    queue.enqueue = AsyncMock(side_effect=_enqueue)
    return queue


@pytest.fixture
def mock_pool_manager() -> AsyncMock:
    """Create a mock PoolManager."""
    pm = AsyncMock()
    pm.get_pool = AsyncMock(return_value=None)
    return pm


@pytest.fixture
def mock_scoring_engine() -> MagicMock:
    """Create a mock ScoringEngine with a mock FeatureStore."""
    engine = MagicMock()
    mock_store = AsyncMock()
    mock_store.get_by_domain = AsyncMock(return_value=[])
    mock_store.get_latest = AsyncMock(return_value=None)
    engine.feature_store = mock_store
    return engine


@pytest.fixture
def mock_ranker() -> MagicMock:
    """Create a mock Ranker."""
    return MagicMock()


@pytest.fixture
def app_with_overrides(
    mock_job_store: AsyncMock,
    mock_queue: AsyncMock,
    mock_pool_manager: AsyncMock,
    mock_scoring_engine: MagicMock,
    mock_ranker: MagicMock,
) -> Generator[FastAPI]:
    """Create a FastAPI app with dependency overrides for route tests.

    Uses in-memory SQLite for the lifespan, then overrides the
    dependencies with mocks so routes don't hit real services.
    """
    settings = Settings(
        api=APISettings(
            job_store_path=":memory:",
        ),
    )
    application = create_app(settings)

    # Override dependencies with mocks
    application.dependency_overrides[get_job_store] = lambda: mock_job_store
    application.dependency_overrides[get_queue] = lambda: mock_queue
    application.dependency_overrides[get_pool_manager] = lambda: mock_pool_manager
    application.dependency_overrides[get_scoring_engine] = lambda: mock_scoring_engine
    application.dependency_overrides[get_ranker] = lambda: mock_ranker

    yield application

    # Clean up overrides
    application.dependency_overrides.clear()


@pytest.fixture
def client(app_with_overrides: FastAPI) -> Generator[TestClient]:
    """Create a TestClient with dependency overrides."""
    with TestClient(app_with_overrides) as c:
        yield c


def make_discovery_job(
    *,
    job_id: str = "test-job-123",
    status: JobStatus = JobStatus.PENDING,
    result: dict[str, object] | None = None,
    session_id: str | None = None,
) -> Job:
    """Helper to create a discovery Job for testing."""
    input_data: dict[str, object] = {
        "query": "test query",
        "channels": ["search"],
        "max_candidates": 100,
    }
    if session_id is not None:
        input_data["session_id"] = session_id
    return Job(
        job_id=job_id,
        job_type=JobType.DISCOVERY,
        status=status,
        input_data=input_data,
        result=result,
    )


def make_screening_job(
    *,
    job_id: str = "screen-job-456",
    status: JobStatus = JobStatus.PENDING,
    result: dict[str, object] | None = None,
    pool_id: str = "pool-abc",
    session_id: str | None = None,
) -> Job:
    """Helper to create a screening Job for testing."""
    input_data: dict[str, object] = {
        "pool_id": pool_id,
        "gate_level": "1",
    }
    if session_id is not None:
        input_data["session_id"] = session_id
    return Job(
        job_id=job_id,
        job_type=JobType.SCREENING,
        status=status,
        input_data=input_data,
        result=result,
    )


def make_assessment_job(
    *,
    job_id: str = "assess-job-789",
    status: JobStatus = JobStatus.PENDING,
    result: dict[str, object] | None = None,
    session_id: str | None = None,
) -> Job:
    """Helper to create an assessment Job for testing."""
    input_data: dict[str, object] = {
        "repo_urls": ["https://github.com/test/repo"],
    }
    if session_id is not None:
        input_data["session_id"] = session_id
    return Job(
        job_id=job_id,
        job_type=JobType.ASSESSMENT,
        status=status,
        input_data=input_data,
        result=result,
    )
