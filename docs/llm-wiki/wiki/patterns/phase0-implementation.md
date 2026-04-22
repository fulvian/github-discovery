---
Title: Phase 0 Implementation Decisions
Topic: patterns
Sources: Context7 verification (Pydantic, pydantic-settings, structlog, MCP Python SDK, ruff, pytest, pre-commit); Roadmap Phase 0
Raw: [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md); [phase0-plan.md](../../plans/phase0-implementation-plan.md)
Updated: 2026-04-22
Confidence: high
---

# Phase 0 Implementation Decisions

Detailed implementation decisions for Phase 0 (Project Foundation & Scaffolding), verified against official documentation via Context7.

## Key Points

- **Build system**: hatchling (PEP 621 compliant, src layout, dependency groups)
- **Project layout**: `src/github_discovery/` with subpackage placeholders for all 6 core modules
- **Configuration**: Nested pydantic-settings with `GHDISC_` prefix and `__` nested delimiter
- **Exception hierarchy**: 10 domain exceptions extending `GitHubDiscoveryError` with structured context
- **Session models**: `SessionState`, `SessionConfig`, `ProgressInfo` for agentic cross-session workflows
- **MCP spec models**: `MCPToolSpec`, `AgentWorkflowConfig`, `WorkflowStep` with predefined tool specs
- **Logging**: structlog with JSON (production) / ConsoleRenderer (TTY) and contextvars

## Details

### pyproject.toml Structure

- **Build backend**: `hatchling` — lightweight, PEP 621 compliant, supports `[project.optional-dependencies]` for dev/test
- **Src layout**: `packages = ["src/github_discovery"]` in `[tool.hatch.build.targets.wheel]`
- **Dependencies**: pydantic>=2.7, pydantic-settings>=2.3, httpx>=0.28, structlog>=24.1, typer>=0.12, mcp>=1.0
- **Dev dependencies**: pytest>=8.0, pytest-asyncio>=0.23, pytest-cov>=5.0, respx>=0.21, ruff>=0.11, mypy>=1.15, pre-commit>=3.7
- **CLI entry point**: `[project.scripts] ghdisc = "github_discovery.cli:app"`

### Configuration Architecture (config.py)

**Root `Settings` composes sub-settings** with independent env prefixes:

| Sub-setting | Env prefix | Example env var |
|-------------|-----------|-----------------|
| `Settings` (root) | `GHDISC_` | `GHDISC_DEBUG`, `GHDISC_LOG_LEVEL` |
| `GitHubSettings` | `GHDISC_GITHUB_` | `GHDISC_GITHUB_TOKEN`, `GHDISC_GITHUB_API_BASE_URL` |
| `DiscoverySettings` | `GHDISC_DISCOVERY_` | `GHDISC_DISCOVERY_MAX_CANDIDATES` |
| `ScreeningSettings` | `GHDISC_SCREENING_` | `GHDISC_SCREENING_MIN_GATE1_SCORE` |
| `AssessmentSettings` | `GHDISC_ASSESSMENT_` | `GHDISC_ASSESSMENT_MAX_TOKENS_PER_REPO` |
| `MCPSettings` | `GHDISC_MCP_` | `GHDISC_MCP_TRANSPORT`, `GHDISC_MCP_READ_ONLY` |

**Key design**: `Settings` uses `env_nested_delimiter="__"` allowing `GHDISC_GITHUB__TOKEN` as alternative to sub-prefix. `SettingsConfigDict` with `env_file=".env"` for local development.

**Critical defaults**:
- `ScreeningSettings.hard_gate_enforcement = True` (Blueprint §16.5 hard rule)
- `MCPSettings.max_context_tokens = 2000` (Blueprint §21.8 context-efficient output)
- `MCPSettings.transport = "stdio"` (local development default)
- `MCPSettings.read_only = True` (Blueprint §21.5 restrictive default)

### Exception Hierarchy

```
GitHubDiscoveryError (base, with context dict)
├── ConfigurationError
├── DiscoveryError
├── ScreeningError (gate_level, repo_url)
├── AssessmentError (repo_url, dimension)
├── ScoringError (domain, repo_url)
├── SessionError
├── MCPError
├── RateLimitError (reset_at, remaining)
├── BudgetExceededError (budget_type, budget_limit, budget_used)
└── HardGateViolationError (repo_url, gate_passed, gate_required)
```

**Pattern**: Each domain exception adds typed context fields specific to its domain. `__str__` includes context as `[key=value, ...]` suffix. Never raise bare `Exception`.

### Session Models (Blueprint §21.4)

- **`SessionConfig`**: Per-session overrides for gate thresholds, token budgets, preferred domains, hard gate enforcement. All numeric fields validated with Pydantic `Field(ge=0.0, le=1.0)` for scores, `gt=0` for counts.
- **`SessionState`**: Auto-generated `session_id` (UUID4), `SessionStatus` enum (CREATED → DISCOVERING → SCREENING → ASSESSING → RANKING → COMPLETED, plus FAILED/CANCELLED), pool tracking, repo count tracking, `touch()` for timestamp updates.
- **`ProgressInfo`**: MCP progress notification format (Blueprint §21.6) with `progress_token`, `progress`/`total` floats, `message`, and optional `session_id`.

### MCP Spec Models (Blueprint §21.3, §21.7)

- **`MCPToolSpec`**: Documents each MCP tool with `name`, `description`, `parameters_schema` (JSON Schema), `output_schema`, `session_aware`, `default_output_format` (SUMMARY), `max_context_tokens` (2000), `gate_level`, `category`.
- **`AgentWorkflowConfig`**: Defines multi-step agent workflows as `WorkflowStep` sequences. Predefined workflows: `discover_underrated` (5 steps), `quick_quality_check` (2 steps).
- **`MCPOutputFormat`** enum: SUMMARY, FULL, JSON.

### Logging Configuration (logging.py)

- **Production (non-TTY)**: `JSONRenderer` with ISO timestamps, log level, logger name, callsite parameters, Unicode decoder, structured tracebacks
- **Development (TTY/debug)**: `ConsoleRenderer` with ANSI colors, rich tracebacks
- **Contextvars**: `structlog.contextvars.merge_contextvars` for request-scoped correlation IDs
- **stdlib integration**: `ProcessorFormatter` + `StreamHandler` for interop with libraries using `logging` natively
- **Module-level logger**: `log = get_logger("github_discovery")` for convenience

### ruff Configuration

- **Line length**: 99 (override from default 88, per AGENTS.md)
- **Target**: Python 3.12
- **Rule selection**: E, W, F, I, UP, B, SIM, TCH, RUF, C4, ERA, PL, PTH, A, ANN, D, S, T20
- **Key ignores**: D100 (module docstrings), D104 (package docstrings), D203/D213 (conflicts), PLR0913 (many args)
- **Per-file**: Tests ignore S101, D, ANN, PLR2004; `__init__.py` ignores F401
- **isort**: `required-imports = ["from __future__ import annotations"]`, `known-first-party = ["github_discovery"]`
- **pydocstyle**: Google convention
- **Format**: double quotes, space indentation, docstring-code-format enabled

### mypy Configuration

- **Mode**: `strict = true` with `extra_checks = true`
- **Overrides**: `mcp.*`, `respx.*`, `typer.*` have `ignore_missing_imports = true` (no stable stubs yet)

### pytest Configuration

- **Markers**: `integration`, `slow`, `agentic` (for Phase 9 MCP client tests)
- **Import mode**: `importlib` (required for src layout)
- **asyncio_mode**: `auto` (pytest-asyncio)
- **Filterwarnings**: `error` with `ignore::DeprecationWarning`

### pre-commit Hooks

- **pre-commit-hooks v5**: trailing-whitespace, end-of-file-fixer, check-yaml, check-toml, check-json, check-merge-conflict, check-added-large-files (max 500KB), debug-statements, detect-private-key
- **ruff-pre-commit v0.11.4**: lint + format
- **mypy v1.15.0**: with pydantic>=2.7, pydantic-settings>=2.3, types-structlog

## See Also

- [Technology Stack Decisions](../patterns/tech-stack.md)
- [Operational Rules](../patterns/operational-rules.md)
- [Session Workflow and Progressive Deepening](../patterns/session-workflow.md)
- [MCP-Native Design](../architecture/mcp-native-design.md)
- [Phase 1 Data Models Implementation Decisions](../patterns/phase1-models-implementation.md)