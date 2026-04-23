"""FastAPI dependency injection providers.

Each provider reads its service from ``request.app.state`` attributes
set during the application lifespan startup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request  # noqa: TC002

from github_discovery.config import Settings  # noqa: TC001
from github_discovery.workers.job_store import JobStore  # noqa: TC001
from github_discovery.workers.queue import AsyncTaskQueue  # noqa: TC001
from github_discovery.workers.worker_manager import WorkerManager  # noqa: TC001

if TYPE_CHECKING:
    from github_discovery.assessment.orchestrator import AssessmentOrchestrator
    from github_discovery.discovery.orchestrator import DiscoveryOrchestrator
    from github_discovery.discovery.pool import PoolManager
    from github_discovery.scoring.engine import ScoringEngine
    from github_discovery.scoring.ranker import Ranker
    from github_discovery.screening.orchestrator import ScreeningOrchestrator


def get_settings(request: Request) -> Settings:
    """Provide application settings from app state."""
    return request.app.state.settings  # type: ignore[no-any-return]


def get_job_store(request: Request) -> JobStore:
    """Provide the job store from app state."""
    return request.app.state.job_store  # type: ignore[no-any-return]


def get_queue(request: Request) -> AsyncTaskQueue:
    """Provide the task queue from app state."""
    return request.app.state.queue  # type: ignore[no-any-return]


def get_pool_manager(request: Request) -> PoolManager:
    """Provide the pool manager from app state."""
    return request.app.state.pool_manager  # type: ignore[no-any-return]


def get_discovery_orch(request: Request) -> DiscoveryOrchestrator:
    """Provide the discovery orchestrator from app state."""
    return request.app.state.discovery_orch  # type: ignore[no-any-return]


def get_screening_orch(request: Request) -> ScreeningOrchestrator:
    """Provide the screening orchestrator from app state."""
    return request.app.state.screening_orch  # type: ignore[no-any-return]


def get_assessment_orch(request: Request) -> AssessmentOrchestrator:
    """Provide the assessment orchestrator from app state."""
    return request.app.state.assessment_orch  # type: ignore[no-any-return]


def get_scoring_engine(request: Request) -> ScoringEngine:
    """Provide the scoring engine from app state."""
    return request.app.state.scoring_engine  # type: ignore[no-any-return]


def get_ranker(request: Request) -> Ranker:
    """Provide the ranker from app state."""
    return request.app.state.ranker  # type: ignore[no-any-return]


def get_worker_manager(request: Request) -> WorkerManager:
    """Provide the worker manager from app state."""
    return request.app.state.worker_manager  # type: ignore[no-any-return]
