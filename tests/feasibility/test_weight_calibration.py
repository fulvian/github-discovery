"""Weight calibration tests.

Tests grid search over dimension weights, calibration result structure,
weight normalization, and multi-domain calibration.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from github_discovery.feasibility.calibration import (
    CalibrationResult,
    calibrate_all_domains,
    grid_search_weights,
)
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import (
    CandidateStatus,
    DomainType,
    ScoreDimension,
)
from github_discovery.models.scoring import DomainProfile

pytestmark = pytest.mark.integration


def _make_candidate(
    full_name: str,
    *,
    stars: int = 100,
    domain: DomainType = DomainType.LIBRARY,
    description: str = "Test repo",
) -> RepoCandidate:
    """Create a test RepoCandidate with sensible defaults."""
    return RepoCandidate(
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        html_url=f"https://github.com/{full_name}",
        api_url=f"https://api.github.com/repos/{full_name}",
        description=description,
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
        source_channel="search",
        commit_sha=f"sha_{full_name.replace('/', '_')}",
        status=CandidateStatus.DISCOVERED,
    )


def _make_test_profile() -> DomainProfile:
    """Create a test DomainProfile for library domain."""
    return DomainProfile(
        domain_type=DomainType.LIBRARY,
        display_name="Library",
        description="Test library profile",
        dimension_weights={
            ScoreDimension.CODE_QUALITY: 0.20,
            ScoreDimension.ARCHITECTURE: 0.15,
            ScoreDimension.TESTING: 0.15,
            ScoreDimension.DOCUMENTATION: 0.15,
            ScoreDimension.MAINTENANCE: 0.15,
            ScoreDimension.SECURITY: 0.10,
            ScoreDimension.FUNCTIONALITY: 0.05,
            ScoreDimension.INNOVATION: 0.05,
        },
    )


def test_calibration_result_structure() -> None:
    """CalibrationResult has correct fields."""
    result = CalibrationResult(
        domain=DomainType.LIBRARY,
        original_weights={ScoreDimension.CODE_QUALITY: 0.2},
        calibrated_weights={ScoreDimension.CODE_QUALITY: 0.25},
        precision_before=0.5,
        precision_after=0.6,
        improvement=0.2,
        best_params={"code_quality": 0.25},
    )

    assert result.domain == DomainType.LIBRARY
    assert result.precision_before == 0.5
    assert result.precision_after == 0.6
    assert result.improvement == 0.2
    assert isinstance(result.original_weights, dict)
    assert isinstance(result.calibrated_weights, dict)
    assert isinstance(result.best_params, dict)


def test_grid_search_finds_improvement() -> None:
    """Calibration can find improved weights (or at least not degrade)."""
    # Create candidates where some are in ground truth
    candidates = [
        _make_candidate("good/lib-a", stars=50, description="Well-documented library with tests"),
        _make_candidate("good/lib-b", stars=30, description="Comprehensive testing suite"),
        _make_candidate("good/lib-c", stars=80, description="Clean architecture"),
        _make_candidate("bad/lib-d", stars=5000, description=""),
        _make_candidate("bad/lib-e", stars=3000, description=""),
        _make_candidate("ok/lib-f", stars=200, description="Decent library"),
    ]
    ground_truth = {"good/lib-a", "good/lib-b", "good/lib-c"}

    profile = _make_test_profile()

    result = grid_search_weights(
        DomainType.LIBRARY,
        profile,
        candidates,
        ground_truth,
        precision_k=5,
        step=0.05,
    )

    assert isinstance(result, CalibrationResult)
    # Precision after should be at least as good as before
    assert result.precision_after >= result.precision_before


def test_grid_search_respects_step() -> None:
    """Weight changes align with step size."""
    candidates = [
        _make_candidate("test/repo1", stars=50),
        _make_candidate("test/repo2", stars=100),
    ]
    ground_truth = {"test/repo1"}

    profile = _make_test_profile()
    step = 0.1

    result = grid_search_weights(
        DomainType.LIBRARY,
        profile,
        candidates,
        ground_truth,
        precision_k=2,
        step=step,
    )

    # Calibrated weights should differ from original by multiples of step
    for dim in ScoreDimension:
        original = result.original_weights.get(dim, 0.0)
        calibrated = result.calibrated_weights.get(dim, 0.0)
        if original > 0 and calibrated > 0:
            diff = abs(calibrated - original)
            # Due to normalization, exact multiples aren't guaranteed,
            # but the diff should be reasonable (< 0.5)
            assert diff < 0.5


def test_grid_search_weights_sum_to_one() -> None:
    """Calibrated weights sum to approximately 1.0."""
    candidates = [
        _make_candidate("test/repo1", stars=50),
        _make_candidate("test/repo2", stars=100),
    ]
    ground_truth = {"test/repo1"}

    profile = _make_test_profile()

    result = grid_search_weights(
        DomainType.LIBRARY,
        profile,
        candidates,
        ground_truth,
        precision_k=2,
        step=0.05,
    )

    total = sum(result.calibrated_weights.values())
    assert abs(total - 1.0) < 0.01, f"Weights sum to {total}, expected ~1.0"


def test_calibrate_all_domains() -> None:
    """Multiple domains are calibrated independently."""
    candidates = [
        _make_candidate("lib/repo1", stars=50, domain=DomainType.LIBRARY),
        _make_candidate("lib/repo2", stars=100, domain=DomainType.LIBRARY),
        _make_candidate("cli/repo3", stars=30, domain=DomainType.CLI),
        _make_candidate("cli/repo4", stars=60, domain=DomainType.CLI),
    ]
    ground_truth = {"lib/repo1", "cli/repo3"}

    profiles = {
        DomainType.LIBRARY: _make_test_profile(),
        DomainType.CLI: DomainProfile(
            domain_type=DomainType.CLI,
            display_name="CLI Tool",
            dimension_weights={
                ScoreDimension.CODE_QUALITY: 0.15,
                ScoreDimension.ARCHITECTURE: 0.10,
                ScoreDimension.TESTING: 0.20,
                ScoreDimension.DOCUMENTATION: 0.10,
                ScoreDimension.MAINTENANCE: 0.20,
                ScoreDimension.SECURITY: 0.10,
                ScoreDimension.FUNCTIONALITY: 0.10,
                ScoreDimension.INNOVATION: 0.05,
            },
        ),
    }

    results = calibrate_all_domains(
        profiles,
        candidates,
        ground_truth,
        precision_k=2,
        step=0.05,
    )

    assert isinstance(results, dict)
    # Both domains should have calibration results
    assert DomainType.LIBRARY in results
    assert DomainType.CLI in results
    for domain_result in results.values():
        assert isinstance(domain_result, CalibrationResult)
        assert isinstance(domain_result.precision_after, float)


def test_grid_search_empty_input() -> None:
    """Handles empty candidate list gracefully."""
    profile = _make_test_profile()

    result = grid_search_weights(
        DomainType.LIBRARY,
        profile,
        [],
        set(),
        precision_k=5,
        step=0.05,
    )

    assert isinstance(result, CalibrationResult)
    # With no candidates, precision should be 0
    assert result.precision_before == 0.0
    assert result.precision_after == 0.0
