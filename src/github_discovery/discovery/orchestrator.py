"""Discovery orchestrator — central coordinator for the discovery pipeline.

Coordinates multiple discovery channels, deduplicates candidates by
full_name, applies breadth and channel-quality bonuses to discovery
scores, and persists the resulting candidate pool via PoolManager.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import structlog

from github_discovery.discovery.code_search_channel import CodeSearchChannel
from github_discovery.discovery.curated_channel import CuratedChannel
from github_discovery.discovery.dependency_channel import DependencyChannel
from github_discovery.discovery.github_client import GitHubRestClient
from github_discovery.discovery.graphql_client import GitHubGraphQLClient
from github_discovery.discovery.registry_channel import RegistryChannel
from github_discovery.discovery.search_channel import SearchChannel
from github_discovery.discovery.seed_expansion import SeedExpansion
from github_discovery.discovery.types import ChannelResult, DiscoveryQuery, DiscoveryResult
from github_discovery.models.enums import DiscoveryChannel

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from github_discovery.config import Settings
    from github_discovery.discovery.pool import PoolManager
    from github_discovery.models.candidate import RepoCandidate

logger = structlog.get_logger("github_discovery.discovery.orchestrator")

# --- Constants ---

_BREADTH_BONUS_PER_EXTRA_CHANNEL = 0.1  # Bonus for each additional channel beyond the first
_CHANNEL_QUALITY_BONUSES: dict[DiscoveryChannel, float] = {
    DiscoveryChannel.AWESOME_LIST: 0.1,  # Human-curated signal
    DiscoveryChannel.CODE_SEARCH: 0.05,  # Quality-signal-based discovery
    DiscoveryChannel.DEPENDENCY: 0.1,  # Provenance from trusted seeds
}
_MAX_DISCOVERY_SCORE = 1.0  # Hard cap on discovery scores

# Alias mapping: common settings strings that differ from enum values.
_CHANNEL_ALIASES: dict[str, DiscoveryChannel] = {
    "curated": DiscoveryChannel.AWESOME_LIST,
}


class DiscoveryOrchestrator:
    """Central orchestrator for the discovery pipeline.

    Coordinates channels, deduplicates candidates, applies scoring
    bonuses (breadth + channel quality), and persists the pool.
    """

    def __init__(
        self,
        settings: Settings,
        pool_manager: PoolManager,
    ) -> None:
        """Initialize orchestrator with settings and pool manager.

        Creates GitHub API clients and instantiates all discovery
        channels for use during ``discover()`` calls.

        Args:
            settings: Application settings (GitHub token, defaults, etc.).
            pool_manager: Pool persistence backend.
        """
        self._settings = settings
        self._pool_manager = pool_manager

        # Create GitHub API clients
        self._rest_client = GitHubRestClient(settings.github)
        self._graphql_client = GitHubGraphQLClient(settings.github)

        # Instantiate all channels
        self._search_channel = SearchChannel(self._rest_client)
        self._code_search_channel = CodeSearchChannel(self._rest_client)
        self._curated_channel = CuratedChannel(self._rest_client)
        self._registry_channel = RegistryChannel()
        self._dependency_channel = DependencyChannel(self._rest_client, self._graphql_client)
        self._seed_expansion = SeedExpansion(self._rest_client, self._graphql_client)

    async def discover(self, query: DiscoveryQuery) -> DiscoveryResult:
        """Run discovery across configured channels.

        Resolves channels from the query or settings defaults, runs
        them concurrently, deduplicates results, applies scoring bonuses,
        truncates to ``max_candidates``, and persists the pool.

        Args:
            query: Discovery query specifying search term, channels, limits.

        Returns:
            DiscoveryResult with deduplicated, scored candidates and pool ID.
        """
        start_time = time.monotonic()

        # 1. Resolve channels to run
        channels = self._resolve_channels(query)

        # 2. Run channels concurrently
        channel_results = await self._run_channels(channels, query)

        # 3. Build candidates_by_channel counts (pre-dedup)
        candidates_by_channel = self._build_channel_counts(channel_results)

        # 4. Deduplicate and score
        candidates, duplicate_count = self._deduplicate_and_score(channel_results)

        # 5. Sort by discovery_score descending
        candidates.sort(key=lambda c: c.discovery_score, reverse=True)

        # 6. Truncate to max_candidates
        candidates = candidates[: query.max_candidates]

        # 7. Persist pool
        pool = await self._pool_manager.create_pool(query, candidates)

        elapsed = time.monotonic() - start_time
        logger.info(
            "orchestrator_discover_complete",
            query=query.query,
            channels=[ch.value for ch in channels],
            total_candidates=len(candidates),
            duplicate_count=duplicate_count,
            elapsed_seconds=round(elapsed, 3),
        )

        return DiscoveryResult(
            pool_id=pool.pool_id,
            total_candidates=len(candidates),
            candidates_by_channel=candidates_by_channel,
            channels_used=channels,
            duplicate_count=duplicate_count,
            elapsed_seconds=elapsed,
            session_id=query.session_id,
        )

    async def close(self) -> None:
        """Close resources owned by the orchestrator.

        The REST client is shared with screening in MCP/API lifespans and is
        closed by the outer lifecycle owner. This method closes resources that
        are unique to discovery orchestration.
        """
        await self._registry_channel.close()
        await self._graphql_client.close()

    def _resolve_channels(self, query: DiscoveryQuery) -> list[DiscoveryChannel]:
        """Resolve which channels to run from query or settings.

        Args:
            query: Discovery query with optional channel override.

        Returns:
            List of DiscoveryChannel enums to execute.
        """
        if query.channels is not None:
            return list(query.channels)

        # Parse default channel strings from settings into enums
        channels: list[DiscoveryChannel] = []
        for channel_str in self._settings.discovery.default_channels:
            # Check aliases first (e.g. "curated" → AWESOME_LIST)
            aliased = _CHANNEL_ALIASES.get(channel_str)
            if aliased is not None:
                channels.append(aliased)
                continue
            try:
                channels.append(DiscoveryChannel(channel_str))
            except ValueError:
                logger.warning(
                    "orchestrator_unknown_channel",
                    channel=channel_str,
                    note="Skipping unknown channel from default_channels",
                )
        return channels if channels else [DiscoveryChannel.SEARCH]

    async def _run_channels(
        self,
        channels: list[DiscoveryChannel],
        query: DiscoveryQuery,
    ) -> list[ChannelResult]:
        """Run selected channels concurrently with error handling.

        Args:
            channels: Channels to execute.
            query: Discovery query to pass to channels.

        Returns:
            List of ChannelResult (empty results for failed channels).
        """
        tasks: list[Awaitable[ChannelResult]] = []
        for channel in channels:
            tasks.append(self._run_single_channel(channel, query))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        channel_results: list[ChannelResult] = []
        for i, result in enumerate(results):
            channel = channels[i]
            if isinstance(result, BaseException):
                logger.warning(
                    "orchestrator_channel_failed",
                    channel=channel.value,
                    error=str(result),
                    note="Continuing with empty result",
                )
                channel_results.append(ChannelResult(channel=channel, candidates=[]))
            else:
                channel_results.append(result)

        return channel_results

    async def _run_single_channel(
        self,
        channel: DiscoveryChannel,
        query: DiscoveryQuery,
    ) -> ChannelResult:
        """Run a single discovery channel.

        SeedExpansion uses ``expand()`` with seed_urls; all other
        channels use ``search()`` with the full query.

        Args:
            channel: The channel to execute.
            query: Discovery query.

        Returns:
            ChannelResult from the channel.
        """
        # Map channel enums to their search methods
        channel_map = {
            DiscoveryChannel.SEARCH: self._search_channel.search,
            DiscoveryChannel.CODE_SEARCH: self._code_search_channel.search,
            DiscoveryChannel.AWESOME_LIST: self._curated_channel.search,
            DiscoveryChannel.REGISTRY: self._registry_channel.search,
            DiscoveryChannel.DEPENDENCY: self._dependency_channel.search,
        }

        if channel in channel_map:
            return await channel_map[channel](query)

        if channel == DiscoveryChannel.SEED_EXPANSION:
            seed_urls = query.seed_urls or []
            if not seed_urls:
                return ChannelResult(channel=channel, candidates=[])
            return await self._seed_expansion.expand(seed_urls)

        logger.warning("orchestrator_unhandled_channel", channel=channel.value)
        return ChannelResult(channel=channel, candidates=[])

    def _deduplicate_and_score(
        self,
        channel_results: list[ChannelResult],
    ) -> tuple[list[RepoCandidate], int]:
        """Deduplicate candidates by full_name and apply scoring.

        For duplicates, keeps the candidate with the highest base
        discovery_score. Tracks all channels that found each candidate
        for breadth and quality bonuses.

        Args:
            channel_results: Results from all channels.

        Returns:
            Tuple of (deduplicated candidates, duplicate count).
        """
        # Track: full_name → (best candidate, set of channels)
        seen: dict[str, tuple[RepoCandidate, set[DiscoveryChannel]]] = {}
        duplicate_count = 0

        for channel_result in channel_results:
            for candidate in channel_result.candidates:
                name = candidate.full_name
                if name in seen:
                    existing_candidate, existing_channels = seen[name]
                    existing_channels.add(candidate.source_channel)
                    # Keep the candidate with the higher base score
                    if candidate.discovery_score > existing_candidate.discovery_score:
                        seen[name] = (candidate, existing_channels)
                    duplicate_count += 1
                else:
                    seen[name] = (candidate, {candidate.source_channel})

        # Apply scoring bonuses
        candidates: list[RepoCandidate] = []
        for _name, (candidate, channels) in seen.items():
            new_score = self._calculate_discovery_score(
                base_score=candidate.discovery_score,
                channels=channels,
            )
            candidates.append(candidate.model_copy(update={"discovery_score": new_score}))

        return candidates, duplicate_count

    def _calculate_discovery_score(
        self,
        base_score: float,
        channels: set[DiscoveryChannel],
    ) -> float:
        """Calculate discovery score with breadth and quality bonuses.

        Formula:
            base + breadth_bonus + channel_quality_bonus
            breadth_bonus = 0.1 * (num_channels - 1)
            channel_quality_bonus = sum of per-channel bonuses
            Capped at 1.0.

        Args:
            base_score: The candidate's base discovery score from the channel.
            channels: Set of all channels that found this candidate.

        Returns:
            Adjusted discovery score, capped at 1.0.
        """
        score = base_score

        # Breadth bonus: repos found by more channels get higher score
        if len(channels) > 1:
            score += _BREADTH_BONUS_PER_EXTRA_CHANNEL * (len(channels) - 1)

        # Channel quality bonus: certain channels add a trust signal
        for channel in channels:
            score += _CHANNEL_QUALITY_BONUSES.get(channel, 0.0)

        return min(score, _MAX_DISCOVERY_SCORE)

    @staticmethod
    def _build_channel_counts(
        channel_results: list[ChannelResult],
    ) -> dict[str, int]:
        """Build a mapping of channel name → candidate count (pre-dedup).

        Args:
            channel_results: Results from all channels.

        Returns:
            Dict mapping channel value strings to their candidate counts.
        """
        counts: dict[str, int] = {}
        for result in channel_results:
            key = result.channel.value
            counts[key] = counts.get(key, 0) + len(result.candidates)
        return counts
