"""Tests for Wave 5 tasks: T5.1 per-profile derivation, T5.2 gate thresholds, T5.3 YAML loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DomainType, GateLevel, ScoreDimension
from github_discovery.models.scoring import DomainProfile
from github_discovery.scoring.engine import ScoringEngine
from github_discovery.scoring.profiles import ProfileRegistry


# --- T5.1: Per-DomainProfile derivation_map ---


class TestPerProfileDerivationMap:
    """Tests for per-profile derivation map (T5.1)."""

    def test_profile_with_custom_derivation_map(self) -> None:
        """Custom derivation_map on DomainProfile overrides engine default."""
        profile = DomainProfile(
            domain_type=DomainType.ML_LIB,
            display_name="Custom ML",
            dimension_weights={
                ScoreDimension.CODE_QUALITY: 0.10,
                ScoreDimension.ARCHITECTURE: 0.10,
                ScoreDimension.TESTING: 0.10,
                ScoreDimension.DOCUMENTATION: 0.10,
                ScoreDimension.MAINTENANCE: 0.15,
                ScoreDimension.SECURITY: 0.05,
                ScoreDimension.FUNCTIONALITY: 0.25,
                ScoreDimension.INNOVATION: 0.15,
            },
            derivation_map={
                "code_quality": [
                    ["complexity", 0.5],
                    ["test_footprint", 0.5],
                ],
            },
        )
        assert profile.derivation_map is not None
        assert "code_quality" in profile.derivation_map

    def test_profile_without_derivation_map_uses_default(self) -> None:
        """Profile without derivation_map returns None (engine uses default)."""
        profile = DomainProfile(
            domain_type=DomainType.LIBRARY,
            display_name="Test",
            dimension_weights={dim: 0.125 for dim in ScoreDimension},
        )
        assert profile.derivation_map is None

    def test_engine_resolves_custom_derivation(self) -> None:
        """ScoringEngine._resolve_derivation_map uses profile derivation_map."""
        engine = ScoringEngine()
        profile = DomainProfile(
            domain_type=DomainType.LIBRARY,
            display_name="Custom",
            dimension_weights={dim: 0.125 for dim in ScoreDimension},
            derivation_map={
                "testing": [
                    ["test_footprint", 1.0],
                ],
            },
        )
        resolved = engine._resolve_derivation_map(profile)
        # Custom mapping for TESTING: only test_footprint
        assert resolved[ScoreDimension.TESTING] == [("test_footprint", 1.0)]
        # Other dimensions fall through to default
        assert ScoreDimension.CODE_QUALITY in resolved

    def test_engine_resolves_default_when_no_profile(self) -> None:
        """ScoringEngine._resolve_derivation_map falls back to default."""
        engine = ScoringEngine()
        resolved = engine._resolve_derivation_map(None)
        # Should be the module-level _DERIVATION_MAP
        assert ScoreDimension.CODE_QUALITY in resolved
        assert ScoreDimension.ARCHITECTURE in resolved
        assert resolved[ScoreDimension.ARCHITECTURE] == []

    def test_engine_derives_with_custom_map(self) -> None:
        """ScoringEngine._derive_from_screening uses custom derivation_map."""
        from github_discovery.models.screening import (
            HygieneScore,
            MetadataScreenResult,
            ScreeningResult,
            TestFootprintScore,
        )

        engine = ScoringEngine()
        profile = DomainProfile(
            domain_type=DomainType.LIBRARY,
            display_name="Custom",
            dimension_weights={dim: 0.125 for dim in ScoreDimension},
            derivation_map={
                "code_quality": [
                    ["test_footprint", 1.0],
                ],
            },
        )

        gate1 = MetadataScreenResult(
            full_name="test/repo",
            test_footprint=TestFootprintScore(value=0.8, weight=1.0),
            hygiene=HygieneScore(value=0.5, weight=1.0),
        )
        screening = ScreeningResult(
            full_name="test/repo",
            gate1=gate1,
        )

        derived = engine._derive_from_screening(screening, profile)
        # With custom map: CODE_QUALITY should be 0.8 (test_footprint only)
        assert ScoreDimension.CODE_QUALITY in derived
        assert abs(derived[ScoreDimension.CODE_QUALITY] - 0.8) < 0.01

    def test_derivation_map_ignores_unknown_dimension(self) -> None:
        """Unknown dimension names in derivation_map are silently ignored."""
        engine = ScoringEngine()
        profile = DomainProfile(
            domain_type=DomainType.LIBRARY,
            display_name="Custom",
            dimension_weights={dim: 0.125 for dim in ScoreDimension},
            derivation_map={
                "nonexistent_dimension": [
                    ["test_footprint", 1.0],
                ],
            },
        )
        resolved = engine._resolve_derivation_map(profile)
        # Unknown dimension should not appear as a key — only valid dimensions
        assert all(isinstance(dim, ScoreDimension) for dim in resolved)
        assert "nonexistent_dimension" not in {d.value for d in resolved}


# --- T5.2: Per-DomainProfile gate_thresholds ---


class TestPerProfileGateThresholds:
    """Tests for per-profile gate thresholds (T5.2)."""

    def test_all_profiles_have_gate_thresholds(self) -> None:
        """All built-in profiles have explicit gate_thresholds."""
        registry = ProfileRegistry()
        for domain in DomainType:
            profile = registry.get(domain)
            assert "gate1" in profile.gate_thresholds, (
                f"Profile {domain.value} missing gate1 threshold"
            )
            assert "gate2" in profile.gate_thresholds, (
                f"Profile {domain.value} missing gate2 threshold"
            )

    def test_security_tool_has_stricter_thresholds(self) -> None:
        """SECURITY_TOOL profile has stricter thresholds than others."""
        registry = ProfileRegistry()
        sec = registry.get(DomainType.SECURITY_TOOL)
        lib = registry.get(DomainType.LIBRARY)
        assert sec.gate_thresholds["gate1"] > lib.gate_thresholds["gate1"]
        assert sec.gate_thresholds["gate2"] > lib.gate_thresholds["gate2"]

    def test_library_profile_thresholds_match_domain_dict(self) -> None:
        """LIBRARY profile gate_thresholds match old _DOMAIN_THRESHOLDS values."""
        from github_discovery.models.scoring import LIBRARY_PROFILE

        assert LIBRARY_PROFILE.gate_thresholds["gate1"] == 0.5
        assert LIBRARY_PROFILE.gate_thresholds["gate2"] == 0.6

    def test_ml_lib_profile_thresholds(self) -> None:
        """ML_LIB profile has lenient thresholds."""
        registry = ProfileRegistry()
        ml = registry.get(DomainType.ML_LIB)
        assert ml.gate_thresholds["gate1"] == 0.4
        assert ml.gate_thresholds["gate2"] == 0.5


# --- T5.3: Custom profiles YAML/TOML loading ---


class TestCustomProfilesLoading:
    """Tests for YAML/TOML profile loading (T5.3)."""

    def _write_yaml(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "profiles.yaml"
        p.write_text(content, encoding="utf-8")
        return p

    def _write_toml(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "profiles.toml"
        p.write_text(content, encoding="utf-8")
        return p

    def test_load_from_yaml(self, tmp_path: Path) -> None:
        """Load custom profiles from YAML file."""
        yaml_content = """
profiles:
  - domain_type: ML_LIB
    display_name: "Custom ML Profile"
    description: "ML with emphasis on testing"
    dimension_weights:
      code_quality: 0.10
      architecture: 0.10
      testing: 0.25
      documentation: 0.10
      maintenance: 0.15
      security: 0.05
      functionality: 0.15
      innovation: 0.10
    gate_thresholds:
      gate1: 0.3
      gate2: 0.4
"""
        path = self._write_yaml(tmp_path, yaml_content)
        registry = ProfileRegistry()
        count = registry.load_from_yaml(path)
        assert count == 1
        profile = registry.get(DomainType.ML_LIB)
        assert profile.display_name == "Custom ML Profile"
        assert profile.gate_thresholds["gate1"] == 0.3

    def test_load_from_toml(self, tmp_path: Path) -> None:
        """Load custom profiles from TOML file."""
        toml_content = """
[[profiles]]
domain_type = "CLI"
display_name = "Custom CLI"
dimension_weights = {code_quality = 0.15, architecture = 0.10, testing = 0.20, documentation = 0.10, maintenance = 0.20, security = 0.10, functionality = 0.10, innovation = 0.05}

[profiles.gate_thresholds]
gate1 = 0.45
gate2 = 0.55
"""
        path = self._write_toml(tmp_path, toml_content)
        registry = ProfileRegistry()
        count = registry.load_from_toml(path)
        assert count == 1
        profile = registry.get(DomainType.CLI)
        assert profile.display_name == "Custom CLI"
        assert profile.gate_thresholds["gate1"] == 0.45

    def test_load_custom_profiles_auto_detects_yaml(self, tmp_path: Path) -> None:
        """load_custom_profiles detects YAML from extension."""
        yaml_content = """
profiles:
  - domain_type: LIBRARY
    display_name: "Custom Lib"
    dimension_weights:
      code_quality: 0.20
      architecture: 0.15
      testing: 0.15
      documentation: 0.15
      maintenance: 0.15
      security: 0.10
      functionality: 0.05
      innovation: 0.05
"""
        path = self._write_yaml(tmp_path, yaml_content)
        registry = ProfileRegistry()
        count = registry.load_custom_profiles(path)
        assert count == 1

    def test_load_custom_profiles_rejects_unknown_extension(self, tmp_path: Path) -> None:
        """load_custom_profiles raises ValueError for unknown extensions."""
        p = tmp_path / "profiles.json"
        p.write_text("{}", encoding="utf-8")
        registry = ProfileRegistry()
        with pytest.raises(ValueError, match="Unsupported"):
            registry.load_custom_profiles(p)

    def test_load_custom_profiles_file_not_found(self, tmp_path: Path) -> None:
        """load_custom_profiles raises FileNotFoundError for missing files."""
        registry = ProfileRegistry()
        with pytest.raises(FileNotFoundError):
            registry.load_custom_profiles(tmp_path / "nonexistent.yaml")

    def test_invalid_weights_skipped(self, tmp_path: Path) -> None:
        """Profiles with invalid weights are skipped with warning."""
        yaml_content = """
profiles:
  - domain_type: LIBRARY
    display_name: "Bad Weights"
    dimension_weights:
      code_quality: 0.50
"""
        path = self._write_yaml(tmp_path, yaml_content)
        registry = ProfileRegistry()
        count = registry.load_from_yaml(path)
        assert count == 0

    def test_invalid_domain_type_skipped(self, tmp_path: Path) -> None:
        """Profiles with unknown domain_type are skipped."""
        yaml_content = """
profiles:
  - domain_type: nonexistent_domain
    display_name: "Bad Domain"
    dimension_weights:
      code_quality: 0.125
"""
        path = self._write_yaml(tmp_path, yaml_content)
        registry = ProfileRegistry()
        count = registry.load_from_yaml(path)
        assert count == 0

    def test_yaml_with_derivation_map(self, tmp_path: Path) -> None:
        """Custom derivation_map is parsed from YAML."""
        yaml_content = """
profiles:
  - domain_type: ML_LIB
    display_name: "ML with custom derivation"
    dimension_weights:
      code_quality: 0.10
      architecture: 0.10
      testing: 0.10
      documentation: 0.10
      maintenance: 0.15
      security: 0.05
      functionality: 0.25
      innovation: 0.15
    derivation_map:
      code_quality:
        - [complexity, 0.5]
        - [test_footprint, 0.5]
"""
        path = self._write_yaml(tmp_path, yaml_content)
        registry = ProfileRegistry()
        count = registry.load_from_yaml(path)
        assert count == 1
        profile = registry.get(DomainType.ML_LIB)
        assert profile.derivation_map is not None
        assert "code_quality" in profile.derivation_map

    def test_load_profiles_validates_weights(self, tmp_path: Path) -> None:
        """Valid profile has weights summing to ~1.0."""
        yaml_content = """
profiles:
  - domain_type: CLI
    display_name: "Valid CLI"
    dimension_weights:
      code_quality: 0.15
      architecture: 0.10
      testing: 0.20
      documentation: 0.10
      maintenance: 0.20
      security: 0.10
      functionality: 0.10
      innovation: 0.05
"""
        path = self._write_yaml(tmp_path, yaml_content)
        registry = ProfileRegistry()
        count = registry.load_from_yaml(path)
        assert count == 1
        profile = registry.get(DomainType.CLI)
        assert profile.validate_weights()
