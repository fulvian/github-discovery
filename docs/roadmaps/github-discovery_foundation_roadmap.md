# GitHub Discovery — Foundation Roadmap

## Meta

- **Stato**: Draft v1
- **Data**: 2026-06-XX
- **Riferimento blueprint**: `docs/foundation/github-discovery_foundation_blueprint.md` (inclusa estensione §21 Agentic Integration)
- **Architettura target**: Option C — API + Scoring Workers + MCP Facade + CLI (hybrid) → aggiornato a: MCP-native Agentic Discovery Engine (MCP primaria, API secondaria, CLI agent-friendly)
- **Stack primario**: Python 3.12+, Pydantic v2, FastAPI, httpx, structlog, MCP Python SDK
- **Durata stimata totale**: 18-28 settimane (iterativa, con checkpoint di validazione; +2-4 settimane per integrazione agentica)

---

## Indice

1. [Panoramica macro-fasi](#1-panoramica-macro-fasi)
2. [Dipendenze tra fasi](#2-dipendenze-tra-fasi)
3. [Dettaglio fasi e task](#3-dettaglio-fasi-e-task)
   - [Phase 0 — Project Foundation & Scaffolding](#phase-0--project-foundation--scaffolding)
   - [Phase 1 — Data Models & Type System](#phase-1--data-models--type-system)
   - [Phase 2 — Discovery Engine (Layer A)](#phase-2--discovery-engine-layer-a)
   - [Phase 3 — Lightweight Quality Screening (Layer B)](#phase-3--lightweight-quality-screening-layer-b)
   - [Phase 4 — Deep Technical Assessment (Layer C)](#phase-4--deep-technical-assessment-layer-c)
   - [Phase 5 — Scoring, Ranking & Explainability (Layer D)](#phase-5--scoring-ranking--explainability-layer-d)
   - [Phase 6 — API & Worker Infrastructure](#phase-6--api--worker-infrastructure)
   - [Phase 7 — MCP Integration Layer](#phase-7--mcp-integration-layer)
   - [Phase 8 — CLI](#phase-8--cli)
   - [Phase 9 — Integration Testing & Feasibility Validation](#phase-9--integration-testing--feasibility-validation)
   - [Phase 10 — Alpha Engine & Polish](#phase-10--alpha-engine--polish)
4. [Milestone & Checkpoint di validazione](#4-milestone--checkpoint-di-validazione)
5. [KPI di avanzamento](#5-kpi-di-avanzamento)
6. [Rischi per fase](#6-rischi-per-fase)
7. [Stack tecnologico verificato](#7-stack-tecnologico-verificato)
8. [Regole operative](#8-regole-operative)

---

## 1) Panoramica macro-fasi

| # | Macro-Fase | Settimane | Priorità | Dipende da | Deliverable principale |
|---|-----------|-----------|----------|------------|----------------------|
| 0 | Project Foundation & Scaffolding | 1-2 | Critica | — | Progetto eseguibile, CI verde, models base, session models |
| 1 | Data Models & Type System | 1-2 | Critica | Phase 0 | Tutti i Pydantic models, schemas API, agent support models |
| 2 | Discovery Engine (Layer A) | 2-3 | Alta | Phase 1 | Pipeline discovery multicanale operativa |
| 3 | Quality Screening (Layer B) | 2-3 | Alta | Phase 1 | Gate 1+2 operativi, screening non-LLM completo |
| 4 | Deep Assessment (Layer C) | 2-3 | Alta | Phase 3 | Gate 3 LLM deep-scan operativo con budget ctrl |
| 5 | Scoring, Ranking & Explainability (Layer D) | 1-2 | Alta | Phase 4 | Motore ranking anti-star bias, explainability |
| 6 | API & Worker Infrastructure | 2-3 | Alta | Phase 5 | FastAPI operativa, worker attivi, queue |
| 7 | MCP-Native Integration Layer | 2-3 | Alta | Phase 5 | MCP primaria: tools granulari, prompts-as-skills, session mgmt, progress notifications |
| 8 | CLI (Batch + Agent-Friendly) | 1-2 | Media | Phase 6+7 | Comandi discover/screen/deep-eval/rank/export + session + streaming |
| 9 | Integration Testing & Feasibility Validation | 2-3 | Critica | Phase 8 | Sprint 0 feasibility + agentic integration testing con client reali |
| 10 | Alpha Engine & Marketplace | 2-3 | Media | Phase 9 | Alpha release, Docker, PyPI, Kilo Marketplace, OpenCode template |

**Nota sulle parallelizzazioni**:
- Phase 2 (Discovery) e Phase 3 (Screening) possono procedere in parallelo dopo Phase 1.
- Phase 8 (CLI) e Phase 7 (MCP) possono procedere in parallelo dopo Phase 5/6.
- Phase 9 (Testing) è il gate critico che valida l'intero sistema.

---

## 2) Dipendenze tra fasi

```
Phase 0 (Scaffolding + Session Models)
  │
  └─► Phase 1 (Models + Agent Support)
        │
        ├─► Phase 2 (Discovery — Layer A)  ──┐
        │                                      ├─► Phase 4 (Deep Assessment — Layer C)
        └─► Phase 3 (Screening — Layer B)  ──┘       │
                                                        └─► Phase 5 (Scoring/Ranking — Layer D)
                                                              │
                                                       ┌──────┴──────┐
                                                       │              │
                                                 Phase 6 (API)   Phase 7 (MCP-Native) ◄── MCP primaria
                                                       │              │
                                                       └──────┬──────┘
                                                              │
                                                       Phase 8 (CLI + Session)
                                                              │
                                                       Phase 9 (Validation + Agentic Testing)
                                                              │
                                                       Phase 10 (Alpha + Marketplace)
```

**Nota architetturale (Blueprint §21)**: Phase 7 (MCP-Native) è ora un'interfaccia primaria co-ordinata con Phase 6 (API). Entrambe consumano gli stessi servizi core. MCP espone tools granulari per progressive deepening; API espone endpoints CRUD/async. Phase 8 (CLI) supporta session management per uso agentico interattivo. Phase 9 include testing agentic integration con client reali.

---

## 3) Dettaglio fasi e task

---

### Phase 0 — Project Foundation & Scaffolding

**Obiettivo**: Creare la struttura progettuale eseguibile con tooling configurato, CI verde e baseline verificabile.

**Durata**: 1-2 settimane

| Task ID | Task | Dettaglio | Output | Verifica |
|---------|------|-----------|--------|----------|
| 0.1 | Inizializzazione struttura progetto | Creare `pyproject.toml` (hatch/setuptools), directory `src/github_discovery/`, `tests/`, `docs/` | Progetto installabile via `pip install -e .` | `python -c "import github_discovery"` funziona |
| 0.2 | Configurazione tooling sviluppo | Ruff (lint+format, line-length=99), mypy --strict, pytest, pre-commit hooks | `make lint` e `make test` verdi | CI passa |
| 0.3 | Moduli `__init__` e `config.py` | `pydantic-settings` con env prefix `GHDISC_`, defaults per sviluppo locale | Classe `Settings` funzionante | `GHDISC_GITHUB_TOKEN=xxx python -c "from github_discovery.config import Settings"` |
| 0.4 | Sistema di logging | `structlog` configurato con JSON output, contesto request/repo | Logger strutturato operativo | Log JSON con campi contestuali |
| 0.5 | Gerarchia eccezioni | `GitHubDiscoveryError` base → `DiscoveryError`, `ScreeningError`, `AssessmentError`, `ScoringError`, `ConfigurationError` | Modulo `exceptions.py` | mypy --strict passa |
| 0.6 | Makefile | Target: `install`, `test`, `lint`, `format`, `typecheck`, `run`, `clean` | Makefile operativo | `make install && make lint && make test` |
| 0.7 | CI baseline (GitHub Actions) | Workflow: lint → typecheck → test, Python 3.12, cache pip | CI verde su push | Badge verde |
| 0.8 | AGENTS.md & CLAUDE.md | Aggiornare con comandi build/lint/test effettivi | Docs operative | Comandi documentati funzionano |
| 0.9 | Modelli sessione agentica | `SessionState` (session_id, config, status, created_at, pool_ids), `SessionConfig` (soglie per-sessione, budget, domini preferiti), `ProgressInfo` (progress_token, percentuale, messaggio) | `models/session.py` | mypy strict, sessione creabile e persistibile |
| 0.10 | MCP tool spec models | `MCPToolSpec` (nome, parametri, output_schema, session_aware), `AgentWorkflowConfig` (workflow_name, tool_sequence, default_params) | `models/mcp_spec.py` | Ogni tool MCP ha spec documentata |
| 0.11 | .kilo/mcp.json template | Template configurazione MCP per Kilocode CLI e VS Code, con github-discovery + GitHub MCP composizione | `.kilo/mcp.json.template` | `kilo mcp list` mostra server configurato |

**Checkpoint Phase 0**: Progetto installabile, CI verde, config funzionante, logging strutturato.

---

### Phase 1 — Data Models & Type System

**Obiettivo**: Definire tutti i modelli Pydantic v2 che costituiscono il vocabolario del dominio. Ogni fase successiva dipende da questi tipi.

**Durata**: 1-2 settimane

| Task ID | Task | Dettaglio | Output | Verifica |
|---------|------|-----------|--------|----------|
| 1.1 | Modello `RepoCandidate` | `full_name`, `url`, `description`, `language`, `topics`, `stars` (solo contesto), `created_at`, `updated_at`, `pushed_at`, `license`, `default_branch`, `size_kb`, `open_issues_count`, `forks_count`, `archived`, `disabled`, `source_channel`, `discovery_score` | `models/candidate.py` | mypy strict, istanziabile da dict JSON |
| 1.2 | Modelli screening Gate 1 | `MetadataScreenResult` con sottoscore: `HygieneScore`, `MaintenanceScore`, `ReleaseDisciplineScore`, `ReviewPracticeScore`, `TestFootprintScore`, `CiCdScore`, `DependencyQualityScore` + `gate1_pass: bool`, `gate1_total: float` | `models/screening.py` | Ogni sottoscore ha range 0.0-1.0 |
| 1.3 | Modelli screening Gate 2 | `StaticScreenResult` con: `SecurityHygieneScore`, `VulnerabilityScore`, `ComplexityScore`, `SecretHygieneScore` + `gate2_pass: bool`, `gate2_total: float` | `models/screening.py` | Range 0.0-1.0, composizione valida |
| 1.4 | Modelli deep assessment Gate 3 | `DeepAssessmentResult` con `DimensionScore` per ciascuna delle 8 dimensioni (Code Quality, Architecture, Testing, Documentation, Maintenance, Security, Functional Completeness, Innovation) + `explanation: str`, `evidence: list[str]`, `confidence: float`, `gate3_pass: bool` | `models/assessment.py` | Dimensioni validate, confidence 0.0-1.0 |
| 1.5 | Modelli scoring & ranking | `ScoreResult` (composite multi-score), `ValueScore` (`quality_score / log10(stars + 10)`), `RankedRepo` (rank position + intra-domain), `ExplainabilityReport` (feature breakdown per dimensione), `DomainProfile` (taxonomy + weights) | `models/scoring.py` | ValueScore calcolabile, domain-aware |
| 1.6 | Modelli API request/response | `DiscoveryQuery`, `ScreeningRequest`, `AssessmentRequest`, `RankingQuery`, `ExportRequest` + response wrappers con pagination | `models/api.py` | Compatibili con FastAPI serialization |
| 1.7 | Enums e tipi condivisi | `DomainType` (CLI, web_framework, data_tool, ml_lib, devops_tool, library, backend, other), `ScoreDimension` enum, `DiscoveryChannel` enum, `GateLevel` enum | `models/enums.py` | Coprono tutti i casi d'uso del blueprint |
| 1.8 | Modello Feature Store | `RepoFeatures` — persistenza feature per repo (evita ricalcolo), key su `repo_full_name + commit_sha`, TTL, source gate | `models/features.py` | Dedup via SHA funzionante |
| 1.9 | Modelli supporto agentico | `ProgressNotification` (progress_token, progress, total, message, session_id), `MCPToolResult` (summary, references, detail_available_via, confidence), `DiscoverySession` (link a SessionState, pool, screening e assessment completati) | `models/agent.py` | Compatibili con FastAPI serialization e MCP structured content |

**Checkpoint Phase 1**: Tutti i modelli passano mypy --strict, serializzazione JSON round-trip, validator Pydantic operativi.

---

### Phase 2 — Discovery Engine (Layer A)

**Obiettivo**: Implementare la pipeline di discovery multicanale che produce un pool di candidati con score preliminare (Gate 0).

**Durata**: 2-3 settimane

| Task ID | Task | Dettaglio | Output | Verifica |
|---------|------|-----------|--------|----------|
| 2.1 | GitHub REST API client | Client `httpx.AsyncClient` con autenticazione (Bearer token), rate limit awareness (`x-ratelimit-*`), retry con backoff, conditional requests (`etag`/`if-modified-since`), paginazione rigorosa | `discovery/github_client.py` | Test con mock `respx`/`pytest-httpx`, rispetta rate limits |
| 2.2 | GitHub GraphQL client | Client GraphQL con cursor-based pagination (`first/after`), batch controllato per query cost, gestione `pageInfo` | `discovery/github_graphql.py` | Query aggregate funzionanti con mock |
| 2.3 | Canale Search API | Query builder con filtri avanzati (topic, language, date range, size, forks), ordinamento per recency/updated | `discovery/search_channel.py` | Trova candidati da query semantiche |
| 2.4 | Canale Code Search | Ricerca pattern di quality signal nei file (es. presenza `pytest`, `CI.yml`, `SECURITY.md`) | `discovery/code_search_channel.py` | Identifica repo con segnali di qualità nel codice |
| 2.5 | Dependency graph traversal | Da repo seed affidabili, traversare `dependencies`/`dependents` per trovare utenti | `discovery/dependency_channel.py` | Trova repo referenziati da progetti affidabili |
| 2.6 | Package registry mapping | Query npm/PyPI/crates.io/Maven per package → mapping al repository GitHub | `discovery/registry_channel.py` | Almeno 2 registry funzionanti |
| 2.7 | Awesome lists & curated sources | Parser per awesome-X lists (GitHub README), curated collection, community lists | `discovery/curated_channel.py` | Estrae repo da almeno 3 awesome lists |
| 2.8 | Seed expansion | Co-contributor analysis, org adjacency (stesso org del seed), co-dependency | `discovery/seed_expansion.py` | Espande pool da seed iniziale |
| 2.9 | Discovery orchestrator | Coordina i canali, deduplica per `full_name`, assegna `discovery_score` preliminare, gestisce concorrenza con `asyncio.Semaphore` | `discovery/orchestrator.py` | Pipeline end-to-end su query di test |
| 2.10 | Candidate pool manager | Persistenza pool candidati (SQLite/JSON interim), stato per candidato (discovered/screened/assessed/ranked) | `discovery/pool.py` | CRUD operazioni su pool funzionanti |

**Checkpoint Phase 2**: Discovery pipeline produce pool di candidati da almeno 3 canali, deduplica funzionante, score preliminare assegnato.

---

### Phase 3 — Lightweight Quality Screening (Layer B)

**Obiettivo**: Implementare Gate 1 (metadata screening, zero LLM) e Gate 2 (static/security screening, zero o low cost) per ridurre il pool ai candidati meritevoli di deep scan.

**Durata**: 2-3 settimane

| Task ID | Task | Dettaglio | Output | Verifica |
|---------|------|-----------|--------|----------|
| 3.1 | Gate 1 — Metadata screening engine | Orchestrazione sottoscore Gate 1, politica di gating (soglie minime per pass), fallback rule-based | `screening/gate1_metadata.py` | Screening riproducibile su repo di test |
| 3.2 | Hygiene files checker | Verifica presenza e qualità di: `LICENSE` (SPDX valid), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md`, `README.md` (con contenuto minimo) | `screening/hygiene.py` | Scoring su repo nota passa/predica correttamente |
| 3.3 | CI/CD detection | Presenza `.github/workflows/`, CI badge nel README, configurazione CI valida (non trivial) | `screening/ci_cd.py` | Rileva workflow GitHub Actions, Travis, Circle |
| 3.4 | Test footprint analyzer | Presenza directory `tests/`/`test_`/`_test.`, file spec/config (`pytest.ini`, `setup.cfg` test section, `conftest.py`), ratio test files / source files | `screening/test_footprint.py` | Rileva almeno 5 pattern di test comuni |
| 3.5 | Release discipline scorer | Tagging semver, cadence di release, changelog per release, release notes | `screening/release_discipline.py` | Scoring su repo con release regolari vs no-release |
| 3.6 | Maintenance signal analyzer | Recency ultimo commit, cadenza commit (PyDriller: commit frequency, code churn), bus factor proxy (PyDriller: `ContributorsCount`/`ContributorsExperience`), risoluzione issue | `screening/maintenance.py` | PyDriller metrics calcolate su clone shallow |
| 3.7 | Issue/PR practices scorer | Template issue/PR, tempo medio risposta, evidenza review, label usage | `screening/practices.py` | Dati da GitHub API (issue/PR metadata) |
| 3.8 | Dependency quality scorer | Lockfile presence (`package-lock.json`, `poetry.lock`, `Pipfile.lock`), pinning, update signals (dependabot/renovate config) | `screening/dependency_quality.py` | Rileva almeno lockfile + pinning |
| 3.9 | Gate 2 — Static/security screening engine | Orchestrazione Gate 2, politica gating (soglie security minime) | `screening/gate2_static.py` | Hard rule: nessun Gate 3 senza Gate 1+2 pass |
| 3.10 | OpenSSF Scorecard integration | Chiamata Scorecard API (`scorecard.dev`), parsing risultato, mapping a `SecurityHygieneScore` | `screening/scorecard_adapter.py` | Score su repo nota con scorecard pubblica |
| 3.11 | Secret hygiene check | Integrazione gitleaks (subprocess su clone shallow), parsing SARIF output | `screening/secrets_check.py` | Rileva secret in repo di test con pattern noti |
| 3.12 | Dependency vulnerability scan | OSV API query per dipendenze dichiarate (da lockfile/manifest), mapping a `VulnerabilityScore` | `screening/osv_adapter.py` | Query OSV su eco-sistema Python/Node |
| 3.13 | Code complexity metrics | Integrazione `scc` (subprocess, JSON output) per LOC/language/complexity, oppure `cloc`, fallback PyDriller per nloc/complexity per lang supportati | `screening/complexity.py` | Metriche calcolate su repo multi-language |
| 3.14 | Screening orchestrator & gating policy | Policy Engine: soglie per dominio, pesi, configurabilità via `GHDISC_*` env, hard gate enforcement (Gate 1+2 prima di Gate 3) | `screening/orchestrator.py` | Nessun candidato passa a Gate 3 senza Gate 1+2 |

**Regola critica (Blueprint §16.5)**: Nessun deep-scan LLM sotto soglia minima Gate 1+2. Implementare come hard constraint nel codice.

**Checkpoint Phase 3**: Gate 1+2 operativi con scoring riproducibile, hard gate enforcement, almeno 4 tool esterni integrati (Scorecard, gitleaks, OSV, scc/cloc).

---

### Phase 4 — Deep Technical Assessment (Layer C)

**Obiettivo**: Implementare la valutazione tecnica ad alta precisione tramite LLM + heuristiche, con budget control rigoroso. Solo top percentile (10-15%) dal Gate 2.

**Durata**: 2-3 settimane

| Task ID | Task | Dettaglio | Output | Verifica |
|---------|------|-----------|--------|----------|
| 4.1 | Repomix integration | Wrappare `repomix` CLI per impacchettare codebase (output: file singolo con struttura), gestire repo grandi con timeout e early-stop | `assessment/repomix_adapter.py` | Output Repomix su repo di test < 50k token |
| 4.2 | LLM provider abstraction | Interfaccia astratta per provider LLM (OpenAI, Anthropic, local), supporto structured output (JSON schema), fallback tra provider | `assessment/llm_provider.py` | Chiamata LLM con structured output funzionante |
| 4.3 | Multi-dimension assessment prompts | Prompt template per ciascuna delle 8 dimensioni, con istruzioni per scoring + explanation + evidence, domain-aware | `assessment/prompts/` directory | Output LLM parseable su dimensione singola |
| 4.4 | Assessment result parser | Parse risposta LLM → `DeepAssessmentResult` Pydantic model, validazione struttura, fallback su parsing parziale | `assessment/result_parser.py` | Parsing robusto con gestione formati LLM variabili |
| 4.5 | Code structure heuristic scoring | Euristiche non-LLM per: modularity (directory structure), coupling (import analysis), abstraction layers, API surface | `assessment/heuristics.py` | Score euristico su repo multi-module |
| 4.6 | Language-specific quality analyzers | Adapter per analizzatori specifici: `ruff` (Python), `eslint` config presence (JS), `cargo clippy` (Rust) — solo dove disponibile | `assessment/lang_analyzers/` | Almeno Python adapter operativo |
| 4.7 | LLM budget controller | Token budget per giorno e per repo, timeout/early-stop su repo troppo grandi, caching obbligatorio risultati intermedi, dedup per commit SHA, retry con backoff | `assessment/budget_controller.py` | Hard limits rispettati, nessun overflow di budget |
| 4.8 | Deep assessment orchestrator | Coordina Repomix → LLM → parser → heuristic → result, gestisce concorrenza (max N repo in parallelo), error recovery | `assessment/orchestrator.py` | Pipeline end-to-end su 5-10 repo reali |

**Regola critica (Blueprint §16.5)**: Massimo budget token/giorno e per repo. Timeout e early-stop obbligatori. Caching per commit SHA.

**Checkpoint Phase 4**: Deep assessment produce `DeepAssessmentResult` con 8 dimensioni + explanation + confidence. Budget controller rispetta i limiti. Caching per SHA funzionante.

---

### Phase 5 — Scoring, Ranking & Explainability (Layer D)

**Obiettivo**: Implementare il motore di ranking finale anti-star bias, intra-dominio, con explainability completa.

**Durata**: 1-2 settimane

| Task ID | Task | Dettaglio | Output | Verifica |
|---------|------|-----------|--------|----------|
| 5.1 | Multi-dimensional scoring engine | Combinazione pesata di Gate 1+2+3 score per dimensione, normalizzazione, gestione missing data (confidence adjustment) | `scoring/engine.py` | Score composito calcolato con pesi configurabili |
| 5.2 | Domain taxonomy & weight profiles | Taxonomia `DomainType` con pesi specifici per dominio (es. CLI: testing 20%, ML: documentation 15%), `DomainProfile` configurabile via YAML/env | `scoring/profiles.py` | Almeno 3 profili dominio definiti |
| 5.3 | Anti-star bias formula | `ValueScore = quality_score / log10(star_count + 10)`, stars come feature di contesto non primaria, normalizzazione per evitare divisioni extreme | `scoring/value_score.py` | Hidden gems (basse stars, alta quality) rankano sopra repo popolari medi |
| 5.4 | Confidence score calculator | Basato su: completezza dati disponibili, numero dimensioni valutate, qualità segnali (API vs euristica vs LLM) | `scoring/confidence.py` | Repo con dati incompleti ha confidence bassa |
| 5.5 | Intra-domain ranking engine | Ranking separato per `DomainType`, no confronto diretto cross-domain, stabilizzazione ranking tra run (determinismo con seed) | `scoring/ranker.py` | Ranking stabile su 2 run successive sullo stesso pool |
| 5.6 | Cross-domain comparison guard | Se confronto cross-domain richiesto: normalizzazione relativa + avviso esplicito di confronto non ideale | `scoring/cross_domain.py` | Warning emesso quando si confrontano domini diversi |
| 5.7 | Explainability report generator | Report per repo: breakdown score per dimensione, feature principali, evidenze chiave, confronto con baseline star-based | `scoring/explainability.py` | Report leggibile per sviluppatore su repo reale |
| 5.8 | Feature store & caching | Persistenza feature per repo (evita ricalcolo), key su `repo_full_name + commit_sha`, TTL configurabile, invalidazione su nuovo commit | `scoring/feature_store.py` | Recupero feature cached senza ricalcolo |

**Checkpoint Phase 5**: Ranking anti-star bias funzionante, explainability leggibile, domain-aware, confidence score significativo.

---

### Phase 6 — API & Worker Infrastructure

**Obiettivo**: Implementare la superficie API REST (FastAPI) e l'infrastruttura worker per esecuzione asincrona delle pipeline di scoring.

**Durata**: 2-3 settimane

| Task ID | Task | Dettaglio | Output | Verifica |
|---------|------|-----------|--------|----------|
| 6.1 | FastAPI application setup | App FastAPI con middleware (CORS, request ID, timing), structlog integration, health/readiness endpoints, error handlers custom | `api/app.py` | `GET /health` ritorna 200 |
| 6.2 | Discovery API endpoints | `POST /api/v1/discover` (avvia discovery), `GET /api/v1/discover/{job_id}` (stato), `GET /api/v1/candidates` (lista pool) | `api/routes/discovery.py` | E2E: avvia discovery → polling → risultati |
| 6.3 | Screening API endpoints | `POST /api/v1/screen` (avvia screening su pool), `GET /api/v1/screen/{job_id}` (stato), `GET /api/v1/shortlist` (candidati Gate 1+2 pass) | `api/routes/screening.py` | Screening asincrono con job tracking |
| 6.4 | Assessment API endpoints | `POST /api/v1/assess` (avvia deep assessment), `GET /api/v1/assess/{job_id}` (stato), hard gate: rifiuta se candidate non passato Gate 1+2 | `api/routes/assessment.py` | Hard gate enforcement nell'API |
| 6.5 | Ranking & query API endpoints | `GET /api/v1/rank` (ranking per dominio), `GET /api/v1/rank/{repo}` (dettaglio singolo repo), `GET /api/v1/explain/{repo}` (explainability), parametri filtro (dominio, range score, query) | `api/routes/ranking.py` | Query con filtri funzionanti |
| 6.6 | Scoring workers | Worker separati per tipo: `MetadataWorker` (Gate 1), `StaticWorker` (Gate 2), `LLMWorker` (Gate 3), esecuzione concorrente con `asyncio.Semaphore`, isolamento errori | `workers/` directory | Workers eseguono pipeline asincrona |
| 6.7 | Task queue integration | Queue per job asincroni (inizialmente `asyncio.Queue` o SQLite-backed, evolvibile verso Redis/RQ), tracking stato job, retry policy | `workers/queue.py` | Job submission → processing → completion |
| 6.8 | Rate limiting & auth middleware | Rate limiting API (per IP/key), API key auth (env-configured), CORS configurabile | `api/middleware.py` | Rate limit rispettato, auth funzionante |
| 6.9 | API documentation | OpenAPI auto-generata da FastAPI, schema export, esempi per ogni endpoint | Swagger UI | `/docs` accessibile e completa |
| 6.10 | Export endpoints | `POST /api/v1/export` (JSON/CSV/Markdown export di risultati ranked) | `api/routes/export.py` | Export JSON e CSV funzionanti |

**Checkpoint Phase 6**: API REST completa, worker asincroni operativi, hard gate enforcement, documentazione auto-generata.

---

### Phase 7 — MCP Integration Layer (MCP-Native Primary Interface)

**Obiettivo**: Implementare l'interfaccia primaria MCP (Model Context Protocol) che espone discovery/scoring/ranking come tools composable, resources strutturate, e prompts come agent skill definitions. MCP è l'interfaccia primaria del sistema — API REST è consumer secondario degli stessi servizi core.

**Principio architetturale (Blueprint §21.2)**: MCP-First Design. I tool sono granulari (per-gate), composable (combinabili in workflow multi-step), e session-aware (supportano progressive deepening cross-sessione).

**Durata**: 2-3 settimane

| Task ID | Task | Dettaglio | Output | Verifica |
|---------|------|-----------|--------|----------|
| 7.1 | MCP server setup (FastMCP) | `FastMCP` Python SDK (`mcp.server.fastmcp`), nome server `github-discovery`, transport configurabile (stdio per Kilocode CLI/OpenClaude, streamable-http per deployment remoto), structured content attivo | `mcp/server.py` | Server avviabile via `python -m github_discovery.mcp serve --transport stdio` e via `--transport http --port 8080` |
| 7.2 | MCP tools — Discovery (progressive) | Tool `discover_repos(query, channels, max_candidates, session_id)` → pool con discovery_score, Tool `get_candidate_pool(pool_id, filters, sort_by, limit)` → candidati on-demand, Tool `expand_seeds(seed_urls, expansion_strategy, max_depth, session_id)` → espansione seed. Ogni tool è session-aware e restituisce summary-first con reference | `mcp/tools/discovery.py` | Invocazione tool da client MCP di test, session_id funzionante |
| 7.3 | MCP tools — Screening (per-gate) | Tool `screen_candidates(pool_id, gate_level, min_gate1_score, min_gate2_score, session_id)` → screening al livello scelto, Tool `get_shortlist(pool_id, min_score, domain, limit)` → shortlist filtrata, Tool `quick_screen(repo_url, gate_levels)` → screening rapido singolo repo | `mcp/tools/screening.py` | Per-gate invocation, soglie configurabili, hard gate enforcement |
| 7.4 | MCP tools — Assessment (per-depth) | Tool `deep_assess(repo_urls, dimensions, budget_tokens, session_id)` → deep assessment con hard gate (rifiuta se non passato Gate 1+2), Tool `quick_assess(repo_url, dimensions)` → assessment rapido subset, Tool `get_assessment(repo_url, session_id)` → cached result | `mcp/tools/assessment.py` | Hard gate enforcement in MCP, budget control, caching per SHA |
| 7.5 | MCP tools — Ranking & Explainability | Tool `rank_repos(domain, min_confidence, min_value_score, max_results, session_id)` → ranking intra-dominio, Tool `explain_repo(repo_url, detail_level, session_id)` → explainability summary-first, Tool `compare_repos(repo_urls, dimensions, session_id)` → confronto side-by-side | `mcp/tools/ranking.py` | Output context-efficient, detail_level controllabile |
| 7.6 | MCP tools — Session Management | Tool `create_session(name, config_overrides)` → session_id, Tool `get_session(session_id)` → stato sessione con progress, Tool `list_sessions(status, limit)` → sessioni attive, Tool `export_session(session_id, format)` → export JSON/CSV/Markdown | `mcp/tools/session.py` | Sessione persistente cross-invocazione, progressive deepening cross-sessione |
| 7.7 | MCP resources | Resource `repo://{owner}/{name}/score` → score di un repo, Resource `pool://{id}/candidates` → candidati di un pool, Resource `rank://{domain}/top` → ranking top per dominio, Resource `session://{id}/status` → stato sessione | `mcp/resources/` | Risorse accessibili via protocollo MCP, parsable da agent |
| 7.8 | MCP prompts come agent skill definitions | Prompt `discover_underrated` (workflow completo 5-step), Prompt `quick_quality_check` (rapido check singolo repo), Prompt `compare_for_adoption` (confronto multi-repo per decisione), Prompt `domain_deep_dive` (esplorazione dominio), Prompt `security_audit` (assessment security-first) | `mcp/prompts.py` | Prompt invocabili da client MCP, guidano workflow multi-step |
| 7.9 | GitHub MCP Server composition | Client verso GitHub MCP ufficiale per operazioni standard (repos, issues, PR), toolset ridotto (`repos,issues,pull_requests,context`), `X-MCP-Readonly: true` in analisi, configurazione composizionale in `.kilo/mcp.json` template | `mcp/github_client.py` | Delega operazioni GitHub standard al MCP ufficiale, non duplicazione |
| 7.10 | Progress notifications & streaming | Implementazione `send_progress_notification` per operazioni lunghe: discovery (candidati per canale), screening (repo processati/totali), deep assessment (repo completati, token usati, budget rimanente). Format compatibile con MCP spec | `mcp/progress.py` | Progress notifications ricevute da client MCP di test |
| 7.11 | Context-efficient output design | Ogni tool restituisce summary-first (top 5-10 risultati + reference per dettaglio on-demand), structured content MCP (JSON parsable) con fallback testo, confidence indicators per ogni risultato, reference-based output (pool_id, session_id, repo_url instead of full data) | `mcp/output_format.py` | Output context-efficient verificato: < 2000 token per invocazione di default |
| 7.12 | Transport & security composizionale | Transport stdio per integrazione Kilocode CLI, streamable-http per deployment, read-only mode di default, lockdown-mode opzionale, configurazione per composizione con GitHub MCP in stesso client | `mcp/transport.py` | Entrambi i transport funzionanti, composizione con GitHub MCP verificata |
| 7.13 | MCP configuration per ambiente | Configurazione via `GHDISC_MCP_*` env variables, toolset selezionabile, exclude-tools support, session backend (sqlite per locale, redis per deployment), configurazione per Kilocode/Kilo Code, OpenCode, Claude Code | `mcp/config.py` | Configurazione dinamica funzionante per multi-ambiente |

**Checkpoint Phase 7**: MCP-native primary interface operativo con tools granulari per-gate (progressive deepening), prompts come skill definitions, session management, progress notifications, context-efficient output, composizione con GitHub MCP verificata.

---

### Phase 8 — CLI

**Obiettivo**: Implementare l'interfaccia CLI per batch processing, automazione CI e uso interattivo.

**Durata**: 1-2 settimane

| Task ID | Task | Dettaglio | Output | Verifica |
|---------|------|-----------|--------|----------|
| 8.1 | CLI framework setup | `typer` con subcomandi, help completo, opzioni globali (verbose, config-file, output-format), `__main__.py` entry point | `cli/app.py` | `python -m github_discovery --help` funziona |
| 8.2 | Comando `discover` | `ghdisc discover --query "static analysis python" --channels search,registry --max 500` → avvia discovery, mostra progress | `cli/discover.py` | Discovery da CLI con output formattato |
| 8.3 | Comando `screen` | `ghdisc screen --pool-id X --gate 1 --gate 2` → avvia screening, mostra pass/fail | `cli/screen.py` | Screening da CLI con output tabellare |
| 8.4 | Comando `deep-eval` | `ghdisc deep-eval --pool-id X --max-repos 50 --budget-tokens 100000` → avvia deep assessment, hard gate enforcement | `cli/deep_eval.py` | Deep eval da CLI con budget control |
| 8.5 | Comando `rank` | `ghdisc rank --domain library --top 20 --output table` → mostra ranking, explainability opzionale | `cli/rank.py` | Ranking formattato da CLI |
| 8.6 | Comando `export` | `ghdisc export --format json --output results.json` → esporta risultati | `cli/export.py` | Export JSON/CSV/Markdown |
| 8.7 | Output formatting | Formattatori per: JSON, tabella (rich/textual), Markdown, YAML. Supporto pipe e redirect | `cli/formatters.py` | Output leggibile per ogni formato |
| 8.8 | Comando `mcp serve` | `ghdisc mcp serve --transport stdio` / `--transport http --port 8080` → avvia MCP server | `cli/mcp_serve.py` | MCP server avviabile da CLI |
| 8.9 | Comandi sessione agentica | `ghdisc session create --name "ml-search"`, `ghdisc session list`, `ghdisc session resume <id>` → gestione sessioni per uso agentico interattivo | `cli/session.py` | Sessione creabile e riprendibile da CLI |
| 8.10 | CLI composizione MCP config | `ghdisc mcp init-config --target kilo|opencode|claude` → genera configurazione MCP per target agentico specifico, include github-discovery + GitHub MCP composition | `cli/mcp_config.py` | Config generata funzionante per almeno Kilocode CLI |
| 8.11 | CLI streaming output | Supporto `--stream` per comandi lunghi (discover, screen, deep-eval): output progressivo con indicatore di avanzamento, risultati parziali a terminale | `cli/progress_display.py` | Streaming visibile in terminale per operazioni lunghe |

**Checkpoint Phase 8**: CLI completamente operativa con 6 comandi principali + MCP serve + session management + streaming output + MCP config generator, entry point `python -m github_discovery`.

---

### Phase 9 — Integration Testing & Feasibility Validation

**Obiettivo**: Validare l'intero sistema con l'esperimento di fattibilità (Sprint 0 del blueprint): dimostrare che il sistema trova repo migliori del baseline star-based su un campione reale.

**Durata**: 2-3 settimane

| Task ID | Task | Dettaglio | Output | Verifica |
|---------|------|-----------|--------|----------|
| 9.1 | Sprint 0 — Mini-pipeline su 500-1000 repo | Pipeline completa Gate 0→1→2→3 su pool reale di 500-1000 candidati, diverse query e domini | Dataset scored | Pipeline completa senza errori su volume reale |
| 9.2 | Baseline metadata score | Calcolo baseline score senza LLM (solo Gate 1+2), confronto con ranking per stelle | Report baseline vs star-ranking | Hidden gems identificati dal metadata score |
| 9.3 | Deep-scan top 10-15% | Deep assessment (Gate 3) solo su top percentile dal Gate 2, rispetto budget LLM | Risultati deep assessment | Budget LLM rispettato, qualità deep assessment |
| 9.4 | Star-based baseline comparison | Ranking per stelle vs ranking GitHub Discovery, overlap analysis, divergenze | Report comparativo | GitHub Discovery trova repo che star-ranking non vede |
| 9.5 | Blind human evaluation | Valutazione umana su campione (20-30 repo) senza indicazione della fonte di ranking, rating di qualità tecnica | Dataset valutazione umana | Correlazione positiva tra ranking GD e valutazione umana |
| 9.6 | Precision@K measurement | Misurare Precision@5, Precision@10, Precision@20 su "hidden gems" (basse stelle, alta qualità tecnica) | Report precision@k | Precision@10 > baseline star-based |
| 9.7 | Weight tuning & calibration | Aggiustamento pesi dimensioni per dominio basato su risultati Sprint 0, domain-specific calibration | Pesi calibrati | Miglioramento precision rispetto a pesi default |
| 9.8 | End-to-end integration tests | Test integrazione completi: CLI → API → Workers → Discovery → Screening → Assessment → Scoring → Export, con mock esterni dove necessario | Test suite integration | Coverage >80% su screening/scoring, integration tests verdi |
| 9.9 | Agentic integration tests | Test MCP tools con client MCP reale: progressive deepening (Gate 1 → decide → Gate 2 → decide → Gate 3), session cross-invocazione, progress notifications, context-efficient output, composizione con GitHub MCP | Test suite agentic | Ogni workflow agentico del Blueprint §21.7 testato end-to-end |
| 9.10 | Kilocode CLI integration test | Test effettivo con Kilocode CLI: configurazione `kilo.json`, agent chiama tool discovery, workflow multi-step con session_id, permission system (allow/ask/deny) | Test report Kilocode | Almeno 1 workflow completo eseguito via Kilocode CLI |
| 9.11 | OpenCode integration test | Test effettivo con OpenCode: configurazione `opencode.jsonc`, agent chiama tool discovery, workflow con plan/build/review modes | Test report OpenCode | Almeno 1 workflow completo eseguito via OpenCode |

**Checkpoint Phase 9 (CRITICO)**: Dimostrazione che GitHub Discovery trova repo tecnicamente migliori del baseline star-based. Precision@K misurata. Pesì calibrati. Integrazione agentica verificata con almeno 2 client (Kilocode CLI + OpenCode). Questo è il go/no-go del progetto.

---

### Phase 10 — Alpha Engine & Polish

**Obiettivo**: Stabilizzare il sistema per release alpha, aggiungere packaging, docs, performance optimization.

**Durata**: 2-3 settimane

| Task ID | Task | Dettaglio | Output | Verifica |
|---------|------|-----------|--------|----------|
| 10.1 | Multi-channel discovery validation | Validazione che tutti i canali discovery producono risultati, misurazione coverage per canale | Report coverage discovery | Almeno 3 canali con coverage significativa |
| 10.2 | Scoring explainability review | Review qualità explainability report su campione ampio, miglioramento template se necessario | Explainability v2 | Report leggibili e informativi |
| 10.3 | Output queryability | Verifica che API/CLI/MCP consentano query flessibili (per dominio, range score, query, pool) | Test query complesse | Query con filtri multipli funzionanti |
| 10.4 | MCP endpoint stabilization | Test MCP con client reali (Kilo Code, Cursor, Claude Desktop), fix compatibilità | MCP v1 stabile | Integrazione con almeno 2 client AI |
| 10.5 | Kilo Marketplace packaging | Creare entry Kilo Marketplace con configurazione MCP predefinita, skill / prompt templates, documentazione per agent skill | Marketplace package | `kilo mcp add github-discovery` funzionante |
| 10.6 | OpenCode agent template | Creare template `.config/opencode/agent/discovery.md` con istruzioni per l'agente OpenCode e configurazione MCP predefinita | Agent template | Configurazione OpenCode funzionante |
| 10.7 | Performance optimization | Profiling bottleneck, caching strategy (feature store, API response), lazy loading, parallelizzazione screening | Benchmark performance | Tempo end-to-end misurabile e migliorato |
| 10.8 | Documentation & user guides | README con quickstart, ARCHITECTURE.md, API reference, MCP integration guide (Blueprint §21), CLI usage guide, Kilocode/OpenCode/Claude setup guide | Documentazione completa | Nuovo utente può setuppare e usare in <30 min |
| 10.9 | Docker packaging | `Dockerfile` multi-stage, `docker-compose.yml` (API + workers + MCP), health checks | Container operativi | `docker compose up` → sistema funzionante |
| 10.10 | Alpha release | Tag v0.1.0-alpha, release notes, PyPI package pubblicabile, Kilo Marketplace entry, OpenCode template | Release alpha | Tag + release notes + PyPI package + marketplace entry su GitHub |

**Checkpoint Phase 10**: Sistema alpha-release completo, Docker-izzato, documentato, testato con client AI reali, Kilo Marketplace entry pubblica, PyPI package, OpenCode template.

---

## 4) Milestone & Checkpoint di validazione

| Milestone | Fase | Criterio di successo | HitL |
|-----------|------|---------------------|------|
| **M0 — Foundation Ready** | Phase 0+1 | Progetto installabile, CI verde, modelli Pydantic completi | Sì — approvazione struttura |
| **M1 — Discovery MVP** | Phase 2 | Discovery da 3+ canali, pool di candidati deduplicato | No |
| **M2 — Screening MVP** | Phase 3 | Gate 1+2 operativi, hard gate enforcement, 4+ tool integrati | No |
| **M3 — Deep Assessment MVP** | Phase 4 | Deep scan LLM con budget control, caching SHA | Sì — approvazione cost/budget |
| **M4 — Ranking MVP** | Phase 5 | Anti-star bias funzionante, explainability leggibile | No |
| **M5 — API & Workers** | Phase 6 | API REST + workers asincroni, hard gate in API | Sì — approvazione API surface |
| **M6 — MCP-Native** | Phase 7 | MCP primaria con tools granulari, progressive deepening, session management, composable con GitHub MCP | Sì — approvazione design MCP |
| **M7 — CLI & Agent-Friendly** | Phase 8 | CLI con session management, streaming, MCP config generator | No |
| **M8 — Feasibility Gate (CRITICO)** | Phase 9 | Precision@K > baseline star-based, valutazione umana positiva, agentic integration testata con 2+ client | Sì — go/no-go decision |
| **M9 — Alpha Release & Marketplace** | Phase 10 | Docker, PyPI, docs, Kilo Marketplace, OpenCode template, v0.1.0-alpha tag | Sì — approvazione release |

---

## 5) KPI di avanzamento

Ogni fase traccia questi indicatori:

| KPI | Misura | Target per Alpha |
|-----|--------|-----------------|
| **Code coverage** | % linee coperte da test | >80% su screening/scoring |
| **Type safety** | mypy --strict error count | 0 |
| **Lint compliance** | ruff check error count | 0 |
| **Pipeline latency** | Tempo end-to-end per repo (Gate 0→3) | <5 min media (Gate 1+2), <15 min (Gate 3) |
| **LLM cost per repo** | Token consumati per deep assessment | <50k token/repo media |
| **Discovery coverage** | Repo unici scoperti per query | >100 per canale attivo |
| **Screening precision** | % repo Gate 1+2 pass che meritano deep scan | Da calibrare in Phase 9 |
| **Hidden gem precision@10** | % top-10 che sono tecnicamente ottimi e sottovisibili | > baseline star-based |
| **Ranking stability** | Variazione ranking tra run identiche | <5% posizione media |
| **Explainability completeness** | % dimensioni con explanation + evidence | >90% per repo deep-assessed |
| **MCP tool context efficiency** | Token medi per invocazione tool MCP di default | <2000 token/invocazione |
| **Progressive deepening adoption** | % workflow agentici che usano granular gate-by-gate vs monolithico | >50% granular |
| **Session resume rate** | % sessioni riprese cross-invocazione | >30% (indica uso reale) |
| **MCP composition success** | % workflow che compongono github-discovery + GitHub MCP tools | Misurabile in Phase 9 |

---

## 6) Rischi per fase

| Fase | Rischio | Impatto | Mitigazione |
|------|---------|---------|-------------|
| Phase 2 | Rate limit GitHub API su discovery bulk | Alto — discovery bloccata | Throttling rigoroso, caching, GraphQL per ridurre chiamate, conditional requests |
| Phase 2 | Bias residuo nei canali discovery (es. Search API popolarità-influenced) | Medio — pool iniziale distorto | Combinare 3+ canali con diverso bias, canali curatoriali come controbilancio |
| Phase 3 | Tool esterni non disponibili o rotti (gitleaks, scc, Scorecard) | Medio — screening incompleto | Fallback a euristiche proprie, graceful degradation, mock per test |
| Phase 4 | Costo LLM fuori controllo su deep scan | Alto — budget overflow | Budget controller hard limits, early-stop, caching SHA, top percentile solo |
| Phase 4 | Qualità risposta LLM variabile | Medio — scoring inconsistente | Prompt template testati, structured output, validation Pydantic, confidence score |
| Phase 5 | Pesi dimensione non calibrati correttamente | Alto — ranking non significativo | Sprint 0 calibration, domain-specific tuning, human evaluation |
| Phase 6 | Worker deadlock o memory leak su run lunghe | Medio — pipeline non completa | Timeout, isolation, health checks, restart policy |
| Phase 7 | MCP protocollo instabile o cambiamenti breaking | Basso — integrazione fragile | Pin SDK version, test con client reali, abstract layer |
| Phase 7 | Context overflow per tool MCP troppo verbosi | Medio — agent dismiss tool per limite contesto | Context-efficient design (summary-first, reference-based, detail on-demand) |
| Phase 7 | Composizione con GitHub MCP Server non funzionante | Medio — agent non può usare tool di scoperta + GitHub insieme | Test integrazione con multi-MCP, configurazione composizionale documentata |
| Phase 8 | CLI session management non robusto per uso agentico | Basso — sessioni perdute o corrotte | SQLite backend testato, fallback in-memory, session recovery |
| Phase 9 | Client MCP (Kilocode/OpenCode) non supportano progress notifications | Basso — agent non ricevere aggiornamenti progressivi | Fallback a polling (tool `get_session`), documentation per client senza streaming |
| Phase 9 | Precision@K non supera baseline | Critico — progetto non dimostra valore | Tuning pesi, aggiungere feature, cambiare soglie, valutare se il gap è nel concetto |
| Phase 10 | Performance inaccettabile su volume reale | Medio — non usabile in produzione | Profiling, caching, lazy loading, parallelizzazione |

---

## 7) Stack tecnologico verificato

Verifica tramite Context7 (documentazione ufficiale aggiornata al 2026-04):

| Componente | Libreria/Tool | Versione riferimento | Fonte verifica |
|-----------|---------------|---------------------|----------------|
| **Web framework** | FastAPI | 0.128+ | Context7: `/fastapi/fastapi` — async, DI, OpenAPI auto-docs |
| **Data models** | Pydantic v2 | 2.x | Context7: `/websites/pydantic_dev_validation` — BaseModel, validators, JSON schema |
| **Settings** | pydantic-settings | 2.x | Context7: `/pydantic/pydantic-settings` — BaseSettings, env_prefix, nested delimiter |
| **Async HTTP** | httpx | 0.28+ | Context7: `/encode/httpx` — AsyncClient, retry transport, HTTP/2 |
| **HTTP mocking (test)** | pytest-httpx / respx | Latest | Context7: `/colin-b/pytest_httpx` — fixture mocking httpx |
| **Git analysis** | PyDriller | 2.x | Context7: `/websites/pydriller_readthedocs_io_en` — commit mining, code churn, contributors |
| **MCP SDK** | mcp (Python) | 1.x | Context7: `/modelcontextprotocol/python-sdk` — FastMCP, tools, resources, prompts, progress notifications, structured content |
| **MCP Apps SDK** | @modelcontextprotocol/ext-apps | 1.x | Context7: `/modelcontextprotocol/ext-apps` — Interactive UI, tool+resource linking, CSP metadata |
| **GitHub MCP** | github-mcp-server | Latest | Context7: `/github/github-mcp-server` — toolsets, read-only, dynamic-toolsets, lockdown |
| **CLI** | typer | 0.12+ | Comunità — subcomandi, help auto, type hints |
| **Logging** | structlog | 24.x | Comunità — JSON structured logging, processors |
| **Lint/Format** | ruff | 0.11+ | Comunità — lint + format, line-length config |
| **Type check** | mypy | 1.15+ | Comunità — strict mode |
| **Testing** | pytest | 8.x | Comunità — fixtures, markers, async support |
| **Security scan** | OpenSSF Scorecard | v5+ | Comunità — API + CLI |
| **Secret detection** | gitleaks | 8.x | Comunità — SARIF output |
| **Vulnerability scan** | OSV API | v1 | Comunità — query per ecosystem/package/version |
| **Code packing** | Repomix | Latest | Comunità — LLM-oriented repo packing |
| **LOC/Complexity** | scc | Latest | Comunità — fast, JSON output, multi-language |
| **Container** | Docker + compose | Latest | Comunità — multi-stage, health checks |

---

## 8) Regole operative

Ogni fase segue il workflow agentico standard (Blueprint §17.2):

```
Explore → Plan → Implement → Verify → Review → Ship
```

### Principi obbligatori per ogni task

1. **Context7-first**: Prima di usare qualsiasi libreria, verificare documentazione ufficiale via Context7.
2. **Verify before complete**: Un task è completato solo quando i criteri di verifica della tabella sono soddisfatti.
3. **Hard gates**: Gate 1+2 sono hard constraint — nessun deep-scan senza passaggio completo.
4. **Anti-star bias**: Stars sono contesto, mai criterio primario di ranking.
5. **Explainability**: Ogni score deve essere spiegabile per feature e dimensione.
6. **Cost awareness**: Budget LLM è requisito architetturale, non ottimizzazione.
7. **Reuse over rebuild**: Integrare tool ufficiali esistenti prima di estendere.
8. **No silent failures**: Errori loggati con contesto e retry strategy.
9. **MCP-First design (Blueprint §21)**: MCP è l'interfaccia primaria, API è consumer secondario. Ogni feature deve essere accessibile via MCP tool prima di essere accessibile via API endpoint.
10. **Progressive deepening (Blueprint §21)**: I tool MCP devono essere granulari e composable — ogni gate è invocabile singolarmente, l'agente ordestra il flusso.
11. **Context-efficient output (Blueprint §21)**: Output MCP summary-first per default, dettaglio on-demand. Limitare output tool a < 2000 token per invocazione di default.
12. **Session-aware (Blueprint §21)**: Ogni tool MCP supporta session_id per workflow cross-sessione e progressive deepening.

### Prossimi passi

Per ogni fase, prima dell'implementazione, verrà elaborato un **piano di implementazione dettagliato** che include:
- Architettura specifica dei moduli
- Sequenza di implementazione dei task
- Test plan per ogni task
- Criteri di accettazione misurabili
- Dipendenze e blocchi potenziali

---

*Stato documento: Draft Roadmap v1 — aggiornato con integrazione agentica MCP-native (Giugno 2026)*
*Data: 2026-04-22 (originale), 2026-06-XX (estensione agentic integration)*
*Basato su: github-discovery_foundation_blueprint.md v1 + §21 Agentic Integration Architecture*
