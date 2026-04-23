"""Tests for scoring types."""

from __future__ import annotations

from github_discovery.models.enums import DomainType, ScoreDimension
from github_discovery.scoring.types import (
    DimensionScoreInfo,
    ScoringContext,
    ScoringInput,
)


class TestDimensionScoreInfo:
    """Tests for DimensionScoreInfo model."""

    def test_default_values(self) -> None:
        info = DimensionScoreInfo(dimension=ScoreDimension.CODE_QUALITY)
        assert info.value == 0.5
        assert info.confidence == 0.0
        assert info.source == "default_neutral"
        assert info.contributing_signals == []

    def test_custom_values(self) -> None:
        info = DimensionScoreInfo(
            dimension=ScoreDimension.TESTING,
            value=0.8,
            confidence=0.7,
            source="gate3_llm",
            contributing_signals=["test_footprint", "ci_cd"],
        )
        assert info.value == 0.8
        assert info.confidence == 0.7
        assert info.source == "gate3_llm"
        assert len(info.contributing_signals) == 2

    def test_value_bounds(self) -> None:
        """Value must be between 0.0 and 1.0."""
        DimensionScoreInfo(dimension=ScoreDimension.CODE_QUALITY, value=0.0)
        DimensionScoreInfo(dimension=ScoreDimension.CODE_QUALITY, value=1.0)


class TestScoringInput:
    """Tests for ScoringInput model."""

    def test_candidate_only(self, sample_candidate) -> None:
        inp = ScoringInput(candidate=sample_candidate)
        assert inp.candidate.full_name == "test/repo"
        assert inp.screening is None
        assert inp.assessment is None

    def test_with_screening(self, sample_candidate, sample_screening_result) -> None:
        inp = ScoringInput(
            candidate=sample_candidate,
            screening=sample_screening_result,
        )
        assert inp.screening is not None
        assert inp.screening.gate1 is not None

    def test_with_all_data(
        self,
        sample_candidate,
        sample_screening_result,
        sample_assessment_result,
    ) -> None:
        inp = ScoringInput(
            candidate=sample_candidate,
            screening=sample_screening_result,
            assessment=sample_assessment_result,
        )
        assert inp.candidate is not None
        assert inp.screening is not None
        assert inp.assessment is not None


class TestScoringContext:
    """Tests for ScoringContext model."""

    def test_basic_context(self, sample_candidate) -> None:
        ctx = ScoringContext(inputs=[ScoringInput(candidate=sample_candidate)])
        assert len(ctx.inputs) == 1
        assert ctx.domain_override is None
        assert ctx.session_id is None

    def test_with_overrides(self, sample_candidate) -> None:
        ctx = ScoringContext(
            inputs=[ScoringInput(candidate=sample_candidate)],
            domain_override=DomainType.CLI,
            session_id="test-session-123",
        )
        assert ctx.domain_override == DomainType.CLI
        assert ctx.session_id == "test-session-123"

    def test_multiple_inputs(self, sample_candidate) -> None:
        from tests.unit.scoring.conftest import _make_candidate  # noqa: PLC0415

        candidates = [_make_candidate(full_name=f"test/repo{i}") for i in range(5)]
        inputs = [ScoringInput(candidate=c) for c in candidates]
        ctx = ScoringContext(inputs=inputs)
        assert len(ctx.inputs) == 5
