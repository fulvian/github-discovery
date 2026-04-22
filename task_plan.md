# GitHub Discovery — Task Plan

## Goal
Creare il Foundation Blueprint per "GitHub Discovery": uno strumento per scoprire repository GitHub di alta qualita tecnica indipendentemente dalla popolarita (stars, discussioni online).

## Problem Statement
I motori di ricerca e gli AI agent (Perplexity, Claude, ChatGPT, Gemini) si basano principalmente su:
- Stelle GitHub (popolarita)
- Frequenza di discussione online (Reddit, Stack Overflow, blog)

Questo crea un bias sistematico che esclude progetti tecnicamente eccellenti ma con scarsa visibilita.

## Phases

### Phase 1: Ricerca Esplorativa [complete]
- [x] Ricerca progetti simili gia esistenti
- [x] Analisi GitHub API per valutazione qualitativa
- [x] Metodi alternativi di valutazione tecnica
- [x] GitHub MCP e strumenti di scanning

### Phase 2: Analisi e Sintesi [complete]
- [x] Confronto approcci trovati
- [x] Identificazione gap e opportunita
- [x] Definizione metriche di qualita tecnica

### Phase 3: Foundation Blueprint [complete]
- [x] Stesura del documento fondativo
- [x] Definizione aree di approfondimento
- [x] Domande aperte per iterazioni successive

### Phase 0: Scaffolding [complete]
- [x] pyproject.toml + build system
- [x] Package structure (src/github_discovery/)
- [x] Configuration (pydantic-settings, GHDISC_ env vars)
- [x] Exception hierarchy
- [x] Structured logging (structlog)
- [x] Session models (SessionState, SessionConfig, ProgressInfo)
- [x] MCP spec models (MCPToolSpec, AgentWorkflowConfig)
- [x] CLI skeleton (typer)
- [x] MCP server skeleton (FastMCP)
- [x] Test infrastructure (pytest, ruff, mypy)
- [x] CI (GitHub Actions, pre-commit)

### Phase 1: Data Models & Type System [complete]
- [x] 1.7 Enums (ScoreDimension: FUNCTIONALITY/INNOVATION, CandidateStatus)
- [x] 1.1 RepoCandidate, CandidatePool
- [x] 1.2 Gate 1 screening models (7 sub-scores + MetadataScreenResult)
- [x] 1.3 Gate 2 screening models (4 sub-scores + StaticScreenResult + ScreeningResult)
- [x] 1.4 Assessment models (DimensionScore, TokenUsage, DeepAssessmentResult)
- [x] 1.5 Scoring models (DomainProfile, ScoreResult, RankedRepo, ExplainabilityReport)
- [x] 1.8 Feature Store (FeatureStoreKey, RepoFeatures)
- [x] 1.6 API request/response models
- [x] 1.9 Agent models (MCPToolResult, DiscoverySession)
- [x] `make ci` green: ruff + mypy --strict + 140 tests passing

### Phase 2: Discovery Engine (Layer A) [complete]
- [x] Phase 2 implementation plan created: `docs/plans/phase2-implementation-plan.md`
- [x] Task 2.1 — GitHub REST API Client (httpx, auth, rate limit, retry, pagination) — 16 tests
- [x] Task 2.2 — GitHub GraphQL Client (cursor-based pagination) — 13 tests
- [x] Task 2.3 — Search API Channel (query builder, filtri, sort recency) — 11 tests
- [x] Task 2.4 — Code Search Channel (quality signal patterns) — 13 tests
- [x] Task 2.5 — Dependency Graph Channel — 25 tests
- [x] Task 2.6 — Package Registry Channel (PyPI, npm) — 30 tests
- [x] Task 2.7 — Awesome Lists & Curated Sources Channel — 17 tests
- [x] Task 2.8 — Seed Expansion (co-contributor, org adjacency) — 25 tests
- [x] Task 2.9 — Discovery Orchestrator (coordination, dedup, scoring) — 15 tests
- [x] Task 2.10 — Candidate Pool Manager (SQLite persistence) — 13 tests
- [x] `discovery/__init__.py` exports updated
- [x] `make ci` green: ruff + mypy --strict + 320 tests passing

## Deliverables
- `docs/foundation/github-discovery_foundation_blueprint.md`
- `findings.md`
- `progress.md`

## Constraints
- Fase esplorativa, non implementativa
- Output: documento blueprint + domande aperte
- Approccio iterativo, non one-shot

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| Tavily research API usage limit | 1 | fallback su Brave/GitHub API/perplexity |
| Firecrawl insufficient credits | 1 | fallback su Brave/GitHub API |
| Brave rate-limited su burst requests | 1 | richieste sequenziali e fonti alternative |
| Perplexity transient network error | 1 | retry con query ridotta |
