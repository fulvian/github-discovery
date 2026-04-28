"""Non-LLM heuristic scoring from packed repo content.

Provides fast, zero-cost baseline scores from structural analysis
of packed repository content. Used as:
1. Baseline before LLM assessment (Gate 3)
2. Fallback when LLM fails or budget is exceeded

All detection methods are pure functions operating on the packed
content string — no side effects, no I/O, no LLM calls.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

import structlog

from github_discovery.assessment.types import HeuristicScores, RepoContent

logger = structlog.get_logger(__name__)

# Patterns used for detection in packed repo content.
# Framework names — detected via substring match in content.
_TEST_FRAMEWORK_PATTERNS: tuple[str, ...] = (
    "pytest",
    "jest",
    "vitest",
    "unittest",
    "mocha",
)

# Directory path patterns — detected via substring match as fallback
# when Repomix file headers are not available.
_TEST_DIR_PATTERNS: tuple[str, ...] = (
    "test/",
    "tests/",
    "__tests__",
    "spec/",
    "specs/",
)

_CI_PATTERNS: tuple[str, ...] = (
    ".github/workflows/",
    "Jenkinsfile",
    ".gitlab-ci.yml",
    ".circleci/",
    "travis",
)

# TD1: Path-based patterns — used as primary detection when file_paths available.
_CI_PATH_PATTERNS: tuple[str, ...] = (
    ".github/workflows/",
    "Jenkinsfile",
    ".gitlab-ci.yml",
    ".circleci/config",
    "azure-pipelines.yml",
    "bitbucket-pipelines.yml",
)

_DOC_PATTERNS: tuple[str, ...] = (
    "README",
    "docs/",
    "CONTRIBUTING",
    "CHANGELOG",
    ".rst",
)

# TD2: Path-based patterns for docs detection.
_DOC_PATH_PATTERNS: tuple[str, ...] = (
    "README.md",
    "README.rst",
    "README.txt",
    "docs/",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "CHANGELOG.rst",
)

_SECURITY_PATTERNS: tuple[str, ...] = (
    "SECURITY.md",
    ".secretsignore",
    "dependabot.yml",
    "renovate.json",
    "scorecard",
    "openssf",
)

# TD2: Path-based patterns for security detection.
_SECURITY_PATH_PATTERNS: tuple[str, ...] = (
    "SECURITY.md",
    ".github/dependabot.yml",
    ".github/renovate.json",
    "renovate.json",
    ".snyk",
    "renovate.bot.json",
)

# Directories that typically contain test files.
_TEST_DIRS: frozenset[str] = frozenset(
    {
        "tests",
        "test",
        "__tests__",
        "spec",
        "specs",
        "testing",
    }
)

# Regex to extract file paths from Repomix-style packed output.
# Matches header lines like: "==== File: src/foo/bar.py ===="
_REPOMIX_FILE_HEADER_RE: re.Pattern[str] = re.compile(
    r"^={4,}\s*(?:File:\s*|file:\s*)(\S+)",
    re.MULTILINE,
)

# Regex to extract file extensions from Repomix-style packed output.
_EXTENSION_RE: re.Pattern[str] = re.compile(
    r"(?:^|[\s/])([\w.-]+\.(py|ts|tsx|js|jsx|rs|go|java|rb|php|c|cpp|h|hpp|"
    r"cs|swift|kt|scala|sh|bash|yaml|yml|json|toml|xml|html|css|scss|md|rst))",
    re.MULTILINE,
)

# Language mapping from file extension to canonical name.
_EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".rs": "Rust",
    ".go": "Go",
    ".java": "Java",
    ".rb": "Ruby",
    ".php": "PHP",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".cs": "C#",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".sh": "Shell",
    ".bash": "Shell",
}

# File-count thresholds for size categorization and structure scoring.
_REASONABLE_FILE_COUNT_MIN = 10
_REASONABLE_FILE_COUNT_MAX = 500
_SIZE_TINY = 10
_SIZE_SMALL = 50
_SIZE_MEDIUM = 200
_SIZE_LARGE = 1000


def _extract_file_paths(packed: str) -> list[str]:
    """Extract file paths from Repomix-style packed output headers.

    Matches lines like: ``==== File: src/foo/bar.py ====``
    Returns an empty list if no file headers are found (non-Repomix content).
    """
    return _REPOMIX_FILE_HEADER_RE.findall(packed)


def _has_test_dir(file_paths: list[str]) -> bool:
    """Check whether any file path is inside a known test directory.

    Uses path-based detection (T2.5) to avoid false positives
    from prose mentions of test frameworks in README files.
    """
    for path_str in file_paths:
        try:
            parts = PurePosixPath(path_str).parts
        except ValueError:
            continue
        for part in parts:
            if part.lower() in _TEST_DIRS:
                return True
    return False


class HeuristicAnalyzer:
    """Non-LLM code structure scoring from packed repo content.

    Provides fast, zero-cost baseline scores from structural
    analysis of packed repository content. Used as:
    1. Baseline before LLM assessment
    2. Fallback when LLM fails or budget exceeded
    """

    def analyze(self, content: RepoContent) -> HeuristicScores:
        """Analyze packed repo content for structural quality signals.

        Args:
            content: Packed repo content from RepomixAdapter

        Returns:
            HeuristicScores with detected signals
        """
        packed_text = content.content
        file_count = content.total_files

        has_tests = self._detect_tests(packed_text)
        has_ci = self._detect_ci(packed_text)
        has_docs = self._detect_docs(packed_text)
        has_security = self._detect_security(packed_text)
        language_distribution = self._detect_languages(packed_text)
        structure_score = self._compute_structure_score(
            packed_text,
            file_count,
        )
        size_category = self._categorize_size(file_count)

        logger.debug(
            "heuristic_analysis_complete",
            full_name=content.full_name,
            has_tests=has_tests,
            has_ci=has_ci,
            has_docs=has_docs,
            has_security=has_security,
            structure_score=structure_score,
            size_category=size_category,
        )

        return HeuristicScores(
            full_name=content.full_name,
            file_count=file_count,
            has_tests=has_tests,
            has_ci=has_ci,
            has_docs=has_docs,
            has_security_policy=has_security,
            language_distribution=language_distribution,
            structure_score=structure_score,
            size_category=size_category,
        )

    def _detect_tests(self, content: str) -> bool:
        """Detect test infrastructure from content.

        Uses path-based detection (T2.5): first checks for test
        directories in the file tree, then falls back to pattern
        matching for test framework names and directory paths.
        """
        # Path-based: check if any file path is inside a test directory
        file_paths = _extract_file_paths(content)
        if file_paths:
            return _has_test_dir(file_paths)

        # Fallback: pattern matching in content (legacy behavior)
        content_lower = content.lower()
        if any(p.lower() in content_lower for p in _TEST_FRAMEWORK_PATTERNS):
            return True
        return any(p.lower() in content_lower for p in _TEST_DIR_PATTERNS)

    def _detect_ci(self, content: str) -> bool:
        """Detect CI/CD configuration from content.

        TD1: Uses path-based detection as primary (authoritative when file
        paths are available from Repomix headers). Falls back to content
        substring match when no file headers are found.
        """
        file_paths = _extract_file_paths(content)
        if file_paths:
            # Path-based detection is authoritative — avoids false
            # positives from "GitHub Actions" appearing in prose.
            for path_str in file_paths:
                for pattern in _CI_PATH_PATTERNS:
                    if pattern in path_str:
                        return True
            return False
        # Legacy fallback when Repomix file headers are not available.
        content_lower = content.lower()
        return any(pattern.lower() in content_lower for pattern in _CI_PATTERNS)

    def _detect_docs(self, content: str) -> bool:
        """Detect documentation presence from content.

        TD2: Uses path-based detection as primary. Falls back to content
        substring match when no file headers are available.

        Special handling for '.md' — only counts if it appears as
        part of a filename path (not just the string '.md' in prose).
        """
        file_paths = _extract_file_paths(content)
        if file_paths:
            for path_str in file_paths:
                for pattern in _DOC_PATH_PATTERNS:
                    if pattern in path_str:
                        return True
            return False
        # Legacy fallback: content substring match.
        content_lower = content.lower()
        for pattern in _DOC_PATTERNS:
            if pattern.lower() in content_lower:
                return True
        # Check for markdown files via extension pattern (e.g. "guide.md").
        return bool(re.search(r"\b\w+\.md\b", content_lower))

    def _detect_security(self, content: str) -> bool:
        """Detect security policy files from content.

        TD2: Uses path-based detection as primary (authoritative when file
        paths are available). Falls back to content substring match.
        """
        file_paths = _extract_file_paths(content)
        if file_paths:
            for path_str in file_paths:
                for pattern in _SECURITY_PATH_PATTERNS:
                    if pattern in path_str:
                        return True
            return False
        content_lower = content.lower()
        return any(pattern.lower() in content_lower for pattern in _SECURITY_PATTERNS)

    def _compute_structure_score(self, content: str, file_count: int) -> float:
        """Compute heuristic structure quality score.

        Based on:
        - Has tests: +0.2
        - Has CI: +0.2
        - Has docs: +0.15
        - Has security: +0.15
        - File count in reasonable range (10-500): +0.15
        - Has src/ or lib/ structure: +0.15
        """
        score = 0.0

        if self._detect_tests(content):
            score += 0.2
        if self._detect_ci(content):
            score += 0.2
        if self._detect_docs(content):
            score += 0.15
        if self._detect_security(content):
            score += 0.15
        if _REASONABLE_FILE_COUNT_MIN <= file_count <= _REASONABLE_FILE_COUNT_MAX:
            score += 0.15
        if "src/" in content or "lib/" in content:
            score += 0.15

        # Clamp to [0.0, 1.0]
        return min(max(score, 0.0), 1.0)

    def _categorize_size(self, file_count: int) -> str:
        """Categorize repo size by file count.

        tiny: <10 files, small: 10-50, medium: 50-200,
        large: 200-1000, huge: >1000
        """
        if file_count < _SIZE_TINY:
            return "tiny"
        if file_count < _SIZE_SMALL:
            return "small"
        if file_count < _SIZE_MEDIUM:
            return "medium"
        if file_count < _SIZE_LARGE:
            return "large"
        return "huge"

    def _detect_languages(self, content: str) -> dict[str, int]:
        """Detect language distribution from file extensions in content.

        Looks for common file path patterns in packed output and
        tallies per-language counts using the extension-to-language
        mapping.
        """
        distribution: dict[str, int] = {}

        for match in _EXTENSION_RE.finditer(content):
            filepath = match.group(1)
            # Extract extension from the matched filename.
            dot_index = filepath.rfind(".")
            if dot_index == -1:
                continue
            ext = filepath[dot_index:]
            language = _EXTENSION_TO_LANGUAGE.get(ext)
            if language is not None:
                distribution[language] = distribution.get(language, 0) + 1

        return distribution
