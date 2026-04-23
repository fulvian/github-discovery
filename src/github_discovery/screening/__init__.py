"""Lightweight quality screening (Layer B) — Gate 1 and Gate 2.

Gate 1: Metadata screening (zero LLM cost).
Gate 2: Static/security screening (zero or low cost).
Hard rule (Blueprint §16.5): no Gate 3 without Gate 1 + Gate 2 pass.
"""

from __future__ import annotations

from github_discovery.screening.ci_cd import CiCdDetector
from github_discovery.screening.complexity import ComplexityAnalyzer
from github_discovery.screening.dependency_quality import DependencyQualityScorer
from github_discovery.screening.gate1_metadata import Gate1MetadataScreener
from github_discovery.screening.gate2_static import Gate2StaticScreener
from github_discovery.screening.hygiene import HygieneChecker
from github_discovery.screening.maintenance import MaintenanceAnalyzer
from github_discovery.screening.orchestrator import ScreeningOrchestrator
from github_discovery.screening.osv_adapter import OsvAdapter
from github_discovery.screening.practices import PracticesScorer
from github_discovery.screening.release_discipline import ReleaseDisciplineScorer
from github_discovery.screening.scorecard_adapter import ScorecardAdapter
from github_discovery.screening.secrets_check import SecretsChecker
from github_discovery.screening.subprocess_runner import SubprocessRunner
from github_discovery.screening.test_footprint import TestFootprintAnalyzer
from github_discovery.screening.types import RepoContext, ScreeningContext, SubprocessResult

__all__ = [
    "CiCdDetector",
    "ComplexityAnalyzer",
    "DependencyQualityScorer",
    "Gate1MetadataScreener",
    "Gate2StaticScreener",
    "HygieneChecker",
    "MaintenanceAnalyzer",
    "OsvAdapter",
    "PracticesScorer",
    "ReleaseDisciplineScorer",
    "RepoContext",
    "ScorecardAdapter",
    "ScreeningContext",
    "ScreeningOrchestrator",
    "SecretsChecker",
    "SubprocessResult",
    "SubprocessRunner",
    "TestFootprintAnalyzer",
]
