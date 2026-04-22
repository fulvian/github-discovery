"""Tests for repository candidate models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from github_discovery.models.candidate import CandidatePool, RepoCandidate
from github_discovery.models.enums import CandidateStatus, DiscoveryChannel, DomainType


def _make_candidate(**overrides: object) -> RepoCandidate:
    """Create a test candidate with sensible defaults.

    Uses model_validate for full Pydantic validation (including
    constraints like ge=0 for stars, ge/le for discovery_score).
    """
    defaults: dict[str, object] = {
        "full_name": "test/repo",
        "url": "https://github.com/test/repo",
        "html_url": "https://github.com/test/repo",
        "api_url": "https://api.github.com/repos/test/repo",
        "description": "A test repository",
        "language": "Python",
        "topics": ["testing", "quality"],
        "domain": DomainType.LIBRARY,
        "stars": 42,
        "forks_count": 5,
        "open_issues_count": 10,
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 4, 1, tzinfo=UTC),
        "pushed_at": datetime(2026, 4, 15, tzinfo=UTC),
        "license_info": {"spdx_id": "MIT", "name": "MIT License"},
        "default_branch": "main",
        "size_kb": 1024,
        "owner_login": "test",
        "source_channel": DiscoveryChannel.SEARCH,
        "discovery_score": 0.75,
    }
    merged = {**defaults, **overrides}
    return RepoCandidate.model_validate(merged)


class TestRepoCandidate:
    """Test RepoCandidate model."""

    def test_create_from_defaults(self) -> None:
        """Candidate can be created with required fields."""
        candidate = _make_candidate()
        assert candidate.full_name == "test/repo"
        assert candidate.language == "Python"
        assert candidate.domain == DomainType.LIBRARY
        assert candidate.status == CandidateStatus.DISCOVERED

    def test_json_round_trip(self) -> None:
        """Candidate serializes to/from JSON."""
        candidate = _make_candidate()
        json_str = candidate.model_dump_json()
        restored = RepoCandidate.model_validate_json(json_str)
        assert restored.full_name == candidate.full_name
        assert restored.stars == candidate.stars
        assert restored.source_channel == DiscoveryChannel.SEARCH

    def test_stars_default_zero(self) -> None:
        """Stars default to 0 and are non-negative."""
        candidate = _make_candidate(stars=0)
        assert candidate.stars == 0

    def test_stars_negative_raises(self) -> None:
        """Stars cannot be negative."""
        with pytest.raises(Exception):  # noqa: B017
            _make_candidate(stars=-1)

    def test_discovery_score_range(self) -> None:
        """Discovery score must be between 0.0 and 1.0."""
        with pytest.raises(Exception):  # noqa: B017
            _make_candidate(discovery_score=1.5)
        with pytest.raises(Exception):  # noqa: B017
            _make_candidate(discovery_score=-0.1)

    def test_owner_name_property(self) -> None:
        """owner_name extracts owner from full_name."""
        candidate = _make_candidate(full_name="pallets/flask")
        assert candidate.owner_name == "pallets"

    def test_repo_name_property(self) -> None:
        """repo_name extracts repo from full_name."""
        candidate = _make_candidate(full_name="pallets/flask")
        assert candidate.repo_name == "flask"

    def test_is_archived_or_disabled(self) -> None:
        """Archived or disabled repos are flagged."""
        assert _make_candidate(archived=True).is_archived_or_disabled is True
        assert _make_candidate(disabled=True).is_archived_or_disabled is True
        assert _make_candidate(archived=False, disabled=False).is_archived_or_disabled is False

    def test_is_active(self) -> None:
        """Repo with push within 365 days is active."""
        recent = datetime.now(UTC) - timedelta(days=30)
        old = datetime.now(UTC) - timedelta(days=400)
        assert _make_candidate(pushed_at=recent).is_active is True
        assert _make_candidate(pushed_at=old).is_active is False
        assert _make_candidate(pushed_at=None).is_active is False

    def test_from_github_api_dict(self) -> None:
        """Candidate can be created from a GitHub API response dict."""
        gh_response: dict[str, object] = {
            "full_name": "python/cpython",
            "url": "https://api.github.com/repos/python/cpython",
            "html_url": "https://github.com/python/cpython",
            "api_url": "https://api.github.com/repos/python/cpython",
            "description": "The Python programming language",
            "language": "Python",
            "topics": ["python", "interpreter"],
            "stars": 65000,
            "forks_count": 25000,
            "open_issues_count": 1000,
            "created_at": "2010-01-01T00:00:00Z",
            "updated_at": "2026-04-22T00:00:00Z",
            "pushed_at": "2026-04-22T00:00:00Z",
            "license_info": {
                "spdx_id": "PSF-2.0",
                "name": "Python Software Foundation License",
            },
            "default_branch": "main",
            "size_kb": 500000,
            "archived": False,
            "disabled": False,
            "is_fork": False,
            "is_template": False,
            "has_issues": True,
            "has_wiki": True,
            "has_pages": False,
            "has_discussions": True,
            "owner_login": "python",
            "owner_type": "Organization",
            "source_channel": "search",
            "discovery_score": 0.9,
        }
        candidate = RepoCandidate.model_validate(gh_response)
        assert candidate.full_name == "python/cpython"
        assert candidate.stars == 65000


class TestCandidatePool:
    """Test CandidatePool model."""

    def test_empty_pool(self) -> None:
        """Empty pool can be created."""
        pool = CandidatePool(query="test")
        assert pool.total_count == 0
        assert pool.unique_full_names == set()

    def test_pool_with_candidates(self) -> None:
        """Pool tracks candidates correctly."""
        candidates = [
            _make_candidate(full_name="user/repo1"),
            _make_candidate(full_name="user/repo2"),
        ]
        pool = CandidatePool(query="python testing", candidates=candidates)
        assert pool.total_count == 2
        assert len(pool.unique_full_names) == 2

    def test_domain_distribution(self) -> None:
        """Pool computes domain distribution."""
        candidates = [
            _make_candidate(full_name="a/lib1", domain=DomainType.LIBRARY),
            _make_candidate(full_name="a/lib2", domain=DomainType.LIBRARY),
            _make_candidate(full_name="a/cli1", domain=DomainType.CLI),
        ]
        pool = CandidatePool(candidates=candidates)
        dist = pool.domain_distribution
        assert dist["library"] == 2
        assert dist["cli"] == 1

    def test_pool_json_round_trip(self) -> None:
        """Pool serializes to/from JSON."""
        pool = CandidatePool(
            query="python static analysis",
            channels_used=[DiscoveryChannel.SEARCH, DiscoveryChannel.REGISTRY],
            candidates=[_make_candidate()],
        )
        json_str = pool.model_dump_json()
        restored = CandidatePool.model_validate_json(json_str)
        assert restored.query == pool.query
        assert restored.total_count == 1
        assert restored.channels_used == [
            DiscoveryChannel.SEARCH,
            DiscoveryChannel.REGISTRY,
        ]
