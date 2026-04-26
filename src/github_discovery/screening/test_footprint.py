"""Test footprint analyzer for Gate 1.

Detects test directories, test file patterns, test configuration
files, and estimates test/source file ratio from contents listing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from github_discovery.models.screening import TestFootprintScore

if TYPE_CHECKING:
    from github_discovery.screening.types import RepoContext

logger = structlog.get_logger("github_discovery.screening.test_footprint")

_TEST_DIR_PATTERNS: list[str] = ["test", "tests", "spec", "specs", "__tests__"]
_TEST_FILE_PATTERNS: list[str] = ["test_", "_test.", "_spec.", ".test.", ".spec."]
_TEST_CONFIG_FILES: list[str] = [
    "pytest.ini",
    "pyproject.toml",
    "setup.cfg",
    "conftest.py",
    "jest.config.js",
    "jest.config.ts",
    ".mocharc.yml",
    ".mocharc.json",
    "vitest.config.ts",
    "Cargo.toml",
]

# Framework detection by config file presence
_FRAMEWORK_MAP: dict[str, str] = {
    "pytest.ini": "pytest",
    "conftest.py": "pytest",
    "jest.config.js": "jest",
    "jest.config.ts": "jest",
    ".mocharc.yml": "mocha",
    ".mocharc.json": "mocha",
    "vitest.config.ts": "vitest",
}


def _has_test_dir(contents: list[str]) -> bool:
    """Check if any top-level test directory exists in contents."""
    for pattern in _TEST_DIR_PATTERNS:
        for path in contents:
            # Match top-level dir: "tests/" or "tests/subfile.py"
            lower = path.lower()
            if lower == pattern or lower.startswith(pattern + "/"):
                return True
    return False


def _detect_frameworks(contents: list[str]) -> list[str]:
    """Detect test frameworks from config files."""
    lower_contents = {c.lower() for c in contents}
    frameworks: list[str] = []

    for config_file, framework in _FRAMEWORK_MAP.items():
        if config_file.lower() in lower_contents and framework not in frameworks:
            frameworks.append(framework)

    # pyproject.toml and setup.cfg can contain pytest config
    # (heuristic: assume pytest if present and test dir exists)
    if (
        "pytest" not in frameworks
        and _has_test_dir(contents)
        and ("pyproject.toml" in lower_contents or "setup.cfg" in lower_contents)
    ):
        frameworks.append("pytest")

    return frameworks


def _has_conftest(contents: list[str]) -> bool:
    """Check if conftest.py is present anywhere in contents."""
    return any("conftest.py" in c.lower() for c in contents)


def _compute_test_file_ratio(contents: list[str]) -> float:
    """Estimate test-to-source file ratio from contents listing.

    Counts files matching test patterns and divides by total files.
    """
    if not contents:
        return 0.0

    test_files = 0
    for path in contents:
        lower = path.lower()
        for pattern in _TEST_FILE_PATTERNS:
            if pattern in lower:
                test_files += 1
                break

    total = len(contents)
    return test_files / total if total > 0 else 0.0


_TEST_FILE_RATIO_LOW = 0.1
_TEST_FILE_RATIO_HIGH = 0.3


class TestFootprintAnalyzer:
    """Analyzes test infrastructure presence and coverage indicators."""

    def score(self, ctx: RepoContext) -> TestFootprintScore:
        """Score test infrastructure from repo contents listing.

        Scoring breakdown:
        - test_dir_present: +0.3
        - test_config found: +0.3
        - test_file_ratio > 0.1: +0.2
        - test_file_ratio > 0.3: +0.2 (bonus)

        Args:
            ctx: Repository context with contents listing.

        Returns:
            TestFootprintScore with value 0.0-1.0 and details.
        """
        contents = ctx.repo_contents

        has_test_dir = _has_test_dir(contents)
        frameworks = _detect_frameworks(contents)
        test_file_ratio = _compute_test_file_ratio(contents)
        has_conftest_val = _has_conftest(contents)

        # Check for any test config file presence
        lower_contents = {c.lower() for c in contents}
        has_test_config = any(cfg.lower() in lower_contents for cfg in _TEST_CONFIG_FILES)

        # Compute score
        score_val = 0.0
        if has_test_dir:
            score_val += 0.3
        if has_test_config:
            score_val += 0.3
        if test_file_ratio > _TEST_FILE_RATIO_LOW:
            score_val += 0.2
        if test_file_ratio > _TEST_FILE_RATIO_HIGH:
            score_val += 0.2

        score_val = min(1.0, score_val)

        details: dict[str, str | int | float | bool | None] = {
            "has_test_dir": has_test_dir,
            "test_frameworks": ", ".join(frameworks),
            "test_file_ratio": round(test_file_ratio, 4),
            "has_conftest": has_conftest_val,
        }

        logger.debug(
            "test_footprint_scored",
            full_name=ctx.candidate.full_name,
            value=round(score_val, 4),
            has_test_dir=has_test_dir,
            frameworks=frameworks,
        )

        return TestFootprintScore(
            value=round(score_val, 4),
            details=details,
            confidence=1.0,
        )
