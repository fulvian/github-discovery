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
