"""T1.1 — Verify hidden gem detection consistency between ScoreResult and ValueScoreCalculator.

Both must use ScoringSettings as single source of truth.
"""

from __future__ import annotations

import pytest

from github_discovery.config import ScoringSettings
from github_discovery.models.scoring import ScoreResult
from github_discovery.scoring.value_score import ValueScoreCalculator

# Deterministic boundary + edge cases covering all quadrants of
# (below/above quality threshold) x (below/above star threshold).
_HG_CASES: list[tuple[float, int]] = [
    (0.75, 10),
    (0.55, 300),
    (0.7, 499),
    (0.7, 500),
    (0.69, 80),
    (0.3, 5),
    (0.9, 0),
    (0.9, 10000),
    (0.71, 499),
    (0.7, 501),
    # Systematic grid for robustness
    *[(q / 100, s) for q in range(0, 101, 10) for s in range(0, 5001, 500)],
]


@pytest.mark.parametrize(
    "quality, stars",
    _HG_CASES,
)
def test_hidden_gem_consistency(quality: float, stars: int) -> None:
    """ScoreResult.is_hidden_gem must match ValueScoreCalculator.is_hidden_gem."""
    settings = ScoringSettings()
    sr = ScoreResult(full_name="test/repo", quality_score=quality, stars=stars)
    calc = ValueScoreCalculator(settings)
    calc_result, _reason = calc.is_hidden_gem(quality, stars, quality)
    assert sr.is_hidden_gem == calc_result, (
        f"Mismatch at quality={quality:.4f}, stars={stars}: "
        f"ScoreResult={sr.is_hidden_gem}, Calculator={calc_result}"
    )


def test_no_hidden_gem_constants_in_models() -> None:
    """Verify _HIDDEN_GEM_* constants removed from models/scoring.py."""
    import github_discovery.models.scoring as scoring_module

    assert not hasattr(scoring_module, "_HIDDEN_GEM_MAX_STARS"), (
        "_HIDDEN_GEM_MAX_STARS should not exist in models/scoring.py"
    )
    assert not hasattr(scoring_module, "_HIDDEN_GEM_MIN_QUALITY"), (
        "_HIDDEN_GEM_MIN_QUALITY should not exist in models/scoring.py"
    )
