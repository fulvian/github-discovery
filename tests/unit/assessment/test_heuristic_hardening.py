"""T2.4/T2.5 — Heuristic fallback and path-based detection tests.

T2.4: HeuristicFallback model with capped confidence (ignorance signal)
T2.5: Path-based test directory detection from Repomix file headers
"""

from __future__ import annotations

from github_discovery.assessment.heuristics import (
    HeuristicAnalyzer,
    _extract_file_paths,
    _has_test_dir,
)
from github_discovery.assessment.types import HeuristicFallback


class TestHeuristicFallbackModel:
    """T2.4 — HeuristicFallback as ignorance signal."""

    def test_default_confidence_capped_low(self) -> None:
        """Default confidence is 0.15 (well below Gate 3 LLM levels)."""
        fb = HeuristicFallback()
        assert fb.confidence == 0.15

    def test_confidence_max_is_025(self) -> None:
        """Confidence cannot exceed 0.25."""
        fb = HeuristicFallback(confidence=0.25)
        assert fb.confidence == 0.25

    def test_confidence_above_025_raises(self) -> None:
        """Setting confidence > 0.25 raises ValidationError."""
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            HeuristicFallback(confidence=0.30)

    def test_default_note_warns_about_reliability(self) -> None:
        """Default note contains a cautionary warning."""
        fb = HeuristicFallback()
        assert "heuristic fallback" in fb.note.lower()
        assert "caution" in fb.note.lower()

    def test_uncertainty_range_default(self) -> None:
        """Default uncertainty range is wide (0.3, 0.7)."""
        fb = HeuristicFallback()
        assert fb.uncertainty_range == (0.3, 0.7)

    def test_point_estimate_default_neutral(self) -> None:
        """Default point estimate is 0.5 (neutral)."""
        fb = HeuristicFallback()
        assert fb.point_estimate == 0.5

    def test_presence_signals_default_empty(self) -> None:
        """Default presence signals is empty dict."""
        fb = HeuristicFallback()
        assert fb.presence_signals == {}


class TestPathBasedDetection:
    """T2.5 — Path-based test directory detection."""

    def test_extract_file_paths_from_repomix_headers(self) -> None:
        """Repomix-style file headers are correctly parsed."""
        content = (
            "================\n"
            "File: src/main.py\n"
            "================\n"
            "def main(): pass\n"
            "================\n"
            "File: tests/test_main.py\n"
            "================\n"
            "def test_main(): pass\n"
        )
        paths = _extract_file_paths(content)
        assert "src/main.py" in paths
        assert "tests/test_main.py" in paths

    def test_extract_file_paths_no_headers(self) -> None:
        """Non-Repomix content returns empty list."""
        content = "some random content\nwith no file headers"
        assert _extract_file_paths(content) == []

    def test_has_test_dir_with_tests_directory(self) -> None:
        """File under tests/ directory is detected."""
        assert _has_test_dir(["src/main.py", "tests/test_main.py"]) is True

    def test_has_test_dir_with_test_directory(self) -> None:
        """File under test/ directory is detected."""
        assert _has_test_dir(["test/app_test.go"]) is True

    def test_has_test_dir_with_spec_directory(self) -> None:
        """File under spec/ directory is detected."""
        assert _has_test_dir(["spec/my_spec.rb"]) is True

    def test_has_test_dir_no_test_dirs(self) -> None:
        """No test directories returns False."""
        assert _has_test_dir(["src/main.py", "lib/utils.py"]) is False

    def test_has_test_dir_nested_test_dir(self) -> None:
        """Nested test directory (e.g. pkg/internal/tests/) is detected."""
        assert _has_test_dir(["pkg/internal/tests/handler_test.go"]) is True

    def test_detect_tests_with_repomix_headers(self) -> None:
        """_detect_tests uses path-based detection with Repomix headers."""
        analyzer = HeuristicAnalyzer()
        content = (
            "================\n"
            "File: src/app.py\n"
            "================\n"
            "code here\n"
            "================\n"
            "File: tests/test_app.py\n"
            "================\n"
            "import pytest\n"
        )
        assert analyzer._detect_tests(content) is True

    def test_detect_tests_repomix_no_tests(self) -> None:
        """Repomix content without test directories returns False."""
        analyzer = HeuristicAnalyzer()
        content = (
            "================\n"
            "File: src/app.py\n"
            "================\n"
            "code here\n"
            "================\n"
            "File: README.md\n"
            "================\n"
            "documentation\n"
        )
        assert analyzer._detect_tests(content) is False

    def test_no_false_positive_from_readme_mention(self) -> None:
        """README mentioning 'pytest' but no test files → not detected with headers.

        T2.5 specifically targets this false positive: prose mentions of
        test frameworks should not trigger detection when file tree is available.
        """
        analyzer = HeuristicAnalyzer()
        content = (
            "================\n"
            "File: README.md\n"
            "================\n"
            "We use pytest for testing. Install with pip install pytest.\n"
        )
        # With Repomix headers and no test dirs → False (path-based wins)
        assert analyzer._detect_tests(content) is False

    def test_fallback_to_patterns_without_headers(self) -> None:
        """Without Repomix headers, pattern matching is used as fallback."""
        analyzer = HeuristicAnalyzer()
        # No headers → falls back to pattern match, "pytest" matches
        assert analyzer._detect_tests("import pytest") is True
        assert analyzer._detect_tests("tests/") is True
