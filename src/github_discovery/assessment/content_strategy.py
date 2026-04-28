"""Adaptive content strategy for repository packing.

Selects the appropriate packing strategy (token budget, sampling mode)
based on repository size tier, to balance assessment quality against
cost and truncation risk.

TC1: Tier-based character limits based on repo size
TC2: Pre-pack size estimation + sampling for huge repos

Size tiers (by file count):
  tiny   : < 10 files   → generous limit (240K chars, ~60K tokens)
  small  : 10-50 files   → moderate limit (200K chars, ~50K tokens)
  medium : 50-200 files  → standard limit (160K chars, ~40K tokens)
  large  : 200-1000 files → conservative limit (120K chars, ~30K tokens)
  huge   : > 1000 files  → minimal limit (80K chars, ~20K tokens)
                         + pre-pack sampling required
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from github_discovery.models.candidate import RepoCandidate

logger = structlog.get_logger(__name__)

# Characters per token (o200k_base encoding approximation).
_CHARS_PER_TOKEN = 4

# Pre-pack size thresholds.
_HUGE_FILE_COUNT = 1000  # Files — triggers sampling mode
_HUGE_TOKEN_ESTIMATE = 1_000_000  # Tokens — triggers pre-pack check

# Tier-based character limits (before compression).
_SIZE_TIER_LIMITS: dict[str, int] = {
    "tiny": 240_000,  # ~60K tokens
    "small": 200_000,  # ~50K tokens
    "medium": 160_000,  # ~40K tokens
    "large": 120_000,  # ~30K tokens
    "huge": 80_000,  # ~20K tokens (sampling required)
}

# Fraction of files to sample in huge repos (for pre-pack estimation).
_HUGE_SAMPLE_FRACTION = 0.05  # 5% of files

# Minimum files to sample in huge repos.
_HUGE_SAMPLE_MIN = 10
# Maximum files to sample in huge repos.
_HUGE_SAMPLE_MAX = 100

# File count thresholds for size tier classification.
_TINY_FILE_COUNT = 10
_SMALL_FILE_COUNT = 50
_MEDIUM_FILE_COUNT = 200


class SizeTier(StrEnum):
    """Repository size tier for adaptive content strategy."""

    TINY = "tiny"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    HUGE = "huge"


def _estimate_file_count(repo: RepoCandidate) -> int:
    """Estimate total file count from repository metadata.

    Uses size_kb heuristic: ~2KB average per source file.
    Returns 0 if no size information is available.
    """
    if repo.size_kb > 0:
        return max(repo.size_kb // 2, 1)
    return 0


def estimate_token_count(repo: RepoCandidate) -> int:
    """Estimate total token count for a repository before packing.

    Uses GitHub API metadata (size_kb) to predict the packed token
    count. This is used to decide whether to enter sampling mode
    for huge repos.

    Args:
        repo: Repository candidate with metadata from GitHub API.

    Returns:
        Estimated token count for the packed repository.
    """
    if repo.size_kb > 0:
        # Average compression ratio ~3 chars/byte for code,
        # and ~4 chars/token → roughly 12 tokens/KB.
        # Add 20% safety margin.
        estimated_tokens = int(repo.size_kb * 12 * 1.2)
        logger.debug(
            "token_estimate_from_size_kb",
            full_name=repo.full_name,
            size_kb=repo.size_kb,
            estimated_tokens=estimated_tokens,
        )
        return estimated_tokens

    # Fallback: use description length heuristic (very rough).
    estimated_tokens = len(repo.description) * 10 if repo.description else 500
    logger.debug(
        "token_estimate_fallback",
        full_name=repo.full_name,
        estimated_tokens=estimated_tokens,
    )
    return estimated_tokens


def classify_size_tier(repo: RepoCandidate) -> SizeTier:
    """Classify a repository into a size tier.

    Uses estimated file count from size_kb heuristic as the primary
    signal. This reflects the actual repository scale before packing.

    Args:
        repo: Repository candidate with metadata.

    Returns:
        SizeTier classification.
    """
    file_count = _estimate_file_count(repo)

    if file_count < _TINY_FILE_COUNT:
        return SizeTier.TINY
    if file_count < _SMALL_FILE_COUNT:
        return SizeTier.SMALL
    if file_count < _MEDIUM_FILE_COUNT:
        return SizeTier.MEDIUM
    if file_count < _HUGE_FILE_COUNT:
        return SizeTier.LARGE
    return SizeTier.HUGE


def get_char_limit(tier: SizeTier) -> int:
    """Return the character limit for a given size tier."""
    return _SIZE_TIER_LIMITS[tier.value]


def compute_sample_size(total_files: int) -> int:
    """Compute the number of files to sample for pre-pack estimation.

    Uses a fixed fraction of total files, clamped to the min/max range.

    Args:
        total_files: Total number of files in the repository.

    Returns:
        Number of files to include in the sample pack.
    """
    fraction = max(int(total_files * _HUGE_SAMPLE_FRACTION), _HUGE_SAMPLE_MIN)
    return min(fraction, _HUGE_SAMPLE_MAX)


def needs_sampling(tier: SizeTier, estimated_tokens: int) -> bool:
    """Return True if the repo needs pre-pack sampling.

    Huge repos (>1M estimated tokens) require sampling to avoid
    packing a truncated representation that loses signal in the
    middle of the codebase.

    Args:
        tier: Size tier from classify_size_tier.
        estimated_tokens: Token estimate from estimate_token_count.

    Returns:
        True if sampling is recommended.
    """
    return tier == SizeTier.HUGE and estimated_tokens > _HUGE_TOKEN_ESTIMATE


class ContentStrategy:
    """Adaptive content strategy selector.

    Determines packing parameters (char limit, sampling mode) for a
    repository based on its size tier, to balance assessment quality
    against LLM cost and truncation risk.
    """

    def __init__(
        self,
        *,
        huge_sample_fraction: float = _HUGE_SAMPLE_FRACTION,
        huge_sample_min: int = _HUGE_SAMPLE_MIN,
        huge_sample_max: int = _HUGE_SAMPLE_MAX,
    ) -> None:
        """Initialize the content strategy.

        Args:
            huge_sample_fraction: Fraction of files to sample in huge repos.
            huge_sample_min: Minimum files to sample in huge repos.
            huge_sample_max: Maximum files to sample in huge repos.
        """
        self._huge_sample_fraction = huge_sample_fraction
        self._huge_sample_min = huge_sample_min
        self._huge_sample_max = huge_sample_max

    def select(
        self,
        repo: RepoCandidate,
    ) -> ContentStrategyResult:
        """Select the appropriate packing strategy for a repository.

        Uses GitHub API metadata to classify the repo's size tier and
        decide whether sampling is needed before the full pack.

        Args:
            repo: Repository candidate with metadata (languages_total_files, size_kb).

        Returns:
            ContentStrategyResult with packing parameters.
        """
        tier = classify_size_tier(repo)
        char_limit = get_char_limit(tier)
        estimated_tokens = estimate_token_count(repo)
        sampling_needed = needs_sampling(tier, estimated_tokens)

        if sampling_needed:
            total_files = _estimate_file_count(repo)
            sample_size = compute_sample_size(total_files)
            logger.info(
                "content_strategy_sampling",
                full_name=repo.full_name,
                tier=tier.value,
                estimated_tokens=estimated_tokens,
                total_files=total_files,
                sample_size=sample_size,
            )
            return ContentStrategyResult(
                tier=tier,
                char_limit=char_limit,
                sampling_needed=True,
                sample_size=sample_size,
                estimated_tokens=estimated_tokens,
            )

        logger.debug(
            "content_strategy_selected",
            full_name=repo.full_name,
            tier=tier.value,
            char_limit=char_limit,
            estimated_tokens=estimated_tokens,
            sampling_needed=False,
        )
        return ContentStrategyResult(
            tier=tier,
            char_limit=char_limit,
            sampling_needed=False,
            sample_size=0,
            estimated_tokens=estimated_tokens,
        )


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


class ContentStrategyResult:
    """Result of content strategy selection for a repository."""

    def __init__(
        self,
        tier: SizeTier,
        char_limit: int,
        sampling_needed: bool,
        sample_size: int,
        estimated_tokens: int,
    ) -> None:
        """Initialize content strategy result.

        Args:
            tier: Size tier classification.
            char_limit: Character limit for the tier.
            sampling_needed: Whether pre-pack sampling is needed.
            sample_size: Number of files to sample if sampling_needed.
            estimated_tokens: Estimated token count before packing.
        """
        self.tier = tier
        self.char_limit = char_limit
        self.sampling_needed = sampling_needed
        self.sample_size = sample_size
        self.estimated_tokens = estimated_tokens

    @property
    def max_chars(self) -> int:
        """Character limit for packing."""
        return self.char_limit

    @property
    def max_tokens_approx(self) -> int:
        """Approximate token limit from char limit."""
        return self.char_limit // _CHARS_PER_TOKEN

    def __repr__(self) -> str:
        """Return a readable representation of the content strategy result."""
        parts = [
            f"tier={self.tier.value}",
            f"char_limit={self.char_limit}",
            f"sampling_needed={self.sampling_needed}",
        ]
        if self.sampling_needed:
            parts.append(f"sample_size={self.sample_size}")
        return f"ContentStrategyResult({', '.join(parts)})"
