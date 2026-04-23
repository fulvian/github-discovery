"""Tests for release discipline scorer."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel
from github_discovery.models.screening import ReleaseDisciplineScore
from github_discovery.screening.release_discipline import ReleaseDisciplineScorer
from github_discovery.screening.types import RepoContext


def _make_context(
    releases: list[dict[str, object]] | None = None,
    contents: list[str] | None = None,
) -> RepoContext:
    """Helper to build a RepoContext with given releases and contents."""
    candidate = RepoCandidate(
        full_name="test/repo",
        url="https://github.com/test/repo",
        html_url="https://github.com/test/repo",
        api_url="https://api.github.com/repos/test/repo",
        owner_login="test",
        created_at=datetime(2023, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        source_channel=DiscoveryChannel.SEARCH,
    )
    return RepoContext(
        candidate=candidate,
        repo_contents=contents or [],
        recent_releases=releases or [],
    )


def _make_releases(
    count: int,
    *,
    tag_prefix: str = "v",
    semver: bool = True,
    body_length: int = 200,
    cadence_days: int = 30,
) -> list[dict[str, object]]:
    """Generate release dicts for testing."""
    releases: list[dict[str, object]] = []
    for i in range(count):
        tag = f"{tag_prefix}1.{i}.0" if semver else f"{tag_prefix}release-{i}"

        published = datetime(2026, 4, 1, tzinfo=UTC) - timedelta(days=cadence_days * i)

        releases.append(
            {
                "tag_name": tag,
                "name": f"Release 1.{i}.0",
                "body": "x" * body_length,
                "draft": False,
                "prerelease": False,
                "created_at": published.isoformat(),
                "published_at": published.isoformat(),
            }
        )
    return releases


class TestReleaseDisciplineScorer:
    """Tests for ReleaseDisciplineScorer."""

    def test_regular_semver_releases(self) -> None:
        """Regular semver releases with good notes → high score."""
        releases = _make_releases(5, semver=True, body_length=200, cadence_days=30)
        ctx = _make_context(
            releases=releases,
            contents=["CHANGELOG.md"],
        )
        result = ReleaseDisciplineScorer().score(ctx)

        assert isinstance(result, ReleaseDisciplineScore)
        # All 5 signals: releases, semver, cadence<90, notes>50%, changelog
        assert result.value == 1.0
        assert result.details["has_semver_tags"] is True
        assert result.details["release_count"] == 5

    def test_no_releases(self) -> None:
        """No releases → score 0.0 (no releases → no other signals either)."""
        ctx = _make_context(releases=[], contents=["CHANGELOG.md"])
        result = ReleaseDisciplineScorer().score(ctx)

        # Only changelog signal: 0.2
        assert result.value == 0.2
        assert result.details["release_count"] == 0

    def test_non_semver_tags(self) -> None:
        """Non-semver tags → semver signal fails."""
        releases = _make_releases(5, semver=False, body_length=200, cadence_days=30)
        ctx = _make_context(releases=releases, contents=["CHANGELOG.md"])

        result = ReleaseDisciplineScorer().score(ctx)

        # has_releases=0.2, semver fails, cadence=0.2, notes=0.2, changelog=0.2
        assert result.details["has_semver_tags"] is False
        expected = 0.8
        assert abs(result.value - expected) < 0.01

    def test_release_cadence_calculated(self) -> None:
        """Release cadence correctly computed from release dates."""
        releases = _make_releases(3, cadence_days=45)
        ctx = _make_context(releases=releases)

        result = ReleaseDisciplineScorer().score(ctx)

        cadence = result.details["release_cadence_days"]
        assert cadence is not None
        assert abs(float(cadence) - 45.0) < 1.0

    def test_slow_cadence_no_bonus(self) -> None:
        """Cadence > 90 days → no cadence bonus."""
        releases = _make_releases(3, cadence_days=120)
        ctx = _make_context(releases=releases, contents=["CHANGELOG.md"])

        result = ReleaseDisciplineScorer().score(ctx)

        # has_releases=0.2, semver=0.2, cadence fails, notes=0.2, changelog=0.2
        assert result.value == 0.8

    def test_release_notes_quality(self) -> None:
        """Short release notes → notes quality signal fails."""
        releases = _make_releases(5, body_length=10)  # too short
        ctx = _make_context(releases=releases)

        result = ReleaseDisciplineScorer().score(ctx)

        # has_releases=0.2, semver=0.2, cadence=0.2, notes fail, no changelog
        assert result.details["has_changelog_per_release"] is False

    def test_details_report_signals(self) -> None:
        """Details dict contains all expected signals."""
        releases = _make_releases(5)
        ctx = _make_context(releases=releases, contents=["CHANGELOG.md"])

        result = ReleaseDisciplineScorer().score(ctx)

        assert "has_semver_tags" in result.details
        assert "release_count" in result.details
        assert "release_cadence_days" in result.details
        assert "has_changelog_per_release" in result.details

    def test_single_release_no_cadence(self) -> None:
        """Single release → cadence is None (can't compute gaps)."""
        releases = _make_releases(1)
        ctx = _make_context(releases=releases)

        result = ReleaseDisciplineScorer().score(ctx)

        assert result.details["release_cadence_days"] is None

    def test_mixed_semver_tags(self) -> None:
        """Mix of semver and non-semver → semver ratio may still pass."""
        releases = _make_releases(10, semver=True)
        # Override a few tags to be non-semver
        releases[0]["tag_name"] = "latest"
        releases[1]["tag_name"] = "nightly"

        ctx = _make_context(releases=releases)
        result = ReleaseDisciplineScorer().score(ctx)

        # 8/10 = 0.8 → passes threshold
        assert result.details["has_semver_tags"] is True

    def test_below_threshold_semver(self) -> None:
        """Semver ratio below 0.8 → has_semver_tags False."""
        releases = _make_releases(10, semver=True)
        # Override 3 to be non-semver → 7/10 = 0.7
        releases[0]["tag_name"] = "latest"
        releases[1]["tag_name"] = "nightly"
        releases[2]["tag_name"] = "dev"

        ctx = _make_context(releases=releases)
        result = ReleaseDisciplineScorer().score(ctx)

        assert result.details["has_semver_tags"] is False
