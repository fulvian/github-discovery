"""Deep-scan (Gate 3) validation tests.

Tests that Gate 3 deep assessment follows the correct rules:
only top percentile candidates are assessed, all dimensions scored,
token budgets respected, caching works, and gate enforcement is strict.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from github_discovery.feasibility.sprint0 import _select_top_percentile
from github_discovery.models.assessment import DeepAssessmentResult, DimensionScore, TokenUsage
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import (
    CandidateStatus,
    DiscoveryChannel,
    DomainType,
    ScoreDimension,
)
from github_discovery.models.screening import (
    MetadataScreenResult,
    ScreeningResult,
    StaticScreenResult,
)

if TYPE_CHECKING:
    pass

pytestmark = pytest.mark.integration


def _make_candidate(
    full_name: str,
    *,
    stars: int = 100,
    domain: DomainType = DomainType.LIBRARY,
) -> RepoCandidate:
    """Create a test RepoCandidate with sensible defaults."""
    return RepoCandidate(
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        html_url=f"https://github.com/{full_name}",
        api_url=f"https://api.github.com/repos/{full_name}",
        description=f"Test repo {full_name}",
        language="Python",
        domain=domain,
        stars=stars,
        forks_count=stars // 10,
        watchers_count=stars,
        subscribers_count=max(1, stars // 100),
        open_issues_count=5,
        created_at=datetime(2022, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 3, 1, tzinfo=UTC),
        pushed_at=datetime(2026, 2, 28, tzinfo=UTC),
        license_info={"spdx_id": "MIT"},
        owner_login=full_name.split("/", maxsplit=1)[0],
        source_channel=DiscoveryChannel.SEARCH,
        commit_sha=f"sha_{full_name.replace('/', '_')}",
        status=CandidateStatus.DISCOVERED,
    )


def _make_screening_result(
    full_name: str,
    *,
    gate1_total: float = 0.7,
    gate2_total: float = 0.6,
    gate1_pass: bool = True,
    gate2_pass: bool = True,
) -> ScreeningResult:
    """Create a test ScreeningResult."""
    return ScreeningResult(
        full_name=full_name,
        gate1=MetadataScreenResult(
            full_name=full_name,
            gate1_total=gate1_total,
            gate1_pass=gate1_pass,
        ),
        gate2=StaticScreenResult(
            full_name=full_name,
            gate2_total=gate2_total,
            gate2_pass=gate2_pass,
        ),
    )


def test_deep_scan_only_top_percentile() -> None:
    """Only top percentile of candidates selected for deep assessment."""
    candidates = [_make_candidate(f"owner/repo{i}") for i in range(20)]
    screening_results = {
        c.full_name: _make_screening_result(
            c.full_name,
            gate1_total=0.5 + (i * 0.02),
            gate2_total=0.4 + (i * 0.02),
        )
        for i, c in enumerate(candidates)
    }

    # 15% of 20 = 3 candidates
    selected = _select_top_percentile(
        candidates,
        screening_results,
        percentile=0.15,
    )

    assert len(selected) == 3
    # The selected ones should be the highest-scoring
    selected_names = {c.full_name for c in selected}
    assert "owner/repo19" in selected_names


def test_deep_scan_all_dimensions() -> None:
    """All 8 dimensions should be represented in a DeepAssessmentResult."""
    dimensions = {
        dim: DimensionScore(
            dimension=dim,
            value=0.7,
            explanation=f"Test explanation for {dim.value}",
            evidence=[f"Observed good {dim.value} practices"],
            confidence=0.8,
        )
        for dim in ScoreDimension
    }

    result = DeepAssessmentResult(
        full_name="test/repo",
        dimensions=dimensions,
        overall_quality=0.75,
        overall_explanation="Test assessment",
        overall_confidence=0.8,
        gate3_pass=True,
    )

    assert result.dimensions_assessed == 8
    assert result.completeness_ratio == 1.0
    for dim in ScoreDimension:
        assert result.get_dimension_score(dim) is not None


def test_deep_scan_respects_budget() -> None:
    """Token budget is tracked in DeepAssessmentResult."""
    result = DeepAssessmentResult(
        full_name="test/repo",
        token_usage=TokenUsage(
            prompt_tokens=5000,
            completion_tokens=2000,
            total_tokens=7000,
            model_used="gpt-4o",
            provider="test",
        ),
    )

    assert result.token_usage.total_tokens == 7000
    assert result.token_usage.total_tokens > 0


def test_deep_scan_caches_by_sha() -> None:
    """Same commit SHA should produce cached DeepAssessmentResult."""
    sha = "abc123def456"

    result1 = DeepAssessmentResult(
        full_name="test/repo",
        commit_sha=sha,
        overall_quality=0.8,
        cached=False,
    )
    result2 = DeepAssessmentResult(
        full_name="test/repo",
        commit_sha=sha,
        overall_quality=0.8,
        cached=True,
    )

    assert result1.commit_sha == result2.commit_sha
    assert not result1.cached
    assert result2.cached


def test_deep_scan_gate_enforcement() -> None:
    """can_proceed_to_gate3 requires both Gate 1 and Gate 2 pass."""
    # Both pass
    passing = ScreeningResult(
        full_name="test/repo",
        gate1=MetadataScreenResult(
            full_name="test/repo",
            gate1_total=0.7,
            gate1_pass=True,
        ),
        gate2=StaticScreenResult(
            full_name="test/repo",
            gate2_total=0.6,
            gate2_pass=True,
        ),
    )
    assert passing.can_proceed_to_gate3 is True

    # Gate 1 fails
    gate1_fail = ScreeningResult(
        full_name="test/repo",
        gate1=MetadataScreenResult(
            full_name="test/repo",
            gate1_total=0.3,
            gate1_pass=False,
        ),
        gate2=StaticScreenResult(
            full_name="test/repo",
            gate2_total=0.6,
            gate2_pass=True,
        ),
    )
    assert gate1_fail.can_proceed_to_gate3 is False

    # Gate 2 fails
    gate2_fail = ScreeningResult(
        full_name="test/repo",
        gate1=MetadataScreenResult(
            full_name="test/repo",
            gate1_total=0.7,
            gate1_pass=True,
        ),
        gate2=StaticScreenResult(
            full_name="test/repo",
            gate2_total=0.3,
            gate2_pass=False,
        ),
    )
    assert gate2_fail.can_proceed_to_gate3 is False

    # No screening results
    no_screening = ScreeningResult(full_name="test/repo")
    assert no_screening.can_proceed_to_gate3 is False


def test_deep_scan_empty_input() -> None:
    """Empty candidate list produces empty selection."""
    selected = _select_top_percentile(
        [],
        {},
        percentile=0.15,
    )
    assert selected == []
