"""Domain taxonomy and weight profile registry.

Manages domain-specific scoring profiles including built-in profiles
for all 12 DomainType values, custom profile registration, and
weight validation.

Built-in profiles are defined in models/scoring.py. This module
extends them with additional domain profiles and provides a
registry for runtime profile management.

T5.3: Supports loading custom profiles from YAML/TOML files via
``ProfileRegistry.load_from_yaml()`` and ``load_from_toml()``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from github_discovery.models.enums import DomainType, ScoreDimension
from github_discovery.models.scoring import (
    DEFAULT_PROFILE,
    DOMAIN_PROFILES,
    DomainProfile,
)

logger = structlog.get_logger("github_discovery.scoring.profiles")

_WEIGHT_TOLERANCE = 0.01
_DERIVATION_MAPPING_MIN_LENGTH = 2


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

    def __init__(self, custom_profiles_path: str | Path | None = None) -> None:
        """Initialize ProfileRegistry with built-in domain profiles.

        Args:
            custom_profiles_path: Optional path to YAML/TOML file with
                custom profiles. When provided, profiles are loaded and
                override built-in ones for matching domains.
        """
        self._profiles = self._load_profiles()
        if custom_profiles_path:
            try:
                count = self.load_custom_profiles(custom_profiles_path)
                logger.info(
                    "auto_loaded_custom_profiles",
                    path=str(custom_profiles_path),
                    count=count,
                )
            except (FileNotFoundError, ValueError) as exc:
                logger.warning(
                    "custom_profiles_load_failed",
                    path=str(custom_profiles_path),
                    error=str(exc),
                )

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

    def load_custom_profiles(self, path: str | Path) -> int:
        """Load custom profiles from a YAML or TOML file.

        Detects format from file extension (.yaml/.yml → YAML, .toml → TOML).
        Validates all profiles before loading. Invalid profiles are skipped
        with a warning.

        Args:
            path: Path to the profiles file.

        Returns:
            Number of profiles loaded.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file format is unsupported.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Custom profiles file not found: {file_path}")

        suffix = file_path.suffix.lower()
        if suffix in (".yaml", ".yml"):
            return self.load_from_yaml(file_path)
        if suffix == ".toml":
            return self.load_from_toml(file_path)
        msg = f"Unsupported profile file format: {suffix} (expected .yaml, .yml, or .toml)"
        raise ValueError(msg)

    def load_from_yaml(self, path: Path) -> int:
        """Load custom profiles from a YAML file.

        Expected format:
            profiles:
              - domain_type: ML_LIB
                display_name: "Custom ML"
                description: "..."
                dimension_weights:
                  code_quality: 0.15
                  architecture: 0.10
                  ...
                gate_thresholds:
                  gate1: 0.3
                  gate2: 0.4

        Args:
            path: Path to the YAML file.

        Returns:
            Number of profiles loaded.
        """
        try:
            import yaml  # type: ignore[import-untyped]  # noqa: PLC0415
        except ImportError:
            logger.error("pyyaml_required", action="pip install pyyaml")
            return 0

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "profiles" not in data:
            logger.warning("invalid_yaml_format", path=str(path))
            return 0

        count = 0
        for entry in data["profiles"]:
            profile = _parse_profile_entry(entry)
            if profile is not None:
                try:
                    self.register(profile)
                    count += 1
                except ValueError as e:
                    logger.warning(
                        "invalid_custom_profile_skipped",
                        domain=entry.get("domain_type", "unknown"),
                        error=str(e),
                    )
        logger.info("custom_profiles_loaded", path=str(path), count=count)
        return count

    def load_from_toml(self, path: Path) -> int:
        """Load custom profiles from a TOML file.

        Expected format:
            [[profiles]]
            domain_type = "ML_LIB"
            display_name = "Custom ML"
            dimension_weights = {code_quality = 0.15, ...}

        Args:
            path: Path to the TOML file.

        Returns:
            Number of profiles loaded.
        """
        import tomllib  # noqa: PLC0415

        data = tomllib.loads(path.read_text(encoding="utf-8"))
        if "profiles" not in data or not isinstance(data["profiles"], list):
            logger.warning("invalid_toml_format", path=str(path))
            return 0

        count = 0
        for entry in data["profiles"]:
            profile = _parse_profile_entry(entry)
            if profile is not None:
                try:
                    self.register(profile)
                    count += 1
                except ValueError as e:
                    logger.warning(
                        "invalid_custom_profile_skipped",
                        domain=entry.get("domain_type", "unknown"),
                        error=str(e),
                    )
        logger.info("custom_profiles_loaded", path=str(path), count=count)
        return count

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
            gate_thresholds={"gate1": 0.5, "gate2": 0.6, "gate3": 0.6},
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
            gate_thresholds={"gate1": 0.4, "gate2": 0.5, "gate3": 0.6},
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
            gate_thresholds={"gate1": 0.4, "gate2": 0.5, "gate3": 0.6},
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
            gate_thresholds={"gate1": 0.6, "gate2": 0.7, "gate3": 0.6},
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
            gate_thresholds={"gate1": 0.5, "gate2": 0.6, "gate3": 0.6},
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
            gate_thresholds={"gate1": 0.5, "gate2": 0.6, "gate3": 0.6},
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
            gate_thresholds={"gate1": 0.4, "gate2": 0.5, "gate3": 0.6},
            star_baseline=600.0,
            preferred_channels=["search", "registry", "awesome_list"],
        ),
    ]


def _parse_profile_entry(entry: dict[str, Any]) -> DomainProfile | None:  # noqa: PLR0912
    """Parse a profile entry from YAML/TOML dict into a DomainProfile.

    Args:
        entry: Dict with profile fields (domain_type, display_name, etc).

    Returns:
        DomainProfile if parsing succeeded, None otherwise.
    """
    domain_type_str = entry.get("domain_type")
    if domain_type_str is None:
        logger.warning("profile_missing_domain_type", entry=entry)
        return None

    # Normalize to lowercase for case-insensitive matching (YAML/TOML often
    # use SCREAMING_SNAKE_CASE like "ML_LIB" while enum values are "ml_lib")
    domain_type_normalized = str(domain_type_str).lower()

    try:
        domain_type = DomainType(domain_type_normalized)
    except ValueError:
        logger.warning(
            "unknown_domain_type",
            domain_type=domain_type_str,
            valid=[d.value for d in DomainType],
        )
        return None

    # Parse dimension_weights from string keys to ScoreDimension keys
    raw_weights = entry.get("dimension_weights", {})
    if not isinstance(raw_weights, dict):
        logger.warning("invalid_dimension_weights", domain_type=domain_type_str)
        return None

    dimension_weights: dict[ScoreDimension, float] = {}
    for key, value in raw_weights.items():
        try:
            dim = ScoreDimension(key)
            dimension_weights[dim] = float(value)
        except ValueError:
            logger.warning(
                "unknown_dimension_in_profile",
                dimension=key,
                domain_type=domain_type_str,
            )
            continue

    # Parse optional gate_thresholds
    raw_thresholds = entry.get("gate_thresholds", {})
    gate_thresholds: dict[str, float] = {}
    if isinstance(raw_thresholds, dict):
        for k, v in raw_thresholds.items():
            gate_thresholds[str(k)] = float(v)

    # Parse optional derivation_map (T5.1)
    raw_derivation = entry.get("derivation_map")
    derivation_map: dict[str, list[list[float | str]]] | None = None
    if isinstance(raw_derivation, dict):
        derivation_map = {}
        for dim_name, mappings in raw_derivation.items():
            if isinstance(mappings, list):
                parsed_mappings: list[list[float | str]] = []
                for item in mappings:
                    if (
                        isinstance(item, (list, tuple))
                        and len(item) >= _DERIVATION_MAPPING_MIN_LENGTH
                    ):
                        parsed_mappings.append([str(item[0]), float(item[1])])
                if parsed_mappings:
                    derivation_map[str(dim_name)] = parsed_mappings

    # Build kwargs, only including optional fields with non-None values
    kwargs: dict[str, object] = {
        "domain_type": domain_type,
        "display_name": entry.get("display_name", domain_type_str),
        "description": entry.get("description", ""),
        "dimension_weights": dimension_weights,
        "star_baseline": float(entry.get("star_baseline", 1000.0)),
        "preferred_channels": entry.get("preferred_channels", []),
    }
    if gate_thresholds:
        kwargs["gate_thresholds"] = gate_thresholds
    if derivation_map is not None:
        kwargs["derivation_map"] = derivation_map

    return DomainProfile(**kwargs)  # type: ignore[arg-type]
