"""FastAPI application factory for the GitHub Discovery API.

Creates and configures a FastAPI application with lifespan management,
CORS middleware, request tracing, timing, and error handlers.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from github_discovery.api.errors import register_error_handlers
from github_discovery.api.middleware import (
    RateLimiter,
    rate_limit_middleware,
    request_id_middleware,
    timing_middleware,
)
from github_discovery.config import Settings
from github_discovery.workers.job_store import JobStore
from github_discovery.workers.queue import AsyncTaskQueue

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


logger = structlog.get_logger("github_discovery.api.app")


def create_app(settings: Settings | None = None) -> FastAPI:  # noqa: PLR0915
    """Create and configure the FastAPI application.

    Args:
        settings: Application settings. Created from env if None.

    Returns:
        Configured FastAPI application instance.
    """
    if settings is None:
        settings = Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Manage application startup and shutdown lifecycle."""
        from github_discovery.assessment.orchestrator import AssessmentOrchestrator
        from github_discovery.discovery.github_client import GitHubRestClient
        from github_discovery.discovery.orchestrator import DiscoveryOrchestrator
        from github_discovery.discovery.pool import PoolManager
        from github_discovery.scoring.engine import ScoringEngine
        from github_discovery.scoring.feature_store import FeatureStore
        from github_discovery.scoring.ranker import Ranker
        from github_discovery.screening.gate1_metadata import Gate1MetadataScreener
        from github_discovery.screening.gate2_static import Gate2StaticScreener
        from github_discovery.screening.orchestrator import ScreeningOrchestrator

        # Startup
        job_store = JobStore(settings.api.job_store_path)
        await job_store.initialize()

        pool_manager = PoolManager(":memory:")

        discovery_orch = DiscoveryOrchestrator(settings, pool_manager)

        # Create screeners and screening orchestrator
        rest_client = GitHubRestClient(settings.github)
        gate1_screener = Gate1MetadataScreener(rest_client, settings.screening)
        gate2_screener = Gate2StaticScreener(
            rest_client,
            settings.screening,
            settings.github,
        )
        screening_orch = ScreeningOrchestrator(settings, gate1_screener, gate2_screener)

        assessment_orch = AssessmentOrchestrator(settings)

        # Initialize scoring with persistent feature store
        feature_store = FeatureStore(
            db_path=".ghdisc/api_features.db",
            ttl_hours=settings.scoring.feature_store_ttl_hours,
        )
        await feature_store.initialize()
        scoring_engine = ScoringEngine(settings.scoring, store=feature_store)
        ranker = Ranker(settings.scoring)
        queue = AsyncTaskQueue(job_store)

        from github_discovery.workers.worker_manager import WorkerManager

        worker_manager = WorkerManager(
            queue=queue,
            job_store=job_store,
            discovery_orch=discovery_orch,
            screening_orch=screening_orch,
            assessment_orch=assessment_orch,
            workers_per_type=settings.api.workers,
        )
        await worker_manager.start()

        app.state.settings = settings
        app.state.rate_limiter = RateLimiter(
            max_requests=settings.api.rate_limit_per_minute,
        )
        app.state.job_store = job_store
        app.state.queue = queue
        app.state.pool_manager = pool_manager
        app.state.discovery_orch = discovery_orch
        app.state.screening_orch = screening_orch
        app.state.assessment_orch = assessment_orch
        app.state.scoring_engine = scoring_engine
        app.state.ranker = ranker
        app.state.feature_store = feature_store
        app.state.worker_manager = worker_manager

        logger.info("api_startup_complete")

        yield

        # Shutdown
        await worker_manager.stop()
        await feature_store.close()
        await pool_manager.close()
        await job_store.close()
        await assessment_orch.close()

        logger.info("api_shutdown_complete")

    from github_discovery.api.auth import verify_api_key
    from github_discovery.api.routes import (
        assessment_router,
        discovery_router,
        export_router,
        ranking_router,
        screening_router,
    )

    # Apply API key auth to all /api/v1 routes (skips health endpoints)
    auth_dep = [Depends(verify_api_key)] if settings.api.api_key else []

    app = FastAPI(
        title="GitHub Discovery API",
        description="REST API for the GitHub Discovery agentic scoring engine",
        version=settings.version,
        lifespan=lifespan,
        servers=[
            {"url": f"http://{settings.api.host}:{settings.api.port}", "description": "Local dev"},
        ],
        openapi_tags=[
            {"name": "health", "description": "Health and readiness checks"},
            {"name": "discovery", "description": "Candidate discovery (Layer A)"},
            {"name": "screening", "description": "Quality screening (Layer B)"},
            {"name": "assessment", "description": "Deep technical assessment (Layer C)"},
            {"name": "ranking", "description": "Scoring, ranking & explainability (Layer D)"},
            {"name": "export", "description": "Export results"},
        ],
    )

    app.include_router(discovery_router, prefix="/api/v1", dependencies=auth_dep)
    app.include_router(screening_router, prefix="/api/v1", dependencies=auth_dep)
    app.include_router(assessment_router, prefix="/api/v1", dependencies=auth_dep)
    app.include_router(ranking_router, prefix="/api/v1", dependencies=auth_dep)
    app.include_router(export_router, prefix="/api/v1", dependencies=auth_dep)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # HTTP middleware (request ID and timing)
    app.middleware("http")(timing_middleware)
    app.middleware("http")(request_id_middleware)
    app.middleware("http")(rate_limit_middleware)

    # Error handlers
    register_error_handlers(app)

    # Health and readiness endpoints
    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Liveness check — always returns OK."""
        return {"status": "ok"}

    @app.get("/ready", tags=["health"])
    async def ready() -> JSONResponse:
        """Readiness check — verifies app.state has settings."""
        if not hasattr(app.state, "settings") or app.state.settings is None:
            return JSONResponse(
                status_code=503,
                content={"status": "not ready"},
            )
        return JSONResponse(content={"status": "ready"})

    return app
