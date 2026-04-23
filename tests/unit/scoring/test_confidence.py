"""Tests for confidence calculator."""

from __future__ import annotations

import pytest

from github_discovery.models.enums import ScoreDimension
from github_discovery.models.screening import ScreeningResult
from github_discovery.scoring.confidence import ConfidenceCalculator
from github_discovery.scoring.types import DimensionScoreInfo
from tests.unit.scoring.conftest import (
    _make_assessment_result,
    _make_screening_result,
)


class TestConfidenceCalculator:
    """Tests for ConfidenceCalculator."""

    def test_no_data_zero_confidence(self) -> None:
        """No dimension infos → confidence 0."""
        calc = ConfidenceCalculator()
        confidence = calc.compute({})
        assert confidence == 0.0

    def test_all_defaults_low_confidence(self) -> None:
        """All dimensions default_neutral → confidence near 0."""
        calc = ConfidenceCalculator()
        infos = {
            dim: DimensionScoreInfo(dimension=dim, source="default_neutral")
            for dim in ScoreDimension
        }
        confidence = calc.compute(infos)
        assert confidence == pytest.approx(0.0, abs=0.01)

    def test_gate12_derived_medium_confidence(self) -> None:
        """Gate 1+2 derived → medium confidence (0.3-0.5 + bonus)."""
        calc = ConfidenceCalculator()
        screening = _make_screening_result()
        infos = {
            dim: DimensionScoreInfo(dimension=dim, source="gate12_derived")
            for dim in ScoreDimension
            if dim not in (ScoreDimension.FUNCTIONALITY, ScoreDimension.INNOVATION)
        }
        # Add defaults for FUNCTIONALITY and INNOVATION
        infos[ScoreDimension.FUNCTIONALITY] = DimensionScoreInfo(
            dimension=ScoreDimension.FUNCTIONALITY,
            source="default_neutral",
        )
        infos[ScoreDimension.INNOVATION] = DimensionScoreInfo(
            dimension=ScoreDimension.INNOVATION,
            source="default_neutral",
        )
        confidence = calc.compute(infos, screening=screening)
        assert 0.2 <= confidence <= 0.6

    def test_gate3_high_confidence(self) -> None:
        """Gate 3 LLM → high confidence (0.5-0.9)."""
        calc = ConfidenceCalculator()
        screening = _make_screening_result()
        assessment = _make_assessment_result()
        infos = {
            dim: DimensionScoreInfo(dimension=dim, source="gate3_llm") for dim in ScoreDimension
        }
        confidence = calc.compute(infos, screening=screening, assessment=assessment)
        assert confidence >= 0.5

    def test_confidence_gradient(self) -> None:
        """More gates → higher confidence: all > gate12 > none."""
        calc = ConfidenceCalculator()
        screening = _make_screening_result()
        assessment = _make_assessment_result()

        # Default only
        infos_default = {
            dim: DimensionScoreInfo(dimension=dim, source="default_neutral")
            for dim in ScoreDimension
        }
        c_default = calc.compute(infos_default)

        # Gate 1+2 derived
        infos_g12 = {
            dim: DimensionScoreInfo(dimension=dim, source="gate12_derived")
            for dim in ScoreDimension
            if dim not in (ScoreDimension.FUNCTIONALITY, ScoreDimension.INNOVATION)
        }
        infos_g12[ScoreDimension.FUNCTIONALITY] = DimensionScoreInfo(
            dimension=ScoreDimension.FUNCTIONALITY,
            source="default_neutral",
        )
        infos_g12[ScoreDimension.INNOVATION] = DimensionScoreInfo(
            dimension=ScoreDimension.INNOVATION,
            source="default_neutral",
        )
        c_g12 = calc.compute(infos_g12, screening=screening)

        # Gate 1+2+3
        infos_g3 = {
            dim: DimensionScoreInfo(dimension=dim, source="gate3_llm") for dim in ScoreDimension
        }
        c_g3 = calc.compute(infos_g3, screening=screening, assessment=assessment)

        assert c_g3 > c_g12 > c_default

    def test_confidence_bounds(self) -> None:
        """Confidence is always [0.0, 1.0]."""
        calc = ConfidenceCalculator()
        infos = {
            dim: DimensionScoreInfo(
                dimension=dim,
                source="gate3_llm",
                confidence=1.0,
            )
            for dim in ScoreDimension
        }
        assessment = _make_assessment_result()
        confidence = calc.compute(infos, assessment=assessment)
        assert 0.0 <= confidence <= 1.0


class TestGateCoverageBonus:
    """Tests for gate coverage bonus."""

    def test_no_gates(self) -> None:
        calc = ConfidenceCalculator()
        assert calc.gate_coverage_bonus(None, None) == 0.0

    def test_gate1_only(self) -> None:
        calc = ConfidenceCalculator()
        screening = _make_screening_result()
        # Override gate2 to None to simulate gate1-only
        screening_only_g1 = ScreeningResult(
            full_name=screening.full_name,
            gate1=screening.gate1,
            gate2=None,
        )
        assert calc.gate_coverage_bonus(screening_only_g1, None) == pytest.approx(0.0)

    def test_gate1_and_gate2(self) -> None:
        screening = _make_screening_result()
        calc = ConfidenceCalculator()
        assert calc.gate_coverage_bonus(screening, None) == pytest.approx(0.05)

    def test_all_gates(self) -> None:
        screening = _make_screening_result()
        assessment = _make_assessment_result()
        calc = ConfidenceCalculator()
        assert calc.gate_coverage_bonus(screening, assessment) == pytest.approx(0.10)
