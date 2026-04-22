---
Title: MCP-Native Agentic Integration Architecture
Topic: architecture
Sources: Foundation Blueprint §21; Roadmap Phase 7
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md)
Updated: 2026-04-22
Confidence: high
---

# MCP-Native Agentic Integration Architecture

GitHub Discovery is designed as a **MCP-native agentic system**, not a standalone app with an MCP facade. MCP (Model Context Protocol) is the primary interface; the REST API is a secondary consumer of the same core services.

## Key Points

- **MCP is the primary interface** — Agents interact via MCP tools, resources, and prompts. REST API consumes the same services.
- **Progressive Deepening** — Every gate is an independent MCP tool. The agent decides when to deepen, not the pipeline.
- **Agent-Driven Policy** — Gating thresholds are tool parameters, not hardcoded constants. Agents configure `min_gate1_score=0.6` for quick checks or `0.3` for deep exploration.
- **Session-Aware** — Operations support `session_id` for cross-session workflow continuity. An agent can discover in session 1, screen in session 2, assess in session 3.
- **Context-Efficient** — Tools return summary-first output (< 2000 tokens default) with on-demand detail via dedicated tools.
- **Composable with GitHub MCP** — No duplication of GitHub functionality. Discovery adds only scoring/ranking.

## Design Principles (Blueprint §21.2)

1. **MCP-First**: MCP tools/resources/prompts are the primary interface. API is secondary.
2. **Progressive Deepening**: Each gate is an independent MCP tool. Linear flow is just one possible workflow.
3. **Agent-Driven Policy**: Thresholds are tool parameters, not hardcoded.
4. **Session-Aware**: `session_id` enables cross-session progressive deepening.
5. **Streaming & Progress**: Long operations emit MCP progress notifications with partial results.
6. **Compositional Tool Design**: Tools compose into multi-step workflows or use pre-defined prompt skills.
7. **Context-Efficient**: Summary-first default, detail on-demand. References (pool_id, session_id, repo_url) instead of full data.

## MCP Tool Design

### Discovery (Layer A)

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `discover_repos` | Find candidate repos | `query`, `channels`, `max_candidates`, `session_id` |
| `get_candidate_pool` | Filter/sort candidate pool | `pool_id`, `filters`, `sort_by`, `limit` |
| `expand_seeds` | Expand from seed URLs | `seed_urls`, `expansion_strategy`, `max_depth`, `session_id` |

### Screening (Layer B)

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `screen_candidates` | Gate 1+2 screening | `pool_id`, `gate_level`, `min_gate1_score`, `min_gate2_score`, `session_id` |
| `get_shortlist` | Get passed candidates | `pool_id`, `min_score`, `domain`, `limit` |
| `quick_screen` | Single repo quick check | `repo_url`, `gate_levels` |

### Assessment (Layer C)

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `deep_assess` | LLM deep assessment | `repo_urls`, `dimensions`, `budget_tokens`, `session_id` |
| `quick_assess` | Subset dimension assessment | `repo_url`, `dimensions` |
| `get_assessment` | Get cached assessment | `repo_url`, `session_id` |

### Scoring & Ranking (Layer D)

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `rank_repos` | Anti-star bias ranking | `domain`, `min_confidence`, `min_value_score`, `max_results`, `session_id` |
| `explain_repo` | Explainability report | `repo_url`, `detail_level`, `session_id` |
| `compare_repos` | Side-by-side comparison | `repo_urls`, `dimensions`, `session_id` |

### Session Management

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `create_session` | Start discovery session | `name`, `config_overrides` |
| `get_session` | Get session state | `session_id` |
| `list_sessions` | List active/completed sessions | `status`, `limit` |
| `export_session` | Export session results | `session_id`, `format` |

## MCP Prompt Skills (Agent Workflows)

| Skill | Description | Steps |
|-------|-------------|-------|
| `discover_underrated` | Find technically excellent underrated repos | Discover → Screen → Deep assess → Rank → Explain |
| `quick_quality_check` | Quick quality check on a repo | Quick screen → Report |
| `compare_for_adoption` | Compare repos for adoption decision | Screen → Quick assess → Compare |
| `domain_deep_dive` | Deep exploration of a domain | Discover → Screen → Deep assess → Domain rank |
| `security_audit` | Security-first assessment | Screen (Gate 2 heavy) → Security assess → Report |

## Composition with GitHub MCP Server

GitHub Discovery operates **in composition** with the official GitHub MCP Server, not replacement:

1. GitHub MCP → standard operations (repo browse, issue management, PR review, code search)
2. GitHub Discovery MCP → discovery, screening, assessment, ranking
3. Agent combines both → discover underrated repos, then deep-dive into issues/PRs

### Configuration Example (Kilocode CLI)

```json
{
  "mcp": {
    "github": {
      "type": "remote",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": {
        "X-MCP-Toolsets": "repos,issues,pull_requests,context",
        "X-MCP-Readonly": "true"
      }
    },
    "github-discovery": {
      "type": "local",
      "command": ["python", "-m", "github_discovery.mcp", "serve", "--transport", "stdio"],
      "environment": {
        "GHDISC_GITHUB_TOKEN": "{env:GITHUB_TOKEN}",
        "GHDISC_SESSION_BACKEND": "sqlite"
      }
    }
  }
}
```

## Context-Efficient Output Design

Every MCP tool returns summary-first by default:

```json
{
  "pool_id": "pool-abc123",
  "total_candidates": 500,
  "gate1_passed": 87,
  "gate2_passed": 23,
  "shortlist_top_5": [
    {"repo": "user/repo1", "gate1_score": 0.89, "gate2_score": 0.82, "discovery_score": 0.75}
  ],
  "session_id": "session-xyz789",
  "detail_available_via": "get_shortlist(pool_id='pool-abc123', limit=50)"
}
```

## See Also

- [Tiered Pipeline](tiered-pipeline.md)
- [Session & Workflow Patterns](../patterns/session-workflow.md)
- [MCP Tool Specs](../apis/mcp-tools.md)
- [Tech Stack Decisions](../patterns/tech-stack.md)