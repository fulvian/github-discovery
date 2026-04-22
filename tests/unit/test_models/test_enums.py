"""Tests for domain enumerations."""

from __future__ import annotations

from github_discovery.models.enums import (
    DiscoveryChannel,
    DomainType,
    GateLevel,
    ScoreDimension,
)


class TestDomainType:
    """Test DomainType enum."""

    def test_all_domain_types_defined(self) -> None:
        """All expected domain types are defined."""
        expected = [
            "cli",
            "web_framework",
            "data_tool",
            "library",
            "ml_lib",
            "devops_tool",
            "security_tool",
            "lang_tool",
            "test_tool",
            "doc_tool",
            "other",
        ]
        values = [dt.value for dt in DomainType]
        assert set(values) == set(expected)

    def test_domain_type_string_enum(self) -> None:
        """DomainType is a string enum."""
        assert DomainType.CLI == "cli"
        assert DomainType.LIBRARY == "library"


class TestGateLevel:
    """Test GateLevel enum."""

    def test_all_gate_levels(self) -> None:
        """All gate levels are defined."""
        assert GateLevel.DISCOVERY == "0"
        assert GateLevel.METADATA == "1"
        assert GateLevel.STATIC_SECURITY == "2"
        assert GateLevel.DEEP_ASSESSMENT == "3"


class TestScoreDimension:
    """Test ScoreDimension enum."""

    def test_all_dimensions_defined(self) -> None:
        """All 8 scoring dimensions are defined."""
        assert len(ScoreDimension) == 8
        assert ScoreDimension.CODE_QUALITY == "code_quality"
        assert ScoreDimension.ARCHITECTURE == "architecture"
        assert ScoreDimension.TESTING == "testing"
        assert ScoreDimension.DOCUMENTATION == "documentation"
        assert ScoreDimension.SECURITY == "security"
        assert ScoreDimension.MAINTENANCE == "maintenance"
        assert ScoreDimension.COMMUNITY == "community"
        assert ScoreDimension.NOVELTY == "novelty"


class TestDiscoveryChannel:
    """Test DiscoveryChannel enum."""

    def test_all_channels_defined(self) -> None:
        """All discovery channels are defined."""
        assert len(DiscoveryChannel) == 6
        assert DiscoveryChannel.SEARCH == "search"
        assert DiscoveryChannel.CODE_SEARCH == "code_search"
        assert DiscoveryChannel.DEPENDENCY == "dependency"
        assert DiscoveryChannel.REGISTRY == "registry"
        assert DiscoveryChannel.AWESOME_LIST == "awesome_list"
        assert DiscoveryChannel.SEED_EXPANSION == "seed_expansion"
