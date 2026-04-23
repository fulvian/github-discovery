"""Tests for Gate 2 static/security screening engine."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from github_discovery.config import GitHubSettings, ScreeningSettings
from github_discovery.exceptions import HardGateViolationError
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel, DomainType
from github_discovery.models.screening import (
    ComplexityScore,
    MetadataScreenResult,
    SecretHygieneScore,
    SecurityHygieneScore,
    StaticScreenResult,
    VulnerabilityScore,
)
from github_discovery.screening.gate2_static import Gate2StaticScreener
from github_discovery.screening.subprocess_runner import SubprocessResult


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


def _make_gate1_pass(full_name: str = "org/repo", total: float = 0.8) -> MetadataScreenResult:
    """Create a passing Gate 1 result."""
    return MetadataScreenResult(
        full_name=full_name,
        gate1_total=total,
        gate1_pass=True,
    )


def _make_gate1_fail(full_name: str = "org/repo") -> MetadataScreenResult:
    """Create a failing Gate 1 result."""
    return MetadataScreenResult(
        full_name=full_name,
        gate1_total=0.1,
        gate1_pass=False,
    )


@pytest.fixture
def settings() -> ScreeningSettings:
    """Default screening settings."""
    return ScreeningSettings()


@pytest.fixture
def settings_no_hard_gate() -> ScreeningSettings:
    """Screening settings with hard gate enforcement disabled."""
    return ScreeningSettings(hard_gate_enforcement=False)


@pytest.fixture
def github_settings() -> GitHubSettings:
    """Default GitHub settings."""
    return GitHubSettings()


@pytest.fixture
def mock_rest_client() -> AsyncMock:
    """Mock GitHubRestClient."""
    return AsyncMock()


@pytest.fixture
def screener(
    mock_rest_client: AsyncMock,
    settings: ScreeningSettings,
    github_settings: GitHubSettings,
) -> Gate2StaticScreener:
    """Gate2StaticScreener with mocked sub-scorers."""
    return Gate2StaticScreener(mock_rest_client, settings, github_settings)


@pytest.fixture
def screener_with_mocks(
    mock_rest_client: AsyncMock,
    settings: ScreeningSettings,
    github_settings: GitHubSettings,
) -> tuple[Gate2StaticScreener, dict[str, AsyncMock]]:
    """Gate2StaticScreener with all sub-scorers mocked.

    Returns (screener, mocks_dict) where mocks_dict has keys:
    scorecard, osv, secrets, complexity.
    """
    s = Gate2StaticScreener(mock_rest_client, settings, github_settings)

    mocks = {
        "scorecard": AsyncMock(return_value=SecurityHygieneScore(value=0.8)),
        "osv": AsyncMock(return_value=VulnerabilityScore(value=0.7)),
        "secrets": AsyncMock(return_value=SecretHygieneScore(value=0.9)),
        "complexity": AsyncMock(return_value=ComplexityScore(value=0.6)),
    }

    s._scorecard.score = mocks["scorecard"]
    s._osv.score = mocks["osv"]
    s._secrets.score = mocks["secrets"]
    s._complexity.score = mocks["complexity"]

    # Mock clone_repo to avoid real git operations
    s._clone_repo = AsyncMock(return_value=None)  # type: ignore[assignment]

    return s, mocks


class TestGate2Screen:
    """Tests for Gate2StaticScreener.screen()."""

    async def test_screen_returns_static_result(
        self,
        screener_with_mocks: tuple[Gate2StaticScreener, dict[str, AsyncMock]],
    ) -> None:
        """screen() returns a StaticScreenResult with all sub-scores."""
        screener, _ = screener_with_mocks
        candidate = _make_candidate()
        gate1 = _make_gate1_pass()

        result = await screener.screen(candidate, gate1)

        assert isinstance(result, StaticScreenResult)
        assert result.full_name == "org/repo"
        assert result.security_hygiene.value == 0.8
        assert result.vulnerability.value == 0.7
        assert result.complexity.value == 0.6
        assert result.secret_hygiene.value == 0.9

    async def test_screen_hard_gate_enforcement(
        self,
        screener: Gate2StaticScreener,
    ) -> None:
        """screen() raises HardGateViolationError when gate1_pass is False."""
        candidate = _make_candidate()
        gate1 = _make_gate1_fail()

        with pytest.raises(HardGateViolationError):
            await screener.screen(candidate, gate1)

    async def test_screen_computes_gate2_total(
        self,
        screener_with_mocks: tuple[Gate2StaticScreener, dict[str, AsyncMock]],
    ) -> None:
        """screen() computes weighted gate2_total from sub-scores."""
        screener, _ = screener_with_mocks
        candidate = _make_candidate()
        gate1 = _make_gate1_pass()

        result = await screener.screen(candidate, gate1)

        # All weights are 1.0 default, so average of 0.8, 0.7, 0.6, 0.9
        expected = (0.8 + 0.7 + 0.6 + 0.9) / 4
        assert abs(result.gate2_total - expected) < 1e-9

    async def test_screen_applies_threshold_pass(
        self,
        screener_with_mocks: tuple[Gate2StaticScreener, dict[str, AsyncMock]],
    ) -> None:
        """screen() sets gate2_pass=True when total >= threshold."""
        screener, _ = screener_with_mocks
        candidate = _make_candidate()
        gate1 = _make_gate1_pass()

        result = await screener.screen(candidate, gate1, threshold=0.5)

        assert result.gate2_pass is True
        assert result.threshold_used == 0.5

    async def test_screen_applies_threshold_fail(
        self,
        screener_with_mocks: tuple[Gate2StaticScreener, dict[str, AsyncMock]],
    ) -> None:
        """screen() sets gate2_pass=False when total < threshold."""
        screener, _ = screener_with_mocks
        candidate = _make_candidate()
        gate1 = _make_gate1_pass()

        # threshold higher than the computed total (~0.75)
        result = await screener.screen(candidate, gate1, threshold=0.99)

        assert result.gate2_pass is False
        assert result.threshold_used == 0.99

    async def test_screen_tools_used_tracking(
        self,
        screener_with_mocks: tuple[Gate2StaticScreener, dict[str, AsyncMock]],
    ) -> None:
        """screen() tracks which tools were successfully used."""
        screener, _ = screener_with_mocks
        candidate = _make_candidate()
        gate1 = _make_gate1_pass()

        result = await screener.screen(candidate, gate1)

        assert "scorecard" in result.tools_used
        assert "osv" in result.tools_used
        assert "gitleaks" in result.tools_used
        assert "scc" in result.tools_used
        assert len(result.tools_failed) == 0

    async def test_screen_graceful_degradation(
        self,
        screener_with_mocks: tuple[Gate2StaticScreener, dict[str, AsyncMock]],
    ) -> None:
        """screen() degrades gracefully when a tool fails."""
        screener, mocks = screener_with_mocks
        # Make scorecard fail
        mocks["scorecard"].side_effect = RuntimeError("API down")

        candidate = _make_candidate()
        gate1 = _make_gate1_pass()

        result = await screener.screen(candidate, gate1)

        assert "scorecard" in result.tools_failed
        assert "scorecard" not in result.tools_used
        # Other tools should still succeed
        assert "osv" in result.tools_used
        # Result should still be computed with fallback score
        assert result.gate2_total > 0.0

    async def test_screen_custom_threshold(
        self,
        screener_with_mocks: tuple[Gate2StaticScreener, dict[str, AsyncMock]],
    ) -> None:
        """screen() uses custom threshold when provided."""
        screener, _ = screener_with_mocks
        candidate = _make_candidate()
        gate1 = _make_gate1_pass()

        result = await screener.screen(candidate, gate1, threshold=0.3)

        assert result.threshold_used == 0.3


class TestGate2HardGateToggle:
    """Tests for hard_gate_enforcement configuration toggle."""

    async def test_hard_gate_disabled_allows_gate1_fail(
        self,
        mock_rest_client: AsyncMock,
        settings_no_hard_gate: ScreeningSettings,
        github_settings: GitHubSettings,
    ) -> None:
        """When hard_gate_enforcement=False, gate1_fail does NOT raise."""
        s = Gate2StaticScreener(mock_rest_client, settings_no_hard_gate, github_settings)

        # Mock sub-scorers so the result is computed
        s._scorecard.score = AsyncMock(return_value=SecurityHygieneScore(value=0.8))
        s._osv.score = AsyncMock(return_value=VulnerabilityScore(value=0.7))
        s._secrets.score = AsyncMock(return_value=SecretHygieneScore(value=0.9))
        s._complexity.score = AsyncMock(return_value=ComplexityScore(value=0.6))
        s._clone_repo = AsyncMock(return_value=None)  # type: ignore[assignment]

        candidate = _make_candidate()
        gate1 = _make_gate1_fail()

        # Should NOT raise — hard gate is disabled
        result = await s.screen(candidate, gate1)

        assert isinstance(result, StaticScreenResult)
        assert result.gate2_pass is True

    async def test_hard_gate_enabled_raises_on_gate1_fail(
        self,
        screener: Gate2StaticScreener,
    ) -> None:
        """When hard_gate_enforcement=True (default), gate1_fail raises."""
        candidate = _make_candidate()
        gate1 = _make_gate1_fail()

        with pytest.raises(HardGateViolationError):
            await screener.screen(candidate, gate1)


class TestGate2CloneManagement:
    """Tests for shallow clone management in Gate 2."""

    async def test_clone_success_passes_dir_to_subprocess_tools(
        self,
        mock_rest_client: AsyncMock,
        settings: ScreeningSettings,
        github_settings: GitHubSettings,
    ) -> None:
        """Successful clone passes clone_dir to secrets and complexity tools."""
        s = Gate2StaticScreener(mock_rest_client, settings, github_settings)

        # Track what clone_dir is passed to each tool
        secrets_calls: list[str | None] = []
        complexity_calls: list[str | None] = []

        async def _mock_secrets_score(
            candidate: object, clone_dir: str | None = None
        ) -> SecretHygieneScore:
            secrets_calls.append(clone_dir)
            return SecretHygieneScore(value=0.9)

        async def _mock_complexity_score(
            candidate: object, clone_dir: str | None = None
        ) -> ComplexityScore:
            complexity_calls.append(clone_dir)
            return ComplexityScore(value=0.6)

        s._secrets.score = _mock_secrets_score  # type: ignore[assignment]
        s._complexity.score = _mock_complexity_score  # type: ignore[assignment]
        s._scorecard.score = AsyncMock(return_value=SecurityHygieneScore(value=0.8))
        s._osv.score = AsyncMock(return_value=VulnerabilityScore(value=0.7))

        # Mock clone_repo to return a path
        s._clone_repo = AsyncMock(return_value="/mocked/clone_dir")  # type: ignore[assignment]
        # Mock cleanup so we don't try to rmtree a fake path
        s._cleanup_clone = staticmethod(lambda _: None)  # type: ignore[assignment]

        candidate = _make_candidate()
        gate1 = _make_gate1_pass()
        result = await s.screen(candidate, gate1)

        assert result.gate2_total > 0
        # Both subprocess tools should have received the clone_dir
        assert secrets_calls == ["/mocked/clone_dir"]
        assert complexity_calls == ["/mocked/clone_dir"]

    async def test_clone_failure_passes_none_to_subprocess_tools(
        self,
        screener_with_mocks: tuple[Gate2StaticScreener, dict[str, AsyncMock]],
    ) -> None:
        """Failed clone (returns None) passes None to subprocess tools."""
        screener, _ = screener_with_mocks
        # screener_with_mocks already sets _clone_repo to return None

        candidate = _make_candidate()
        gate1 = _make_gate1_pass()

        result = await screener.screen(candidate, gate1)

        assert result.gate2_total > 0

    async def test_cleanup_called_even_on_error(
        self,
        mock_rest_client: AsyncMock,
        settings: ScreeningSettings,
        github_settings: GitHubSettings,
    ) -> None:
        """Cleanup is called even when sub-scorers raise exceptions."""
        s = Gate2StaticScreener(mock_rest_client, settings, github_settings)

        s._scorecard.score = AsyncMock(side_effect=RuntimeError("boom"))
        s._osv.score = AsyncMock(side_effect=RuntimeError("boom"))
        s._secrets.score = AsyncMock(side_effect=RuntimeError("boom"))
        s._complexity.score = AsyncMock(side_effect=RuntimeError("boom"))

        clone_dir = "/mocked/clone_cleanup"
        s._clone_repo = AsyncMock(return_value=clone_dir)  # type: ignore[assignment]

        cleanup_calls: list[str | None] = []
        original_cleanup = s._cleanup_clone

        def _track_cleanup(d: str | None) -> None:
            cleanup_calls.append(d)
            original_cleanup(d)

        s._cleanup_clone = staticmethod(_track_cleanup)  # type: ignore[assignment]

        candidate = _make_candidate()
        gate1 = _make_gate1_pass()
        result = await s.screen(candidate, gate1)

        # Cleanup should have been called with the clone_dir
        assert clone_dir in cleanup_calls
        # Result should still be computed (graceful degradation)
        assert isinstance(result, StaticScreenResult)

    async def test_close_closes_scorecard(self) -> None:
        """close() delegates to scorecard.close()."""
        mock_rest = AsyncMock()
        s = Gate2StaticScreener(mock_rest, ScreeningSettings(), GitHubSettings())
        s._scorecard.close = AsyncMock()  # type: ignore[assignment]

        await s.close()

        s._scorecard.close.assert_awaited_once()  # type: ignore[attr-defined]


class TestGate2ScreenBatch:
    """Tests for Gate2StaticScreener.screen_batch()."""

    async def test_screen_batch_filters_gate1_failed(
        self,
        screener_with_mocks: tuple[Gate2StaticScreener, dict[str, AsyncMock]],
    ) -> None:
        """screen_batch() skips Gate 2 for candidates that failed Gate 1."""
        screener, mocks = screener_with_mocks

        c1 = _make_candidate("org/pass")
        c2 = _make_candidate("org/fail")
        gate1_pass = _make_gate1_pass("org/pass")
        gate1_fail = _make_gate1_fail("org/fail")

        results = await screener.screen_batch(
            [(c1, gate1_pass), (c2, gate1_fail)],
        )

        assert len(results) == 2
        # First should be screened
        assert results[0].full_name == "org/pass"
        assert results[0].gate2_pass is True
        # Second should have a failed result (not screened through Gate 2)
        assert results[1].full_name == "org/fail"
        assert results[1].gate2_pass is False

        # Only 1 candidate should have been scored (the pass one)
        assert mocks["scorecard"].call_count == 1

    async def test_screen_batch_empty(
        self,
        screener_with_mocks: tuple[Gate2StaticScreener, dict[str, AsyncMock]],
    ) -> None:
        """screen_batch() returns empty list for empty input."""
        screener, _ = screener_with_mocks

        results = await screener.screen_batch([])

        assert results == []


class TestGate2CloneRepo:
    """Tests for the _clone_repo internal method."""

    async def test_clone_repo_success(
        self,
        mock_rest_client: AsyncMock,
        settings: ScreeningSettings,
        github_settings: GitHubSettings,
    ) -> None:
        """_clone_repo returns path on successful clone."""
        s = Gate2StaticScreener(mock_rest_client, settings, github_settings)

        # Mock subprocess runner
        s._subprocess_runner.run = AsyncMock(  # type: ignore[union-attr]
            return_value=SubprocessResult(returncode=0, stdout="", stderr=""),
        )

        candidate = _make_candidate()
        with patch(
            "github_discovery.screening.gate2_static.tempfile.mkdtemp",
            return_value="/mocked/clone",
        ):
            result = await s._clone_repo(candidate)

        assert result is not None
        assert result == "/mocked/clone"

    async def test_clone_repo_failure_returns_none(
        self,
        mock_rest_client: AsyncMock,
        settings: ScreeningSettings,
        github_settings: GitHubSettings,
    ) -> None:
        """_clone_repo returns None when git clone fails."""
        s = Gate2StaticScreener(mock_rest_client, settings, github_settings)

        s._subprocess_runner.run = AsyncMock(  # type: ignore[union-attr]
            return_value=SubprocessResult(
                returncode=128, stdout="", stderr="fatal: repo not found"
            ),
        )

        candidate = _make_candidate()
        with patch(
            "github_discovery.screening.gate2_static.tempfile.mkdtemp",
            return_value="/mocked/clone",
        ):
            result = await s._clone_repo(candidate)

        assert result is None

    async def test_cleanup_clone_removes_dir(self) -> None:
        """_cleanup_clone removes the directory if it exists."""
        # Create a real temp dir to test cleanup
        real_dir = tempfile.mkdtemp(prefix="test_cleanup_")

        # Verify it exists
        assert Path(real_dir).exists()

        # Clean it up
        Gate2StaticScreener._cleanup_clone(real_dir)

        # Should be removed
        assert not Path(real_dir).exists()

    @staticmethod
    def test_cleanup_clone_handles_none() -> None:
        """_cleanup_clone does nothing when given None."""
        # Should not raise
        Gate2StaticScreener._cleanup_clone(None)
