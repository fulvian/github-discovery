# GitHub Discovery — Phase 6 Implementation Plan

## Meta

- **Stato**: Draft v1
- **Data**: 2026-04-23
- **Riferimento roadmap**: `docs/roadmaps/github-discovery_foundation_roadmap.md` — Phase 6
- **Riferimento blueprint**: `docs/foundation/github-discovery_foundation_blueprint.md` — §8 (API), §17 (Operational Rules)
- **Riferimento wiki**: `docs/llm-wiki/wiki/` — articoli su tiered pipeline, MCP-native design, tech stack, operational rules
- **Durata stimata**: 2-3 settimane
- **Milestone**: M5 — API & Workers (FastAPI operativa, worker attivi, queue, hard gate in API)
- **Dipendenza**: Phase 0+1+2+3+4+5 completate (863 tests passing, `make ci` verde)
- **Context7 verification**: FastAPI 0.128+, uvicorn — middleware, CORS, lifespan, error handlers, dependency injection, BackgroundTasks, StreamingResponse, APIKeyHeader

---

## Indice

1. [Obiettivo](#1-obiettivo)
2. [Task Overview](#2-task-overview)
3. [Architettura generale](#3-architettura-generale)
4. [Nuove dipendenze](#4-nuove-dipendenze)
5. [Configurazione — APISettings](#5-configurazione--apisettings)
6. [Task 6.7 — Job Store & Task Queue](#6-task-67--job-store--task-queue)
7. [Task 6.1 — FastAPI Application Setup](#7-task-61--fastapi-application-setup)
8. [Task 6.6 — Scoring Workers](#8-task-66--scoring-workers)
9. [Task 6.2 — Discovery API Endpoints](#9-task-62--discovery-api-endpoints)
10. [Task 6.3 — Screening API Endpoints](#10-task-63--screening-api-endpoints)
11. [Task 6.4 — Assessment API Endpoints](#11-task-64--assessment-api-endpoints)
12. [Task 6.5 — Ranking & Query API Endpoints](#12-task-65--ranking--query-api-endpoints)
13. [Task 6.8 — Rate Limiting & Auth Middleware](#13-task-68--rate-limiting--auth-middleware)
14. [Task 6.9 — API Documentation](#14-task-69--api-documentation)
15. [Task 6.10 — Export Endpoints](#15-task-610--export-endpoints)
16. [Sequenza di implementazione — Waves](#16-sequenza-di-implementazione--waves)
17. [Test plan](#17-test-plan)
18. [Criteri di accettazione](#18-criteri-di-accettazione)
19. [Rischi e mitigazioni](#19-rischi-e-mitigazioni)
20. [Verifica Context7](#20-verifica-context7)

---

## 1) Obiettivo

Implementare la superficie API REST (FastAPI) e l'infrastruttura worker per esecuzione asincrona delle pipeline di scoring.

Al completamento della Phase 6:

- **FastAPI** operativa con middleware (CORS, request ID, timing), health/readiness endpoints, error handlers custom
- **5 route groups**: discovery, screening, assessment, ranking, export — tutti async
- **3 worker types**: MetadataWorker (Gate 1+2), AssessmentWorker (Gate 3), RankingWorker (post-scoring)
- **Job queue**: submit → track → complete, SQLite-backed per consistenza con PoolManager
- **Hard gate enforcement nell'API**: assessment route rifiuta candidate non passati Gate 1+2
- **Rate limiting + auth**: per IP/key, API key header opzionale
- **OpenAPI auto-documentata**: `/docs` accessibile e completa
- **Export**: JSON, CSV, Markdown

### Principio architetturale

**MCP-First (Blueprint §21.1)**: L'API REST è consumer secondario degli stessi servizi core. Ogni endpoint API invoca gli stessi orchestratori che i tool MCP useranno in Phase 7. Non duplicare logica di business nelle route.

---

## 2) Task Overview

| Task ID | Task | Output | Dipende da |
|---------|------|--------|------------|
| 6.1 | FastAPI application setup | `api/app.py`, `api/deps.py`, `api/errors.py` | — |
| 6.2 | Discovery API endpoints | `api/routes/discovery.py` | 6.1, 6.6, 6.7 |
| 6.3 | Screening API endpoints | `api/routes/screening.py` | 6.1, 6.6, 6.7 |
| 6.4 | Assessment API endpoints | `api/routes/assessment.py` | 6.1, 6.6, 6.7 |
| 6.5 | Ranking & query API endpoints | `api/routes/ranking.py` | 6.1, 6.6 |
| 6.6 | Scoring workers | `workers/base_worker.py`, 3 concrete workers, `worker_manager.py` | 6.7 |
| 6.7 | Task queue integration | `workers/types.py`, `workers/job_store.py`, `workers/queue.py` | — |
| 6.8 | Rate limiting & auth middleware | `api/middleware.py` | 6.1 |
| 6.9 | API documentation | OpenAPI customization | 6.2–6.5 |
| 6.10 | Export endpoints | `api/routes/export.py` | 6.1, 6.5 |

---

## 3) Architettura generale

### Struttura moduli

```
src/github_discovery/
├── api/
│   ├── __init__.py              # Exports: create_app
│   ├── app.py                   # FastAPI application factory + lifespan
│   ├── deps.py                  # Dependency injection providers
│   ├── middleware.py             # CORS, request ID, timing, rate limit, auth
│   ├── errors.py                # Exception → JSON response handlers
│   └── routes/
│       ├── __init__.py          # Router aggregation (include all route modules)
│       ├── discovery.py         # POST /api/v1/discover, GET /api/v1/discover/{job_id}, GET /api/v1/candidates
│       ├── screening.py         # POST /api/v1/screen, GET /api/v1/screen/{job_id}, GET /api/v1/shortlist
│       ├── assessment.py        # POST /api/v1/assess, GET /api/v1/assess/{job_id}
│       ├── ranking.py           # GET /api/v1/rank, GET /api/v1/rank/{repo}, GET /api/v1/explain/{repo}
│       └── export.py            # POST /api/v1/export
├── workers/
│   ├── __init__.py              # Exports
│   ├── types.py                 # JobStatus, Job, WorkerResult, JobType
│   ├── job_store.py             # SQLite-backed job persistence
│   ├── queue.py                 # AsyncTaskQueue (asyncio.Queue + JobStore)
│   ├── base_worker.py           # BaseWorker ABC
│   ├── discovery_worker.py      # Wraps DiscoveryOrchestrator
│   ├── screening_worker.py      # Wraps ScreeningOrchestrator
│   ├── assessment_worker.py     # Wraps AssessmentOrchestrator
│   └── worker_manager.py        # Worker lifecycle management
```

### Flusso request → response (job-based)

```
Client POST /api/v1/discover
    │
    ├── Route handler:
    │   1. Validate request (Pydantic model)
    │   2. Create Job (JobStore, status=pending)
    │   3. Enqueue (AsyncTaskQueue)
    │   4. Return 202 Accepted + job_id
    │
    └── Worker (background):
        1. Dequeue job
        2. Update status → running
        3. Deserialize input → call orchestrator
        4. Update status → completed/failed + result
```

```
Client GET /api/v1/discover/{job_id}
    │
    └── Route handler:
        1. Look up Job from JobStore
        2. Return status + result (if completed) / error (if failed)
```

### Flusso request → response (synchronous — ranking/explain)

```
Client GET /api/v1/rank?domain=library&max_results=20
    │
    └── Route handler:
        1. Validate params
        2. Call ScoringEngine + Ranker directly
        3. Return 200 + ranked results
```

### Lifespan management

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup:
    # 1. Initialize JobStore (SQLite)
    # 2. Initialize orchestrators (discovery, screening, assessment)
    # 3. Initialize ScoringEngine, Ranker
    # 4. Start WorkerManager (spawns worker tasks)
    # 5. Store all in app.state
    yield
    # Shutdown:
    # 1. Cancel worker tasks
    # 2. Close JobStore
    # 3. Close httpx clients (via orchestrators)
```

---

## 4) Nuove dipendenze

Da aggiungere a `pyproject.toml`:

| Package | Versione | Purpose |
|---------|----------|---------|
| `fastapi` | `>=0.115` | Web framework — async routes, DI, OpenAPI |
| `uvicorn[standard]` | `>=0.30` | ASGI server — run FastAPI |

**Non servono nuove dipendenze per**:
- Queue: `asyncio.Queue` (stdlib) + SQLite (via `aiosqlite`, già presente)
- Rate limiting: implementazione custom (token bucket in-memory)
- Auth: `fastapi.security.APIKeyHeader` (built-in)
- Job store: `aiosqlite` (già presente)
- Export JSON/CSV/Markdown: `json`, `csv`, `io` (stdlib)

---

## 5) Configurazione — APISettings

Nuova sezione in `config.py`:

```python
class APISettings(BaseSettings):
    """API server settings."""

    model_config = SettingsConfigDict(
        env_prefix="GHDISC_API_",
        env_file=".env",
    )

    host: str = Field(default="127.0.0.1", description="API server host")
    port: int = Field(default=8000, description="API server port")
    workers: int = Field(default=1, description="Number of worker tasks per type")
    rate_limit_per_minute: int = Field(default=60, description="Rate limit per IP per minute")
    api_key: str = Field(default="", description="API key for auth (empty = no auth)")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed CORS origins",
    )
    job_store_path: str = Field(
        default=".ghdisc/jobs.db",
        description="SQLite database path for job persistence",
    )
```

Aggiornare `Settings`:
```python
class Settings(BaseSettings):
    ...
    api: APISettings = Field(default_factory=APISettings)
```

---

## 6) Task 6.7 — Job Store & Task Queue

### workers/types.py

```python
from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class JobType(StrEnum):
    """Types of background jobs."""
    DISCOVERY = "discovery"
    SCREENING = "screening"
    ASSESSMENT = "assessment"
    RANKING = "ranking"


class JobStatus(StrEnum):
    """Job lifecycle states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(BaseModel):
    """Background job representation."""
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    job_type: JobType
    status: JobStatus = Field(default=JobStatus.PENDING)
    input_data: dict[str, object] = Field(default_factory=dict)
    result: dict[str, object] | None = Field(default=None)
    error_message: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)


class WorkerResult(BaseModel):
    """Result from a worker processing a job."""
    success: bool
    data: dict[str, object] = Field(default_factory=dict)
    error: str | None = None
```

### workers/job_store.py

SQLite-backed job persistence. Schema:

```sql
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    input_data TEXT NOT NULL DEFAULT '{}',  -- JSON
    result TEXT,                             -- JSON, nullable
    error_message TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_type ON jobs(job_type);
```

API pubblica:

```python
class JobStore:
    async def create(self, job: Job) -> Job: ...
    async def get(self, job_id: str) -> Job | None: ...
    async def update_status(self, job_id: str, status: JobStatus, **kwargs) -> Job | None: ...
    async def list_jobs(self, *, job_type: JobType | None = None, status: JobStatus | None = None, limit: int = 50) -> list[Job]: ...
    async def delete(self, job_id: str) -> bool: ...
    async def close(self) -> None: ...
```

- Usa `aiosqlite` (già in deps)
- Path configurabile via `APISettings.job_store_path`
- `input_data` e `result` serializzati come JSON text

### workers/queue.py

```python
class AsyncTaskQueue:
    """Async task queue backed by JobStore for persistence."""

    def __init__(self, job_store: JobStore) -> None:
        self._store = job_store
        self._queue: asyncio.Queue[str] = asyncio.Queue()  # job_ids

    async def enqueue(self, job: Job) -> Job: ...  # persist + put job_id
    async def dequeue(self, timeout: float = 1.0) -> Job | None: ...  # get job_id → load from store
    async def requeue_stale(self, max_age_seconds: int = 3600) -> int: ...  # recovery: requeue running jobs older than N seconds
    @property
    def size(self) -> int: ...
```

---

## 7) Task 6.1 — FastAPI Application Setup

### api/app.py

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from github_discovery.api.routes import discovery, screening, assessment, ranking, export


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory with optional settings override."""
    _settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        job_store = JobStore(_settings.api.job_store_path)
        await job_store.initialize()

        # Orchestrators
        rest_client = GitHubRestClient(_settings.github)
        graphql_client = GitHubGraphQLClient(_settings.github)
        pool_manager = PoolManager()
        discovery_orch = DiscoveryOrchestrator(_settings, pool_manager)
        gate1 = Gate1MetadataScreener()
        gate2 = Gate2StaticScreener(_settings)
        screening_orch = ScreeningOrchestrator(_settings, gate1, gate2)
        assessment_orch = AssessmentOrchestrator(_settings)
        scoring_engine = ScoringEngine()
        ranker = Ranker(_settings.scoring)

        # Queue + Workers
        queue = AsyncTaskQueue(job_store)
        worker_manager = WorkerManager(
            queue=queue,
            job_store=job_store,
            discovery_orch=discovery_orch,
            screening_orch=screening_orch,
            assessment_orch=assessment_orch,
            scoring_engine=scoring_engine,
            ranker=ranker,
            workers_per_type=_settings.api.workers,
        )
        await worker_manager.start()

        # Store in app.state
        app.state.settings = _settings
        app.state.job_store = job_store
        app.state.queue = queue
        app.state.worker_manager = worker_manager
        app.state.pool_manager = pool_manager
        app.state.discovery_orch = discovery_orch
        app.state.screening_orch = screening_orch
        app.state.assessment_orch = assessment_orch
        app.state.scoring_engine = scoring_engine
        app.state.ranker = ranker

        yield

        # Shutdown
        await worker_manager.stop()
        await job_store.close()
        await rest_client.close()
        await graphql_client.close()

    app = FastAPI(
        title="GitHub Discovery",
        description="MCP-native agentic discovery engine for high-quality GitHub repositories",
        version="0.1.0-alpha",
        lifespan=lifespan,
    )

    # Middleware (order matters — added in reverse execution order)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(timing_middleware)
    app.middleware("http")(request_id_middleware)

    # Error handlers
    register_error_handlers(app)

    # Routes
    app.include_router(discovery.router, prefix="/api/v1")
    app.include_router(screening.router, prefix="/api/v1")
    app.include_router(assessment.router, prefix="/api/v1")
    app.include_router(ranking.router, prefix="/api/v1")
    app.include_router(export.router, prefix="/api/v1")

    # Health
    @app.get("/health")
    async def health(): return {"status": "ok"}
    @app.get("/ready")
    async def ready(): return {"status": "ready"}

    return app
```

### api/deps.py

```python
from fastapi import Depends, Request, HTTPException, status
from github_discovery.config import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings

def get_job_store(request: Request) -> JobStore:
    return request.app.state.job_store

def get_queue(request: Request) -> AsyncTaskQueue:
    return request.app.state.queue

def get_discovery_orch(request: Request) -> DiscoveryOrchestrator:
    return request.app.state.discovery_orch

def get_screening_orch(request: Request) -> ScreeningOrchestrator:
    return request.app.state.screening_orch

def get_assessment_orch(request: Request) -> AssessmentOrchestrator:
    return request.app.state.assessment_orch

def get_scoring_engine(request: Request) -> ScoringEngine:
    return request.app.state.scoring_engine

def get_ranker(request: Request) -> Ranker:
    return request.app.state.ranker

def get_pool_manager(request: Request) -> PoolManager:
    return request.app.state.pool_manager
```

### api/middleware.py

```python
import time
import uuid
import structlog

logger = structlog.get_logger("github_discovery.api.middleware")


async def request_id_middleware(request: Request, call_next):
    """Add X-Request-ID header to every request."""
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


async def timing_middleware(request: Request, call_next):
    """Add X-Process-Time header to every response."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    response.headers["X-Process-Time"] = f"{elapsed:.4f}"
    return response
```

### api/errors.py

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from github_discovery.exceptions import (
    GitHubDiscoveryError,
    HardGateViolationError,
    BudgetExceededError,
)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(GitHubDiscoveryError)
    async def domain_error_handler(request: Request, exc: GitHubDiscoveryError):
        status_code = _map_exception_to_status(exc)
        return JSONResponse(
            status_code=status_code,
            content={"error": type(exc).__name__, "message": str(exc), "context": exc.context},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        logger.error("unhandled_exception", error=str(exc), request_url=str(request.url))
        return JSONResponse(
            status_code=500,
            content={"error": "InternalServerError", "message": "An unexpected error occurred"},
        )
```

---

## 8) Task 6.6 — Scoring Workers

### workers/base_worker.py

```python
class BaseWorker(ABC):
    """Abstract base worker for processing background jobs."""

    def __init__(self, job_store: JobStore) -> None:
        self._store = job_store

    @abstractmethod
    async def process(self, job: Job) -> WorkerResult:
        """Process a job and return the result."""
        ...

    async def execute(self, job: Job) -> None:
        """Execute job with status tracking."""
        await self._store.update_status(job.job_id, JobStatus.RUNNING, started_at=datetime.now(UTC))
        try:
            result = await self.process(job)
            if result.success:
                await self._store.update_status(
                    job.job_id, JobStatus.COMPLETED,
                    result=result.data, completed_at=datetime.now(UTC),
                )
            else:
                await self._store.update_status(
                    job.job_id, JobStatus.FAILED,
                    error_message=result.error, completed_at=datetime.now(UTC),
                )
        except Exception as e:
            await self._store.update_status(
                job.job_id, JobStatus.FAILED,
                error_message=str(e), completed_at=datetime.now(UTC),
            )
```

### workers/discovery_worker.py

```python
class DiscoveryWorker(BaseWorker):
    """Worker for discovery jobs — calls DiscoveryOrchestrator."""

    def __init__(self, job_store: JobStore, orchestrator: DiscoveryOrchestrator) -> None:
        super().__init__(job_store)
        self._orchestrator = orchestrator

    async def process(self, job: Job) -> WorkerResult:
        query = DiscoveryQuery.model_validate(job.input_data)
        result = await self._orchestrator.discover(query)
        return WorkerResult(success=True, data=result.model_dump())
```

### workers/screening_worker.py

```python
class ScreeningWorker(BaseWorker):
    """Worker for screening jobs — calls ScreeningOrchestrator."""

    def __init__(self, job_store: JobStore, orchestrator: ScreeningOrchestrator) -> None:
        super().__init__(job_store)
        self._orchestrator = orchestrator

    async def process(self, job: Job) -> WorkerResult:
        # Deserialize context from job input
        context = ScreeningContext.model_validate(job.input_data)
        results = await self._orchestrator.screen(context)
        return WorkerResult(success=True, data={
            "total_screened": len(results),
            "passed": sum(1 for r in results if r.can_proceed_to_gate3),
            "failed": sum(1 for r in results if not r.can_proceed_to_gate3),
            "results": [r.model_dump() for r in results],
        })
```

### workers/assessment_worker.py

```python
class AssessmentWorker(BaseWorker):
    """Worker for assessment jobs — calls AssessmentOrchestrator.

    Hard gate enforcement: rejects jobs where candidates haven't passed Gate 1+2.
    """

    def __init__(self, job_store: JobStore, orchestrator: AssessmentOrchestrator) -> None:
        super().__init__(job_store)
        self._orchestrator = orchestrator

    async def process(self, job: Job) -> WorkerResult:
        context = AssessmentContext.model_validate(job.input_data)
        results = await self._orchestrator.assess(context)
        return WorkerResult(success=True, data={
            "total_assessed": len(results),
            "gate3_passed": sum(1 for r in results if r.gate3_pass),
            "from_cache": sum(1 for r in results if r.cached),
            "results": [r.model_dump() for r in results],
        })
```

### workers/worker_manager.py

```python
class WorkerManager:
    """Manages lifecycle of background worker tasks."""

    def __init__(
        self,
        queue: AsyncTaskQueue,
        job_store: JobStore,
        discovery_orch: DiscoveryOrchestrator,
        screening_orch: ScreeningOrchestrator,
        assessment_orch: AssessmentOrchestrator,
        scoring_engine: ScoringEngine,
        ranker: Ranker,
        workers_per_type: int = 1,
    ) -> None: ...

    async def start(self) -> None:
        """Start worker tasks."""
        # Requeue stale jobs from previous sessions
        await self._queue.requeue_stale()
        # Spawn worker tasks
        for i in range(self._workers_per_type):
            self._tasks.append(asyncio.create_task(self._worker_loop(f"discovery-{i}"), name=f"worker-discovery-{i}"))
            self._tasks.append(asyncio.create_task(self._worker_loop(f"screening-{i}"), name=f"worker-screening-{i}"))
            self._tasks.append(asyncio.create_task(self._worker_loop(f"assessment-{i}"), name=f"worker-assessment-{i}"))

    async def stop(self) -> None:
        """Cancel all worker tasks gracefully."""
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _worker_loop(self, worker_name: str) -> None:
        """Main worker loop: dequeue → get worker → execute."""
        while True:
            job = await self._queue.dequeue(timeout=1.0)
            if job is None:
                continue
            worker = self._get_worker_for_type(job.job_type)
            if worker:
                await worker.execute(job)

    @property
    def active_workers(self) -> int: ...
    @property
    def is_running(self) -> bool: ...
```

---

## 9) Task 6.2 — Discovery API Endpoints

### api/routes/discovery.py

```python
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(tags=["discovery"])


@router.post("/discover", response_model=DiscoveryResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_discovery(
    request: DiscoveryQuery,
    queue: AsyncTaskQueue = Depends(get_queue),
    job_store: JobStore = Depends(get_job_store),
):
    """Start a discovery job. Returns job_id for polling."""
    job = Job(job_type=JobType.DISCOVERY, input_data=request.model_dump())
    job = await job_store.create(job)
    await queue.enqueue(job)
    return DiscoveryResponse(job_id=job.job_id, status=job.status, session_id=request.session_id)


@router.get("/discover/{job_id}", response_model=DiscoveryResponse)
async def get_discovery_status(
    job_id: str,
    job_store: JobStore = Depends(get_job_store),
):
    """Get status of a discovery job."""
    job = await job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    response = DiscoveryResponse(job_id=job.job_id, status=job.status)
    if job.status == JobStatus.COMPLETED and job.result:
        response.total_candidates = job.result.get("total_count", 0)
        response.pool_id = job.result.get("pool_id")
        response.channels_used = job.result.get("channels_used", [])
    elif job.status == JobStatus.FAILED:
        response.status = "failed"
    return response


@router.get("/candidates")
async def list_candidates(
    pool_id: str | None = None,
    pagination: PaginationParams = Depends(),
    pool_manager: PoolManager = Depends(get_pool_manager),
):
    """List candidates in a pool."""
    if not pool_id:
        raise HTTPException(status_code=400, detail="pool_id is required")
    candidates = await pool_manager.get_pool(pool_id)
    if not candidates:
        raise HTTPException(status_code=404, detail=f"Pool {pool_id} not found")
    # Apply pagination
    start = (pagination.page - 1) * pagination.page_size
    end = start + pagination.page_size
    page = candidates[start:end]
    return PaginatedResponse(
        total_count=len(candidates),
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=(len(candidates) + pagination.page_size - 1) // pagination.page_size,
        has_next=end < len(candidates),
        has_prev=pagination.page > 1,
    )
```

---

## 10) Task 6.3 — Screening API Endpoints

### api/routes/screening.py

```python
router = APIRouter(tags=["screening"])


@router.post("/screen", response_model=ScreeningResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_screening(
    request: ScreeningRequest,
    queue: AsyncTaskQueue = Depends(get_queue),
    job_store: JobStore = Depends(get_job_store),
):
    """Start a screening job on a candidate pool."""
    job = Job(job_type=JobType.SCREENING, input_data=request.model_dump())
    job = await job_store.create(job)
    await queue.enqueue(job)
    return ScreeningResponse(job_id=job.job_id, status=job.status, pool_id=request.pool_id)


@router.get("/screen/{job_id}", response_model=ScreeningResponse)
async def get_screening_status(job_id: str, job_store: JobStore = Depends(get_job_store)):
    """Get status of a screening job."""
    job = await job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    response = ScreeningResponse(job_id=job.job_id, status=job.status, pool_id="", gate_level=GateLevel.METADATA)
    if job.status == JobStatus.COMPLETED and job.result:
        response.total_screened = job.result.get("total_screened", 0)
        response.passed = job.result.get("passed", 0)
        response.failed = job.result.get("failed", 0)
    return response


@router.get("/shortlist")
async def get_shortlist(
    pool_id: str,
    min_score: float = 0.5,
    domain: DomainType | None = None,
    limit: int = 50,
    job_store: JobStore = Depends(get_job_store),
):
    """Get shortlisted candidates (Gate 1+2 pass) from a pool."""
    # Query completed screening jobs for this pool, filter results
    ...
```

---

## 11) Task 6.4 — Assessment API Endpoints

### api/routes/assessment.py

```python
router = APIRouter(tags=["assessment"])


@router.post("/assess", response_model=AssessmentResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_assessment(
    request: AssessmentRequest,
    queue: AsyncTaskQueue = Depends(get_queue),
    job_store: JobStore = Depends(get_job_store),
    pool_manager: PoolManager = Depends(get_pool_manager),
):
    """Start a deep assessment job.

    Hard gate enforcement (Blueprint §16.5): Only repos that passed
    Gate 1+2 can be assessed. Returns 422 if any repo hasn't passed.
    """
    # Validate hard gate: check that candidates have Gate 1+2 pass
    # This requires looking up screening results from the pool
    # If screening not done, return 422 with appropriate message
    ...


@router.get("/assess/{job_id}", response_model=AssessmentResponse)
async def get_assessment_status(job_id: str, job_store: JobStore = Depends(get_job_store)):
    """Get status of an assessment job."""
    job = await job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    response = AssessmentResponse(job_id=job.job_id, status=job.status)
    if job.status == JobStatus.COMPLETED and job.result:
        response.total_repos = job.result.get("total_assessed", 0)
        response.assessed = job.result.get("gate3_passed", 0)
        response.tokens_used = job.result.get("tokens_used", 0)
    return response
```

---

## 12) Task 6.5 — Ranking & Query API Endpoints

### api/routes/ranking.py

I ranking endpoint sono **sincroni** (non job-based) — chiamano ScoringEngine + Ranker direttamente.

```python
router = APIRouter(tags=["ranking"])


@router.get("/rank", response_model=RankingResponse)
async def get_ranking(
    query: RankingQuery = Depends(),
    scoring_engine: ScoringEngine = Depends(get_scoring_engine),
    ranker: Ranker = Depends(get_ranker),
    job_store: JobStore = Depends(get_job_store),
):
    """Get ranked results. Synchronous — computes on-demand from stored scores."""
    # 1. Load scored repos from completed assessment + scoring jobs
    # 2. Call ranker.rank() with filters
    # 3. Return paginated results
    ...


@router.get("/rank/{repo:path}")
async def get_repo_detail(
    repo: str,
    job_store: JobStore = Depends(get_job_store),
):
    """Get detailed scoring for a single repository."""
    ...


@router.get("/explain/{repo:path}")
async def explain_repo(
    repo: str,
    detail_level: str = "summary",
    scoring_engine: ScoringEngine = Depends(get_scoring_engine),
):
    """Generate explainability report for a repository."""
    ...
```

**Nota**: `repo:path` usa Starlette path converter per catturare `owner/repo` come singolo path segment.

---

## 13) Task 6.8 — Rate Limiting & Auth Middleware

### api/middleware.py (estensione)

```python
import time
from collections import defaultdict


class RateLimiter:
    """Token bucket rate limiter per IP."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        # Clean old entries
        self._requests[key] = [t for t in self._requests[key] if now - t < self._window]
        if len(self._requests[key]) >= self._max:
            return False
        self._requests[key].append(now)
        return True


async def rate_limit_middleware(request: Request, call_next):
    """Rate limit middleware — applied when rate limiting is configured."""
    settings = request.app.state.settings
    if not settings.api.rate_limit_per_minute:
        return await call_next(request)

    limiter = request.app.state.rate_limiter
    client_ip = request.client.host if request.client else "unknown"

    if not limiter.is_allowed(client_ip):
        return JSONResponse(
            status_code=429,
            content={"error": "RateLimitExceeded", "message": "Too many requests"},
        )
    return await call_next(request)
```

### Auth (API Key Header)

```python
from fastapi.security import APIKeyHeader

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    request: Request,
    api_key: str | None = Depends(_api_key_header),
):
    """Verify API key if configured. Skip auth if no key configured."""
    settings = request.app.state.settings
    if not settings.api.api_key:
        return  # Auth disabled

    if api_key != settings.api.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
```

Applicata come dipendenza opzionale sui route che richiedono autenticazione.

---

## 14) Task 6.9 — API Documentation

FastAPI auto-genera OpenAPI spec. Customizzazione:

```python
app = FastAPI(
    title="GitHub Discovery API",
    description="""...""",  # Markdown description of the system
    version="0.1.0-alpha",
    contact={"name": "GitHub Discovery", "url": "https://github.com/..."},
    license_info={"name": "MIT"},
    servers=[
        {"url": "http://localhost:8000", "description": "Local development"},
    ],
    openapi_tags=[
        {"name": "discovery", "description": "Candidate discovery (Layer A)"},
        {"name": "screening", "description": "Quality screening (Layer B)"},
        {"name": "assessment", "description": "Deep technical assessment (Layer C)"},
        {"name": "ranking", "description": "Scoring, ranking & explainability (Layer D)"},
        {"name": "export", "description": "Export results"},
    ],
)
```

Ogni route ha `summary`, `description`, `response_model` definiti. I Pydantic models in `models/api.py` forniscono automaticamente schema e validation.

**Verifica**: `/docs` (Swagger UI) accessibile e navigabile. `/redoc` (ReDoc) accessibile. `/openapi.json` scaricabile.

---

## 15) Task 6.10 — Export Endpoints

### api/routes/export.py

```python
router = APIRouter(tags=["export"])


@router.post("/export")
async def export_results(
    request: ExportRequest,
    job_store: JobStore = Depends(get_job_store),
    ranker: Ranker = Depends(get_ranker),
):
    """Export session results in JSON, CSV, or Markdown format.

    For small exports, content is returned inline.
    For large exports, returns a download URL.
    """
    # 1. Load completed ranking results for session
    # 2. Apply domain filter if specified
    # 3. Format based on ExportFormat
    # 4. Return ExportResponse with content or download_url
    ...


def _format_csv(results: list[dict]) -> str:
    """Format results as CSV."""
    ...


def _format_markdown(results: list[dict]) -> str:
    """Format results as Markdown table."""
    ...
```

---

## 16) Sequenza di implementazione — Waves

### Wave A — Foundation (Tasks 6.1 + 6.7)

**Obiettivo**: Infrastrutura base — app, middleware, error handlers, job store, queue.

**File da creare**:
1. `src/github_discovery/workers/types.py` — JobType, JobStatus, Job, WorkerResult
2. `src/github_discovery/workers/job_store.py` — JobStore (SQLite)
3. `src/github_discovery/workers/queue.py` — AsyncTaskQueue
4. `src/github_discovery/api/errors.py` — Error handlers
5. `src/github_discovery/api/middleware.py` — Request ID, timing middleware
6. `src/github_discovery/api/deps.py` — Dependency injection providers
7. `src/github_discovery/api/app.py` — Application factory + lifespan + health
8. `src/github_discovery/api/routes/__init__.py` — Empty router aggregation
9. `src/github_discovery/config.py` — Add APISettings

**Test**: ~25 test
- `tests/unit/workers/test_types.py` — Job creation, serialization, status transitions
- `tests/unit/workers/test_job_store.py` — CRUD, status updates, listing
- `tests/unit/workers/test_queue.py` — Enqueue, dequeue, requeue stale
- `tests/unit/api/test_app.py` — Health, readiness, middleware headers
- `tests/unit/api/test_errors.py` — Error handler responses

**Verifica**: `GET /health` ritorna 200, job store CRUD funzionante, queue enqueue/dequeue OK.

### Wave B — Workers (Task 6.6)

**Obiettivo**: 3 worker types + worker manager.

**File da creare**:
1. `src/github_discovery/workers/base_worker.py` — BaseWorker ABC
2. `src/github_discovery/workers/discovery_worker.py` — DiscoveryWorker
3. `src/github_discovery/workers/screening_worker.py` — ScreeningWorker
4. `src/github_discovery/workers/assessment_worker.py` — AssessmentWorker
5. `src/github_discovery/workers/worker_manager.py` — WorkerManager

**Test**: ~30 test
- `tests/unit/workers/test_base_worker.py` — Status tracking, error handling
- `tests/unit/workers/test_discovery_worker.py` — Discovery job processing
- `tests/unit/workers/test_screening_worker.py` — Screening job processing
- `tests/unit/workers/test_assessment_worker.py` — Assessment job processing + hard gate
- `tests/unit/workers/test_worker_manager.py` — Start, stop, worker loop

**Verifica**: Worker processa job end-to-end, status transitions corretti.

### Wave C — API Routes (Tasks 6.2 + 6.3 + 6.4 + 6.5)

**Obiettivo**: Tutti i route endpoint operativi.

**File da creare**:
1. `src/github_discovery/api/routes/discovery.py`
2. `src/github_discovery/api/routes/screening.py`
3. `src/github_discovery/api/routes/assessment.py`
4. `src/github_discovery/api/routes/ranking.py`
5. Aggiornare `src/github_discovery/api/routes/__init__.py`

**Test**: ~35 test
- `tests/unit/api/routes/test_discovery.py` — POST discover, GET status, GET candidates
- `tests/unit/api/routes/test_screening.py` — POST screen, GET status, GET shortlist
- `tests/unit/api/routes/test_assessment.py` — POST assess (hard gate), GET status
- `tests/unit/api/routes/test_ranking.py` — GET rank, GET repo detail, GET explain

**Verifica**: E2E: POST → job_id → polling → risultati. Hard gate enforcement nell'API.

### Wave D — Final Integration (Tasks 6.8 + 6.9 + 6.10)

**Obiettivo**: Rate limiting, auth, export, documentazione, integrazione finale.

**File da creare/aggiornare**:
1. `src/github_discovery/api/middleware.py` — Aggiungere rate_limit_middleware, verify_api_key
2. `src/github_discovery/api/routes/export.py`
3. `src/github_discovery/api/app.py` — Aggiungere OpenAPI tags, rate limiter, auth

**Test**: ~20 test
- `tests/unit/api/test_middleware.py` — Rate limiting, auth
- `tests/unit/api/routes/test_export.py` — Export JSON/CSV/Markdown
- `tests/integration/test_api_e2e.py` — Full pipeline: discover → screen → assess → rank → export

**Verifica**: Rate limit rispettato, auth funzionante, export JSON/CSV/MD, `/docs` accessibile, `make ci` verde.

---

## 17) Test plan

### Test files structure

```
tests/
├── unit/
│   ├── api/
│   │   ├── conftest.py           # TestClient fixture, mock orchestrators
│   │   ├── test_app.py           # Health, readiness, lifespan
│   │   ├── test_errors.py        # Error handlers
│   │   ├── test_middleware.py     # Request ID, timing, rate limit, auth
│   │   └── routes/
│   │       ├── test_discovery.py
│   │       ├── test_screening.py
│   │       ├── test_assessment.py
│   │       ├── test_ranking.py
│   │       └── test_export.py
│   └── workers/
│       ├── conftest.py           # Mock job store, queue
│       ├── test_types.py
│       ├── test_job_store.py
│       ├── test_queue.py
│       ├── test_base_worker.py
│       ├── test_discovery_worker.py
│       ├── test_screening_worker.py
│       ├── test_assessment_worker.py
│       └── test_worker_manager.py
└── integration/
    └── test_api_e2e.py           # Full pipeline via API
```

### Test approach

| Layer | Tool | Pattern |
|-------|------|---------|
| API routes | `httpx.AsyncClient` + `fastapi.testclient.TestClient` | Mock orchestratori via deps override |
| Workers | `pytest-asyncio` | Mock queue + job store, verify orchestrator calls |
| Job store | In-memory SQLite (`:memory:`) | Direct CRUD testing |
| Middleware | `TestClient` | Verify headers, rate limit, auth |
| Integration | `TestClient` | Full pipeline with mock orchestratori |
| Error handlers | `TestClient` + mock routes raising exceptions | Verify JSON error format |

### Key test scenarios

1. **Discovery E2E**: POST /discover → 202 → GET /discover/{id} → pending → worker processes → GET → completed
2. **Hard gate in API**: POST /assess with repo not passed Gate 1+2 → 422
3. **Rate limiting**: 61 rapid requests → 429 on 61st
4. **Auth**: Request without API key → 401 (when key configured)
5. **Job recovery**: Stale running job → requeued on startup
6. **Export formats**: JSON, CSV, Markdown output correctness
7. **Pagination**: Large result set → correct page/offset
8. **Concurrent workers**: Multiple jobs processed concurrently

### Coverage target

>80% su api/ e workers/, coerente con il target del progetto.

---

## 18) Criteri di accettazione

| Criterio | Misura | Target |
|----------|--------|--------|
| **FastAPI operativa** | `GET /health` ritorna 200 | ✅ |
| **Discovery endpoint** | POST /discover → 202, GET status → job state | ✅ |
| **Screening endpoint** | POST /screen → 202, GET shortlist → filtered | ✅ |
| **Assessment hard gate** | POST /assess senza Gate 1+2 → 422 | ✅ |
| **Ranking sync** | GET /rank → ranked results | ✅ |
| **Explainability** | GET /explain/{repo} → report | ✅ |
| **Worker processing** | Job: pending → running → completed | ✅ |
| **Job persistence** | JobStore CRUD + recovery stale jobs | ✅ |
| **Rate limiting** | 61 req/min → 429 on excess | ✅ |
| **Auth** | API key check when configured | ✅ |
| **Export** | JSON + CSV + Markdown | ✅ |
| **OpenAPI docs** | `/docs` accessibile e completa | ✅ |
| **make ci verde** | ruff + mypy --strict + pytest | ✅ |
| **Test count** | ~110 nuovi test | ✅ |
| **Type safety** | mypy --strict 0 errori | ✅ |

---

## 19) Rischi e mitigazioni

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| **Worker deadlock su run lunghe** | Medio — pipeline non completa | Timeout per job, WorkerManager health check, cancellation |
| **Job store SQLite contention** | Basso — single-writer bottleneck | Write-through singleton, WAL mode, evolvibile a Redis |
| **Memory leak in long-running API** | Medio — degrado performance | Lifespan cleanup, httpx client close, periodic gc |
| **Orchestrator constructor changes** | Basso — API breaks | deps.py centralizza costruzione, test di integrazione |
| **PoolManager/JobStore path conflict** | Basso — data corruption | Paths separati (.ghdisc/pools.db vs .ghdisc/jobs.db) |
| **Hard gate enforcement gap** | Alto — LLM cost overflow | Double enforcement: API route + worker |
| **Rate limiter in distributed setup** | Basso — single-instance only | In-memory per ora, Redis-backed in futuro |

---

## 20) Verifica Context7

| Libreria | Library ID | Pattern verificati |
|----------|-----------|-------------------|
| FastAPI | `/fastapi/fastapi` | CORS middleware, request timing middleware, lifespan context manager, `@app.middleware("http")`, `app.add_middleware()`, `BaseHTTPMiddleware` |
| FastAPI docs | `/websites/fastapi_tiangolo` | BackgroundTasks, StreamingResponse/EventSourceResponse, APIKeyHeader/APIKeyCookie security, dependency injection |
| uvicorn | `/kludex/uvicorn` | ASGI server setup |

### FastAPI patterns verified

1. **Lifespan**: `@asynccontextmanager` con yield — startup/shutdown logic
2. **CORS**: `CORSMiddleware` con `allow_origins`, `allow_credentials`, `allow_methods`, `allow_headers`
3. **Request timing**: `@app.middleware("http")` con `call_next` + `time.perf_counter()`
4. **Error handlers**: `@app.exception_handler(ExceptionClass)` → `JSONResponse`
5. **Dependency injection**: `Depends()` per Settings, orchestrators, job store
6. **API Key auth**: `fastapi.security.APIKeyHeader` con `auto_error=False`
7. **Background tasks**: `BackgroundTasks.add_task()` per operazioni post-response
8. **OpenAPI**: Auto-generato da FastAPI con Pydantic models

---

*Stato documento: Draft v1 — Phase 6 Implementation Plan*
*Autore: General Manager (orchestrator)*
*Approvazione richiesta: Milestone M5 (HitL)*
