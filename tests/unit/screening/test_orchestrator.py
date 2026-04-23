"""Tests for Screening Orchestrator and Policy Engine."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from github_discovery.config import Settings
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel, DomainType, GateLevel
from github_discovery.models.screening import (
    MetadataScreenResult,
    ScreeningResult,
    StaticScreenResult,
)
from github_discovery.screening.gate1_metadata import Gate1MetadataScreener
from github_discovery.screening.gate2_static import Gate2StaticScreener
from github_discovery.screening.orchestrator import ScreeningOrchestrator
from github_discovery.screening.types import ScreeningContext


def _make_candidate(
    full_name: str = "org/repo",
    domain: DomainType = DomainType.OTHER,
) -> RepoCandidate:
    """Create a minimal RepoCandidate for tests."""
    return RepoCandidate(
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        html_url=f"https://github.com/{full_name}",
        api_url=f"https://api.github.com/repos/{full_name}",
        language="Python",
        domain=domain,
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        owner_login=full_name.split("/", maxsplit=1)[0],
        source_channel=DiscoveryChannel.SEARCH,
    )


def _make_gate1_result(
    full_name: str = "org/repo",
    passed: bool = True,
    total: float = 0.8,
) -> MetadataScreenResult:
    """Create a Gate 1 result."""
    return MetadataScreenResult(
        full_name=full_name,
        gate1_total=total,
        gate1_pass=passed,
    )


def _make_gate2_result(
    full_name: str = "org/repo",
    passed: bool = True,
    total: float = 0.7,
) -> StaticScreenResult:
    """Create a Gate 2 result."""
    return StaticScreenResult(
        full_name=full_name,
        gate2_total=total,
        gate2_pass=passed,
    )


@pytest.fixture
def mock_gate1() -> AsyncMock:
    """Mock Gate1MetadataScreener."""
    screener = AsyncMock(spec=Gate1MetadataScreener)
    screener.screen = AsyncMock(
        return_value=_make_gate1_result(passed=True),
    )
    return screener


@pytest.fixture
def mock_gate2() -> AsyncMock:
    """Mock Gate2StaticScreener."""
    screener = AsyncMock(spec=Gate2StaticScreener)
    screener.screen = AsyncMock(
        return_value=_make_gate2_result(passed=True),
    )
    return screener


@pytest.fixture
def settings() -> Settings:
    """Default application settings."""
    return Settings()


@pytest.fixture
def orchestrator(
    settings: Settings,
    mock_gate1: AsyncMock,
    mock_gate2: AsyncMock,
) -> ScreeningOrchestrator:
    """ScreeningOrchestrator with mocked gate screeners."""
    return ScreeningOrchestrator(settings, mock_gate1, mock_gate2)


class TestScreenGate1Only:
    """Test orchestrator running only Gate 1."""

    async def test_screen_gate1_only(
        self,
        orchestrator: ScreeningOrchestrator,
        mock_gate1: AsyncMock,
        mock_gate2: AsyncMock,
    ) -> None:
        """When gate_level=METADATA, only Gate 1 runs."""
        candidate = _make_candidate()
        context = ScreeningContext(
            pool_id="test-pool",
            candidates=[candidate],
            gate_level=GateLevel.METADATA,
        )

        results = await orchestrator.screen(context)

        assert len(results) == 1
        assert results[0].gate1 is not None
        assert results[0].gate2 is None
        mock_gate1.screen.assert_called_once()
        mock_gate2.screen.assert_not_called()

    async def test_screen_both_gates(
        self,
        orchestrator: ScreeningOrchestrator,
        mock_gate1: AsyncMock,
        mock_gate2: AsyncMock,
    ) -> None:
        """When gate_level=STATIC_SECURITY, both gates run if Gate 1 passes."""
        candidate = _make_candidate()
        context = ScreeningContext(
            pool_id="test-pool",
            candidates=[candidate],
            gate_level=GateLevel.STATIC_SECURITY,
        )

        results = await orchestrator.screen(context)

        assert len(results) == 1
        assert results[0].gate1 is not None
        assert results[0].gate2 is not None
        mock_gate1.screen.assert_called_once()
        mock_gate2.screen.assert_called_once()

    async def test_screen_gate1_fail_no_gate2(
        self,
        orchestrator: ScreeningOrchestrator,
        mock_gate1: AsyncMock,
        mock_gate2: AsyncMock,
    ) -> None:
        """When Gate 1 fails, Gate 2 is NOT executed."""
        mock_gate1.screen.return_value = _make_gate1_result(passed=False, total=0.2)
        candidate = _make_candidate()
        context = ScreeningContext(
            pool_id="test-pool",
            candidates=[candidate],
            gate_level=GateLevel.STATIC_SECURITY,
        )

        results = await orchestrator.screen(context)

        assert len(results) == 1
        assert results[0].gate1 is not None
        assert results[0].gate1.gate1_pass is False
        assert results[0].gate2 is None
        mock_gate2.screen.assert_not_called()


class TestHardGateEnforcement:
    """Test hard gate enforcement via can_proceed_to_gate3."""

    async def test_hard_gate_enforcement_both_pass(
        self,
        orchestrator: ScreeningOrchestrator,
        mock_gate1: AsyncMock,
        mock_gate2: AsyncMock,
    ) -> None:
        """can_proceed_to_gate3 is True only when both gates pass."""
        mock_gate1.screen.return_value = _make_gate1_result(passed=True, total=0.8)
        mock_gate2.screen.return_value = _make_gate2_result(passed=True, total=0.7)

        candidate = _make_candidate()
        context = ScreeningContext(
            pool_id="test-pool",
            candidates=[candidate],
            gate_level=GateLevel.STATIC_SECURITY,
        )

        results = await orchestrator.screen(context)

        assert results[0].can_proceed_to_gate3 is True

    async def test_hard_gate_enforcement_gate2_fails(
        self,
        orchestrator: ScreeningOrchestrator,
        mock_gate1: AsyncMock,
        mock_gate2: AsyncMock,
    ) -> None:
        """can_proceed_to_gate3 is False when Gate 2 fails."""
        mock_gate1.screen.return_value = _make_gate1_result(passed=True, total=0.8)
        mock_gate2.screen.return_value = _make_gate2_result(passed=False, total=0.3)

        candidate = _make_candidate()
        context = ScreeningContext(
            pool_id="test-pool",
            candidates=[candidate],
            gate_level=GateLevel.STATIC_SECURITY,
        )

        results = await orchestrator.screen(context)

        assert results[0].can_proceed_to_gate3 is False


class TestThresholdPolicy:
    """Test domain-specific and override threshold logic."""

    async def test_domain_specific_threshold(
        self,
        orchestrator: ScreeningOrchestrator,
        mock_gate1: AsyncMock,
    ) -> None:
        """Library domain uses higher Gate 1 threshold (0.5)."""
        candidate = _make_candidate(domain=DomainType.LIBRARY)
        context = ScreeningContext(
            pool_id="test-pool",
            candidates=[candidate],
            gate_level=GateLevel.METADATA,
        )

        await orchestrator.screen(context)

        # Verify threshold passed to gate1.screen
        call_args = mock_gate1.screen.call_args
        threshold_used = call_args.kwargs.get("threshold")
        assert threshold_used == 0.5

    async def test_threshold_override(
        self,
        orchestrator: ScreeningOrchestrator,
        mock_gate1: AsyncMock,
    ) -> None:
        """Explicit override in context takes priority over domain and default."""
        candidate = _make_candidate(domain=DomainType.LIBRARY)
        context = ScreeningContext(
            pool_id="test-pool",
            candidates=[candidate],
            gate_level=GateLevel.METADATA,
            min_gate1_score=0.9,
        )

        await orchestrator.screen(context)

        call_args = mock_gate1.screen.call_args
        threshold_used = call_args.kwargs.get("threshold")
        assert threshold_used == 0.9

    async def test_default_threshold_no_domain(
        self,
        orchestrator: ScreeningOrchestrator,
        mock_gate1: AsyncMock,
    ) -> None:
        """Default threshold (0.4) is used when no domain override."""
        candidate = _make_candidate(domain=DomainType.OTHER)
        context = ScreeningContext(
            pool_id="test-pool",
            candidates=[candidate],
            gate_level=GateLevel.METADATA,
        )

        await orchestrator.screen(context)

        call_args = mock_gate1.screen.call_args
        threshold_used = call_args.kwargs.get("threshold")
        assert threshold_used == 0.4

    async def test_gate2_domain_threshold(
        self,
        orchestrator: ScreeningOrchestrator,
        mock_gate1: AsyncMock,
        mock_gate2: AsyncMock,
    ) -> None:
        """Library domain uses higher Gate 2 threshold (0.6)."""
        candidate = _make_candidate(domain=DomainType.LIBRARY)
        context = ScreeningContext(
            pool_id="test-pool",
            candidates=[candidate],
            gate_level=GateLevel.STATIC_SECURITY,
        )

        await orchestrator.screen(context)

        call_args = mock_gate2.screen.call_args
        threshold_used = call_args.kwargs.get("threshold")
        assert threshold_used == 0.6


class TestBatchScreening:
    """Test batch screening through orchestrator."""

    async def test_batch_screening(
        self,
        orchestrator: ScreeningOrchestrator,
        mock_gate1: AsyncMock,
    ) -> None:
        """All candidates in pool are screened."""
        candidates = [_make_candidate(f"org/repo{i}") for i in range(5)]
        context = ScreeningContext(
            pool_id="test-pool",
            candidates=candidates,
            gate_level=GateLevel.METADATA,
        )

        results = await orchestrator.screen(context)

        assert len(results) == 5
        assert mock_gate1.screen.call_count == 5
        assert all(r.gate1 is not None for r in results)

    async def test_error_recovery(
        self,
        orchestrator: ScreeningOrchestrator,
        mock_gate1: AsyncMock,
    ) -> None:
        """If one candidate fails, others continue screening."""
        call_count = 0

        async def _side_effect(candidate: RepoCandidate, **kwargs: object) -> MetadataScreenResult:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("API error for repo2")
            return _make_gate1_result(full_name=candidate.full_name)

        mock_gate1.screen.side_effect = _side_effect

        candidates = [_make_candidate(f"org/repo{i}") for i in range(3)]
        context = ScreeningContext(
            pool_id="test-pool",
            candidates=candidates,
            gate_level=GateLevel.METADATA,
        )

        results = await orchestrator.screen(context)

        assert len(results) == 3
        # 2nd candidate should have gate1=None due to error
        failed = [r for r in results if r.gate1 is None]
        assert len(failed) == 1
        # Other 2 should have results
        succeeded = [r for r in results if r.gate1 is not None]
        assert len(succeeded) == 2

    async def test_screen_empty_pool(
        self,
        orchestrator: ScreeningOrchestrator,
        mock_gate1: AsyncMock,
    ) -> None:
        """Empty candidates list returns empty results."""
        context = ScreeningContext(
            pool_id="empty-pool",
            candidates=[],
            gate_level=GateLevel.METADATA,
        )

        results = await orchestrator.screen(context)

        assert results == []
        mock_gate1.screen.assert_not_called()


class TestQuickScreen:
    """Test quick_screen single-repo shortcut."""

    async def test_quick_screen_single_repo(
        self,
        orchestrator: ScreeningOrchestrator,
        mock_gate1: AsyncMock,
        mock_gate2: AsyncMock,
    ) -> None:
        """quick_screen screens a single repo through Gate 1 (and optionally Gate 2)."""
        candidate = _make_candidate()

        result = await orchestrator.quick_screen(candidate, gate_levels="1")

        assert isinstance(result, ScreeningResult)
        assert result.gate1 is not None
        assert result.gate2 is None
        mock_gate1.screen.assert_called_once()
        mock_gate2.screen.assert_not_called()

    async def test_quick_screen_both_gates(
        self,
        orchestrator: ScreeningOrchestrator,
        mock_gate1: AsyncMock,
        mock_gate2: AsyncMock,
    ) -> None:
        """quick_screen with gate_levels='2' runs both gates."""
        candidate = _make_candidate()

        result = await orchestrator.quick_screen(candidate, gate_levels="2")

        assert result.gate1 is not None
        assert result.gate2 is not None
        mock_gate1.screen.assert_called_once()
        mock_gate2.screen.assert_called_once()

    async def test_quick_screen_gate1_fail(
        self,
        orchestrator: ScreeningOrchestrator,
        mock_gate1: AsyncMock,
        mock_gate2: AsyncMock,
    ) -> None:
        """quick_screen skips Gate 2 when Gate 1 fails."""
        mock_gate1.screen.return_value = _make_gate1_result(passed=False, total=0.2)
        candidate = _make_candidate()

        result = await orchestrator.quick_screen(candidate, gate_levels="2")

        assert result.gate1 is not None
        assert result.gate1.gate1_pass is False
        assert result.gate2 is None
        mock_gate2.screen.assert_not_called()


class TestAllDomainThresholds:
    """Verify all DomainType values have explicit thresholds."""

    @pytest.mark.parametrize(
        "domain,expected_gate1,expected_gate2",
        [
            (DomainType.LIBRARY, 0.5, 0.6),
            (DomainType.SECURITY_TOOL, 0.6, 0.7),
            (DomainType.DEVOPS_TOOL, 0.5, 0.6),
            (DomainType.ML_LIB, 0.4, 0.5),
            (DomainType.CLI, 0.4, 0.5),
            (DomainType.BACKEND, 0.5, 0.6),
            (DomainType.WEB_FRAMEWORK, 0.5, 0.6),
            (DomainType.DATA_TOOL, 0.4, 0.5),
            (DomainType.LANG_TOOL, 0.5, 0.6),
            (DomainType.TEST_TOOL, 0.5, 0.6),
            (DomainType.DOC_TOOL, 0.4, 0.5),
        ],
    )
    async def test_domain_gate1_threshold(
        self,
        orchestrator: ScreeningOrchestrator,
        mock_gate1: AsyncMock,
        domain: DomainType,
        expected_gate1: float,
        expected_gate2: float,
    ) -> None:
        """Each domain uses its configured Gate 1 threshold."""
        candidate = _make_candidate(domain=domain)
        context = ScreeningContext(
            pool_id="test-pool",
            candidates=[candidate],
            gate_level=GateLevel.METADATA,
        )

        await orchestrator.screen(context)

        call_args = mock_gate1.screen.call_args
        threshold_used = call_args.kwargs.get("threshold")
        assert threshold_used == expected_gate1

    @pytest.mark.parametrize(
        "domain,expected_gate2",
        [
            (DomainType.LIBRARY, 0.6),
            (DomainType.SECURITY_TOOL, 0.7),
            (DomainType.DEVOPS_TOOL, 0.6),
            (DomainType.ML_LIB, 0.5),
            (DomainType.CLI, 0.5),
            (DomainType.BACKEND, 0.6),
            (DomainType.WEB_FRAMEWORK, 0.6),
            (DomainType.DATA_TOOL, 0.5),
            (DomainType.LANG_TOOL, 0.6),
            (DomainType.TEST_TOOL, 0.6),
            (DomainType.DOC_TOOL, 0.5),
        ],
    )
    async def test_domain_gate2_threshold(
        self,
        orchestrator: ScreeningOrchestrator,
        mock_gate1: AsyncMock,
        mock_gate2: AsyncMock,
        domain: DomainType,
        expected_gate2: float,
    ) -> None:
        """Each domain uses its configured Gate 2 threshold."""
        candidate = _make_candidate(domain=domain)
        context = ScreeningContext(
            pool_id="test-pool",
            candidates=[candidate],
            gate_level=GateLevel.STATIC_SECURITY,
        )

        await orchestrator.screen(context)

        call_args = mock_gate2.screen.call_args
        threshold_used = call_args.kwargs.get("threshold")
        assert threshold_used == expected_gate2
