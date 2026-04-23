"""Tests for issue/PR practices scorer."""

from __future__ import annotations

from github_discovery.models.candidate import RepoCandidate
from github_discovery.screening.practices import PracticesScorer
from github_discovery.screening.types import RepoContext


class TestPractices:
    """Tests for PracticesScorer."""

    def test_templates_detected(self, sample_repo_context: RepoContext) -> None:
        """PR and issue templates are detected from repo contents."""
        scorer = PracticesScorer()
        result = scorer.score(sample_repo_context)

        assert result.details["has_pr_template"] is True
        assert result.details["has_issue_template"] is True
        # Templates contribute 0.3 weight
        assert result.value > 0.0

    def test_review_presence_scored(self, sample_repo_context: RepoContext) -> None:
        """PRs with review comments or reviewers contribute to score."""
        scorer = PracticesScorer()
        result = scorer.score(sample_repo_context)

        assert "review_rate" in result.details
        assert isinstance(result.details["review_rate"], float)
        # Sample PRs have review_comments on every 3rd PR and
        # requested_reviewers on every 4th, so review_rate > 0
        assert result.details["review_rate"] > 0.0

    def test_label_usage_scored(self, sample_repo_context: RepoContext) -> None:
        """Issues and PRs with labels contribute to score."""
        scorer = PracticesScorer()
        result = scorer.score(sample_repo_context)

        assert "label_usage" in result.details
        assert isinstance(result.details["label_usage"], float)
        # Sample data: issues with labels every 3rd, PRs every 2nd
        assert result.details["label_usage"] > 0.0

    def test_no_practices(self, sample_candidate: RepoCandidate) -> None:
        """No templates, no reviews, no labels produces low score."""
        ctx = RepoContext(
            candidate=sample_candidate,
            repo_contents=["README.md", "main.py"],
            recent_prs=[
                {
                    "number": 1,
                    "review_comments": 0,
                    "requested_reviewers": [],
                    "labels": [],
                },
            ],
            recent_issues=[
                {
                    "number": 1,
                    "labels": [],
                },
            ],
        )
        scorer = PracticesScorer()
        result = scorer.score(ctx)

        assert result.details["has_pr_template"] is False
        assert result.details["has_issue_template"] is False
        assert result.details["review_rate"] == 0.0
        assert result.details["label_usage"] == 0.0
        assert result.value == 0.0

    def test_details_report_signals(self, sample_repo_context: RepoContext) -> None:
        """Score details contain all expected signal keys."""
        scorer = PracticesScorer()
        result = scorer.score(sample_repo_context)

        assert "has_pr_template" in result.details
        assert "has_issue_template" in result.details
        assert "review_rate" in result.details
        assert "label_usage" in result.details
