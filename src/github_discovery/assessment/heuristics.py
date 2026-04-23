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

import structlog

from github_discovery.assessment.types import HeuristicScores, RepoContent

logger = structlog.get_logger(__name__)

# Patterns used for detection in packed repo content.
_TEST_PATTERNS: tuple[str, ...] = (
    "test/",
    "tests/",
    "__test__",
    "spec/",
    "pytest",
    "jest",
    "vitest",
    "unittest",
)

_CI_PATTERNS: tuple[str, ...] = (
    ".github/workflows/",
    "Jenkinsfile",
    ".gitlab-ci.yml",
    ".circleci/",
    "travis",
)

_DOC_PATTERNS: tuple[str, ...] = (
    "README",
    "docs/",
    "CONTRIBUTING",
    "CHANGELOG",
    ".rst",
)

_SECURITY_PATTERNS: tuple[str, ...] = (
    "SECURITY.md",
    ".secretsignore",
    "dependabot.yml",
    "renovate.json",
    "scorecard",
)

# Regex to extract file extensions from Repomix-style packed output.
# Matches paths like "src/foo/bar.py" or "lib/utils.ts" that appear
# in the file header lines of packed content.
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
        """Detect test infrastructure from content."""
        content_lower = content.lower()
        return any(pattern.lower() in content_lower for pattern in _TEST_PATTERNS)

    def _detect_ci(self, content: str) -> bool:
        """Detect CI/CD configuration from content."""
        content_lower = content.lower()
        return any(pattern.lower() in content_lower for pattern in _CI_PATTERNS)

    def _detect_docs(self, content: str) -> bool:
        """Detect documentation presence from content.

        Special handling for '.md' — only counts if it appears as
        part of a filename path (not just the string '.md' in prose).
        """
        content_lower = content.lower()
        for pattern in _DOC_PATTERNS:
            if pattern.lower() in content_lower:
                return True
        # Check for markdown files via extension pattern (e.g. "guide.md").
        return bool(re.search(r"\b\w+\.md\b", content_lower))

    def _detect_security(self, content: str) -> bool:
        """Detect security policy files from content."""
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
