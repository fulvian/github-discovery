"""Tests for cross-domain comparison guard."""

from __future__ import annotations

from github_discovery.models.enums import DomainType
from github_discovery.scoring.cross_domain import CrossDomainGuard
from tests.unit.scoring.conftest import _make_score_result


class TestCrossDomainGuard:
    """Tests for CrossDomainGuard."""

    def test_same_domain_no_warning(self) -> None:
        """Same domain comparison → no warning."""
        guard = CrossDomainGuard()
        results = [
            _make_score_result(full_name="repo/a", domain=DomainType.LIBRARY),
            _make_score_result(full_name="repo/b", domain=DomainType.LIBRARY),
        ]
        comparison = guard.compare(results)
        assert comparison.is_cross_domain is False
        assert len(comparison.warnings) == 0

    def test_cross_domain_emits_warning(self) -> None:
        """Cross-domain comparison → warning emitted."""
        guard = CrossDomainGuard()
        results = [
            _make_score_result(full_name="repo/lib", domain=DomainType.LIBRARY),
            _make_score_result(full_name="repo/cli", domain=DomainType.CLI),
        ]
        comparison = guard.compare(results)
        assert comparison.is_cross_domain is True
        assert len(comparison.warnings) > 0
        assert "cross-domain" in comparison.warnings[0].lower()

    def test_normalization_produces_scores(self) -> None:
        """Comparison produces normalized scores."""
        guard = CrossDomainGuard()
        results = [
            _make_score_result(full_name="repo/a", domain=DomainType.LIBRARY, quality_score=0.8),
            _make_score_result(full_name="repo/b", domain=DomainType.CLI, quality_score=0.6),
        ]
        comparison = guard.compare(results)
        assert len(comparison.results) == 2
        for norm in comparison.results:
            assert 0.0 <= norm.normalized_quality <= 1.0
            assert 0.0 <= norm.normalized_value_score <= 1.0

    def test_domain_summaries(self) -> None:
        """Domain summaries include stats for each domain."""
        guard = CrossDomainGuard()
        results = [
            _make_score_result(full_name="repo/a", domain=DomainType.LIBRARY, quality_score=0.8),
            _make_score_result(full_name="repo/b", domain=DomainType.LIBRARY, quality_score=0.6),
            _make_score_result(full_name="repo/c", domain=DomainType.CLI, quality_score=0.7),
        ]
        comparison = guard.compare(results)
        assert "library" in comparison.domain_summaries
        assert "cli" in comparison.domain_summaries
        assert comparison.domain_summaries["library"]["count"] == 2.0

    def test_empty_results(self) -> None:
        """Empty results produce empty comparison."""
        guard = CrossDomainGuard()
        comparison = guard.compare([])
        assert len(comparison.results) == 0
        assert len(comparison.warnings) > 0  # "No results to compare"

    def test_results_sorted_by_normalized_score(self) -> None:
        """Results are sorted by normalized value_score descending."""
        guard = CrossDomainGuard()
        results = [
            _make_score_result(full_name="repo/a", quality_score=0.5),
            _make_score_result(full_name="repo/b", quality_score=0.9),
        ]
        comparison = guard.compare(results)
        scores = [r.normalized_value_score for r in comparison.results]
        assert scores == sorted(scores, reverse=True)

    def test_warning_disabled(self) -> None:
        """Warning can be disabled via settings."""
        from github_discovery.config import ScoringSettings  # noqa: PLC0415

        settings = ScoringSettings(cross_domain_warning=False)
        guard = CrossDomainGuard(settings)
        results = [
            _make_score_result(full_name="repo/lib", domain=DomainType.LIBRARY),
            _make_score_result(full_name="repo/cli", domain=DomainType.CLI),
        ]
        comparison = guard.compare(results)
        assert comparison.is_cross_domain is True
        assert len(comparison.warnings) == 0
