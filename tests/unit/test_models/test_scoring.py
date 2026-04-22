"""Tests for scoring, ranking, and explainability models."""

from __future__ import annotations

from math import log10

from github_discovery.models.enums import DomainType, ScoreDimension
from github_discovery.models.scoring import (
    CLI_PROFILE,
    DEFAULT_PROFILE,
    DEVOPS_PROFILE,
    LIBRARY_PROFILE,
    ExplainabilityReport,
    RankedRepo,
    ScoreResult,
    get_domain_profile,
)


class TestValueScore:
    """Test anti-star bias Value Score computation."""

    def test_hidden_gem_high_value(self) -> None:
        """Low stars + high quality = high value score (hidden gem)."""
        score = ScoreResult(
            full_name="hidden/gem",
            quality_score=0.9,
            stars=10,
        )
        expected = 0.9 / log10(10 + 10)
        assert abs(score.value_score - expected) < 0.001
        assert score.value_score > 0.5  # High value score

    def test_popular_repo_moderate_value(self) -> None:
        """High stars + high quality = moderate value score."""
        score = ScoreResult(
            full_name="popular/repo",
            quality_score=0.9,
            stars=50000,
        )
        expected = 0.9 / log10(50000 + 10)
        assert abs(score.value_score - expected) < 0.001
        # Should be lower than hidden gem with same quality
        assert score.value_score < 0.2

    def test_zero_quality_zero_value(self) -> None:
        """Zero quality = zero value score."""
        score = ScoreResult(full_name="bad/repo", quality_score=0.0, stars=100)
        assert score.value_score == 0.0

    def test_zero_stars_high_quality(self) -> None:
        """Zero stars + high quality = very high value score."""
        score = ScoreResult(
            full_name="new/repo",
            quality_score=0.8,
            stars=0,
        )
        expected = 0.8 / log10(0 + 10)
        assert abs(score.value_score - expected) < 0.001
        assert score.value_score > 0.5

    def test_anti_star_bias_ordering(self) -> None:
        """Hidden gems rank higher than popular repos with same quality."""
        hidden = ScoreResult(full_name="hidden/gem", quality_score=0.85, stars=15)
        popular = ScoreResult(full_name="popular/repo", quality_score=0.85, stars=30000)
        assert hidden.value_score > popular.value_score


class TestDomainProfile:
    """Test domain weight profiles."""

    def test_library_profile_weights_sum_to_one(self) -> None:
        """Library profile weights sum to 1.0."""
        assert LIBRARY_PROFILE.validate_weights() is True

    def test_cli_profile_weights_sum_to_one(self) -> None:
        """CLI profile weights sum to 1.0."""
        assert CLI_PROFILE.validate_weights() is True

    def test_default_profile_weights_sum_to_one(self) -> None:
        """Default profile weights sum to 1.0."""
        assert DEFAULT_PROFILE.validate_weights() is True

    def test_devops_security_weight_higher(self) -> None:
        """DevOps profile weights security higher than library."""
        devops_sec = DEVOPS_PROFILE.dimension_weights[ScoreDimension.SECURITY]
        lib_sec = LIBRARY_PROFILE.dimension_weights[ScoreDimension.SECURITY]
        assert devops_sec > lib_sec

    def test_cli_testing_weight_higher(self) -> None:
        """CLI profile weights testing higher than default."""
        cli_test = CLI_PROFILE.dimension_weights[ScoreDimension.TESTING]
        default_test = DEFAULT_PROFILE.dimension_weights[ScoreDimension.TESTING]
        assert cli_test > default_test

    def test_get_domain_profile(self) -> None:
        """get_domain_profile returns correct profile."""
        assert get_domain_profile(DomainType.LIBRARY) is LIBRARY_PROFILE
        assert get_domain_profile(DomainType.OTHER) is DEFAULT_PROFILE
        # Unknown domain returns default
        assert get_domain_profile(DomainType.ML_LIB) is DEFAULT_PROFILE

    def test_devops_profile_weights_sum_to_one(self) -> None:
        """DevOps profile weights sum to 1.0."""
        assert DEVOPS_PROFILE.validate_weights() is True


class TestRankedRepo:
    """Test ranked repository model."""

    def test_computed_fields(self) -> None:
        """RankedRepo exposes computed fields from ScoreResult."""
        score = ScoreResult(
            full_name="test/repo",
            quality_score=0.8,
            stars=100,
        )
        ranked = RankedRepo(
            rank=1,
            full_name="test/repo",
            domain=DomainType.LIBRARY,
            score_result=score,
        )
        assert ranked.quality_score == 0.8
        assert ranked.stars == 100
        assert ranked.value_score == score.value_score


class TestExplainabilityReport:
    """Test explainability report model."""

    def test_report_creation(self) -> None:
        """Report can be created with all fields."""
        report = ExplainabilityReport(
            full_name="test/repo",
            domain=DomainType.LIBRARY,
            overall_quality=0.8,
            value_score=0.6,
            strengths=["Excellent test coverage", "Clean architecture"],
            weaknesses=["Missing security policy"],
            hidden_gem_indicator=True,
            hidden_gem_reason="High quality (0.8) with low visibility (42 stars)",
        )
        assert report.hidden_gem_indicator is True
        assert len(report.strengths) == 2

    def test_json_round_trip(self) -> None:
        """Report serializes to/from JSON."""
        report = ExplainabilityReport(
            full_name="test/repo",
            domain=DomainType.CLI,
            overall_quality=0.7,
            value_score=0.5,
        )
        json_str = report.model_dump_json()
        restored = ExplainabilityReport.model_validate_json(json_str)
        assert restored.full_name == "test/repo"
        assert restored.domain == DomainType.CLI
