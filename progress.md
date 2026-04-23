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
