"""Weight calibration for domain-specific scoring profiles.

Provides grid search over dimension weights to find optimal
weight profiles that maximize precision@k for each domain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

from github_discovery.models.enums import DomainType, ScoreDimension
from github_discovery.models.scoring import DomainProfile  # noqa: TC001

if TYPE_CHECKING:
    from github_discovery.models.candidate import RepoCandidate
    from github_discovery.models.scoring import RankedRepo

logger = structlog.get_logger("github_discovery.feasibility.calibration")

_NORMALIZATION_TOLERANCE = 0.01
_GRID_RANGE_MULTIPLIER = 3
_DEFAULT_DIMENSION_VALUE = 0.5
_LOW_DESCRIPTION_PENALTY = 0.3


@dataclass
class CalibrationResult:
    """Result of weight calibration for a single domain.

    Attributes:
        domain: Domain that was calibrated.
        original_weights: Weights before calibration.
        calibrated_weights: Weights after calibration.
        precision_before: Precision@k with original weights.
        precision_after: Precision@k with calibrated weights.
        improvement: Relative improvement in precision.
        best_params: Best weight parameters found.
    """

    domain: DomainType
    original_weights: dict[ScoreDimension, float]
    calibrated_weights: dict[ScoreDimension, float]
    precision_before: float
    precision_after: float
    improvement: float
    best_params: dict[str, float] = field(default_factory=dict)


def grid_search_weights(
    domain: DomainType,
    base_profile: DomainProfile,
    candidates: list[RepoCandidate],
    ground_truth: set[str],
    *,
    precision_k: int = 10,
    step: float = 0.05,
) -> CalibrationResult:
    """Grid search over dimension weights for a domain.

    Varies each dimension weight by +/- step in [0.0, 1.0] range,
    normalizes weights to sum to 1.0, and evaluates precision@k
    for each configuration. Iterates dimensions one at a time
    (not full combinatorial) for tractability.

    Args:
        domain: Domain to calibrate.
        base_profile: Starting domain profile with base weights.
        candidates: Candidate repos with scoring data.
        ground_truth: Set of relevant repo full_names.
        precision_k: K for precision@k evaluation.
        step: Grid step size for weight variation.

    Returns:
        CalibrationResult with best weights and improvement metrics.
    """
    original_weights = dict(base_profile.dimension_weights)

    # Compute baseline precision
    baseline_ranked = _rank_with_weights(candidates, original_weights, domain)
    precision_before = _compute_precision(baseline_ranked, ground_truth, k=precision_k)

    # Track best configuration
    best_weights = dict(original_weights)
    best_precision = precision_before

    # Grid search: vary one dimension at a time
    for dim in ScoreDimension:
        original_value = original_weights.get(dim, 0.0)
        if original_value <= 0.0:
            continue

        variations = _generate_weight_variations(original_value, step)

        for variation in variations:
            modified = dict(best_weights)
            modified[dim] = variation

            normalized = _normalize_weights(modified)
            if normalized is None:
                continue

            ranked = _rank_with_weights(candidates, normalized, domain)
            precision = _compute_precision(ranked, ground_truth, k=precision_k)

            if precision > best_precision:
                best_precision = precision
                best_weights = normalized

    # Compute improvement
    improvement = 0.0
    if precision_before > 0.0:
        improvement = (best_precision - precision_before) / precision_before
    elif best_precision > 0.0:
        improvement = float("inf")

    return CalibrationResult(
        domain=domain,
        original_weights=dict(original_weights),
        calibrated_weights=best_weights,
        precision_before=round(precision_before, 4),
        precision_after=round(best_precision, 4),
        improvement=round(improvement, 4),
        best_params={dim.value: w for dim, w in best_weights.items()},
    )


def calibrate_all_domains(
    base_profiles: dict[DomainType, DomainProfile],
    candidates: list[RepoCandidate],
    ground_truth: set[str],
    *,
    precision_k: int = 10,
    step: float = 0.05,
) -> dict[DomainType, CalibrationResult]:
    """Calibrate weights for all domains with available profiles.

    Args:
        base_profiles: Map of domain type to domain profile.
        candidates: Candidate repos with scoring data.
        ground_truth: Set of relevant repo full_names.
        precision_k: K for precision@k evaluation.
        step: Grid step size for weight variation.

    Returns:
        Map of domain type to CalibrationResult.
    """
    results: dict[DomainType, CalibrationResult] = {}

    for domain, profile in base_profiles.items():
        domain_candidates = [c for c in candidates if c.domain == domain]
        if not domain_candidates:
            logger.debug(
                "calibration_skip_no_candidates",
                domain=domain.value,
            )
            continue

        results[domain] = grid_search_weights(
            domain,
            profile,
            domain_candidates,
            ground_truth,
            precision_k=precision_k,
            step=step,
        )

        logger.info(
            "calibration_domain_complete",
            domain=domain.value,
            precision_before=results[domain].precision_before,
            precision_after=results[domain].precision_after,
            improvement=results[domain].improvement,
        )

    return results


def _generate_weight_variations(
    original: float,
    step: float,
) -> list[float]:
    """Generate weight variations around original value.

    Produces values from max(0, original - 3*step) to
    min(1, original + 3*step) in increments of step.
    """
    lower = max(0.0, original - _GRID_RANGE_MULTIPLIER * step)
    upper = min(1.0, original + _GRID_RANGE_MULTIPLIER * step)

    variations: list[float] = []
    current = lower
    while current <= upper + _NORMALIZATION_TOLERANCE:
        variations.append(round(current, 4))
        current += step

    return variations


def _normalize_weights(
    weights: dict[ScoreDimension, float],
) -> dict[ScoreDimension, float] | None:
    """Normalize weights to sum to 1.0.

    Returns None if total is zero (no valid weights).
    """
    total = sum(weights.values())
    if total < _NORMALIZATION_TOLERANCE:
        return None

    return {dim: w / total for dim, w in weights.items()}


def _rank_with_weights(
    candidates: list[RepoCandidate],
    weights: dict[ScoreDimension, float],
    domain: DomainType,
) -> list[RankedRepo]:
    """Rank candidates using specified weights.

    Computes a weighted quality score from each candidate's
    dimension scores. For candidates without explicit dimension
    scores, uses heuristic estimates from metadata.
    """
    from github_discovery.models.scoring import RankedRepo, ScoreResult  # noqa: PLC0415

    scored: list[tuple[float, RepoCandidate]] = []
    for candidate in candidates:
        quality = _compute_weighted_quality(candidate, weights)
        scored.append((quality, candidate))

    scored.sort(key=lambda x: x[0], reverse=True)

    ranked: list[RankedRepo] = []
    for i, (quality, candidate) in enumerate(scored, start=1):
        score_result = ScoreResult(
            full_name=candidate.full_name,
            commit_sha=candidate.commit_sha,
            domain=candidate.domain,
            quality_score=quality,
            stars=candidate.stars,
        )
        ranked.append(
            RankedRepo(
                rank=i,
                full_name=candidate.full_name,
                domain=domain,
                score_result=score_result,
            ),
        )

    return ranked


def _compute_weighted_quality(
    candidate: RepoCandidate,
    weights: dict[ScoreDimension, float],
) -> float:
    """Compute weighted quality score for a candidate.

    Uses dimension scores from the candidate's metadata when
    available. Falls back to heuristic estimates otherwise.
    """
    weighted_sum = 0.0
    total_weight = 0.0

    for dim, weight in weights.items():
        dim_value = _estimate_dimension_value(candidate, dim)
        weighted_sum += dim_value * weight
        total_weight += weight

    if total_weight <= 0:
        return candidate.discovery_score if candidate.discovery_score > 0.0 else 0.5

    return weighted_sum / total_weight


def _estimate_dimension_value(
    candidate: RepoCandidate,
    dimension: ScoreDimension,
) -> float:
    """Estimate a dimension score from candidate metadata.

    Provides rough heuristic estimates when actual dimension
    scores from screening/assessment are not available.
    """
    if dimension == ScoreDimension.DOCUMENTATION:
        return _DEFAULT_DIMENSION_VALUE if candidate.description else _LOW_DESCRIPTION_PENALTY
    return _DEFAULT_DIMENSION_VALUE


def _compute_precision(
    ranked: list[RankedRepo],
    ground_truth: set[str],
    *,
    k: int,
) -> float:
    """Compute precision@k for a ranked list."""
    if k <= 0 or not ranked or not ground_truth:
        return 0.0

    top_k = ranked[:k]
    relevant = sum(1 for r in top_k if r.full_name in ground_truth)
    return relevant / k
