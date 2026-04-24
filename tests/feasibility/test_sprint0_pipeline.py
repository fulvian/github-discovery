"""Sprint 0 pipeline validation tests.

Tests that the full pipeline Gate 0→1→2→3 executes correctly
on a representative dataset of candidates.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from github_discovery.config import Settings
from github_discovery.feasibility.sprint0 import Sprint0Config, Sprint0Result, run_sprint0
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import CandidateStatus, DiscoveryChannel, DomainType
from github_discovery.models.scoring import RankedRepo, ScoreResult
from github_discovery.models.screening import (
    MetadataScreenResult,
    ScreeningResult,
    StaticScreenResult,
)

if TYPE_CHECKING:
    pass

pytestmark = pytest.mark.integration


def test_sprint0_config_defaults() -> None:
    """Sprint0Config has correct defaults."""
    config = Sprint0Config()
    assert config.max_candidates == 500
    assert config.gate1_threshold == 0.4
    assert config.gate2_threshold == 0.3
    assert config.deep_assess_percentile == 0.15
    assert config.llm_budget_tokens == 500_000
    assert config.seed == 42
    assert len(config.queries) == 5
    assert len(config.domains) == 5


def test_sprint0_config_custom() -> None:
    """Sprint0Config can be customized."""
    config = Sprint0Config(
        max_candidates=100,
        queries=["test query"],
        gate1_threshold=0.5,
        gate2_threshold=0.4,
        deep_assess_percentile=0.2,
        llm_budget_tokens=100_000,
        seed=123,
    )
    assert config.max_candidates == 100
    assert config.queries == ["test query"]
    assert config.gate1_threshold == 0.5
    assert config.gate2_threshold == 0.4
    assert config.deep_assess_percentile == 0.2
    assert config.llm_budget_tokens == 100_000
    assert config.seed == 123


def test_sprint0_result_creation() -> None:
    """Sprint0Result dataclass creates correctly."""
    result = Sprint0Result()
    assert result.total_discovered == 0
    assert result.gate1_passed == 0
    assert result.gate2_passed == 0
    assert result.gate3_assessed == 0
    assert result.ranked_repos == []
    assert result.hidden_gems == []
    assert result.domain_distribution == {}
    assert result.pipeline_duration_seconds == 0.0
    assert result.llm_tokens_used == 0

    result_with_data = Sprint0Result(
        total_discovered=50,
        gate1_passed=30,
        gate2_passed=20,
        gate3_assessed=5,
        pipeline_duration_seconds=12.5,
    )
    assert result_with_data.total_discovered == 50
    assert result_with_data.gate1_passed == 30


async def test_sprint0_with_mock_candidates(
    feasibility_settings: Settings,
    sprint0_config: Sprint0Config,
    sample_candidates: list[RepoCandidate],
) -> None:
    """run_sprint0 with pre-provided candidates completes."""
    with (
        patch(
            "github_discovery.feasibility.sprint0._run_screening",
        ) as mock_screening,
        patch(
            "github_discovery.feasibility.sprint0._run_assessment",
        ) as mock_assessment,
        patch(
            "github_discovery.feasibility.sprint0._run_scoring",
        ) as mock_scoring,
        patch(
            "github_discovery.feasibility.sprint0._run_ranking",
        ) as mock_ranking,
    ):
        # Build mock screening results — pass all candidates through gates
        screening_map: dict[str, ScreeningResult] = {}
        for c in sample_candidates[:20]:
            screening_map[c.full_name] = ScreeningResult(
                full_name=c.full_name,
                gate1=MetadataScreenResult(
                    full_name=c.full_name,
                    gate1_total=0.7,
                    gate1_pass=True,
                ),
                gate2=StaticScreenResult(
                    full_name=c.full_name,
                    gate2_total=0.6,
                    gate2_pass=True,
                ),
            )
        mock_screening.return_value = screening_map
        mock_assessment.return_value = ({}, 0)

        # Build mock score results
        score_results = [
            ScoreResult(
                full_name=c.full_name,
                domain=c.domain,
                quality_score=0.75,
                stars=c.stars,
            )
            for c in sample_candidates[:20]
        ]
        mock_scoring.return_value = score_results

        # Build mock ranked repos
        ranked = [
            RankedRepo(
                rank=i + 1,
                full_name=sr.full_name,
                domain=sr.domain,
                score_result=sr,
            )
            for i, sr in enumerate(score_results)
        ]
        mock_ranking.return_value = ranked

        result = await run_sprint0(
            feasibility_settings,
            sprint0_config,
            candidates=sample_candidates[:20],
        )

    assert isinstance(result, Sprint0Result)
    assert result.total_discovered == 20


async def test_sprint0_respects_max_candidates(
    feasibility_settings: Settings,
    sprint0_config: Sprint0Config,
    sample_candidates: list[RepoCandidate],
) -> None:
    """result.total_discovered equals provided candidates count."""
    limited = sample_candidates[:10]
    with (
        patch("github_discovery.feasibility.sprint0._run_screening") as mock_screening,
        patch("github_discovery.feasibility.sprint0._run_assessment") as mock_assessment,
        patch("github_discovery.feasibility.sprint0._run_scoring") as mock_scoring,
        patch("github_discovery.feasibility.sprint0._run_ranking") as mock_ranking,
    ):
        mock_screening.return_value = {}
        mock_assessment.return_value = ({}, 0)
        mock_scoring.return_value = []
        mock_ranking.return_value = []

        result = await run_sprint0(
            feasibility_settings,
            sprint0_config,
            candidates=limited,
        )

    assert result.total_discovered == 10


async def test_sprint0_identifies_hidden_gems(
    feasibility_settings: Settings,
    sprint0_config: Sprint0Config,
) -> None:
    """hidden_gems list is populated for low-star, high-quality repos."""
    candidates = [
        RepoCandidate(
            full_name="gem/hidden-tool",
            url="https://github.com/gem/hidden-tool",
            html_url="https://github.com/gem/hidden-tool",
            api_url="https://api.github.com/repos/gem/hidden-tool",
            description="A hidden gem library",
            language="Python",
            domain=DomainType.LIBRARY,
            stars=42,
            forks_count=5,
            watchers_count=42,
            subscribers_count=4,
            open_issues_count=1,
            created_at=datetime(2022, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 3, 1, tzinfo=UTC),
            pushed_at=datetime(2026, 2, 28, tzinfo=UTC),
            license_info={"spdx_id": "MIT"},
            owner_login="gem",
            source_channel=DiscoveryChannel.SEARCH,
            commit_sha="abc123",
            status=CandidateStatus.DISCOVERED,
        ),
        RepoCandidate(
            full_name="popular/big-tool",
            url="https://github.com/popular/big-tool",
            html_url="https://github.com/popular/big-tool",
            api_url="https://api.github.com/repos/popular/big-tool",
            description="A popular library",
            language="Python",
            domain=DomainType.LIBRARY,
            stars=50000,
            forks_count=5000,
            watchers_count=50000,
            subscribers_count=800,
            open_issues_count=200,
            created_at=datetime(2018, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 3, 1, tzinfo=UTC),
            pushed_at=datetime(2026, 2, 28, tzinfo=UTC),
            license_info={"spdx_id": "MIT"},
            owner_login="popular",
            source_channel=DiscoveryChannel.SEARCH,
            commit_sha="def456",
            status=CandidateStatus.DISCOVERED,
        ),
    ]

    with (
        patch("github_discovery.feasibility.sprint0._run_screening") as mock_screening,
        patch("github_discovery.feasibility.sprint0._run_assessment") as mock_assessment,
        patch("github_discovery.feasibility.sprint0._run_scoring") as mock_scoring,
        patch("github_discovery.feasibility.sprint0._run_ranking") as mock_ranking,
    ):
        mock_screening.return_value = {}
        mock_assessment.return_value = ({}, 0)

        # The hidden gem gets high quality, the popular one moderate
        gem_score = ScoreResult(
            full_name="gem/hidden-tool",
            domain=DomainType.LIBRARY,
            quality_score=0.85,
            stars=42,
        )
        pop_score = ScoreResult(
            full_name="popular/big-tool",
            domain=DomainType.LIBRARY,
            quality_score=0.60,
            stars=50000,
        )
        mock_scoring.return_value = [gem_score, pop_score]

        ranked = [
            RankedRepo(
                rank=1,
                full_name="gem/hidden-tool",
                domain=DomainType.LIBRARY,
                score_result=gem_score,
            ),
            RankedRepo(
                rank=2,
                full_name="popular/big-tool",
                domain=DomainType.LIBRARY,
                score_result=pop_score,
            ),
        ]
        mock_ranking.return_value = ranked

        result = await run_sprint0(
            feasibility_settings,
            sprint0_config,
            candidates=candidates,
        )

    # Hidden gem: quality >= 0.7 and stars < 100
    assert len(result.hidden_gems) >= 1
    assert result.hidden_gems[0].full_name == "gem/hidden-tool"


async def test_sprint0_gate_ordering(
    feasibility_settings: Settings,
    sprint0_config: Sprint0Config,
    sample_candidates: list[RepoCandidate],
) -> None:
    """gate1 >= gate2 >= gate3 counts (funnel narrows)."""
    subset = sample_candidates[:15]

    with (
        patch("github_discovery.feasibility.sprint0._run_screening") as mock_screening,
        patch("github_discovery.feasibility.sprint0._run_assessment") as mock_assessment,
        patch("github_discovery.feasibility.sprint0._run_scoring") as mock_scoring,
        patch("github_discovery.feasibility.sprint0._run_ranking") as mock_ranking,
    ):
        # 15 discovered, 10 pass gate1, 5 pass gate1+gate2
        screening_map: dict[str, ScreeningResult] = {}
        for i, c in enumerate(subset):
            gate1_pass = i < 10
            gate2_pass = i < 5
            screening_map[c.full_name] = ScreeningResult(
                full_name=c.full_name,
                gate1=MetadataScreenResult(
                    full_name=c.full_name,
                    gate1_total=0.7 if gate1_pass else 0.2,
                    gate1_pass=gate1_pass,
                ),
                gate2=StaticScreenResult(
                    full_name=c.full_name,
                    gate2_total=0.6 if gate2_pass else 0.2,
                    gate2_pass=gate2_pass,
                )
                if gate1_pass
                else None,
            )
        mock_screening.return_value = screening_map
        mock_assessment.return_value = ({}, 0)
        mock_scoring.return_value = []
        mock_ranking.return_value = []

        result = await run_sprint0(
            feasibility_settings,
            sprint0_config,
            candidates=subset,
        )

    assert result.total_discovered == 15
    assert result.gate1_passed == 10
    assert result.gate2_passed <= result.gate1_passed
    assert result.gate3_assessed <= result.gate2_passed or result.gate3_assessed == 0


async def test_sprint0_domain_distribution(
    feasibility_settings: Settings,
    sprint0_config: Sprint0Config,
    sample_candidates: list[RepoCandidate],
) -> None:
    """domain_distribution dict is populated from candidates."""
    with (
        patch("github_discovery.feasibility.sprint0._run_screening") as mock_screening,
        patch("github_discovery.feasibility.sprint0._run_assessment") as mock_assessment,
        patch("github_discovery.feasibility.sprint0._run_scoring") as mock_scoring,
        patch("github_discovery.feasibility.sprint0._run_ranking") as mock_ranking,
    ):
        mock_screening.return_value = {}
        mock_assessment.return_value = ({}, 0)
        mock_scoring.return_value = []
        mock_ranking.return_value = []

        result = await run_sprint0(
            feasibility_settings,
            sprint0_config,
            candidates=sample_candidates,
        )

    assert isinstance(result.domain_distribution, dict)
    assert len(result.domain_distribution) > 0
    # At minimum we should have library, cli, ml_lib, data_tool, web_framework
    expected_domains = {"library", "cli", "ml_lib", "data_tool", "web_framework"}
    assert expected_domains.issubset(set(result.domain_distribution.keys()))


async def test_sprint0_deterministic_with_seed(
    feasibility_settings: Settings,
    sprint0_config: Sprint0Config,
    sample_candidates: list[RepoCandidate],
) -> None:
    """Same seed produces same result."""
    subset = sample_candidates[:10]

    with (
        patch("github_discovery.feasibility.sprint0._run_screening") as mock_screening,
        patch("github_discovery.feasibility.sprint0._run_assessment") as mock_assessment,
        patch("github_discovery.feasibility.sprint0._run_scoring") as mock_scoring,
        patch("github_discovery.feasibility.sprint0._run_ranking") as mock_ranking,
    ):
        mock_screening.return_value = {}
        mock_assessment.return_value = ({}, 0)
        mock_scoring.return_value = []
        mock_ranking.return_value = []

        result1 = await run_sprint0(
            feasibility_settings,
            sprint0_config,
            candidates=subset,
        )
        result2 = await run_sprint0(
            feasibility_settings,
            sprint0_config,
            candidates=subset,
        )

    assert result1.total_discovered == result2.total_discovered


async def test_sprint0_tracks_timing(
    feasibility_settings: Settings,
    sprint0_config: Sprint0Config,
    sample_candidates: list[RepoCandidate],
) -> None:
    """pipeline_duration_seconds > 0 after a run."""
    with (
        patch("github_discovery.feasibility.sprint0._run_screening") as mock_screening,
        patch("github_discovery.feasibility.sprint0._run_assessment") as mock_assessment,
        patch("github_discovery.feasibility.sprint0._run_scoring") as mock_scoring,
        patch("github_discovery.feasibility.sprint0._run_ranking") as mock_ranking,
    ):
        mock_screening.return_value = {}
        mock_assessment.return_value = ({}, 0)
        mock_scoring.return_value = []
        mock_ranking.return_value = []

        result = await run_sprint0(
            feasibility_settings,
            sprint0_config,
            candidates=sample_candidates[:5],
        )

    assert result.pipeline_duration_seconds > 0
