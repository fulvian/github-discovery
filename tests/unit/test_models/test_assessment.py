"""Tests for deep assessment models (Gate 3)."""

from __future__ import annotations

import pytest

from github_discovery.models.assessment import (
    DeepAssessmentResult,
    DimensionScore,
    TokenUsage,
)
from github_discovery.models.enums import ScoreDimension


def _make_dimension_score(
    dimension: ScoreDimension,
    value: float = 0.8,
) -> DimensionScore:
    """Create a test dimension score."""
    return DimensionScore(
        dimension=dimension,
        value=value,
        explanation=f"{dimension.value} looks good",
        evidence=[f"evidence_{dimension.value}"],
        confidence=0.85,
    )


class TestDimensionScore:
    """Test individual dimension score."""

    def test_valid_score(self) -> None:
        """DimensionScore accepts valid values."""
        ds = DimensionScore(
            dimension=ScoreDimension.CODE_QUALITY,
            value=0.75,
            explanation="Well-structured code",
            evidence=["Consistent naming", "Good modularity"],
        )
        assert ds.dimension == ScoreDimension.CODE_QUALITY
        assert ds.value == 0.75
        assert len(ds.evidence) == 2

    def test_invalid_value_range(self) -> None:
        """DimensionScore rejects values outside 0.0-1.0."""
        with pytest.raises(Exception):  # noqa: B017
            DimensionScore(dimension=ScoreDimension.TESTING, value=1.5)


class TestDeepAssessmentResult:
    """Test Gate 3 deep assessment result."""

    def test_empty_result(self) -> None:
        """Empty result has no dimensions scored."""
        result = DeepAssessmentResult(full_name="test/repo")
        assert result.dimensions_assessed == 0
        assert result.completeness_ratio == 0.0
        assert result.gate3_pass is False

    def test_with_all_dimensions(self) -> None:
        """Result with all 8 dimensions."""
        dims = {d: _make_dimension_score(d) for d in ScoreDimension}
        result = DeepAssessmentResult(
            full_name="test/repo",
            dimensions=dims,
            overall_quality=0.82,
            gate3_pass=True,
        )
        assert result.dimensions_assessed == 8
        assert result.completeness_ratio == 1.0

    def test_get_dimension_score(self) -> None:
        """Can retrieve score by dimension."""
        ds = _make_dimension_score(ScoreDimension.SECURITY, value=0.9)
        result = DeepAssessmentResult(
            full_name="test/repo",
            dimensions={ScoreDimension.SECURITY: ds},
        )
        retrieved = result.get_dimension_score(ScoreDimension.SECURITY)
        assert retrieved is not None
        assert retrieved.value == 0.9

    def test_compute_overall_confidence(self) -> None:
        """Overall confidence is minimum of dimension confidences."""
        dims = {
            ScoreDimension.CODE_QUALITY: DimensionScore(
                dimension=ScoreDimension.CODE_QUALITY,
                value=0.9,
                confidence=0.9,
            ),
            ScoreDimension.TESTING: DimensionScore(
                dimension=ScoreDimension.TESTING,
                value=0.7,
                confidence=0.6,
            ),
        }
        result = DeepAssessmentResult(
            full_name="test/repo",
            dimensions=dims,
        )
        assert result.compute_overall_confidence() == 0.6

    def test_json_round_trip(self) -> None:
        """DeepAssessmentResult serializes to/from JSON."""
        dims = {
            ScoreDimension.ARCHITECTURE: _make_dimension_score(
                ScoreDimension.ARCHITECTURE,
            ),
        }
        result = DeepAssessmentResult(
            full_name="test/repo",
            dimensions=dims,
            overall_quality=0.8,
            token_usage=TokenUsage(total_tokens=5000, model_used="gpt-4o"),
        )
        json_str = result.model_dump_json()
        restored = DeepAssessmentResult.model_validate_json(json_str)
        assert restored.full_name == "test/repo"
        assert restored.token_usage.total_tokens == 5000

    def test_cached_flag(self) -> None:
        """Result tracks whether it came from cache."""
        result = DeepAssessmentResult(full_name="test/repo", cached=True)
        assert result.cached is True


class TestTokenUsage:
    """Test token usage tracking."""

    def test_default_usage(self) -> None:
        """Default usage is zero."""
        usage = TokenUsage()
        assert usage.total_tokens == 0

    def test_usage_tracking(self) -> None:
        """Usage tracks prompt and completion tokens."""
        usage = TokenUsage(
            prompt_tokens=3000,
            completion_tokens=2000,
            total_tokens=5000,
            model_used="gpt-4o",
            provider="openai",
        )
        assert usage.total_tokens == 5000
        assert usage.model_used == "gpt-4o"
