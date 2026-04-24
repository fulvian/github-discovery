# Knowledge Base Index

<!-- AUTO-GENERATED: This index is maintained by the LLM. Do not edit manually unless fixing errors. -->
<!-- Format: - [Title](path) — one-line summary | Updated: YYYY-MM-DD -->

## Architecture

- [Tiered Scoring Pipeline](architecture/tiered-pipeline.md) — 4-gate progressive pipeline: discovery → metadata screening → static/security screening → LLM deep assessment → ranking | Updated: 2026-04-22
- [MCP-Native Agentic Integration Architecture](architecture/mcp-native-design.md) — MCP-first design principles, progressive deepening, session-aware tools, agent workflows | Updated: 2026-04-22
- [Anti-Star Bias Philosophy](architecture/anti-star-bias.md) — Value Score formula, intra-domain ranking, star independence rationale | Updated: 2026-04-22
- [Option C Hybrid Architecture Decision](architecture/option-c-hybrid.md) — Architecture decision: API+Worker+MCP native+CLI hybrid, now evolved to MCP-native | Updated: 2026-04-22

## APIs

- [MCP Tool Specifications](apis/mcp-tools.md) — Complete specification of all MCP tools: discovery, screening, assessment, ranking, session management | Updated: 2026-04-22
- [GitHub API Patterns and Constraints](apis/github-api-patterns.md) — REST/GraphQL API usage patterns, rate limits, pagination, MCP composition | Updated: 2026-04-22

## Domain

- [Scoring Dimensions and Weight Profiles](domain/scoring-dimensions.md) — 8 evaluation dimensions, domain-dependent weights, confidence scores, Value Score computation | Updated: 2026-04-22
- [Discovery Channels and Strategies](domain/discovery-channels.md) — 6 discovery channels: Search, Code Search, Dependency, Registry, Awesome Lists, Seed Expansion | Updated: 2026-04-22
- [Screening Gates Detail](domain/screening-gates.md) — Gate 1 metadata sub-scores, Gate 2 static/security sub-scores, tool integrations, hard gate enforcement | Updated: 2026-04-22
- [Competitive Landscape and Gap Analysis](domain/competitive-landscape.md) — Existing projects (github_repo_classifier, CHAOSS, OpenSSF, etc.) and the gap GitHub Discovery fills | Updated: 2026-04-22
- [Domain Strategy and Repository Taxonomy](domain/domain-strategy.md) — Domain taxonomy (CLI, web_framework, data_tool, etc.), domain-specific weights and thresholds | Updated: 2026-04-22

## Patterns

- [Session Workflow and Progressive Deepening](patterns/session-workflow.md) — Cross-session progressive deepening, session state, context compaction, progress notifications | Updated: 2026-04-22
- [Agent Workflow Patterns](patterns/agent-workflows.md) — MCP prompt skills, standard agent workflow, CLI patterns, permission/security models | Updated: 2026-04-22
- [Technology Stack Decisions](patterns/tech-stack.md) — Verified tech stack (Python 3.12+, FastAPI, Pydantic v2, httpx, MCP SDK), integrations, coding conventions | Updated: 2026-04-22
- [Operational Rules and Workflow Standards](patterns/operational-rules.md) — Guiding principles, hard architecture constraints, error handling standards | Updated: 2026-04-22
- [Phase 0 Implementation Decisions](patterns/phase0-implementation.md) — Detailed implementation decisions for Phase 0: config architecture, exception hierarchy, session models, MCP spec models, logging, ruff/mypy/pytest configuration | Updated: 2026-04-22
- [Python Development Tooling Configuration](patterns/dev-tooling-and-ci.md) — Context7-verified configurations for pydantic-settings, structlog, ruff, pytest, pre-commit, mypy | Updated: 2026-04-22
- [MCP Python SDK Verification](apis/mcp-sdk-verification.md) — Context7-verified MCP Python SDK API patterns: FastMCP, tools, resources, Context, progress notifications, transports | Updated: 2026-04-22
- [Phase 1 Data Models Implementation Decisions](patterns/phase1-models-implementation.md) — Detailed implementation decisions for Phase 1: ScoreDimension realignment, SubScore pattern, RepoCandidate, ValueScore computed_field, Feature Store SHA dedup, MCPToolResult context-efficient design | Updated: 2026-04-22
- [Phase 2 Discovery Engine Implementation](patterns/phase2-discovery-plan.md) — Discovery Engine (Layer A) COMPLETE: REST/GraphQL clients, 6 discovery channels, orchestrator with scoring/dedup, SQLite pool manager, 320 tests | Updated: 2026-04-22
- [Phase 3 Screening Implementation](patterns/phase3-screening-implementation.md) — Lightweight Quality Screening (Layer B) COMPLETE + VERIFIED: Gate 1 (7 metadata sub-scores) + Gate 2 (4 static/security sub-scores) + Policy Engine + hard gate enforcement + clone management + OSV API integration + 500 total tests | Updated: 2026-04-23
- [Phase 4 Deep Assessment Implementation](patterns/phase4-assessment-implementation.md) — Deep Technical Assessment (Layer C) COMPLETE + VERIFIED: NanoGPT provider (instructor+openai), repomix packing, 8 dimension prompts with domain focus, cache TTL enforcement, budget controller, heuristic fallback, lang_analyzers, 230 assessment tests (863 total) | Updated: 2026-04-23
- [Phase 5 Scoring & Ranking Implementation](patterns/phase5-scoring-implementation.md) — Scoring & Ranking (Layer D) COMPLETE + VERIFIED: ScoringEngine (composite multi-gate + FeatureStore caching), ProfileRegistry (11 domains), ValueScoreCalculator (anti-star bias), ConfidenceCalculator, Ranker (seeded tie-breaking), CrossDomainGuard, ExplainabilityGenerator, FeatureStore (SQLite), 130 scoring tests (863 total) | Updated: 2026-04-23
- [Phase 6 API & Worker Implementation](patterns/phase6-api-worker-plan.md) — API & Worker Infrastructure COMPLETE + VERIFIED: FastAPI app factory + lifespan, SQLite JobStore, AsyncTaskQueue, 3 worker types (Discovery/Screening/Assessment), 5 route groups, rate limiting + API key auth, OpenAPI docs, export (JSON/CSV/MD), 127 new tests (990 total) | Updated: 2026-04-23
- [Phase 7 MCP Integration Implementation](patterns/phase7-mcp-plan.md) — MCP-Native Integration Layer COMPLETE + VERIFIED: FastMCP server (16 tools, 4 resources, 5 prompts), SessionManager (SQLite), CLI integration (mcp serve/init-config), progress notifications, context-efficient output, GitHub MCP composition, stdio+HTTP transports, 124 new MCP tests (1114 total) | Updated: 2026-04-23
- [Phase 8 CLI Implementation Plan](patterns/phase8-cli-plan.md) — CLI (Batch + Agent-Friendly) COMPLETE + VERIFIED: typer app refactor to cli/ package, 6 pipeline commands (discover/screen/deep-eval/rank/export/session), Rich output formatting (4 formats), streaming progress, session management, 82 new CLI tests (1199 total) | Updated: 2026-04-24
- [Phase 9 Integration Testing & Feasibility Validation](patterns/phase9-feasibility-plan.md) — COMPLETE + VERIFIED: feasibility module (sprint0, baseline, metrics, calibration), 113 new tests (1314 total), E2E pipeline + API integration, agentic MCP client integration (Context7-verified ClientSession pattern), Kilocode + OpenCode integration, Precision@K + NDCG + MRR metrics, star-based baseline comparison, weight calibration | Updated: 2026-04-24