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