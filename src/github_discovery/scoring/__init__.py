"""GitHub Discovery scoring module (Layer D).

Provides scoring, ranking, and explainability for repository quality assessment.

Key components:
- ScoringEngine: Multi-dimensional scoring combining Gate 1+2+3 results
- Ranker: Intra-domain ranking with anti-star bias
- ValueScoreCalculator: Anti-star bias value score formula
- ConfidenceCalculator: Confidence scoring based on data completeness
- ProfileRegistry: Domain-specific weight profiles
- CrossDomainGuard: Cross-domain comparison with warnings
- ExplainabilityGenerator: Human-readable score explanations
- FeatureStore: SQLite-backed score caching with TTL
"""

from __future__ import annotations

from github_discovery.scoring.confidence import ConfidenceCalculator
from github_discovery.scoring.cross_domain import CrossDomainGuard
from github_discovery.scoring.engine import ScoringEngine
from github_discovery.scoring.explainability import ExplainabilityGenerator
from github_discovery.scoring.feature_store import FeatureStore
from github_discovery.scoring.profiles import ProfileRegistry, validate_profile
from github_discovery.scoring.ranker import Ranker
from github_discovery.scoring.types import (
    CrossDomainComparison,
    DimensionScoreInfo,
    FeatureStoreStats,
    NormalizedScore,
    RankingResult,
    ScoringContext,
    ScoringInput,
)
from github_discovery.scoring.value_score import ValueScoreCalculator

__all__ = [
    "ConfidenceCalculator",
    "CrossDomainComparison",
    "CrossDomainGuard",
    "DimensionScoreInfo",
    "ExplainabilityGenerator",
    "FeatureStore",
    "FeatureStoreStats",
    "NormalizedScore",
    "ProfileRegistry",
    "Ranker",
    "RankingResult",
    "ScoringContext",
    "ScoringEngine",
    "ScoringInput",
    "ValueScoreCalculator",
    "validate_profile",
]
