---
Title: Operational Rules and Workflow Standards
Topic: patterns
Sources: Foundation Blueprint §17; Roadmap §8
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md)
Updated: 2026-04-22
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
- **Cost awareness**: LLM budget is an architectural requirement, not an optimization
- **MCP-First**: Every feature accessible via MCP tool before API endpoint
- **Progressive deepening**: MCP tools are granular and composable
- **Context efficiency**: Default < 2000 tokens per MCP tool invocation
- **Session-aware**: Every MCP tool supports `session_id`

## Error Handling Standards

- Custom exception hierarchy: `GitHubDiscoveryError` → `DiscoveryError`, `ScreeningError`, `AssessmentError`, `ScoringError`, `ConfigurationError`
- Structured error results over exceptions for expected failures (e.g., repo not scorable)
- `structlog` for structured JSON logging — never `print()` for diagnostics
- Always include context in error messages (repo URL, dimension, gate level)

## See Also

- [Agent Workflow Patterns](agent-workflows.md)
- [Tiered Pipeline](../architecture/tiered-pipeline.md)