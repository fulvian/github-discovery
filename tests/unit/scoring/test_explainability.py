"""Tests for explainability report generator."""

from __future__ import annotations

from github_discovery.models.enums import DomainType, ScoreDimension
from github_discovery.models.scoring import ExplainabilityReport
from github_discovery.scoring.explainability import ExplainabilityGenerator
from github_discovery.scoring.types import DimensionScoreInfo
from tests.unit.scoring.conftest import (
    _make_score_result,
)


class TestExplainabilityGenerator:
    """Tests for ExplainabilityGenerator."""

    def test_summary_report(self) -> None:
        gen = ExplainabilityGenerator()
        result = _make_score_result(quality_score=0.8, stars=100)
        report = gen.explain(result, detail_level="summary")
        assert isinstance(report, ExplainabilityReport)
        assert report.full_name == "test/repo"
        assert report.overall_quality == 0.8
        assert len(report.strengths) > 0 or len(report.weaknesses) > 0
        assert report.star_context != ""

    def test_full_report(self) -> None:
        gen = ExplainabilityGenerator()
        result = _make_score_result(quality_score=0.75)
        infos = {
            dim: DimensionScoreInfo(
                dimension=dim,
                value=0.75,
                confidence=0.8,
                source="gate3_llm",
                contributing_signals=[f"gate3_{dim.value}"],
            )
            for dim in ScoreDimension
        }
        report = gen.explain(result, infos, detail_level="full")
        assert len(report.dimension_breakdown) == 8
        for _dim_name, entry in report.dimension_breakdown.items():
            assert "score" in entry
            assert "confidence" in entry
            assert "signals" in entry

    def test_hidden_gem_indicator(self) -> None:
        gen = ExplainabilityGenerator()
        result = _make_score_result(quality_score=0.9, stars=50, confidence=0.8)
        report = gen.explain(result)
        assert report.hidden_gem_indicator is True
        assert report.hidden_gem_reason != ""

    def test_not_hidden_gem(self) -> None:
        gen = ExplainabilityGenerator()
        result = _make_score_result(quality_score=0.5, stars=5000)
        report = gen.explain(result)
        assert report.hidden_gem_indicator is False

    def test_strengths_extracted(self) -> None:
        gen = ExplainabilityGenerator()
        result = _make_score_result(quality_score=0.8)
        report = gen.explain(result, detail_level="summary")
        # With high scores, should have strengths
        assert isinstance(report.strengths, list)

    def test_weaknesses_extracted(self) -> None:
        gen = ExplainabilityGenerator()
        result = _make_score_result(quality_score=0.3)
        infos = {
            dim: DimensionScoreInfo(
                dimension=dim,
                value=0.2,
                confidence=0.1,
                source="default_neutral",
            )
            for dim in ScoreDimension
        }
        report = gen.explain(result, infos)
        assert len(report.weaknesses) > 0

    def test_recommendations_generated(self) -> None:
        gen = ExplainabilityGenerator()
        result = _make_score_result(quality_score=0.3)
        infos = {
            dim: DimensionScoreInfo(
                dimension=dim,
                value=0.2,
                confidence=0.1,
                source="default_neutral",
            )
            for dim in ScoreDimension
        }
        report = gen.explain(result, infos)
        assert isinstance(report.recommendations, list)

    def test_star_context_present(self) -> None:
        gen = ExplainabilityGenerator()
        result = _make_score_result(stars=42)
        report = gen.explain(result)
        assert "42" in report.star_context

    def test_compare_reports(self) -> None:
        gen = ExplainabilityGenerator()
        reports = [
            gen.explain(_make_score_result(full_name="repo/a", quality_score=0.8)),
            gen.explain(_make_score_result(full_name="repo/b", quality_score=0.6)),
        ]
        comparison = gen.compare_reports(reports)
        assert "repo/a" in comparison
        assert "repo/b" in comparison
        assert "Comparison" in comparison

    def test_compare_empty_reports(self) -> None:
        gen = ExplainabilityGenerator()
        comparison = gen.compare_reports([])
        assert "No reports" in comparison

    def test_star_baseline_comparison(self) -> None:
        gen = ExplainabilityGenerator()
        result = _make_score_result(quality_score=0.7, stars=50, domain=DomainType.LIBRARY)
        report = gen.explain(result)
        assert report.compared_to_star_baseline != ""

    def test_confidence_preserved(self) -> None:
        gen = ExplainabilityGenerator()
        result = _make_score_result(confidence=0.85)
        report = gen.explain(result)
        assert report.confidence == 0.85
