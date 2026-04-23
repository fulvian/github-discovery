"""Tests for maintenance signal analyzer."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from github_discovery.models.candidate import RepoCandidate
from github_discovery.screening.maintenance import MaintenanceAnalyzer
from github_discovery.screening.types import RepoContext


class TestMaintenance:
    """Tests for MaintenanceAnalyzer."""

    def test_active_repo_score(self, sample_candidate: RepoCandidate) -> None:
        """Active repo with recent commits gets high score."""
        now = datetime.now(UTC)
        authors = ["dev1", "dev2", "dev3", "dev4", "dev5"]
        commits = [
            {
                "sha": f"abc{i:04d}",
                "commit": {
                    "author": {
                        "name": authors[i % len(authors)],
                        "email": f"{authors[i % len(authors)]}@example.com",
                        "date": (now - timedelta(days=i)).isoformat(),
                    },
                    "message": f"Commit {i}",
                },
            }
            for i in range(30)
        ]
        ctx = RepoContext(
            candidate=sample_candidate,
            recent_commits=commits,
            recent_issues=[
                {"number": 1, "state": "closed"},
                {"number": 2, "state": "closed"},
                {"number": 3, "state": "open"},
            ],
        )
        analyzer = MaintenanceAnalyzer()
        result = analyzer.score(ctx)

        # Commits: daily from 5 authors, last one is today (0 days ago)
        assert result.value > 0.5
        assert result.details["last_commit_days_ago"] == 0

    def test_inactive_repo_score(self, sample_candidate: RepoCandidate) -> None:
        """Inactive repo with old commits gets low score."""
        old_date = (datetime.now(UTC) - timedelta(days=400)).isoformat()
        ctx = RepoContext(
            candidate=sample_candidate,
            recent_commits=[
                {
                    "sha": "abc123",
                    "commit": {
                        "author": {
                            "name": "dev1",
                            "email": "dev1@example.com",
                            "date": old_date,
                        },
                        "message": "old commit",
                    },
                },
            ],
            recent_issues=[],
        )
        analyzer = MaintenanceAnalyzer()
        result = analyzer.score(ctx)

        assert result.details["last_commit_days_ago"] >= 365
        # Recency component should be 0.1, pulling total down
        assert result.value < 0.5

    def test_commit_cadence_active(self, sample_repo_context: RepoContext) -> None:
        """Daily commits produce high cadence score."""
        analyzer = MaintenanceAnalyzer()
        result = analyzer.score(sample_repo_context)

        # Sample commits are daily, so cadence_days should be ~1
        assert result.details["commit_cadence_days"] < 7

    def test_bus_factor_healthy(self, sample_repo_context: RepoContext) -> None:
        """5 unique authors produce healthy bus factor score."""
        analyzer = MaintenanceAnalyzer()
        result = analyzer.score(sample_repo_context)

        assert result.details["bus_factor"] == 5

    def test_bus_factor_single_maintainer(self, sample_candidate: RepoCandidate) -> None:
        """Single maintainer produces low bus factor."""
        recent = datetime.now(UTC) - timedelta(days=1)
        ctx = RepoContext(
            candidate=sample_candidate,
            recent_commits=[
                {
                    "sha": f"abc{i}",
                    "commit": {
                        "author": {
                            "name": "lonely-dev",
                            "email": "lonely@example.com",
                            "date": (recent - timedelta(days=i)).isoformat(),
                        },
                        "message": f"commit {i}",
                    },
                }
                for i in range(10)
            ],
            recent_issues=[],
        )
        analyzer = MaintenanceAnalyzer()
        result = analyzer.score(ctx)

        assert result.details["bus_factor"] == 1

    def test_issue_resolution_good(self, sample_repo_context: RepoContext) -> None:
        """20 closed / 30 total issues produce good resolution rate."""
        analyzer = MaintenanceAnalyzer()
        result = analyzer.score(sample_repo_context)

        # 20 closed / 30 total = 0.667
        assert result.details["issue_resolution_rate"] > 0.5

    def test_composite_weighted(self, sample_repo_context: RepoContext) -> None:
        """Composite score is weighted average of components."""
        analyzer = MaintenanceAnalyzer()
        result = analyzer.score(sample_repo_context)

        # With good signals across all dimensions, value should be high
        assert 0.5 < result.value <= 1.0
        # Verify value is capped at 1.0
        assert result.value <= 1.0

    def test_details_report_signals(self, sample_repo_context: RepoContext) -> None:
        """Score details contain all expected signal keys."""
        analyzer = MaintenanceAnalyzer()
        result = analyzer.score(sample_repo_context)

        assert "last_commit_days_ago" in result.details
        assert "commit_cadence_days" in result.details
        assert "bus_factor" in result.details
        assert "issue_resolution_rate" in result.details

    def test_confidence_api_based(self, sample_repo_context: RepoContext) -> None:
        """API-based analysis has confidence 0.7."""
        analyzer = MaintenanceAnalyzer()
        result = analyzer.score(sample_repo_context)

        assert result.confidence == 0.7

    def test_no_commits_data(self, sample_candidate: RepoCandidate) -> None:
        """Missing commit data produces minimal score with note."""
        ctx = RepoContext(
            candidate=sample_candidate,
            recent_commits=[],
            recent_issues=[],
        )
        analyzer = MaintenanceAnalyzer()
        result = analyzer.score(ctx)

        # No data should yield low score
        assert result.value < 0.3
        assert len(result.notes) > 0
