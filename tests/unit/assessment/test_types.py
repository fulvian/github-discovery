"""Tests for assessment type models.

Tests RepoContent, HeuristicScores, AssessmentContext,
LLMDimensionOutput, and LLMBatchOutput Pydantic models.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from github_discovery.assessment.types import (
    AssessmentContext,
    HeuristicScores,
    LLMBatchOutput,
    LLMDimensionOutput,
    RepoContent,
)
from github_discovery.models.enums import ScoreDimension


class TestRepoContent:
    """Tests for the RepoContent model."""

    def test_creation_with_defaults(self) -> None:
        """RepoContent can be created with only required fields."""
        content = RepoContent(full_name="test/repo")

        assert content.full_name == "test/repo"
        assert content.content == ""
        assert content.total_files == 0
        assert content.total_tokens == 0
        assert content.total_chars == 0
        assert content.compressed is False
        assert content.truncated is False
        assert content.clone_url == ""

    def test_creation_with_all_fields(self) -> None:
        """RepoContent accepts all optional fields."""
        content = RepoContent(
            full_name="test/repo",
            content="print('hello')",
            total_files=5,
            total_tokens=100,
            total_chars=400,
            compressed=True,
            truncated=True,
            clone_url="https://github.com/test/repo",
        )

        assert content.content == "print('hello')"
        assert content.total_files == 5
        assert content.total_tokens == 100
        assert content.total_chars == 400
        assert content.compressed is True
        assert content.truncated is True
        assert content.clone_url == "https://github.com/test/repo"

    def test_total_files_rejects_negative(self) -> None:
        """total_files with ge=0 rejects negative values."""
        with pytest.raises(ValidationError):
            RepoContent(full_name="test/repo", total_files=-1)

    def test_total_tokens_rejects_negative(self) -> None:
        """total_tokens with ge=0 rejects negative values."""
        with pytest.raises(ValidationError):
            RepoContent(full_name="test/repo", total_tokens=-10)

    def test_total_chars_rejects_negative(self) -> None:
        """total_chars with ge=0 rejects negative values."""
        with pytest.raises(ValidationError):
            RepoContent(full_name="test/repo", total_chars=-5)

    def test_zero_values_accepted(self) -> None:
        """Zero values pass ge=0 validation."""
        content = RepoContent(
            full_name="test/repo",
            total_files=0,
            total_tokens=0,
            total_chars=0,
        )

        assert content.total_files == 0
        assert content.total_tokens == 0
        assert content.total_chars == 0


class TestHeuristicScores:
    """Tests for the HeuristicScores model."""

    def test_creation_with_defaults(self) -> None:
        """HeuristicScores can be created with only full_name."""
        scores = HeuristicScores(full_name="test/repo")

        assert scores.full_name == "test/repo"
        assert scores.file_count == 0
        assert scores.has_tests is False
        assert scores.has_ci is False
        assert scores.has_docs is False
        assert scores.has_security_policy is False
        assert scores.language_distribution == {}
        assert scores.structure_score == 0.5
        assert scores.size_category == "medium"

    def test_creation_with_all_fields(self) -> None:
        """HeuristicScores accepts all optional fields."""
        scores = HeuristicScores(
            full_name="test/repo",
            file_count=42,
            has_tests=True,
            has_ci=True,
            has_docs=True,
            has_security_policy=True,
            language_distribution={"Python": 30, "JavaScript": 12},
            structure_score=0.85,
            size_category="small",
        )

        assert scores.file_count == 42
        assert scores.has_tests is True
        assert scores.language_distribution == {"Python": 30, "JavaScript": 12}
        assert scores.structure_score == 0.85

    def test_file_count_rejects_negative(self) -> None:
        """file_count with ge=0 rejects negative values."""
        with pytest.raises(ValidationError):
            HeuristicScores(full_name="test/repo", file_count=-1)

    def test_structure_score_rejects_below_zero(self) -> None:
        """structure_score with ge=0.0 rejects negative values."""
        with pytest.raises(ValidationError):
            HeuristicScores(full_name="test/repo", structure_score=-0.1)

    def test_structure_score_rejects_above_one(self) -> None:
        """structure_score with le=1.0 rejects values > 1.0."""
        with pytest.raises(ValidationError):
            HeuristicScores(full_name="test/repo", structure_score=1.5)

    def test_structure_score_boundary_values(self) -> None:
        """structure_score accepts exact boundary values 0.0 and 1.0."""
        min_scores = HeuristicScores(full_name="test/repo", structure_score=0.0)
        max_scores = HeuristicScores(full_name="test/repo", structure_score=1.0)

        assert min_scores.structure_score == 0.0
        assert max_scores.structure_score == 1.0


class TestAssessmentContext:
    """Tests for the AssessmentContext model."""

    def test_creation_with_defaults(self) -> None:
        """AssessmentContext has sensible defaults."""
        ctx = AssessmentContext()

        assert ctx.candidates == []
        assert ctx.screening_results == {}
        assert ctx.gate3_threshold == 0.6
        assert ctx.session_id is None
        assert ctx.batch_mode is True

    def test_default_dimensions_are_all_eight(self) -> None:
        """Default dimensions contain all 8 ScoreDimension values."""
        ctx = AssessmentContext()

        assert len(ctx.dimensions) == 8
        assert set(ctx.dimensions) == set(ScoreDimension)

    def test_custom_dimensions(self) -> None:
        """dimensions can be overridden to a subset."""
        ctx = AssessmentContext(
            dimensions=[ScoreDimension.CODE_QUALITY, ScoreDimension.SECURITY],
        )

        assert len(ctx.dimensions) == 2
        assert ScoreDimension.CODE_QUALITY in ctx.dimensions
        assert ScoreDimension.SECURITY in ctx.dimensions

    def test_gate3_threshold_rejects_invalid(self) -> None:
        """gate3_threshold with ge=0.0, le=1.0 rejects out-of-range values."""
        with pytest.raises(ValidationError):
            AssessmentContext(gate3_threshold=-0.1)

        with pytest.raises(ValidationError):
            AssessmentContext(gate3_threshold=1.5)

    def test_gate3_threshold_boundary_values(self) -> None:
        """gate3_threshold accepts exact boundary values."""
        min_ctx = AssessmentContext(gate3_threshold=0.0)
        max_ctx = AssessmentContext(gate3_threshold=1.0)

        assert min_ctx.gate3_threshold == 0.0
        assert max_ctx.gate3_threshold == 1.0

    def test_with_session_id(self) -> None:
        """session_id can be set for cross-session workflows."""
        ctx = AssessmentContext(session_id="sess-123")

        assert ctx.session_id == "sess-123"

    def test_batch_mode_can_be_disabled(self) -> None:
        """batch_mode can be set to False for per-dimension assessment."""
        ctx = AssessmentContext(batch_mode=False)

        assert ctx.batch_mode is False


class TestLLMDimensionOutput:
    """Tests for the LLMDimensionOutput model."""

    def test_creation_with_defaults(self) -> None:
        """LLMDimensionOutput has sensible defaults."""
        output = LLMDimensionOutput(score=0.8)

        assert output.score == 0.8
        assert output.explanation == ""
        assert output.evidence == []
        assert output.confidence == 0.7

    def test_creation_with_all_fields(self) -> None:
        """LLMDimensionOutput accepts all optional fields."""
        output = LLMDimensionOutput(
            score=0.9,
            explanation="Excellent code quality.",
            evidence=["Consistent formatting", "Type hints throughout"],
            confidence=0.85,
        )

        assert output.score == 0.9
        assert output.explanation == "Excellent code quality."
        assert len(output.evidence) == 2
        assert output.confidence == 0.85

    def test_score_rejects_below_zero(self) -> None:
        """score with ge=0.0 rejects negative values."""
        with pytest.raises(ValidationError):
            LLMDimensionOutput(score=-0.1)

    def test_score_rejects_above_one(self) -> None:
        """score with le=1.0 rejects values > 1.0."""
        with pytest.raises(ValidationError):
            LLMDimensionOutput(score=1.5)

    def test_confidence_rejects_invalid_range(self) -> None:
        """confidence with ge=0.0, le=1.0 rejects out-of-range."""
        with pytest.raises(ValidationError):
            LLMDimensionOutput(score=0.5, confidence=-0.1)

        with pytest.raises(ValidationError):
            LLMDimensionOutput(score=0.5, confidence=1.5)

    def test_boundary_score_values(self) -> None:
        """score accepts exact boundary values 0.0 and 1.0."""
        min_output = LLMDimensionOutput(score=0.0)
        max_output = LLMDimensionOutput(score=1.0)

        assert min_output.score == 0.0
        assert max_output.score == 1.0

    def test_evidence_is_list_of_strings(self) -> None:
        """evidence accepts a list of strings."""
        output = LLMDimensionOutput(
            score=0.7,
            evidence=["Point 1", "Point 2", "Point 3"],
        )

        assert output.evidence == ["Point 1", "Point 2", "Point 3"]


class TestLLMBatchOutput:
    """Tests for the LLMBatchOutput model."""

    def test_creation_with_defaults(self) -> None:
        """LLMBatchOutput has sensible defaults."""
        output = LLMBatchOutput()

        assert output.dimensions == {}
        assert output.overall_explanation == ""

    def test_creation_with_dimensions(self) -> None:
        """LLMBatchOutput accepts dimension outputs keyed by name."""
        dims = {
            "code_quality": LLMDimensionOutput(score=0.8),
            "testing": LLMDimensionOutput(score=0.7),
        }
        output = LLMBatchOutput(
            dimensions=dims,
            overall_explanation="Good overall quality.",
        )

        assert len(output.dimensions) == 2
        assert output.dimensions["code_quality"].score == 0.8
        assert output.dimensions["testing"].score == 0.7
        assert output.overall_explanation == "Good overall quality."

    def test_empty_dimensions_is_valid(self) -> None:
        """LLMBatchOutput with no dimensions is valid."""
        output = LLMBatchOutput()

        assert len(output.dimensions) == 0

    def test_full_eight_dimensions(self) -> None:
        """LLMBatchOutput with all 8 dimensions."""
        dimensions = {dim.value: LLMDimensionOutput(score=0.75) for dim in ScoreDimension}
        output = LLMBatchOutput(dimensions=dimensions)

        assert len(output.dimensions) == 8
