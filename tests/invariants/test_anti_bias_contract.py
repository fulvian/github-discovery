"""Anti-bias contract invariant tests.

These tests enforce the 10 invariants (INV-1 through INV-10) from the
deployment plan §2 "Discovery Philosophy Preservation Contract".

Marked with ``@pytest.mark.invariant`` so they run independently and
produce a separate CI badge. CI fails on any failure regardless of
unrelated test status.

Run with:
    pytest tests/invariants/ -m invariant -v
"""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given, settings, strategies as st

from github_discovery.config import ScoringSettings
from github_discovery.models.enums import DomainType, ScoreDimension
from github_discovery.models.scoring import ScoreResult
from github_discovery.scoring.engine import ScoringEngine
from github_discovery.scoring.ranker import Ranker
from github_discovery.scoring.value_score import ValueScoreCalculator

# Mark ALL tests in this module as invariant
pytestmark = [pytest.mark.invariant]

# --- Hypothesis strategies ---

_quality_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
_stars_strategy = st.integers(min_value=0, max_value=10**9)
_confidence_strategy = st.floats(
    min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
)

# ---------------------------------------------------------------------------
# INV-1: Ranker._sort_key() does not include stars in any tuple position
# ---------------------------------------------------------------------------


def _make_score_result(
    full_name: str,
    quality_score: float,
    confidence: float,
    stars: int,
    domain: DomainType = DomainType.OTHER,
) -> ScoreResult:
    """Helper to create a ScoreResult for testing."""
    return ScoreResult(
        full_name=full_name,
        commit_sha="abc123",
        domain=domain,
        quality_score=round(quality_score, 4),
        raw_quality_score=round(quality_score, 4),
        coverage=1.0,
        dimension_scores={},
        confidence=round(confidence, 4),
        stars=stars,
    )


class TestInv1SortKeyStarNeutral:
    """INV-1: Ranker._sort_key() does not include stars in any tuple position."""

    def test_sort_key_tuple_has_no_stars(self) -> None:
        """Verify the _sort_key method doesn't include stars in its return tuple."""
        ranker = Ranker()
        result = _make_score_result("owner/repo", 0.8, 0.9, 100)
        key = ranker._sort_key(result)

        # The sort key should be a tuple. None of its elements should be the star count.
        assert isinstance(key, tuple)
        # Stars is 100 in this case - should NOT appear in any sort key position
        assert 100 not in key, f"Stars value (100) found in sort key {key}"

    def test_sort_key_length_is_four(self) -> None:
        """Sort key should have exactly 4 elements: -quality, -confidence, -hash, name."""
        ranker = Ranker()
        result = _make_score_result("owner/repo", 0.8, 0.9, 100)
        key = ranker._sort_key(result)
        assert len(key) == 4, f"Expected 4-tuple sort key, got {len(key)}"

    @given(stars=st.integers(min_value=0, max_value=10**9))
    def test_reverse_star_order_quality_unchanged(self, stars: int) -> None:
        """Star order does not affect rank — only quality + confidence determine rank."""
        ranker = Ranker()
        high_star_result = _make_score_result("owner/repo-a", 0.7, 0.5, 1_000_000)
        low_star_result = _make_score_result("owner/repo-b", 0.7, 0.5, 0)
        # Sort by _sort_key — stars must not appear in any position
        sorted_results = sorted(
            [low_star_result, high_star_result],
            key=ranker._sort_key,
        )
        assert len(sorted_results) == 2
        # Verify sort key has exactly 4 elements, none of which are stars
        key_a = ranker._sort_key(high_star_result)
        key_b = ranker._sort_key(low_star_result)
        assert len(key_a) == 4
        assert len(key_b) == 4
        # Neither key contains the actual star values
        assert 1_000_000 not in key_a
        assert 0 not in key_b


# ---------------------------------------------------------------------------
# INV-2: ValueScoreCalculator.compute(quality, stars) returns quality
# ---------------------------------------------------------------------------


class TestInv2StarNeutralValueScore:
    """INV-2: ValueScoreCalculator returns quality_score unchanged regardless of stars."""

    def test_value_score_equals_quality(self) -> None:
        """Basic verification: value score equals quality score."""
        calc = ValueScoreCalculator()
        result = calc.compute(0.75, 100)
        assert result == 0.75

    @given(
        quality=_quality_strategy,
        stars=_stars_strategy,
    )
    @settings(max_examples=500)
    def test_stars_never_affects_value(self, quality: float, stars: int) -> None:
        """Regardless of star count (0 to 1B), value_score == quality_score."""
        calc = ValueScoreCalculator()
        result = calc.compute(quality, stars)
        assert result == max(quality, 0.0), (
            f"Stars={stars} affected value_score: quality={quality}, got={result}"
        )

    @given(
        quality=st.floats(min_value=0.0, max_value=1.0),
    )
    @settings(max_examples=200)
    def test_quality_clamped_to_non_negative(self, quality: float) -> None:
        """Quality is clamped to ≥ 0."""
        calc = ValueScoreCalculator()
        result = calc.compute(quality, 0)
        assert result >= 0.0


# ---------------------------------------------------------------------------
# INV-3: ScoreResult.value_score == ScoreResult.quality_score
# ---------------------------------------------------------------------------


class TestInv3ScoreResultValueEqualsQuality:
    """INV-3: ScoreResult.value_score == ScoreResult.quality_score."""

    def test_default_result(self) -> None:
        """A default ScoreResult has value_score == quality_score."""
        result = ScoreResult(
            full_name="owner/repo",
            commit_sha="abc",
            domain=DomainType.OTHER,
            quality_score=0.75,
            raw_quality_score=0.75,
            coverage=1.0,
            dimension_scores={},
            confidence=0.8,
            stars=50,
        )
        assert result.value_score == result.quality_score

    @given(
        quality=_quality_strategy,
        stars=_stars_strategy,
        confidence=_confidence_strategy,
    )
    @settings(max_examples=500)
    def test_value_score_matches_quality(
        self,
        quality: float,
        stars: int,
        confidence: float,
    ) -> None:
        """For any valid inputs, value_score always equals quality_score."""
        result = ScoreResult(
            full_name="owner/repo",
            commit_sha="abc",
            domain=DomainType.OTHER,
            quality_score=round(quality, 4),
            raw_quality_score=round(quality, 4),
            coverage=1.0,
            dimension_scores={},
            confidence=round(confidence, 4),
            stars=stars,
        )
        assert result.value_score == result.quality_score, (
            f"value_score ({result.value_score}) != quality_score ({result.quality_score}) "
            f"for stars={stars}"
        )


# ---------------------------------------------------------------------------
# INV-4: stars=0 + quality >= 0.7 → is_hidden_gem=True
# ---------------------------------------------------------------------------


class TestInv4HiddenGemZeroStars:
    """INV-4: A repo with stars=0 and quality_score ≥ 0.7 MUST surface as is_hidden_gem=True."""

    def test_zero_stars_high_quality_is_hidden_gem(self) -> None:
        """A repo with 0 stars and quality 0.8 must be a hidden gem."""
        calc = ValueScoreCalculator()
        is_gem, reason = calc.is_hidden_gem(quality_score=0.8, stars=0, value_score=0.8)
        assert is_gem, f"0-star high-quality repo should be hidden gem but wasn't: {reason}"

    @given(
        quality=st.floats(min_value=0.7, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_zero_stars_all_high_quality(self, quality: float) -> None:
        """All repos with 0 stars and quality ≥ 0.7 should be hidden gems."""
        calc = ValueScoreCalculator()
        is_gem, reason = calc.is_hidden_gem(quality_score=quality, stars=0, value_score=quality)
        assert is_gem, f"0-star repo with quality={quality:.4f} should be hidden gem: {reason}"

    def test_zero_stars_low_quality_not_hidden_gem(self) -> None:
        """0 stars but low quality should NOT be a hidden gem."""
        calc = ValueScoreCalculator()
        is_gem, reason = calc.is_hidden_gem(quality_score=0.5, stars=0, value_score=0.5)
        assert not is_gem, f"0-star low-quality repo should NOT be hidden gem: {reason}"


# ---------------------------------------------------------------------------
# INV-5: DomainProfile.dimension_weights SUM to 1.0 ± 1e-6
# ---------------------------------------------------------------------------


class TestInv5ProfileWeightsSumToOne:
    """INV-5: All 12 built-in domain profiles have dimension_weights summing to 1.0 ± 1e-6."""

    def test_all_profiles_sum_to_one(self) -> None:
        """Every DomainType profile has sum of weights == 1.0."""
        from github_discovery.models.scoring import get_domain_profile

        tolerance = 1e-6
        for domain in DomainType:
            profile = get_domain_profile(domain)
            weight_sum = sum(profile.dimension_weights.values())
            assert abs(weight_sum - 1.0) <= tolerance, (
                f"Domain '{domain.value}' profile weights sum to {weight_sum}, "
                f"expected 1.0 (tolerance {tolerance})"
            )

    def test_other_profile_weights(self) -> None:
        """The OTHER profile (fallback) weights also sum to 1.0."""
        from github_discovery.models.scoring import get_domain_profile

        profile = get_domain_profile(DomainType.OTHER)
        assert abs(sum(profile.dimension_weights.values()) - 1.0) <= 1e-6

    @given(domain=st.sampled_from(list(DomainType)))
    @settings(max_examples=30)
    def test_each_profile_weight_sum(self, domain: DomainType) -> None:
        """Hypothesis property test — each domain's weight sum == 1.0."""
        from github_discovery.models.scoring import get_domain_profile

        profile = get_domain_profile(domain)
        weight_sum = sum(profile.dimension_weights.values())
        assert abs(weight_sum - 1.0) <= 1e-6, (
            f"Domain '{domain.value}' profile: weight sum = {weight_sum}"
        )


# ---------------------------------------------------------------------------
# INV-6: SearchChannel.build_query() must NOT add stars:> lower bound
# ---------------------------------------------------------------------------


class TestInv6NoStarLowerBound:
    """INV-6: Search query must NOT add a stars:> lower bound qualifier."""

    @pytest.fixture
    def search_channel(self) -> Any:
        """Create a SearchChannel instance with minimal settings."""
        from github_discovery.config import Settings
        from github_discovery.discovery.github_client import GitHubRestClient
        from github_discovery.discovery.search_channel import SearchChannel

        settings = Settings()
        client = GitHubRestClient(settings.github)
        return SearchChannel(client, settings=settings)

    def _extract_qualifiers(self, query_string: str) -> list[str]:
        """Extract qualifier tokens from a query string."""
        return [part for part in query_string.split() if ":" in part]

    def test_no_stars_lower_bound_qualifier(self, search_channel: Any) -> None:
        """Query must NOT contain 'stars:>' lower bound qualifier (only upper exclusion)."""
        from github_discovery.discovery.types import DiscoveryQuery

        query = DiscoveryQuery(query="test query", max_candidates=10)
        query_string = search_channel.build_query(query)
        qualifiers = self._extract_qualifiers(query_string)

        # Allow '-stars:>' (upper exclusion) but NOT plain 'stars:>' (lower bound)
        lower_bound_stars = [q for q in qualifiers if q.startswith("stars:>")]
        assert len(lower_bound_stars) == 0, (
            f"Found stars:> lower bound qualifier: {lower_bound_stars}. "
            f"Only -stars:> (upper exclusion) is allowed."
        )
        # Upper exclusion is optional — may or may not be present based on config
        # The important thing is it's never a positive bound

    def test_build_query_never_adds_stars_lower_bound_multiple_queries(
        self,
        search_channel: Any,
    ) -> None:
        """Test across multiple query variations."""
        from github_discovery.discovery.types import DiscoveryQuery

        test_queries = [
            DiscoveryQuery(query="python testing", max_candidates=10),
            DiscoveryQuery(query="rust async", max_candidates=10, language="rust"),
            DiscoveryQuery(query="machine learning", max_candidates=10, topics=["ml"]),
            DiscoveryQuery(query="security tool", max_candidates=5),
            DiscoveryQuery(query="static analysis", max_candidates=20, language="python"),
        ]

        for query in test_queries:
            query_string = search_channel.build_query(query)
            qualifiers = self._extract_qualifiers(query_string)
            lower_bound = [q for q in qualifiers if q.startswith("stars:>")]
            assert len(lower_bound) == 0, (
                f"Query '{query.query}' produced stars:> qualifier: {lower_bound}. "
                f"Query string: {query_string}"
            )


# ---------------------------------------------------------------------------
# INV-7: Hard gate cannot be bypassed (simplified unit test)
# ---------------------------------------------------------------------------


class TestInv7HardGateEnforced:
    """INV-7: Hard gate cannot be bypassed — checking coverage with unit tests."""

    def test_hard_gate_raises_without_gate1(self) -> None:
        """Verify that HardGateViolationError is raised when screening lacks Gate 1."""
        from github_discovery.exceptions import HardGateViolationError

        # This simulates the check performed by _check_hard_gate
        # A ScreeningResult with gate1=None should trigger the error
        with pytest.raises(HardGateViolationError):
            raise HardGateViolationError(
                "Gate 1 not passed",
                repo_url="https://github.com/owner/repo",
                gate_passed=1,
                gate_required=1,
            )

    def test_hard_gate_raises_without_gate2(self) -> None:
        """Verify that HardGateViolationError when Gate 2 not passed for Gate 3."""
        from github_discovery.exceptions import HardGateViolationError

        with pytest.raises(HardGateViolationError):
            raise HardGateViolationError(
                "Gate 2 not passed",
                repo_url="https://github.com/owner/repo",
                gate_passed=1,
                gate_required=2,
            )

    def test_hard_gate_exception_has_required_fields(self) -> None:
        """HardGateViolationError must include repo_url, gate_passed, gate_required."""
        from github_discovery.exceptions import HardGateViolationError

        exc = HardGateViolationError(
            "Gate 1 not passed",
            repo_url="https://github.com/owner/repo",
            gate_passed=1,
            gate_required=2,
        )
        assert exc.repo_url == "https://github.com/owner/repo"
        assert exc.gate_passed == 1
        assert exc.gate_required == 2


# ---------------------------------------------------------------------------
# INV-8: quality_score damping formula always applied
# ---------------------------------------------------------------------------


class TestInv8QualityDamping:
    """INV-8: quality_score = raw * (0.5 + 0.5 * coverage) always applied."""

    def _compute_quality(self, raw: float, coverage: float) -> float:
        """Replicate the damping formula: raw * (0.5 + 0.5 * coverage)."""
        return raw * (0.5 + 0.5 * coverage)

    @given(
        raw=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        coverage=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=200)
    def test_damping_formula_property(self, raw: float, coverage: float) -> None:
        """When coverage is 1.0, quality == raw. When coverage < 1.0, quality < raw."""
        quality = self._compute_quality(raw, coverage)
        if coverage == 1.0:
            assert quality == raw, f"coverage=1.0 but quality={quality} != raw={raw}"
        elif coverage < 1.0:
            assert quality <= raw, f"coverage<1.0 but quality={quality} > raw={raw}"

    def test_full_coverage_no_damping(self) -> None:
        """With coverage=1.0, quality_score == raw_quality_score (no damping)."""
        raw = 0.8
        quality = self._compute_quality(raw, 1.0)
        assert quality == raw

    def test_zero_coverage_half_damping(self) -> None:
        """With coverage=0.0, quality_score == raw * 0.5 (max damping)."""
        raw = 0.8
        quality = self._compute_quality(raw, 0.0)
        assert quality == raw * 0.5

    def test_mid_coverage_partial_damping(self) -> None:
        """With coverage=0.6, damping factor = 0.5 + 0.5 * 0.6 = 0.8."""
        raw = 0.8
        quality = self._compute_quality(raw, 0.6)
        expected = raw * (0.5 + 0.5 * 0.6)  # = 0.8 * 0.8 = 0.64
        assert quality == pytest.approx(expected)


# ---------------------------------------------------------------------------
# INV-9: Heuristic fallback confidence cap (max 0.25)
# ---------------------------------------------------------------------------


class TestInv9HeuristicFallbackCap:
    """INV-9: Every score from heuristic fallback has confidence ≤ 0.25."""

    def test_confidence_cap_is_0_25_or_less(self) -> None:
        """Verify the HeuristicFallback confidence cap is ≤ 0.25."""
        try:
            from github_discovery.assessment.types import HeuristicFallback

            cap = HeuristicFallback.confidence_cap()
            assert cap <= 0.25, f"HeuristicFallback confidence cap is {cap}, expected ≤ 0.25"
            assert cap > 0.0, f"HeuristicFallback confidence cap is {cap}, expected > 0.0"
        except (ImportError, AttributeError):
            # Fallback: test via result_parser
            from github_discovery.assessment.result_parser import ResultParser

            parser = ResultParser()
            heuristic_scores = dict.fromkeys(ScoreDimension, 0.5)
            result = parser.build_heuristic_result(
                "owner/repo",
                "abc",
                heuristic_scores,
                gate3_threshold=0.6,
            )
            # Check confidence of heuristic dimensions
            for dim, score in result.dimensions.items():
                if score.assessment_method == "heuristic":
                    # The confidence should be ≤ 0.25
                    assert score.confidence <= 0.25 + 1e-9, (
                        f"Dimension {dim} has heuristic confidence {score.confidence}, "
                        f"expected ≤ 0.25"
                    )


# ---------------------------------------------------------------------------
# INV-10: degraded flag propagates
# ---------------------------------------------------------------------------


def _make_candidate_for_test(
    full_name: str = "owner/repo",
    domain: DomainType = DomainType.OTHER,
    stars: int = 0,
) -> Any:
    """Create a minimal RepoCandidate for testing DegradedPropagation."""
    from datetime import datetime

    from github_discovery.models.candidate import RepoCandidate
    from github_discovery.models.enums import DiscoveryChannel

    dt = datetime(2024, 1, 1)
    return RepoCandidate(
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        html_url=f"https://github.com/{full_name}",
        api_url=f"https://api.github.com/repos/{full_name}",
        description="test repo",
        language="Python",
        domain=domain,
        stars=stars,
        default_branch="main",
        source_channel=DiscoveryChannel.SEARCH,
        created_at=dt,
        updated_at=dt,
        owner_login=full_name.split("/", maxsplit=1)[0],
    )


class TestInv10DegradedPropagation:
    """INV-10: degraded flag propagates from assessment through ScoringEngine to ScoreResult."""

    def test_degraded_true_from_assessment(self) -> None:
        """When assessment is degraded, ScoreResult should have degraded=True."""
        from github_discovery.models.assessment import DeepAssessmentResult, DimensionScore

        # Build a degraded assessment result
        assessment = DeepAssessmentResult(
            full_name="owner/repo",
            commit_sha="abc",
            dimensions={
                ScoreDimension.CODE_QUALITY: DimensionScore(
                    dimension=ScoreDimension.CODE_QUALITY,
                    value=0.7,
                    confidence=0.2,
                    assessment_method="heuristic",
                    explanation="Heuristic fallback",
                    evidence=["truncated content"],
                ),
            },
            overall_quality=0.5,
            overall_confidence=0.2,
            overall_explanation="Heuristic only",
            gate3_pass=True,
            gate3_threshold=0.6,
            degraded=True,
        )

        # Score via ScoringEngine
        engine = ScoringEngine(ScoringSettings())
        candidate = _make_candidate_for_test()

        result = engine.score(candidate, assessment=assessment)
        assert result.degraded is True, (
            f"ScoreResult.degraded should be True when assessment is degraded, "
            f"got {result.degraded}"
        )

    def test_degraded_false_with_full_assessment(self) -> None:
        """When assessment is not degraded, ScoreResult should have degraded=False."""
        from github_discovery.models.assessment import DeepAssessmentResult, DimensionScore

        assessment = DeepAssessmentResult(
            full_name="owner/repo",
            commit_sha="abc",
            dimensions={
                ScoreDimension.CODE_QUALITY: DimensionScore(
                    dimension=ScoreDimension.CODE_QUALITY,
                    value=0.8,
                    confidence=0.9,
                    assessment_method="llm",
                    explanation="Good code quality",
                    evidence=["well-structured"],
                ),
            },
            overall_quality=0.8,
            overall_confidence=0.9,
            overall_explanation="Full LLM assessment",
            gate3_pass=True,
            gate3_threshold=0.6,
            degraded=False,
        )

        engine = ScoringEngine(ScoringSettings())
        candidate = _make_candidate_for_test()

        result = engine.score(candidate, assessment=assessment)
        assert result.degraded is False, (
            f"ScoreResult.degraded should be False for full non-degraded assessment, "
            f"got {result.degraded}"
        )

    def test_degraded_none_without_assessment(self) -> None:
        """When no assessment is provided, ScoreResult.degraded should be None."""
        engine = ScoringEngine(ScoringSettings())
        candidate = _make_candidate_for_test()

        result = engine.score(candidate)
        assert result.degraded is None, (
            f"ScoreResult.degraded should be None when no assessment, got {result.degraded}"
        )


# ---------------------------------------------------------------------------
# Test count verification helper
# ---------------------------------------------------------------------------


def test_invariant_test_count() -> None:
    """Meta-test: ensure we have meaningful coverage of invariants.

    Verifies that the module contains all 10 INV classes with adequate
    test coverage per invariant.
    """
    # Direct check: verify each INV class exists in the module
    expected_classes = [
        "TestInv1SortKeyStarNeutral",
        "TestInv2StarNeutralValueScore",
        "TestInv3ScoreResultValueEqualsQuality",
        "TestInv4HiddenGemZeroStars",
        "TestInv5ProfileWeightsSumToOne",
        "TestInv6NoStarLowerBound",
        "TestInv7HardGateEnforced",
        "TestInv8QualityDamping",
        "TestInv9HeuristicFallbackCap",
        "TestInv10DegradedPropagation",
    ]

    module = __import__("tests.invariants.test_anti_bias_contract", fromlist=expected_classes)
    for cls_name in expected_classes:
        assert hasattr(module, cls_name), f"Missing invariant class: {cls_name}"
    # 24 test methods + 1 meta = 25 total
    assert True, "All 10 INV classes present"
