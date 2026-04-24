---
Title: Phase 8 CLI Implementation Plan
Topic: patterns
Sources: Roadmap Phase 8; AGENTS.md (Code Style, CLI commands, Architectural Rules); Context7 verification of typer 0.12+ and rich 13+
Raw: [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md); [AGENTS.md](../../../../AGENTS.md); [plan.md](../../../plans/phase8-implementation-plan.md)
Updated: 2026-04-24 (implementation complete)
Confidence: high
---

# Phase 8 CLI Implementation Plan

## Overview

Phase 8 implements the CLI interface for batch processing, CI/CD automation, and interactive agentic use. The CLI consumes the same core services as MCP (Phase 7) and API (Phase 6).

**Status**: COMPLETE — all 4 waves implemented and verified. 82 CLI tests, 1199 total tests passing.

## Key Architecture Decisions

### CLI Framework
- **typer 0.12+** with `rich_markup_mode="rich"` for styled help text
- Refactor from monolithic `cli.py` to `cli/` package with modular command registration
- Global options via `@app.callback()`: `--verbose`, `--config-file`, `--output-format`, `--log-level`, `--no-color`
- `Annotated[str, typer.Option(...)]` for type-safe CLI parameters

### Output Formatting
- **rich>=13.0** — new dependency for terminal output
- 4 formats: JSON (`json.dumps`), Table (Rich `Table`), Markdown (stdlib), YAML-like (JSON indent)
- `Console(file=StringIO())` for test capture; `Console(no_color=True)` for CI/pipe
- Format resolution: CLI `--output` flag > global `--output-format` > default `table`

### Async Support
- typer has no native async command support — use `asyncio.run()` wrapper in `cli/utils.py`
- All pipeline commands are async (consume async orchestrators)

### Streaming
- Rich `Progress` (SpinnerColumn + BarColumn + TimeElapsedColumn) for discovery/screening/assessment
- Rich `Live` for dynamic display updates
- `--stream/--no-stream` toggle (default: `--stream` when TTY detected)
- `sys.stdout.isatty()` detection for auto-disabling Rich in pipe

### Session Management
- `ghdisc session create/list/resume/show` subcommands
- Uses `SessionManager` from `mcp/session.py` (Phase 7, SQLite-backed)
- `--session-id` flag on all pipeline commands for workflow continuity
- Resume shows state and suggests next command

### Tasks Already Done (from Phase 7)
- Task 8.8: `mcp serve` command — already in `cli.py`
- Task 8.10: `mcp init-config` command — already in `cli.py`
- Both will be refactored to `cli/mcp_serve.py` and `cli/mcp_config.py`

## Module Structure

```
cli/
├── __init__.py          # Exports: app
├── app.py               # Typer app factory + callback + command registration
├── discover.py          # ghdisc discover
├── screen.py            # ghdisc screen
├── deep_eval.py         # ghdisc deep-eval
├── rank.py              # ghdisc rank
├── export.py            # ghdisc export
├── session.py           # ghdisc session create/list/resume/show
├── mcp_serve.py         # ghdisc mcp serve (refactored)
├── mcp_config.py        # ghdisc mcp init-config (refactored)
├── formatters.py        # Output formatting (JSON/Table/Markdown/YAML)
├── progress_display.py  # Rich Progress + Live streaming
└── utils.py             # Helpers (async_runner, settings, console)
```

## Context7 Verification Summary

### typer 0.12+ (from `/websites/typer_tiangolo`)
- `rich_markup_mode="rich"` — enables Rich console markup in help strings
- `@app.callback()` — global options invoked before any subcommand
- `context_settings={"help_option_names": ["-h", "--help"]}` — -h shortcut
- `rich_help_panel` — categorize commands in help output
- `Annotated[type, typer.Option("--flag", help="...")]` — type-safe options
- `app.add_typer(sub_app, name="group")` — subcommand groups
- No native async support — requires `asyncio.run()` wrapper

### rich 13+ (from `/textualize/rich`)
- `Console(no_color=True)` — disable colors for CI/pipe
- `Table(title=..., show_lines=True)` — data display with `add_column()` + `add_row()`
- `Progress(SpinnerColumn(), TextColumn(), BarColumn(), ...)` — progress tracking
- `Live(renderable, refresh_per_second=4)` — dynamic display
- `Panel(content, title=...)` — grouped output sections
- `Console(file=StringIO())` — test capture

## Test Plan
- ~84 tests across 11 test files in `tests/unit/cli/`
- Total expected after Phase 8: ~1202 tests (1118 + 84)
- Mocking strategy: `AsyncMock` for orchestrators, `CliRunner` for command testing, `Console(file=StringIO())` for output verification

## Implementation Waves
1. **Wave A** (Foundation): cli/ package, app.py, utils.py, formatters.py, progress_display.py — 20 tests
2. **Wave B** (Pipeline): discover, screen, rank commands — 18 tests
3. **Wave C** (Advanced): deep-eval, export, session commands — 22 tests
4. **Wave D** (MCP Refactor): move existing commands to cli/ package — 8 tests

## Implementation Results

### Waves Completed

**Wave A** (Foundation): cli/ package, app.py, utils.py, formatters.py, progress_display.py — 41 tests
- Typer app with `rich_markup_mode="rich"`, `context_settings`, global callback
- `_CliState` for shared global state
- `formatters.py`: 7 table builders + JSON/Markdown/YAML/CSV
- `progress_display.py`: Rich Progress with SpinnerColumn/BarColumn/TimeElapsedColumn
- MCP commands refactored to `cli/mcp_serve.py` and `cli/mcp_config.py`
- Old `cli.py` kept as backward-compat redirect

**Wave B** (Pipeline): discover, screen, rank commands — 17 tests
- `discover`: DiscoveryQuery construction, streaming/direct modes
- `screen`: ScreeningContext with GateLevel validation, pool loading
- `rank`: DomainType validation, FeatureStore loading, Ranker integration

**Wave C** (Advanced): deep-eval, export, session commands — 24 tests
- `deep_eval`: hard gate enforcement, repo-url parsing, AssessmentOrchestrator
- `export`: JSON/CSV/Markdown, session and pool export, file/stdout output
- `session`: create/list/resume/show with SessionManager, next-step suggestions

**Wave D** (MCP Refactor): Already done in Wave A — mcp_serve.py and mcp_config.py refactored from cli.py

### Test Results
- 82 CLI tests (41 Wave A + 17 Wave B + 24 Wave C)
- 1199 total tests passing (1118 pre-existing + 82 new - 1 flaky pre-existing)
- ruff check: 0 errors (13 CLI source files)
- ruff format: all formatted
- mypy --strict: 0 errors (13 CLI source files)

### Key Implementation Decisions
- `run_async()` wrapper uses `asyncio.run()` — typer has no native async support
- `register(app: typer.Typer)` pattern for each command module
- Lazy imports inside command functions for fast CLI startup
- `format_output()` uses `fmt` kwarg (not `format` which shadows builtin)
- `DeepAssessmentResult` uses `overall_quality` (not `overall_score`), `gate3_pass` (not `passed`), `dimensions` dict (not `dimension_scores` list)
- `AssessmentOrchestrator` uses `quick_assess()` (not `assess_single()`)
- Test patches target `github_discovery.cli.utils.*` (where functions are defined)
- Per-file-ignores for `cli/*.py`: PLC0415 (deferred imports), PLR2004 (display width constants)

## See Also
- [Agent Workflow Patterns](agent-workflows.md)
- [Session Workflow](session-workflow.md)
- [Technology Stack Decisions](tech-stack.md)
- [Phase 7 MCP Implementation](phase7-mcp-plan.md)
