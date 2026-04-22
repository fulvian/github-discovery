"""Domain enumerations for GitHub Discovery.

Defines the core enums used across the scoring pipeline:
DomainType, GateLevel, ScoreDimension, DiscoveryChannel, CandidateStatus.
"""

from __future__ import annotations

from enum import StrEnum


class DomainType(StrEnum):
    """Repository domain types for domain-specific scoring."""

    CLI = "cli"
    WEB_FRAMEWORK = "web_framework"
    DATA_TOOL = "data_tool"
    LIBRARY = "library"
    ML_LIB = "ml_lib"
    DEVOPS_TOOL = "devops_tool"
    SECURITY_TOOL = "security_tool"
    LANG_TOOL = "lang_tool"
    TEST_TOOL = "test_tool"
    DOC_TOOL = "doc_tool"
    OTHER = "other"


class GateLevel(StrEnum):
    """Pipeline gate levels."""

    DISCOVERY = "0"
    METADATA = "1"
    STATIC_SECURITY = "2"
    DEEP_ASSESSMENT = "3"


class ScoreDimension(StrEnum):
    """Scoring dimensions for repository evaluation.

    Aligned with Blueprint §7 — 8 evaluation dimensions:
    1. Code Quality (20% default)
    2. Architecture & Modularity (15%)
    3. Testability & Verification (15%)
    4. Documentation & Developer Experience (10%)
    5. Maintenance & Project Operations (15%)
    6. Security & Supply Chain Hygiene (10%)
    7. Functional Completeness (10%)
    8. Innovation & Distinctiveness (5%)
    """

    CODE_QUALITY = "code_quality"
    ARCHITECTURE = "architecture"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    SECURITY = "security"
    MAINTENANCE = "maintenance"
    FUNCTIONALITY = "functionality"
    INNOVATION = "innovation"


class DiscoveryChannel(StrEnum):
    """Discovery channels for candidate repository search."""

    SEARCH = "search"
    CODE_SEARCH = "code_search"
    DEPENDENCY = "dependency"
    REGISTRY = "registry"
    AWESOME_LIST = "awesome_list"
    SEED_EXPANSION = "seed_expansion"


class CandidateStatus(StrEnum):
    """Status of a repo candidate through the pipeline."""

    DISCOVERED = "discovered"
    SCREENING_GATE1 = "screening_gate1"
    SCREENING_GATE2 = "screening_gate2"
    GATE1_PASSED = "gate1_passed"
    GATE1_FAILED = "gate1_failed"
    GATE2_PASSED = "gate2_passed"
    GATE2_FAILED = "gate2_failed"
    ASSESSING = "assessing"
    ASSESSED = "assessed"
    RANKED = "ranked"
    EXCLUDED = "excluded"
