"""Shared fixtures for scoring module tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from github_discovery.models.assessment import (
    DeepAssessmentResult,
    DimensionScore,
    TokenUsage,
)
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import (
    CandidateStatus,
    DiscoveryChannel,
    DomainType,
    ScoreDimension,
)
from github_discovery.models.scoring import ScoreResult
from github_discovery.models.screening import (
    CiCdScore,
    ComplexityScore,
    DependencyQualityScore,
    HygieneScore,
    MaintenanceScore,
    MetadataScreenResult,
    ReleaseDisciplineScore,
    ReviewPracticeScore,
    ScreeningResult,
    SecretHygieneScore,
    SecurityHygieneScore,
    StaticScreenResult,
    TestFootprintScore,
    VulnerabilityScore,
)
from github_discovery.scoring.engine import ScoringEngine
from github_discovery.scoring.ranker import Ranker
from github_discovery.scoring.value_score import ValueScoreCalculator


def _make_candidate(
    full_name: str = "test/repo",
    stars: int = 100,
    domain: DomainType = DomainType.LIBRARY,
    commit_sha: str = "abc123",
) -> RepoCandidate:
    """Create a sample RepoCandidate for testing."""
    return RepoCandidate(
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        html_url=f"https://github.com/{full_name}",
        api_url=f"https://api.github.com/repos/{full_name}",
        description="Test repository",
        language="Python",
        domain=domain,
        stars=stars,
        forks_count=10,
        watchers_count=5,
        subscribers_count=3,
        open_issues_count=5,
        created_at=datetime(2023, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 6, 1, tzinfo=UTC),
        pushed_at=datetime(2024, 6, 1, tzinfo=UTC),
        owner_login=full_name.split("/", maxsplit=1)[0],
        source_channel=DiscoveryChannel.SEARCH,
        commit_sha=commit_sha,
        status=CandidateStatus.DISCOVERED,
    )


def _make_gate1_result(
    full_name: str = "test/repo",
    hygiene: float = 0.7,
    maintenance: float = 0.6,
    release_discipline: float = 0.5,
    review_practice: float = 0.6,
    test_footprint: float = 0.7,
    ci_cd: float = 0.5,
    dependency_quality: float = 0.6,
) -> MetadataScreenResult:
    """Create a sample Gate 1 result."""
    return MetadataScreenResult(
        full_name=full_name,
        hygiene=HygieneScore(value=hygiene),
        maintenance=MaintenanceScore(value=maintenance),
        release_discipline=ReleaseDisciplineScore(value=release_discipline),
        review_practice=ReviewPracticeScore(value=review_practice),
        test_footprint=TestFootprintScore(value=test_footprint),
        ci_cd=CiCdScore(value=ci_cd),
        dependency_quality=DependencyQualityScore(value=dependency_quality),
        gate1_total=0.6,
        gate1_pass=True,
    )


def _make_gate2_result(
    full_name: str = "test/repo",
    security_hygiene: float = 0.6,
    vulnerability: float = 0.7,
    complexity: float = 0.5,
    secret_hygiene: float = 0.8,
) -> StaticScreenResult:
    """Create a sample Gate 2 result."""
    return StaticScreenResult(
        full_name=full_name,
        security_hygiene=SecurityHygieneScore(value=security_hygiene),
        vulnerability=VulnerabilityScore(value=vulnerability),
        complexity=ComplexityScore(value=complexity),
        secret_hygiene=SecretHygieneScore(value=secret_hygiene),
        gate2_total=0.65,
        gate2_pass=True,
    )


def _make_screening_result(
    full_name: str = "test/repo",
    hygiene: float = 0.7,
    maintenance: float = 0.6,
    release_discipline: float = 0.5,
    review_practice: float = 0.6,
    test_footprint: float = 0.7,
    ci_cd: float = 0.5,
    dependency_quality: float = 0.6,
    security_hygiene: float = 0.6,
    vulnerability: float = 0.7,
    complexity: float = 0.5,
    secret_hygiene: float = 0.8,
) -> ScreeningResult:
    """Create a sample ScreeningResult with Gate 1+2 passed."""
    return ScreeningResult(
        full_name=full_name,
        gate1=_make_gate1_result(
            full_name,
            hygiene=hygiene,
            maintenance=maintenance,
            release_discipline=release_discipline,
            review_practice=review_practice,
            test_footprint=test_footprint,
            ci_cd=ci_cd,
            dependency_quality=dependency_quality,
        ),
        gate2=_make_gate2_result(
            full_name,
            security_hygiene=security_hygiene,
            vulnerability=vulnerability,
            complexity=complexity,
            secret_hygiene=secret_hygiene,
        ),
    )


def _make_assessment_result(
    full_name: str = "test/repo",
    dimensions: dict[ScoreDimension, float] | None = None,
) -> DeepAssessmentResult:
    """Create a sample DeepAssessmentResult with all 8 dimensions."""
    if dimensions is None:
        dimensions = {
            ScoreDimension.CODE_QUALITY: 0.8,
            ScoreDimension.ARCHITECTURE: 0.7,
            ScoreDimension.TESTING: 0.75,
            ScoreDimension.DOCUMENTATION: 0.6,
            ScoreDimension.MAINTENANCE: 0.7,
            ScoreDimension.SECURITY: 0.65,
            ScoreDimension.FUNCTIONALITY: 0.7,
            ScoreDimension.INNOVATION: 0.5,
        }

    dim_scores = {
        dim: DimensionScore(
            dimension=dim,
            value=val,
            confidence=0.8,
        )
        for dim, val in dimensions.items()
    }

    return DeepAssessmentResult(
        full_name=full_name,
        dimensions=dim_scores,
        overall_quality=0.7,
        overall_confidence=0.8,
        gate3_pass=True,
        token_usage=TokenUsage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500),
    )


def _make_score_result(
    full_name: str = "test/repo",
    quality_score: float = 0.75,
    stars: int = 100,
    domain: DomainType = DomainType.LIBRARY,
    confidence: float = 0.7,
    commit_sha: str = "abc123",
    dimension_scores: dict[ScoreDimension, float] | None = None,
) -> ScoreResult:
    """Create a sample ScoreResult for testing."""
    dims = dimension_scores or {
        ScoreDimension.CODE_QUALITY: 0.8,
        ScoreDimension.ARCHITECTURE: 0.7,
        ScoreDimension.TESTING: 0.75,
        ScoreDimension.DOCUMENTATION: 0.6,
        ScoreDimension.MAINTENANCE: 0.7,
        ScoreDimension.SECURITY: 0.65,
        ScoreDimension.FUNCTIONALITY: 0.7,
        ScoreDimension.INNOVATION: 0.5,
    }
    return ScoreResult(
        full_name=full_name,
        commit_sha=commit_sha,
        domain=domain,
        quality_score=quality_score,
        dimension_scores=dims,
        confidence=confidence,
        stars=stars,
        gate1_total=0.6,
        gate2_total=0.65,
        gate3_available=True,
    )


@pytest.fixture
def sample_candidate() -> RepoCandidate:
    """Repo candidate with realistic metadata."""
    return _make_candidate()


@pytest.fixture
def sample_screening_result() -> ScreeningResult:
    """Screening result with Gate 1+2 passed."""
    return _make_screening_result()


@pytest.fixture
def sample_assessment_result() -> DeepAssessmentResult:
    """Deep assessment result with all 8 dimensions."""
    return _make_assessment_result()


@pytest.fixture
def sample_score_result() -> ScoreResult:
    """Sample ScoreResult for testing."""
    return _make_score_result()


@pytest.fixture
def scoring_engine() -> ScoringEngine:
    """ScoringEngine with default settings."""
    return ScoringEngine()


@pytest.fixture
def value_calculator() -> ValueScoreCalculator:
    """ValueScoreCalculator with default settings."""
    return ValueScoreCalculator()


@pytest.fixture
def ranker() -> Ranker:
    """Ranker with default settings."""
    return Ranker()
