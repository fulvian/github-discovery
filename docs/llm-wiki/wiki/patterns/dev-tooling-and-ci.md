---
Title: Python Development Tooling Configuration (Context7 Verified)
Topic: patterns
Sources: Context7 verification of Pydantic v2, pydantic-settings, structlog, ruff, pytest, pre-commit; Brave Search best practices research
Raw: [phase0-plan.md](../../plans/phase0-implementation-plan.md)
Updated: 2026-04-22
Confidence: high
---

# Python Development Tooling Configuration (Context7 Verified)

Verified patterns and configurations for the Python development toolchain, sourced from official documentation via Context7 and community best practices research (2025-2026).

## Key Points

- **hatchling** as build backend is PEP 621 compliant and recommended by pytest documentation for src layout
- **pydantic-settings v2** uses `SettingsConfigDict` (not `class Config:`) and supports `env_nested_delimiter="__"`
- **structlog** stdlib integration uses `ProcessorFormatter` wrapping `StreamHandler`, not direct rendering
- **ruff** rule selection follows principle of maximum safety with pragmatic exclusions (D100, D104, PLR0913)
- **pytest** import-mode=importlib required for src layout
- **pre-commit** v5 with ruff-pre-commit and mypy mirrors

## pydantic-settings v2 Patterns (Context7 Verified)

### SettingsConfigDict (Not class Config)

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GHDISC_",          # All env vars start with GHDISC_
        env_file=".env",               # Read from .env file
        env_file_encoding="utf-8",
        env_nested_delimiter="__",     # GHDISC_GITHUB__TOKEN for nested
    )
    
    debug: bool = False
    github: GitHubSettings = Field(default_factory=GitHubSettings)
```

**Key insight**: Sub-settings have their own `env_prefix` (e.g., `GHDISC_GITHUB_`), enabling both `GHDISC_GITHUB_TOKEN` and `GHDISC_GITHUB__TOKEN` patterns.

### Nested Settings with Field(default_factory=)

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GHDISC_",
        env_nested_delimiter="__",
    )
    
    github: GitHubSettings = Field(default_factory=GitHubSettings)
    # NOT: github: GitHubSettings = GitHubSettings()  # evaluates at import time
```

**Pattern**: Always use `Field(default_factory=...)` for sub-settings to avoid shared state between instances.

### AliasChoices for Flexible Env Vars

```python
from pydantic import Field, AliasChoices

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GHDISC_")
    
    # Accept multiple env var names
    redis_dsn: RedisDsn = Field(
        default="redis://localhost:6379",
        validation_alias=AliasChoices("GHDISC_REDIS_URL", "GHDISC_REDIS_DSN"),
    )
```

## structlog Configuration (Context7 Verified)

### Production-Ready Configuration

```python
import sys
import logging
import structlog

def configure_logging(log_level: str = "INFO", debug: bool = False) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )
    
    shared_processors = [
        structlog.contextvars.merge_contextvars,  # Request-scoped context
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        structlog.processors.CallsiteParameterAdder({
            structlog.processors.CallsiteParameter.FILENAME,
            structlog.processors.CallsiteParameter.FUNC_NAME,
            structlog.processors.CallsiteParameter.LINENO,
        }),
    ]
    
    renderer = (
        structlog.dev.ConsoleRenderer()  # Pretty for TTY/debug
        if debug or sys.stderr.isatty()
        else structlog.processors.JSONRenderer()  # JSON for production
    )
    
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
```

**Key pattern**: `structlog.stdlib.LoggerFactory()` for interop with `logging` natively. The `ProcessorFormatter` wraps structlog processors for stdlib `logging.Handler`.

### Using contextvars for Request-Scoped Logging

```python
import structlog

# Bind context variables in a request/session
async with structlog.contextvars.bound_contextvars(
    session_id=session.id,
    repo_url=repo.url,
    gate_level=2,
):
    log.info("Screening candidate")  # Includes session_id, repo_url, gate_level
```

## ruff Configuration (Context7 Verified)

### pyproject.toml Configuration

```toml
[tool.ruff]
line-length = 99  # Override from default 88 per AGENTS.md
target-version = "py312"
src = ["src"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "UP", "B", "SIM", "TCH", "RUF", "C4", "ERA", "PL", "PTH", "A", "ANN", "D", "S", "T20"]
ignore = ["D100", "D104", "D203", "D213", "PLR0913", "ANN101", "ANN102"]

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

**Key decisions**:
- `line-length = 99` per AGENTS.md convention (ruff default is 88)
- `required-imports = ["from __future__ import annotations"]` enforced by isort
- `D203/D213` ignored to avoid conflict (using D212/D211 instead)
- `ANN101/ANN102` ignored (self/cls type annotations unnecessary)
- `PLR0913` ignored (many args common in API models)

## pytest Configuration (Context7 Verified)

```toml
[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short --strict-markers --import-mode=importlib"
markers = [
    "integration: marks integration tests",
    "slow: marks slow tests",
    "agentic: marks agentic/MCP integration tests",
]
asyncio_mode = "auto"
filterwarnings = [
    "error",
    "ignore::DeprecationWarning",
]
```

**Key pattern**: `--import-mode=importlib` is REQUIRED for src layout per pytest documentation. Without it, tests may import the wrong package.

## pre-commit Configuration (Context7 Verified)

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

**Key pattern**: `additional_dependencies` in mypy hook is essential — without pydantic stubs, mypy strict will fail on Pydantic models.

## See Also

- [Technology Stack Decisions](../patterns/tech-stack.md)
- [Phase 0 Implementation](../patterns/phase0-implementation.md)
- [Operational Rules](../patterns/operational-rules.md)