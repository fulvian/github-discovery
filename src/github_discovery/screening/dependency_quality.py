"""Dependency management quality scorer for Gate 1.

Checks lockfile presence, dependency pinning signals, and
automated update configuration (dependabot/renovate).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from github_discovery.models.screening import DependencyQualityScore

if TYPE_CHECKING:
    from github_discovery.screening.types import RepoContext

_LOCKFILE_PATTERNS: dict[str, list[str]] = {
    "python": ["poetry.lock", "Pipfile.lock", "pdm.lock", "uv.lock"],
    "javascript": ["package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb"],
    "rust": ["Cargo.lock"],
    "go": ["go.sum"],
    "ruby": ["Gemfile.lock"],
}
_DEPENDABOT_CONFIG: list[str] = [".github/dependabot.yml", ".github/dependabot.yaml"]
_RENOVATE_CONFIG: list[str] = ["renovate.json", ".github/renovate.json", "renovate.json5"]

# Scoring weights
_WEIGHT_LOCKFILE = 0.4
_WEIGHT_AUTOMATION = 0.3
_WEIGHT_MULTI_ECOSYSTEM = 0.2
_WEIGHT_PINNING = 0.1


class DependencyQualityScorer:
    """Scores dependency management quality."""

    def score(self, ctx: RepoContext) -> DependencyQualityScore:
        """Score dependency quality based on lockfiles and update automation."""
        contents = set(ctx.repo_contents)

        # 1. Lockfile detection — check all ecosystems
        found_lockfiles: list[str] = []
        found_ecosystems: set[str] = set()

        for ecosystem, patterns in _LOCKFILE_PATTERNS.items():
            for pattern in patterns:
                if pattern in contents:
                    found_lockfiles.append(pattern)
                    found_ecosystems.add(ecosystem)

        has_lockfile = len(found_lockfiles) > 0
        is_multi_ecosystem = len(found_ecosystems) > 1

        # 2. Dependabot / renovate detection
        has_dependabot = any(path in contents for path in _DEPENDABOT_CONFIG)
        has_renovate = any(path in contents for path in _RENOVATE_CONFIG)
        has_automation = has_dependabot or has_renovate

        # 3. Pinning signals — lockfile presence is a proxy for pinning
        #    (exact pinning ratio requires deeper analysis, so we use
        #    lockfile + automation as proxy)
        has_pinning_signals = has_lockfile and has_automation

        # 4. Compute score
        score = 0.0
        notes: list[str] = []

        if has_lockfile:
            score += _WEIGHT_LOCKFILE
            notes.append(f"Lockfile(s) found: {', '.join(found_lockfiles)}")

        if has_automation:
            score += _WEIGHT_AUTOMATION
            tool = "dependabot" if has_dependabot else "renovate"
            notes.append(f"Update automation found: {tool}")

        if is_multi_ecosystem:
            score += _WEIGHT_MULTI_ECOSYSTEM
            notes.append(f"Multi-ecosystem lockfiles: {', '.join(found_ecosystems)}")

        if has_pinning_signals:
            score += _WEIGHT_PINNING
            notes.append("Pinning signals detected (lockfile + automation)")

        # Cap at 1.0
        score = min(score, 1.0)

        return DependencyQualityScore(
            value=score,
            details={
                "has_lockfile": has_lockfile,
                "lockfiles_found": found_lockfiles,
                "has_dependabot": has_dependabot,
                "has_renovate": has_renovate,
                "multi_ecosystem": is_multi_ecosystem,
            },
            confidence=1.0,
            notes=notes,
        )
