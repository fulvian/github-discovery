---
Title: Technology Stack Decisions
Topic: patterns
Sources: Foundation Blueprint §9, §16; Roadmap §7
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md)
Updated: 2026-04-22
Confidence: high
---

# Technology Stack Decisions

All technology choices have been verified against official documentation via Context7. The stack emphasizes Python-first development with async patterns, modern tooling, and MCP-native integration.

## Core Stack

| Component | Library/Tool | Version | Justification |
|-----------|-------------|---------|---------------|
| **Language** | Python | 3.12+ | Modern syntax (type aliases, match, f-strings), async support |
| **Web framework** | FastAPI | 0.128+ | Async, DI, auto-generated OpenAPI docs |
| **Data models** | Pydantic v2 | 2.x | BaseModel, validators, JSON schema, settings |
| **Settings** | pydantic-settings | 2.x | BaseSettings, env_prefix (`GHDISC_`), nested delimiter |
| **Async HTTP** | httpx | 0.28+ | AsyncClient, retry transport, HTTP/2 |
| **HTTP mocking (test)** | pytest-httpx / respx | Latest | httpx mocking for tests |
| **Git analysis** | PyDriller | 2.x | Commit mining, code churn, contributors |
| **MCP SDK** | mcp (Python) | 1.x | FastMCP, tools, resources, prompts, progress notifications |
| **MCP Apps SDK** | @modelcontextprotocol/ext-apps | 1.x | Interactive UI, tool+resource linking |
| **GitHub MCP** | github-mcp-server | Latest | Toolsets, read-only, dynamic-toolsets |
| **CLI** | typer | 0.12+ | Subcommands, auto-help, type hints |
| **Logging** | structlog | 24.x | JSON structured logging, processors |
| **Lint/Format** | ruff | 0.11+ | Lint + format, line-length=99 |
| **Type check** | mypy | 1.15+ | strict mode |
| **Testing** | pytest | 8.x | Fixtures, markers, async support |

## External Tool Integrations

| Tool | Purpose | Integration |
|------|---------|-------------|
| OpenSSF Scorecard v5+ | Security posture | HTTP API (scorecard.dev) |
| gitleaks 8.x | Secret detection | Subprocess, SARIF output |
| OSV API v1 | Vulnerability scanning | HTTP API query by ecosystem/package/version |
| Repomix | Codebase packing for LLM | CLI subprocess |
| scc | LOC/language/complexity | Subprocess, JSON output |
| cloc | Alternative LOC counting | Subprocess |
| Semgrep CE | Static analysis multi-lang | Subprocess |

## Architecture Patterns

### Code Style (from AGENTS.md)
- Line length: 99 characters (ruff override)
- `from __future__ import annotations` for forward references
- `snake_case` variables/functions, `PascalCase` classes/models, `UPPER_SNAKE_CASE` constants
- All public functions: full type annotations (mypy --strict)
- Pydantic v2 models over raw dicts
- Custom exception hierarchy (`GitHubDiscoveryError` base)
- Structured logging with `structlog` — never `print()`

### Async Patterns
- `async/await` for I/O-bound operations
- `httpx.AsyncClient` for GitHub API calls
- `asyncio.Semaphore` for rate limiting
- Task queues for workers (not raw `asyncio.gather` for unbounded parallelism)

### Configuration
- All settings via `GHDISC_` env prefix
- `pydantic-settings` for typed configuration
- MCP settings via `GHDISC_MCP_*` prefix
- Never hardcode API tokens

### Session Backend
- SQLite (default, local development)
- Redis (deployment, multi-user)

## Packaging & Distribution

| Format | Purpose |
|--------|---------|
| PyPI package (`github-discovery`) | `pip install github-discovery` |
| Docker image (`ghcr.io/github-discovery/server`) | Remote deployment |
| Kilo Marketplace skill | MCP skill with pre-configured prompts |
| OpenCode agent template | `.config/opencode/agent/discovery.md` |

## See Also

- [MCP-Native Design](../architecture/mcp-native-design.md)
- [Option C Architecture](../architecture/option-c-hybrid.md)