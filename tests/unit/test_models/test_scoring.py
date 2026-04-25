"""Tests for scoring, ranking, and explainability models."""

from __future__ import annotations

import pytest

from github_discovery.models.enums import DomainType, ScoreDimension
from github_discovery.models.scoring import (
    BACKEND_PROFILE,
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
    """Test star-neutral value score (value_score = quality_score)."""

    def test_hidden_gem_value_equals_quality(self) -> None:
        """Value score equals quality score regardless of stars (star-neutral)."""
        score = ScoreResult(
            full_name="hidden/gem",
            quality_score=0.9,
            stars=10,
        )
        assert score.value_score == pytest.approx(0.9, abs=0.001)
        assert score.is_hidden_gem is True  # high quality + low stars

    def test_popular_repo_value_equals_quality(self) -> None:
        """Popular repo value_score equals quality_score (no star penalty)."""
        score = ScoreResult(
            full_name="popular/repo",
            quality_score=0.9,
            stars=50000,
        )
        assert score.value_score == pytest.approx(0.9, abs=0.001)
        assert score.is_hidden_gem is False  # too many stars

    def test_zero_quality_zero_value(self) -> None:
        """Zero quality = zero value score."""
        score = ScoreResult(full_name="bad/repo", quality_score=0.0, stars=100)
        assert score.value_score == 0.0

    def test_zero_stars_high_quality(self) -> None:
        """Zero stars + high quality = value_score = quality_score (no boost)."""
        score = ScoreResult(
            full_name="new/repo",
            quality_score=0.8,
            stars=0,
        )
        assert score.value_score == pytest.approx(0.8, abs=0.001)

    def test_star_neutral_ordering(self) -> None:
        """Star-neutral: same quality = same value_score, regardless of stars."""
        hidden = ScoreResult(full_name="hidden/gem", quality_score=0.85, stars=15)
        popular = ScoreResult(full_name="popular/repo", quality_score=0.85, stars=30000)
        assert hidden.value_score == pytest.approx(popular.value_score, abs=0.001)


class TestCorroborationLevel:
    """Test corroboration_level computed field."""

    def test_new_repo(self) -> None:
        assert (
            ScoreResult(full_name="a/b", quality_score=0.5, stars=0).corroboration_level == "new"
        )

    def test_unvalidated(self) -> None:
        assert (
            ScoreResult(full_name="a/b", quality_score=0.5, stars=10).corroboration_level
            == "unvalidated"
        )

    def test_emerging(self) -> None:
        assert (
            ScoreResult(full_name="a/b", quality_score=0.5, stars=100).corroboration_level
            == "emerging"
        )

    def test_validated(self) -> None:
        assert (
            ScoreResult(full_name="a/b", quality_score=0.5, stars=1000).corroboration_level
            == "validated"
        )

    def test_widely_adopted(self) -> None:
        assert (
            ScoreResult(full_name="a/b", quality_score=0.5, stars=10000).corroboration_level
            == "widely_adopted"
        )


class TestIsHiddenGem:
    """Test is_hidden_gem computed field (informational label)."""

    def test_high_quality_low_stars(self) -> None:
        score = ScoreResult(full_name="a/b", quality_score=0.7, stars=50)
        assert score.is_hidden_gem is True

    def test_high_quality_high_stars(self) -> None:
        score = ScoreResult(full_name="a/b", quality_score=0.8, stars=500)
        assert score.is_hidden_gem is False

    def test_low_quality_low_stars(self) -> None:
        score = ScoreResult(full_name="a/b", quality_score=0.3, stars=10)
        assert score.is_hidden_gem is False

    def test_boundary_quality(self) -> None:
        """quality_score = 0.5 is the minimum for hidden gem."""
        score = ScoreResult(full_name="a/b", quality_score=0.5, stars=50)
        assert score.is_hidden_gem is True

    def test_boundary_stars(self) -> None:
        """stars = 99 is below threshold, 100 is at/below."""
        below = ScoreResult(full_name="a/b", quality_score=0.7, stars=99)
        assert below.is_hidden_gem is True
        at_threshold = ScoreResult(full_name="a/b", quality_score=0.7, stars=100)
        assert at_threshold.is_hidden_gem is False


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
        assert get_domain_profile(DomainType.BACKEND) is BACKEND_PROFILE
        # Unknown domain returns default
        assert get_domain_profile(DomainType.ML_LIB) is DEFAULT_PROFILE

    def test_devops_profile_weights_sum_to_one(self) -> None:
        """DevOps profile weights sum to 1.0."""
        assert DEVOPS_PROFILE.validate_weights() is True

    def test_backend_profile_weights_sum_to_one(self) -> None:
        """Backend profile weights sum to 1.0."""
        assert BACKEND_PROFILE.validate_weights() is True

    def test_backend_architecture_weight_higher(self) -> None:
        """Backend profile weights architecture higher than default."""
        backend_arch = BACKEND_PROFILE.dimension_weights[ScoreDimension.ARCHITECTURE]
        default_arch = DEFAULT_PROFILE.dimension_weights[ScoreDimension.ARCHITECTURE]
        assert backend_arch > default_arch


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
            value_score=0.8,
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
            value_score=0.7,
        )
        json_str = report.model_dump_json()
        restored = ExplainabilityReport.model_validate_json(json_str)
        assert restored.full_name == "test/repo"
        assert restored.domain == DomainType.CLI
