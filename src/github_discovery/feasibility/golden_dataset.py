"""Golden dataset schema and validation helpers for Wave 4.

This module provides a strict schema for the external 200-repo labeling
dataset and deterministic validation checks used before calibration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path  # noqa: TC003

from pydantic import BaseModel, Field

from github_discovery.models.enums import DomainType  # noqa: TC001

_MIN_DOMAIN_COVERAGE_WARNING = 8


class ExpertRating(BaseModel):
    """Single rater evaluation for one repository."""

    rater_id: str = Field(min_length=1)
    code_quality: int = Field(ge=1, le=5)
    architecture: int = Field(ge=1, le=5)
    testing: int = Field(ge=1, le=5)
    documentation: int = Field(ge=1, le=5)
    maintenance: int = Field(ge=1, le=5)
    security: int = Field(ge=1, le=5)
    functionality: int = Field(ge=1, le=5)
    innovation: int = Field(ge=1, le=5)
    notes: str = Field(default="")


class GoldenDatasetEntry(BaseModel):
    """One labeled repository entry in the golden dataset."""

    full_name: str = Field(min_length=3)
    commit_sha: str = Field(min_length=1)
    domain: DomainType
    language: str = Field(min_length=1)
    stars_at_label: int = Field(ge=0)
    ratings: list[ExpertRating] = Field(min_length=1)


@dataclass
class GoldenDatasetValidationReport:
    """Validation report for golden dataset readiness checks."""

    total_entries: int
    unique_repositories: int
    domain_counts: dict[DomainType, int]
    min_ratings_per_repo: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ready_for_calibration(self) -> bool:
        """Whether the dataset satisfies mandatory checks."""
        return len(self.errors) == 0


def load_golden_dataset(path: Path) -> list[GoldenDatasetEntry]:
    """Load and parse a golden dataset JSON file."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        msg = f"Golden dataset must be a JSON array, got {type(payload).__name__}"
        raise ValueError(msg)
    return [GoldenDatasetEntry.model_validate(item) for item in payload]


def validate_golden_dataset(
    entries: list[GoldenDatasetEntry],
    *,
    expected_size: int = 200,
    min_raters_per_repo: int = 3,
) -> GoldenDatasetValidationReport:
    """Validate dataset readiness against Wave 4 acceptance preconditions."""
    errors: list[str] = []
    warnings: list[str] = []

    seen: set[str] = set()
    duplicates: set[str] = set()
    domain_counts: dict[DomainType, int] = {}
    min_ratings = min((len(e.ratings) for e in entries), default=0)

    for entry in entries:
        if entry.full_name in seen:
            duplicates.add(entry.full_name)
        seen.add(entry.full_name)
        domain_counts[entry.domain] = domain_counts.get(entry.domain, 0) + 1

    if len(entries) < expected_size:
        errors.append(
            f"Dataset has {len(entries)} entries, expected at least {expected_size}",
        )

    if len(duplicates) > 0:
        dup_list = ", ".join(sorted(duplicates))
        errors.append(f"Duplicate repositories detected: {dup_list}")

    if min_ratings < min_raters_per_repo:
        errors.append(
            f"Minimum ratings per repo is {min_ratings}, expected at least {min_raters_per_repo}",
        )

    if len(domain_counts) < _MIN_DOMAIN_COVERAGE_WARNING:
        warnings.append(
            "Domain coverage is low "
            f"(<{_MIN_DOMAIN_COVERAGE_WARNING} domains represented); "
            "calibration may be biased",
        )

    return GoldenDatasetValidationReport(
        total_entries=len(entries),
        unique_repositories=len(seen),
        domain_counts=domain_counts,
        min_ratings_per_repo=min_ratings,
        errors=errors,
        warnings=warnings,
    )
