"""Code complexity metrics via scc subprocess for Gate 2.

Runs scc on a shallow clone for LOC, language breakdown, and
complexity metrics. Falls back to GitHub API data if scc
is not available.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog

from github_discovery.models.candidate import RepoCandidate  # noqa: TC001
from github_discovery.models.screening import ComplexityScore

if TYPE_CHECKING:
    from github_discovery.screening.subprocess_runner import SubprocessRunner

logger = structlog.get_logger("github_discovery.screening.complexity")

_SCC_BINARY = "scc"
_SCC_TIMEOUT = 60.0
_SMALL_PROJECT_LOC = 10_000
_MEDIUM_PROJECT_LOC = 100_000
_LARGE_PROJECT_LOC = 500_000
_LANGUAGE_FRAGMENTATION_THRESHOLD = 5


class ComplexityAnalyzer:
    """Code complexity and size metrics via scc subprocess."""

    def __init__(self, subprocess_runner: SubprocessRunner | None = None) -> None:
        """Initialize with optional SubprocessRunner."""
        self._runner = subprocess_runner

    async def score(
        self,
        candidate: RepoCandidate,
        clone_dir: str | None = None,
    ) -> ComplexityScore:
        """Run scc and return ComplexityScore.

        If clone_dir is None, falls back to GitHub API language/size data.
        """
        if self._runner is None or clone_dir is None:
            return self._fallback_score(candidate)

        result = await self._runner.run(
            [_SCC_BINARY, clone_dir, "--format", "json", "--by-file", "--no-cocomo"],
            timeout=_SCC_TIMEOUT,
        )

        if result.returncode == -1 and "not found" in result.stderr.lower():
            return self._fallback_score(candidate)

        return self._parse_scc_output(result.stdout, candidate)

    def _fallback_score(self, candidate: RepoCandidate) -> ComplexityScore:
        """Fallback using GitHub API size/languages data."""
        value = 0.5  # Neutral default
        return ComplexityScore(
            value=value,
            confidence=0.3,
            details={
                "total_loc": 0,
                "languages": dict(candidate.languages),
                "file_count": 0,
                "avg_complexity": 0.0,
                "source": "fallback",
            },
            notes=["scc not available, using GitHub API data"],
        )

    def _parse_scc_output(self, stdout: str, candidate: RepoCandidate) -> ComplexityScore:
        """Parse scc JSON output."""
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return self._fallback_score(candidate)

        total_loc = 0
        language_data: dict[str, int] = {}
        total_complexity = 0.0
        file_count = 0

        for lang_data in data.values():
            if not isinstance(lang_data, dict):
                continue
            loc = int(lang_data.get("Code", 0))
            total_loc += loc
            language_data[lang_data.get("Name", "Unknown")] = loc
            total_complexity += float(lang_data.get("Complexity", 0))
            file_count += int(lang_data.get("Files", 0))

        # Size-based scoring
        if total_loc < _SMALL_PROJECT_LOC:
            value = 0.7
        elif total_loc < _MEDIUM_PROJECT_LOC:
            value = 1.0
        elif total_loc < _LARGE_PROJECT_LOC:
            value = 0.8
        else:
            value = 0.5

        # Language fragmentation penalty
        if len(language_data) > _LANGUAGE_FRAGMENTATION_THRESHOLD:
            value = max(value - 0.1, 0.1)

        avg_complexity = total_complexity / file_count if file_count > 0 else 0.0

        return ComplexityScore(
            value=value,
            confidence=1.0,
            details={
                "total_loc": total_loc,
                "languages": language_data,
                "file_count": file_count,
                "avg_complexity": avg_complexity,
                "source": "scc",
            },
        )
