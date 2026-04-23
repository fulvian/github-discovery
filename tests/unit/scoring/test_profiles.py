"""Tests for profile registry."""

from __future__ import annotations

import pytest

from github_discovery.models.enums import DomainType, ScoreDimension
from github_discovery.models.scoring import DEFAULT_PROFILE, DomainProfile
from github_discovery.scoring.profiles import ProfileRegistry, validate_profile


class TestProfileRegistry:
    """Tests for ProfileRegistry."""

    def test_get_library_profile(self) -> None:
        registry = ProfileRegistry()
        profile = registry.get(DomainType.LIBRARY)
        assert profile.domain_type == DomainType.LIBRARY
        assert profile.display_name == "Library"

    def test_get_unknown_domain_returns_default(self) -> None:
        registry = ProfileRegistry()
        profile = registry.get(DomainType.OTHER)
        assert profile.domain_type == DomainType.OTHER

    def test_all_profiles_returns_dict(self) -> None:
        registry = ProfileRegistry()
        profiles = registry.all_profiles()
        assert DomainType.LIBRARY in profiles
        assert DomainType.CLI in profiles

    def test_register_custom_profile(self) -> None:
        registry = ProfileRegistry()
        custom = DomainProfile(
            domain_type=DomainType.LIBRARY,
            display_name="Custom Lib",
            description="Custom library profile",
            dimension_weights={
                ScoreDimension.CODE_QUALITY: 0.30,
                ScoreDimension.ARCHITECTURE: 0.15,
                ScoreDimension.TESTING: 0.15,
                ScoreDimension.DOCUMENTATION: 0.10,
                ScoreDimension.MAINTENANCE: 0.10,
                ScoreDimension.SECURITY: 0.10,
                ScoreDimension.FUNCTIONALITY: 0.05,
                ScoreDimension.INNOVATION: 0.05,
            },
        )
        registry.register(custom)
        assert registry.get(DomainType.LIBRARY).display_name == "Custom Lib"

    def test_register_invalid_weights_raises(self) -> None:
        registry = ProfileRegistry()
        invalid = DomainProfile(
            domain_type=DomainType.LIBRARY,
            display_name="Bad",
            dimension_weights={
                ScoreDimension.CODE_QUALITY: 0.5,
                ScoreDimension.TESTING: 0.3,
            },
        )
        with pytest.raises(ValueError, match="invalid weights"):
            registry.register(invalid)

    def test_additional_profiles_loaded(self) -> None:
        """Registry loads additional profiles for all 12 DomainTypes."""
        registry = ProfileRegistry()
        profiles = registry.all_profiles()
        # At least 6 profiles should exist
        assert len(profiles) >= 6

    def test_web_framework_profile(self) -> None:
        registry = ProfileRegistry()
        profile = registry.get(DomainType.WEB_FRAMEWORK)
        assert profile.display_name == "Web Framework"
        assert profile.validate_weights()

    def test_ml_lib_profile(self) -> None:
        registry = ProfileRegistry()
        profile = registry.get(DomainType.ML_LIB)
        assert profile.display_name == "ML Library"
        assert profile.validate_weights()
        assert profile.dimension_weights[ScoreDimension.INNOVATION] == 0.15

    def test_data_tool_profile(self) -> None:
        registry = ProfileRegistry()
        profile = registry.get(DomainType.DATA_TOOL)
        assert profile.display_name == "Data Tool"
        assert profile.validate_weights()
        assert profile.dimension_weights[ScoreDimension.FUNCTIONALITY] == 0.20


class TestValidateProfile:
    """Tests for validate_profile function."""

    def test_valid_profile(self) -> None:
        profile = DEFAULT_PROFILE
        validate_profile(profile)  # Should not raise

    def test_invalid_weights_raises(self) -> None:
        bad = DomainProfile(
            domain_type=DomainType.OTHER,
            display_name="Bad",
            dimension_weights={ScoreDimension.CODE_QUALITY: 0.3},
        )
        with pytest.raises(ValueError):
            validate_profile(bad)
