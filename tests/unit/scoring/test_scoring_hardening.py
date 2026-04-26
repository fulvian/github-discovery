"""T2.1-T2.3 - Scoring logic hardening tests.

T2.1: Revised _DERIVATION_MAP (ARCHITECTURE empty, CODE_QUALITY rebalanced)
T2.2: Weighted confidence using profile weights + missing-dimension penalty
T2.3: Per-dimension variable confidence from Gate 1+2
"""

from __future__ import annotations

import pytest

from github_discovery.models.enums import DomainType, ScoreDimension
from github_discovery.scoring.confidence import (
    _DIMENSION_CONFIDENCE_FROM_GATE12,
    ConfidenceCalculator,
)
from github_discovery.scoring.engine import _DERIVATION_MAP, ScoringEngine
from github_discovery.scoring.profiles import ProfileRegistry
from github_discovery.scoring.types import DimensionScoreInfo
from tests.unit.scoring.conftest import (
    _make_candidate,
    _make_screening_result,
)


class TestDerivationMapT21:
    """T2.1 - Verify revised _DERIVATION_MAP."""

    def test_architecture_not_derivable(self) -> None:
        """ARCHITECTURE has empty derivation map (not derivable from Gate 1+2)."""
        assert _DERIVATION_MAP[ScoreDimension.ARCHITECTURE] == []

    def test_code_quality_includes_complexity_and_test(self) -> None:
        """CODE_QUALITY now includes complexity and test_footprint signals."""
        subs = {name for name, _ in _DERIVATION_MAP[ScoreDimension.CODE_QUALITY]}
        assert "complexity" in subs
        assert "test_footprint" in subs
        assert "review_practice" in subs
        assert "ci_cd" in subs

    def test_code_quality_weights_sum_to_one(self) -> None:
        """CODE_QUALITY derivation weights must sum to ~1.0."""
        total = sum(w for _, w in _DERIVATION_MAP[ScoreDimension.CODE_QUALITY])
        assert abs(total - 1.0) < 0.01

    def test_documentation_excludes_review_practice(self) -> None:
        """DOCUMENTATION no longer uses review_practice (no causal relation)."""
        subs = {name for name, _ in _DERIVATION_MAP[ScoreDimension.DOCUMENTATION]}
        assert "review_practice" not in subs
        assert "hygiene" in subs
        assert "release_discipline" in subs

    def test_functionality_not_derivable(self) -> None:
        """FUNCTIONALITY has empty derivation map."""
        assert _DERIVATION_MAP[ScoreDimension.FUNCTIONALITY] == []

    def test_innovation_not_derivable(self) -> None:
        """INNOVATION has empty derivation map."""
        assert _DERIVATION_MAP[ScoreDimension.INNOVATION] == []

    def test_all_derived_dimensions_weights_sum_to_one(self) -> None:
        """Every non-empty derivation entry must have weights summing to ~1.0."""
        for dim, mappings in _DERIVATION_MAP.items():
            if not mappings:
                continue
            total = sum(w for _, w in mappings)
            assert abs(total - 1.0) < 0.01, f"{dim.value} weights sum to {total:.4f}, expected 1.0"

    def test_architecture_defaults_without_gate3(self) -> None:
        """ARCHITECTURE defaults to 0.5 without Gate 3 (empty derivation)."""
        engine = ScoringEngine()
        candidate = _make_candidate()
        screening = _make_screening_result()
        result = engine.score(candidate, screening=screening)
        assert result.dimension_scores[ScoreDimension.ARCHITECTURE] == 0.5

    def test_code_quality_uses_complexity(self) -> None:
        """CODE_QUALITY derived score reflects complexity sub-score."""
        engine = ScoringEngine()
        candidate = _make_candidate()
        screening = _make_screening_result(complexity=0.9)
        result = engine.score(candidate, screening=screening)
        # With complexity=0.9 weighted at 0.35, CODE_QUALITY should be > 0.5
        assert result.dimension_scores[ScoreDimension.CODE_QUALITY] > 0.5


class TestWeightedConfidenceT22:
    """T2.2 - Confidence weighted by profile weights."""

    def test_weighted_confidence_with_profile(self) -> None:
        """Weighted confidence differs from unweighted average."""
        calc = ConfidenceCalculator()
        registry = ProfileRegistry()
        profile = registry.get(DomainType.LIBRARY)
        screening = _make_screening_result()

        # Build infos with mixed sources
        infos: dict[ScoreDimension, DimensionScoreInfo] = {}
        for dim in ScoreDimension:
            if dim in (ScoreDimension.FUNCTIONALITY, ScoreDimension.INNOVATION):
                infos[dim] = DimensionScoreInfo(
                    dimension=dim,
                    source="default_neutral",
                )
            else:
                infos[dim] = DimensionScoreInfo(
                    dimension=dim,
                    source="gate12_derived",
                )

        weighted = calc.compute(infos, screening=screening, profile=profile)
        unweighted = calc.compute(infos, screening=screening, profile=None)

        # They should differ because profile weights are not uniform
        assert weighted != unweighted

    def test_missing_critical_dimension_penalty(self) -> None:
        """Missing dimension with weight >= 0.15 triggers 0.10 penalty."""
        calc = ConfidenceCalculator()
        registry = ProfileRegistry()
        profile = registry.get(DomainType.LIBRARY)

        # All dimensions default_neutral - some with high weight
        infos = {
            dim: DimensionScoreInfo(dimension=dim, source="default_neutral")
            for dim in ScoreDimension
        }
        confidence = calc.compute(infos, profile=profile)

        # Should be 0.0 (all defaults -> 0, plus penalty stays clamped at 0)
        assert confidence == 0.0

    def test_ml_lib_partial_coverage_lower_confidence(self) -> None:
        """ML_LIB with Gate 1+2 only has lower confidence than LIBRARY.

        ML_LIB weights FUNCTIONALITY at 0.25 and INNOVATION at 0.15,
        both non-derivable -> confidence penalty applies.
        """
        calc = ConfidenceCalculator()
        registry = ProfileRegistry()
        profile_ml = registry.get(DomainType.ML_LIB)
        profile_lib = registry.get(DomainType.LIBRARY)
        screening = _make_screening_result()

        # Gate 1+2 derived for derivable dims, default for rest
        infos: dict[ScoreDimension, DimensionScoreInfo] = {}
        for dim in ScoreDimension:
            if dim in (ScoreDimension.FUNCTIONALITY, ScoreDimension.INNOVATION):
                infos[dim] = DimensionScoreInfo(
                    dimension=dim,
                    source="default_neutral",
                )
            else:
                infos[dim] = DimensionScoreInfo(
                    dimension=dim,
                    source="gate12_derived",
                )

        conf_ml = calc.compute(infos, screening=screening, profile=profile_ml)
        conf_lib = calc.compute(infos, screening=screening, profile=profile_lib)

        # ML_LIB should have lower confidence (FUNCTIONALITY=0.25 missing)
        assert conf_ml < conf_lib


class TestPerDimensionConfidenceT23:
    """T2.3 - Per-dimension variable confidence from Gate 1+2."""

    def test_testing_has_highest_gate12_confidence(self) -> None:
        """TESTING has the highest Gate 1+2 confidence (strong mapping)."""
        calc = ConfidenceCalculator()
        screening = _make_screening_result()

        testing_conf = calc.compute_dimension_confidence(
            ScoreDimension.TESTING,
            "gate12_derived",
            screening,
            None,
        )
        arch_conf = calc.compute_dimension_confidence(
            ScoreDimension.ARCHITECTURE,
            "gate12_derived",
            screening,
            None,
        )

        assert testing_conf > arch_conf
        assert testing_conf == pytest.approx(0.55)

    def test_architecture_gate12_confidence_is_zero(self) -> None:
        """ARCHITECTURE has zero Gate 1+2 confidence (empty derivation)."""
        calc = ConfidenceCalculator()
        conf = calc.compute_dimension_confidence(
            ScoreDimension.ARCHITECTURE,
            "gate12_derived",
            None,
            None,
        )
        assert conf == 0.0

    def test_functionality_gate12_confidence_is_zero(self) -> None:
        """FUNCTIONALITY has zero Gate 1+2 confidence."""
        calc = ConfidenceCalculator()
        conf = calc.compute_dimension_confidence(
            ScoreDimension.FUNCTIONALITY,
            "gate12_derived",
            None,
            None,
        )
        assert conf == 0.0

    def test_all_dimensions_in_map(self) -> None:
        """All 8 dimensions have a confidence entry."""
        assert set(_DIMENSION_CONFIDENCE_FROM_GATE12.keys()) == set(ScoreDimension)

    def test_non_derivable_dims_have_zero_confidence(self) -> None:
        """ARCHITECTURE, FUNCTIONALITY, INNOVATION are non-derivable."""
        for dim in (
            ScoreDimension.ARCHITECTURE,
            ScoreDimension.FUNCTIONALITY,
            ScoreDimension.INNOVATION,
        ):
            assert _DIMENSION_CONFIDENCE_FROM_GATE12[dim] == 0.0, (
                f"{dim.value} should have zero Gate 1+2 confidence"
            )

    def test_derivable_dims_have_positive_confidence(self) -> None:
        """Derivable dimensions have positive Gate 1+2 confidence."""
        for dim in (
            ScoreDimension.CODE_QUALITY,
            ScoreDimension.TESTING,
            ScoreDimension.DOCUMENTATION,
            ScoreDimension.MAINTENANCE,
            ScoreDimension.SECURITY,
        ):
            assert _DIMENSION_CONFIDENCE_FROM_GATE12[dim] > 0.0, (
                f"{dim.value} should have positive Gate 1+2 confidence"
            )
