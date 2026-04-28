"""Tests for adaptive content strategy (TC1, TC2).

Tests tier classification, char limits, token estimation,
and sampling decisions for the content strategy module.
"""

from __future__ import annotations

from github_discovery.assessment.content_strategy import (
    ContentStrategy,
    SizeTier,
    classify_size_tier,
    compute_sample_size,
    estimate_token_count,
    get_char_limit,
    needs_sampling,
)
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel


def _make_candidate(
    full_name: str = "test/repo",
    size_kb: int = 100,
    description: str = "A test repository",
) -> RepoCandidate:
    """Create a test RepoCandidate with given size."""
    return RepoCandidate(
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        html_url=f"https://github.com/{full_name}",
        api_url=f"https://api.github.com/repos/{full_name}",
        description=description,
        language="Python",
        stars=50,
        owner_login="test",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-06-01T00:00:00Z",
        pushed_at="2024-06-01T00:00:00Z",
        source_channel=DiscoveryChannel.SEARCH,
        size_kb=size_kb,
    )


class TestSizeTierClassification:
    """Tests for classify_size_tier."""

    def test_tiny_repo(self) -> None:
        """Repo < 10 files (size_kb < 20) is TINY."""
        candidate = _make_candidate(size_kb=10)
        assert classify_size_tier(candidate) == SizeTier.TINY

    def test_small_repo(self) -> None:
        """Repo 10-50 files is SMALL."""
        candidate = _make_candidate(size_kb=60)
        assert classify_size_tier(candidate) == SizeTier.SMALL

    def test_medium_repo(self) -> None:
        """Repo 50-200 files is MEDIUM."""
        candidate = _make_candidate(size_kb=300)
        assert classify_size_tier(candidate) == SizeTier.MEDIUM

    def test_large_repo(self) -> None:
        """Repo 200-1000 files is LARGE."""
        candidate = _make_candidate(size_kb=800)
        assert classify_size_tier(candidate) == SizeTier.LARGE

    def test_huge_repo(self) -> None:
        """Repo > 1000 files is HUGE."""
        candidate = _make_candidate(size_kb=2500)
        assert classify_size_tier(candidate) == SizeTier.HUGE

    def test_zero_size_returns_tiny(self) -> None:
        """Repo with size_kb=0 falls back to TINY."""
        candidate = _make_candidate(size_kb=0)
        assert classify_size_tier(candidate) == SizeTier.TINY


class TestCharLimits:
    """Tests for get_char_limit per tier."""

    def test_tiny_limit(self) -> None:
        """Tiny tier has 240K char limit."""
        assert get_char_limit(SizeTier.TINY) == 240_000

    def test_small_limit(self) -> None:
        """Small tier has 200K char limit."""
        assert get_char_limit(SizeTier.SMALL) == 200_000

    def test_medium_limit(self) -> None:
        """Medium tier has 160K char limit."""
        assert get_char_limit(SizeTier.MEDIUM) == 160_000

    def test_large_limit(self) -> None:
        """Large tier has 120K char limit."""
        assert get_char_limit(SizeTier.LARGE) == 120_000

    def test_huge_limit(self) -> None:
        """Huge tier has 80K char limit."""
        assert get_char_limit(SizeTier.HUGE) == 80_000


class TestTokenEstimation:
    """Tests for estimate_token_count."""

    def test_estimation_from_size_kb(self) -> None:
        """Token estimate uses size_kb * 12 * 1.2 formula."""
        # 100 KB * 12 * 1.2 = 1440 tokens
        candidate = _make_candidate(size_kb=100)
        estimate = estimate_token_count(candidate)
        assert estimate == 1440

    def test_estimation_huge_repo(self) -> None:
        """Large repo produces proportional token estimate."""
        # 2000 KB * 12 * 1.2 = 28800 tokens
        candidate = _make_candidate(size_kb=2000)
        estimate = estimate_token_count(candidate)
        assert estimate == 28800

    def test_estimation_fallback_zero_size(self) -> None:
        """Repo with size_kb=0 uses description heuristic fallback."""
        candidate = _make_candidate(size_kb=0, description="A short description")
        estimate = estimate_token_count(candidate)
        assert estimate == len("A short description") * 10

    def test_estimation_fallback_no_description(self) -> None:
        """Repo with size_kb=0 and no description returns 500."""
        candidate = _make_candidate(size_kb=0, description="")
        estimate = estimate_token_count(candidate)
        assert estimate == 500


class TestSampling:
    """Tests for sampling decisions (TC2)."""

    def test_sampling_not_needed_for_medium(self) -> None:
        """Medium repos do not need sampling."""
        candidate = _make_candidate(size_kb=300)
        tier = classify_size_tier(candidate)
        estimated = estimate_token_count(candidate)
        assert not needs_sampling(tier, estimated)

    def test_sampling_needed_for_huge(self) -> None:
        """Huge repos with >1M estimated tokens need sampling."""
        assert needs_sampling(SizeTier.HUGE, 1_500_000)

    def test_sampling_not_needed_for_huge_below_threshold(self) -> None:
        """Huge repos below 1M token threshold do NOT need sampling."""
        assert not needs_sampling(SizeTier.HUGE, 500_000)

    def test_compute_sample_size_mid_range(self) -> None:
        """1000 files → 50 samples (5% of 1000 = 50)."""
        assert compute_sample_size(1000) == 50

    def test_compute_sample_size_min_clamp(self) -> None:
        """50 files → 10 samples (clamped to _HUGE_SAMPLE_MIN=10)."""
        assert compute_sample_size(50) == 10

    def test_compute_sample_size_max_clamp(self) -> None:
        """10000 files → 100 samples (clamped to _HUGE_SAMPLE_MAX=100)."""
        assert compute_sample_size(10000) == 100


class TestContentStrategySelect:
    """Tests for ContentStrategy.select()."""

    def test_select_huge_with_sampling(self) -> None:
        """Huge repo (>1M tokens) triggers sampling."""
        strategy = ContentStrategy()
        # 100_000 KB * 12 * 1.2 = 1_440_000 tokens > 1M threshold
        candidate = _make_candidate(size_kb=100_000)

        result = strategy.select(candidate)

        assert result.tier == SizeTier.HUGE
        assert result.sampling_needed is True
        assert result.sample_size > 0
        assert result.max_chars == 80_000

    def test_select_tiny_without_sampling(self) -> None:
        """Tiny repo does not trigger sampling."""
        strategy = ContentStrategy()
        candidate = _make_candidate(size_kb=10)

        result = strategy.select(candidate)

        assert result.tier == SizeTier.TINY
        assert result.sampling_needed is False
        assert result.sample_size == 0
        assert result.max_chars == 240_000

    def test_select_estimated_tokens_reported(self) -> None:
        """Estimated tokens are reported in the result."""
        strategy = ContentStrategy()
        candidate = _make_candidate(size_kb=500)

        result = strategy.select(candidate)

        assert result.estimated_tokens > 0
        assert result.max_tokens_approx == result.max_chars // 4
