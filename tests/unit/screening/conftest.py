"""Shared fixtures for screening unit tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from github_discovery.config import GitHubSettings, ScreeningSettings
from github_discovery.discovery.github_client import GitHubRestClient
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel, DomainType
from github_discovery.screening.subprocess_runner import SubprocessRunner
from github_discovery.screening.types import RepoContext, SubprocessResult


@pytest.fixture
def screening_settings() -> ScreeningSettings:
    """Default screening settings."""
    return ScreeningSettings()


@pytest.fixture
def github_settings() -> GitHubSettings:
    """Default GitHub settings for tests."""
    return GitHubSettings(token="test-token")  # noqa: S106


@pytest.fixture
def mock_rest_client() -> AsyncMock:
    """GitHubRestClient mock with async methods."""
    client = AsyncMock(spec=GitHubRestClient)
    client.get_json = AsyncMock(return_value={})
    client.get_all_pages = AsyncMock(return_value=[])
    return client


@pytest.fixture
def sample_candidate() -> RepoCandidate:
    """A fully populated RepoCandidate for testing."""
    return RepoCandidate(
        full_name="test-org/test-repo",
        url="https://github.com/test-org/test-repo",
        html_url="https://github.com/test-org/test-repo",
        api_url="https://api.github.com/repos/test-org/test-repo",
        description="A test repository for screening",
        language="Python",
        topics=["testing", "quality"],
        domain=DomainType.LIBRARY,
        stars=150,
        forks_count=25,
        open_issues_count=10,
        created_at=datetime(2023, 1, 15, tzinfo=UTC),
        updated_at=datetime(2026, 4, 1, tzinfo=UTC),
        pushed_at=datetime(2026, 4, 15, tzinfo=UTC),
        license_info={"spdx_id": "MIT", "name": "MIT License"},
        default_branch="main",
        size_kb=5000,
        owner_login="test-org",
        source_channel=DiscoveryChannel.SEARCH,
        discovery_score=0.75,
    )


@pytest.fixture
def sample_repo_contents() -> list[str]:
    """Root directory listing with typical project files."""
    return [
        ".github",
        ".github/workflows",
        ".github/workflows/ci.yml",
        ".github/workflows/release.yml",
        ".github/ISSUE_TEMPLATE",
        ".github/PULL_REQUEST_TEMPLATE.md",
        ".github/dependabot.yml",
        "src",
        "tests",
        "tests/__init__.py",
        "tests/test_main.py",
        "tests/test_utils.py",
        "tests/conftest.py",
        "README.md",
        "LICENSE",
        "pyproject.toml",
        "poetry.lock",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "SECURITY.md",
    ]


@pytest.fixture
def sample_repo_metadata() -> dict[str, object]:
    """Sample /repos/{owner}/{repo} API response data."""
    return {
        "full_name": "test-org/test-repo",
        "description": "A test repository",
        "language": "Python",
        "stargazers_count": 150,
        "forks_count": 25,
        "open_issues_count": 10,
        "license": {"spdx_id": "MIT", "name": "MIT License"},
        "topics": ["testing", "quality"],
        "archived": False,
        "disabled": False,
        "default_branch": "main",
        "size": 5000,
    }


@pytest.fixture
def sample_releases() -> list[dict[str, object]]:
    """10 releases with semver tags and release notes."""
    releases: list[dict[str, object]] = []
    for i in range(10):
        version = f"1.{i}.0"
        releases.append(
            {
                "tag_name": f"v{version}",
                "name": f"Release {version}",
                "body": (
                    f"## Changes in {version}\n\n- Bug fixes\n- Performance improvements\n"
                    f"## Breaking Changes\n\nNone\n\n## Contributors\n\n- dev1\n- dev2\n"
                ),
                "draft": False,
                "prerelease": False,
                "created_at": (
                    datetime(2026, 4, 1, tzinfo=UTC) - timedelta(days=30 * i)
                ).isoformat(),
                "published_at": (
                    datetime(2026, 4, 1, tzinfo=UTC) - timedelta(days=30 * i)
                ).isoformat(),
            }
        )
    return releases


@pytest.fixture
def sample_commits() -> list[dict[str, object]]:
    """30 commits with dates and authors."""
    commits: list[dict[str, object]] = []
    authors = ["dev1", "dev2", "dev3", "dev4", "dev5"]
    for i in range(30):
        commits.append(
            {
                "sha": f"abc{str(i).zfill(4)}",
                "commit": {
                    "author": {
                        "name": authors[i % len(authors)],
                        "email": f"{authors[i % len(authors)]}@example.com",
                        "date": (datetime(2026, 4, 1, tzinfo=UTC) - timedelta(days=i)).isoformat(),
                    },
                    "message": f"Commit {i}: fix issue #{i * 10}",
                },
            }
        )
    return commits


@pytest.fixture
def sample_issues() -> list[dict[str, object]]:
    """30 issues with labels and state."""
    issues: list[dict[str, object]] = []
    for i in range(30):
        is_closed = i < 20  # 20 closed, 10 open
        issues.append(
            {
                "number": i + 1,
                "state": "closed" if is_closed else "open",
                "title": f"Issue {i + 1}",
                "labels": [{"name": "bug"}] if i % 3 == 0 else [],
                "created_at": (datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i)).isoformat(),
                "closed_at": (
                    (datetime(2026, 1, 5, tzinfo=UTC) + timedelta(days=i)).isoformat()
                    if is_closed
                    else None
                ),
            }
        )
    return issues


@pytest.fixture
def sample_prs() -> list[dict[str, object]]:
    """30 PRs with reviews, labels, and state."""
    prs: list[dict[str, object]] = []
    for i in range(30):
        is_merged = i < 20
        prs.append(
            {
                "number": i + 1,
                "state": "closed" if is_merged else "open",
                "title": f"PR {i + 1}: Fix issue {i + 1}",
                "labels": [{"name": "bug fix"}] if i % 2 == 0 else [],
                "review_comments": 3 if i % 3 == 0 else 0,
                "requested_reviewers": [{"login": "reviewer1"}] if i % 4 == 0 else [],
                "created_at": (datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i)).isoformat(),
                "merged_at": (
                    (datetime(2026, 1, 3, tzinfo=UTC) + timedelta(days=i)).isoformat()
                    if is_merged
                    else None
                ),
            }
        )
    return prs


@pytest.fixture
def sample_repo_context(
    sample_candidate: RepoCandidate,
    sample_repo_contents: list[str],
    sample_repo_metadata: dict[str, object],
    sample_releases: list[dict[str, object]],
    sample_commits: list[dict[str, object]],
    sample_issues: list[dict[str, object]],
    sample_prs: list[dict[str, object]],
) -> RepoContext:
    """Fully populated RepoContext for testing."""
    return RepoContext(
        candidate=sample_candidate,
        repo_metadata=sample_repo_metadata,
        repo_contents=sample_repo_contents,
        recent_releases=sample_releases,
        recent_commits=sample_commits,
        recent_issues=sample_issues,
        recent_prs=sample_prs,
        languages={"Python": 45000, "JavaScript": 5000},
        topics=["testing", "quality"],
    )


@pytest.fixture
def sample_scorecard_response() -> dict[str, object]:
    """OpenSSF Scorecard API response."""
    return {
        "date": "2026-04-15",
        "repo": {"name": "github.com/test-org/test-repo"},
        "score": 8.5,
        "scorecard": {"version": "v5"},
        "checks": [
            {"name": "Branch-Protection", "score": 9},
            {"name": "Token-Permissions", "score": 8},
            {"name": "Dangerous-Workflow", "score": 10},
            {"name": "Pinned-Dependencies", "score": 7},
            {"name": "Signed-Releases", "score": 9},
        ],
    }


@pytest.fixture
def sample_osv_response() -> dict[str, object]:
    """OSV API response with vulnerabilities."""
    return {
        "vulns": [
            {
                "id": "GHSA-xxxx-xxxx-xxxx",
                "summary": "A test vulnerability",
                "severity": "HIGH",
                "database_specific": {"severity": "HIGH"},
            },
        ],
    }


@pytest.fixture
def sample_sarif_output() -> dict[str, object]:
    """gitleaks SARIF output."""
    return {
        "$schema": (
            "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/"
            "master/Schemata/sarif-schema-2.1.0.json"
        ),
        "version": "2.1.0",
        "runs": [
            {
                "results": [
                    {"ruleId": "test-rule", "message": {"text": "Test finding"}},
                    {"ruleId": "test-rule-2", "message": {"text": "Another finding"}},
                ],
            },
        ],
    }


@pytest.fixture
def sample_scc_output() -> dict[str, object]:
    """scc JSON output."""
    return {
        "Python": {
            "Name": "Python",
            "Code": 12000,
            "Comment": 3000,
            "Blank": 2000,
            "Complexity": 450,
            "Files": 85,
            "Lines": 17000,
        },
        "JavaScript": {
            "Name": "JavaScript",
            "Code": 2500,
            "Comment": 500,
            "Blank": 300,
            "Complexity": 80,
            "Files": 15,
            "Lines": 3300,
        },
    }


@pytest.fixture
def mock_subprocess_runner() -> AsyncMock:
    """SubprocessRunner mock with configurable responses."""
    runner = AsyncMock(spec=SubprocessRunner)
    runner.run = AsyncMock(
        return_value=SubprocessResult(returncode=0, stdout="{}", stderr=""),
    )
    return runner
