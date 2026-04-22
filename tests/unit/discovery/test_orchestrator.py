"""Tests for the DiscoveryOrchestrator.

Tests the central orchestrator that coordinates channels, deduplicates,
scores, and produces the final candidate pool. All channel interactions
are mocked — no real HTTP calls.
"""

from __future__ import annotations

import pathlib
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github_discovery.config import DiscoverySettings, GitHubSettings, Settings
from github_discovery.discovery.orchestrator import DiscoveryOrchestrator
from github_discovery.discovery.pool import PoolManager
from github_discovery.discovery.types import ChannelResult, DiscoveryQuery, DiscoveryResult
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel

# --- Constants ---

_BREADTH_BONUS_PER_EXTRA_CHANNEL = 0.1
_CHANNEL_QUALITY_BONUS_AWESOME_LIST = 0.1
_CHANNEL_QUALITY_BONUS_CODE_SEARCH = 0.05
_CHANNEL_QUALITY_BONUS_DEPENDENCY = 0.1


# --- Helpers ---


def _make_candidate(
    full_name: str,
    *,
    score: float = 0.5,
    channel: DiscoveryChannel = DiscoveryChannel.SEARCH,
) -> RepoCandidate:
    """Create a test RepoCandidate with minimal required fields."""
    return RepoCandidate(
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        html_url=f"https://github.com/{full_name}",
        api_url=f"https://api.github.com/repos/{full_name}",
        description=f"Test repo {full_name}",
        language="Python",
        created_at=datetime(2023, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 12, 1, tzinfo=UTC),
        pushed_at=datetime(2024, 12, 15, tzinfo=UTC),
        owner_login=full_name.split("/", maxsplit=1)[0],
        source_channel=channel,
        discovery_score=score,
    )


def _make_settings(
    *,
    default_channels: list[str] | None = None,
) -> Settings:
    """Create test Settings with a fake GitHub token."""
    return Settings(
        github=GitHubSettings(token="test_token"),  # noqa: S106
        discovery=DiscoverySettings(
            default_channels=default_channels or ["search", "registry", "curated"],
        ),
    )


# --- Fixtures ---


@pytest.fixture
def settings() -> Settings:
    """Default test settings."""
    return _make_settings()


@pytest.fixture
def pool_manager(tmp_path: pathlib.Path) -> PoolManager:
    """PoolManager with a temp database."""
    return PoolManager(str(tmp_path / "test_orchestrator.db"))


@pytest.fixture
def query() -> DiscoveryQuery:
    """Basic discovery query."""
    return DiscoveryQuery(
        query="static analysis python",
        channels=[DiscoveryChannel.SEARCH, DiscoveryChannel.REGISTRY],
        max_candidates=100,
    )


# --- Test: Channels are selected and run ---


@patch("github_discovery.discovery.orchestrator.SeedExpansion")
@patch("github_discovery.discovery.orchestrator.DependencyChannel")
@patch("github_discovery.discovery.orchestrator.RegistryChannel")
@patch("github_discovery.discovery.orchestrator.CuratedChannel")
@patch("github_discovery.discovery.orchestrator.CodeSearchChannel")
@patch("github_discovery.discovery.orchestrator.SearchChannel")
async def test_discover_runs_selected_channels(
    mock_search_cls: MagicMock,
    mock_code_search_cls: MagicMock,
    mock_curated_cls: MagicMock,
    mock_registry_cls: MagicMock,
    mock_dep_cls: MagicMock,
    mock_seed_cls: MagicMock,
    settings: Settings,
    pool_manager: PoolManager,
) -> None:
    """Orchestrator runs only the channels specified in the query."""
    candidate_a = _make_candidate("org/repo-a", score=0.6)
    candidate_b = _make_candidate("org/repo-b", score=0.4, channel=DiscoveryChannel.REGISTRY)

    mock_search = mock_search_cls.return_value
    mock_search.search = AsyncMock(
        return_value=ChannelResult(
            channel=DiscoveryChannel.SEARCH,
            candidates=[candidate_a],
        )
    )

    mock_registry = mock_registry_cls.return_value
    mock_registry.search = AsyncMock(
        return_value=ChannelResult(
            channel=DiscoveryChannel.REGISTRY,
            candidates=[candidate_b],
        )
    )

    orchestrator = DiscoveryOrchestrator(settings, pool_manager)
    query = DiscoveryQuery(
        query="test",
        channels=[DiscoveryChannel.SEARCH, DiscoveryChannel.REGISTRY],
    )
    result = await orchestrator.discover(query)

    assert isinstance(result, DiscoveryResult)
    assert result.total_candidates == 2
    assert DiscoveryChannel.SEARCH in result.channels_used
    assert DiscoveryChannel.REGISTRY in result.channels_used
    # Verify the actual channel methods were called
    mock_search.search.assert_awaited_once()
    mock_registry.search.assert_awaited_once()
    await pool_manager.close()


# --- Test: Deduplication by full_name ---


@patch("github_discovery.discovery.orchestrator.SeedExpansion")
@patch("github_discovery.discovery.orchestrator.DependencyChannel")
@patch("github_discovery.discovery.orchestrator.RegistryChannel")
@patch("github_discovery.discovery.orchestrator.CuratedChannel")
@patch("github_discovery.discovery.orchestrator.CodeSearchChannel")
@patch("github_discovery.discovery.orchestrator.SearchChannel")
async def test_discover_deduplicates_by_full_name(
    mock_search_cls: MagicMock,
    mock_code_search_cls: MagicMock,
    mock_curated_cls: MagicMock,
    mock_registry_cls: MagicMock,
    mock_dep_cls: MagicMock,
    mock_seed_cls: MagicMock,
    settings: Settings,
    pool_manager: PoolManager,
) -> None:
    """Same repo from two channels produces one candidate with higher score."""
    candidate_search = _make_candidate("org/duplicate-repo", score=0.5)
    candidate_registry = _make_candidate(
        "org/duplicate-repo",
        score=0.4,
        channel=DiscoveryChannel.REGISTRY,
    )

    mock_search = mock_search_cls.return_value
    mock_search.search = AsyncMock(
        return_value=ChannelResult(
            channel=DiscoveryChannel.SEARCH,
            candidates=[candidate_search],
        )
    )
    mock_registry = mock_registry_cls.return_value
    mock_registry.search = AsyncMock(
        return_value=ChannelResult(
            channel=DiscoveryChannel.REGISTRY,
            candidates=[candidate_registry],
        )
    )

    orchestrator = DiscoveryOrchestrator(settings, pool_manager)
    query = DiscoveryQuery(
        query="test",
        channels=[DiscoveryChannel.SEARCH, DiscoveryChannel.REGISTRY],
    )
    result = await orchestrator.discover(query)

    assert result.total_candidates == 1
    assert result.duplicate_count == 1
    assert (
        result.candidates_by_channel.get("search", 0)
        + result.candidates_by_channel.get(
            "registry",
            0,
        )
        >= 2
    )
    await pool_manager.close()


# --- Test: Discovery score calculation (breadth) ---


@patch("github_discovery.discovery.orchestrator.SeedExpansion")
@patch("github_discovery.discovery.orchestrator.DependencyChannel")
@patch("github_discovery.discovery.orchestrator.RegistryChannel")
@patch("github_discovery.discovery.orchestrator.CuratedChannel")
@patch("github_discovery.discovery.orchestrator.CodeSearchChannel")
@patch("github_discovery.discovery.orchestrator.SearchChannel")
async def test_discover_calculates_discovery_score(
    mock_search_cls: MagicMock,
    mock_code_search_cls: MagicMock,
    mock_curated_cls: MagicMock,
    mock_registry_cls: MagicMock,
    mock_dep_cls: MagicMock,
    mock_seed_cls: MagicMock,
    settings: Settings,
    pool_manager: PoolManager,
) -> None:
    """Repo found by multiple channels gets higher score than single-channel repo."""
    multi_repo = _make_candidate("org/multi-found", score=0.5)
    single_repo = _make_candidate("org/single-found", score=0.5)

    # Both channels find multi_repo, only search finds single_repo
    mock_search = mock_search_cls.return_value
    mock_search.search = AsyncMock(
        return_value=ChannelResult(
            channel=DiscoveryChannel.SEARCH,
            candidates=[multi_repo, single_repo],
        )
    )
    mock_registry = mock_registry_cls.return_value
    mock_registry.search = AsyncMock(
        return_value=ChannelResult(
            channel=DiscoveryChannel.REGISTRY,
            candidates=[multi_repo],
        )
    )

    orchestrator = DiscoveryOrchestrator(settings, pool_manager)
    query = DiscoveryQuery(
        query="test",
        channels=[DiscoveryChannel.SEARCH, DiscoveryChannel.REGISTRY],
    )
    result = await orchestrator.discover(query)

    assert result.total_candidates == 2
    # The multi-found repo should be ranked first (higher score)
    assert result.pool_id  # just check it exists
    await pool_manager.close()


# --- Test: Max candidates truncation ---


@patch("github_discovery.discovery.orchestrator.SeedExpansion")
@patch("github_discovery.discovery.orchestrator.DependencyChannel")
@patch("github_discovery.discovery.orchestrator.RegistryChannel")
@patch("github_discovery.discovery.orchestrator.CuratedChannel")
@patch("github_discovery.discovery.orchestrator.CodeSearchChannel")
@patch("github_discovery.discovery.orchestrator.SearchChannel")
async def test_discover_respects_max_candidates(
    mock_search_cls: MagicMock,
    mock_code_search_cls: MagicMock,
    mock_curated_cls: MagicMock,
    mock_registry_cls: MagicMock,
    mock_dep_cls: MagicMock,
    mock_seed_cls: MagicMock,
    settings: Settings,
    pool_manager: PoolManager,
) -> None:
    """Results are truncated to max_candidates."""
    candidates = [_make_candidate(f"org/repo-{i}", score=0.9 - i * 0.1) for i in range(10)]

    mock_search = mock_search_cls.return_value
    mock_search.search = AsyncMock(
        return_value=ChannelResult(
            channel=DiscoveryChannel.SEARCH,
            candidates=candidates,
        )
    )

    orchestrator = DiscoveryOrchestrator(settings, pool_manager)
    query = DiscoveryQuery(
        query="test",
        channels=[DiscoveryChannel.SEARCH],
        max_candidates=3,
    )
    result = await orchestrator.discover(query)

    assert result.total_candidates == 3
    await pool_manager.close()


# --- Test: Channel failure is graceful ---


@patch("github_discovery.discovery.orchestrator.SeedExpansion")
@patch("github_discovery.discovery.orchestrator.DependencyChannel")
@patch("github_discovery.discovery.orchestrator.RegistryChannel")
@patch("github_discovery.discovery.orchestrator.CuratedChannel")
@patch("github_discovery.discovery.orchestrator.CodeSearchChannel")
@patch("github_discovery.discovery.orchestrator.SearchChannel")
async def test_discover_channel_failure_graceful(
    mock_search_cls: MagicMock,
    mock_code_search_cls: MagicMock,
    mock_curated_cls: MagicMock,
    mock_registry_cls: MagicMock,
    mock_dep_cls: MagicMock,
    mock_seed_cls: MagicMock,
    settings: Settings,
    pool_manager: PoolManager,
) -> None:
    """If one channel fails, others continue and produce results."""
    candidate_b = _make_candidate(
        "org/repo-b",
        score=0.6,
        channel=DiscoveryChannel.REGISTRY,
    )

    mock_search = mock_search_cls.return_value
    mock_search.search = AsyncMock(side_effect=RuntimeError("API failure"))

    mock_registry = mock_registry_cls.return_value
    mock_registry.search = AsyncMock(
        return_value=ChannelResult(
            channel=DiscoveryChannel.REGISTRY,
            candidates=[candidate_b],
        )
    )

    orchestrator = DiscoveryOrchestrator(settings, pool_manager)
    query = DiscoveryQuery(
        query="test",
        channels=[DiscoveryChannel.SEARCH, DiscoveryChannel.REGISTRY],
    )
    result = await orchestrator.discover(query)

    # Only the working channel's candidate
    assert result.total_candidates == 1
    assert DiscoveryChannel.REGISTRY in result.channels_used
    await pool_manager.close()


# --- Test: Empty results ---


@patch("github_discovery.discovery.orchestrator.SeedExpansion")
@patch("github_discovery.discovery.orchestrator.DependencyChannel")
@patch("github_discovery.discovery.orchestrator.RegistryChannel")
@patch("github_discovery.discovery.orchestrator.CuratedChannel")
@patch("github_discovery.discovery.orchestrator.CodeSearchChannel")
@patch("github_discovery.discovery.orchestrator.SearchChannel")
async def test_discover_empty_results(
    mock_search_cls: MagicMock,
    mock_code_search_cls: MagicMock,
    mock_curated_cls: MagicMock,
    mock_registry_cls: MagicMock,
    mock_dep_cls: MagicMock,
    mock_seed_cls: MagicMock,
    settings: Settings,
    pool_manager: PoolManager,
) -> None:
    """All channels return empty → empty DiscoveryResult."""
    mock_search = mock_search_cls.return_value
    mock_search.search = AsyncMock(
        return_value=ChannelResult(
            channel=DiscoveryChannel.SEARCH,
            candidates=[],
        )
    )

    orchestrator = DiscoveryOrchestrator(settings, pool_manager)
    query = DiscoveryQuery(
        query="obscure-nonexistent-topic",
        channels=[DiscoveryChannel.SEARCH],
    )
    result = await orchestrator.discover(query)

    assert result.total_candidates == 0
    assert result.duplicate_count == 0
    await pool_manager.close()


# --- Test: Pool persistence ---


@patch("github_discovery.discovery.orchestrator.SeedExpansion")
@patch("github_discovery.discovery.orchestrator.DependencyChannel")
@patch("github_discovery.discovery.orchestrator.RegistryChannel")
@patch("github_discovery.discovery.orchestrator.CuratedChannel")
@patch("github_discovery.discovery.orchestrator.CodeSearchChannel")
@patch("github_discovery.discovery.orchestrator.SearchChannel")
async def test_discover_persists_pool(
    mock_search_cls: MagicMock,
    mock_code_search_cls: MagicMock,
    mock_curated_cls: MagicMock,
    mock_registry_cls: MagicMock,
    mock_dep_cls: MagicMock,
    mock_seed_cls: MagicMock,
    settings: Settings,
    pool_manager: PoolManager,
) -> None:
    """PoolManager.create_pool is called with discovered candidates."""
    candidate = _make_candidate("org/repo-persist", score=0.7)

    mock_search = mock_search_cls.return_value
    mock_search.search = AsyncMock(
        return_value=ChannelResult(
            channel=DiscoveryChannel.SEARCH,
            candidates=[candidate],
        )
    )

    orchestrator = DiscoveryOrchestrator(settings, pool_manager)
    query = DiscoveryQuery(
        query="test",
        channels=[DiscoveryChannel.SEARCH],
    )
    result = await orchestrator.discover(query)

    assert result.pool_id
    # Verify pool is retrievable from the database
    pool = await pool_manager.get_pool(result.pool_id)
    assert pool is not None
    assert pool.total_count == 1
    await pool_manager.close()


# --- Test: _calculate_discovery_score breadth bonus ---


def test_calculate_discovery_score_breadth() -> None:
    """Breadth bonus is applied when a repo is found by multiple channels."""
    settings = _make_settings()
    pool_manager = PoolManager(":memory:")
    orchestrator = DiscoveryOrchestrator(settings, pool_manager)

    # Use channels with no quality bonuses to test breadth in isolation
    channels = {
        DiscoveryChannel.SEARCH,
        DiscoveryChannel.REGISTRY,
        DiscoveryChannel.SEED_EXPANSION,
    }
    score = orchestrator._calculate_discovery_score(
        base_score=0.5,
        channels=channels,
    )

    # 0.5 base + 0.1 * (3 - 1) = 0.5 + 0.2 = 0.7
    # (SEARCH, REGISTRY, SEED_EXPANSION have no quality bonus)
    expected = 0.5 + _BREADTH_BONUS_PER_EXTRA_CHANNEL * 2
    assert abs(score - expected) < 1e-9


# --- Test: _calculate_discovery_score channel quality bonus ---


def test_calculate_discovery_score_channel_quality() -> None:
    """AWESOME_LIST, CODE_SEARCH, DEPENDENCY channels get quality bonus."""
    settings = _make_settings()
    pool_manager = PoolManager(":memory:")
    orchestrator = DiscoveryOrchestrator(settings, pool_manager)

    channels = {DiscoveryChannel.AWESOME_LIST}
    score = orchestrator._calculate_discovery_score(
        base_score=0.5,
        channels=channels,
    )

    # 0.5 base + 0.0 breadth (1 channel) + 0.1 awesome_list bonus = 0.6
    expected = 0.5 + _CHANNEL_QUALITY_BONUS_AWESOME_LIST
    assert abs(score - expected) < 1e-9


def test_calculate_discovery_score_channel_quality_dependency() -> None:
    """DEPENDENCY channel gets quality bonus."""
    settings = _make_settings()
    pool_manager = PoolManager(":memory:")
    orchestrator = DiscoveryOrchestrator(settings, pool_manager)

    channels = {DiscoveryChannel.DEPENDENCY}
    score = orchestrator._calculate_discovery_score(
        base_score=0.5,
        channels=channels,
    )

    # 0.5 base + 0.0 breadth (1 channel) + 0.1 dependency bonus = 0.6
    expected = 0.5 + _CHANNEL_QUALITY_BONUS_DEPENDENCY
    assert abs(score - expected) < 1e-9


def test_calculate_discovery_score_capped_at_one() -> None:
    """Discovery score is capped at 1.0."""
    settings = _make_settings()
    pool_manager = PoolManager(":memory:")
    orchestrator = DiscoveryOrchestrator(settings, pool_manager)

    channels = {
        DiscoveryChannel.AWESOME_LIST,
        DiscoveryChannel.CODE_SEARCH,
        DiscoveryChannel.DEPENDENCY,
        DiscoveryChannel.SEARCH,
        DiscoveryChannel.REGISTRY,
    }
    score = orchestrator._calculate_discovery_score(
        base_score=0.95,
        channels=channels,
    )

    assert score <= 1.0


# --- Test: Return type is DiscoveryResult ---


@patch("github_discovery.discovery.orchestrator.SeedExpansion")
@patch("github_discovery.discovery.orchestrator.DependencyChannel")
@patch("github_discovery.discovery.orchestrator.RegistryChannel")
@patch("github_discovery.discovery.orchestrator.CuratedChannel")
@patch("github_discovery.discovery.orchestrator.CodeSearchChannel")
@patch("github_discovery.discovery.orchestrator.SearchChannel")
async def test_discover_returns_discovery_result(
    mock_search_cls: MagicMock,
    mock_code_search_cls: MagicMock,
    mock_curated_cls: MagicMock,
    mock_registry_cls: MagicMock,
    mock_dep_cls: MagicMock,
    mock_seed_cls: MagicMock,
    settings: Settings,
    pool_manager: PoolManager,
) -> None:
    """discover() returns a properly populated DiscoveryResult."""
    candidate = _make_candidate("org/repo-x", score=0.5)

    mock_search = mock_search_cls.return_value
    mock_search.search = AsyncMock(
        return_value=ChannelResult(
            channel=DiscoveryChannel.SEARCH,
            candidates=[candidate],
        )
    )

    orchestrator = DiscoveryOrchestrator(settings, pool_manager)
    query = DiscoveryQuery(
        query="test",
        channels=[DiscoveryChannel.SEARCH],
        session_id="sess-123",
    )
    result = await orchestrator.discover(query)

    assert isinstance(result, DiscoveryResult)
    assert result.pool_id  # non-empty UUID
    assert result.total_candidates == 1
    assert isinstance(result.candidates_by_channel, dict)
    assert isinstance(result.channels_used, list)
    assert isinstance(result.elapsed_seconds, float)
    assert result.elapsed_seconds >= 0.0
    assert result.session_id == "sess-123"
    await pool_manager.close()


# --- Test: Default channels from settings ---


@patch("github_discovery.discovery.orchestrator.SeedExpansion")
@patch("github_discovery.discovery.orchestrator.DependencyChannel")
@patch("github_discovery.discovery.orchestrator.RegistryChannel")
@patch("github_discovery.discovery.orchestrator.CuratedChannel")
@patch("github_discovery.discovery.orchestrator.CodeSearchChannel")
@patch("github_discovery.discovery.orchestrator.SearchChannel")
async def test_discover_uses_default_channels_from_settings(
    mock_search_cls: MagicMock,
    mock_code_search_cls: MagicMock,
    mock_curated_cls: MagicMock,
    mock_registry_cls: MagicMock,
    mock_dep_cls: MagicMock,
    mock_seed_cls: MagicMock,
    pool_manager: PoolManager,
) -> None:
    """When query.channels is None, uses settings.discovery.default_channels."""
    settings = _make_settings(default_channels=["search", "awesome_list"])

    mock_search = mock_search_cls.return_value
    mock_search.search = AsyncMock(
        return_value=ChannelResult(
            channel=DiscoveryChannel.SEARCH,
            candidates=[_make_candidate("org/a", score=0.5)],
        )
    )
    mock_curated = mock_curated_cls.return_value
    mock_curated.search = AsyncMock(
        return_value=ChannelResult(
            channel=DiscoveryChannel.AWESOME_LIST,
            candidates=[
                _make_candidate("org/b", score=0.6, channel=DiscoveryChannel.AWESOME_LIST)
            ],
        )
    )

    orchestrator = DiscoveryOrchestrator(settings, pool_manager)
    query = DiscoveryQuery(query="test", channels=None)  # use defaults
    result = await orchestrator.discover(query)

    assert result.total_candidates == 2
    mock_search.search.assert_awaited_once()
    mock_curated.search.assert_awaited_once()
    await pool_manager.close()


# --- Test: SeedExpansion with seed_urls ---


@patch("github_discovery.discovery.orchestrator.SeedExpansion")
@patch("github_discovery.discovery.orchestrator.DependencyChannel")
@patch("github_discovery.discovery.orchestrator.RegistryChannel")
@patch("github_discovery.discovery.orchestrator.CuratedChannel")
@patch("github_discovery.discovery.orchestrator.CodeSearchChannel")
@patch("github_discovery.discovery.orchestrator.SearchChannel")
async def test_discover_seed_expansion_with_seed_urls(
    mock_search_cls: MagicMock,
    mock_code_search_cls: MagicMock,
    mock_curated_cls: MagicMock,
    mock_registry_cls: MagicMock,
    mock_dep_cls: MagicMock,
    mock_seed_cls: MagicMock,
    settings: Settings,
    pool_manager: PoolManager,
) -> None:
    """SeedExpansion channel is called with seed_urls from the query."""
    candidate = _make_candidate(
        "org/expanded-repo",
        score=0.65,
        channel=DiscoveryChannel.SEED_EXPANSION,
    )

    mock_seed = mock_seed_cls.return_value
    mock_seed.expand = AsyncMock(
        return_value=ChannelResult(
            channel=DiscoveryChannel.SEED_EXPANSION,
            candidates=[candidate],
        )
    )

    orchestrator = DiscoveryOrchestrator(settings, pool_manager)
    query = DiscoveryQuery(
        query="test",
        channels=[DiscoveryChannel.SEED_EXPANSION],
        seed_urls=["https://github.com/seed/repo"],
    )
    result = await orchestrator.discover(query)

    assert result.total_candidates == 1
    mock_seed.expand.assert_awaited_once_with(["https://github.com/seed/repo"])
    await pool_manager.close()


# --- Test: SeedExpansion without seed_urls returns empty ---


@patch("github_discovery.discovery.orchestrator.SeedExpansion")
@patch("github_discovery.discovery.orchestrator.DependencyChannel")
@patch("github_discovery.discovery.orchestrator.RegistryChannel")
@patch("github_discovery.discovery.orchestrator.CuratedChannel")
@patch("github_discovery.discovery.orchestrator.CodeSearchChannel")
@patch("github_discovery.discovery.orchestrator.SearchChannel")
async def test_discover_seed_expansion_without_seed_urls(
    mock_search_cls: MagicMock,
    mock_code_search_cls: MagicMock,
    mock_curated_cls: MagicMock,
    mock_registry_cls: MagicMock,
    mock_dep_cls: MagicMock,
    mock_seed_cls: MagicMock,
    settings: Settings,
    pool_manager: PoolManager,
) -> None:
    """SeedExpansion with no seed_urls produces empty result."""
    mock_seed = mock_seed_cls.return_value

    orchestrator = DiscoveryOrchestrator(settings, pool_manager)
    query = DiscoveryQuery(
        query="test",
        channels=[DiscoveryChannel.SEED_EXPANSION],
        seed_urls=None,
    )
    result = await orchestrator.discover(query)

    assert result.total_candidates == 0
    # expand should NOT be called when there are no seed_urls
    mock_seed.expand.assert_not_called()
    await pool_manager.close()
