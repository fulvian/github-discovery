# GitHub Discovery — Phase 8 Implementation Plan

## Meta

- **Stato**: Draft v1
- **Data**: 2026-04-24
- **Riferimento roadmap**: `docs/roadmaps/github-discovery_foundation_roadmap.md` — Phase 8
- **Riferimento blueprint**: `docs/foundation/github-discovery_foundation_blueprint.md` — §21 (Agentic Integration Architecture)
- **Riferimento wiki**: `docs/llm-wiki/wiki/` — articoli su agent workflows, session workflow, MCP-native design
- **Durata stimata**: 1-2 settimane
- **Milestone**: M7 — CLI & Agent-Friendly (CLI con session management, streaming, MCP config generator)
- **Dipendenza**: Phase 0+1+2+3+4+5+6+7 completate (1118 tests passing, `make ci` verde)
- **Context7 verification**: typer 0.12+ (callback, rich_markup_mode, Annotated types, subcommands, context_settings), rich 13+ (Console, Table, Progress, Live, Markdown, SpinnerColumn)

---

## Indice

1. [Obiettivo](#1-obiettivo)
2. [Task Overview](#2-task-overview)
3. [Architettura generale](#3-architettura-generale)
4. [Nuove dipendenze](#4-nuove-dipendenze)
5. [Codice esistente — stato attuale](#5-codice-esistente--stato-attuale)
6. [Task 8.1 — CLI Framework Setup (Enhancement)](#6-task-81--cli-framework-setup-enhancement)
7. [Task 8.2 — Comando `discover`](#7-task-82--comando-discover)
8. [Task 8.3 — Comando `screen`](#8-task-83--comando-screen)
9. [Task 8.4 — Comando `deep-eval`](#9-task-84--comando-deep-eval)
10. [Task 8.5 — Comando `rank`](#10-task-85--comando-rank)
11. [Task 8.6 — Comando `export`](#11-task-86--comando-export)
12. [Task 8.7 — Output Formatting Module](#12-task-87--output-formatting-module)
13. [Task 8.8 — Comando `mcp serve` (GIÀ IMPLEMENTATO)](#13-task-88--comando-mcp-serve-già-implementato)
14. [Task 8.9 — Comandi Sessione Agentica](#14-task-89--comandi-sessione-agentica)
15. [Task 8.10 — CLI MCP Config Generator (GIÀ IMPLEMENTATO)](#15-task-810--cli-mcp-config-generator-già-implementato)
16. [Task 8.11 — CLI Streaming Output](#16-task-811--cli-streaming-output)
17. [Sequenza di implementazione — Waves](#17-sequenza-di-implementazione--waves)
18. [Test plan](#18-test-plan)
19. [Criteri di accettazione](#19-criteri-di-accettazione)
20. [Rischi e mitigazioni](#20-rischi-e-mitigazioni)
21. [Verifica Context7](#21-verifica-context7)

---

## 1) Obiettivo

Implementare l'interfaccia CLI completa per batch processing, automazione CI/CD e uso interattivo agentico. La CLI è un'interfaccia agent-friendly che consuma gli stessi servizi core di MCP (Phase 7) e API (Phase 6).

Al completamento della Phase 8:

- **CLI completa** con 6 comandi principali: `discover`, `screen`, `deep-eval`, `rank`, `export`, `session`
- **Opzioni globali**: `--verbose`, `--config-file`, `--output-format`, `--log-level`
- **Session management**: `session create`, `session list`, `session resume` per uso agentico interattivo
- **Streaming output**: supporto `--stream` per operazioni lunghe con progress indicator
- **Output formattato**: JSON, tabella (Rich), Markdown, YAML
- **MCP serve** e **MCP init-config**: già implementati in Phase 7, manutenzione
- **Entry point**: `python -m github_discovery` e `ghdisc` (console script)

### Principi architetturali

1. **Reuse Core Services**: La CLI chiama direttamente orchestrator/scorer/ranker (come API e MCP), non passa per API HTTP
2. **Session-Aware**: Ogni comando supporta `--session-id` per workflow agentici multi-step
3. **Agent-Friendly**: Output strutturato (JSON/YAML) per pipe, tabella formattata per uso umano
4. **No Silent Failures**: Errori con contesto completo (repo URL, gate level, dimensione)
5. **Streaming nativo**: Rich Progress + Live per feedback visivo su operazioni lunghe

---

## 2) Task Overview

| Task ID | Task | Output | Stato | Dipende da |
|---------|------|--------|-------|------------|
| 8.1 | CLI framework setup (enhancement) | `cli/app.py` con global options, callback | DA FARE | — |
| 8.2 | Comando `discover` | `cli/discover.py` | DA FARE | 8.1, 8.7 |
| 8.3 | Comando `screen` | `cli/screen.py` | DA FARE | 8.1, 8.7 |
| 8.4 | Comando `deep-eval` | `cli/deep_eval.py` | DA FARE | 8.1, 8.7 |
| 8.5 | Comando `rank` | `cli/rank.py` | DA FARE | 8.1, 8.7 |
| 8.6 | Comando `export` | `cli/export.py` | DA FARE | 8.1, 8.7 |
| 8.7 | Output formatting module | `cli/formatters.py` | DA FARE | — |
| 8.8 | Comando `mcp serve` | `cli/mcp_serve.py` | ✅ GIÀ FATTO | — |
| 8.9 | Comandi sessione agentica | `cli/session.py` | DA FARE | 8.1, 8.7 |
| 8.10 | CLI MCP config generator | `cli/mcp_config.py` | ✅ GIÀ FATTO | — |
| 8.11 | CLI streaming output | `cli/progress_display.py` | DA FARE | 8.7 |

---

## 3) Architettura generale

### Struttura moduli

```
src/github_discovery/cli/
├── __init__.py                  # Exports: app (typer.Typer)
├── app.py                       # Typer app factory + callback globale + subcommand registration
├── discover.py                  # ghdisc discover --query "..." --channels ... --max ...
├── screen.py                    # ghdisc screen --pool-id X --gate 1 --gate 2
├── deep_eval.py                 # ghdisc deep-eval --pool-id X --max-repos 50 --budget-tokens 100000
├── rank.py                      # ghdisc rank --domain library --top 20 --output table
├── export.py                    # ghdisc export --format json --output results.json
├── session.py                   # ghdisc session create/list/resume
├── mcp_serve.py                 # ghdisc mcp serve (refactored from current cli.py)
├── mcp_config.py                # ghdisc mcp init-config (refactored from current cli.py)
├── formatters.py                # OutputFormatter: JSON, Table (Rich), Markdown, YAML
├── progress_display.py          # CLI streaming: Rich Progress + Live per operazioni lunghe
└── utils.py                     # Helpers: async_runner, parse_options, settings_from_cli
```

### File esistenti da refactorizzare

| File attuale | Azione | Nuova posizione |
|-------------|--------|-----------------|
| `cli.py` (root) | Refactor: spostare in `cli/app.py` | `cli/app.py` |
| `cli.py` → `version` command | Spostare in `cli/app.py` | `cli/app.py` |
| `cli.py` → `mcp serve` command | Spostare in `cli/mcp_serve.py` | `cli/mcp_serve.py` |
| `cli.py` → `mcp init-config` command | Spostare in `cli/mcp_config.py` | `cli/mcp_config.py` |
| `__main__.py` | Aggiornare import da `cli.py` → `cli/app.py` | `__main__.py` |

### CLI command tree

```
ghdisc (python -m github_discovery)
├── version                              # Show version
├── discover                             # Discover candidate repos
│   ├── --query TEXT (required)
│   ├── --channels TEXT (comma-sep: search,registry,curated,code_search,dependency,seed)
│   ├── --max INT (default: 100)
│   ├── --session-id TEXT
│   ├── --output FORMAT (json|table|markdown|yaml, default: table)
│   ├── --stream / --no-stream
│   └── --languages TEXT (comma-sep filter)
├── screen                               # Screen candidates (Gate 1+2)
│   ├── --pool-id TEXT (required)
│   ├── --gate TEXT (1|2|both, default: both)
│   ├── --min-gate1-score FLOAT
│   ├── --min-gate2-score FLOAT
│   ├── --session-id TEXT
│   ├── --output FORMAT (default: table)
│   └── --stream / --no-stream
├── deep-eval                            # Deep LLM assessment (Gate 3)
│   ├── --pool-id TEXT (required)
│   ├── --repo-urls TEXT (comma-sep, alternative to pool-id)
│   ├── --max-repos INT (default: 50)
│   ├── --budget-tokens INT
│   ├── --dimensions TEXT (comma-sep subset)
│   ├── --session-id TEXT
│   ├── --output FORMAT (default: table)
│   └── --stream / --no-stream
├── rank                                 # Anti-star bias ranking
│   ├── --domain TEXT
│   ├── --top INT (default: 20)
│   ├── --min-confidence FLOAT
│   ├── --min-value-score FLOAT
│   ├── --session-id TEXT
│   └── --output FORMAT (default: table)
├── export                               # Export results
│   ├── --session-id TEXT (or --pool-id)
│   ├── --format FORMAT (json|csv|markdown, default: json)
│   ├── --output PATH (file path, default: stdout)
│   ├── --domain TEXT
│   └── --include-details / --no-include-details
├── session                              # Session management
│   ├── create --name TEXT
│   ├── list [--status TEXT] [--limit INT]
│   ├── resume --session-id TEXT
│   └── show --session-id TEXT
└── mcp                                  # MCP server (già implementato)
    ├── serve --transport stdio|http [--host] [--port]
    └── init-config --target kilo|opencode|claude [--output]
```

### Global options (via @app.callback)

```
ghdisc [GLOBAL OPTIONS] COMMAND [COMMAND OPTIONS]

Global Options:
  --verbose / --no-verbose       Enable verbose output (default: False)
  --config-file PATH             Path to .env config file (default: .env)
  --output-format FORMAT         Default output format: json|table|markdown|yaml
  --log-level LEVEL              Log level: DEBUG|INFO|WARNING|ERROR (default: INFO)
  --no-color                     Disable colored output
```

---

## 4) Nuove dipendenze

Da aggiungere a `pyproject.toml`:

| Package | Versione | Purpose |
|---------|----------|---------|
| `rich` | `>=13.0` | Terminal output: Table, Progress, Live, Console markup, Markdown rendering |

**Non servono nuove dipendenze per**:
- CLI framework: `typer` (già presente, >=0.12)
- Async support: `asyncio` (stdlib)
- JSON/YAML: `json` (stdlib), `csv` (stdlib), `io` (stdlib)
- Session persistence: `aiosqlite` (già presente)
- Logging: `structlog` (già presente)
- Core services: tutti già implementati in Phase 0-7

**Nota su YAML**: Per evitare una dipendenza addizionale, l'output YAML sarà generato via `json.dumps()` con formatting manuale (indentazione). Se in futuro serve YAML completo, si aggiungerà `pyyaml`.

---

## 5) Codice esistente — stato attuale

### File da refactorizzare

**`src/github_discovery/cli.py`** (132 righe):
- Typer app con `version`, `mcp serve`, `mcp init-config`
- Già funzionale ma monolitico — va scomposto in moduli
- `mcp_app` sub-Typer va separato

**`src/github_discovery/__main__.py`** (13 righe):
- Entry point per `python -m github_discovery`
- Importa `app` da `cli.py` — va aggiornato dopo refactor

### Modelli utilizzabili (già esistenti)

| Modello | File | Utilizzo CLI |
|---------|------|-------------|
| `DiscoveryQuery` | `models/api.py` | Parsing parametri discover |
| `ScreeningRequest` | `models/api.py` | Parsing parametri screen |
| `AssessmentRequest` | `models/api.py` | Parsing parametri deep-eval |
| `RankingQuery` | `models/api.py` | Parsing parametri rank |
| `ExportRequest` / `ExportFormat` | `models/api.py` | Parsing parametri export |
| `SessionState` | `models/session.py` | Visualizzazione sessione |
| `SessionConfig` | `models/session.py` | Creazione sessione |
| `SessionStatus` | `models/session.py` | Filtraggio sessioni |
| `RepoCandidate` | `models/candidate.py` | Visualizzazione candidati |
| `RankedRepo` | `models/scoring.py` | Visualizzazione ranking |
| `Settings` | `config.py` | Configurazione globale |
| `GateLevel` | `models/enums.py` | Parsing gate level |
| `DomainType` | `models/enums.py` | Parsing dominio |

### Servizi core da consumare (già esistenti)

| Servizio | Modulo | Metodo CLI |
|----------|--------|-----------|
| `DiscoveryOrchestrator` | `discovery/orchestrator.py` | discover, expand_seeds |
| `PoolManager` | `discovery/pool.py` | get_pool, list_pools |
| `ScreeningOrchestrator` | `screening/orchestrator.py` | screen_pool, screen_single |
| `AssessmentOrchestrator` | `assessment/orchestrator.py` | assess_pool, assess_single |
| `ScoringEngine` | `scoring/engine.py` | score |
| `Ranker` | `scoring/ranker.py` | rank |
| `FeatureStore` | `scoring/feature_store.py` | get, get_batch |
| `ExplainabilityGenerator` | `scoring/explainability.py` | generate_report |
| `SessionManager` | `mcp/session.py` | create, get, list, update |

---

## 6) Task 8.1 — CLI Framework Setup (Enhancement)

### Obiettivo

Refactorizzare `cli.py` monolitico in package `cli/` con app factory, callback globale per opzioni condivise, e registrazione modulare dei comandi.

### cli/__init__.py

```python
"""GitHub Discovery CLI — command-line interface for batch processing and agent-friendly usage."""

from __future__ import annotations

from github_discovery.cli.app import app

__all__ = ["app"]
```

### cli/app.py

```python
from __future__ import annotations

from typing import Annotated

import typer

from github_discovery import __version__

app = typer.Typer(
    name="ghdisc",
    help="GitHub Discovery — MCP-native agentic discovery engine",
    no_args_is_help=True,
    rich_markup_mode="rich",  # Context7: enable Rich markup in help strings
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Sub-Typer groups
mcp_app = typer.Typer(
    name="mcp",
    help="MCP server commands",
    no_args_is_help=True,
)
session_app = typer.Typer(
    name="session",
    help="Session management for agentic workflows",
    no_args_is_help=True,
)


# --- Global state ---
class _CliState:
    """Shared CLI state from global options."""

    verbose: bool = False
    config_file: str = ".env"
    output_format: str = "table"
    log_level: str = "INFO"
    no_color: bool = False


cli_state = _CliState()


@app.callback()
def main_callback(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose output"),
    ] = False,
    config_file: Annotated[
        str,
        typer.Option("--config-file", help="Path to .env config file"),
    ] = ".env",
    output_format: Annotated[
        str,
        typer.Option(
            "--output-format",
            "-o",
            help="Default output format: json|table|markdown|yaml",
        ),
    ] = "table",
    log_level: Annotated[
        str,
        typer.Option("--log-level", help="Log level: DEBUG|INFO|WARNING|ERROR"),
    ] = "INFO",
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable colored output"),
    ] = False,
) -> None:
    """GitHub Discovery — MCP-native agentic discovery engine.

    Find high-quality GitHub repositories independent of popularity (stars).

    Use [bold green]ghdisc discover[/bold green] to start finding repos,
    or [bold green]ghdisc mcp serve[/bold green] to start the MCP server.
    """
    cli_state.verbose = verbose
    cli_state.config_file = config_file
    cli_state.output_format = output_format
    cli_state.log_level = log_level
    cli_state.no_color = no_color

    # Configure logging based on CLI flags
    from github_discovery.config import Settings

    settings = Settings(_env_file=config_file)
    # Override log level if CLI flag differs from config
    if log_level != "INFO":
        import logging
        logging.getLogger("github_discovery").setLevel(getattr(logging, log_level.upper()))


@app.command()
def version() -> None:
    """Show the current version."""
    typer.echo(f"github-discovery {__version__}")


# --- Register sub-groups ---
app.add_typer(mcp_app, name="mcp")
app.add_typer(session_app, name="session")

# --- Lazy import and register commands ---
# This avoids importing heavy dependencies until the specific command is used.
# Each module registers its commands on the appropriate Typer app via a register_* function.


def _register_commands() -> None:
    """Register all CLI commands via lazy imports."""
    from github_discovery.cli.discover import register as reg_discover
    from github_discovery.cli.screen import register as reg_screen
    from github_discovery.cli.deep_eval import register as reg_deep_eval
    from github_discovery.cli.rank import register as reg_rank
    from github_discovery.cli.export import register as reg_export
    from github_discovery.cli.session import register as reg_session
    from github_discovery.cli.mcp_serve import register as reg_mcp_serve
    from github_discovery.cli.mcp_config import register as reg_mcp_config

    reg_discover(app)
    reg_screen(app)
    reg_deep_eval(app)
    reg_rank(app)
    reg_export(app)
    reg_session(session_app)
    reg_mcp_serve(mcp_app)
    reg_mcp_config(mcp_app)


_register_commands()


if __name__ == "__main__":
    app()
```

### cli/utils.py

```python
"""CLI utility helpers."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable, Coroutine
from typing import Any

import structlog
from rich.console import Console

from github_discovery.cli.app import cli_state

logger = structlog.get_logger("github_discovery.cli")


def get_console() -> Console:
    """Get a Rich Console respecting CLI state (no-color, verbose)."""
    return Console(
        no_color=cli_state.no_color,
        stderr=True,
    )


def get_output_console() -> Console:
    """Get a Rich Console for stdout output."""
    return Console(
        no_color=cli_state.no_color,
        stderr=False,
    )


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run an async coroutine from synchronous CLI context.

    Typer does not natively support async commands.
    This wrapper bridges the gap with asyncio.run().
    """
    return asyncio.run(coro)


def resolve_output_format(format_override: str | None) -> str:
    """Resolve output format: CLI flag > global option > default 'table'."""
    return format_override or cli_state.output_format or "table"


def get_settings() -> Any:
    """Load Settings with CLI-specified config file."""
    from github_discovery.config import Settings

    return Settings(_env_file=cli_state.config_file)


def comma_separated_to_list(value: str) -> list[str]:
    """Parse a comma-separated string into a list of stripped strings."""
    return [s.strip() for s in value.split(",") if s.strip()]


def exit_with_error(message: str, code: int = 1) -> None:
    """Print error to stderr and exit with code."""
    console = get_console()
    console.print(f"[bold red]Error:[/bold red] {message}")
    raise SystemExit(code)
```

### __main__.py (aggiornato)

```python
"""GitHub Discovery CLI entry point for `python -m github_discovery`."""

from __future__ import annotations

from github_discovery.cli.app import app

if __name__ == "__main__":
    app()
```

### pyproject.toml (aggiornamento)

```toml
[project.scripts]
ghdisc = "github_discovery.cli.app:app"
```

---

## 7) Task 8.2 — Comando `discover`

### cli/discover.py

Il comando `discover` avvia la pipeline discovery multicanale e mostra i risultati con il formato scelto.

```python
from __future__ import annotations

from typing import Annotated

import typer

from github_discovery.cli.utils import (
    comma_separated_to_list,
    exit_with_error,
    get_console,
    get_output_console,
    get_settings,
    resolve_output_format,
    run_async,
)


def register(app: typer.Typer) -> None:
    """Register the discover command."""

    @app.command(
        name="discover",
        help="Discover candidate repositories matching a query.",
        rich_help_panel="Pipeline",
    )
    async def discover(
        query: Annotated[
            str,
            typer.Argument(help="Search query for repositories"),
        ],
        channels: Annotated[
            str | None,
            typer.Option(
                "--channels",
                "-c",
                help="Discovery channels (comma-sep: search,registry,curated,code_search,dependency,seed)",
            ),
        ] = None,
        max_candidates: Annotated[
            int,
            typer.Option("--max", "-m", help="Maximum candidates to discover"),
        ] = 100,
        session_id: Annotated[
            str | None,
            typer.Option("--session-id", "-s", help="Session ID for workflow continuity"),
        ] = None,
        output: Annotated[
            str | None,
            typer.Option("--output", "-o", help="Output format: json|table|markdown|yaml"),
        ] = None,
        languages: Annotated[
            str | None,
            typer.Option("--languages", "-l", help="Filter by languages (comma-sep)"),
        ] = None,
        stream: Annotated[
            bool,
            typer.Option("--stream/--no-stream", help="Show streaming progress"),
        ] = True,
    ) -> None:
        """Discover candidate repositories matching a query.

        Searches across multiple channels (GitHub Search, Code Search, Package
        Registries, Awesome Lists, Dependency Graph) to find candidate repos.
        Results are deduplicated and scored with a preliminary discovery_score.

        Examples:
            ghdisc discover "static analysis python" --channels search,registry --max 500
            ghdisc discover "machine learning framework" --session-id abc123 --output json
        """
        settings = get_settings()
        channel_list = comma_separated_to_list(channels) if channels else None
        lang_list = comma_separated_to_list(languages) if languages else None
        fmt = resolve_output_format(output)
        console = get_console()

        if stream:
            from github_discovery.cli.progress_display import display_discovery_progress

            await display_discovery_progress(
                settings=settings,
                query=query,
                channels=channel_list,
                max_candidates=max_candidates,
                session_id=session_id,
                languages=lang_list,
            )
        else:
            # Non-streaming: direct call
            from github_discovery.discovery.orchestrator import DiscoveryOrchestrator
            from github_discovery.discovery.pool import PoolManager

            pool_mgr = PoolManager()
            orch = DiscoveryOrchestrator(settings, pool_mgr)

            try:
                result = await orch.discover(
                    query=query,
                    channels=channel_list or settings.discovery.default_channels,
                    max_candidates=max_candidates,
                )

                from github_discovery.cli.formatters import format_output

                formatted = format_output(
                    data=result,
                    format=fmt,
                    output_type="discovery",
                )
                out_console = get_output_console()
                out_console.print(formatted)
            finally:
                await pool_mgr.close()
```

**Verifica**: `ghdisc discover "static analysis python" --max 50 --output json` produce output JSON. `ghdisc discover "test" --output table` produce tabella formattata.

---

## 8) Task 8.3 — Comando `screen`

### cli/screen.py

```python
from __future__ import annotations

from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    """Register the screen command."""

    @app.command(
        name="screen",
        help="Screen candidate repositories through quality gates (Gate 1+2).",
        rich_help_panel="Pipeline",
    )
    async def screen(
        pool_id: Annotated[
            str,
            typer.Option("--pool-id", "-p", help="Candidate pool ID from discover"),
        ],
        gate: Annotated[
            str,
            typer.Option("--gate", "-g", help="Gate level: 1, 2, or both"),
        ] = "both",
        min_gate1_score: Annotated[
            float | None,
            typer.Option("--min-gate1", help="Override minimum Gate 1 score"),
        ] = None,
        min_gate2_score: Annotated[
            float | None,
            typer.Option("--min-gate2", help="Override minimum Gate 2 score"),
        ] = None,
        session_id: Annotated[
            str | None,
            typer.Option("--session-id", "-s", help="Session ID for workflow continuity"),
        ] = None,
        output: Annotated[
            str | None,
            typer.Option("--output", "-o", help="Output format: json|table|markdown|yaml"),
        ] = None,
        stream: Annotated[
            bool,
            typer.Option("--stream/--no-stream", help="Show streaming progress"),
        ] = True,
    ) -> None:
        """Screen candidate repositories through quality gates.

        Gate 1: Metadata screening (zero LLM cost) — checks hygiene, CI/CD,
        test footprint, release discipline, maintenance, dependency quality.
        Gate 2: Static/security screening (zero or low cost) — Scorecard,
        secret detection, vulnerability scan, complexity metrics.

        Hard gate: No repository can proceed to Gate 3 without passing
        both Gate 1 and Gate 2.

        Examples:
            ghdisc screen --pool-id abc123 --gate 1 --output table
            ghdisc screen --pool-id abc123 --gate both --stream
        """
        # ... implementation pattern similar to discover
```

**Verifica**: `ghdisc screen --pool-id X --gate 1` mostra pass/fail per Gate 1. `ghdisc screen --pool-id X --gate both --output json` produce output JSON.

---

## 9) Task 8.4 — Comando `deep-eval`

### cli/deep_eval.py

```python
from __future__ import annotations

from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    """Register the deep-eval command."""

    @app.command(
        name="deep-eval",
        help="Deep LLM assessment of top candidates (Gate 3).",
        rich_help_panel="Pipeline",
    )
    async def deep_eval(
        pool_id: Annotated[
            str | None,
            typer.Option("--pool-id", "-p", help="Pool ID (uses shortlist)"),
        ] = None,
        repo_urls: Annotated[
            str | None,
            typer.Option("--repo-urls", "-r", help="Specific repo URLs (comma-sep)"),
        ] = None,
        max_repos: Annotated[
            int,
            typer.Option("--max-repos", "-m", help="Maximum repos to assess"),
        ] = 50,
        budget_tokens: Annotated[
            int | None,
            typer.Option("--budget-tokens", "-b", help="Override token budget"),
        ] = None,
        dimensions: Annotated[
            str | None,
            typer.Option("--dimensions", "-d", help="Dimensions subset (comma-sep)"),
        ] = None,
        session_id: Annotated[
            str | None,
            typer.Option("--session-id", "-s", help="Session ID for workflow continuity"),
        ] = None,
        output: Annotated[
            str | None,
            typer.Option("--output", "-o", help="Output format: json|table|markdown|yaml"),
        ] = None,
        stream: Annotated[
            bool,
            typer.Option("--stream/--no-stream", help="Show streaming progress"),
        ] = True,
    ) -> None:
        """Deep LLM assessment of top candidates (Gate 3).

        HARD GATE ENFORCEMENT: Only repos that passed Gate 1+2 will be
        assessed. The command will reject unqualified repos with an error.

        This is the most expensive operation — uses LLM tokens per repo.
        Budget control is enforced: max tokens per repo and per day.

        Examples:
            ghdisc deep-eval --pool-id abc123 --max-repos 10 --budget-tokens 100000
            ghdisc deep-eval --repo-urls "https://github.com/o/r1,https://github.com/o/r2" --stream
        """
        # Must specify either pool-id or repo-urls
        if not pool_id and not repo_urls:
            exit_with_error("Must specify either --pool-id or --repo-urls")

        # ... implementation pattern:
        # 1. Load settings
        # 2. Initialize AssessmentOrchestrator
        # 3. If pool_id: get shortlist from screening results
        # 4. Hard gate check: verify repos passed Gate 1+2
        # 5. Run assessment with streaming progress (Rich Progress)
        # 6. Format output
```

**Verifica**: `ghdisc deep-eval --pool-id X --max-repos 5 --stream` mostra progress bar e risultati. `ghdisc deep-eval --repo-urls "..." --output json` produce JSON.

---

## 10) Task 8.5 — Comando `rank`

### cli/rank.py

```python
from __future__ import annotations

from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    """Register the rank command."""

    @app.command(
        name="rank",
        help="Rank repositories using anti-star bias scoring.",
        rich_help_panel="Pipeline",
    )
    async def rank(
        domain: Annotated[
            str | None,
            typer.Option("--domain", "-d", help="Domain for ranking (e.g., library, cli, ml_lib)"),
        ] = None,
        top: Annotated[
            int,
            typer.Option("--top", "-t", help="Number of top repos to show"),
        ] = 20,
        min_confidence: Annotated[
            float,
            typer.Option("--min-confidence", help="Minimum confidence threshold"),
        ] = 0.3,
        min_value_score: Annotated[
            float,
            typer.Option("--min-value-score", help="Minimum value score (anti-star bias)"),
        ] = 0.0,
        session_id: Annotated[
            str | None,
            typer.Option("--session-id", "-s", help="Session ID for workflow continuity"),
        ] = None,
        output: Annotated[
            str | None,
            typer.Option("--output", "-o", help="Output format: json|table|markdown|yaml"),
        ] = None,
    ) -> None:
        """Rank repositories using anti-star bias scoring.

        Repositories are ranked within their domain (intra-domain ranking).
        Hidden gems (low stars, high quality) rank above popular mediocrity.
        The value_score formula (quality_score / log10(stars + 10)) identifies
        repos that are technically excellent but not yet widely known.

        Examples:
            ghdisc rank --domain library --top 20 --output table
            ghdisc rank --session-id abc123 --min-value-score 0.5 --output json
        """
        # ... implementation:
        # 1. Load scored repos from FeatureStore (by session or domain)
        # 2. Run Ranker.rank() with domain and filters
        # 3. Format and output
```

**Verifica**: `ghdisc rank --domain library --top 10` mostra tabella con ranking. Hidden gems visibili. `--output json` produce JSON parsabile.

---

## 11) Task 8.6 — Comando `export`

### cli/export.py

```python
from __future__ import annotations

from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    """Register the export command."""

    @app.command(
        name="export",
        help="Export session results in JSON, CSV, or Markdown format.",
        rich_help_panel="Pipeline",
    )
    async def export_cmd(
        session_id: Annotated[
            str | None,
            typer.Option("--session-id", "-s", help="Session to export"),
        ] = None,
        pool_id: Annotated[
            str | None,
            typer.Option("--pool-id", "-p", help="Pool to export (alternative to session)"),
        ] = None,
        format: Annotated[
            str,
            typer.Option("--format", "-f", help="Export format: json|csv|markdown"),
        ] = "json",
        output: Annotated[
            str,
            typer.Option("--output", "-o", help="Output file path (default: stdout)"),
        ] = "-",
        domain: Annotated[
            str | None,
            typer.Option("--domain", "-d", help="Filter by domain"),
        ] = None,
        include_details: Annotated[
            bool,
            typer.Option("--include-details/--no-include-details", help="Include full dimension breakdown"),
        ] = False,
    ) -> None:
        """Export session results in JSON, CSV, or Markdown format.

        Examples:
            ghdisc export --session-id abc123 --format json --output results.json
            ghdisc export --pool-id pool456 --format csv --output report.csv
            ghdisc export --session-id abc123 --format markdown --include-details
        """
        # ... implementation:
        # 1. Load session or pool data
        # 2. Collect scored/ranked repos
        # 3. Format according to requested format
        # 4. Write to file or stdout
```

**Verifica**: `ghdisc export --session-id X --format json --output results.json` crea file JSON. `ghdisc export --session-id X --format csv` stampa CSV su stdout.

---

## 12) Task 8.7 — Output Formatting Module

### cli/formatters.py

Modulo centrale per formattare output in 4 formati: JSON, tabella (Rich), Markdown, YAML-like.

```python
from __future__ import annotations

import csv
import io
import json
from collections.abc import Sequence
from typing import Any

from rich.console import Console
from rich.table import Table

from github_discovery.cli.app import cli_state


def format_output(
    data: Any,
    format: str,
    output_type: str,
) -> str:
    """Format data for CLI output.

    Args:
        data: Data to format (Pydantic model, dict, or list)
        format: Output format (json, table, markdown, yaml)
        output_type: Type hint for formatters (discovery, screening, assessment, ranking, session, export)

    Returns:
        Formatted string for console output.
    """
    normalized = _normalize_data(data)

    if format == "json":
        return _format_json(normalized)
    elif format == "table":
        return _format_table(normalized, output_type)
    elif format == "markdown":
        return _format_markdown(normalized, output_type)
    elif format == "yaml":
        return _format_yaml(normalized)
    else:
        msg = f"Unknown output format: {format}"
        raise ValueError(msg)


def _normalize_data(data: Any) -> dict[str, Any] | list[dict[str, Any]]:
    """Convert Pydantic models or other data to dicts."""
    if hasattr(data, "model_dump"):
        return data.model_dump(mode="json")
    if isinstance(data, list):
        return [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in data
        ]
    return data  # type: ignore[return-value]


def _format_json(data: Any) -> str:
    """Format as indented JSON."""
    return json.dumps(data, indent=2, default=str)


def _format_table(data: Any, output_type: str) -> str:
    """Format as Rich Table.

    Uses Rich Console to render a table to string.
    The output is captured via Console(file=StringIO).
    """
    console = Console(file=io.StringIO(), no_color=cli_state.no_color, width=120)

    table_builders: dict[str, Any] = {
        "discovery": _build_discovery_table,
        "screening": _build_screening_table,
        "assessment": _build_assessment_table,
        "ranking": _build_ranking_table,
        "session": _build_session_table,
        "session_list": _build_session_list_table,
    }

    builder = table_builders.get(output_type, _build_generic_table)
    table = builder(data)
    console.print(table)

    return console.file.getvalue()  # type: ignore[return-value]


def _build_ranking_table(data: dict[str, Any]) -> Table:
    """Build Rich Table for ranking results."""
    table = Table(title="Repository Ranking", show_lines=True)
    table.add_column("#", style="bold cyan", width=4)
    table.add_column("Repository", style="bold", width=40)
    table.add_column("Value Score", style="green", width=12)
    table.add_column("Quality", width=10)
    table.add_column("Stars", justify="right", width=8)
    table.add_column("Domain", width=12)
    table.add_column("Gem", width=6)

    repos = data if isinstance(data, list) else data.get("ranked_repos", data.get("repos", []))
    for i, repo in enumerate(repos, 1):
        is_gem = repo.get("is_hidden_gem", False)
        gem_marker = "💎" if is_gem else ""
        table.add_row(
            str(i),
            str(repo.get("full_name", repo.get("repo", ""))),
            f"{repo.get('value_score', 0.0):.3f}",
            f"{repo.get('quality_score', repo.get('overall_score', 0.0)):.2f}",
            str(repo.get("stars", 0)),
            str(repo.get("domain", "")),
            gem_marker,
        )
    return table


def _build_discovery_table(data: dict[str, Any]) -> Table:
    """Build Rich Table for discovery results."""
    table = Table(title="Discovered Candidates", show_lines=True)
    table.add_column("#", style="bold cyan", width=4)
    table.add_column("Repository", style="bold", width=40)
    table.add_column("Score", width=8)
    table.add_column("Language", width=12)
    table.add_column("Stars", justify="right", width=8)
    table.add_column("Channel", width=12)

    candidates = data.get("candidates", data) if isinstance(data, dict) else data
    if isinstance(candidates, list):
        for i, c in enumerate(candidates[:50], 1):  # Show max 50 in table
            table.add_row(
                str(i),
                str(c.get("full_name", "")),
                f"{c.get('discovery_score', 0.0):.2f}",
                str(c.get("language", "")),
                str(c.get("stars", 0)),
                str(c.get("source_channel", "")),
            )
    return table


def _build_screening_table(data: dict[str, Any]) -> Table:
    """Build Rich Table for screening results."""
    table = Table(title="Screening Results", show_lines=True)
    table.add_column("Repository", style="bold", width=40)
    table.add_column("Gate 1", width=10)
    table.add_column("Gate 1 Score", width=12)
    table.add_column("Gate 2", width=10)
    table.add_column("Gate 2 Score", width=12)
    table.add_column("Pass", width=8)
    # ... populate rows
    return table


def _build_assessment_table(data: dict[str, Any]) -> Table:
    """Build Rich Table for assessment results."""
    table = Table(title="Deep Assessment Results", show_lines=True)
    table.add_column("#", style="bold cyan", width=4)
    table.add_column("Repository", style="bold", width=35)
    table.add_column("Overall", width=10)
    table.add_column("Confidence", width=10)
    table.add_column("Gate 3", width=8)
    table.add_column("Top Dimension", width=15)
    table.add_column("Weak Dimension", width=15)
    # ... populate rows
    return table


def _build_session_table(data: dict[str, Any]) -> Table:
    """Build Rich Table for session details."""
    table = Table(title="Session Details", show_lines=False)
    table.add_column("Property", style="bold cyan", width=20)
    table.add_column("Value", width=60)
    table.add_row("Session ID", str(data.get("session_id", "")))
    table.add_row("Name", str(data.get("name", "")))
    table.add_row("Status", str(data.get("status", "")))
    table.add_row("Discovered", str(data.get("discovered_repo_count", 0)))
    table.add_row("Screened", str(data.get("screened_repo_count", 0)))
    table.add_row("Assessed", str(data.get("assessed_repo_count", 0)))
    table.add_row("Created", str(data.get("created_at", "")))
    return table


def _build_session_list_table(data: dict[str, Any]) -> Table:
    """Build Rich Table for session list."""
    table = Table(title="Sessions", show_lines=True)
    table.add_column("Session ID", style="bold", width=36)
    table.add_column("Name", width=20)
    table.add_column("Status", width=12)
    table.add_column("Discovered", justify="right", width=12)
    table.add_column("Screened", justify="right", width=10)
    table.add_column("Assessed", justify="right", width=10)
    table.add_column("Created", width=20)
    # ... populate rows from session list
    return table


def _build_generic_table(data: Any) -> Table:
    """Fallback table builder for unknown data types."""
    table = Table(title="Results")
    if isinstance(data, dict):
        for key, value in data.items():
            table.add_column(str(key))
        table.add_row(*[str(v) for v in data.values()])
    return table


def _format_markdown(data: Any, output_type: str) -> str:
    """Format as Markdown table or document."""
    # ... Markdown table generation using stdlib
    lines: list[str] = []
    if isinstance(data, dict):
        lines.append(f"# {output_type.replace('_', ' ').title()}")
        lines.append("")
        for key, value in data.items():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                # Render as table
                headers = list(value[0].keys())
                lines.append(f"## {key}")
                lines.append("")
                lines.append("| " + " | ".join(headers) + " |")
                lines.append("| " + " | ".join(["---" for _ in headers]) + " |")
                for item in value:
                    lines.append("| " + " | ".join(str(item.get(h, "")) for h in headers) + " |")
                lines.append("")
            else:
                lines.append(f"- **{key}**: {value}")
    return "\n".join(lines)


def _format_yaml(data: Any) -> str:
    """Format as YAML-like output (no pyyaml dependency).

    Produces a simple indented output that looks like YAML
    but uses json.dumps for complex values.
    """
    return json.dumps(data, indent=2, default=str)  # YAML-like via JSON indent
```

**Verifica**: Ogni formato produce output leggibile e parsabile. Table rendering con Rich funziona correttamente. JSON round-trip.

---

## 13) Task 8.8 — Comando `mcp serve` (GIÀ IMPLEMENTATO)

Questo comando è già implementato in `cli.py` (Phase 7, task 7.13 Wave E). Sarà spostato in `cli/mcp_serve.py` durante il refactor.

### cli/mcp_serve.py

```python
from __future__ import annotations

from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    """Register MCP serve command."""

    @app.command(name="serve")
    async def serve(
        transport: str = typer.Option("stdio", "--transport", "-t", help="Transport: stdio or http"),
        host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host for HTTP transport"),
        port: int = typer.Option(8080, "--port", "-p", help="Port for HTTP transport"),
    ) -> None:
        """Start the MCP server with the specified transport."""
        from github_discovery.cli.utils import get_settings

        settings = get_settings()
        settings.mcp.transport = transport
        if host != "127.0.0.1":
            settings.mcp.host = host
        if port != 8080:
            settings.mcp.port = port

        from github_discovery.mcp.server import serve as mcp_serve

        mcp_serve(settings)
```

**Verifica**: `ghdisc mcp serve --transport stdio` avvia MCP server. `python -m github_discovery mcp serve` funziona ancora.

---

## 14) Task 8.9 — Comandi Sessione Agentica

### cli/session.py

```python
from __future__ import annotations

from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    """Register session management commands."""

    @app.command(name="create")
    async def create(
        name: Annotated[str, typer.Argument(help="Human-readable session name")] = "",
    ) -> None:
        """Create a new discovery session.

        Sessions enable progressive deepening: discover in one invocation,
        screen in the next, assess in a third — all sharing the same session.

        Example:
            ghdisc session create --name "ml-search"
        """
        from github_discovery.cli.utils import get_console, get_settings, resolve_output_format
        from github_discovery.mcp.session import SessionManager

        settings = get_settings()
        mgr = SessionManager(settings.mcp.session_store_path)
        await mgr.initialize()
        try:
            session = await mgr.create(name=name)
            console = get_console()
            console.print(f"[green]Created session:[/green] {session.session_id}")
            console.print(f"  Name: {session.name or '(unnamed)'}")
            console.print(f"  Use --session-id {session.session_id} with other commands")
        finally:
            await mgr.close()

    @app.command(name="list")
    async def list_sessions(
        status: Annotated[
            str | None,
            typer.Option("--status", help="Filter by status: created, screening, assessing, completed"),
        ] = None,
        limit: Annotated[
            int,
            typer.Option("--limit", "-n", help="Max sessions to show"),
        ] = 10,
    ) -> None:
        """List active or completed sessions.

        Example:
            ghdisc session list --status completed --limit 20
        """
        # ... load and display sessions via SessionManager

    @app.command(name="resume")
    async def resume(
        session_id: Annotated[str, typer.Argument(help="Session ID to resume")],
    ) -> None:
        """Resume an existing session and show its state.

        Displays the session's current progress: how many repos discovered,
        screened, and assessed. Suggests the next step in the workflow.

        Example:
            ghdisc session resume abc123-def456
        """
        # ... load session, display state, suggest next command

    @app.command(name="show")
    async def show(
        session_id: Annotated[str, typer.Argument(help="Session ID to inspect")],
        output: Annotated[
            str | None,
            typer.Option("--output", "-o", help="Output format: json|table|markdown"),
        ] = None,
    ) -> None:
        """Show detailed session state.

        Example:
            ghdisc session show abc123 --output json
        """
        # ... load full session with associated results
```

**Verifica**: `ghdisc session create --name "test"` crea sessione. `ghdisc session list` mostra sessioni. `ghdisc session resume <id>` mostra stato e suggerisce prossimo step.

---

## 15) Task 8.10 — CLI MCP Config Generator (GIÀ IMPLEMENTATO)

Questo comando è già implementato in `cli.py` (Phase 7). Sarà spostato in `cli/mcp_config.py` durante il refactor.

### cli/mcp_config.py

```python
from __future__ import annotations

from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    """Register MCP init-config command."""

    @app.command(name="init-config")
    async def init_config(
        target: str = typer.Option("kilo", "--target", "-t", help="Target: kilo, opencode, claude"),
        output: str = typer.Option("-", "--output", "-o", help="Output file path (default: stdout)"),
    ) -> None:
        """Generate MCP client configuration for agent integration."""
        # ... same implementation as current cli.py init_config command
```

**Verifica**: `ghdisc mcp init-config --target kilo` produce configurazione JSON valida.

---

## 16) Task 8.11 — CLI Streaming Output

### cli/progress_display.py

Modulo per visualizzare progresso di operazioni lunghe (discovery, screening, assessment) usando Rich Progress + Live.

```python
from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from github_discovery.cli.app import cli_state


def _create_progress() -> Progress:
    """Create a styled Rich Progress bar for CLI operations.

    Uses Context7-verified Rich Progress pattern:
    SpinnerColumn + TextColumn + BarColumn + TaskProgressColumn + TimeRemainingColumn
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(elapsed_when_finished=True),
        TimeElapsedColumn(),
        console=Console(stderr=True, no_color=cli_state.no_color),
        transient=False,
    )


async def display_discovery_progress(
    settings: Any,
    query: str,
    channels: list[str] | None,
    max_candidates: int,
    session_id: str | None,
    languages: list[str] | None,
) -> None:
    """Display streaming progress for discovery operation.

    Shows:
    - Progress bar per channel
    - Live candidate count
    - Top 5 candidates so far
    """
    from github_discovery.discovery.orchestrator import DiscoveryOrchestrator
    from github_discovery.discovery.pool import PoolManager

    console = Console(stderr=True, no_color=cli_state.no_color)
    pool_mgr = PoolManager()
    orch = DiscoveryOrchestrator(settings, pool_mgr)

    with _create_progress() as progress:
        task = progress.add_task(
            f"[cyan]Discovering[/cyan] '{query}'",
            total=None,  # Indeterminate until we know
        )

        try:
            result = await orch.discover(
                query=query,
                channels=channels or settings.discovery.default_channels,
                max_candidates=max_candidates,
            )

            progress.update(task, total=max_candidates, completed=result.total_count)

            # Show results summary
            console.print()
            console.print(
                Panel(
                    f"[green]Discovered {result.total_count} candidates[/green]\n"
                    f"Channels: {', '.join(result.channels_used)}\n"
                    f"Pool ID: {result.pool_id}",
                    title="Discovery Complete",
                )
            )

            # Show top 5 table
            if result.candidates:
                table = Table(title="Top 5 Candidates", show_lines=True)
                table.add_column("#", style="bold cyan", width=4)
                table.add_column("Repository", style="bold")
                table.add_column("Score", width=8)
                table.add_column("Language", width=12)
                table.add_column("Stars", justify="right")

                for i, c in enumerate(result.candidates[:5], 1):
                    table.add_row(
                        str(i),
                        c.full_name,
                        f"{c.discovery_score:.2f}",
                        c.language or "",
                        str(c.stars),
                    )
                console.print(table)

            console.print()
            console.print(
                f"[dim]Next: ghdisc screen --pool-id {result.pool_id} --gate both[/dim]"
            )

        finally:
            await pool_mgr.close()


async def display_screening_progress(
    settings: Any,
    pool_id: str,
    gate_level: str,
    min_gate1: float | None,
    min_gate2: float | None,
    session_id: str | None,
) -> None:
    """Display streaming progress for screening operation."""
    # Similar pattern: Rich Progress + Live table updates
    # Shows: candidates screened / total, pass/fail count per gate
    ...


async def display_assessment_progress(
    settings: Any,
    repo_urls: list[str],
    dimensions: list[str] | None,
    budget_tokens: int | None,
    session_id: str | None,
) -> None:
    """Display streaming progress for deep assessment operation.

    Shows:
    - Progress bar with repos assessed / total
    - Token budget remaining
    - Current repo being assessed
    - Live results as they complete
    """
    # Rich Progress with multiple tasks:
    # - Main progress (repos)
    # - Budget tracker (tokens used / total)
    ...
```

**Verifica**: Con `--stream` (default), operazioni lunghe mostrano progress bar e risultati intermedi. Con `--no-stream`, output è singolo blocco al completamento.

---

## 17) Sequenza di implementazione — Waves

### Wave A: Foundation (Task 8.1 + 8.7 + 8.11)

**Priorità**: Critica — tutto il resto dipende da questi moduli

1. Aggiungere dipendenza `rich>=13.0` a `pyproject.toml`
2. Creare `src/github_discovery/cli/` package
3. Implementare `cli/__init__.py`, `cli/app.py` (app factory con callback globale)
4. Implementare `cli/utils.py` (async_runner, settings, console helpers)
5. Implementare `cli/formatters.py` (JSON, Table, Markdown, YAML formatters)
6. Implementare `cli/progress_display.py` (Rich Progress + Live streaming)
7. Aggiornare `__main__.py` per importare da `cli/app.py`
8. Aggiornare `pyproject.toml` scripts entry point
9. Rimuovere vecchio `cli.py` monolitico
10. Aggiungere ruff per-file-ignores per `cli/` (PLC0415, PLR2004)
11. Test: 20 unit tests (formatters, utils, app factory)

### Wave B: Pipeline Commands (Task 8.2 + 8.3 + 8.5)

**Priorità**: Alta — comandi principali del pipeline

1. Implementare `cli/discover.py` (discover command)
2. Implementare `cli/screen.py` (screen command)
3. Implementare `cli/rank.py` (rank command)
4. Test: 18 unit tests (param parsing, output formatting, service mocking)

### Wave C: Advanced Commands (Task 8.4 + 8.6 + 8.9)

**Priorità**: Alta — completano la pipeline CLI

1. Implementare `cli/deep_eval.py` (deep-eval command con hard gate + budget)
2. Implementare `cli/export.py` (export JSON/CSV/Markdown)
3. Implementare `cli/session.py` (create, list, resume, show)
4. Test: 22 unit tests (deep-eval gate enforcement, export formats, session CRUD)

### Wave D: MCP Refactor + Integration (Task 8.8 + 8.10)

**Priorità**: Media — refactoring di codice esistente

1. Spostare `mcp serve` da `cli.py` a `cli/mcp_serve.py`
2. Spostare `mcp init-config` da `cli.py` a `cli/mcp_config.py`
3. Rimuovere vecchio `cli.py`
4. Verificare retro-compatibilità: `python -m github_discovery` e `ghdisc` funzionano
5. Test: 8 integration tests (end-to-end CLI → service → output)

---

## 18) Test plan

### File di test

```
tests/unit/cli/
├── __init__.py
├── conftest.py                    # Fixtures: mock settings, mock services, mock consoles
├── test_app.py                    # App factory, callback, global options (6 tests)
├── test_utils.py                  # async_runner, comma parser, settings loader (8 tests)
├── test_formatters.py             # JSON, Table, Markdown, YAML formatters (14 tests)
├── test_discover.py               # Discover command parsing and output (6 tests)
├── test_screen.py                 # Screen command with gate levels (6 tests)
├── test_deep_eval.py              # Deep-eval with hard gate enforcement (8 tests)
├── test_rank.py                   # Rank command with domain filtering (6 tests)
├── test_export.py                 # Export formats: JSON, CSV, Markdown (8 tests)
├── test_session.py                # Session CRUD commands (8 tests)
├── test_progress_display.py       # Streaming display helpers (6 tests)
└── test_integration.py            # End-to-end CLI→service→output (8 tests)
```

### Totale: ~84 test

| Modulo | Test | Focus |
|--------|------|-------|
| `test_app.py` | 6 | App creation, callback global state, version command |
| `test_utils.py` | 8 | async_runner, resolve_output_format, comma parser, exit_with_error |
| `test_formatters.py` | 14 | 4 formati × 3 data types + edge cases |
| `test_discover.py` | 6 | Param parsing, service mock, output format, stream toggle |
| `test_screen.py` | 6 | Gate levels, thresholds, pass/fail display |
| `test_deep_eval.py` | 8 | Hard gate enforcement, budget control, repo selection |
| `test_rank.py` | 6 | Domain filter, value score, hidden gem display |
| `test_export.py` | 8 | JSON/CSV/Markdown formats, file vs stdout |
| `test_session.py` | 8 | CRUD operations, status filter, resume suggestions |
| `test_progress_display.py` | 6 | Progress bar creation, Live display, streaming |
| `test_integration.py` | 8 | E2E: discover→screen→rank, session workflow |

### Strategy di mocking

- **Orchestratori**: `unittest.mock.AsyncMock` per `DiscoveryOrchestrator`, `ScreeningOrchestrator`, `AssessmentOrchestrator`
- **Pool/FeatureStore**: Mock con dati di test pre-costruiti
- **Console output**: Catturare con `Console(file=StringIO())` per verificare formato
- **Typer testing**: `typer.testing.CliRunner` per invocare comandi CLI nei test

---

## 19) Criteri di accettazione

### Per comando

| Comando | Criterio | Verifica |
|---------|----------|----------|
| `ghdisc discover --query "test" --output json` | Output JSON valido con candidates | `jq .` passa |
| `ghdisc discover --query "test" --output table` | Tabella Rich con candidates | Output leggibile in terminale |
| `ghdisc discover --query "test" --stream` | Progress bar visibile durante discovery | Rich Progress rendering |
| `ghdisc screen --pool-id X --gate 1 --output table` | Tabella con pass/fail Gate 1 | Colonne corrette |
| `ghdisc screen --pool-id X --gate both` | Entrambi i gate eseguiti | Gate 1 e Gate 2 scores |
| `ghdisc deep-eval --pool-id X --max-repos 5` | Hard gate: solo candidati Gate 1+2 pass | Messaggio errore per non qualificati |
| `ghdisc deep-eval --pool-id X --budget-tokens 5000` | Budget rispettato | Nessun overflow |
| `ghdisc rank --domain library --top 10` | Ranking intra-domain, hidden gems visibili | 💎 marker |
| `ghdisc rank --output json` | JSON parsabile con ranked repos | `jq .` passa |
| `ghdisc export --session-id X --format json --output out.json` | File JSON creato | File exists + valid JSON |
| `ghdisc export --session-id X --format csv` | CSV su stdout con header | `head -1` mostra colonne |
| `ghdisc session create --name "test"` | Sessione creata, ID mostrato | Session ID in output |
| `ghdisc session list` | Lista sessioni con stato | Tabella sessioni |
| `ghdisc session resume <id>` | Stato sessione + suggerimento prossimo step | "Next: ghdisc screen..." |
| `ghdisc mcp serve --transport stdio` | MCP server avviabile | Server responds |
| `ghdisc mcp init-config --target kilo` | JSON config per Kilocode | Valid JSON + github-discovery key |
| `ghdisc version` | Versione mostrata | "github-discovery 0.1.0-alpha" |
| `ghdisc --help` | Help completo con tutti i comandi | Tutti i comandi elencati |
| `python -m github_discovery --help` | Equivalente a `ghdisc --help` | Stesso output |

### Generici

| Criterio | Verifica |
|----------|----------|
| `make ci` verde (ruff + mypy --strict + pytest) | 0 errori |
| Nuovi test ≥ 80 | ~84 test pianificati |
| Totale test ≥ 1200 | 1118 (attuali) + 84 (nuovi) ≈ 1202 |
| `pip install -e .` funziona | Entry point `ghdisc` disponibile |
| Retro-compatibilità | `python -m github_discovery` e `ghdisc` funzionano identici |
| Zero dipendenze rotte | `pip check` passa |
| mypy --strict passa su tutti i nuovi file | 0 errori |

---

## 20) Rischi e mitigazioni

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| Refactor CLI rompe entry point esistente | Alto — utenti non possono avviare il tool | Test retro-compatibilità espliciti: `python -m github_discovery --help` e `ghdisc --help` funzionano |
| Rich dipendenza pesante per installazione | Basso — CLI è optional | Rich è già dipendenza indiretta di typer (via click-rich); aggiunta esplicita è trasparente |
| Async commands in typer non supportati nativamente | Medio — comandi falliscono | Wrapper `asyncio.run()` in `cli/utils.py`; testato e documentato nel piano |
| Streaming output non funziona in pipe (`|` o `>`) | Medio — output corrotto in CI | Rilevare `sys.stdout.isatty()` e disabilitare Rich quando in pipe; fallback a plain JSON |
| Output YAML senza pyyaml | Basso — formato non-standard | Documentare che "yaml" output è JSON-like; aggiungere pyyaml solo se richiesto |
| Comandi lunghi senza timeout | Basso — CLI bloccata | Aggiungere `--timeout` globale (default 300s); `asyncio.wait_for()` wrapper |
| Session resume non trova dati | Medio — sessione persa | SQLite backend già testato (Phase 7); verificare path resolution cross-platform |

---

## 21) Verifica Context7

### Typer (Context7: `/websites/typer_tiangolo`)

**Verificato e confermato**:
- ✅ `typer.Typer(rich_markup_mode="rich")` per Rich markup in help strings
- ✅ `@app.callback()` per global options con `invoke_without_command=False` (default)
- ✅ `context_settings={"help_option_names": ["-h", "--help"]}` per -h shortcut
- ✅ `rich_help_panel` per categorizzare comandi in help output
- ✅ `Annotated[str, typer.Option("--flag", help="...")]` per type-safe options
- ✅ `Annotated[str, typer.Argument(help="...")]` per positional args
- ✅ `typer.Typer(no_args_is_help=True)` per mostrare help senza argomenti
- ✅ `app.add_typer(sub_app, name="group")` per sottogruppi (mcp, session)
- ✅ Typer non supporta async nativamente — serve wrapper `asyncio.run()`

### Rich (Context7: `/textualize/rich`)

**Verificato e confermato**:
- ✅ `Console(no_color=True)` per disabilitare colori (CI/pipe)
- ✅ `Table(title=..., show_lines=True)` con `add_column()` + `add_row()`
- ✅ `Progress(SpinnerColumn(), TextColumn(), BarColumn(), TaskProgressColumn(), TimeRemainingColumn())`
- ✅ `Live(renderable, console=..., refresh_per_second=4)` per display dinamico
- ✅ `Markdown(content)` per rendering Markdown nel terminale
- ✅ `Console(file=StringIO())` per catturare output nei test
- ✅ `Progress(transient=False)` per mantenere output dopo completamento
- ✅ `Panel(content, title=...)` per raggruppare output

### Nuova dipendenza

```toml
# pyproject.toml — dependencies
dependencies = [
    # ... existing ...
    "rich>=13.0",
]
```

---

*Stato documento: Draft v1 — Phase 8 CLI Implementation Plan*
*Data: 2026-04-24*
*Basato su: roadmap Phase 8, blueprint §21, wiki articles (agent-workflows, session-workflow, mcp-native-design)*
*Context7 verification: typer 0.12+ (2026-04-24), rich 13+ (2026-04-24)*
