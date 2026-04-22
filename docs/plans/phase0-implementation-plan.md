# GitHub Discovery — Phase 0 Implementation Plan

## Meta

- **Stato**: Draft v1
- **Data**: 2026-04-22
- **Riferimento roadmap**: `docs/roadmaps/github-discovery_foundation_roadmap.md` — Phase 0
- **Riferimento blueprint**: `docs/foundation/github-discovery_foundation_blueprint.md`
- **Durata stimata**: 1-2 settimane
- **Milestone**: M0 — Foundation Ready

---

## Indice

1. [Obiettivo](#1-obiettivo)
2. [Task Overview](#2-task-overview)
3. [Architettura della directory di progetto](#3-architettura-della-directory-di-progetto)
4. [Task 0.1 — Inizializzazione struttura progetto](#4-task-01--inizializzazione-struttura-progetto)
5. [Task 0.2 — Configurazione tooling sviluppo](#5-task-02--configurazione-tooling-sviluppo)
6. [Task 0.3 — Moduli `__init__` e `config.py`](#6-task-03--moduli-__init__-e-configpy)
7. [Task 0.4 — Sistema di logging strutturato](#7-task-04--sistema-di-logging-strutturato)
8. [Task 0.5 — Gerarchia eccezioni personalizzate](#8-task-05--gerarchia-eccezioni-personalizzate)
9. [Task 0.6 — Makefile](#9-task-06--makefile)
10. [Task 0.7 — CI baseline (GitHub Actions)](#10-task-07--ci-baseline-github-actions)
11. [Task 0.8 — AGENTS.md & CLAUDE.md aggiornamento](#11-task-08--agentsmd--claudemd-aggiornamento)
12. [Task 0.9 — Modelli sessione agentica](#12-task-09--modelli-sessione-agentica)
13. [Task 0.10 — MCP tool spec models](#13-task-010--mcp-tool-spec-models)
14. [Task 0.11 — `.kilo/mcp.json` template](#14-task-011--kilomcpjson-template)
15. [Sequenza di implementazione](#15-sequenza-di-implementazione)
16. [Test plan](#16-test-plan)
17. [Criteri di accettazione](#17-criteri-di-accettazione)
18. [Rischi e mitigazioni](#18-rischi-e-mitigazioni)
19. [Verifica Context7 completata](#19-verifica-context7-completata)

---

## 1) Obiettivo

Creare la struttura progettuale eseguibile con tooling configurato, CI verde e baseline verificabile. Al completamento della Phase 0:

- Il progetto è installabile via `pip install -e ".[dev]"`
- `python -c "import github_discovery"` funziona
- `make install && make lint && make test` sono verdi
- CI GitHub Actions passa su ogni push
- I modelli base (config, exceptions, logging, session, MCP spec) sono definiti e tipizzati
- La configurazione MCP template per Kilocode CLI è in place

---

## 2) Task Overview

| Task ID | Task | Priorità | Dipendenze | Output verificabile |
|---------|------|----------|------------|---------------------|
| 0.1 | Inizializzazione struttura progetto | Critica | — | `pip install -e .` funziona |
| 0.2 | Configurazione tooling sviluppo | Critica | 0.1 | `make lint && make test` verdi |
| 0.3 | Config module (`config.py`) | Critica | 0.1 | Settings istanziabile da env |
| 0.4 | Sistema di logging | Critica | 0.1 | Log JSON con campi contestuali |
| 0.5 | Gerarchia eccezioni | Critica | 0.1 | mypy --strict passa |
| 0.6 | Makefile | Alta | 0.1, 0.2 | `make install && make lint && make test` |
| 0.7 | CI baseline (GitHub Actions) | Alta | 0.2 | CI verde su push |
| 0.8 | AGENTS.md & CLAUDE.md aggiornamento | Alta | 0.2 | Comandi documentati funzionano |
| 0.9 | Modelli sessione agentica | Alta | 0.3 | Sessione creabile e persistibile |
| 0.10 | MCP tool spec models | Alta | 0.3 | Ogni tool MCP ha spec documentata |
| 0.11 | `.kilo/mcp.json` template | Media | 0.9, 0.10 | Kilo mostra server configurato |

---

## 3) Architettura della directory di progetto

La structure segue il pattern **src layout** (consigliato da pytest e Python Packaging Authority):

```
github-discovery/
├── src/
│   └── github_discovery/
│       ├── __init__.py                  # Versione e exports pubblici
│       ├── config.py                    # pydantic-settings (GHDISC_ prefix)
│       ├── exceptions.py                # Gerarchia eccezioni custom
│       ├── logging.py                   # structlog configuration
│       ├── models/
│       │   ├── __init__.py
│       │   ├── enums.py                 # DomainType, ScoreDimension, GateLevel, DiscoveryChannel
│       │   ├── session.py               # SessionState, SessionConfig, ProgressInfo
│       │   └── mcp_spec.py              # MCPToolSpec, AgentWorkflowConfig
│       ├── discovery/                   # Phase 2 (vuoto per ora)
│       │   └── __init__.py
│       ├── screening/                   # Phase 3 (vuoto per ora)
│       │   └── __init__.py
│       ├── assessment/                  # Phase 4 (vuoto per ora)
│       │   └── __init__.py
│       ├── scoring/                     # Phase 5 (vuoto per ora)
│       │   └── __init__.py
│       ├── api/                         # Phase 6 (vuoto per ora)
│       │   └── __init__.py
│       ├── mcp/                         # Phase 7 (vuoto per ora)
│       │   ├── __init__.py
│       │   ├── server.py                # FastMCP server placeholder
│       │   ├── tools/                   # MCP tools (vuoto per ora)
│       │   │   └── __init__.py
│       │   ├── resources/              # MCP resources (vuoto per ora)
│       │   │   └── __init__.py
│       │   ├── prompts.py              # Agent skill definitions placeholder
│       │   ├── session.py              # Session management (placeholder)
│       │   ├── progress.py             # Progress notifications (placeholder)
│       │   ├── output_format.py        # Context-efficient output (placeholder)
│       │   ├── github_client.py        # GitHub MCP composition (placeholder)
│       │   ├── transport.py            # STDIO + streamable-http (placeholder)
│       │   └── config.py               # MCP configuration (GHDISC_MCP_*)
│       ├── workers/                     # Phase 6 (vuoto per ora)
│       │   └── __init__.py
│       └── cli.py                       # CLI entry point placeholder (typer)
├── tests/
│   ├── __init__.py
│   ├── conftest.py                      # Shared fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_config.py
│   │   ├── test_exceptions.py
│   │   ├── test_logging.py
│   │   ├── test_models/
│   │   │   ├── __init__.py
│   │   │   ├── test_enums.py
│   │   │   ├── test_session.py
│   │   │   └── test_mcp_spec.py
│   │   └── test_mcp/
│   │       ├── __init__.py
│   │       └── test_server.py
│   ├── integration/
│   │   ├── __init__.py
│   │   └── test_imports.py
│   └── agentic/                         # Phase 9 (vuoto per ora)
│       └── __init__.py
├── .github/
│   └── workflows/
│       └── ci.yml
├── .kilo/
│   └── mcp.json.template
├── .pre-commit-config.yaml
├── .gitignore                           # Già esistente
├── pyproject.toml                       # Main config file
├── Makefile
├── AGENTS.md                            # Già esistente — aggiornare
├── README.md                            # Già esistente — aggiornare
├── docs/
│   ├── foundation/                      # Già esistente
│   ├── roadmaps/                        # Già esistente
│   ├── plans/                           # Questo documento
│   └── llm-wiki/                        # Già esistente
├── findings.md                          # Già esistente
├── task_plan.md                         # Già esistente
└── progress.md                          # Già esistente
```

**Note sulla struttura**:
- **src layout**: Il package principale è in `src/github_discovery/`. Questo previene import accidentali del codice non installato (pytest best practice).
- **Subpackage vuoti**: Si creano i subpackage per discovery, screening, assessment, scoring, api, mcp, workers con solo `__init__.py` per stabilire la struttura. Verranno popolati nelle fasi successive.
- **MCP subpackage**: Già strutturato con i moduli previsti nel blueprint §21 (server, tools, resources, prompts, session, progress, output_format, github_client, transport, config).
- **tests**: Mirror della struttura src con test unitari, integration e agentic (per Phase 9).

---

## 4) Task 0.1 — Inizializzazione struttura progetto

### Obiettivo
Creare `pyproject.toml` (hatchling), directory `src/github_discovery/`, `tests/` e rendere il progetto installabile.

### pyproject.toml (estratto chiave)

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "github-discovery"
version = "0.1.0-alpha"
description = "MCP-native agentic discovery engine for high-quality GitHub repositories, independent of popularity"
readme = "README.md"
requires-python = ">=3.12"
license = {text = "MIT"}
authors = [
    {name = "GitHub Discovery Team"},
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Software Development :: Quality Assurance",
    "Topic :: Software Development :: Libraries :: Python Modules",
]
dependencies = [
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "httpx>=0.28",
    "structlog>=24.1",
    "typer>=0.12",
    "mcp>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "respx>=0.21",
    "ruff>=0.11",
    "mypy>=1.15",
    "pre-commit>=3.7",
]
integration = [
    "pytest-httpx>=0.30",
]

[project.scripts]
ghdisc = "github_discovery.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/github_discovery"]
```

**Giustificazioni**:
- **hatchling** come build backend: lightweight, PEP 621 compliant, supporto dependency groups nativo, usato da pytest docs ufficiali.
- **Python >=3.12**: come specificato in AGENTS.md (type aliases, match statements, f-strings moderni).
- **pydantic v2 + pydantic-settings**: per modelli dati e configurazione con env prefix `GHDISC_`.
- **httpx** con supporto async per chiamate GitHub API.
- **structlog** per logging strutturato JSON.
- **typer** per CLI con subcomandi (Phase 8).
- **mcp** (Python SDK) per FastMCP server (Phase 7).
- **respx** invece di `pytest-httpx` per mocking httpx (più maturo per async).

### __init__.py principale

```python
"""GitHub Discovery — MCP-native agentic discovery engine."""

from __future__ import annotations

__version__ = "0.1.0-alpha"
```

### Verifica

```bash
pip install -e ".[dev]"
python -c "import github_discovery; print(github_discovery.__version__)"
# Output: 0.1.0-alpha
```

---

## 5) Task 0.2 — Configurazione tooling sviluppo

### Obiettivo
Configurare Ruff (lint+format, line-length=99), mypy --strict, pytest, pre-commit hooks.

### Ruff configuration (in pyproject.toml)

```toml
[tool.ruff]
line-length = 99
target-version = "py312"
src = ["src"]

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # Pyflakes
    "I",      # isort
    "UP",     # pyupgrade
    "B",      # flake8-bugbear
    "SIM",    # flake8-simplify
    "TCH",    # flake8-type-checking
    "RUF",    # Ruff-specific rules
    "C4",     # flake8-comprehensions
    "ERA",    # eradicate (commented-out code)
    "PL",     # Pylint
    "PTH",    # flake8-use-pathlib
    "A",      # flake8-builtins
    "ANN",    # flake8-annotations
    "D",      # pydocstyle
    "S",      # flake8-bandit (security)
    "T20",    # flake8-print (no print statements)
]
ignore = [
    "D100",   # Missing docstring in public module
    "D104",   # Missing docstring in public package
    "D203",   # one-blank-line-before-class (conflict with D211)
    "D213",   # multi-line-summary-second-line (conflict with D212)
    "PLR0913",# Too many arguments (common in API models)
    "ANN101", # Missing type annotation for self (unnecessary)
    "ANN102", # Missing type annotation for cls (unnecessary)
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*" = ["S101", "D", "ANN", "PLR2004", "TCH"]
"__init__.py" = ["F401"]

[tool.ruff.lint.isort]
required-imports = ["from __future__ import annotations"]
known-first-party = ["github_discovery"]
combine-as-imports = true

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
docstring-code-format = true
docstring-code-line-length = 79
```

### mypy configuration (in pyproject.toml)

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_unreachable = true
extra_checks = true

[[tool.mypy.overrides]]
module = ["mcp.*", "respx.*", "typer.*"]
ignore_missing_imports = true
```

### pytest configuration (in pyproject.toml)

```toml
[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short --strict-markers --import-mode=importlib"
markers = [
    "integration: marks integration tests (deselect with '-m \"not integration\"')",
    "slow: marks slow tests (deselect with '-m \"not slow\"')",
    "agentic: marks agentic/MCP integration tests",
]
asyncio_mode = "auto"
filterwarnings = [
    "error",
    "ignore::DeprecationWarning",
]
```

### pre-commit configuration (`.pre-commit-config.yaml`)

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-json
      - id: check-merge-conflict
      - id: check-added-large-files
        args: ['--maxkb=500']
      - id: debug-statements
      - id: detect-private-key

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.4
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.15.0
    hooks:
      - id: mypy
        additional_dependencies:
          - pydantic>=2.7
          - pydantic-settings>=2.3
          - types-structlog
        args: [--strict]
```

### Verifica

```bash
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/ --strict
pytest tests/ -v
pre-commit run --all-files
```

---

## 6) Task 0.3 — Moduli `__init__` e `config.py`

### Obiettivo
Configurazione tipizzata con `pydantic-settings` con env prefix `GHDISC_` e defaults per sviluppo locale.

### Implementazione: `src/github_discovery/config.py`

```python
"""GitHub Discovery configuration via environment variables with GHDISC_ prefix."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GitHubSettings(BaseSettings):
    """GitHub API connection settings."""

    model_config = SettingsConfigDict(
        env_prefix="GHDISC_GITHUB_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    token: str = Field(default="", description="GitHub personal access token")
    api_base_url: str = Field(
        default="https://api.github.com",
        description="GitHub API base URL",
    )
    graphql_url: str = Field(
        default="https://api.github.com/graphql",
        description="GitHub GraphQL API URL",
    )
    request_timeout: int = Field(default=30, description="HTTP request timeout in seconds")
    max_concurrent_requests: int = Field(default=10, description="Max concurrent API requests")


class DiscoverySettings(BaseSettings):
    """Discovery channel settings."""

    model_config = SettingsConfigDict(
        env_prefix="GHDISC_DISCOVERY_",
        env_file=".env",
    )

    max_candidates: int = Field(default=1000, description="Max candidates per discovery query")
    default_channels: list[str] = Field(
        default=["search", "registry", "curated"],
        description="Default discovery channels",
    )


class ScreeningSettings(BaseSettings):
    """Screening gate settings."""

    model_config = SettingsConfigDict(
        env_prefix="GHDISC_SCREENING_",
        env_file=".env",
    )

    min_gate1_score: float = Field(default=0.4, description="Minimum Gate 1 score to pass")
    min_gate2_score: float = Field(default=0.5, description="Minimum Gate 2 score to pass")
    hard_gate_enforcement: bool = Field(
        default=True,
        description="Hard gate: no Gate 3 without Gate 1+2 pass",
    )


class AssessmentSettings(BaseSettings):
    """Deep assessment (Gate 3) settings."""

    model_config = SettingsConfigDict(
        env_prefix="GHDISC_ASSESSMENT_",
        env_file=".env",
    )

    max_tokens_per_repo: int = Field(
        default=50000,
        description="Max LLM tokens per repo assessment",
    )
    max_tokens_per_day: int = Field(
        default=500000,
        description="Max LLM tokens per day budget",
    )
    llm_provider: str = Field(
        default="openai",
        description="LLM provider (openai, anthropic, local)",
    )
    llm_model: str = Field(
        default="gpt-4o",
        description="LLM model identifier",
    )
    cache_ttl_hours: int = Field(
        default=24,
        description="Cache TTL for assessment results (hours)",
    )


class MCPSettings(BaseSettings):
    """MCP server settings."""

    model_config = SettingsConfigDict(
        env_prefix="GHDISC_MCP_",
        env_file=".env",
    )

    transport: str = Field(
        default="stdio",
        description="MCP transport: stdio or http",
    )
    host: str = Field(default="127.0.0.1", description="MCP HTTP host")
    port: int = Field(default=8080, description="MCP HTTP port")
    max_context_tokens: int = Field(
        default=2000,
        description="Max tokens per MCP tool invocation output",
    )
    session_backend: str = Field(
        default="sqlite",
        description="Session backend: sqlite or redis",
    )
    read_only: bool = Field(
        default=True,
        description="Read-only mode for analysis pipelines",
    )


class Settings(BaseSettings):
    """Root application settings composing all sub-settings."""

    model_config = SettingsConfigDict(
        env_prefix="GHDISC_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

    app_name: str = "github-discovery"
    version: str = "0.1.0-alpha"
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Log level (DEBUG, INFO, WARNING, ERROR)")

    github: GitHubSettings = Field(default_factory=GitHubSettings)
    discovery: DiscoverySettings = Field(default_factory=DiscoverySettings)
    screening: ScreeningSettings = Field(default_factory=ScreeningSettings)
    assessment: AssessmentSettings = Field(default_factory=AssessmentSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)
```

**Giustificazioni**:
- **pydantic-settings** con `SettingsConfigDict`: approach moderno per Pydantic v2, supporta env prefix, .env file, nested delimiter.
- **Sub-settings con factory proprie**: `GitHubSettings`, `ScreeningSettings`, etc. hanno ciascuno il proprio env prefix, permettendo configurazione granulare. Es.: `GHDISC_GITHUB_TOKEN`, `GHDISC_SCREENING_MIN_GATE1_SCORE`, `GHDISC_MCP_TRANSPORT`.
- **Defaults per sviluppo locale**: tutti i campi hanno defaults sensati per funzionare senza configurazione aggiuntiva in dev.
- **Nested delimiter `__`**: permette override come `GHDISC_GITHUB__TOKEN` per sub-settings (alternativa a sub-prefix).

### Test: `tests/unit/test_config.py`

```python
"""Tests for configuration module."""

from __future__ import annotations

import os

import pytest

from github_discovery.config import Settings, GitHubSettings, MCPSettings


class TestSettings:
    """Test configuration loading."""

    def test_default_settings_instantiable(self) -> None:
        """Settings can be instantiated with defaults."""
        settings = Settings()
        assert settings.app_name == "github-discovery"
        assert settings.debug is False
        assert settings.log_level == "INFO"

    def test_github_settings_defaults(self) -> None:
        """GitHub settings have sensible defaults."""
        settings = GitHubSettings()
        assert settings.api_base_url == "https://api.github.com"
        assert settings.request_timeout == 30
        assert settings.max_concurrent_requests == 10

    def test_settings_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings can be loaded from environment variables."""
        monkeypatch.setenv("GHDISC_DEBUG", "true")
        monkeypatch.setenv("GHDISC_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("GHDISC_GITHUB_TOKEN", "ghp_test123")
        settings = Settings()
        assert settings.debug is True
        assert settings.log_level == "DEBUG"
        assert settings.github.token == "ghp_test123"

    def test_mcp_settings_defaults(self) -> None:
        """MCP settings default to stdio transport."""
        settings = MCPSettings()
        assert settings.transport == "stdio"
        assert settings.max_context_tokens == 2000
        assert settings.read_only is True

    def test_screening_settings_hard_gate(self) -> None:
        """Hard gate enforcement is True by default."""
        from github_discovery.config import ScreeningSettings
        settings = ScreeningSettings()
        assert settings.hard_gate_enforcement is True
        assert settings.min_gate1_score == 0.4
        assert settings.min_gate2_score == 0.5
```

### Verifica

```bash
GHDISC_GITHUB_TOKEN=test python -c "from github_discovery.config import Settings; s = Settings(); print(s.model_dump())"
mypy src/github_discovery/config.py --strict
pytest tests/unit/test_config.py -v
```

---

## 7) Task 0.4 — Sistema di logging strutturato

### Obiettivo
Configurare `structlog` con JSON output per produzione e console pretty per sviluppo. Aggiungere contesto request/repo.

### Implementazione: `src/github_discovery/logging.py`

```python
"""Structured logging configuration for GitHub Discovery."""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(log_level: str = "INFO", debug: bool = False) -> None:
    """Configure structlog for structured JSON logging.

    In debug mode (or when stderr is a TTY), uses ConsoleRenderer
    for human-readable output. In production, uses JSONRenderer for
    machine-parseable logs.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        debug: Whether debug mode is enabled (uses pretty console output).
    """
    # Set stdlib logging level
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            },
        ),
    ]

    if debug or sys.stderr.isatty():
        # Pretty console output for development
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        # JSON output for production
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            *shared_processors,
            renderer,
        ],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Optional logger name (typically module name).

    Returns:
        A structlog BoundLogger for structured, context-aware logging.
    """
    return structlog.get_logger(name)


# Module-level logger for convenience
log = get_logger("github_discovery")
```

**Giustificazioni**:
- **structlog JSONRenderer** per produzione: log machine-parseable per aggregazione (ELK, Datadog).
- **ConsoleRenderer** per sviluppo: output leggibile in TTY, con tracebacks ANSI colors.
- **Contextvars**: supporto per contesto request-scoped (correlation ID, repo URL, session ID).
- **CallsiteParameterAdder**: aggiunge filename, function name, line number per debugging.
- **stdlib LoggerFactory**: interoperabilità con logging standard Python per librerie che usano `logging` nativo.

### Test: `tests/unit/test_logging.py`

```python
"""Tests for structured logging configuration."""

from __future__ import annotations

import json

from github_discovery.logging import configure_logging, get_logger


class TestLogging:
    """Test logging configuration."""

    def test_configure_logging_json(self, capsys) -> None:
        """JSON logging produces valid JSON output."""
        configure_logging(log_level="DEBUG", debug=False)
        logger = get_logger("test")
        logger.info("test_event", key="value")
        # Verify output is valid JSON (structural check, not exact match)

    def test_configure_logging_debug_mode(self) -> None:
        """Debug mode uses ConsoleRenderer."""
        configure_logging(log_level="DEBUG", debug=True)
        logger = get_logger("test")
        # Should not raise
        logger.info("debug_event")

    def test_get_logger_returns_bound_logger(self) -> None:
        """get_logger returns a BoundLogger."""
        configure_logging()
        logger = get_logger("test_module")
        assert logger is not None
```

### Verifica

```bash
python -c "
from github_discovery.logging import configure_logging, get_logger
configure_logging(log_level='DEBUG', debug=True)
log = get_logger('test')
log.info('hello', repo='user/repo', score=0.85)
"
mypy src/github_discovery/logging.py --strict
```

---

## 8) Task 0.5 — Gerarchia eccezioni personalizzate

### Obiettivo
Gerarchia di eccezioni custom con contesto (repo URL, dimensione, gate level). Mai raise bare `Exception`.

### Implementazione: `src/github_discovery/exceptions.py`

```python
"""Custom exception hierarchy for GitHub Discovery.

Never raise bare Exception — always use the appropriate domain exception
with context (repo URL, dimension, gate level, etc.).
"""

from __future__ import annotations


class GitHubDiscoveryError(Exception):
    """Base exception for all GitHub Discovery errors."""

    def __init__(self, message: str, *, context: dict[str, object] | None = None) -> None:
        self.context = context or {}
        super().__init__(message)

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f" [{ctx_str}]")
        return "".join(parts)


# --- Domain Exceptions ---


class ConfigurationError(GitHubDiscoveryError):
    """Raised when configuration is invalid or missing."""


class DiscoveryError(GitHubDiscoveryError):
    """Raised when candidate discovery fails."""


class ScreeningError(GitHubDiscoveryError):
    """Raised when quality screening fails."""

    def __init__(
        self,
        message: str,
        *,
        gate_level: int | None = None,
        repo_url: str | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        ctx = context or {}
        if gate_level is not None:
            ctx["gate_level"] = gate_level
        if repo_url is not None:
            ctx["repo_url"] = repo_url
        super().__init__(message, context=ctx)
        self.gate_level = gate_level
        self.repo_url = repo_url


class AssessmentError(GitHubDiscoveryError):
    """Raised when deep technical assessment fails."""

    def __init__(
        self,
        message: str,
        *,
        repo_url: str | None = None,
        dimension: str | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        ctx = context or {}
        if repo_url is not None:
            ctx["repo_url"] = repo_url
        if dimension is not None:
            ctx["dimension"] = dimension
        super().__init__(message, context=ctx)
        self.repo_url = repo_url
        self.dimension = dimension


class ScoringError(GitHubDiscoveryError):
    """Raised when scoring or ranking fails."""

    def __init__(
        self,
        message: str,
        *,
        domain: str | None = None,
        repo_url: str | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        ctx = context or {}
        if domain is not None:
            ctx["domain"] = domain
        if repo_url is not None:
            ctx["repo_url"] = repo_url
        super().__init__(message, context=ctx)
        self.domain = domain
        self.repo_url = repo_url


class SessionError(GitHubDiscoveryError):
    """Raised when session management fails."""


class MCPError(GitHubDiscoveryError):
    """Raised when MCP tool execution fails."""


class RateLimitError(GitHubDiscoveryError):
    """Raised when GitHub API rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        *,
        reset_at: str | None = None,
        remaining: int | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        ctx = context or {}
        if reset_at is not None:
            ctx["reset_at"] = reset_at
        if remaining is not None:
            ctx["remaining"] = remaining
        super().__init__(message, context=ctx)
        self.reset_at = reset_at
        self.remaining = remaining


class BudgetExceededError(GitHubDiscoveryError):
    """Raised when LLM token budget is exceeded."""

    def __init__(
        self,
        message: str,
        *,
        budget_type: str | None = None,
        budget_limit: int | None = None,
        budget_used: int | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        ctx = context or {}
        if budget_type is not None:
            ctx["budget_type"] = budget_type
        if budget_limit is not None:
            ctx["budget_limit"] = budget_limit
        if budget_used is not None:
            ctx["budget_used"] = budget_used
        super().__init__(message, context=ctx)
        self.budget_type = budget_type
        self.budget_limit = budget_limit
        self.budget_used = budget_used


class HardGateViolationError(GitHubDiscoveryError):
    """Raised when hard gate enforcement prevents Gate 3 without Gate 1+2 pass."""

    def __init__(
        self,
        message: str,
        *,
        repo_url: str | None = None,
        gate_passed: int | None = None,
        gate_required: int | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        ctx = context or {}
        if repo_url is not None:
            ctx["repo_url"] = repo_url
        if gate_passed is not None:
            ctx["gate_passed"] = gate_passed
        if gate_required is not None:
            ctx["gate_required"] = gate_required
        super().__init__(message, context=ctx)
        self.repo_url = repo_url
        self.gate_passed = gate_passed
        self.gate_required = gate_required
```

### Test: `tests/unit/test_exceptions.py`

```python
"""Tests for custom exception hierarchy."""

from __future__ import annotations

import pytest

from github_discovery.exceptions import (
    AssessmentError,
    BudgetExceededError,
    ConfigurationError,
    GitHubDiscoveryError,
    HardGateViolationError,
    RateLimitError,
    ScreeningError,
    ScoringError,
)


class TestExceptionHierarchy:
    """Test exception hierarchy and context."""

    def test_base_exception_with_context(self) -> None:
        """Base exception includes context in string representation."""
        exc = GitHubDiscoveryError("test error", context={"key": "value"})
        assert "test error" in str(exc)
        assert "key=value" in str(exc)

    def test_screening_error_gate_context(self) -> None:
        """ScreeningError includes gate level and repo URL."""
        exc = ScreeningError(
            "Gate 1 failed",
            gate_level=1,
            repo_url="https://github.com/user/repo",
        )
        assert exc.gate_level == 1
        assert exc.repo_url == "https://github.com/user/repo"
        assert "gate_level=1" in str(exc)

    def test_hard_gate_violation(self) -> None:
        """HardGateViolationError captures gate violation context."""
        exc = HardGateViolationError(
            "Cannot proceed to Gate 3",
            repo_url="https://github.com/user/repo",
            gate_passed=1,
            gate_required=2,
        )
        assert exc.gate_passed == 1
        assert exc.gate_required == 2
        assert "gate_passed=1" in str(exc)

    def test_budget_exceeded_error(self) -> None:
        """BudgetExceededError captures budget context."""
        exc = BudgetExceededError(
            "Token budget exceeded",
            budget_type="daily",
            budget_limit=500000,
            budget_used=510000,
        )
        assert exc.budget_type == "daily"
        assert exc.budget_limit == 500000

    def test_inheritance_chain(self) -> None:
        """All domain exceptions inherit from GitHubDiscoveryError."""
        assert issubclass(ConfigurationError, GitHubDiscoveryError)
        assert issubclass(ScreeningError, GitHubDiscoveryError)
        assert issubclass(AssessmentError, GitHubDiscoveryError)
        assert issubclass(ScoringError, GitHubDiscoveryError)
        assert issubclass(RateLimitError, GitHubDiscoveryError)
        assert issubclass(HardGateViolationError, GitHubDiscoveryError)
```

### Verifica

```bash
mypy src/github_discovery/exceptions.py --strict
pytest tests/unit/test_exceptions.py -v
```

---

## 9) Task 0.6 — Makefile

### Implementazione: `Makefile`

```makefile
.PHONY: install install-dev test lint format typecheck clean run help

# Default target
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install the package
	pip install -e .

install-dev: ## Install with dev dependencies
	pip install -e ".[dev]"
	pre-commit install

test: ## Run all tests
	pytest tests/ -v --tb=short

test-unit: ## Run unit tests only
	pytest tests/unit/ -v -m "not integration and not slow"

test-integration: ## Run integration tests
	pytest tests/integration/ -v -m "integration"

test-cov: ## Run tests with coverage report
	pytest tests/ --cov=github_discovery --cov-report=term-missing --cov-report=html

lint: ## Run ruff linter
	ruff check src/ tests/

lint-fix: ## Run ruff linter with auto-fix
	ruff check --fix src/ tests/

format: ## Run ruff formatter
	ruff format src/ tests/

format-check: ## Check ruff formatting
	ruff format --check src/ tests/

typecheck: ## Run mypy type checker
	mypy src/ --strict

ci: ## Run all CI checks (lint + format check + typecheck + test)
	ruff check src/ tests/
	ruff format --check src/ tests/
	mypy src/ --strict
	pytest tests/ -v --tb=short

clean: ## Remove build artifacts
	rm -rf build/ dist/ *.egg-info .eggs/
	rm -rf .mypy_cache/ .ruff_cache/ .pytest_cache/
	rm -rf htmlcov/ .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

run: ## Run CLI locally (requires install)
	python -m github_discovery --help
```

### Verifica

```bash
make install-dev && make ci
```

---

## 10) Task 0.7 — CI baseline (GitHub Actions)

### Implementazione: `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint-and-typecheck:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]

    steps:
      - uses: actions/checkout@v5

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Lint with ruff
        run: ruff check src/ tests/

      - name: Check formatting with ruff
        run: ruff format --check src/ tests/

      - name: Type check with mypy
        run: mypy src/ --strict

  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]

    steps:
      - uses: actions/checkout@v5

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Run tests
        run: pytest tests/ -v --tb=short -m "not integration and not slow"

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          fail_ci: false
```

### Verifica

- Push su branch `main` o PR su `main` triggera CI.
- CI verde = badge verde su README.

---

## 11) Task 0.8 — AGENTS.md & CLAUDE.md aggiornamento

### Obiettivo
Aggiornare AGENTS.md con i comandi build/lint/test effettivi. Creare CLAUDE.md per Claude Code.

#### AGENTS.md — Sezione Build/Lint/Test Commands

La sezione esistente va aggiornata con i comandi reali che ora funzionano:

```bash
# Install dependencies (dev + runtime)
make install-dev

# Run all tests
make test

# Run a single test file
pytest tests/unit/test_config.py -v

# Run a single test by name
pytest tests/unit/test_config.py::TestSettings::test_default_settings_instantiable -v

# Run only unit tests (exclude integration/slow)
pytest tests/unit/ -m "not integration and not slow" -v

# Lint everything
make lint

# Format check
make format-check

# Type check
make typecheck

# Run full CI locally
make ci

# Run the CLI locally (after install)
python -m github_discovery --help

# Run MCP server locally
python -m github_discovery.mcp serve --transport stdio

# Run MCP server with HTTP transport
python -m github_discovery.mcp serve --transport http --port 8080
```

#### CLAUDE.md (nuovo file)

```markdown
# CLAUDE.md

## Build & Test Commands
- Install: `make install-dev`
- Run all tests: `make test`
- Run unit tests: `pytest tests/unit/ -v`
- Lint: `make lint`
- Format: `make format`
- Type check: `make typecheck`
- Full CI: `make ci`

## Code Style
- Python 3.12+, type hints required, mypy --strict enforced
- Line length: 99 chars (ruff)
- Trailing commas in multi-line collections
- f-strings over .format()
- snake_case for variables/functions, PascalCase for classes/models
- Import order: stdlib → third-party → local (enforced by ruff isort)
- `from __future__ import annotations` at top of all files

## Key Rules
- Never raise bare Exception — use domain exceptions from exceptions.py
- Stars are context only, never a primary ranking signal
- Hard gate: no Gate 3 without Gate 1+2 pass
- All public functions must have full type annotations
- Use structlog for all logging — never use print() for diagnostics
```

### Verifica

I comandi documentati in AGENTS.md e CLAUDE.md funzionano effettivamente.

---

## 12) Task 0.9 — Modelli sessione agentica

### Obiettivo
Definire `SessionState`, `SessionConfig`, `ProgressInfo` come modelli Pydantic per supportare workflow agentici cross-sessione (Blueprint §21.4).

### Implementazione: `src/github_discovery/models/session.py`

```python
"""Session and progress models for agentic workflow support.

These models enable cross-session progressive deepening (Blueprint §21.4):
an agent can create a session, discover candidates, screen them,
and resume in a later session without losing state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    """Status of a discovery session."""

    CREATED = "created"
    DISCOVERING = "discovering"
    SCREENING = "screening"
    ASSESSING = "assessing"
    RANKING = "ranking"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SessionConfig(BaseModel):
    """Per-session configuration that overrides global defaults.

    Agents can configure session-specific thresholds, budgets,
    and domain preferences.
    """

    min_gate1_score: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Minimum Gate 1 score threshold for this session",
    )
    min_gate2_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum Gate 2 score threshold for this session",
    )
    max_tokens_per_repo: int = Field(
        default=50000,
        gt=0,
        description="Max LLM tokens per repo assessment for this session",
    )
    max_tokens_per_day: int = Field(
        default=500000,
        gt=0,
        description="Max LLM tokens per day budget for this session",
    )
    preferred_domains: list[str] = Field(
        default_factory=list,
        description="Preferred domain types for ranking",
    )
    excluded_channels: list[str] = Field(
        default_factory=list,
        description="Discovery channels to exclude",
    )
    hard_gate_enforcement: bool = Field(
        default=True,
        description="Hard gate: noGate3 without Gate1+2 pass",
    )


class ProgressInfo(BaseModel):
    """Progress notification for long-running operations.

    Used by MCP tools to emit progress notifications (Blueprint §21.6).
    """

    progress_token: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique token for this progress stream",
    )
    progress: float = Field(
        default=0.0,
        ge=0.0,
        description="Current progress value",
    )
    total: float = Field(
        default=100.0,
        ge=0.0,
        description="Total value for progress calculation",
    )
    message: str = Field(
        default="",
        description="Human-readable progress message",
    )
    session_id: str | None = Field(
        default=None,
        description="Associated session ID",
    )


class SessionState(BaseModel):
    """Persistent session state for cross-invocation agentic workflows.

    Session state tracks the progress of a discovery workflow across
    multiple MCP tool invocations and even across sessions.
    """

    session_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique session identifier",
    )
    name: str = Field(
        default="",
        description="Human-readable session name",
    )
    status: SessionStatus = Field(
        default=SessionStatus.CREATED,
        description="Current session status",
    )
    config: SessionConfig = Field(
        default_factory=SessionConfig,
        description="Per-session configuration overrides",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Session creation timestamp (UTC)",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Session last update timestamp (UTC)",
    )
    pool_ids: list[str] = Field(
        default_factory=list,
        description="IDs of candidate pools in this session",
    )
    discovered_repo_count: int = Field(
        default=0,
        ge=0,
        description="Total repos discovered in this session",
    )
    screened_repo_count: int = Field(
        default=0,
        ge=0,
        description="Total repos screened in this session",
    )
    assessed_repo_count: int = Field(
        default=0,
        ge=0,
        description="Total repos deep-assessed in this session",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if session failed",
    )

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc)
```

### Test: `tests/unit/test_models/test_session.py`

```python
"""Tests for session and progress models."""

from __future__ import annotations

from github_discovery.models.session import (
    ProgressInfo,
    SessionConfig,
    SessionState,
    SessionStatus,
)


class TestSessionConfig:
    """Test SessionConfig model."""

    def test_default_config(self) -> None:
        """Default config has sensible values."""
        config = SessionConfig()
        assert config.min_gate1_score == 0.4
        assert config.min_gate2_score == 0.5
        assert config.hard_gate_enforcement is True

    def test_custom_config(self) -> None:
        """Custom config overrides defaults."""
        config = SessionConfig(
            min_gate1_score=0.3,
            max_tokens_per_repo=30000,
            preferred_domains=["library", "cli"],
        )
        assert config.min_gate1_score == 0.3
        assert config.preferred_domains == ["library", "cli"]

    def test_score_validation(self) -> None:
        """Score must be between 0.0 and 1.0."""
        import pytest

        with pytest.raises(ValueError):
            SessionConfig(min_gate1_score=1.5)


class TestSessionState:
    """Test SessionState model."""

    def test_default_state(self) -> None:
        """Default state is CREATED with auto-generated IDs."""
        state = SessionState(name="test-session")
        assert state.name == "test-session"
        assert state.status == SessionStatus.CREATED
        assert len(state.session_id) > 0
        assert state.pool_ids == []

    def test_state_serialization(self) -> None:
        """Session state can serialize to/from JSON."""
        state = SessionState(name="test")
        json_str = state.model_dump_json()
        restored = SessionState.model_validate_json(json_str)
        assert restored.session_id == state.session_id
        assert restored.name == state.name

    def test_touch_updates_timestamp(self) -> None:
        """touch() updates the updated_at field."""
        state = SessionState(name="test")
        old_updated = state.updated_at
        state.touch()
        assert state.updated_at >= old_updated


class TestProgressInfo:
    """Test ProgressInfo model."""

    def test_default_progress(self) -> None:
        """Default progress starts at 0.0."""
        progress = ProgressInfo(message="Starting discovery")
        assert progress.progress == 0.0
        assert progress.total == 100.0
        assert "Starting discovery" in progress.message

    def test_progress_serialization(self) -> None:
        """Progress info serializes to JSON."""
        progress = ProgressInfo(
            progress=42.0,
            total=100.0,
            message="Screened 42/100 candidates",
            session_id="session-123",
        )
        data = progress.model_dump()
        assert data["progress"] == 42.0
        assert data["session_id"] == "session-123"
```

### Verifica

```bash
mypy src/github_discovery/models/session.py --strict
pytest tests/unit/test_models/test_session.py -v
```

---

## 13) Task 0.10 — MCP tool spec models

### Obiettivo
Definire `MCPToolSpec` e `AgentWorkflowConfig` per documentare ogni tool MCP e workflow agentico (Blueprint §21.3, §21.7).

### Implementazione: `src/github_discovery/models/mcp_spec.py`

```python
"""MCP tool and agent workflow specification models.

These models define the contract for each MCP tool and agent workflow,
enabling progressive deepening (Blueprint §21.2) and context-efficient
design (Blueprint §21.8).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class MCPOutputFormat(str, Enum):
    """Supported output formats for MCP tools."""

    SUMMARY = "summary"
    FULL = "full"
    JSON = "json"


class MCPToolSpec(BaseModel):
    """Specification for an MCP tool in the GitHub Discovery system.

    Each tool is documented with its parameters, output schema,
    session awareness, and context budget.
    """

    name: str = Field(description="Tool name (e.g., 'discover_repos')")
    description: str = Field(description="Human-readable tool description")
    parameters_schema: dict[str, object] = Field(
        default_factory=dict,
        description="JSON Schema for tool parameters",
    )
    output_schema: dict[str, object] = Field(
        default_factory=dict,
        description="JSON Schema for tool output",
    )
    session_aware: bool = Field(
        default=True,
        description="Whether the tool supports session_id for cross-session workflows",
    )
    default_output_format: MCPOutputFormat = Field(
        default=MCPOutputFormat.SUMMARY,
        description="Default output format (summary-first for context efficiency)",
    )
    max_context_tokens: int = Field(
        default=2000,
        description="Maximum context tokens per invocation (default output)",
    )
    gate_level: int | None = Field(
        default=None,
        description="Gate level this tool belongs to (0-3), None for management tools",
    )
    category: str = Field(
        description="Tool category: discovery, screening, assessment, ranking, session",
    )


class WorkflowStep(BaseModel):
    """A single step in an agent workflow."""

    tool_name: str = Field(description="MCP tool to invoke")
    description: str = Field(description="What this step accomplishes")
    default_params: dict[str, object] = Field(
        default_factory=dict,
        description="Default parameters for the tool invocation",
    )
    optional: bool = Field(
        default=False,
        description="Whether this step can be skipped",
    )


class AgentWorkflowConfig(BaseModel):
    """Configuration for an agent workflow (MCP prompt/skill).

    Defines a structured multi-step workflow that guides an agent
    through progressive deepening (Blueprint §21.7).
    """

    name: str = Field(description="Workflow name (e.g., 'discover_underrated')")
    description: str = Field(description="Human-readable workflow description")
    steps: list[WorkflowStep] = Field(
        description="Ordered sequence of tool invocations",
    )
    category: str = Field(
        description="Workflow category: discovery, assessment, comparison, security",
    )
    output_format: MCPOutputFormat = Field(
        default=MCPOutputFormat.SUMMARY,
        description="Recommended default output format",
    )


# --- Predefined Tool Specifications ---

DISCOVER_REPOS_SPEC = MCPToolSpec(
    name="discover_repos",
    description="Find candidate repositories matching a query across multiple channels",
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query for repositories"},
            "channels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Discovery channels to use",
            },
            "max_candidates": {"type": "integer", "description": "Max candidates to return"},
            "session_id": {"type": "string", "description": "Session ID for workflow continuity"},
        },
        "required": ["query"],
    },
    session_aware=True,
    max_context_tokens=2000,
    gate_level=0,
    category="discovery",
)

SCREEN_CANDIDATES_SPEC = MCPToolSpec(
    name="screen_candidates",
    description="Screen candidate repositories at specified gate level(s)",
    parameters_schema={
        "type": "object",
        "properties": {
            "pool_id": {"type": "string", "description": "Candidate pool ID"},
            "gate_level": {"type": "string", "description": "Gate level: '1', '2', or 'both'"},
            "min_gate1_score": {"type": "number", "description": "Minimum Gate 1 score threshold"},
            "min_gate2_score": {"type": "number", "description": "Minimum Gate 2 score threshold"},
            "session_id": {"type": "string", "description": "Session ID"},
        },
        "required": ["pool_id", "gate_level"],
    },
    session_aware=True,
    max_context_tokens=2000,
    gate_level=1,
    category="screening",
)

DEEP_ASSESS_SPEC = MCPToolSpec(
    name="deep_assess",
    description="Deep LLM assessment of top candidates (Gate 3) — requires Gate 1+2 pass",
    parameters_schema={
        "type": "object",
        "properties": {
            "repo_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Repository URLs to assess",
            },
            "dimensions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Assessment dimensions to evaluate",
            },
            "budget_tokens": {"type": "integer", "description": "Token budget for this assessment"},
            "session_id": {"type": "string", "description": "Session ID"},
        },
        "required": ["repo_urls"],
    },
    session_aware=True,
    max_context_tokens=2000,
    gate_level=3,
    category="assessment",
)

RANK_REPOS_SPEC = MCPToolSpec(
    name="rank_repos",
    description="Rank repositories within a domain using anti-star bias scoring",
    parameters_schema={
        "type": "object",
        "properties": {
            "domain": {"type": "string", "description": "Domain type for ranking"},
            "min_confidence": {"type": "number", "description": "Minimum confidence score"},
            "min_value_score": {"type": "number", "description": "Minimum value score"},
            "max_results": {"type": "integer", "description": "Max results to return"},
            "session_id": {"type": "string", "description": "Session ID"},
        },
    },
    session_aware=True,
    max_context_tokens=2000,
    gate_level=None,
    category="ranking",
)

# --- Predefined Workflow Configurations ---

DISCOVER_UNDERRATED_WORKFLOW = AgentWorkflowConfig(
    name="discover_underrated",
    description="Find technically excellent repos that are underrated by star count",
    steps=[
        WorkflowStep(
            tool_name="discover_repos",
            description="Discover candidate pool",
            default_params={"max_candidates": 50},
        ),
        WorkflowStep(
            tool_name="screen_candidates",
            description="Screen candidates through Gate 1 and 2",
            default_params={"gate_level": "both"},
        ),
        WorkflowStep(
            tool_name="deep_assess",
            description="Deep assess top candidates",
            default_params={"dimensions": ["code_quality", "architecture", "testing"]},
            optional=True,
        ),
        WorkflowStep(
            tool_name="rank_repos",
            description="Rank with anti-star bias value score",
        ),
        WorkflowStep(
            tool_name="explain_repo",
            description="Explain top findings",
            default_params={"detail_level": "summary"},
            optional=True,
        ),
    ],
    category="discovery",
)

QUICK_QUALITY_CHECK_WORKFLOW = AgentWorkflowConfig(
    name="quick_quality_check",
    description="Quick quality assessment of a specific repository",
    steps=[
        WorkflowStep(
            tool_name="quick_screen",
            description="Quick screen (Gate 1) of repository",
            default_params={"gate_levels": "1"},
        ),
        WorkflowStep(
            tool_name="explain_repo",
            description="Report quality signals",
            default_params={"detail_level": "summary"},
        ),
    ],
    category="assessment",
)
```

### Test: `tests/unit/test_models/test_mcp_spec.py`

```python
"""Tests for MCP tool spec models."""

from __future__ import annotations

from github_discovery.models.mcp_spec import (
    DISCOVER_REPOS_SPEC,
    DEEP_ASSESS_SPEC,
    DISCOVER_UNDERRATED_WORKFLOW,
    MCPToolSpec,
    MCPOutputFormat,
    AgentWorkflowConfig,
    WorkflowStep,
)


class TestMCPToolSpec:
    """Test MCP tool specification model."""

    def test_predefined_specs(self) -> None:
        """Predefined specs are valid and well-formed."""
        assert DISCOVER_REPOS_SPEC.name == "discover_repos"
        assert DISCOVER_REPOS_SPEC.gate_level == 0
        assert DISCOVER_REPOS_SPEC.session_aware is True
        assert DEEP_ASSESS_SPEC.gate_level == 3
        assert DEEP_ASSESS_SPEC.category == "assessment"

    def test_tool_spec_serialization(self) -> None:
        """Tool specs serialize to/from JSON."""
        spec = MCPToolSpec(
            name="test_tool",
            description="A test tool",
            category="testing",
        )
        json_str = spec.model_dump_json()
        restored = MCPToolSpec.model_validate_json(json_str)
        assert restored.name == "test_tool"

    def test_custom_tool_spec(self) -> None:
        """Custom tool specs can be created."""
        spec = MCPToolSpec(
            name="compare_repos",
            description="Compare repositories side-by-side",
            session_aware=True,
            max_context_tokens=3000,
            category="ranking",
        )
        assert spec.default_output_format == MCPOutputFormat.SUMMARY


class TestAgentWorkflowConfig:
    """Test agent workflow configuration model."""

    def test_predefined_workflow(self) -> None:
        """Discover underrated workflow has 5 steps."""
        assert len(DISCOVER_UNDERRATED_WORKFLOW.steps) == 5
        assert DISCOVER_UNDERRATED_WORKFLOW.steps[0].tool_name == "discover_repos"
        assert DISCOVER_UNDERRATED_WORKFLOW.category == "discovery"

    def test_workflow_serialization(self) -> None:
        """Workflow configs serialize to/from JSON."""
        workflow = DISCOVER_UNDERRATED_WORKFLOW
        json_str = workflow.model_dump_json()
        restored = AgentWorkflowConfig.model_validate_json(json_str)
        assert restored.name == "discover_underrated"
        assert len(restored.steps) == 5
```

### Verifica

```bash
mypy src/github_discovery/models/mcp_spec.py --strict
pytest tests/unit/test_models/test_mcp_spec.py -v
```

---

## 14) Task 0.11 — `.kilo/mcp.json` template

### Obiettivo
Creare il template di configurazione MCP per Kilocode CLI con composizione github-discovery + GitHub MCP.

### Implementazione: `.kilo/mcp.json.template`

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

### Implementazione: `.kilo/mcp.json` (config attiva per sviluppo locale)

```json
{
  "mcp": {
    "github-discovery": {
      "type": "local",
      "command": ["python", "-m", "github_discovery.mcp", "serve", "--transport", "stdio"],
      "environment": {
        "GHDISC_GITHUB_TOKEN": "{env:GITHUB_TOKEN}",
        "GHDISC_SESSION_BACKEND": "sqlite",
        "GHDISC_MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

**Note**:
- La config attiva contiene solo github-discovery per sviluppo locale.
- Per produzione, usare il template che include composizione con GitHub MCP.
- `{env:GITHUB_TOKEN}` è una variabile d'ambiente risolta dal client MCP.

### Verifica

```bash
# Verificare che il template sia JSON valido
python -c "import json; json.load(open('.kilo/mcp.json.template'))"
# Verificare che il server MCP placeholder si avvii (verrà implementato in Phase 7)
python -c "import json; json.load(open('.kilo/mcp.json'))"
```

---

## 15) Sequenza di implementazione

L'ordine raccomandato per l'implementazione è:

```
1. 0.1 — pyproject.toml + directory structure + __init__.py
   │
   ├─► 0.3 — config.py (dipende da pydantic-settings installato)
   ├─► 0.5 — exceptions.py
   └─► 0.4 — logging.py (dipende da structlog installato)

2. 0.2 — Ruff + mypy + pytest + pre-commit configuration
   │
   └─► 0.6 — Makefile (dipende su tooling configurato)

3. 0.9 — models/session.py (dipende da config.py e enums)
   │
   └─► 0.10 — models/mcp_spec.py

4. 0.7 — CI (dipende su 0.1-0.6 completati e verdi)

5. 0.8 — AGENTS.md + CLAUDE.md aggiornamento

6. 0.11 — .kilo/mcp.json template (dipende su 0.9-0.10 completati)
```

**Parallelizzazioni possibili**:
- 0.3, 0.4, 0.5 possono procedere in parallelo dopo 0.1.
- 0.9 e 0.10 possono procedere in parallelo dopo 0.3.
- 0.7 (CI) e 0.11 (MCP config) possono procedere in parallelo dopo le dipendenze.

**Bloccanti**:
- 0.1 blocca tutto il resto.
- 0.2 blocca 0.6 e 0.7.
- 0.3 blocca 0.9 e 0.10.

---

## 16) Test plan

### Unit tests (per ogni task)

| Modulo | Test file | Copertura target |
|--------|-----------|-------------------|
| `config.py` | `tests/unit/test_config.py` | Settings defaults, env override, validation |
| `logging.py` | `tests/unit/test_logging.py` | JSON output, debug mode, console renderer |
| `exceptions.py` | `tests/unit/test_exceptions.py` | Context, inheritance, string representation |
| `models/session.py` | `tests/unit/test_models/test_session.py` | Defaults, serialization, validation, touch() |
| `models/mcp_spec.py` | `tests/unit/test_models/test_mcp_spec.py` | Spec validity, serialization, predefined specs |
| `models/enums.py` | `tests/unit/test_models/test_enums.py` | All enum values defined |
| Import smoke test | `tests/integration/test_imports.py` | All modules importable |

### Integration tests

```python
# tests/integration/test_imports.py
"""Smoke test: all modules are importable."""

from __future__ import annotations

import pytest


def test_import_main_package() -> None:
    """Main package is importable."""
    import github_discovery
    assert github_discovery.__version__ == "0.1.0-alpha"


def test_import_config() -> None:
    """Config module is importable."""
    from github_discovery.config import Settings
    assert Settings is not None


def test_import_exceptions() -> None:
    """Exceptions module is importable."""
    from github_discovery.exceptions import GitHubDiscoveryError
    assert GitHubDiscoveryError is not None


def test_import_logging() -> None:
    """Logging module is importable."""
    from github_discovery.logging import configure_logging, get_logger
    assert configure_logging is not None
    assert get_logger is not None


def test_import_session_models() -> None:
    """Session models are importable."""
    from github_discovery.models.session import SessionState, SessionConfig, ProgressInfo
    assert SessionState is not None


def test_import_mcp_spec_models() -> None:
    """MCP spec models are importable."""
    from github_discovery.models.mcp_spec import MCPToolSpec, AgentWorkflowConfig
    assert MCPToolSpec is not None
```

### Coverage target

- **Linee guida**: >80% per modelli, config, exceptions
- **Mypy**: 0 errori con `--strict`
- **Ruff**: 0 errori con configurazione definita

---

## 17) Criteri di accettazione

La Phase 0 è completata quando **tutti** i seguenti criteri sono soddisfatti:

| # | Criterio | Verifica |
|---|----------|----------|
| 1 | Progetto installabile via `pip install -e ".[dev]"` | `python -c "import github_discovery"` funziona |
| 2 | `make lint` passa senza errori | `ruff check src/ tests/` exit code 0 |
| 3 | `make format-check` passa | `ruff format --check src/ tests/` exit code 0 |
| 4 | `make typecheck` passa senza errori | `mypy src/ --strict` exit code 0 |
| 5 | `make test` passa con coverage >80% su modelli | `pytest tests/ -v --cov` verde |
| 6 | `make ci` passa localmente | `make ci` exit code 0 |
| 7 | CI GitHub Actions passa su push | Badge verde su README |
| 8 | `Settings()` istanziabile con defaults | `python -c "from github_discovery.config import Settings; print(Settings().model_dump())"` |
| 9 | `Settings()` istanziabile da env vars | `GHDISC_GITHUB_TOKEN=test python -c "from github_discovery.config import Settings; s=Settings(); assert s.github.token=='test'"` |
| 10 | Logging JSON strutturato funzionante | `python -c "from github_discovery.logging import configure_logging, get_logger; configure_logging(); log=get_logger('test'); log.info('test', key='value')"` |
| 11 | Eccezioni custom con contesto | `python -c "from github_discovery.exceptions import ScreeningError; e=ScreeningError('test', gate_level=1); print(e)"` |
| 12 | Modelli session serializzabili | `python -c "from github_discovery.models.session import SessionState; s=SessionState(name='test'); print(s.model_dump_json())"` |
| 13 | MCP tool specs documentate | `python -c "from github_discovery.models.mcp_spec import DISCOVER_REPOS_SPEC; print(DISCOVER_REPOS_SPEC.name)"` |
| 14 | `.kilo/mcp.json` JSON valido | `python -c "import json; json.load(open('.kilo/mcp.json.template'))"` |
| 15 | Directory struttura completa | `ls src/github_discovery/models/` mostra `enums.py`, `session.py`, `mcp_spec.py` |
| 16 | Pre-commit hooks installati | `pre-commit run --all-files` passa |

---

## 18) Rischi e mitigazioni

| Rischio | Impatto | Probabilità | Mitigazione |
|---------|---------|-------------|-------------|
| mypy --strict trova troppi errori nei subpackage vuoti | Medio | Alta | Iniziare con `__init__.py` minimali; usare `type: ignore` commenti temporanei per placeholder; risolvere gradualmente |
| pydantic-settings nested models non si risolvono da env | Medio | Bassa | Usare `env_prefix` separati per sub-settings; testare env override |
| ruff regole troppo restrittive per project iniziale | Basso | Media | Iniziare con subset `E,W,F,I,UP,B,SIM`; aggiungere regole gradualmente |
| MCP SDK breaking changes tra versioni | Medio | Media | Pin versione SDK nel pyproject.toml; usare `ignore_missing_imports` per moduli MCP nei test iniziali |
| pre-commit hooks lenti | Basso | Media | Configurare `fail_fast: false`; escludere file large; usare ruff che è veloce |

---

## 19) Verifica Context7 completata

| Libreria | Versione riferimento | Fonte | Note |
|----------|---------------------|-------|------|
| Pydantic v2 | 2.x | Context7: `/pydantic/pydantic` | BaseModel, model_validate, model_dump, Field, validators |
| pydantic-settings | 2.x | Context7: `/pydantic/pydantic-settings` | BaseSettings, env_prefix, SettingsConfigDict, nested delimiter |
| MCP Python SDK | 1.x | Context7: `/modelcontextprotocol/python-sdk` | FastMCP, tools, resources, prompts, Context.report_progress |
| structlog | 24.x | Context7: `/hynek/structlog` | JSONRenderer, ConsoleRenderer, stdlib integration, contextvars |
| ruff | 0.11+ | Context7: `/astral-sh/ruff` | lint+format, pyproject.toml config, line-length=99 |
| pytest | 8.x | Context7: `/pytest-dev/pytest` | config in pyproject.toml, markers, async support |
| pre-commit | 5.x | Context7: `/pre-commit/pre-commit.com` | .pre-commit-config.yaml, ruff+mypy hooks |
| hatchling | Latest | Python Packaging Authority | PEP 621 compliant, src layout support |

**Tutte le librerie sono state verificate per compatibilità con Python 3.12+ e tra loro.** Non sono stati identificati conflitti di versione.

---

*Stato documento: Phase 0 Implementation Plan v1 — pronto per implementazione*
*Data: 2026-04-22*
*Basato su: github-discovery_foundation_blueprint.md + roadmap Phase 0 + ricerca Context7*