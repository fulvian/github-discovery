"""Shared test fixtures for assessment tests."""

from __future__ import annotations

import pytest

from github_discovery.config import Settings
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel, DomainType, ScoreDimension
from github_discovery.models.screening import (
    HygieneScore,
    MetadataScreenResult,
    ScreeningResult,
    StaticScreenResult,
)
from github_discovery.assessment.types import (
    HeuristicScores,
    LLMBatchOutput,
    LLMDimensionOutput,
    RepoContent,
)
from github_discovery.models.assessment import TokenUsage


@pytest.fixture
def settings() -> Settings:
    """Provide default settings for assessment tests."""
    return Settings()


@pytest.fixture
def sample_candidate() -> RepoCandidate:
    """Provide a sample RepoCandidate for testing."""
    return RepoCandidate(
        full_name="test/awesome-lib",
        url="https://github.com/test/awesome-lib",
        html_url="https://github.com/test/awesome-lib",
        api_url="https://api.github.com/repos/test/awesome-lib",
        description="A test library",
        language="Python",
        stars=100,
        owner_login="test",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-06-01T00:00:00Z",
        pushed_at="2024-06-01T00:00:00Z",
        source_channel=DiscoveryChannel.SEARCH,
        commit_sha="abc123",
    )


@pytest.fixture
def sample_repo_content() -> RepoContent:
    """Provide a sample RepoContent for testing."""
    return RepoContent(
        full_name="test/awesome-lib",
        content=(
            "src/main.py\ndef hello():\n    pass\n"
            "tests/test_main.py\ndef test_hello():\n    assert True\n"
        ),
        total_files=10,
        total_tokens=500,
        total_chars=2000,
        compressed=True,
        truncated=False,
        clone_url="https://github.com/test/awesome-lib",
    )


@pytest.fixture
def sample_heuristic_scores() -> HeuristicScores:
    """Provide sample heuristic scores for testing."""
    return HeuristicScores(
        full_name="test/awesome-lib",
        file_count=10,
        has_tests=True,
        has_ci=True,
        has_docs=True,
        has_security_policy=False,
        language_distribution={"Python": 8, "JavaScript": 2},
        structure_score=0.7,
        size_category="small",
    )


@pytest.fixture
def sample_screening_passed() -> ScreeningResult:
    """Provide a screening result that passes both gates."""
    return ScreeningResult(
        full_name="test/awesome-lib",
        commit_sha="abc123",
        gate1=MetadataScreenResult(
            full_name="test/awesome-lib",
            hygiene=HygieneScore(value=0.7),
            gate1_total=0.6,
            gate1_pass=True,
        ),
        gate2=StaticScreenResult(
            full_name="test/awesome-lib",
            gate2_total=0.6,
            gate2_pass=True,
        ),
    )


@pytest.fixture
def sample_screening_failed() -> ScreeningResult:
    """Provide a screening result that fails Gate 1."""
    return ScreeningResult(
        full_name="test/awesome-lib",
        commit_sha="abc123",
        gate1=MetadataScreenResult(
            full_name="test/awesome-lib",
            gate1_total=0.2,
            gate1_pass=False,
        ),
    )


@pytest.fixture
def sample_llm_dimension_output() -> LLMDimensionOutput:
    """Provide a sample LLMDimensionOutput for testing."""
    return LLMDimensionOutput(
        score=0.85,
        explanation="Good code quality with consistent patterns.",
        evidence=["Uses type hints", "Follows PEP 8", "Has docstrings"],
        confidence=0.8,
    )


@pytest.fixture
def sample_llm_batch_output() -> LLMBatchOutput:
    """Provide a sample LLMBatchOutput with all 8 dimensions."""
    dimensions: dict[str, LLMDimensionOutput] = {}
    for dim in ScoreDimension:
        dimensions[dim.value] = LLMDimensionOutput(
            score=0.75,
            explanation=f"Adequate {dim.value}.",
            evidence=[f"Evidence for {dim.value}"],
            confidence=0.7,
        )
    return LLMBatchOutput(
        dimensions=dimensions,
        overall_explanation="Overall the repository is of adequate quality.",
    )


@pytest.fixture
def sample_token_usage() -> TokenUsage:
    """Provide a sample TokenUsage for testing."""
    return TokenUsage(
        prompt_tokens=1000,
        completion_tokens=500,
        total_tokens=1500,
        model_used="gpt-4o",
        provider="nanogpt",
    )
