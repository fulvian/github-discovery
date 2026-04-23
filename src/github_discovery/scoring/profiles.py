"""Domain taxonomy and weight profile registry.

Manages domain-specific scoring profiles including built-in profiles
for all 12 DomainType values, custom profile registration, and
weight validation.

Built-in profiles are defined in models/scoring.py. This module
extends them with additional domain profiles and provides a
registry for runtime profile management.
"""

from __future__ import annotations

import structlog

from github_discovery.models.enums import DomainType, ScoreDimension
from github_discovery.models.scoring import (
    DEFAULT_PROFILE,
    DOMAIN_PROFILES,
    DomainProfile,
)

logger = structlog.get_logger("github_discovery.scoring.profiles")

_WEIGHT_TOLERANCE = 0.01


class ProfileRegistry:
    """Registry of domain profiles with loading and validation.

    Supports:
    - Built-in profiles for all 12 DomainType values
    - Custom profile registration (replaces built-in)
    - Validation: weights must sum to 1.0 (±0.01)

    Usage:
        registry = ProfileRegistry()
        profile = registry.get(DomainType.LIBRARY)
        # profile.dimension_weights gives per-dimension weights
    """

    def __init__(self) -> None:
        """Initialize ProfileRegistry with built-in domain profiles."""
        self._profiles = self._load_profiles()

    def get(self, domain: DomainType) -> DomainProfile:
        """Get profile for a domain (built-in or default).

        Returns domain-specific profile if registered,
        otherwise returns DEFAULT_PROFILE.
        """
        return self._profiles.get(domain, DEFAULT_PROFILE)

    def all_profiles(self) -> dict[DomainType, DomainProfile]:
        """Return all registered profiles."""
        return dict(self._profiles)

    def register(self, profile: DomainProfile) -> None:
        """Register a custom profile (replaces built-in if same domain).

        Args:
            profile: The profile to register. Must have valid weights.

        Raises:
            ValueError: If weights don't sum to approximately 1.0.
        """
        validate_profile(profile)
        self._profiles[profile.domain_type] = profile
        logger.info(
            "profile_registered",
            domain=profile.domain_type.value,
            display_name=profile.display_name,
        )

    def _load_profiles(self) -> dict[DomainType, DomainProfile]:
        """Load built-in profiles and extend with additional domain profiles.

        Returns a dict of all known profiles keyed by DomainType.
        """
        profiles = dict(DOMAIN_PROFILES)

        # Add additional domain profiles not in models/scoring.py
        additional = _build_additional_profiles()
        for profile in additional:
            profiles[profile.domain_type] = profile

        return profiles


def validate_profile(profile: DomainProfile) -> None:
    """Validate a profile: weights must sum to 1.0 (±0.01).

    Args:
        profile: The profile to validate.

    Raises:
        ValueError: If weights don't sum to approximately 1.0.
    """
    if not profile.validate_weights():
        total = sum(profile.dimension_weights.values())
        msg = (
            f"Profile for {profile.domain_type.value} has invalid weights: "
            f"sum = {total:.4f}, expected 1.0 (±{_WEIGHT_TOLERANCE})"
        )
        raise ValueError(msg)


def _build_additional_profiles() -> list[DomainProfile]:
    """Build additional domain profiles for domains not in models/scoring.py.

    The base DOMAIN_PROFILES already covers: LIBRARY, CLI, DEVOPS_TOOL, BACKEND, OTHER.
    We add: WEB_FRAMEWORK, DATA_TOOL, ML_LIB, SECURITY_TOOL, LANG_TOOL,
    TEST_TOOL, DOC_TOOL.
    """
    return [
        DomainProfile(
            domain_type=DomainType.WEB_FRAMEWORK,
            display_name="Web Framework",
            description="Web frameworks and servers",
            dimension_weights={
                ScoreDimension.CODE_QUALITY: 0.15,
                ScoreDimension.ARCHITECTURE: 0.15,
                ScoreDimension.TESTING: 0.15,
                ScoreDimension.DOCUMENTATION: 0.15,
                ScoreDimension.MAINTENANCE: 0.15,
                ScoreDimension.SECURITY: 0.10,
                ScoreDimension.FUNCTIONALITY: 0.10,
                ScoreDimension.INNOVATION: 0.05,
            },
            star_baseline=5000.0,
            preferred_channels=["search", "registry", "dependency"],
        ),
        DomainProfile(
            domain_type=DomainType.DATA_TOOL,
            display_name="Data Tool",
            description="Data processing and analysis tools",
            dimension_weights={
                ScoreDimension.CODE_QUALITY: 0.15,
                ScoreDimension.ARCHITECTURE: 0.10,
                ScoreDimension.TESTING: 0.10,
                ScoreDimension.DOCUMENTATION: 0.15,
                ScoreDimension.MAINTENANCE: 0.15,
                ScoreDimension.SECURITY: 0.10,
                ScoreDimension.FUNCTIONALITY: 0.20,
                ScoreDimension.INNOVATION: 0.05,
            },
            star_baseline=800.0,
            preferred_channels=["search", "registry", "awesome_list"],
        ),
        DomainProfile(
            domain_type=DomainType.ML_LIB,
            display_name="ML Library",
            description="Machine learning libraries",
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
            star_baseline=2000.0,
            preferred_channels=["search", "registry", "dependency"],
        ),
        DomainProfile(
            domain_type=DomainType.SECURITY_TOOL,
            display_name="Security Tool",
            description="Security analysis and tooling",
            dimension_weights={
                ScoreDimension.CODE_QUALITY: 0.15,
                ScoreDimension.ARCHITECTURE: 0.10,
                ScoreDimension.TESTING: 0.15,
                ScoreDimension.DOCUMENTATION: 0.10,
                ScoreDimension.MAINTENANCE: 0.15,
                ScoreDimension.SECURITY: 0.20,
                ScoreDimension.FUNCTIONALITY: 0.10,
                ScoreDimension.INNOVATION: 0.05,
            },
            star_baseline=1500.0,
            preferred_channels=["search", "awesome_list"],
        ),
        DomainProfile(
            domain_type=DomainType.LANG_TOOL,
            display_name="Language Tool",
            description="Language servers, linters, formatters",
            dimension_weights={
                ScoreDimension.CODE_QUALITY: 0.20,
                ScoreDimension.ARCHITECTURE: 0.15,
                ScoreDimension.TESTING: 0.20,
                ScoreDimension.DOCUMENTATION: 0.10,
                ScoreDimension.MAINTENANCE: 0.15,
                ScoreDimension.SECURITY: 0.05,
                ScoreDimension.FUNCTIONALITY: 0.10,
                ScoreDimension.INNOVATION: 0.05,
            },
            star_baseline=1000.0,
            preferred_channels=["search", "registry"],
        ),
        DomainProfile(
            domain_type=DomainType.TEST_TOOL,
            display_name="Test Tool",
            description="Testing frameworks and utilities",
            dimension_weights={
                ScoreDimension.CODE_QUALITY: 0.15,
                ScoreDimension.ARCHITECTURE: 0.10,
                ScoreDimension.TESTING: 0.25,
                ScoreDimension.DOCUMENTATION: 0.15,
                ScoreDimension.MAINTENANCE: 0.15,
                ScoreDimension.SECURITY: 0.05,
                ScoreDimension.FUNCTIONALITY: 0.10,
                ScoreDimension.INNOVATION: 0.05,
            },
            star_baseline=500.0,
            preferred_channels=["search", "registry", "dependency"],
        ),
        DomainProfile(
            domain_type=DomainType.DOC_TOOL,
            display_name="Doc Tool",
            description="Documentation generators and tools",
            dimension_weights={
                ScoreDimension.CODE_QUALITY: 0.10,
                ScoreDimension.ARCHITECTURE: 0.10,
                ScoreDimension.TESTING: 0.10,
                ScoreDimension.DOCUMENTATION: 0.25,
                ScoreDimension.MAINTENANCE: 0.15,
                ScoreDimension.SECURITY: 0.05,
                ScoreDimension.FUNCTIONALITY: 0.15,
                ScoreDimension.INNOVATION: 0.10,
            },
            star_baseline=600.0,
            preferred_channels=["search", "registry", "awesome_list"],
        ),
    ]
