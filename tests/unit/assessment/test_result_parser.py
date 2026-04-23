"""Tests for ResultParser — LLM response parsing into DeepAssessmentResult.

Tests batch parsing, dimension parsing, heuristic fallback,
dimension name normalization, quality/confidence computation,
and Gate 3 threshold behavior.
"""

from __future__ import annotations

import pytest

from github_discovery.assessment.result_parser import ResultParser
from github_discovery.assessment.types import (
    HeuristicScores,
    LLMBatchOutput,
    LLMDimensionOutput,
)
from github_discovery.models.assessment import (
    DeepAssessmentResult,
    DimensionScore,
    TokenUsage,
)
from github_discovery.models.enums import ScoreDimension


class TestParseBatch:
    """Tests for ResultParser.parse_batch."""

    def test_parse_batch_with_full_output(
        self,
        sample_llm_batch_output: LLMBatchOutput,
    ) -> None:
        """parse_batch returns DeepAssessmentResult with all 8 dimensions."""
        parser = ResultParser()
        result = parser.parse_batch(
            sample_llm_batch_output,
            full_name="test/repo",
            commit_sha="abc123",
        )

        assert isinstance(result, DeepAssessmentResult)
        assert result.full_name == "test/repo"
        assert result.commit_sha == "abc123"
        assert len(result.dimensions) == 8

    def test_parse_batch_sets_gate3_pass(self) -> None:
        """parse_batch sets gate3_pass=True when quality >= threshold."""
        parser = ResultParser()
        # All dimensions score 0.9 → overall quality should be 0.9
        dims = {dim.value: LLMDimensionOutput(score=0.9, confidence=0.8) for dim in ScoreDimension}
        batch = LLMBatchOutput(dimensions=dims)
        result = parser.parse_batch(
            batch,
            full_name="test/repo",
            commit_sha="abc",
            gate3_threshold=0.6,
        )

        assert result.gate3_pass is True
        assert result.gate3_threshold == 0.6

    def test_parse_batch_sets_gate3_fail(self) -> None:
        """parse_batch sets gate3_pass=False when quality < threshold."""
        parser = ResultParser()
        dims = {dim.value: LLMDimensionOutput(score=0.3, confidence=0.5) for dim in ScoreDimension}
        batch = LLMBatchOutput(dimensions=dims)
        result = parser.parse_batch(
            batch,
            full_name="test/repo",
            commit_sha="abc",
            gate3_threshold=0.6,
        )

        assert result.gate3_pass is False

    def test_parse_batch_with_token_usage(self) -> None:
        """parse_batch records token_usage when provided."""
        parser = ResultParser()
        dims = {
            ScoreDimension.CODE_QUALITY.value: LLMDimensionOutput(score=0.7),
        }
        batch = LLMBatchOutput(dimensions=dims)
        usage = TokenUsage(total_tokens=500)
        result = parser.parse_batch(
            batch,
            full_name="test/repo",
            commit_sha="abc",
            token_usage=usage,
        )

        assert result.token_usage.total_tokens == 500

    def test_parse_batch_with_partial_dimensions(self) -> None:
        """parse_batch fills missing dimensions with heuristics."""
        parser = ResultParser()
        # Only 2 dimensions in LLM output
        dims = {
            ScoreDimension.CODE_QUALITY.value: LLMDimensionOutput(score=0.8),
            ScoreDimension.TESTING.value: LLMDimensionOutput(score=0.7),
        }
        batch = LLMBatchOutput(dimensions=dims)
        heuristics = HeuristicScores(
            full_name="test/repo",
            has_tests=True,
            structure_score=0.6,
        )
        result = parser.parse_batch(
            batch,
            full_name="test/repo",
            commit_sha="abc",
            heuristic_scores=heuristics,
        )

        # CODE_QUALITY and TESTING are LLM-assessed, rest are heuristic fallback
        assert len(result.dimensions) == 8
        assert result.dimensions[ScoreDimension.CODE_QUALITY].assessment_method == "llm"
        assert result.dimensions[ScoreDimension.TESTING].assessment_method == "llm"
        # Missing dimensions should be filled
        assert result.dimensions[ScoreDimension.SECURITY].assessment_method == "heuristic"

    def test_parse_batch_without_heuristic_scores(self) -> None:
        """parse_batch without heuristics leaves missing dimensions empty."""
        parser = ResultParser()
        dims = {
            ScoreDimension.CODE_QUALITY.value: LLMDimensionOutput(score=0.8),
        }
        batch = LLMBatchOutput(dimensions=dims)
        result = parser.parse_batch(
            batch,
            full_name="test/repo",
            commit_sha="abc",
        )

        # Only 1 dimension without heuristic fill
        assert len(result.dimensions) == 1
        assert ScoreDimension.CODE_QUALITY in result.dimensions

    def test_parse_batch_ignores_unknown_dimension(self) -> None:
        """parse_batch skips unknown dimension names from LLM output."""
        parser = ResultParser()
        dims = {
            "unknown_dimension": LLMDimensionOutput(score=0.5),
            ScoreDimension.CODE_QUALITY.value: LLMDimensionOutput(score=0.8),
        }
        batch = LLMBatchOutput(dimensions=dims)
        result = parser.parse_batch(
            batch,
            full_name="test/repo",
            commit_sha="abc",
        )

        assert len(result.dimensions) == 1
        assert ScoreDimension.CODE_QUALITY in result.dimensions

    def test_parse_batch_sets_overall_explanation(self) -> None:
        """parse_batch propagates overall_explanation from batch output."""
        parser = ResultParser()
        batch = LLMBatchOutput(
            dimensions={},
            overall_explanation="Good quality repo.",
        )
        result = parser.parse_batch(
            batch,
            full_name="test/repo",
            commit_sha="abc",
        )

        assert result.overall_explanation == "Good quality repo."


class TestParseDimension:
    """Tests for ResultParser.parse_dimension."""

    def test_parse_dimension_returns_dimension_score(
        self,
        sample_llm_dimension_output: LLMDimensionOutput,
    ) -> None:
        """parse_dimension returns DimensionScore with correct fields."""
        parser = ResultParser()
        result = parser.parse_dimension(
            ScoreDimension.CODE_QUALITY,
            sample_llm_dimension_output,
            "test/repo",
            "abc123",
        )

        assert isinstance(result, DimensionScore)
        assert result.dimension == ScoreDimension.CODE_QUALITY
        assert result.value == 0.85
        assert result.explanation == "Good code quality with consistent patterns."
        assert result.evidence == ["Uses type hints", "Follows PEP 8", "Has docstrings"]
        assert result.confidence == 0.8
        assert result.assessment_method == "llm"


class TestComposeFromDimensions:
    """Tests for ResultParser.compose_from_dimensions."""

    def test_compose_from_llm_dimensions(self) -> None:
        """compose_from_dimensions builds result from dimension scores."""
        parser = ResultParser()
        dims = {
            ScoreDimension.CODE_QUALITY: DimensionScore(
                dimension=ScoreDimension.CODE_QUALITY,
                value=0.8,
                assessment_method="llm",
            ),
            ScoreDimension.TESTING: DimensionScore(
                dimension=ScoreDimension.TESTING,
                value=0.7,
                assessment_method="llm",
            ),
        }
        result = parser.compose_from_dimensions(
            dims,
            full_name="test/repo",
            commit_sha="abc",
        )

        assert len(result.dimensions) == 2
        assert result.full_name == "test/repo"

    def test_compose_fills_missing_with_heuristics(self) -> None:
        """compose_from_dimensions fills missing dims via heuristics."""
        parser = ResultParser()
        dims = {
            ScoreDimension.CODE_QUALITY: DimensionScore(
                dimension=ScoreDimension.CODE_QUALITY,
                value=0.8,
                assessment_method="llm",
            ),
        }
        heuristics = HeuristicScores(
            full_name="test/repo",
            has_tests=True,
            structure_score=0.6,
        )
        result = parser.compose_from_dimensions(
            dims,
            full_name="test/repo",
            commit_sha="abc",
            heuristic_scores=heuristics,
        )

        assert len(result.dimensions) == 8
        assert result.dimensions[ScoreDimension.TESTING].assessment_method == "heuristic"

    def test_compose_with_custom_threshold(self) -> None:
        """compose_from_dimensions respects custom gate3_threshold."""
        parser = ResultParser()
        dims = {
            ScoreDimension.CODE_QUALITY: DimensionScore(
                dimension=ScoreDimension.CODE_QUALITY,
                value=0.5,
            ),
        }
        result = parser.compose_from_dimensions(
            dims,
            full_name="test/repo",
            commit_sha="abc",
            gate3_threshold=0.8,
        )

        assert result.gate3_threshold == 0.8


class TestCreateHeuristicFallback:
    """Tests for ResultParser.create_heuristic_fallback."""

    def test_creates_fallback_for_all_dimensions(self) -> None:
        """create_heuristic_fallback creates scores for all 8 dimensions."""
        parser = ResultParser()
        heuristics = HeuristicScores(
            full_name="test/repo",
            structure_score=0.5,
            has_tests=True,
            has_docs=True,
            has_security_policy=False,
        )
        result = parser.create_heuristic_fallback(
            heuristics,
            full_name="test/repo",
            commit_sha="abc",
        )

        assert len(result.dimensions) == 8
        assert result.full_name == "test/repo"
        assert result.overall_confidence == 0.3

    def test_fallback_all_heuristic_method(self) -> None:
        """All fallback dimensions have assessment_method='heuristic'."""
        parser = ResultParser()
        heuristics = HeuristicScores(full_name="test/repo")
        result = parser.create_heuristic_fallback(
            heuristics,
            full_name="test/repo",
            commit_sha="abc",
        )

        for dim_score in result.dimensions.values():
            assert dim_score.assessment_method == "heuristic"
            assert dim_score.confidence == 0.3

    def test_fallback_testing_high_when_tests_present(self) -> None:
        """Heuristic TESTING score is 0.6 when has_tests=True."""
        parser = ResultParser()
        heuristics = HeuristicScores(full_name="test/repo", has_tests=True)
        result = parser.create_heuristic_fallback(
            heuristics,
            full_name="test/repo",
            commit_sha="abc",
        )

        testing_score = result.dimensions[ScoreDimension.TESTING]
        assert testing_score.value == 0.6

    def test_fallback_testing_low_when_no_tests(self) -> None:
        """Heuristic TESTING score is 0.2 when has_tests=False."""
        parser = ResultParser()
        heuristics = HeuristicScores(full_name="test/repo", has_tests=False)
        result = parser.create_heuristic_fallback(
            heuristics,
            full_name="test/repo",
            commit_sha="abc",
        )

        testing_score = result.dimensions[ScoreDimension.TESTING]
        assert testing_score.value == 0.2

    def test_fallback_docs_high_when_docs_present(self) -> None:
        """Heuristic DOCUMENTATION score is 0.6 when has_docs=True."""
        parser = ResultParser()
        heuristics = HeuristicScores(full_name="test/repo", has_docs=True)
        result = parser.create_heuristic_fallback(
            heuristics,
            full_name="test/repo",
            commit_sha="abc",
        )

        docs_score = result.dimensions[ScoreDimension.DOCUMENTATION]
        assert docs_score.value == 0.6

    def test_fallback_security_depends_on_policy(self) -> None:
        """Heuristic SECURITY score is 0.5 with policy, 0.2 without."""
        parser = ResultParser()

        with_policy = HeuristicScores(full_name="test/repo", has_security_policy=True)
        result_with = parser.create_heuristic_fallback(
            with_policy,
            full_name="test/repo",
            commit_sha="abc",
        )
        assert result_with.dimensions[ScoreDimension.SECURITY].value == 0.5

        without_policy = HeuristicScores(full_name="test/repo", has_security_policy=False)
        result_without = parser.create_heuristic_fallback(
            without_policy,
            full_name="test/repo",
            commit_sha="abc",
        )
        assert result_without.dimensions[ScoreDimension.SECURITY].value == 0.2

    def test_fallback_overall_explanation(self) -> None:
        """Fallback result has appropriate overall_explanation."""
        parser = ResultParser()
        heuristics = HeuristicScores(full_name="test/repo")
        result = parser.create_heuristic_fallback(
            heuristics,
            full_name="test/repo",
            commit_sha="abc",
        )

        assert "heuristic" in result.overall_explanation.lower()


class TestParseDimensionName:
    """Tests for ResultParser._parse_dimension_name."""

    def test_parses_snake_case(self) -> None:
        """'code_quality' → ScoreDimension.CODE_QUALITY."""
        parser = ResultParser()
        result = parser._parse_dimension_name("code_quality")
        assert result == ScoreDimension.CODE_QUALITY

    def test_parses_uppercase(self) -> None:
        """'CODE_QUALITY' → ScoreDimension.CODE_QUALITY."""
        parser = ResultParser()
        result = parser._parse_dimension_name("CODE_QUALITY")
        assert result == ScoreDimension.CODE_QUALITY

    def test_parses_spaces(self) -> None:
        """'Code Quality' → ScoreDimension.CODE_QUALITY."""
        parser = ResultParser()
        result = parser._parse_dimension_name("Code Quality")
        assert result == ScoreDimension.CODE_QUALITY

    def test_parses_hyphens(self) -> None:
        """'code-quality' → ScoreDimension.CODE_QUALITY."""
        parser = ResultParser()
        result = parser._parse_dimension_name("code-quality")
        assert result == ScoreDimension.CODE_QUALITY

    def test_returns_none_for_unknown(self) -> None:
        """Unknown dimension name returns None."""
        parser = ResultParser()
        result = parser._parse_dimension_name("nonexistent_dimension")
        assert result is None

    def test_parses_all_dimensions(self) -> None:
        """All ScoreDimension values are parseable."""
        parser = ResultParser()
        for dim in ScoreDimension:
            result = parser._parse_dimension_name(dim.value)
            assert result == dim

    def test_handles_whitespace(self) -> None:
        """Leading/trailing whitespace is stripped."""
        parser = ResultParser()
        result = parser._parse_dimension_name("  code_quality  ")
        assert result == ScoreDimension.CODE_QUALITY


class TestComputeOverallQuality:
    """Tests for ResultParser._compute_overall_quality."""

    def test_empty_dimensions_returns_zero(self) -> None:
        """No dimensions → quality = 0.0."""
        parser = ResultParser()
        assert parser._compute_overall_quality({}) == 0.0

    def test_single_dimension_quality(self) -> None:
        """Single dimension score reflects that dimension."""
        parser = ResultParser()
        dims = {
            ScoreDimension.CODE_QUALITY: DimensionScore(
                dimension=ScoreDimension.CODE_QUALITY,
                value=0.8,
            ),
        }
        quality = parser._compute_overall_quality(dims)
        assert abs(quality - 0.8) < 0.001

    def test_weighted_average_of_dimensions(self) -> None:
        """Multiple dimensions are weighted per DEFAULT_PROFILE."""
        parser = ResultParser()
        # Use known values: code_quality=1.0 (weight=0.20), testing=0.0 (weight=0.15)
        dims = {
            ScoreDimension.CODE_QUALITY: DimensionScore(
                dimension=ScoreDimension.CODE_QUALITY,
                value=1.0,
            ),
            ScoreDimension.TESTING: DimensionScore(
                dimension=ScoreDimension.TESTING,
                value=0.0,
            ),
        }
        quality = parser._compute_overall_quality(dims)

        # Expected: (1.0*0.20 + 0.0*0.15) / (0.20+0.15) = 0.20/0.35 ≈ 0.5714
        expected = 0.20 / 0.35
        assert abs(quality - expected) < 0.01


class TestComputeOverallConfidence:
    """Tests for ResultParser._compute_overall_confidence."""

    def test_empty_dimensions_returns_zero(self) -> None:
        """No dimensions → confidence = 0.0."""
        parser = ResultParser()
        assert parser._compute_overall_confidence({}) == 0.0

    def test_returns_minimum_confidence(self) -> None:
        """Overall confidence is minimum of all dimension confidences."""
        parser = ResultParser()
        dims = {
            ScoreDimension.CODE_QUALITY: DimensionScore(
                dimension=ScoreDimension.CODE_QUALITY,
                value=0.8,
                confidence=0.9,
            ),
            ScoreDimension.TESTING: DimensionScore(
                dimension=ScoreDimension.TESTING,
                value=0.7,
                confidence=0.5,
            ),
        }
        confidence = parser._compute_overall_confidence(dims)
        assert confidence == 0.5

    def test_single_dimension_confidence(self) -> None:
        """Single dimension → confidence = that dimension's confidence."""
        parser = ResultParser()
        dims = {
            ScoreDimension.SECURITY: DimensionScore(
                dimension=ScoreDimension.SECURITY,
                value=0.6,
                confidence=0.7,
            ),
        }
        assert parser._compute_overall_confidence(dims) == 0.7

    def test_all_same_confidence(self) -> None:
        """All dimensions with same confidence → that value."""
        parser = ResultParser()
        dims = {
            dim: DimensionScore(dimension=dim, value=0.5, confidence=0.8) for dim in ScoreDimension
        }
        assert parser._compute_overall_confidence(dims) == 0.8


class TestGate3ThresholdBehavior:
    """Tests for Gate 3 pass/fail threshold logic."""

    def test_quality_at_threshold_passes(self) -> None:
        """overall_quality == threshold → gate3_pass = True."""
        parser = ResultParser()
        # All dims at 0.6 → quality should be 0.6
        dims = {dim.value: LLMDimensionOutput(score=0.6, confidence=0.7) for dim in ScoreDimension}
        batch = LLMBatchOutput(dimensions=dims)
        result = parser.parse_batch(
            batch,
            full_name="test/repo",
            commit_sha="abc",
            gate3_threshold=0.6,
        )

        assert result.gate3_pass is True

    def test_quality_below_threshold_fails(self) -> None:
        """overall_quality < threshold → gate3_pass = False."""
        parser = ResultParser()
        dims = {dim.value: LLMDimensionOutput(score=0.5, confidence=0.7) for dim in ScoreDimension}
        batch = LLMBatchOutput(dimensions=dims)
        result = parser.parse_batch(
            batch,
            full_name="test/repo",
            commit_sha="abc",
            gate3_threshold=0.6,
        )

        assert result.gate3_pass is False

    def test_custom_threshold_zero_everything_passes(self) -> None:
        """With threshold 0.0, even zero scores pass."""
        parser = ResultParser()
        dims = {dim.value: LLMDimensionOutput(score=0.0, confidence=0.5) for dim in ScoreDimension}
        batch = LLMBatchOutput(dimensions=dims)
        result = parser.parse_batch(
            batch,
            full_name="test/repo",
            commit_sha="abc",
            gate3_threshold=0.0,
        )

        assert result.gate3_pass is True
