---
Title: Phase 7 MCP Integration Implementation Plan
Topic: patterns
Sources: Foundation Blueprint §21; Roadmap Phase 7; Context7 verification of MCP Python SDK + GitHub MCP Server
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md); [plan.md](../../plans/phase7-implementation-plan.md)
Updated: 2026-04-23
Confidence: high
---

# Phase 7 MCP Integration Implementation Plan

Implementation plan for the MCP-Native Integration Layer — the primary interface of GitHub Discovery.

## Status: COMPLETE ✅ (1114 tests passing, 118 source files, 0 lint/type errors)

## Key Architecture Decisions

### FastMCP Server with Lifespan

- **Pattern**: `FastMCP("github-discovery", json_response=True, lifespan=app_lifespan)`
- **AppContext**: Typed dataclass with all services (session_manager, orchestrators, scoring_engine, ranker, pool_manager, feature_store)
- **Access in tools**: `ctx.request_context.lifespan_context` → cast to AppContext
- **Verified via Context7**: Lifespan with `@asynccontextmanager async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]`

### 16 MCP Tools (5 categories)

| File | Tools |
|------|-------|
| `tools/discovery.py` | discover_repos, get_candidate_pool, expand_seeds |
| `tools/screening.py` | screen_candidates, get_shortlist, quick_screen |
| `tools/assessment.py` | deep_assess, quick_assess, get_assessment |
| `tools/ranking.py` | rank_repos, explain_repo, compare_repos |
| `tools/session.py` | create_session, get_session, list_sessions, export_session |

### 4 MCP Resources (URI templates)

| URI | Resource |
|-----|----------|
| `repo://{owner}/{name}/score` | Repository score |
| `pool://{pool_id}/candidates` | Pool candidates |
| `rank://{domain}/top` | Domain top ranking |
| `session://{session_id}/status` | Session state |

### 5 MCP Prompts (Agent Skill Definitions)

1. `discover_underrated` — Find hidden gems (5-step workflow)
2. `quick_quality_check` — Quick repo quality check
3. `compare_for_adoption` — Adoption decision comparison
4. `domain_deep_dive` — Deep domain exploration
5. `security_audit` — Security-first assessment

### Context-Efficient Output

- `format_tool_result()` → MCPToolResult dict with summary-first, references, confidence
- Default: < 2000 tokens per invocation (configurable via `GHDISC_MCP_MAX_CONTEXT_TOKENS`)
- `truncate_for_context()` for list truncation within budget

### Progress Notifications

- `ctx.report_progress(progress, total, message)` — NOT the removed `mcp.shared.progress`
- Phase-specific helpers: `report_discovery_progress()`, `report_screening_progress()`, `report_assessment_progress()`

### Session Management

- **SessionManager**: SQLite-backed CRUD for SessionState
- Cross-session progressive deepening: session_id propagated across tools
- Session store path: `.ghdisc/sessions.db` (configurable)

### GitHub MCP Composition

- Config generation for 3 targets: kilo, opencode, claude
- No tool duplication: DELEGATED_TOOLS list vs DISCOVERY_TOOLS list
- Read-only default: `X-MCP-Readonly: true`

### Transport

- **stdio** (default): Kilocode CLI, OpenCode, Claude Code local
- **streamable-http**: Production deployment (recommended by MCP SDK)

## Context7 Verified Patterns

### MCP Python SDK v1.x

1. `FastMCP("name", json_response=True, lifespan=...)` — server setup
2. `@mcp.tool()` — async tool with Context parameter
3. `@mcp.resource("uri://{param}")` — resource with URI template
4. `@mcp.prompt()` — prompt with typed arguments, returns string
5. `await ctx.report_progress(progress, total, message)` — progress
6. `await ctx.info/debug/warning/error()` — logging
7. `mcp.run(transport="stdio")` or `mcp.run(transport="streamable-http", ...)` — transport
8. Return Pydantic BaseModel from tool → automatic structured content

### GitHub MCP Server

1. Remote: `https://api.githubcopilot.com/mcp/` with headers
2. `X-MCP-Toolsets: repos,issues,pull_requests` — toolset selection
3. `X-MCP-Readonly: true` — read-only mode
4. `X-MCP-Lockdown: true` — push-access-only content
5. `--dynamic-toolsets` CLI flag — runtime toolset discovery

## New Dependencies

- `mcp>=1.6` — MCP Python SDK

## Implementation Waves

| Wave | Tasks | Focus | Status | Tests |
|------|-------|-------|--------|-------|
| A | 7.1, 7.10, 7.11, 7.12, 7.13 | Foundation (server, output, progress, config, transport, session) | ✅ | ~25 |
| B | 7.2, 7.3 | Discovery + Screening tools (6 tools) | ✅ | ~25 |
| C | 7.4, 7.5, 7.6 | Assessment + Ranking + Session tools (10 tools) | ✅ | ~35 |
| D | 7.7, 7.8, 7.9 | Resources + Prompts + Composition | ✅ | ~25 |
| E | Integration | CLI entry point, e2e tests, agentic stubs | ✅ | 15 (12 passed, 3 skipped) |

### Wave E Results

- `mcp/__main__.py` — entry point for `python -m github_discovery.mcp serve`
- `cli.py` — updated with `mcp` subcommand group: `serve` (starts server) and `init-config` (generates config)
- `tests/integration/test_mcp_server.py` — 12 integration tests: server creation, tool/resource/prompt registration counts, filtering, lifespan, CLI commands
- `tests/agentic/test_mcp_client.py` — 3 skipped stubs for future MCP client integration
- `.kilo/mcp.json.template` — verified with correct config

### Implementation Quirks Discovered

1. **Some tools create service instances directly** (e.g., `get_candidate_pool` creates `PoolManager()`) instead of using `app_ctx` services. This works but is inconsistent with other tools that use `app_ctx`.
2. **`get_enabled_tools()` logs on every call** — 16 duplicate log lines per server creation. Cosmetic noise, not a bug.
3. **Ruff per-file-ignores** needed for MCP tool modules: PLC0415 (deferred imports), PLR0915 (many statements), TCH (runtime type introspection), S101 (assert narrowing).
4. **Resource templates** stored in `mcp._resource_manager._templates` (not `_resources` which is for static resources).

## See Also

- [MCP-Native Design](../architecture/mcp-native-design.md)
- [MCP Tool Specs](../apis/mcp-tools.md)
- [MCP SDK Verification](../apis/mcp-sdk-verification.md)
- [Session Workflow](../patterns/session-workflow.md)
- [Agent Workflows](../patterns/agent-workflows.md)
- [Phase 6 API & Worker](../patterns/phase6-api-worker-plan.md)
