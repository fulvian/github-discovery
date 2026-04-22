"""Domain enumerations for GitHub Discovery.

Defines the core enums used across the scoring pipeline:
DomainType, GateLevel, ScoreDimension, DiscoveryChannel.
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
    """Scoring dimensions for repository evaluation."""

    CODE_QUALITY = "code_quality"
    ARCHITECTURE = "architecture"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    SECURITY = "security"
    MAINTENANCE = "maintenance"
    COMMUNITY = "community"
    NOVELTY = "novelty"


class DiscoveryChannel(StrEnum):
    """Discovery channels for candidate repository search."""

    SEARCH = "search"
    CODE_SEARCH = "code_search"
    DEPENDENCY = "dependency"
    REGISTRY = "registry"
    AWESOME_LIST = "awesome_list"
    SEED_EXPANSION = "seed_expansion"
