# GitHub Discovery — Progress Log

## Session: 2025-04-22

### 11:06 — Inizializzazione
- Creata struttura directory (docs/foundation, .workflow)
- Inizializzato repository git
- Creati file di planning
- Avviate ricerche parallele

## Session: 2026-04-22

### 11:28 — Ripresa e completamento
- Ripreso contesto dai file di planning
- Consolidata ricerca su strumenti esistenti, API GitHub, metriche qualitative, MCP
- Identificato benchmark principale: `chriscarrollsmith/github_repo_classifier`
- Redatto documento fondativo completo:
  - `docs/foundation/github-discovery_foundation_blueprint.md`
- Revisione incrementale completata con focus:
  - pre-screening low/zero LLM cost
  - approfondimento architettura Option C ibrida
  - adozione GitHub MCP ufficiale come servizio interno
  - workflow agentico CLI-first (OpenCode CLI, Kilo CLI, Claude Code)
- Aggiornati file di supporto:
  - `findings.md`
  - `task_plan.md`
  - `.workflow/state.md`

### Note operative
- Alcuni provider di ricerca hanno restituito limiti piano/rate limit (Tavily, Brave in burst, Firecrawl credits).
- Ricerca proseguita con fonti alternative e conferme multi-sorgente.

## Session: 2026-04-22 (Phase 0 Implementation)

### 13:00 — Phase 0 Scaffolding Complete
- Implemented all 11 tasks from `docs/plans/phase0-implementation-plan.md`
- Context7 verification completed for: Pydantic v2, pydantic-settings, MCP Python SDK, structlog, ruff, pytest
- Key implementation decisions:
  - StrEnum (Python 3.12+) used for all enumerations
  - `datetime.UTC` used instead of `timezone.utc`
  - Domain exception __init__ methods include docstrings for D107
  - `from __future__ import annotations` enforced in all files
  - structlog.get_logger() typed explicitly for mypy strict
- All acceptance criteria verified:
  - `pip install -e ".[dev]"` ✓
  - `python -c "import github_discovery"` ✓ (version 0.1.0-alpha)
  - `make ci` passes (ruff + mypy --strict + 46 tests) ✓
  - Settings, logging, exceptions, session models, MCP specs all work ✓
  - `.kilo/mcp.json` and template are valid JSON ✓

### Files Created/Modified
- `pyproject.toml` — Build config, dependencies, tooling config
- `src/github_discovery/` — Full package structure (config, exceptions, logging, models, cli, mcp, etc.)
- `tests/` — Unit tests (config, exceptions, logging, enums, session, mcp_spec) + integration tests
- `Makefile` — Dev commands (install, test, lint, format, typecheck, ci, clean)
- `.pre-commit-config.yaml` — Pre-commit hooks (ruff, mypy, base hooks)
- `.github/workflows/ci.yml` — CI pipeline (lint+typecheck, test on Python 3.12/3.13)
- `.kilo/mcp.json` + `.kilo/mcp.json.template` — Kilocode CLI MCP config
- `CLAUDE.md` — Claude Code agent instructions

## Session: 2026-04-22 (Phase 1 Planning)

### 14:00 — Phase 1 Implementation Plan Drafted
- Created `docs/plans/phase1-implementation-plan.md`
- Followed AGENTS.md session start protocol: wiki → relevant articles → Context7 → plan
- Context7 verification: Pydantic v2 computed_field, model_validator, JSON schema generation
- Key decisions:
  - ScoreDimension alignment: COMMUNITY → FUNCTIONALITY, NOVELTY → INNOVATION
  - SubScore base pattern for 11 gate sub-scores
  - ValueScore as computed_field (quality_score / log10(stars + 10))
  - Feature Store with SHA dedup + TTL
  - MCPToolResult for context-efficient MCP output
- Wiki updated:
  - Created wiki/patterns/phase1-models-implementation.md
  - Updated wiki/index.md with new article
  - Updated wiki/log.md with ingest entry
  - Cross-referenced from phase0-implementation.md

## Session: 2026-04-22 (Phase 1 Implementation)

### 15:30 — Phase 1 Data Models Complete
- Implemented all 9 tasks from `docs/plans/phase1-implementation-plan.md`
- All model files written and tested:
  - `models/enums.py` — ScoreDimension (FUNCTIONALITY, INNOVATION) + CandidateStatus (new)
  - `models/candidate.py` — RepoCandidate, CandidatePool
  - `models/screening.py` — SubScore, 7 Gate1 sub-scores, MetadataScreenResult, 4 Gate2 sub-scores, StaticScreenResult, ScreeningResult
  - `models/assessment.py` — DimensionScore, TokenUsage, DeepAssessmentResult
  - `models/scoring.py` — DomainProfile, ScoreResult (value_score computed_field), RankedRepo, ExplainabilityReport, 4 predefined profiles
  - `models/features.py` — FeatureStoreKey, RepoFeatures
  - `models/api.py` — All request/response models + pagination + export
  - `models/agent.py` — MCPToolResult, DiscoverySession
  - `models/__init__.py` — All Phase 1 exports
- Test files: 113 new unit tests across 8 test files (140 total with Phase 0)
- `make ci` green: ruff + mypy --strict + pytest

### Issues Resolved During Implementation
- `@computed_field` + `@property` mypy prop-decorator → `# type: ignore[prop-decorator]`
- `TestFootprintScore` collected by pytest → aliased as `FootprintScore` in test
- `model_copy(update=...)` bypasses validation → `model_validate(merged_dict)` in test helper
- SubScore weight `le=1.0` → fixed test from 2.0 to 0.5
- Ruff TC001 for Pydantic runtime imports → `# noqa: TC001`
- Ruff PLR2004 magic values → extracted constants `_ACTIVE_THRESHOLD_DAYS`, `_WEIGHT_TOLERANCE`
- Ruff E501 long descriptions → wrapped multi-line strings
- Ruff RUF022 unsorted `__all__` → auto-fixed
- Ruff B017 blind exceptions → `# noqa: B017`
- Makefile bare commands → `$(PYTHON) -m` with venv python

## Session: 2026-04-22 (Phase 2 Planning)

### 18:00 — Phase 2 Discovery Engine Implementation Plan Created
- Created `docs/plans/phase2-implementation-plan.md`
- Followed AGENTS.md session start protocol: wiki → relevant articles → Context7 → plan
- Context7 verification completed for:
  - httpx AsyncClient, AsyncHTTPTransport(retries), Auth subclass, event hooks
  - pytest-httpx HTTPXMock fixture, add_response, custom headers, reusable responses
  - GitHub REST API: /search/repositories, /search/code, /rate_limit, conditional requests (ETag)
  - GitHub GraphQL: cursor-based pagination (first/after, pageInfo), rateLimit cost
  - GitHub dependency-graph/sbom API
- Plan covers 10 tasks (2.1-2.10) with:
  - Detailed design per module with code signatures
  - ~79 unit tests planned across 10 test files
  - New dependency: aiosqlite>=0.20 for SQLite pool persistence
  - Implementation sequence in 4 phases (A→B→C→D) over 2-3 weeks
  - Risk assessment with mitigations
- Wiki updated:
  - Updated wiki/index.md with plan reference
  - Updated wiki/log.md with ingest entry
  - Updated task_plan.md with Phase 2 task breakdown

## Session: 2026-04-22 (Phase 2 Implementation)

### 20:00 — Phase 2 Discovery Engine Complete
- All 10 tasks (2.1–2.10) implemented and verified
- 320 tests passing (149 new + 171 pre-existing), `make ci` green
- 45 source files pass mypy --strict, 77 files pass ruff check/format

### Modules Created
- **Infrastructure**: `github_client.py`, `graphql_client.py`, `pool.py`, `types.py`
- **Channels**: `search_channel.py`, `curated_channel.py`, `code_search_channel.py`, `registry_channel.py`, `dependency_channel.py`, `seed_expansion.py`
- **Integration**: `orchestrator.py`, `__init__.py` (exports)

### Key Decisions
- `_BearerAuth(httpx.Auth)` uses `Generator[Request, Response, None]` not `Iterator` for httpx compatibility
- HTTP status codes as named constants (`_HTTP_FORBIDDEN`, `_HTTP_NOT_MODIFIED`)
- `contextlib.suppress` replaces try/except/pass blocks
- Pydantic models need runtime imports (`# noqa: TC001`, not TYPE_CHECKING)
- `CandidatePool.total_count` is `@property`, not constructor param
- `DiscoveryChannel.AWESOME_LIST` (not CURATED) for curated channel
- Discovery scoring: base + breadth bonus + channel quality bonuses, capped at 1.0
- `SeedExpansion.expand()` takes `seed_urls` not `DiscoveryQuery` — orchestrator special-cases it
- `DependencyChannel.discover_dependents()` returns empty (no public GitHub API for dependents)

### Files Modified
- `pyproject.toml` — Added aiosqlite>=0.20, pytest-httpx>=0.30
- `src/github_discovery/discovery/` — 12 new modules
- `tests/unit/discovery/` — 10 new test files + updated conftest.py
- `docs/llm-wiki/wiki/` — Updated phase2-discovery-plan.md, index.md, log.md

## Session: 2026-04-23 (Phase 3 Implementation)

### 00:00 — Phase 3 Lightweight Quality Screening Complete
- Implemented all 14 tasks from `docs/plans/phase3-implementation-plan.md`
- 459 tests passing (139 new screening tests + 320 pre-existing), `make ci` green
- 61 source files pass mypy --strict, 111 files pass ruff check/format

### Modules Created (16 in `src/github_discovery/screening/`)
- **Infrastructure**: `types.py` (RepoContext, ScreeningContext, SubprocessResult), `subprocess_runner.py`
- **Gate 1 sub-score checkers**: `hygiene.py`, `ci_cd.py`, `test_footprint.py`, `release_discipline.py`, `dependency_quality.py`, `practices.py`, `maintenance.py`
- **Gate 1 engine**: `gate1_metadata.py` (Gate1MetadataScreener)
- **Gate 2 adapters**: `scorecard_adapter.py`, `osv_adapter.py`, `secrets_check.py`, `complexity.py`
- **Gate 2 engine**: `gate2_static.py` (Gate2StaticScreener)
- **Orchestrator**: `orchestrator.py` (ScreeningOrchestrator — Policy Engine)

### Test Files Created (18 in `tests/unit/screening/`)
- `conftest.py` (16 shared fixtures), `__init__.py`
- `test_types.py` (9), `test_subprocess_runner.py` (5)
- `test_hygiene.py` (10), `test_ci_cd.py` (10), `test_test_footprint.py` (10)
- `test_release_discipline.py` (10), `test_dependency_quality.py` (7)
- `test_practices.py` (5), `test_maintenance.py` (10)
- `test_gate1_metadata.py` (8), `test_scorecard_adapter.py` (6)
- `test_osv_adapter.py` (7), `test_secrets_check.py` (8)
- `test_complexity.py` (9), `test_gate2_static.py` (10), `test_orchestrator.py` (16)

### Key Decisions
- Sub-process tools (gitleaks, scc) use `SubprocessRunner` with graceful degradation (confidence=0.0-0.3)
- PyDriller requires local clone — maintenance analyzer uses API-based heuristics by default (confidence=0.7)
- OSV adapter returns neutral scores (confidence=0.0) since full lockfile parsing is deferred
- Gate 1 uses 7 sub-score checkers with weighted composite (`compute_total()`)
- Gate 2 uses 4 adapters: Scorecard API, OSV API, gitleaks, scc
- Hard gate enforcement: `ScreeningResult.can_proceed_to_gate3` checks both gates pass
- Orchestrator supports domain-specific thresholds (SECURITY domain → stricter Gate 2)
- `_context_override` helper compares against Pydantic field default to detect explicit user overrides
- `TypeVar("_SubScoreT", bound=SubScore)` for type-safe sub-score collection in Gate 1

### Issues Resolved
- Ruff I001 import sorting in `__init__.py` and `test_scorecard_adapter.py` — auto-fixed
- Ruff RUF022 `__all__` not sorted — removed inline comments, alphabetical order
- Ruff S108 `/tmp/repo` in tests — added `# noqa: S108` (mock paths in tests)
- Ruff PLR0911 too many return statements — refactored `_get_json` to dict dispatch
- Ruff format issue in `scorecard_adapter.py` — auto-fixed

### Files Modified
- `src/github_discovery/screening/` — 16 new modules + `__init__.py` updated with all exports
- `tests/unit/screening/` — 18 new test files
- `.workflow/state.md` — Updated with Phase 3 completion
- `progress.md` — This update

## Session: 2026-04-23 (Phase 5 Implementation)

### 13:00 — Phase 5 Scoring & Ranking (Layer D) Complete
- Implemented all 8 tasks from `docs/plans/phase5-implementation-plan.md`
- 810 tests passing (110 new scoring tests + 700 pre-existing), `make ci` green
- ruff check ✅ | ruff format ✅ | mypy --strict ✅ | pytest 810/810 ✅

### Modules Created (10 in `src/github_discovery/scoring/`)
- **types.py**: ScoringInput, DimensionScoreInfo, RankingResult, ExplainReport
- **engine.py**: ScoringEngine — composite scoring across Gate 1+2+3 with per-dimension source tracking
- **profiles.py**: ProfileRegistry — 11 domain weight profiles (4 existing + 7 new: WEB_FRAMEWORK, DATA_TOOL, ML_LIB, SECURITY_TOOL, LANG_TOOL, TEST_TOOL, DOC_TOOL)
- **value_score.py**: ValueScoreCalculator — anti-star bias formula with hidden gem detection + batch normalization
- **confidence.py**: ConfidenceCalculator — per-dimension confidence + gate coverage bonus
- **ranker.py**: Ranker — intra-domain ranking + deterministic tie-breaking + hidden gem identification
- **cross_domain.py**: CrossDomainGuard — min-max normalization + cross-domain comparison warnings
- **explainability.py**: ExplainabilityGenerator — summary/full reports + improvement suggestions
- **feature_store.py**: FeatureStore — SQLite-backed with TTL, CRUD, batch ops, statistics
- **config.py**: Added ScoringSettings with GHDISC_SCORING_* env prefix

### Test Files Created (10 in `tests/unit/scoring/`)
- `conftest.py` (shared fixtures), `__init__.py`
- `test_types.py` (9), `test_engine.py` (13), `test_profiles.py` (10)
- `test_value_score.py` (20), `test_confidence.py` (13), `test_ranker.py` (13)
- `test_cross_domain.py` (8), `test_explainability.py` (14), `test_feature_store.py` (10)

### Key Implementation Patterns Discovered
- Pydantic model fields need runtime imports (# noqa: TC001), NOT TYPE_CHECKING blocks
- StrEnum.__members__ returns uppercase names (CODE_QUALITY), not values (code_quality)
- pytest async yield fixtures need # noqa: ANN001 for type annotation conflict
- mypy strict requires explicit None arguments even with default parameters

### Pre-existing Ruff Issues Fixed
- `test_budget_controller.py`: PLW0108 unnecessary lambda → direct reference
- `test_orchestrator.py`: F841 unused variable + PLC0415 misplaced import

### Files Modified
- `src/github_discovery/scoring/` — 9 new modules + `__init__.py` updated with all exports
- `src/github_discovery/config.py` — Added ScoringSettings class
- `tests/unit/scoring/` — 10 new test files
- `tests/unit/assessment/` — 3 files fixed (pre-existing ruff issues)
- `docs/llm-wiki/wiki/` — Updated index.md, log.md, scoring-dimensions.md, anti-star-bias.md, new phase5-scoring-implementation.md
- `progress.md` — This update

## Session: 2026-04-23 (Phase 4+5 Post-Implementation Verification)

### 14:00 — Deep Analysis and Bug Fixes
- Systematic analysis of all Phase 4 (assessment/) and Phase 5 (scoring/) modules
- 25+ issues identified across both phases; all fixed
- 863 tests passing (53 new), `make ci` green: ruff + mypy --strict + pytest

### Phase 4 Fixes Applied
1. **Cache TTL enforcement (Issue #1)**: `orchestrator._cache` changed from `dict[str, DeepAssessmentResult]` → `dict[str, tuple[DeepAssessmentResult, float]]` with `time.monotonic()` timestamps. Expired entries are evicted on read. `_cache_ttl_seconds` from `AssessmentSettings.cache_ttl_hours`.
2. **Domain-specific prompt adjustments (Issue #3)**: `get_prompt()` now accepts `domain: DomainType | None`. Added `_DOMAIN_FOCUS` registry with 10 entries: CLI+code_quality, CLI+testing, ML_LIB+innovation, ML_LIB+functionality, SECURITY_TOOL+security, DEVOPS_TOOL+maintenance, DEVOPS_TOOL+testing, LANG_TOOL+code_quality, LANG_TOOL+testing, DATA_TOOL+testing, DATA_TOOL+documentation.
3. **Prompt tests (Issue #2)**: Created `tests/unit/assessment/test_prompts/` with 26 tests — registry completeness, content structure, domain focus behavior.
4. **repomix_adapter.py**: Added `timeout_seconds=120` with `asyncio.wait_for()`. Fixed `total_tokens` inflation after truncation.
5. **orchestrator.py**: Added pre-pack budget check. Fixed `gate_passed` derivation in hard gate error.
6. **llm_provider.py**: Added fallback model retry. Safe `close()` with try/except.
7. **config.py**: Added `llm_fallback_model`, `llm_subscription_mode`, `effective_base_url`.
8. **lang_analyzers/**: Created new module (base.py, python_analyzer.py) + 15 tests.

### Phase 5 Fixes Applied
1. **FeatureStore get_batch key collision**: Changed from `dict[str, ...]` → `dict[tuple[str, str], ...]`.
2. **ScoringEngine ↔ FeatureStore integration (Issue #4)**: Added `store: FeatureStore | None` to constructor. New `async score_cached()` — checks store before computing, writes back after. Sync `score()` unchanged.
3. **Ranker ranking_seed consumption (Issue #5)**: `_sort_key()` uses 4-tuple with `hash((ranking_seed, full_name))` for deterministic but seed-dependent tie-breaking.
4. **types.py**: Added `profile_override: DomainProfile | None` to `ScoringContext`.
5. **Dead code removed**: value_score.py (unreachable branch), confidence.py (redundant check), cross_domain.py (unused method).

### Test Files Changed
- `tests/unit/assessment/test_orchestrator.py` — Updated cache test (tuple), added 3 TTL tests
- `tests/unit/assessment/test_prompts/test_dimension_prompts.py` — NEW: 26 tests
- `tests/unit/assessment/test_prompts/__init__.py` — NEW
- `tests/unit/scoring/test_engine.py` — Added 7 FeatureStore integration tests
- `tests/unit/scoring/test_ranker.py` — Added 3 ranking_seed tests

### Files Modified
- `src/github_discovery/assessment/orchestrator.py` — Cache TTL enforcement
- `src/github_discovery/assessment/prompts/__init__.py` — Domain-specific focus adjustments
- `src/github_discovery/scoring/engine.py` — FeatureStore integration + async score_cached()
- `src/github_discovery/scoring/ranker.py` — Seeded hash tie-breaking
- `docs/llm-wiki/wiki/` — Updated phase4, phase5, index.md, log.md
- `progress.md` — This update

## Session: 2026-04-23 (Phase 6 Implementation)

### 15:30 — Phase 6 API & Worker Infrastructure Complete
- Implemented all 10 tasks from `docs/plans/phase6-implementation-plan.md`
- 990 tests passing (127 new), `make ci` green
- ruff check ✅ | ruff format ✅ | mypy --strict (108 files) ✅ | pytest 990/990 ✅

### Implementation Waves

**Wave A — Foundation (40 tests)**:
- `workers/types.py` — JobType, JobStatus, Job, WorkerResult
- `workers/job_store.py` — SQLite-backed JobStore with async CRUD
- `workers/queue.py` — AsyncTaskQueue (asyncio.Queue + JobStore)
- `api/app.py` — FastAPI application factory with lifespan, CORS, middleware
- `api/deps.py` — 10 dependency injection providers
- `api/middleware.py` — Request ID and timing middleware
- `api/errors.py` — Domain exception → HTTP status mapping
- `api/routes/__init__.py` — Route aggregation

**Wave B — Workers (32 tests)**:
- `workers/base_worker.py` — BaseWorker ABC with status tracking
- `workers/discovery_worker.py` — DiscoveryWorker wrapping DiscoveryOrchestrator
- `workers/screening_worker.py` — ScreeningWorker wrapping ScreeningOrchestrator
- `workers/assessment_worker.py` — AssessmentWorker wrapping AssessmentOrchestrator
- `workers/worker_manager.py` — WorkerManager lifecycle + typed dispatch
- Updated `api/app.py` — Integrated WorkerManager in lifespan

**Wave C — API Routes (33 tests)**:
- `api/routes/discovery.py` — POST /discover, GET /discover/{id}, GET /candidates
- `api/routes/screening.py` — POST /screen, GET /screen/{id}, GET /shortlist
- `api/routes/assessment.py` — POST /assess, GET /assess/{id}
- `api/routes/ranking.py` — GET /rank, GET /rank/{repo}, GET /explain/{repo}

**Wave D — Integration (22 tests)**:
- `api/middleware.py` — Added RateLimiter + rate_limit_middleware
- `api/auth.py` — API key authentication via APIKeyHeader
- `api/routes/export.py` — POST /export (JSON, CSV, Markdown)
- Updated `api/app.py` — Rate limiter state, export router, OpenAPI tags

### Key Implementation Decisions
- Lifespan uses deferred imports (inside function) to avoid circular imports
- Gate1MetadataScreener and Gate2StaticScreener require `rest_client` + `settings` in constructor
- PoolManager initialized with `:memory:` in API lifespan (stateless per instance)
- Rate limiter uses token bucket algorithm with monotonic time
- APIKeyHeader with `auto_error=False` for optional auth
- Export endpoint returns inline content for small exports
- Ranking/explain routes return stub responses (full E2E requires completed scoring pipeline)

### Files Created/Modified
- `pyproject.toml` — Added fastapi>=0.115, uvicorn[standard]>=0.30
- `src/github_discovery/config.py` — Added APISettings class
- `src/github_discovery/api/` — 11 new/updated modules
- `src/github_discovery/workers/` — 9 new/updated modules
- `tests/unit/api/` — 9 new test files (67 tests)
- `tests/unit/workers/` — 7 new test files (60 tests)
- `docs/llm-wiki/wiki/` — Updated phase6 plan status

## Session: 2026-04-23 (Phase 7 Implementation)

### 19:30 — Phase 7 MCP-Native Integration Layer Complete
- Implemented all 13 tasks from `docs/plans/phase7-implementation-plan.md`
- 1114 tests passing (124 new MCP tests + 990 pre-existing), `make ci` green
- ruff check ✅ | mypy --strict (118 files) ✅ | pytest 1114/1114 ✅

### Implementation Waves

**Wave A — Foundation (~25 tests)**:
- `mcp/server.py` — FastMCP factory, AppContext dataclass, app_lifespan, create_server, serve
- `mcp/session.py` — SessionManager with SQLite CRUD (initialize/close/get_or_create/update/delete/list_sessions)
- `mcp/output_format.py` — format_tool_result() + truncate_for_context()
- `mcp/progress.py` — report_discovery/screening/assessment_progress()
- `mcp/config.py` — ALL_TOOLS, TOOLSET_MAP, get_enabled_tools(), should_register_tool()
- `mcp/transport.py` — get_transport_args() for stdio + streamable-http
- `mcp/__init__.py` — Exports create_server, serve

**Wave B — Discovery + Screening Tools (~25 tests)**:
- `mcp/tools/discovery.py` — discover_repos, get_candidate_pool, expand_seeds
- `mcp/tools/screening.py` — screen_candidates, get_shortlist, quick_screen

**Wave C — Assessment + Ranking + Session Tools (~35 tests)**:
- `mcp/tools/assessment.py` — deep_assess, quick_assess, get_assessment
- `mcp/tools/ranking.py` — rank_repos, explain_repo, compare_repos
- `mcp/tools/session.py` — create_session, get_session, list_sessions, export_session

**Wave D — Resources + Prompts + Composition (~25 tests)**:
- `mcp/resources/repo_score.py` — `repo://{owner}/{name}/score` resource template
- `mcp/resources/pool_candidates.py` — `pool://{pool_id}/candidates` resource template
- `mcp/resources/domain_ranking.py` — `rank://{domain}/top` resource template
- `mcp/resources/session_status.py` — `session://{session_id}/status` resource template
- `mcp/prompts.py` — 5 prompt skills (discover_underrated, quick_quality_check, compare_for_adoption, domain_deep_dive, security_audit)
- `mcp/github_client.py` — get_composition_config() for kilo/opencode/claude targets

**Wave E — CLI Integration & Tests (15 tests)**:
- `mcp/__main__.py` — Entry point for `python -m github_discovery.mcp serve`
- `cli.py` — Updated with `mcp` subcommand: `serve` (start server) + `init-config` (generate config)
- `tests/integration/test_mcp_server.py` — 12 integration tests
- `tests/agentic/test_mcp_client.py` — 3 stub tests (skipped, future MCP client)

### Key Implementation Decisions
- AppContext contains only `settings` + `session_manager`; tools create orchestrators/pool_managers per invocation (stateless)
- Tool filtering: `should_register_tool()` checks both `enabled_toolsets` and `exclude_tools`
- Ruff per-file-ignores needed for MCP tool modules: PLC0415, PLR0915, TCH, S101
- MCPSettings extended with 6 fields: session_store_path, enabled_toolsets, exclude_tools, json_response, stateless_http, streamable_http_path
- Resource templates stored in `mcp._resource_manager._templates` (not `_resources`)
- CLI `mcp serve` overrides Settings transport/host/port from CLI flags

### Files Created/Modified
- `pyproject.toml` — Added mcp>=1.6, per-file-ignores for MCP modules
- `src/github_discovery/config.py` — MCPSettings extended with 6 new fields
- `src/github_discovery/cli.py` — Full CLI with mcp serve + init-config commands
- `src/github_discovery/mcp/` — 20 source files (server, session, tools, resources, prompts, config, transport, etc.)
- `tests/unit/mcp/` — 22 unit test files
- `tests/integration/test_mcp_server.py` — 12 integration tests
- `tests/agentic/test_mcp_client.py` — 3 stub tests
- `docs/llm-wiki/wiki/` — Updated phase7 plan, index, log
- `.workflow/state.md` — Phase 7 completion
