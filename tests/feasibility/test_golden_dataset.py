"""Tests for Wave 4 golden dataset schema and validator."""

from __future__ import annotations

import json
from pathlib import Path

from github_discovery.feasibility.golden_dataset import (
    GoldenDatasetEntry,
    load_golden_dataset,
    validate_golden_dataset,
)


def _entry(full_name: str) -> dict[str, object]:
    return {
        "full_name": full_name,
        "commit_sha": "abc123",
        "domain": "library",
        "language": "Python",
        "stars_at_label": 10,
        "ratings": [
            {
                "rater_id": "r1",
                "code_quality": 4,
                "architecture": 4,
                "testing": 4,
                "documentation": 4,
                "maintenance": 4,
                "security": 4,
                "functionality": 4,
                "innovation": 4,
                "notes": "ok",
            },
            {
                "rater_id": "r2",
                "code_quality": 4,
                "architecture": 4,
                "testing": 4,
                "documentation": 4,
                "maintenance": 4,
                "security": 4,
                "functionality": 4,
                "innovation": 4,
                "notes": "ok",
            },
            {
                "rater_id": "r3",
                "code_quality": 4,
                "architecture": 4,
                "testing": 4,
                "documentation": 4,
                "maintenance": 4,
                "security": 4,
                "functionality": 4,
                "innovation": 4,
                "notes": "ok",
            },
        ],
    }


def test_load_golden_dataset_parses_entries(tmp_path: Path) -> None:
    payload = [_entry("owner/repo")]
    path = tmp_path / "golden.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    entries = load_golden_dataset(path)
    assert len(entries) == 1
    assert isinstance(entries[0], GoldenDatasetEntry)
    assert entries[0].full_name == "owner/repo"


def test_validate_golden_dataset_happy_path() -> None:
    entries = [GoldenDatasetEntry.model_validate(_entry(f"owner/repo-{i}")) for i in range(4)]

    report = validate_golden_dataset(entries, expected_size=4, min_raters_per_repo=3)
    assert report.ready_for_calibration is True
    assert report.errors == []


def test_validate_golden_dataset_detects_duplicates() -> None:
    entries = [
        GoldenDatasetEntry.model_validate(_entry("owner/repo")),
        GoldenDatasetEntry.model_validate(_entry("owner/repo")),
    ]

    report = validate_golden_dataset(entries, expected_size=2, min_raters_per_repo=3)
    assert report.ready_for_calibration is False
    assert any("Duplicate repositories" in err for err in report.errors)


def test_validate_golden_dataset_detects_min_raters_violation() -> None:
    raw = _entry("owner/repo")
    ratings = raw["ratings"]
    assert isinstance(ratings, list)
    raw["ratings"] = ratings[:2]

    entries = [GoldenDatasetEntry.model_validate(raw)]
    report = validate_golden_dataset(entries, expected_size=1, min_raters_per_repo=3)
    assert report.ready_for_calibration is False
    assert any("Minimum ratings per repo" in err for err in report.errors)
