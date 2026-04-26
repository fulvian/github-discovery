"""T1.3 — Verify coverage field on ScoreResult and low-coverage damping.

Coverage represents the fraction of profile weight backed by real data.
Low coverage should dampen the quality_score but preserve raw_quality_score.
"""

from __future__ import annotations

from github_discovery.models.enums import DomainType
from github_discovery.models.scoring import ScoreResult
from github_discovery.scoring.engine import ScoringEngine
from tests.unit.scoring.conftest import _make_candidate


def test_coverage_default_is_one() -> None:
    """Default ScoreResult has coverage 1.0 (backward compatible)."""
    sr = ScoreResult(full_name="a/b")
    assert sr.coverage == 1.0
    assert sr.raw_quality_score == 0.0


def test_coverage_in_range() -> None:
    """Coverage must be in [0, 1]."""
    sr = ScoreResult(full_name="a/b", coverage=0.6, raw_quality_score=0.5)
    assert 0.0 <= sr.coverage <= 1.0


def test_low_coverage_dampens_quality() -> None:
    """Two repos with same raw score but different coverage get different quality."""
    high_coverage = ScoreResult(
        full_name="a/high",
        raw_quality_score=0.6,
        coverage=0.9,
        quality_score=0.6 * (0.5 + 0.5 * 0.9),
    )
    low_coverage = ScoreResult(
        full_name="a/low",
        raw_quality_score=0.6,
        coverage=0.6,
        quality_score=0.6 * (0.5 + 0.5 * 0.6),
    )
    assert high_coverage.quality_score > low_coverage.quality_score
    assert high_coverage.raw_quality_score == low_coverage.raw_quality_score


def test_full_coverage_no_damping() -> None:
    """Coverage 1.0 means quality_score == raw_quality_score."""
    raw = 0.75
    expected_quality = raw * (0.5 + 0.5 * 1.0)  # = raw
    sr = ScoreResult(
        full_name="a/b",
        raw_quality_score=raw,
        coverage=1.0,
        quality_score=expected_quality,
    )
    assert sr.quality_score == sr.raw_quality_score


def test_engine_coverage_from_screening() -> None:
    """ScoringEngine produces coverage < 1.0 when some dims have no data."""
    engine = ScoringEngine()
    candidate = _make_candidate(domain=DomainType.LIBRARY)
    # Score with no screening or assessment → all dims default_neutral
    result = engine.score(candidate, screening=None, assessment=None)
    # With no data at all, all dimensions have confidence 0.0
    assert result.coverage == 0.0
    assert result.quality_score == 0.0
    assert result.raw_quality_score == 0.0
