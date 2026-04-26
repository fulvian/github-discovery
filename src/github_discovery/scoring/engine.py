"""Multi-dimensional scoring engine (Layer D).

Combines Gate 1 + Gate 2 + Gate 3 results into a composite
quality score with per-dimension breakdown.

Priority for each dimension:
1. Gate 3 (LLM deep assessment) — highest confidence
2. Gate 1+2 derived scores — medium confidence
3. Neutral default (0.5, confidence 0.0) — no data
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from github_discovery.config import ScoringSettings
from github_discovery.models.enums import ScoreDimension
from github_discovery.models.scoring import DomainProfile, ScoreResult
from github_discovery.scoring.confidence import ConfidenceCalculator
from github_discovery.scoring.profiles import ProfileRegistry
from github_discovery.scoring.types import DimensionScoreInfo, ScoringContext, ScoringInput
from github_discovery.scoring.value_score import ValueScoreCalculator

if TYPE_CHECKING:
    from github_discovery.models.assessment import DeepAssessmentResult
    from github_discovery.models.candidate import RepoCandidate
    from github_discovery.models.screening import ScreeningResult
    from github_discovery.scoring.feature_store import FeatureStore

logger = structlog.get_logger("github_discovery.scoring.engine")

# Dimension → (sub-score name from Gate 1/2, weight in derivation)
_DERIVATION_MAP: dict[ScoreDimension, list[tuple[str, float]]] = {
    ScoreDimension.CODE_QUALITY: [
        ("review_practice", 0.5),
        ("ci_cd", 0.3),
        ("dependency_quality", 0.2),
    ],
    ScoreDimension.ARCHITECTURE: [
        ("complexity", 0.7),
        ("ci_cd", 0.3),
    ],
    ScoreDimension.TESTING: [
        ("test_footprint", 0.7),
        ("ci_cd", 0.3),
    ],
    ScoreDimension.DOCUMENTATION: [
        ("hygiene", 0.6),
        ("review_practice", 0.4),
    ],
    ScoreDimension.MAINTENANCE: [
        ("maintenance", 0.4),
        ("release_discipline", 0.3),
        ("ci_cd", 0.2),
        ("hygiene", 0.1),
    ],
    ScoreDimension.SECURITY: [
        ("security_hygiene", 0.35),
        ("vulnerability", 0.25),
        ("secret_hygiene", 0.25),
        ("dependency_quality", 0.15),
    ],
    ScoreDimension.FUNCTIONALITY: [],
    ScoreDimension.INNOVATION: [],
}

_ALL_DIMENSIONS = list(ScoreDimension)


class ScoringEngine:
    """Multi-dimensional scoring engine (Layer D).

    Combines Gate 1 + Gate 2 + Gate 3 results into a composite
    quality score with per-dimension breakdown.

    Optionally backed by a FeatureStore for persistent caching — avoids
    expensive recomputation when the same repo at the same commit is
    scored again.

    Usage:
        engine = ScoringEngine()
        result = engine.score(candidate, screening, assessment)
    """

    def __init__(
        self,
        settings: ScoringSettings | None = None,
        store: FeatureStore | None = None,
    ) -> None:
        """Initialize ScoringEngine with optional settings and feature store.

        Args:
            settings: Scoring configuration. Uses defaults if None.
            store: Optional FeatureStore for caching ScoreResults.
                When provided, the engine checks the store before computing
                and writes results back after computing.
        """
        self._settings = settings or ScoringSettings()
        self._store = store
        self._registry = ProfileRegistry()
        self._confidence_calc = ConfidenceCalculator()
        self._value_calc = ValueScoreCalculator(self._settings)

    @property
    def feature_store(self) -> FeatureStore | None:
        """Return the backing FeatureStore, if configured."""
        return self._store

    def score(
        self,
        candidate: RepoCandidate,
        screening: ScreeningResult | None = None,
        assessment: DeepAssessmentResult | None = None,
        profile: DomainProfile | None = None,
    ) -> ScoreResult:
        """Score a single candidate.

        Args:
            candidate: Repo metadata (includes stars for ValueScore).
            screening: Gate 1+2 screening result (optional).
            assessment: Gate 3 deep assessment (optional, only for top %).
            profile: Domain profile for weighting (auto-detected if None).

        Returns:
            ScoreResult with composite quality_score, per-dimension scores,
            confidence, and value_score (computed field).
        """
        if profile is None:
            profile = self._registry.get(candidate.domain)

        dimension_infos = self._compute_dimension_scores(screening, assessment)
        raw_quality_score, coverage = self._apply_weights(dimension_infos, profile)
        # Penalize low-coverage scores conservatively (max 50% damping):
        # coverage 1.0 → no damping; coverage 0.6 → score *= 0.8
        quality_score = raw_quality_score * (0.5 + 0.5 * coverage)
        confidence = self._confidence_calc.compute(
            dimension_infos,
            screening,
            assessment,
        )

        dimension_scores = {dim: info.value for dim, info in dimension_infos.items()}

        gate1_total = self._extract_gate1_total(screening)
        gate2_total = self._extract_gate2_total(screening)

        return ScoreResult(
            full_name=candidate.full_name,
            commit_sha=candidate.commit_sha,
            domain=candidate.domain,
            quality_score=round(quality_score, 4),
            raw_quality_score=round(raw_quality_score, 4),
            coverage=round(coverage, 4),
            dimension_scores=dimension_scores,
            confidence=round(confidence, 4),
            stars=candidate.stars,
            gate1_total=gate1_total,
            gate2_total=gate2_total,
            gate3_available=assessment is not None,
        )

    async def score_cached(
        self,
        candidate: RepoCandidate,
        screening: ScreeningResult | None = None,
        assessment: DeepAssessmentResult | None = None,
        profile: DomainProfile | None = None,
    ) -> ScoreResult:
        """Score a single candidate with optional FeatureStore caching.

        When a FeatureStore is configured, checks the store for a cached
        result before computing. Stores the result after computing.

        This is the async counterpart to ``score()`` — use it when a
        FeatureStore is available to avoid redundant computation.

        Args:
            candidate: Repo metadata (includes stars for ValueScore).
            screening: Gate 1+2 screening result (optional).
            assessment: Gate 3 deep assessment (optional, only for top %).
            profile: Domain profile for weighting (auto-detected if None).

        Returns:
            ScoreResult — from cache if available, otherwise freshly computed.
        """
        if self._store is not None and candidate.commit_sha:
            cached = await self._store.get(
                candidate.full_name,
                candidate.commit_sha,
            )
            if cached is not None:
                logger.debug(
                    "scoring_cache_hit",
                    full_name=candidate.full_name,
                    commit_sha=candidate.commit_sha,
                )
                return cached

        result = self.score(candidate, screening, assessment, profile)

        if self._store is not None and candidate.commit_sha:
            await self._store.put(result)

        return result

    def score_batch(
        self,
        inputs: list[ScoringInput],
        profile: DomainProfile | None = None,
    ) -> list[ScoreResult]:
        """Score a batch of candidates.

        All candidates are scored with the same domain profile
        (or their own if profile is None).
        """
        return [
            self.score(
                inp.candidate,
                inp.screening,
                inp.assessment,
                profile,
            )
            for inp in inputs
        ]

    def score_from_context(self, context: ScoringContext) -> list[ScoreResult]:
        """Score all candidates in a ScoringContext, applying overrides.

        If ``context.domain_override`` is set, each candidate's domain is
        temporarily replaced so the correct profile is resolved.  If
        ``context.profile_override`` is set, that profile is used for every
        candidate regardless of domain.

        Args:
            context: ScoringContext with inputs and optional overrides.

        Returns:
            List of ScoreResult with overrides applied.
        """
        results: list[ScoreResult] = []
        for inp in context.inputs:
            candidate = inp.candidate

            # Apply domain override by creating a shallow copy
            if context.domain_override is not None:
                candidate = candidate.model_copy(
                    update={"domain": context.domain_override},
                )

            # profile_override takes precedence over auto-detected profile
            profile = context.profile_override

            results.append(
                self.score(
                    candidate,
                    inp.screening,
                    inp.assessment,
                    profile,
                ),
            )
        return results

    def _compute_dimension_scores(
        self,
        screening: ScreeningResult | None,
        assessment: DeepAssessmentResult | None,
    ) -> dict[ScoreDimension, DimensionScoreInfo]:
        """Compute per-dimension scores from available data.

        For each dimension:
        1. Gate 3 score available → use it (high confidence)
        2. No Gate 3 → derive from Gate 1+2 (lower confidence)
        3. No data → neutral 0.5, confidence 0.0
        """
        derived = self._derive_from_screening(screening)
        result: dict[ScoreDimension, DimensionScoreInfo] = {}

        for dim in _ALL_DIMENSIONS:
            # Check Gate 3 first
            if assessment is not None:
                dim_score = assessment.get_dimension_score(dim)
                if dim_score is not None:
                    result[dim] = DimensionScoreInfo(
                        dimension=dim,
                        value=dim_score.value,
                        confidence=dim_score.confidence,
                        source="gate3_llm",
                        contributing_signals=[f"gate3_{dim.value}"],
                    )
                    continue

            # Fall back to Gate 1+2 derived
            if dim in derived:
                result[dim] = DimensionScoreInfo(
                    dimension=dim,
                    value=derived[dim],
                    confidence=0.4,
                    source="gate12_derived",
                    contributing_signals=self._get_contributing_signals(dim),
                )
                continue

            # No data — neutral default
            result[dim] = DimensionScoreInfo(
                dimension=dim,
                value=0.5,
                confidence=0.0,
                source="default_neutral",
                contributing_signals=[],
            )

        return result

    def _derive_from_screening(
        self,
        screening: ScreeningResult | None,
    ) -> dict[ScoreDimension, float]:
        """Derive preliminary dimension scores from Gate 1+2.

        Maps sub-scores to dimensions using weighted composition.
        Returns empty for dimensions that can't be derived (FUNCTIONALITY, INNOVATION).
        """
        if screening is None:
            return {}

        sub_scores = self._collect_sub_scores(screening)
        result: dict[ScoreDimension, float] = {}

        for dim, mappings in _DERIVATION_MAP.items():
            if not mappings:
                continue
            total_weight = 0.0
            weighted_sum = 0.0
            for sub_name, weight in mappings:
                if sub_name in sub_scores:
                    weighted_sum += sub_scores[sub_name] * weight
                    total_weight += weight
            if total_weight > 0:
                result[dim] = weighted_sum / total_weight

        return result

    def _collect_sub_scores(self, screening: ScreeningResult) -> dict[str, float]:
        """Collect all sub-scores from screening result."""
        scores: dict[str, float] = {}
        if screening.gate1 is not None:
            scores["hygiene"] = screening.gate1.hygiene.value
            scores["maintenance"] = screening.gate1.maintenance.value
            scores["release_discipline"] = screening.gate1.release_discipline.value
            scores["review_practice"] = screening.gate1.review_practice.value
            scores["test_footprint"] = screening.gate1.test_footprint.value
            scores["ci_cd"] = screening.gate1.ci_cd.value
            scores["dependency_quality"] = screening.gate1.dependency_quality.value
        if screening.gate2 is not None:
            scores["security_hygiene"] = screening.gate2.security_hygiene.value
            scores["vulnerability"] = screening.gate2.vulnerability.value
            scores["complexity"] = screening.gate2.complexity.value
            scores["secret_hygiene"] = screening.gate2.secret_hygiene.value
        return scores

    def _apply_weights(
        self,
        dimension_scores: dict[ScoreDimension, DimensionScoreInfo],
        profile: DomainProfile,
    ) -> tuple[float, float]:
        """Apply domain-specific weights to compute composite quality_score.

        Dimensions with confidence 0.0 (no data / neutral default) are
        excluded from the weighted average. Their weight is redistributed
        proportionally to the dimensions that have actual data. This prevents
        phantom 0.5 defaults from inflating or deflating the composite score.

        Returns:
            Tuple of (raw_score, coverage) where coverage ∈ [0, 1] represents
            the fraction of profile weight backed by real data.
        """
        weighted_sum = 0.0
        total_weight_used = 0.0
        total_weight_possible = sum(profile.dimension_weights.values())  # ~1.0

        for dim, info in dimension_scores.items():
            weight = profile.dimension_weights.get(dim, 0.0)
            # Skip dimensions with no real data (confidence 0.0 = default_neutral)
            if info.confidence <= 0.0:
                continue
            weighted_sum += info.value * weight
            total_weight_used += weight

        if total_weight_used <= 0.0:
            return 0.0, 0.0

        raw_score = weighted_sum / total_weight_used
        coverage = total_weight_used / total_weight_possible if total_weight_possible > 0 else 0.0
        return raw_score, coverage

    def _get_contributing_signals(self, dim: ScoreDimension) -> list[str]:
        """Get the sub-score names that contribute to a dimension."""
        mappings = _DERIVATION_MAP.get(dim, [])
        return [name for name, _ in mappings]

    def _extract_gate1_total(self, screening: ScreeningResult | None) -> float:
        """Extract Gate 1 total from screening."""
        if screening is not None and screening.gate1 is not None:
            return screening.gate1.gate1_total
        return 0.0

    def _extract_gate2_total(self, screening: ScreeningResult | None) -> float:
        """Extract Gate 2 total from screening."""
        if screening is not None and screening.gate2 is not None:
            return screening.gate2.gate2_total
        return 0.0
