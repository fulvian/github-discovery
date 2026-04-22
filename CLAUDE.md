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