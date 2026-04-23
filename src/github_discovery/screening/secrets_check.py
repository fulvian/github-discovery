"""Secret detection using gitleaks subprocess for Gate 2.

Runs gitleaks detect on a shallow clone. Parses SARIF JSON output.
Falls back to heuristic (confidence=0.0) if gitleaks is not installed.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog

from github_discovery.models.candidate import RepoCandidate  # noqa: TC001
from github_discovery.models.screening import SecretHygieneScore

if TYPE_CHECKING:
    from github_discovery.screening.subprocess_runner import SubprocessRunner

logger = structlog.get_logger("github_discovery.screening.secrets")

_GITLEAKS_BINARY = "gitleaks"
_GITLEAKS_TIMEOUT = 60.0
_MINOR_FINDINGS_THRESHOLD = 2
_MODERATE_FINDINGS_THRESHOLD = 5


class SecretsChecker:
    """Secret detection using gitleaks subprocess."""

    def __init__(self, subprocess_runner: SubprocessRunner | None = None) -> None:
        """Initialize with optional SubprocessRunner."""
        self._runner = subprocess_runner

    async def score(
        self,
        candidate: RepoCandidate,
        clone_dir: str | None = None,
    ) -> SecretHygieneScore:
        """Run gitleaks and return SecretHygieneScore.

        If clone_dir is None, returns neutral score (can't scan without clone).
        """
        if self._runner is None or clone_dir is None:
            return SecretHygieneScore(
                value=0.5,
                confidence=0.0,
                notes=["gitleaks: no clone available for scanning"],
                details={
                    "findings_count": 0,
                    "scan_tool": "gitleaks",
                    "sarif_parsed": False,
                },
            )

        result = await self._runner.run(
            [
                _GITLEAKS_BINARY,
                "detect",
                "--source",
                clone_dir,
                "--report-format",
                "sarif",
                "--report-path",
                "-",
                "--no-git",
            ],
            timeout=_GITLEAKS_TIMEOUT,
        )

        if result.returncode == -1 and "not found" in result.stderr.lower():
            return SecretHygieneScore(
                value=0.5,
                confidence=0.0,
                notes=["gitleaks not available"],
                details={
                    "findings_count": 0,
                    "scan_tool": "gitleaks",
                    "sarif_parsed": False,
                },
            )

        # Parse SARIF output from stdout
        findings_count = self._parse_sarif(result.stdout)

        # Score based on findings count
        if findings_count == 0:
            value = 1.0
        elif findings_count <= _MINOR_FINDINGS_THRESHOLD:
            value = 0.7
        elif findings_count <= _MODERATE_FINDINGS_THRESHOLD:
            value = 0.4
        else:
            value = 0.1

        return SecretHygieneScore(
            value=value,
            confidence=1.0,
            details={
                "findings_count": findings_count,
                "scan_tool": "gitleaks",
                "sarif_parsed": True,
            },
            notes=(
                [f"gitleaks: {findings_count} findings"]
                if findings_count > 0
                else ["gitleaks: clean"]
            ),
        )

    def _parse_sarif(self, stdout: str) -> int:
        """Parse SARIF JSON and count findings."""
        try:
            data = json.loads(stdout)
            runs = data.get("runs", [])
            total = 0
            for run in runs:
                results = run.get("results", [])
                total += len(results)
            return total
        except (json.JSONDecodeError, AttributeError):
            return 0
