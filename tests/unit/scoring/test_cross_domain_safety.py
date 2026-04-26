"""Tests for cross-domain z-score safety — T3.6."""

from __future__ import annotations

from github_discovery.models.enums import DomainType
from github_discovery.scoring.cross_domain import CrossDomainGuard
from tests.unit.scoring.conftest import _make_score_result


class TestCrossDomainSafety:
    """Tests for z-score skip when N<3 or near-uniform."""

    def test_skip_z_score_fewer_than_3(self) -> None:
        """Domains with <3 repos skip z-score normalization."""
        results = [
            _make_score_result(
                full_name="lib/a",
                quality_score=0.8,
                domain=DomainType.LIBRARY,
            ),
            _make_score_result(
                full_name="lib/b",
                quality_score=0.7,
                domain=DomainType.LIBRARY,
            ),
            _make_score_result(
                full_name="cli/a",
                quality_score=0.5,
                domain=DomainType.CLI,
            ),
        ]
        guard = CrossDomainGuard()
        comparison = guard.compare(results)

        # Library has only 2 repos → skip z-score
        assert any("skipped" in w.lower() for w in comparison.warnings)
        assert comparison.cross_domain_confidence < 1.0

    def test_skip_z_score_near_uniform(self) -> None:
        """Domains with near-uniform scores (std < 0.05) skip z-score."""
        results = [
            _make_score_result(
                full_name="lib/a",
                quality_score=0.800,
                domain=DomainType.LIBRARY,
            ),
            _make_score_result(
                full_name="lib/b",
                quality_score=0.801,
                domain=DomainType.LIBRARY,
            ),
            _make_score_result(
                full_name="lib/c",
                quality_score=0.799,
                domain=DomainType.LIBRARY,
            ),
        ]
        guard = CrossDomainGuard()
        comparison = guard.compare(results)

        # All same domain → not cross-domain, no skip warning
        assert comparison.is_cross_domain is False
        assert comparison.cross_domain_confidence == 0.0

    def test_near_uniform_cross_domain(self) -> None:
        """Near-uniform domains in cross-domain comparison get skipped."""
        results = [
            _make_score_result(
                full_name="lib/a",
                quality_score=0.800,
                domain=DomainType.LIBRARY,
            ),
            _make_score_result(
                full_name="lib/b",
                quality_score=0.801,
                domain=DomainType.LIBRARY,
            ),
            _make_score_result(
                full_name="lib/c",
                quality_score=0.799,
                domain=DomainType.LIBRARY,
            ),
            _make_score_result(
                full_name="cli/a",
                quality_score=0.6,
                domain=DomainType.CLI,
            ),
            _make_score_result(
                full_name="cli/b",
                quality_score=0.7,
                domain=DomainType.CLI,
            ),
        ]
        guard = CrossDomainGuard()
        comparison = guard.compare(results)

        # Library is near-uniform → skipped; CLI has only 2 → skipped
        assert any("skipped" in w.lower() for w in comparison.warnings)
        assert comparison.cross_domain_confidence == 0.0

    def test_normal_z_score_with_enough_repos(self) -> None:
        """Domains with >=3 repos and sufficient std get normalized."""
        results = [
            _make_score_result(
                full_name="lib/a",
                quality_score=0.9,
                domain=DomainType.LIBRARY,
            ),
            _make_score_result(
                full_name="lib/b",
                quality_score=0.6,
                domain=DomainType.LIBRARY,
            ),
            _make_score_result(
                full_name="lib/c",
                quality_score=0.4,
                domain=DomainType.LIBRARY,
            ),
            _make_score_result(
                full_name="cli/a",
                quality_score=0.7,
                domain=DomainType.CLI,
            ),
            _make_score_result(
                full_name="cli/b",
                quality_score=0.5,
                domain=DomainType.CLI,
            ),
            _make_score_result(
                full_name="cli/c",
                quality_score=0.8,
                domain=DomainType.CLI,
            ),
        ]
        guard = CrossDomainGuard()
        comparison = guard.compare(results)

        # Both domains have enough repos and non-uniform scores
        assert comparison.cross_domain_confidence == 1.0
        assert len(comparison.results) == 6

    def test_empty_results_confidence_zero(self) -> None:
        """Empty results → confidence 0."""
        guard = CrossDomainGuard()
        comparison = guard.compare([])
        assert comparison.cross_domain_confidence == 0.0

    def test_single_result_confidence_zero(self) -> None:
        """Single result → skip z-score → confidence 0."""
        results = [
            _make_score_result(
                full_name="lib/a",
                quality_score=0.8,
                domain=DomainType.LIBRARY,
            ),
        ]
        guard = CrossDomainGuard()
        comparison = guard.compare(results)
        assert comparison.cross_domain_confidence == 0.0

    def test_skipped_domain_uses_original_scores(self) -> None:
        """When z-score is skipped, normalized_score equals original."""
        results = [
            _make_score_result(
                full_name="lib/a",
                quality_score=0.8,
                domain=DomainType.LIBRARY,
            ),
            _make_score_result(
                full_name="lib/b",
                quality_score=0.7,
                domain=DomainType.LIBRARY,
            ),
        ]
        guard = CrossDomainGuard()
        comparison = guard.compare(results)

        # Both in same domain with <3 repos → skip z-score
        for norm in comparison.results:
            # When z-score is skipped, normalized equals original (clamped)
            assert norm.normalized_quality == norm.original_quality

    def test_get_skip_domains_method(self) -> None:
        """_get_skip_domains correctly identifies small and uniform domains."""
        summaries = {
            "library": {"mean": 0.7, "std": 0.2, "count": 5.0, "vs_mean": 0.7, "vs_std": 0.2},
            "cli": {"mean": 0.5, "std": 0.1, "count": 2.0, "vs_mean": 0.5, "vs_std": 0.1},
            "backend": {"mean": 0.6, "std": 0.01, "count": 4.0, "vs_mean": 0.6, "vs_std": 0.01},
        }
        skip = CrossDomainGuard._get_skip_domains(summaries)
        # cli: count=2 < 3 → skip
        # backend: std=0.01 < 0.05 → skip
        # library: count=5 >= 3, std=0.2 >= 0.05 → don't skip
        assert "cli" in skip
        assert "backend" in skip
        assert "library" not in skip
