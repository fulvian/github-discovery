---
Title: MCP Tool Specifications
Topic: apis
Sources: Foundation Blueprint §21.3-21.8; Roadmap Phase 7
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md)
Updated: 2026-04-22
Confidence: high
---

# MCP Tool Specifications

Complete specification of all MCP tools exposed by GitHub Discovery. MCP is the primary interface (see [MCP-Native Design](../architecture/mcp-native-design.md)).

## Tool Implementations

**Module structure**: `src/github_discovery/mcp/tools/`

| File | Tools |
|------|-------|
| `discovery.py` | `discover_repos`, `get_candidate_pool`, `expand_seeds` |
| `screening.py` | `screen_candidates`, `get_shortlist`, `quick_screen` |
| `assessment.py` | `deep_assess`, `quick_assess`, `get_assessment` |
| `ranking.py` | `rank_repos`, `explain_repo`, `compare_repos` |
| `session.py` | `create_session`, `get_session`, `list_sessions`, `export_session` |

## Discovery Tools (Layer A)

### `discover_repos`
- **Parameters**: `query: str`, `channels: list[DiscoveryChannel]`, `max_candidates: int`, `session_id: str | None`
- **Output**: Candidate pool with `discovery_score`, reference to `session_id`
- **Progress**: Emits candidate count per channel
- **Note**: Creates or updates session. Agent can resume.

### `get_candidate_pool`
- **Parameters**: `pool_id: str`, `filters: dict | None`, `sort_by: str`, `limit: int`
- **Output**: Paginated candidate list with preliminary scores
- **Note**: On-demand filtering and sorting

### `expand_seeds`
- **Parameters**: `seed_urls: list[str]`, `expansion_strategy: str`, `max_depth: int`, `session_id: str | None`
- **Output**: New candidates from seed expansion
- **Note**: Co-contributor, org adjacency, co-dependency strategies

## Screening Tools (Layer B)

### `screen_candidates`
- **Parameters**: `pool_id: str`, `gate_level: str` ("1" | "2" | "both"), `min_gate1_score: float`, `min_gate2_score: float`, `session_id: str | None`
- **Output**: `ScreenResult` with pass/fail per gate, sub-scores
- **Progress**: Repo processed / total per gate
- **Policy**: Thresholds are tool parameters (agent-driven), not hardcoded

### `get_shortlist`
- **Parameters**: `pool_id: str`, `min_score: float`, `domain: str | None`, `limit: int`
- **Output**: Candidates that passed specified gates
- **Note**: On-demand filtering

### `quick_screen`
- **Parameters**: `repo_url: str`, `gate_levels: str` ("1" | "1,2")
- **Output**: Single repo quick screening result
- **Note**: Fast quality check on a specific repo

## Assessment Tools (Layer C)

### `deep_assess`
- **Parameters**: `repo_urls: list[str]`, `dimensions: list[ScoreDimension] | None`, `budget_tokens: int`, `session_id: str | None`
- **Output**: `DeepAssessmentResult` per repo with dimensions, explanation, confidence
- **Hard gate**: Refuses if candidate has not passed Gate 1+2
- **Progress**: Repo completed, tokens used, budget remaining

### `quick_assess`
- **Parameters**: `repo_url: str`, `dimensions: list[ScoreDimension]`
- **Output**: Rapid assessment on a subset of dimensions
- **Note**: Targeted evaluation, lower cost

### `get_assessment`
- **Parameters**: `repo_url: str`, `session_id: str | None`
- **Output**: Existing cached assessment (if available)
- **Note**: Avoids expensive recalculation

## Ranking & Explainability Tools (Layer D)

### `rank_repos`
- **Parameters**: `domain: str`, `min_confidence: float`, `min_value_score: float`, `max_results: int`, `session_id: str | None`
- **Output**: `RankedRepo` list with `value_score` and explainability
- **Note**: Intra-domain ranking with filters

### `explain_repo`
- **Parameters**: `repo_url: str`, `detail_level: str` ("summary" | "full"), `session_id: str | None`
- **Output**: `ExplainabilityReport` with per-dimension breakdown
- **Note**: Summary-first by default, full detail on demand

### `compare_repos`
- **Parameters**: `repo_urls: list[str]`, `dimensions: list[ScoreDimension] | None`, `session_id: str | None`
- **Output**: Side-by-side comparison on specified dimensions
- **Warning**: Emits cross-domain comparison warning when repos span different domains

## Session Management Tools

### `create_session`
- **Parameters**: `name: str`, `config_overrides: SessionConfig | None`
- **Output**: `session_id` with initial state
- **Note**: Per-session thresholds, budget, domain preferences

### `get_session`
- **Parameters**: `session_id: str`
- **Output**: Session state, pools, progress, results
- **Note**: For resuming interrupted workflows

### `list_sessions`
- **Parameters**: `status: str | None`, `limit: int`
- **Output**: List of active/completed sessions

### `export_session`
- **Parameters**: `session_id: str`, `format: str` ("json" | "csv" | "markdown")
- **Output**: Complete results export
- **Note**: For persistence and sharing

## MCP Resources

| Resource URI | Content |
|-------------|---------|
| `repo://{owner}/{name}/score` | Score for a specific repo |
| `pool://{id}/candidates` | Candidates in a pool |
| `rank://{domain}/top` | Top-ranked repos for a domain |
| `session://{id}/status` | Session state |

## Context Efficiency

- Default output: < 2000 tokens per tool invocation
- Summary-first with `detail_available_via` references
- Structured MCP content (JSON) with text fallback
- Confidence indicators on every result

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `GHDISC_MCP_TRANSPORT` | `stdio` | Transport mode (stdio, http) |
| `GHDISC_MCP_PORT` | `8080` | HTTP transport port |
| `GHDISC_MCP_MAX_CONTEXT_TOKENS` | `2000` | Max tokens per tool invocation |
| `GHDISC_SESSION_BACKEND` | `sqlite` | Session backend (sqlite, redis) |
| `GHDISC_GITHUB_TOKEN` | — | GitHub authentication token |

## See Also

- [MCP-Native Design](../architecture/mcp-native-design.md)
- [Session Workflow](../patterns/session-workflow.md)
- [Screening Gates Detail](../domain/screening-gates.md)