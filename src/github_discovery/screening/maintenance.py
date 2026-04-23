"""Maintenance signal analyzer for Gate 1.

Analyzes commit recency, cadence, bus factor proxy, and issue
resolution from API data. PyDriller is optional (for deep analysis
when clone is available); by default uses API-based heuristics.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from github_discovery.models.screening import MaintenanceScore

if TYPE_CHECKING:
    from github_discovery.screening.types import RepoContext

logger = structlog.get_logger("github_discovery.screening.maintenance")

_MAINTENANCE_THRESHOLD_DAYS = 365
_BUS_FACTOR_LOW = 2
_BUS_FACTOR_MEDIUM = 3
_BUS_FACTOR_GOOD = 5

# Recency thresholds (days)
_RECENCY_EXCELLENT = 30
_RECENCY_GOOD = 90
_RECENCY_FAIR = 180
_RECENCY_POOR = 365

# Cadence thresholds (days)
_CADENCE_EXCELLENT = 7
_CADENCE_GOOD = 30
_CADENCE_FAIR = 90

# Issue resolution ratio thresholds
_RESOLUTION_EXCELLENT = 2.0
_RESOLUTION_GOOD = 1.0
_RESOLUTION_FAIR = 0.5

# Minimum commits for cadence calculation
_MIN_CADENCE_COMMITS = 2

# Scoring weights for composite
_WEIGHT_RECENCY = 0.3
_WEIGHT_CADENCE = 0.25
_WEIGHT_BUS_FACTOR = 0.25
_WEIGHT_RESOLUTION = 0.2

# Confidence for API-based analysis (not clone-based)
_API_CONFIDENCE = 0.7

# Default score for missing data
_DEFAULT_MISSING_SCORE = 0.0
_NEUTRAL_RESOLUTION_SCORE = 0.5


def _parse_commit_date(commit: dict[str, object]) -> datetime | None:
    """Extract author date from a commit dict."""
    commit_data = commit.get("commit")
    if not isinstance(commit_data, dict):
        return None
    author = commit_data.get("author")
    if not isinstance(author, dict):
        return None
    date_str = author.get("date")
    if not isinstance(date_str, str):
        return None
    return datetime.fromisoformat(date_str)


def _score_recency(days_ago: int) -> float:
    """Score commit recency based on age thresholds."""
    if days_ago < _RECENCY_EXCELLENT:
        return 1.0
    if days_ago < _RECENCY_GOOD:
        return 0.8
    if days_ago < _RECENCY_FAIR:
        return 0.5
    if days_ago < _RECENCY_POOR:
        return 0.3
    return 0.1


def _score_cadence(avg_days: float) -> float:
    """Score commit cadence based on average gap thresholds."""
    if avg_days < _CADENCE_EXCELLENT:
        return 1.0
    if avg_days < _CADENCE_GOOD:
        return 0.7
    if avg_days < _CADENCE_FAIR:
        return 0.4
    return 0.2


def _score_bus_factor(unique_authors: int) -> float:
    """Score bus factor proxy based on contributor count."""
    if unique_authors >= _BUS_FACTOR_GOOD:
        return 1.0
    if unique_authors >= _BUS_FACTOR_MEDIUM:
        return 0.7
    if unique_authors >= _BUS_FACTOR_LOW:
        return 0.4
    return 0.2


def _score_issue_resolution(closed_count: int, total_count: int) -> float:
    """Score issue resolution rate based on closed/open ratio."""
    if total_count == 0:
        return _NEUTRAL_RESOLUTION_SCORE

    open_count = total_count - closed_count
    if open_count <= 0:
        return 1.0

    ratio = closed_count / open_count
    if ratio > _RESOLUTION_EXCELLENT:
        return 1.0
    if ratio >= _RESOLUTION_GOOD:
        return 0.7
    if ratio >= _RESOLUTION_FAIR:
        return 0.4
    return 0.2


def _analyze_commits(
    commits: list[dict[str, object]],
    now: datetime,
) -> tuple[float, float, int, float, int, list[str]]:
    """Analyze commit data for recency, cadence, and bus factor.

    Returns:
        (recency_score, cadence_score, bus_factor, cadence_days, last_days_ago, notes)
    """
    notes: list[str] = []
    commit_dates: list[datetime] = []
    authors: set[str] = set()

    for commit in commits:
        dt = _parse_commit_date(commit)
        if dt is not None:
            commit_dates.append(dt)

        commit_data = commit.get("commit")
        if isinstance(commit_data, dict):
            author = commit_data.get("author")
            if isinstance(author, dict):
                name = author.get("name")
                if isinstance(name, str):
                    authors.add(name)

    if not commit_dates:
        return _DEFAULT_MISSING_SCORE, _DEFAULT_MISSING_SCORE, 0, 0.0, 0, notes

    # Sort descending (newest first)
    commit_dates.sort(reverse=True)

    # Recency
    delta = now - commit_dates[0]
    last_days_ago = delta.days
    recency_score = _score_recency(last_days_ago)
    notes.append(f"Last commit: {last_days_ago} days ago")

    # Cadence
    if len(commit_dates) >= _MIN_CADENCE_COMMITS:
        total_span = (commit_dates[0] - commit_dates[-1]).days
        cadence_days = total_span / (len(commit_dates) - 1)
    else:
        cadence_days = 0.0

    cadence_score = _score_cadence(cadence_days)
    notes.append(f"Cadence: {cadence_days:.1f} days between commits")

    # Bus factor
    bus_factor = len(authors)
    notes.append(f"Bus factor: {bus_factor} unique authors")

    return recency_score, cadence_score, bus_factor, cadence_days, last_days_ago, notes


class MaintenanceAnalyzer:
    """Analyzes maintenance signals from commit history and activity.

    Primary (API-based): commit recency, cadence, contributor count,
    issue resolution. No clone needed — uses recent_commits/issues data.
    """

    def score(self, ctx: RepoContext) -> MaintenanceScore:
        """Score maintenance signals from API data."""
        notes: list[str] = []
        now = datetime.now(UTC)

        # --- Commit analysis ---
        if ctx.recent_commits:
            (
                recency_score,
                cadence_score,
                bus_factor,
                cadence_days,
                last_days_ago,
                commit_notes,
            ) = _analyze_commits(ctx.recent_commits, now)
            notes.extend(commit_notes)
            bus_factor_score = _score_bus_factor(bus_factor)
        else:
            recency_score = _DEFAULT_MISSING_SCORE
            cadence_score = _DEFAULT_MISSING_SCORE
            bus_factor = 0
            bus_factor_score = _DEFAULT_MISSING_SCORE
            last_days_ago = 0
            cadence_days = 0.0
            notes.append("No commit data available")

        # --- Issue resolution ---
        issue_resolution_rate = 0.0
        if ctx.recent_issues:
            total_issues = len(ctx.recent_issues)
            closed_issues = sum(1 for issue in ctx.recent_issues if issue.get("state") == "closed")
            issue_resolution_rate = closed_issues / total_issues
            resolution_score = _score_issue_resolution(closed_issues, total_issues)
            notes.append(
                f"Issue resolution: {closed_issues}/{total_issues} closed "
                f"({issue_resolution_rate:.0%})"
            )
        else:
            resolution_score = _NEUTRAL_RESOLUTION_SCORE
            notes.append("No issue data available")

        # --- Composite weighted score ---
        composite = (
            recency_score * _WEIGHT_RECENCY
            + cadence_score * _WEIGHT_CADENCE
            + bus_factor_score * _WEIGHT_BUS_FACTOR
            + resolution_score * _WEIGHT_RESOLUTION
        )

        # Ensure value is in [0.0, 1.0]
        composite = min(max(composite, 0.0), 1.0)

        return MaintenanceScore(
            value=composite,
            details={
                "last_commit_days_ago": last_days_ago,
                "commit_cadence_days": round(cadence_days, 2),
                "bus_factor": bus_factor,
                "issue_resolution_rate": round(issue_resolution_rate, 4),
            },
            confidence=_API_CONFIDENCE,
            notes=notes,
        )
