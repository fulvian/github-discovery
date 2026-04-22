.PHONY: install install-dev test lint format typecheck clean run help

PYTHON ?= .venv/bin/python

# Default target
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install the package
	$(PYTHON) -m pip install -e .

install-dev: ## Install with dev dependencies
	$(PYTHON) -m pip install -e ".[dev]"

test: ## Run all tests
	$(PYTHON) -m pytest tests/ -v --tb=short

test-unit: ## Run unit tests only
	$(PYTHON) -m pytest tests/unit/ -v -m "not integration and not slow"

test-integration: ## Run integration tests
	$(PYTHON) -m pytest tests/integration/ -v -m "integration"

test-cov: ## Run tests with coverage report
	$(PYTHON) -m pytest tests/ --cov=github_discovery --cov-report=term-missing --cov-report=html

lint: ## Run ruff linter
	$(PYTHON) -m ruff check src/ tests/

lint-fix: ## Run ruff linter with auto-fix
	$(PYTHON) -m ruff check --fix src/ tests/

format: ## Run ruff formatter
	$(PYTHON) -m ruff format src/ tests/

format-check: ## Check ruff formatting
	$(PYTHON) -m ruff format --check src/ tests/

typecheck: ## Run mypy type checker
	$(PYTHON) -m mypy src/ --strict

ci: ## Run all CI checks (lint + format check + typecheck + test)
	$(PYTHON) -m ruff check src/ tests/
	$(PYTHON) -m ruff format --check src/ tests/
	$(PYTHON) -m mypy src/ --strict
	$(PYTHON) -m pytest tests/ -v --tb=short

clean: ## Remove build artifacts
	rm -rf build/ dist/ *.egg-info .eggs/
	rm -rf .mypy_cache/ .ruff_cache/ .pytest_cache/
	rm -rf htmlcov/ .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

run: ## Run CLI locally (requires install)
	$(PYTHON) -m github_discovery --help