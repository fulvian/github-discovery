"""Repository hygiene files checker for Gate 1.

Checks presence and quality of LICENSE, CONTRIBUTING.md,
CODE_OF_CONDUCT.md, SECURITY.md, CHANGELOG.md, README.md.
Uses repo contents listing (already in RepoContext).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from github_discovery.models.screening import HygieneScore

if TYPE_CHECKING:
    from github_discovery.screening.types import RepoContext

logger = structlog.get_logger("github_discovery.screening.hygiene")

_HYGIENE_FILES: dict[str, dict[str, object]] = {
    "license": {
        "paths": ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"],
        "weight": 0.25,
        "required": True,
    },
    "readme": {
        "paths": ["README.md", "README.rst", "README.txt", "README"],
        "weight": 0.20,
        "required": True,
    },
    "contributing": {
        "paths": ["CONTRIBUTING.md", "CONTRIBUTING.rst", ".github/CONTRIBUTING.md"],
        "weight": 0.15,
        "required": False,
    },
    "code_of_conduct": {
        "paths": ["CODE_OF_CONDUCT.md", ".github/CODE_OF_CONDUCT.md"],
        "weight": 0.10,
        "required": False,
    },
    "security": {
        "paths": ["SECURITY.md", ".github/SECURITY.md", "SECURITY.txt"],
        "weight": 0.15,
        "required": False,
    },
    "changelog": {
        "paths": ["CHANGELOG.md", "CHANGELOG.rst", "CHANGES.md", "HISTORY.md"],
        "weight": 0.15,
        "required": False,
    },
}


def _file_present(expected_paths: list[str], contents: list[str]) -> bool:
    """Check if any expected path exists in contents (case-insensitive)."""
    lower_contents = {c.lower() for c in contents}
    return any(p.lower() in lower_contents for p in expected_paths)


def _license_quality(ctx: RepoContext) -> float:
    """Evaluate LICENSE quality based on SPDX validation.

    Returns:
        1.0 if valid SPDX license found, 0.5 if file present but no
        valid SPDX, 0.0 if not present.
    """
    paths = _HYGIENE_FILES["license"]["paths"]
    if not isinstance(paths, list):
        return 0.0

    if not _file_present(paths, ctx.repo_contents):
        return 0.0

    license_info = ctx.candidate.license_info
    if license_info is None:
        return 0.5

    spdx_id = license_info.get("spdx_id")
    if spdx_id is not None and spdx_id != "NOASSERTION":
        return 1.0

    return 0.5


class HygieneChecker:
    """Checks presence and quality of repository hygiene files.

    Uses repo_contents listing to detect files. LICENSE gets additional
    SPDX validation via candidate.license_info. README gets a
    presence check (content size not available from listing alone).
    """

    def score(self, ctx: RepoContext) -> HygieneScore:
        """Score hygiene files presence and quality.

        Args:
            ctx: Repository context with contents listing and metadata.

        Returns:
            HygieneScore with value 0.0-1.0 and details about which files found.
        """
        contents = ctx.repo_contents
        details: dict[str, object] = {}
        weighted_sum = 0.0
        total_weight = sum(
            float(cfg["weight"])  # type: ignore[arg-type, misc]
            for cfg in _HYGIENE_FILES.values()
        )

        # LICENSE — special quality logic
        license_paths = _HYGIENE_FILES["license"]["paths"]
        if not isinstance(license_paths, list):
            license_paths = []
        license_present = _file_present(license_paths, contents)
        details["license"] = license_present

        license_quality = _license_quality(ctx)
        license_weight = float(_HYGIENE_FILES["license"]["weight"])  # type: ignore[arg-type]
        weighted_sum += license_weight * license_quality

        # All other hygiene files — presence = quality 1.0
        for file_type, cfg in _HYGIENE_FILES.items():
            if file_type == "license":
                continue

            paths = cfg["paths"]
            if not isinstance(paths, list):
                paths = []
            present = _file_present(paths, contents)
            details[file_type] = present

            weight = float(cfg["weight"])  # type: ignore[arg-type]
            quality = 1.0 if present else 0.0
            weighted_sum += weight * quality

        value = weighted_sum / total_weight if total_weight > 0 else 0.0
        confidence = 1.0 if contents else 0.5

        logger.debug(
            "hygiene_scored",
            full_name=ctx.candidate.full_name,
            value=round(value, 4),
            details=details,
        )

        return HygieneScore(
            value=round(value, 4),
            details=details,
            confidence=confidence,
        )
