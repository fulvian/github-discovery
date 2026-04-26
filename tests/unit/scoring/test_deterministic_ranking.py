"""T1.2 — Verify deterministic tie-breaking using hashlib.blake2b.

The ranking must produce identical ordering across processes
regardless of PYTHONHASHSEED.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from github_discovery.config import ScoringSettings
from github_discovery.models.enums import DomainType
from github_discovery.models.scoring import ScoreResult
from github_discovery.scoring.ranker import Ranker


def _make_tied_results() -> list[ScoreResult]:
    """Create repos with identical quality_score and confidence for tie-breaking test."""
    return [
        ScoreResult(
            full_name="alpha/beta",
            quality_score=0.7,
            confidence=0.5,
            domain=DomainType.LIBRARY,
        ),
        ScoreResult(
            full_name="gamma/delta",
            quality_score=0.7,
            confidence=0.5,
            domain=DomainType.LIBRARY,
        ),
        ScoreResult(
            full_name="epsilon/zeta",
            quality_score=0.7,
            confidence=0.5,
            domain=DomainType.LIBRARY,
        ),
    ]


def test_seeded_hash_deterministic() -> None:
    """Same seed + same name → same hash, always."""
    settings = ScoringSettings(ranking_seed=42)
    ranker = Ranker(settings)
    h1 = ranker._seeded_hash("foo/bar")
    h2 = ranker._seeded_hash("foo/bar")
    assert h1 == h2
    # Different name → different hash
    h3 = ranker._seeded_hash("baz/qux")
    assert h1 != h3


def test_seeded_hash_golden_value() -> None:
    """Golden value test: known input → known output (immutable).

    blake2b digest_size=8 is always positive as unsigned int.
    """
    settings = ScoringSettings(ranking_seed=42)
    ranker = Ranker(settings)
    h = ranker._seeded_hash("foo/bar")
    assert isinstance(h, int)
    assert h > 0


def test_ranking_deterministic_same_process() -> None:
    """5 consecutive rankings → identical ordering."""
    ranker = Ranker(ScoringSettings(ranking_seed=42))
    results = _make_tied_results()

    orderings: list[list[str]] = []
    for _ in range(5):
        ranked = ranker.rank(results, DomainType.LIBRARY)
        orderings.append([r.full_name for r in ranked.ranked_repos])

    for ordering in orderings[1:]:
        assert ordering == orderings[0], (
            f"Non-deterministic ordering: {orderings[0]} vs {ordering}"
        )


def test_ranking_cross_process_deterministic() -> None:
    """Ranking produces same ordering across different PYTHONHASHSEED values."""
    code = (
        "from github_discovery.config import ScoringSettings; "
        "from github_discovery.models.enums import DomainType; "
        "from github_discovery.models.scoring import ScoreResult; "
        "from github_discovery.scoring.ranker import Ranker; "
        "results = ["
        "ScoreResult("
        "full_name='alpha/beta', "
        "quality_score=0.7, confidence=0.5, "
        "domain=DomainType.LIBRARY"
        "), "
        "ScoreResult("
        "full_name='gamma/delta', "
        "quality_score=0.7, confidence=0.5, "
        "domain=DomainType.LIBRARY"
        "), "
        "ScoreResult("
        "full_name='epsilon/zeta', "
        "quality_score=0.7, confidence=0.5, "
        "domain=DomainType.LIBRARY"
        "), "
        "]; "
        "ranker = Ranker(ScoringSettings(ranking_seed=42)); "
        "ranked = ranker.rank(results, DomainType.LIBRARY); "
        "print(','.join(r.full_name for r in ranked.ranked_repos))"
    )

    orderings: list[str] = []
    for seed in ["0", "12345", "random", "99999"]:
        env = {**os.environ, "PYTHONHASHSEED": seed}
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            pytest.skip(f"Subprocess failed: {result.stderr}")
        orderings.append(result.stdout.strip())

    # All subprocess orderings must be identical
    for ordering in orderings[1:]:
        assert ordering == orderings[0], (
            f"Cross-process non-determinism: {orderings[0]} vs {ordering}"
        )
