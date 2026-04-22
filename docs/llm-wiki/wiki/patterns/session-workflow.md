---
Title: Session Workflow and Progressive Deepening
Topic: patterns
Sources: Foundation Blueprint §21.4-21.6; Roadmap Phase 7
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md)
Updated: 2026-04-22
Confidence: high
---

# Session Workflow and Progressive Deepening

GitHub Discovery supports cross-session progressive deepening: an agent can discover candidates in one session, screen in another, and assess in a third. This is the core workflow pattern for MCP-native agentic integration.

## Key Points

- Every MCP operation can specify `session_id` for state continuity
- Sessions persist results (pools, screening, assessments) in a Feature Store
- Agents decide when to deepen (progressive deepening), not the pipeline
- Context compaction supports long sessions without overflow

## Progressive Deepening Patterns

### Pattern 1: Quick Assessment
```
→ discover_repos(query="static analysis python", max_candidates=50)
→ quick_screen(repo_url) or screen_candidates(gate_level="1")
→ Result: fast quality signal
```

### Pattern 2: Deep Discovery (Progressive Deepening)
```
→ create_session(name="ml-search")
→ discover_repos(query="machine learning framework", session_id=...)
→ screen_candidates(gate_level="both", session_id=...)
→ deep_assess(repo_urls=[...], session_id=...)
→ rank_repos(domain="ml_lib", session_id=...)
→ explain_repo(repo_url=..., detail_level="full")
```

### Pattern 3: Comparison for Adoption
```
→ screen_candidates → quick_assess → compare_repos
→ Result: side-by-side comparison for decision
```

## Session State

```python
class SessionState(BaseModel):
    session_id: str
    name: str
    config: SessionConfig
    status: SessionStatus  # active, completed, abandoned
    created_at: datetime
    updated_at: datetime
    pool_ids: list[str]
    screening_results: dict[str, ScreenResult]
    assessment_results: dict[str, DeepAssessmentResult]
    ranking_results: dict[str, list[RankedRepo]]
```

### Per-Session Configuration

```python
class SessionConfig(BaseModel):
    gate_thresholds: dict[GateLevel, float]  # override defaults
    llm_budget: TokenBudget
    preferred_domains: list[DomainType]
    max_candidates: int
    detail_level: DetailLevel  # summary | full
```

## Context Compaction

For long sessions:
- Intermediate results can be compacted: summary kept, details archived
- References (pool_id, session_id, repo_url) replace full data
- Agents can retrieve detail on-demand via dedicated tools

## Progress Notifications

MCP supports `send_progress_notification` for long operations:

```json
{
  "progress_token": "session-abc123",
  "progress": 42.0,
  "total": 100.0,
  "message": "Screened 42/100 candidates (Gate 1)"
}
```

## Session Backends

| Backend | Use Case | Module |
|---------|----------|--------|
| SQLite (default) | Local development, single-user | `mcp/session.py` |
| Redis | Multi-user deployment | `mcp/session.py` |

Configured via `GHDISC_SESSION_BACKEND` environment variable.

## Agent Integration Models

### Kilocode CLI
- Config in `kilo.json` or `.kilo/kilo.json`
- Permission patterns: `github-discovery_*` in allow/ask/deny
- Kilo Marketplace packaging for distribution
- Agent Manager can orchestrate discovery on separate worktrees

### OpenCode/OpenClaude
- Config in `.config/opencode/` or `opencode.jsonc`
- Agent modes: plan/build/review with discovery workflows as MCP prompts
- Session isolation: each agent uses separate `session_id`

### Claude Code
- Config in `~/.config/claude/` with STDIO server config
- `CLAUDE.md` project-level instructions for discovery workflows
- Permission gating: screening and deep assessment default to `ask`

## See Also

- [MCP-Native Design](../architecture/mcp-native-design.md)
- [MCP Tool Specs](../apis/mcp-tools.md)