"""Tests for repository hygiene files checker."""

from __future__ import annotations

from datetime import UTC, datetime

from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel
from github_discovery.models.screening import HygieneScore
from github_discovery.screening.hygiene import HygieneChecker
from github_discovery.screening.types import RepoContext


def _make_context(
    contents: list[str],
    license_info: dict[str, object] | None = None,
) -> RepoContext:
    """Helper to build a RepoContext with given contents and license."""
    candidate = RepoCandidate(
        full_name="test/repo",
        url="https://github.com/test/repo",
        html_url="https://github.com/test/repo",
        api_url="https://api.github.com/repos/test/repo",
        owner_login="test",
        created_at=datetime(2023, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        source_channel=DiscoveryChannel.SEARCH,
        license_info=license_info,
    )
    return RepoContext(
        candidate=candidate,
        repo_contents=contents,
    )


class TestHygieneChecker:
    """Tests for HygieneChecker."""

    def test_all_hygiene_files_present(self) -> None:
        """Context with all hygiene files → score ~1.0."""
        ctx = _make_context(
            contents=[
                "LICENSE",
                "README.md",
                "CONTRIBUTING.md",
                "CODE_OF_CONDUCT.md",
                "SECURITY.md",
                "CHANGELOG.md",
            ],
            license_info={"spdx_id": "MIT", "name": "MIT License"},
        )
        result = HygieneChecker().score(ctx)

        assert isinstance(result, HygieneScore)
        assert result.value == 1.0
        assert result.confidence == 1.0

    def test_only_required_files_present(self) -> None:
        """Only LICENSE + README → partial score."""
        ctx = _make_context(
            contents=["LICENSE", "README.md"],
            license_info={"spdx_id": "MIT", "name": "MIT License"},
        )
        result = HygieneChecker().score(ctx)

        # Weight: license=0.25, readme=0.20 → found=0.45, total=1.0
        expected = 0.45
        assert abs(result.value - expected) < 0.01

    def test_no_hygiene_files(self) -> None:
        """Empty contents → score 0.0."""
        ctx = _make_context(contents=[])
        result = HygieneChecker().score(ctx)

        assert result.value == 0.0

    def test_license_spdx_validation(self) -> None:
        """Valid SPDX license → full license quality (1.0 contribution)."""
        ctx = _make_context(
            contents=["LICENSE"],
            license_info={"spdx_id": "Apache-2.0", "name": "Apache License 2.0"},
        )
        result = HygieneChecker().score(ctx)

        # license weight=0.25, quality=1.0 → 0.25/1.0 = 0.25
        assert abs(result.value - 0.25) < 0.01

    def test_license_noassertion(self) -> None:
        """SPDX NOASSERTION → reduced license quality (0.5 contribution)."""
        ctx = _make_context(
            contents=["LICENSE"],
            license_info={"spdx_id": "NOASSERTION", "name": "Other"},
        )
        result = HygieneChecker().score(ctx)

        # license weight=0.25, quality=0.5 → 0.125/1.0 = 0.125
        assert abs(result.value - 0.125) < 0.01

    def test_case_insensitive_matching(self) -> None:
        """Lowercase 'license' matches 'LICENSE'."""
        ctx = _make_context(
            contents=["license", "readme.md"],
            license_info={"spdx_id": "MIT", "name": "MIT License"},
        )
        result = HygieneChecker().score(ctx)

        assert result.details["license"] is True
        assert result.details["readme"] is True

    def test_hygiene_details_list_files_found(self) -> None:
        """Details dict correctly lists found files."""
        ctx = _make_context(
            contents=["LICENSE", "README.md", "CHANGELOG.md"],
            license_info={"spdx_id": "MIT", "name": "MIT"},
        )
        result = HygieneChecker().score(ctx)

        assert result.details["license"] is True
        assert result.details["readme"] is True
        assert result.details["changelog"] is True
        assert result.details["contributing"] is False
        assert result.details["code_of_conduct"] is False
        assert result.details["security"] is False

    def test_empty_contents_low_confidence(self) -> None:
        """Empty repo_contents → confidence 0.5."""
        ctx = _make_context(contents=[])
        result = HygieneChecker().score(ctx)

        assert result.confidence == 0.5

    def test_license_present_no_info(self) -> None:
        """LICENSE file present but no license_info → quality 0.5."""
        ctx = _make_context(
            contents=["LICENSE"],
            license_info=None,
        )
        result = HygieneChecker().score(ctx)

        # weight=0.25, quality=0.5 → 0.125/1.0
        assert abs(result.value - 0.125) < 0.01

    def test_non_default_paths(self) -> None:
        """Alternative file names like COPYING, HISTORY.md are detected."""
        ctx = _make_context(
            contents=["COPYING", "HISTORY.md", "README.rst"],
            license_info={"spdx_id": "GPL-3.0", "name": "GPL"},
        )
        result = HygieneChecker().score(ctx)

        assert result.details["license"] is True
        assert result.details["changelog"] is True
        assert result.details["readme"] is True
