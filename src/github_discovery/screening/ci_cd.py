"""CI/CD detection and scoring for Gate 1.

Detects presence of CI/CD configurations: GitHub Actions, Travis CI,
CircleCI, GitLab CI, Jenkins. Primary signal: .github/workflows/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from github_discovery.models.screening import CiCdScore

if TYPE_CHECKING:
    from github_discovery.screening.types import RepoContext

logger = structlog.get_logger("github_discovery.screening.ci_cd")

_CI_CONFIG_PATHS: dict[str, list[str]] = {
    "github_actions": [".github/workflows/"],
    "travis": [".travis.yml"],
    "circleci": [".circleci/config.yml"],
    "gitlab_ci": [".gitlab-ci.yml"],
    "jenkins": ["Jenkinsfile"],
}


def _count_workflows(contents: list[str]) -> int:
    """Count workflow files in .github/workflows/ directory."""
    count = 0
    for path in contents:
        lower = path.lower()
        if lower.startswith(".github/workflows/") and (
            lower.endswith(".yml") or lower.endswith(".yaml")
        ):
            count += 1
    return count


def _detect_ci_systems(contents: list[str]) -> list[str]:
    """Detect which CI systems are present in the repository."""
    lower_contents = {c.lower() for c in contents}
    detected: list[str] = []

    for system, paths in _CI_CONFIG_PATHS.items():
        for pattern in paths:
            # For directory-based patterns (ending with /), check prefix
            if pattern.endswith("/"):
                if any(c.lower().startswith(pattern.lower()) for c in contents):
                    detected.append(system)
                    break
            elif pattern.lower() in lower_contents:
                detected.append(system)
                break

    return detected


class CiCdDetector:
    """Detects CI/CD pipelines and evaluates their configuration.

    Primary signal: .github/workflows/ presence (most common).
    Secondary: other CI system config files.
    """

    def score(self, ctx: RepoContext) -> CiCdScore:
        """Score CI/CD pipeline presence.

        Args:
            ctx: Repository context with contents listing.

        Returns:
            CiCdScore with value 0.0-1.0 and details about detected CI systems.
        """
        contents = ctx.repo_contents
        detected = _detect_ci_systems(contents)
        workflow_count = _count_workflows(contents)

        has_github_actions = "github_actions" in detected

        # Scoring: GitHub Actions = 1.0, other CI = 0.7,
        # multiple CI systems = +0.1 bonus (capped at 1.0)
        if has_github_actions:
            value = 1.0
        elif detected:
            value = 0.7
        else:
            value = 0.0

        if len(detected) > 1:
            value = min(1.0, value + 0.1)

        details: dict[str, str | int | float | bool | None] = {
            "has_github_actions": has_github_actions,
            "workflow_count": workflow_count,
            "ci_systems": ", ".join(detected),
        }

        logger.debug(
            "ci_cd_scored",
            full_name=ctx.candidate.full_name,
            value=round(value, 4),
            detected=detected,
        )

        return CiCdScore(
            value=round(value, 4),
            details=details,
            confidence=1.0,
        )
