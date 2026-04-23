---
Title: Phase 6 API & Worker Implementation Plan
Topic: patterns
Sources: Roadmap Phase 6; Blueprint §8 (API), §17 (Operational Rules), §21.1 (MCP-First); Context7 verification of FastAPI, uvicorn
Raw: [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md); [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [phase6-plan.md](../../../plans/phase6-implementation-plan.md)
Updated: 2026-04-23
Confidence: high
---

# Phase 6 API & Worker Implementation Plan

Phase 6 implements the REST API surface (FastAPI) and async worker infrastructure for executing the scoring pipeline as background jobs.

**Status: COMPLETE** — All 4 waves implemented, 127 new tests (990 total), `make ci` green. Context7 verified FastAPI + uvicorn patterns.

## Key Architecture Decisions

### Application Factory Pattern

- `create_app(settings)` returns configured FastAPI instance
- Lifespan context manager handles startup (initialize orchestrators, job store, workers) and shutdown (cancel workers, close connections)
- All service instances stored in `app.state` for dependency injection via `Depends()`

### Job-Based Async Pattern

- Long-running operations (discovery, screening, assessment) use job queue:
  - `POST /api/v1/discover` → creates Job → enqueues → returns 202 + job_id
  - `GET /api/v1/discover/{job_id}` → polls job status
  - Worker dequeues → updates status → executes orchestrator → stores result
- Synchronous operations (ranking, explain) call orchestrators directly

### SQLite JobStore

- Consistent with existing PoolManager pattern (aiosqlite)
- Jobs table: job_id, type, status, input_json, result_json, error_message, timestamps
- Recovery: stale running jobs requeued on startup
- Evolvable to Redis for distributed deployment

### 3 Worker Types

- DiscoveryWorker: wraps DiscoveryOrchestrator
- ScreeningWorker: wraps ScreeningOrchestrator
- AssessmentWorker: wraps AssessmentOrchestrator (with hard gate check)
- WorkerManager: asyncio task lifecycle, graceful cancellation

### MCP-First Compliance

- API routes do NOT contain business logic — they delegate to the same orchestrators that MCP tools will use in Phase 7
- No duplication of scoring/ranking logic in routes

### Rate Limiting & Auth

- In-memory token bucket rate limiter (per IP, configurable req/min)
- API key header auth (optional, disabled by default for local dev)
- Both configurable via GHDISC_API_* env vars

## New Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | >=0.115 | Web framework, async routes, DI, OpenAPI |
| uvicorn[standard] | >=0.30 | ASGI server |

## New Configuration (APISettings)

| Setting | Env Var | Default |
|---------|---------|---------|
| host | GHDISC_API_HOST | 127.0.0.1 |
| port | GHDISC_API_PORT | 8000 |
| workers | GHDISC_API_WORKERS | 1 |
| rate_limit_per_minute | GHDISC_API_RATE_LIMIT_PER_MINUTE | 60 |
| api_key | GHDISC_API_KEY | "" (disabled) |
| cors_origins | GHDISC_API_CORS_ORIGINS | ["*"] |
| job_store_path | GHDISC_API_JOB_STORE_PATH | .ghdisc/jobs.db |

## Module Structure

```
api/
├── app.py, deps.py, middleware.py, errors.py
└── routes/ (discovery, screening, assessment, ranking, export)
workers/
├── types.py, job_store.py, queue.py
├── base_worker.py, discovery_worker.py, screening_worker.py, assessment_worker.py
└── worker_manager.py
```

## Implementation Waves

1. **Wave A**: Foundation — app, middleware, errors, job store, queue (~25 tests)
2. **Wave B**: Workers — 3 workers + manager (~30 tests)
3. **Wave C**: Routes — 4 route groups (~35 tests)
4. **Wave D**: Integration — rate limit, auth, export, docs (~20 tests)

## See Also

- [Tiered Pipeline](../architecture/tiered-pipeline.md)
- [MCP-Native Design](../architecture/mcp-native-design.md)
- [Tech Stack](tech-stack.md)
- [Phase 5 Implementation](phase5-scoring-implementation.md)
