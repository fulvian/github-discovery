"""Release discipline scorer for Gate 1.

Evaluates semver tagging, release cadence, changelog per release,
and release notes quality.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING

import structlog

from github_discovery.models.screening import ReleaseDisciplineScore

if TYPE_CHECKING:
    from github_discovery.screening.types import RepoContext

logger = structlog.get_logger("github_discovery.screening.release_discipline")

_SEMVER_RE = re.compile(r"^v?\d+\.\d+\.\d+")

# Minimum body length for "good" release notes
_MIN_RELEASE_NOTES_LENGTH = 100
_MIN_RELEASES_FOR_CADENCE = 2
_SEMVER_RATIO_THRESHOLD = 0.8
_CADENCE_DAYS_THRESHOLD = 90
_RELEASE_NOTES_RATIO_THRESHOLD = 0.5


def _parse_iso_date(date_str: object) -> datetime | None:
    """Parse an ISO date string from release data."""
    if not isinstance(date_str, str):
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _compute_cadence_days(releases: list[dict[str, object]]) -> float | None:
    """Compute average days between consecutive releases.

    Returns None if fewer than 2 releases with valid dates.
    """
    dates: list[datetime] = []
    for release in releases:
        published = release.get("published_at") or release.get("created_at")
        dt = _parse_iso_date(published)
        if dt is not None:
            dates.append(dt)

    if len(dates) < _MIN_RELEASES_FOR_CADENCE:
        return None

    # Sort descending (newest first in API response)
    dates.sort(reverse=True)

    gaps: list[float] = []
    for i in range(len(dates) - 1):
        delta = (dates[i] - dates[i + 1]).total_seconds() / 86400.0
        gaps.append(abs(delta))

    return sum(gaps) / len(gaps) if gaps else None


class ReleaseDisciplineScorer:
    """Scores release discipline and versioning practices."""

    def score(self, ctx: RepoContext) -> ReleaseDisciplineScore:
        """Score release discipline from release history and repo contents.

        Scoring breakdown (each +0.2, max 1.0):
        - Has releases: recent_releases non-empty
        - Semver ratio > 0.8
        - Release cadence < 90 days
        - Release notes quality (>50% have body > 100 chars)
        - Changelog file present in repo_contents

        Args:
            ctx: Repository context with releases and contents.

        Returns:
            ReleaseDisciplineScore with value 0.0-1.0 and details.
        """
        releases = ctx.recent_releases
        contents = ctx.repo_contents

        score_val = 0.0
        release_count = len(releases)

        # Signal 1: Has releases
        has_releases = release_count > 0
        if has_releases:
            score_val += 0.2

        # Signal 2: Semver tagging ratio
        semver_count = 0
        for release in releases:
            tag_name = release.get("tag_name", "")
            if isinstance(tag_name, str) and _SEMVER_RE.match(tag_name):
                semver_count += 1

        semver_ratio = semver_count / release_count if release_count > 0 else 0.0
        has_semver_tags = semver_ratio >= _SEMVER_RATIO_THRESHOLD
        if has_semver_tags:
            score_val += 0.2

        # Signal 3: Release cadence
        cadence_days = _compute_cadence_days(releases)
        if cadence_days is not None and cadence_days < _CADENCE_DAYS_THRESHOLD:
            score_val += 0.2

        # Signal 4: Release notes quality
        good_notes = 0
        for release in releases:
            body = release.get("body", "")
            if isinstance(body, str) and len(body) > _MIN_RELEASE_NOTES_LENGTH:
                good_notes += 1

        notes_ratio = good_notes / release_count if release_count > 0 else 0.0
        has_changelog_per_release = notes_ratio > _RELEASE_NOTES_RATIO_THRESHOLD
        if has_changelog_per_release:
            score_val += 0.2

        # Signal 5: Changelog file in repo
        lower_contents = {c.lower() for c in contents}
        changelog_paths = {"changelog.md", "changelog.rst", "changes.md", "history.md"}
        has_changelog_file = bool(changelog_paths & lower_contents)
        if has_changelog_file:
            score_val += 0.2

        score_val = min(1.0, score_val)

        details: dict[str, str | int | float | bool | None] = {
            "has_semver_tags": has_semver_tags,
            "release_count": release_count,
            "release_cadence_days": round(cadence_days, 1) if cadence_days is not None else None,
            "has_changelog_per_release": has_changelog_per_release,
        }

        logger.debug(
            "release_discipline_scored",
            full_name=ctx.candidate.full_name,
            value=round(score_val, 4),
            release_count=release_count,
            semver_ratio=round(semver_ratio, 2),
            cadence_days=cadence_days,
        )

        return ReleaseDisciplineScore(
            value=round(score_val, 4),
            details=details,
            confidence=1.0,
        )
