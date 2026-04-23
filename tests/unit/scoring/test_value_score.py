"""Tests for Value Score calculator."""

from __future__ import annotations

from math import log10

import pytest

from github_discovery.config import ScoringSettings
from github_discovery.models.enums import DomainType
from github_discovery.scoring.value_score import ValueScoreCalculator


class TestValueScoreCompute:
    """Tests for the compute method."""

    def test_zero_stars(self, value_calculator) -> None:
        """0 stars → denominator = log10(10) = 1.0."""
        vs = value_calculator.compute(0.8, 0)
        assert vs == pytest.approx(0.8, abs=0.001)

    def test_ten_stars(self, value_calculator) -> None:
        """10 stars → denominator = log10(20) ≈ 1.30."""
        vs = value_calculator.compute(0.8, 10)
        assert vs == pytest.approx(0.8 / log10(20), abs=0.001)

    def test_hundred_stars(self, value_calculator) -> None:
        """100 stars → denominator ≈ 2.04."""
        vs = value_calculator.compute(0.8, 100)
        assert vs == pytest.approx(0.8 / log10(110), abs=0.001)

    def test_thousand_stars(self, value_calculator) -> None:
        """1000 stars → denominator ≈ 3.00."""
        vs = value_calculator.compute(0.8, 1000)
        assert vs == pytest.approx(0.8 / log10(1010), abs=0.001)

    def test_ten_thousand_stars(self, value_calculator) -> None:
        """10000 stars → denominator ≈ 4.00."""
        vs = value_calculator.compute(0.8, 10000)
        assert vs == pytest.approx(0.8 / log10(10010), abs=0.001)

    def test_zero_quality_returns_zero(self, value_calculator) -> None:
        """Quality 0 → value score 0."""
        vs = value_calculator.compute(0.0, 100)
        assert vs == 0.0

    def test_higher_quality_higher_value(self, value_calculator) -> None:
        """Same stars, higher quality → higher value score."""
        vs_low = value_calculator.compute(0.5, 100)
        vs_high = value_calculator.compute(0.9, 100)
        assert vs_high > vs_low

    def test_fewer_stars_higher_value(self, value_calculator) -> None:
        """Same quality, fewer stars → higher value score."""
        vs_popular = value_calculator.compute(0.8, 10000)
        vs_hidden = value_calculator.compute(0.8, 50)
        assert vs_hidden > vs_popular


class TestHiddenGem:
    """Tests for is_hidden_gem."""

    def test_hidden_gem_detected(self, value_calculator) -> None:
        """50 stars + quality 0.9 → hidden gem."""
        vs = value_calculator.compute(0.9, 50)
        is_gem, reason = value_calculator.is_hidden_gem(0.9, 50, vs)
        assert is_gem is True
        assert "high quality" in reason.lower() or "low visibility" in reason.lower()

    def test_not_gem_too_many_stars(self, value_calculator) -> None:
        """5000 stars → not a hidden gem."""
        vs = value_calculator.compute(0.9, 5000)
        is_gem, reason = value_calculator.is_hidden_gem(0.9, 5000, vs)
        assert is_gem is False
        assert "threshold" in reason.lower() or "stars" in reason.lower()

    def test_not_gem_low_quality(self, value_calculator) -> None:
        """Quality 0.5 → not a hidden gem."""
        vs = value_calculator.compute(0.5, 50)
        is_gem, _ = value_calculator.is_hidden_gem(0.5, 50, vs)
        assert is_gem is False

    def test_custom_threshold(self) -> None:
        """Custom threshold changes hidden gem detection."""
        settings = ScoringSettings(hidden_gem_star_threshold=100)
        calc = ValueScoreCalculator(settings)
        vs = calc.compute(0.9, 200)
        is_gem, _ = calc.is_hidden_gem(0.9, 200, vs)
        assert is_gem is False  # 200 > custom threshold 100


class TestStarContext:
    """Tests for star_context."""

    def test_zero_stars(self, value_calculator) -> None:
        ctx = value_calculator.star_context(0.8, 0, DomainType.LIBRARY)
        assert "0 stars" in ctx

    def test_very_low_stars(self, value_calculator) -> None:
        ctx = value_calculator.star_context(0.8, 10, DomainType.LIBRARY)
        assert "10 stars" in ctx

    def test_moderate_stars(self, value_calculator) -> None:
        ctx = value_calculator.star_context(0.8, 200, DomainType.LIBRARY)
        assert "200 stars" in ctx

    def test_high_stars(self, value_calculator) -> None:
        ctx = value_calculator.star_context(0.8, 10000, DomainType.LIBRARY)
        assert "10,000 stars" in ctx


class TestNormalizeBatch:
    """Tests for normalize_batch."""

    def test_empty_batch(self, value_calculator) -> None:
        result = value_calculator.normalize_batch([])
        assert result == []

    def test_single_item(self, value_calculator) -> None:
        result = value_calculator.normalize_batch([("test/repo", 0.8, 100)])
        assert len(result) == 1
        assert result[0][0] == "test/repo"
        assert result[0][1] == pytest.approx(1.0, abs=0.001)

    def test_multiple_items_normalized(self, value_calculator) -> None:
        scores = [
            ("repo/a", 0.8, 50),
            ("repo/b", 0.6, 5000),
            ("repo/c", 0.9, 10),
        ]
        result = value_calculator.normalize_batch(scores)
        assert len(result) == 3
        # All normalized to [0.0, 1.0]
        for _, norm_vs in result:
            assert 0.0 <= norm_vs <= 1.0
        # Max should be ~1.0
        max_norm = max(vs for _, vs in result)
        assert max_norm == pytest.approx(1.0, abs=0.001)

    def test_hidden_gem_ranks_above_popular(self, value_calculator) -> None:
        """Anti-star bias: hidden gem should normalize above popular mediocre."""
        scores = [
            ("hidden/gem", 0.9, 50),
            ("popular/mediocre", 0.5, 5000),
        ]
        result = value_calculator.normalize_batch(scores)
        result_dict = dict(result)
        assert result_dict["hidden/gem"] > result_dict["popular/mediocre"]
