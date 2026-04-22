"""Tests for domain enumerations."""

from __future__ import annotations

from github_discovery.models.enums import (
    CandidateStatus,
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
            "backend",
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
    """Test ScoreDimension enum — aligned with Blueprint §7."""

    def test_exactly_8_dimensions(self) -> None:
        """All 8 scoring dimensions are defined."""
        assert len(ScoreDimension) == 8

    def test_code_quality(self) -> None:
        assert ScoreDimension.CODE_QUALITY == "code_quality"

    def test_architecture(self) -> None:
        assert ScoreDimension.ARCHITECTURE == "architecture"

    def test_testing(self) -> None:
        assert ScoreDimension.TESTING == "testing"

    def test_documentation(self) -> None:
        assert ScoreDimension.DOCUMENTATION == "documentation"

    def test_security(self) -> None:
        assert ScoreDimension.SECURITY == "security"

    def test_maintenance(self) -> None:
        assert ScoreDimension.MAINTENANCE == "maintenance"

    def test_functionality(self) -> None:
        """ScoreDimension.FUNCTIONALITY replaces old COMMUNITY."""
        assert ScoreDimension.FUNCTIONALITY == "functionality"

    def test_innovation(self) -> None:
        """ScoreDimension.INNOVATION replaces old NOVELTY."""
        assert ScoreDimension.INNOVATION == "innovation"


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


class TestCandidateStatus:
    """Test CandidateStatus enum — tracks pipeline state."""

    def test_all_statuses_defined(self) -> None:
        """All expected candidate statuses are defined."""
        assert len(CandidateStatus) == 11

    def test_discovery_statuses(self) -> None:
        assert CandidateStatus.DISCOVERED == "discovered"

    def test_screening_statuses(self) -> None:
        assert CandidateStatus.SCREENING_GATE1 == "screening_gate1"
        assert CandidateStatus.SCREENING_GATE2 == "screening_gate2"
        assert CandidateStatus.GATE1_PASSED == "gate1_passed"
        assert CandidateStatus.GATE1_FAILED == "gate1_failed"
        assert CandidateStatus.GATE2_PASSED == "gate2_passed"
        assert CandidateStatus.GATE2_FAILED == "gate2_failed"

    def test_assessment_statuses(self) -> None:
        assert CandidateStatus.ASSESSING == "assessing"
        assert CandidateStatus.ASSESSED == "assessed"

    def test_final_statuses(self) -> None:
        assert CandidateStatus.RANKED == "ranked"
        assert CandidateStatus.EXCLUDED == "excluded"
