---
Title: Operational Rules and Workflow Standards
Topic: patterns
Sources: Foundation Blueprint §17; Roadmap §8
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md)
Updated: 2026-04-27
Confidence: high
---

# Operational Rules and Workflow Standards

The project follows a strict set of operational principles derived from Blueprint §17. These are non-negotiable constraints that guide all development and agent operations.

## Guiding Principles

1. **Plan before code** — Every non-trivial task starts with an explicit plan
2. **Verify before complete** — A task is not done without verifiable evidence
3. **Reuse over rebuild** — Integrate existing official tools before extending
4. **Least privilege by default** — Read-only and allowlist for commands/tools
5. **Context discipline** — Short sessions, clear scope, reset between unrelated tasks
6. **No silent failures** — Errors must be logged with context and retry strategy

## Agent Workflow Standard

```
Explore → Plan → Implement → Verify → Review → Ship
```

| Phase | Description |
|-------|-------------|
| **Explore** | Read-only analysis of context |
| **Plan** | Implementation plan with verification criteria |
| **Implement** | Minimal, iterative changes |
| **Verify** | Test/lint/typecheck/metrics required |
| **Review** | Final check (human or sub-agent) |
| **Ship** | Commit/PR with rationale |

## Cross-Tool Guardrails

- **Permission gating**: Granular `allow/ask/deny` policy per platform
- **Subagent isolation**: Decompose tasks into isolated contexts, summarize on return
- **Deterministic checks**: Encode recurring checks via hooks/workflows/commands
- **No silent failures**: Errors logged with context and explicit retry strategy

## Hard Architecture Constraints

- **Gate enforcement**: Gate 1+2 pass required before Gate 3 deep assessment — implemented as hard constraint
- **Anti-star bias**: Stars are context, never primary ranking signal
- **Explainability**: Every score must be explainable by feature and dimension
- **Cost awareness**: LLM budget uses soft monitoring (2M daily soft limit, warning only) — per-repo hard limit (100k) enforces context window boundary; daily limit never blocks assessment
- **MCP-First**: Every feature accessible via MCP tool before API endpoint
- **Progressive deepening**: MCP tools are granular and composable
- **Context efficiency**: Default < 2000 tokens per MCP tool invocation
- **Session-aware**: Every MCP tool supports `session_id`

## Error Handling Standards

### Custom Exception Hierarchy

```
GitHubDiscoveryError (base)
├── DiscoveryError
├── ScreeningError
│   └── HardGateViolationError
├── AssessmentError
├── ScoringError
├── ConfigurationError
└── GitHubFetchError (Fase 2 Wave 3)
    ├── GitHubAuthError (401/403)
    ├── GitHubRateLimitError (429 — includes retry_after)
    └── GitHubServerError (5xx)
```

### Error Handling Rules

- Structured error results over exceptions for expected failures (e.g., repo not scorable)
- `structlog` for structured JSON logging — never `print()` for diagnostics
- Always include context in error messages (repo URL, dimension, gate level)
- Typed GitHub API errors (`GitHubFetchError` hierarchy) enable differentiated retry behavior
- Non-retryable errors (`GitHubAuthError`, generic 4xx) fail fast with diagnostics

## Retry/Backoff Policy (Fase 2 Wave 3)

- GitHub HTTP failures are mapped to typed exceptions before retry decisions
- Retry is allowed only for transient classes (`GitHubRateLimitError`, `GitHubServerError`)
- Backoff uses exponential jitter with bounded wait; `Retry-After` is honored when provided
- Non-retryable classes (`GitHubAuthError`, generic 4xx) fail fast and propagate explicit diagnostics

## Resource Lifecycle (Fase 2 Wave 3)

- **LLM Provider**: Explicit `AsyncOpenAI` handle with proper `close()`. Supports `async with` context manager. Assessment orchestrator nullifies provider reference after close
- **FeatureStore**: TTL-based expiry with consistent `expires_at` semantics across read/stats/cleanup paths. Legacy rows (pre-migration) fall back to `scored_at` + TTL
- **Clone directories**: Orphan cleanup at MCP server startup (`cleanup_orphan_clones()`) removes stale clones from interrupted runs
- **`ghdisc db prune` CLI**: Manual FeatureStore cleanup with dry-run support

## Production Readiness v1 — Assessment Improvements (2026-04-27)

### Hard Daily Limit (`hard_daily_limit`)

The assessment budget system now enforces a hard daily limit as a true ceiling:

- `AssessmentSettings.hard_daily_limit` (env: `GHDISC_ASSESSMENT_HARD_DAILY_LIMIT`, default=0=disabled)
- When enabled, `BudgetController.check_daily_soft_limit()` first checks hard limit and raises `BudgetExceededError(budget_type="daily_hard")` when exceeded — blocks assessment rather than warn
- Soft limit remains at 2M tokens with warning-only enforcement (does not block)

### Persistent Assessment Cache (FeatureStore cross-session)

`FeatureStore` now persists `DeepAssessmentResult` across sessions:

- `assessment_results` table stores full `DimensionScore` arrays for each repo
- `put_assessment()`, `get_assessment()`, `get_assessment_batch()`, `delete_assessment()`
- `_serialize_assessment_dimensions()` / `_row_to_assessment()` for complete `DimensionScore` serialization
- `AssessmentOrchestrator` accepts `feature_store: FeatureStore | None`; results loaded from persistent store on init
- MCP server passes `feature_store` to orchestrator for cross-session cache continuity

### Content Strategy (Adaptive Token Limits + Degraded Flag)

Adaptive content truncation ensures token budget is never exceeded:

- `ContentStrategy` computes max tokens based on `remaining_budget`, `n_repos`, `repo_sizes`
- `AdaptiveHeuristicChunker` chunk sizes: `target_tokens = max(500, remaining_budget // n_repos)`
- `ContentTruncationHeuristic` detects truncation via content similarity drop (`THRESHOLD=0.70`)
- `HeuristicFallback` uses additive structure scoring (files, avg size, pattern matches) when content is truncated
- `ScoreResult.degraded: bool | None` field signals when scores may be unreliable due to content truncation
  - `ScoringEngine.score()` passes `degraded=assessment.degraded` when building result
  - CLI `rank` command shows `degraded` column to surface score uncertainty

## See Also

- [Agent Workflow Patterns](agent-workflows.md)
- [Tiered Pipeline](../architecture/tiered-pipeline.md)
- [Phase 2 Remediation Decisions](../architecture/phase2-remediation.md)
- [Screening Gates Detail](../domain/screening-gates.md)
