"""Shared fixtures for feasibility validation tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from github_discovery.config import (
    DiscoverySettings,
    GitHubSettings,
    Settings,
)
from github_discovery.feasibility.sprint0 import Sprint0Config
from github_discovery.models.candidate import RepoCandidate

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def feasibility_settings(tmp_path: Path) -> Settings:
    """Settings with temp databases and no real token for feasibility tests."""
    return Settings(
        github=GitHubSettings(token=""),
        discovery=DiscoverySettings(
            max_candidates=50,
        ),
    )


@pytest.fixture
def sprint0_config() -> Sprint0Config:
    """Sprint0Config with small pool size for testing."""
    return Sprint0Config(
        max_candidates=50,
        queries=["static analysis python", "machine learning framework"],
        gate1_threshold=0.4,
        gate2_threshold=0.3,
        deep_assess_percentile=0.15,
        llm_budget_tokens=10_000,
        seed=42,
    )


@pytest.fixture
def sample_repos_json() -> dict[str, object]:
    """Load the raw JSON dict from tests/fixtures/sample_repos.json."""
    json_path = FIXTURES_DIR / "sample_repos.json"
    with json_path.open() as f:
        data: dict[str, object] = json.load(f)
    return data


@pytest.fixture
def sample_candidates(sample_repos_json: dict[str, object]) -> list[RepoCandidate]:
    """Load RepoCandidate list from fixtures JSON."""
    repos_data = sample_repos_json.get("repos", [])
    assert isinstance(repos_data, list)
    candidates: list[RepoCandidate] = []
    for repo_dict in repos_data:
        assert isinstance(repo_dict, dict)
        candidates.append(RepoCandidate.model_validate(repo_dict))
    return candidates


@pytest.fixture
def ground_truth_good() -> set[str]:
    """Set of full_names of repos known to be high-quality hidden gems.

    These repos in sample_repos.json have great quality signals but low stars.
    """
    return {
        "cool-dev/tiny-ml-utils",
        "rustacean/secure-cli",
        "datapipeline/flow-engine",
        "golang-master/task-runner",
        "webperf/http-bench",
        "typescriptsdk/validation-kit",
        "server-kit/rust-jwt",
        "quality-first/py-sast",
        "rust-tools/cargo-audit-lite",
        "streaming-dev/kafka-lite-py",
        "ts-enthusiast/config-vault",
        "ml-research/tinygrad-ext",
        "cache-lib/redis-memo-py",
        "distributed-sys/raft-rs",
        "datastack/etl-framework",
    }


@pytest.fixture
def ground_truth_scores() -> dict[str, float]:
    """Dict of repo full_name -> quality score (0.0-1.0).

    Hidden gems get high quality scores, overhyped repos get low scores,
    popular well-maintained repos get moderate-high scores.
    """
    return {
        # Hidden gems — high quality, low stars
        "cool-dev/tiny-ml-utils": 0.85,
        "rustacean/secure-cli": 0.88,
        "datapipeline/flow-engine": 0.82,
        "golang-master/task-runner": 0.79,
        "webperf/http-bench": 0.81,
        "typescriptsdk/validation-kit": 0.83,
        "server-kit/rust-jwt": 0.80,
        "quality-first/py-sast": 0.77,
        "rust-tools/cargo-audit-lite": 0.84,
        "streaming-dev/kafka-lite-py": 0.76,
        "ts-enthusiast/config-vault": 0.78,
        "ml-research/tinygrad-ext": 0.81,
        "cache-lib/redis-memo-py": 0.79,
        "distributed-sys/raft-rs": 0.86,
        "datastack/etl-framework": 0.83,
        # Popular, well-maintained — moderate-high quality
        "pallets/flask": 0.72,
        "fastapi/fastapi": 0.78,
        "tokio-rs/axum": 0.80,
        "scikit-learn/scikit-learn": 0.75,
        "pytorch/pytorch": 0.73,
        "cli/cli": 0.76,
        "BurntSushi/ripgrep": 0.85,
        "pola-rs/polars": 0.82,
        "pytest-dev/pytest": 0.80,
        "static-analysis/ruff-linter": 0.87,
        "static-analysis/pylint-pro": 0.78,
        "apache/airflow": 0.68,
        # Overhyped — high stars, low quality
        "hype-dev/trending-ml-lib": 0.32,
        "viral-coder/awesome-tool": 0.28,
        "overhyped/rust-web-mega": 0.35,
        "shallow-dev/data-lib-popular": 0.38,
        "abandoned-dev/old-popular-lib": 0.22,
        "stale-dev/abandoned-cli": 0.25,
    }
