# Knowledge Base Index

<!-- AUTO-GENERATED: This index is maintained by the LLM. Do not edit manually unless fixing errors. -->
<!-- Format: - [Title](path) — one-line summary | Updated: YYYY-MM-DD -->

## Architecture

- [Tiered Scoring Pipeline](architecture/tiered-pipeline.md) — 4-gate progressive pipeline: discovery → metadata screening → static/security screening → LLM deep assessment → ranking. Coverage damping, derivation map, confidence per dimension, error handling (Fase 2) | Updated: 2026-04-26
- [MCP-Native Agentic Integration Architecture](architecture/mcp-native-design.md) — MCP-first design principles, progressive deepening, session-aware tools, agent workflows | Updated: 2026-04-22
- [Star-Neutral Quality Scoring](architecture/anti-star-bias.md) — Star-neutral design: value_score = quality_score, corroboration levels, hidden gem as informational label (ScoringSettings single-source), quality-first ranking, deterministic blake2b tie-breaking | Updated: 2026-04-26
- [Option C Hybrid Architecture Decision](architecture/option-c-hybrid.md) — Architecture decision: API+Worker+MCP native+CLI hybrid, now evolved to MCP-native | Updated: 2026-04-22
- [Architecture Analysis — Complete System Overview](architecture/architecture-analysis.md) — Comprehensive architecture analysis (v0.1.0-alpha): 4-gate pipeline detail, star-neutral scoring, 107-file codebase structure, 1326 tests, data flow, database architecture, error patterns | Updated: 2026-04-26
- [Phase 2 Audit Remediation — Decision Log](architecture/phase2-remediation.md) — Post-audit remediation decisions: Waves 0–3+5 complete (1587 tests), Wave 4 infrastructure ready, key decisions on derivation map, coverage damping, deterministic ranking, custom profiles | Updated: 2026-04-26

## APIs

- [MCP Tool Specifications](apis/mcp-tools.md) — Complete specification of all MCP tools: discovery, screening, assessment, ranking, session management | Updated: 2026-04-22
- [MCP Python SDK Verification](apis/mcp-sdk-verification.md) — Context7-verified MCP Python SDK API patterns: FastMCP, tools, resources, Context, progress notifications, transports | Updated: 2026-04-22
- [GitHub API Patterns and Constraints](apis/github-api-patterns.md) — REST/GraphQL API usage patterns, rate limits with exponential backoff retry, pagination, MCP composition | Updated: 2026-04-25
- [Agenti di Coding — Integrazione MCP](apis/agent-integration.md) — Complete MCP integration guide for Claude Code, Kilocode CLI/Kilo Code, and OpenCode: Context7+Brave verified config formats, .mcp.json and .kilo/mcp.json files, env var syntax differences, platform comparison table, best practices | Updated: 2026-04-26

## Domain

- [Scoring Dimensions and Weight Profiles](domain/scoring-dimensions.md) — 8 evaluation dimensions, domain-dependent weights, confidence scores, star-neutral value score, corroboration levels, hidden gem label (ScoringSettings single-source), derivation map, per-dimension confidence caps, coverage damping, per-profile derivation maps (T5.1), custom YAML/TOML profiles (T5.3) | Updated: 2026-04-26
- [Discovery Channels and Strategies](domain/discovery-channels.md) — 6 discovery channels: Search, Code Search, Dependency, Registry, Awesome Lists, Seed Expansion. CuratedChannel: no mega-list fallback, topic matching, 50 candidate cap | Updated: 2026-04-27
- [Screening Gates Detail](domain/screening-gates.md) — Gate 1 metadata sub-scores, Gate 2 static/security sub-scores, degraded-mode handling, typed fetch errors, hard gate enforcement, scorecard fallback aligned (0.3), MCP hard gate per-tool (Gate 1 for deep_assess, Gate 1+2 for quick_assess) | Updated: 2026-04-27
- [Competitive Landscape and Gap Analysis](domain/competitive-landscape.md) — Existing projects (github_repo_classifier, CHAOSS, OpenSSF, etc.) and the gap GitHub Discovery fills | Updated: 2026-04-22
- [Domain Strategy and Repository Taxonomy](domain/domain-strategy.md) — 12 domain types, domain-specific weights, thresholds, star baselines, per-profile derivation maps, custom YAML/TOML profiles, ghdisc profiles CLI | Updated: 2026-04-26

## Patterns

- [Session Workflow and Progressive Deepening](patterns/session-workflow.md) — Cross-session progressive deepening, session state, context compaction, progress notifications | Updated: 2026-04-22
- [Agent Workflow Patterns](patterns/agent-workflows.md) — MCP prompt skills, standard agent workflow, CLI patterns, permission/security models | Updated: 2026-04-22
- [Technology Stack Decisions](patterns/tech-stack.md) — Verified tech stack (Python 3.12+, FastAPI, Pydantic v2, httpx, MCP SDK), integrations, coding conventions | Updated: 2026-04-22
- [Operational Rules and Workflow Standards](patterns/operational-rules.md) — Guiding principles, hard architecture constraints, error handling standards, and retry/backoff policy | Updated: 2026-04-27
- [Phase 0 Implementation Decisions](patterns/phase0-implementation.md) — Detailed implementation decisions for Phase 0: config architecture, exception hierarchy, session models, MCP spec models, logging, ruff/mypy/pytest configuration | Updated: 2026-04-22
- [Python Development Tooling Configuration](patterns/dev-tooling-and-ci.md) — Context7-verified configurations for pydantic-settings, structlog, ruff, pytest, pre-commit, mypy | Updated: 2026-04-22
- [MCP Server Environment Isolation Resilience](patterns/env-isolation-resilience.md) — Fix for pydantic-settings crash when MCP server is spawned from a foreign project directory with its own .env: extra='ignore' on all SettingsConfigDict, structlog None-logger safety, CWD-independent data paths | Updated: 2026-04-26
- [Phase 1 Data Models Implementation Decisions](patterns/phase1-models-implementation.md) — Detailed implementation decisions for Phase 1: ScoreDimension realignment, SubScore pattern, RepoCandidate, ValueScore computed_field, Feature Store SHA dedup, MCPToolResult context-efficient design | Updated: 2026-04-22
- [Phase 2 Discovery Engine Implementation](patterns/phase2-discovery-plan.md) — Discovery Engine (Layer A) COMPLETE: REST/GraphQL clients, 6 discovery channels, orchestrator with scoring/dedup, SQLite pool manager, 320 tests | Updated: 2026-04-22
- [Phase 3 Screening Implementation](patterns/phase3-screening-implementation.md) — Lightweight Quality Screening (Layer B) COMPLETE + VERIFIED: Gate 1 (7 metadata sub-scores) + Gate 2 (4 static/security sub-scores) + Policy Engine + hard gate enforcement + clone management + OSV API integration + 500 total tests | Updated: 2026-04-23
- [Phase 4 Deep Assessment Implementation](patterns/phase4-assessment-implementation.md) — Deep Technical Assessment (Layer C) COMPLETE + VERIFIED: NanoGPT provider (instructor+openai), repomix packing, 8 dimension prompts with domain focus, cache TTL enforcement, soft budget controller (100k per-repo hard, 2M daily soft), heuristic fallback, lang_analyzers, 230 assessment tests (863 total) | Updated: 2026-04-27
- [Phase 5 Scoring & Ranking Implementation](patterns/phase5-scoring-implementation.md) — Scoring & Ranking (Layer D) COMPLETE + STAR-NEUTRAL REDESIGN + FASE 2 AUDIT REMEDIATION: ScoringEngine, 12 domain profiles, star-neutral ValueScoreCalculator, ConfidenceCalculator (weighted+penalty), Ranker (quality DESC, deterministic blake2b), FeatureStore (SQLite), HeuristicFallback, per-profile derivation maps (T5.1), custom YAML/TOML profiles (T5.3), 1587 total tests | Updated: 2026-04-26
- [Phase 6 API & Worker Implementation](patterns/phase6-api-worker-plan.md) — API & Worker Infrastructure COMPLETE + VERIFIED: FastAPI app factory + lifespan, SQLite JobStore, AsyncTaskQueue, 3 worker types, 5 route groups, rate limiting + API key auth, OpenAPI docs, export (JSON/CSV/MD), 127 new tests (990 total) | Updated: 2026-04-23
- [Phase 7 MCP Integration Implementation](patterns/phase7-mcp-plan.md) — MCP-Native Integration Layer COMPLETE + VERIFIED: FastMCP server (16 tools, 4 resources, 5 prompts), SessionManager (SQLite), CLI integration, progress notifications, context-efficient output, GitHub MCP composition, stdio+HTTP transports, 124 new MCP tests (1114 total) | Updated: 2026-04-23
- [Phase 8 CLI Implementation Plan](patterns/phase8-cli-plan.md) — CLI (Batch + Agent-Friendly) COMPLETE + VERIFIED: typer app refactor to cli/ package, 6 pipeline commands, Rich output formatting (4 formats), streaming progress, session management, 82 new CLI tests (1199 total) | Updated: 2026-04-24
- [Phase 9 Integration Testing & Feasibility Validation](patterns/phase9-feasibility-plan.md) — COMPLETE + VERIFIED: feasibility module (sprint0, baseline, metrics, calibration), 113 new tests (1314 total), E2E pipeline + API integration, agentic MCP client integration, Precision@K + NDCG + MRR metrics, star-based baseline comparison, weight calibration | Updated: 2026-04-24
- [Phase 10 Alpha Engine & Marketplace Analysis](patterns/phase10-alpha-analysis.md) — ANALYSIS + SMOKE TEST VERIFIED + STAR-NEUTRAL REDESIGN: Phase 10 strategy, Kilo Marketplace format, deployment model, smoke test results, real E2E validation with 20 MCP office repos, Gate 3 deep assessment verified | Updated: 2026-04-25
- [Kilo Marketplace MCP Server Deployment Model](patterns/marketplace-deployment.md) — Kilo Marketplace structure (Skills/MCP Servers/Modes), MCP.yaml format, UVX/Docker/HTTP install options, PR submission process, Kilo Code + OpenCode + Claude Desktop configuration patterns | Updated: 2026-04-24
