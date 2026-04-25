"""Explainability report generator.

Every score must be explainable per feature and dimension (Blueprint §3).
Reports provide both human-readable explanations and machine-readable
feature breakdowns for transparency.

Stars are metadata (corroboration level), not a scoring signal.
Hidden gem is an informational label, not a score modifier.

Two detail levels:
- "summary": top strengths, weaknesses, hidden gem indicator, corroboration
- "full": complete dimension breakdown, all evidence, recommendations
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from github_discovery.models.scoring import DomainProfile, ExplainabilityReport, ScoreResult
from github_discovery.scoring.profiles import ProfileRegistry
from github_discovery.scoring.types import DimensionScoreInfo
from github_discovery.scoring.value_score import ValueScoreCalculator

if TYPE_CHECKING:
    from github_discovery.models.assessment import DeepAssessmentResult
    from github_discovery.models.enums import ScoreDimension
    from github_discovery.models.screening import ScreeningResult

logger = structlog.get_logger("github_discovery.scoring.explainability")

_WEAKNESS_SCORE_THRESHOLD = 0.5
_LOW_CONFIDENCE_THRESHOLD = 0.3


class ExplainabilityGenerator:
    """Generate human-readable explainability reports.

    Every score is explainable per feature and dimension (Blueprint §3).
    Reports include strengths, weaknesses, recommendations, and star context.
    """

    def __init__(
        self,
        value_calculator: ValueScoreCalculator | None = None,
        profile_registry: ProfileRegistry | None = None,
    ) -> None:
        """Initialize ExplainabilityGenerator with optional dependencies."""
        self._value_calc = value_calculator or ValueScoreCalculator()
        self._registry = profile_registry or ProfileRegistry()

    def explain(
        self,
        score_result: ScoreResult,
        dimension_infos: dict[ScoreDimension, DimensionScoreInfo] | None = None,
        screening: ScreeningResult | None = None,
        assessment: DeepAssessmentResult | None = None,
        *,
        detail_level: str = "summary",
    ) -> ExplainabilityReport:
        """Generate explainability report for a scored repo.

        Args:
            score_result: The scoring result to explain.
            dimension_infos: Per-dimension metadata (sources, signals).
            screening: Gate 1+2 results for evidence extraction.
            assessment: Gate 3 results for evidence extraction.
            detail_level: "summary" (concise) or "full" (complete).

        Returns:
            ExplainabilityReport with breakdown, strengths, weaknesses.
        """
        if dimension_infos is None:
            dimension_infos = self._build_default_infos(score_result)

        profile = self._registry.get(score_result.domain)

        strengths = self._extract_strengths(dimension_infos, score_result)
        weaknesses = self._extract_weaknesses(dimension_infos, score_result)
        recommendations = self._generate_recommendations(weaknesses, dimension_infos)
        star_ctx = self._build_star_context(score_result, profile)

        is_gem, gem_reason = self._value_calc.is_hidden_gem(
            score_result.quality_score,
            score_result.stars,
            score_result.value_score,
        )

        breakdown = self._dimension_breakdown(
            score_result,
            dimension_infos,
            detail_level,
        )

        compared = self._star_baseline_comparison(score_result, profile)

        return ExplainabilityReport(
            full_name=score_result.full_name,
            domain=score_result.domain,
            overall_quality=score_result.quality_score,
            value_score=score_result.value_score,
            dimension_breakdown=breakdown,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
            star_context=star_ctx,
            hidden_gem_indicator=is_gem,
            hidden_gem_reason=gem_reason,
            compared_to_star_baseline=compared,
            confidence=score_result.confidence,
            generated_at=datetime.now(UTC),
        )

    def compare_reports(
        self,
        reports: list[ExplainabilityReport],
    ) -> str:
        """Generate side-by-side comparison text for multiple repos.

        Used by MCP tool compare_repos for decision-making.
        """
        if not reports:
            return "No reports to compare."

        lines: list[str] = ["# Repository Comparison\n"]

        for report in reports:
            lines.append(f"## {report.full_name} ({report.domain.value})")
            lines.append(
                f"- Quality: {report.overall_quality:.2f}/1.0 | "
                f"Value: {report.value_score:.2f} | "
                f"Confidence: {report.confidence:.2f}",
            )
            if report.hidden_gem_indicator:
                lines.append(f"- **Hidden Gem** ✓ — {report.hidden_gem_reason}")

            if report.strengths:
                lines.append("- **Strengths**: " + "; ".join(report.strengths[:3]))
            if report.weaknesses:
                lines.append("- **Weaknesses**: " + "; ".join(report.weaknesses[:3]))
            lines.append("")

        return "\n".join(lines)

    def _extract_strengths(
        self,
        dimension_infos: dict[ScoreDimension, DimensionScoreInfo],
        score_result: ScoreResult,
    ) -> list[str]:
        """Extract top 3-5 strengths from dimension scores.

        Strengths are dimensions where score > 0.7 or significantly
        above the average dimension score.
        """
        if not score_result.dimension_scores:
            return []

        avg = sum(score_result.dimension_scores.values()) / len(
            score_result.dimension_scores,
        )
        threshold = max(0.7, avg)

        strengths: list[str] = []
        sorted_dims = sorted(
            score_result.dimension_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        for dim, score in sorted_dims[:5]:
            if score >= threshold:
                info = dimension_infos.get(dim)
                source = info.source if info else "unknown"
                strengths.append(
                    f"{dim.value} ({score:.2f}, {source})",
                )

        return strengths

    def _extract_weaknesses(
        self,
        dimension_infos: dict[ScoreDimension, DimensionScoreInfo],
        score_result: ScoreResult,
    ) -> list[str]:
        """Extract top 3-5 weaknesses from dimension scores.

        Weaknesses are dimensions where score < 0.5 or confidence < 0.3.
        """
        if not score_result.dimension_scores:
            return []

        weaknesses: list[str] = []
        sorted_dims = sorted(
            score_result.dimension_scores.items(),
            key=lambda x: x[1],
        )

        for dim, score in sorted_dims[:5]:
            info = dimension_infos.get(dim)
            if score < _WEAKNESS_SCORE_THRESHOLD or (
                info is not None and info.confidence < _LOW_CONFIDENCE_THRESHOLD
            ):
                reason = (
                    f"low score ({score:.2f})"
                    if score < _WEAKNESS_SCORE_THRESHOLD
                    else "low confidence"
                )
                weaknesses.append(f"{dim.value} — {reason}")

        return weaknesses

    def _generate_recommendations(
        self,
        weaknesses: list[str],
        dimension_infos: dict[ScoreDimension, DimensionScoreInfo],
    ) -> list[str]:
        """Generate actionable recommendations based on weaknesses."""
        recommendations: list[str] = []
        seen_dims: set[str] = set()

        for weakness in weaknesses:
            dim_name = weakness.split(" — ")[0]
            if dim_name in seen_dims:
                continue
            seen_dims.add(dim_name)

            recommendation = self._dim_recommendation(dim_name)
            if recommendation:
                recommendations.append(recommendation)

        return recommendations

    def _dim_recommendation(self, dim_name: str) -> str | None:
        """Get a recommendation string for a dimension weakness."""
        recommendations_map: dict[str, str] = {
            "testing": "Add comprehensive test coverage and CI integration",
            "documentation": "Improve README, add API docs and usage examples",
            "security": "Add SECURITY.md, enable dependabot, pin dependencies",
            "maintenance": "Increase commit cadence, add contributing guidelines",
            "code_quality": "Establish code review practices, add linting config",
            "architecture": "Reduce complexity, improve module separation",
        }
        return recommendations_map.get(dim_name)

    def _build_star_context(
        self,
        score_result: ScoreResult,
        profile: DomainProfile,
    ) -> str:
        """Build star context string with domain awareness."""
        return self._value_calc.star_context(
            score_result.quality_score,
            score_result.stars,
            score_result.domain,
        )

    def _dimension_breakdown(
        self,
        score_result: ScoreResult,
        dimension_infos: dict[ScoreDimension, DimensionScoreInfo],
        detail_level: str,
    ) -> dict[str, dict[str, object]]:
        """Build per-dimension breakdown for the report."""
        breakdown: dict[str, dict[str, object]] = {}

        for dim, score in score_result.dimension_scores.items():
            info = dimension_infos.get(dim)
            entry: dict[str, object] = {
                "score": score,
                "source": info.source if info else "unknown",
            }

            if detail_level == "full":
                entry["confidence"] = info.confidence if info else 0.0
                entry["signals"] = info.contributing_signals if info else []

            breakdown[dim.value] = entry

        return breakdown

    def _star_baseline_comparison(
        self,
        score_result: ScoreResult,
        profile: DomainProfile,
    ) -> str:
        """Describe corroboration level relative to domain baseline.

        Stars indicate how many users have validated quality.
        This is informational — it never changes the quality_score.
        """
        if score_result.stars == 0:
            return "No stars — quality based purely on technical assessment"
        if score_result.stars < profile.star_baseline * 0.1:
            return (
                f"Corroboration: low ({score_result.stars} stars vs "
                f"{profile.star_baseline:.0f} domain baseline). "
                f"Quality score is the primary signal."
            )
        if score_result.stars < profile.star_baseline:
            return (
                f"Corroboration: emerging ({score_result.stars} stars vs "
                f"{profile.star_baseline:.0f} domain baseline). "
                f"Community interest aligns with quality assessment."
            )
        return (
            f"Corroboration: strong ({score_result.stars:,} stars vs "
            f"{profile.star_baseline:.0f} domain baseline). "
            f"Broad community adoption validates the quality score."
        )

    def _build_default_infos(
        self,
        score_result: ScoreResult,
    ) -> dict[ScoreDimension, DimensionScoreInfo]:
        """Build default dimension infos from score result when not provided."""
        infos: dict[ScoreDimension, DimensionScoreInfo] = {}
        for dim, score in score_result.dimension_scores.items():
            infos[dim] = DimensionScoreInfo(
                dimension=dim,
                value=score,
                confidence=score_result.confidence,
                source="unknown",
            )
        return infos
