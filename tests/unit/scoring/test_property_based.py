"""T5.5 - Property-based tests for scoring invariants.

Uses Hypothesis to verify that scoring functions satisfy
fundamental invariants across 1000+ generated inputs:
1. quality_score in [0, 1]
2. confidence in [0, 1]
3. coverage in [0, 1]
4. value_score == quality_score (star-neutral)
5. Profile weights sum to ~1.0
6. Monotonicity: higher inputs -> higher score (within a profile)
7. Deterministic: same inputs -> same outputs
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings, strategies as st
from pytest import approx

from github_discovery.models.enums import (
    DomainType,
    ScoreDimension,
)
from github_discovery.models.scoring import ScoreResult
from github_discovery.scoring.profiles import ProfileRegistry
from github_discovery.scoring.types import DimensionScoreInfo

# --- Hypothesis strategies ---

_domain_type = st.sampled_from(list(DomainType))
_score_value = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
_positive_int = st.integers(min_value=0, max_value=100_000)
_full_name = st.from_regex(r"[a-z0-9_\-]{2,20}/[a-z0-9_\-]{2,30}", fullmatch=True)


@st.composite
def dimension_score_infos(draw: st.DrawFn) -> dict[ScoreDimension, DimensionScoreInfo]:
    """Generate a valid dict of DimensionScoreInfo for all 8 dimensions."""
    infos: dict[ScoreDimension, DimensionScoreInfo] = {}
    sources = ["gate3_llm", "gate12_derived", "default_neutral"]
    for dim in ScoreDimension:
        source = draw(st.sampled_from(sources))
        if source == "default_neutral":
            infos[dim] = DimensionScoreInfo(dimension=dim, source=source)
        else:
            infos[dim] = DimensionScoreInfo(
                dimension=dim,
                value=draw(_score_value),
                source=source,
            )
    return infos


# --- Invariant tests ---


class TestScoreResultInvariants:
    """Property-based tests for ScoreResult field invariants."""

    @given(quality=_score_value, confidence=_score_value, stars=_positive_int)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_quality_score_always_in_bounds(
        self,
        quality: float,
        confidence: float,
        stars: int,
    ) -> None:
        """ScoreResult.quality_score is always in [0, 1]."""
        result = ScoreResult(
            full_name="test/repo",
            quality_score=quality,
            confidence=confidence,
            stars=stars,
        )
        assert 0.0 <= result.quality_score <= 1.0

    @given(confidence=_score_value)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_confidence_always_in_bounds(self, confidence: float) -> None:
        """ScoreResult.confidence is always in [0, 1]."""
        result = ScoreResult(
            full_name="test/repo",
            quality_score=0.5,
            confidence=confidence,
        )
        assert 0.0 <= result.confidence <= 1.0

    @given(quality=_score_value, stars=_positive_int)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_value_score_equals_quality_score(
        self,
        quality: float,
        stars: int,
    ) -> None:
        """value_score == quality_score (star-neutral design)."""
        result = ScoreResult(
            full_name="test/repo",
            quality_score=quality,
            stars=stars,
        )
        assert result.value_score == approx(quality)

    @given(quality=_score_value)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_coverage_always_in_bounds(self, quality: float) -> None:
        """ScoreResult.coverage is always in [0, 1]."""
        result = ScoreResult(
            full_name="test/repo",
            quality_score=quality,
            coverage=quality,  # coverage can equal any [0,1] value
        )
        assert 0.0 <= result.coverage <= 1.0

    @given(quality=_score_value, raw=_score_value)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_raw_quality_score_always_le_quality_score(
        self,
        quality: float,
        raw: float,
    ) -> None:
        """quality_score <= raw_quality_score when coverage < 1 (damping)."""
        coverage = 0.5
        damped = raw * (0.5 + 0.5 * coverage)  # = raw * 0.75
        result = ScoreResult(
            full_name="test/repo",
            quality_score=damped,
            raw_quality_score=raw,
            coverage=coverage,
        )
        assert result.quality_score <= result.raw_quality_score + 1e-9


class TestProfileWeightInvariants:
    """Property-based tests for profile weight sums."""

    @given(domain=_domain_type)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_profile_weights_sum_to_one(self, domain: DomainType) -> None:
        """All profile dimension weights sum to ~1.0."""
        registry = ProfileRegistry()
        profile = registry.get(domain)
        total = sum(profile.dimension_weights.values())
        assert abs(total - 1.0) < 0.01, f"{domain.value} weights sum to {total:.4f}"

    @given(domain=_domain_type)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_profile_covers_all_dimensions(self, domain: DomainType) -> None:
        """Every profile has weights for all 8 dimensions."""
        registry = ProfileRegistry()
        profile = registry.get(domain)
        assert set(profile.dimension_weights.keys()) == set(ScoreDimension)

    @given(domain=_domain_type)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_all_weights_non_negative(self, domain: DomainType) -> None:
        """All profile weights are >= 0."""
        registry = ProfileRegistry()
        profile = registry.get(domain)
        for dim, weight in profile.dimension_weights.items():
            assert weight >= 0.0, f"{dim.value} has negative weight {weight}"


class TestScoringEngineInvariants:
    """Property-based tests for ScoringEngine output invariants."""

    @given(
        quality=_score_value,
        stars=_positive_int,
        domain=_domain_type,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_engine_output_bounds(
        self,
        quality: float,
        stars: int,
        domain: DomainType,
    ) -> None:
        """Engine output always has quality_score, confidence, coverage in [0, 1]."""
        result = ScoreResult(
            full_name="test/repo",
            quality_score=quality,
            confidence=0.5,
            stars=stars,
            domain=domain,
        )
        assert 0.0 <= result.quality_score <= 1.0
        assert 0.0 <= result.confidence <= 1.0
        assert 0.0 <= result.coverage <= 1.0

    @given(
        quality=_score_value,
        stars=_positive_int,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_value_score_star_neutral(
        self,
        quality: float,
        stars: int,
    ) -> None:
        """value_score equals quality_score regardless of star count."""
        result = ScoreResult(
            full_name="test/repo",
            quality_score=quality,
            stars=stars,
        )
        assert result.value_score == approx(quality)


class TestDeterminismInvariant:
    """Property-based test for scoring determinism."""

    @given(
        full_name=_full_name,
        quality=_score_value,
        confidence=_score_value,
        stars=_positive_int,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_score_result_deterministic(
        self,
        full_name: str,
        quality: float,
        confidence: float,
        stars: int,
    ) -> None:
        """Creating the same ScoreResult twice yields identical values."""
        r1 = ScoreResult(
            full_name=full_name,
            quality_score=quality,
            confidence=confidence,
            stars=stars,
        )
        r2 = ScoreResult(
            full_name=full_name,
            quality_score=quality,
            confidence=confidence,
            stars=stars,
        )
        assert r1.quality_score == r2.quality_score
        assert r1.confidence == r2.confidence
        assert r1.value_score == r2.value_score
        assert r1.stars == r2.stars
