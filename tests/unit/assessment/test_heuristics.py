"""Tests for HeuristicAnalyzer — non-LLM heuristic scoring.

Tests all detection methods, structure score computation,
size categorization, and language detection.
"""

from __future__ import annotations

from github_discovery.assessment.heuristics import HeuristicAnalyzer
from github_discovery.assessment.types import HeuristicScores, RepoContent


class TestDetectTests:
    """Tests for HeuristicAnalyzer._detect_tests."""

    def test_detects_test_directory(self) -> None:
        """Content with 'test/' pattern is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_tests("some test/ file content") is True

    def test_detects_tests_directory(self) -> None:
        """Content with 'tests/' pattern is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_tests("some tests/ file content") is True

    def test_detects_pytest_framework(self) -> None:
        """Content mentioning pytest is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_tests("import pytest") is True

    def test_detects_jest_framework(self) -> None:
        """Content mentioning jest is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_tests("jest.mock('module')") is True

    def test_detects_vitest_framework(self) -> None:
        """Content mentioning vitest is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_tests("import { test } from 'vitest'") is True

    def test_detects_unittest_framework(self) -> None:
        """Content mentioning unittest is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_tests("import unittest") is True

    def test_detects_spec_directory(self) -> None:
        """Content with 'spec/' pattern is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_tests("spec/my_spec.rb") is True

    def test_detects_dunder_test(self) -> None:
        """Content with '__test__' pattern is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_tests("__test__ module") is True

    def test_no_tests_detected(self) -> None:
        """Content without test patterns returns False."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_tests("just regular code here") is False

    def test_case_insensitive_detection(self) -> None:
        """Test detection is case-insensitive."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_tests("Pytest configuration") is True
        assert analyzer._detect_tests("JEST config") is True


class TestDetectCI:
    """Tests for HeuristicAnalyzer._detect_ci."""

    def test_detects_github_actions(self) -> None:
        """Content with '.github/workflows/' is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_ci(".github/workflows/ci.yml") is True

    def test_detects_jenkinsfile(self) -> None:
        """Content with 'Jenkinsfile' is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_ci("Jenkinsfile content") is True

    def test_detects_gitlab_ci(self) -> None:
        """Content with '.gitlab-ci.yml' is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_ci(".gitlab-ci.yml") is True

    def test_detects_circleci(self) -> None:
        """Content with '.circleci/' is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_ci(".circleci/config.yml") is True

    def test_detects_travis(self) -> None:
        """Content with 'travis' is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_ci("travis-ci configuration") is True

    def test_no_ci_detected(self) -> None:
        """Content without CI patterns returns False."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_ci("just source code") is False


class TestDetectDocs:
    """Tests for HeuristicAnalyzer._detect_docs."""

    def test_detects_readme(self) -> None:
        """Content with 'README' is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_docs("README.md content") is True

    def test_detects_docs_directory(self) -> None:
        """Content with 'docs/' is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_docs("docs/index.md") is True

    def test_detects_contributing(self) -> None:
        """Content with 'CONTRIBUTING' is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_docs("CONTRIBUTING.md") is True

    def test_detects_changelog(self) -> None:
        """Content with 'CHANGELOG' is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_docs("CHANGELOG.md") is True

    def test_detects_rst_extension(self) -> None:
        """Content with '.rst' is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_docs("docs/index.rst") is True

    def test_detects_markdown_file(self) -> None:
        """Content with markdown file extension is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_docs("guide.md") is True

    def test_no_docs_detected(self) -> None:
        """Content without doc patterns returns False."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_docs("just source code") is False

    def test_md_in_prose_not_detected(self) -> None:
        """Bare '.md' in prose text without word boundary is not a doc signal."""
        analyzer = HeuristicAnalyzer()
        # The regex requires word boundary: \b\w+\.md\b
        # "random.md" should match, but isolated ".md" may or may not
        result = analyzer._detect_docs("the extension .md is common")
        # This tests the word boundary logic — ".md" alone has no \w+ before it
        assert result is False


class TestDetectSecurity:
    """Tests for HeuristicAnalyzer._detect_security."""

    def test_detects_security_md(self) -> None:
        """Content with 'SECURITY.md' is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_security("SECURITY.md") is True

    def test_detects_secretsignore(self) -> None:
        """Content with '.secretsignore' is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_security(".secretsignore") is True

    def test_detects_dependabot(self) -> None:
        """Content with 'dependabot.yml' is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_security("dependabot.yml") is True

    def test_detects_renovate(self) -> None:
        """Content with 'renovate.json' is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_security("renovate.json") is True

    def test_detects_scorecard(self) -> None:
        """Content with 'scorecard' is detected."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_security("scorecard check") is True

    def test_no_security_detected(self) -> None:
        """Content without security patterns returns False."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._detect_security("just code") is False


class TestComputeStructureScore:
    """Tests for HeuristicAnalyzer._compute_structure_score."""

    def test_all_signals_present_max_score(self) -> None:
        """All 6 signals present → score = 0.2+0.2+0.15+0.15+0.15+0.15 = 1.0."""
        analyzer = HeuristicAnalyzer()
        content = (
            "tests/test_main.py pytest\n"
            ".github/workflows/ci.yml\n"
            "README.md\n"
            "SECURITY.md\n"
            "src/main.py\n"
        )
        # All signals: tests (+0.2), ci (+0.2), docs (+0.15), security (+0.15),
        # file_count in range (+0.15), src/ present (+0.15) = 1.0
        score = analyzer._compute_structure_score(content, file_count=50)
        assert score == 1.0

    def test_no_signals_min_score(self) -> None:
        """No signals → score = 0.0."""
        analyzer = HeuristicAnalyzer()
        score = analyzer._compute_structure_score("plain text", file_count=5)
        assert score == 0.0

    def test_only_tests_signal(self) -> None:
        """Only tests detected → score = 0.2."""
        analyzer = HeuristicAnalyzer()
        score = analyzer._compute_structure_score("pytest test", file_count=5)
        assert abs(score - 0.2) < 0.001

    def test_only_ci_signal(self) -> None:
        """Only CI detected → score = 0.2."""
        analyzer = HeuristicAnalyzer()
        score = analyzer._compute_structure_score(".github/workflows/ci.yml", file_count=5)
        assert abs(score - 0.2) < 0.001

    def test_file_count_in_range_adds_score(self) -> None:
        """File count in 10-500 range adds 0.15."""
        analyzer = HeuristicAnalyzer()
        # Only file count in range, nothing else
        score = analyzer._compute_structure_score("plain text", file_count=50)
        assert abs(score - 0.15) < 0.001

    def test_file_count_below_range_no_bonus(self) -> None:
        """File count below 10 does not add file count bonus."""
        analyzer = HeuristicAnalyzer()
        score = analyzer._compute_structure_score("plain text", file_count=5)
        assert score == 0.0

    def test_file_count_above_range_no_bonus(self) -> None:
        """File count above 500 does not add file count bonus."""
        analyzer = HeuristicAnalyzer()
        score = analyzer._compute_structure_score("plain text", file_count=600)
        assert score == 0.0

    def test_src_structure_adds_score(self) -> None:
        """Content with 'src/' adds 0.15."""
        analyzer = HeuristicAnalyzer()
        score = analyzer._compute_structure_score("src/main.py", file_count=5)
        assert abs(score - 0.15) < 0.001

    def test_lib_structure_adds_score(self) -> None:
        """Content with 'lib/' adds 0.15."""
        analyzer = HeuristicAnalyzer()
        score = analyzer._compute_structure_score("lib/utils.py", file_count=5)
        assert abs(score - 0.15) < 0.001

    def test_score_clamped_to_one(self) -> None:
        """Score is clamped to 1.0 even if sum exceeds it."""
        analyzer = HeuristicAnalyzer()
        # All signals present — already exactly 1.0, no overflow
        content = "tests/ pytest .github/workflows/ README.md SECURITY.md src/"
        score = analyzer._compute_structure_score(content, file_count=100)
        assert score <= 1.0


class TestCategorizeSize:
    """Tests for HeuristicAnalyzer._categorize_size."""

    def test_tiny_below_10(self) -> None:
        """file_count < 10 → 'tiny'."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._categorize_size(0) == "tiny"
        assert analyzer._categorize_size(5) == "tiny"
        assert analyzer._categorize_size(9) == "tiny"

    def test_small_10_to_49(self) -> None:
        """file_count 10-49 → 'small'."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._categorize_size(10) == "small"
        assert analyzer._categorize_size(25) == "small"
        assert analyzer._categorize_size(49) == "small"

    def test_medium_50_to_199(self) -> None:
        """file_count 50-199 → 'medium'."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._categorize_size(50) == "medium"
        assert analyzer._categorize_size(100) == "medium"
        assert analyzer._categorize_size(199) == "medium"

    def test_large_200_to_999(self) -> None:
        """file_count 200-999 → 'large'."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._categorize_size(200) == "large"
        assert analyzer._categorize_size(500) == "large"
        assert analyzer._categorize_size(999) == "large"

    def test_huge_1000_plus(self) -> None:
        """file_count >= 1000 → 'huge'."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._categorize_size(1000) == "huge"
        assert analyzer._categorize_size(5000) == "huge"

    def test_boundary_values(self) -> None:
        """Boundary values between categories are correct."""
        analyzer = HeuristicAnalyzer()
        assert analyzer._categorize_size(9) == "tiny"
        assert analyzer._categorize_size(10) == "small"
        assert analyzer._categorize_size(49) == "small"
        assert analyzer._categorize_size(50) == "medium"
        assert analyzer._categorize_size(199) == "medium"
        assert analyzer._categorize_size(200) == "large"
        assert analyzer._categorize_size(999) == "large"
        assert analyzer._categorize_size(1000) == "huge"


class TestDetectLanguages:
    """Tests for HeuristicAnalyzer._detect_languages."""

    def test_detects_python_files(self) -> None:
        """Python .py files are detected and tallied."""
        analyzer = HeuristicAnalyzer()
        content = "src/main.py\nsrc/utils.py\nsrc/helper.py"
        dist = analyzer._detect_languages(content)

        assert "Python" in dist
        assert dist["Python"] == 3

    def test_detects_typescript_files(self) -> None:
        """TypeScript .ts and .tsx files are detected."""
        analyzer = HeuristicAnalyzer()
        content = "src/app.tsx\nsrc/hooks.ts"
        dist = analyzer._detect_languages(content)

        assert "TypeScript" in dist
        assert dist["TypeScript"] == 2

    def test_detects_javascript_files(self) -> None:
        """JavaScript .js and .jsx files are detected."""
        analyzer = HeuristicAnalyzer()
        content = "src/index.js\nsrc/component.jsx"
        dist = analyzer._detect_languages(content)

        assert "JavaScript" in dist
        assert dist["JavaScript"] == 2

    def test_detects_rust_files(self) -> None:
        """Rust .rs files are detected."""
        analyzer = HeuristicAnalyzer()
        content = "src/main.rs\nsrc/lib.rs"
        dist = analyzer._detect_languages(content)

        assert "Rust" in dist
        assert dist["Rust"] == 2

    def test_detects_go_files(self) -> None:
        """Go .go files are detected."""
        analyzer = HeuristicAnalyzer()
        content = "main.go\npkg/handler.go"
        dist = analyzer._detect_languages(content)

        assert "Go" in dist
        assert dist["Go"] == 2

    def test_detects_mixed_languages(self) -> None:
        """Multiple languages are detected in mixed content."""
        analyzer = HeuristicAnalyzer()
        content = "src/app.py\nsrc/utils.ts\nsrc/handler.go\nREADME.md"
        dist = analyzer._detect_languages(content)

        assert "Python" in dist
        assert "TypeScript" in dist
        assert "Go" in dist

    def test_no_language_files(self) -> None:
        """Content without code files returns empty distribution."""
        analyzer = HeuristicAnalyzer()
        dist = analyzer._detect_languages("just plain text no files")

        assert dist == {}

    def test_empty_content(self) -> None:
        """Empty content returns empty distribution."""
        analyzer = HeuristicAnalyzer()
        dist = analyzer._detect_languages("")

        assert dist == {}


class TestAnalyze:
    """Tests for HeuristicAnalyzer.analyze — end-to-end."""

    def test_analyze_with_sample_repo_content(
        self,
        sample_repo_content: RepoContent,
    ) -> None:
        """analyze() returns HeuristicScores from RepoContent."""
        analyzer = HeuristicAnalyzer()
        scores = analyzer.analyze(sample_repo_content)

        assert isinstance(scores, HeuristicScores)
        assert scores.full_name == "test/awesome-lib"
        assert scores.file_count == 10
        assert scores.has_tests is True  # "tests/" in content
        assert scores.size_category == "small"  # 10 files → small

    def test_analyze_empty_content(self) -> None:
        """analyze() handles empty content gracefully."""
        analyzer = HeuristicAnalyzer()
        content = RepoContent(
            full_name="test/empty",
            content="",
            total_files=0,
        )
        scores = analyzer.analyze(content)

        assert scores.full_name == "test/empty"
        assert scores.has_tests is False
        assert scores.has_ci is False
        assert scores.has_docs is False
        assert scores.has_security_policy is False
        assert scores.structure_score == 0.0
        assert scores.size_category == "tiny"
        assert scores.language_distribution == {}

    def test_analyze_full_featured_repo(self) -> None:
        """analyze() with rich content detects all signals."""
        analyzer = HeuristicAnalyzer()
        content = RepoContent(
            full_name="test/rich-repo",
            content=(
                "src/main.py\ndef main(): pass\n"
                "tests/test_main.py\nimport pytest\n"
                ".github/workflows/ci.yml\n"
                "README.md\n"
                "SECURITY.md\n"
                "dependabot.yml\n"
            ),
            total_files=50,
        )
        scores = analyzer.analyze(content)

        assert scores.has_tests is True
        assert scores.has_ci is True
        assert scores.has_docs is True
        assert scores.has_security_policy is True
        assert scores.structure_score > 0.0
        assert scores.size_category == "medium"
