---
Title: Agent Workflow Patterns
Topic: patterns
Sources: Foundation Blueprint §21.7, §17; Roadmap Phase 7-9
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md)
Updated: 2026-04-22
Confidence: high
---

# Agent Workflow Patterns

MCP Prompts are not just text templates — they are **skill definitions** that guide agents through structured multi-step workflows. The pattern follows: hooks → skills → plugins → MCP (increasing context cost).

## MCP Prompt Skills (Pre-Defined Workflows)

| Skill Name | Purpose | Steps |
|------------|---------|-------|
| `discover_underrated` | Find technically excellent repos underrated by star count | 1. Discover pool → 2. Screen (Gate 1+2) → 3. Deep assess top candidates → 4. Rank with value_score → 5. Explain top finds |
| `quick_quality_check` | Quick quality check on a specific repository | 1. Quick screen (Gate 1) → 2. Report quality signals |
| `compare_for_adoption` | Compare multiple repos for adoption decision | 1. Screen candidates → 2. Quick assess on key dimensions → 3. Side-by-side comparison |
| `domain_deep_dive` | Deep exploration of a specific domain | 1. Discover in domain → 2. Screen → 3. Deep assess → 4. Domain-specific ranking |
| `security_audit` | Security-first assessment of repositories | 1. Screen (Gate 2 heavy) → 2. Security-focused deep assess → 3. Security report |

## Standard Agent Workflow (Blueprint §17.2)

```
Explore → Plan → Implement → Verify → Review → Ship
```

1. **Explore**: Read-only analysis of context
2. **Plan**: Implementation plan with verification criteria
3. **Implement**: Minimal, iterative changes
4. **Verify**: Test/lint/typecheck/metrics required
5. **Review**: Final check (human or sub-agent)
6. **Ship**: Commit/PR with rationale

## CLI Agent Patterns

### Kilocode CLI
- Interactive sessions for discovery/planning
- `kilo run --auto` for non-interactive pipeline automation
- Agent Manager for orchestrating complex multi-step discovery

### OpenCode CLI
- `opencode run` for automation
- `opencode serve` for headless backend
- `opencode mcp add/list/auth` for MCP management
- Agent modes: `plan` / `build` / `review` with granularity

### Claude Code CLI
- Explore → plan → implement → verify cycle
- `/clear` to separate unrelated tasks
- `claude -p` for non-interactive automation
- `CLAUDE.md` for project-level instructions

## Permission and Security Patterns

### Permission Gating
- Tools configured with `allow/ask/deny` patterns per agent platform
- Discovery tools: default `allow`
- Screening tools: default `allow`
- Deep assessment: default `ask` (budget implications)
- Ranking/explain: default `allow`

### Read-Only Default
- Analysis pipelines default to `read-only` mode
- Write operations only in authorized workflows
- `X-MCP-Readonly: true` header when composing with GitHub MCP

### Subagent Isolation
- Decompose complex tasks into isolated contexts with summary return
- Each subagent uses separate `session_id` for result isolation
- Deterministic checks encoded via hooks/workflows/commands

## Operational Rules (Blueprint §17)

1. **Plan before code** — every non-trivial task starts with explicit plan
2. **Verify before complete** — task not done without verifiable evidence
3. **Reuse over rebuild** — integrate existing tools before extending
4. **Least privilege** — read-only and allowlist for commands/tools
5. **Context discipline** — short sessions, clear scope, reset between unrelated tasks
6. **No silent failures** — errors logged with context and retry strategy

## See Also

- [MCP-Native Design](../architecture/mcp-native-design.md)
- [Session Workflow](session-workflow.md)
- [Operational Rules](operational-rules.md)