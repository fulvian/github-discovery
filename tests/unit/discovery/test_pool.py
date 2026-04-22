"""Tests for PoolManager — Task 2.10."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from github_discovery.discovery.pool import PoolManager
from github_discovery.discovery.types import DiscoveryQuery
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import CandidateStatus, DiscoveryChannel

# --- Helpers ---


def _make_candidate(full_name: str, score: float = 0.5) -> RepoCandidate:
    """Create a minimal RepoCandidate for testing."""
    return RepoCandidate(
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        html_url=f"https://github.com/{full_name}",
        api_url=f"https://api.github.com/repos/{full_name}",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 6, 1, tzinfo=UTC),
        owner_login=full_name.split("/", maxsplit=1)[0],
        source_channel=DiscoveryChannel.SEARCH,
        description=f"Test repo {full_name}",
        language="Python",
        stars=100,
        forks_count=10,
        open_issues_count=5,
        size_kb=1000,
        default_branch="main",
        discovery_score=score,
    )


@pytest.fixture
def pool_manager(tmp_path: Path) -> PoolManager:
    """Create PoolManager with temporary database."""
    return PoolManager(db_path=tmp_path / "test.db")


@pytest.fixture
def sample_query() -> DiscoveryQuery:
    """A sample discovery query."""
    return DiscoveryQuery(query="python web framework")


@pytest.fixture
def sample_candidates() -> list[RepoCandidate]:
    """Five sample RepoCandidate instances."""
    return [
        _make_candidate("pallets/flask", 0.8),
        _make_candidate("fastapi/fastapi", 0.9),
        _make_candidate("django/django", 0.7),
        _make_candidate("tiangolo/uvicorn", 0.6),
        _make_candidate("encode/httpx", 0.5),
    ]


# --- Tests ---


class TestCreatePool:
    """Tests for pool creation."""

    async def test_create_pool_with_candidates(
        self,
        pool_manager: PoolManager,
        sample_query: DiscoveryQuery,
        sample_candidates: list[RepoCandidate],
    ) -> None:
        """Creating a pool should persist candidates."""
        async with pool_manager:
            pool = await pool_manager.create_pool(sample_query, sample_candidates)

            assert pool.pool_id is not None
            assert pool.total_count == 5
            assert len(pool.candidates) == 5
            assert pool.query == "python web framework"

    async def test_create_pool_returns_candidate_data(
        self,
        pool_manager: PoolManager,
        sample_query: DiscoveryQuery,
        sample_candidates: list[RepoCandidate],
    ) -> None:
        """Pool should contain the correct candidate data."""
        async with pool_manager:
            pool = await pool_manager.create_pool(sample_query, sample_candidates)

            full_names = {c.full_name for c in pool.candidates}
            assert "pallets/flask" in full_names
            assert "fastapi/fastapi" in full_names


class TestGetPool:
    """Tests for pool retrieval."""

    async def test_get_pool_returns_correct_data(
        self,
        pool_manager: PoolManager,
        sample_query: DiscoveryQuery,
        sample_candidates: list[RepoCandidate],
    ) -> None:
        """Retrieved pool should have the correct query and candidates."""
        async with pool_manager:
            created = await pool_manager.create_pool(sample_query, sample_candidates)
            retrieved = await pool_manager.get_pool(created.pool_id)

            assert retrieved is not None
            assert retrieved.pool_id == created.pool_id
            assert retrieved.total_count == 5
            assert retrieved.query == "python web framework"

    async def test_get_pool_nonexistent_returns_none(
        self,
        pool_manager: PoolManager,
    ) -> None:
        """Non-existent pool_id should return None."""
        async with pool_manager:
            result = await pool_manager.get_pool("nonexistent-id")
            assert result is None


class TestAddCandidates:
    """Tests for adding candidates to existing pool."""

    async def test_add_candidates_deduplicates(
        self,
        pool_manager: PoolManager,
        sample_query: DiscoveryQuery,
        sample_candidates: list[RepoCandidate],
    ) -> None:
        """Adding a duplicate candidate should be ignored."""
        async with pool_manager:
            pool = await pool_manager.create_pool(sample_query, sample_candidates)

            # Try to add an existing candidate
            new_count = await pool_manager.add_candidates(
                pool.pool_id,
                [_make_candidate("pallets/flask")],
            )
            assert new_count == 0  # Duplicate ignored

    async def test_add_candidates_new(
        self,
        pool_manager: PoolManager,
        sample_query: DiscoveryQuery,
        sample_candidates: list[RepoCandidate],
    ) -> None:
        """Adding a new candidate should succeed."""
        async with pool_manager:
            pool = await pool_manager.create_pool(sample_query, sample_candidates)

            new_count = await pool_manager.add_candidates(
                pool.pool_id,
                [_make_candidate("new/repo", 0.3)],
            )
            assert new_count == 1

            # Verify total count updated (total_count is a computed property)
            updated = await pool_manager.get_pool(pool.pool_id)
            assert updated is not None
            assert updated.total_count == 6


class TestUpdateStatus:
    """Tests for candidate status updates."""

    async def test_update_candidate_status(
        self,
        pool_manager: PoolManager,
        sample_query: DiscoveryQuery,
        sample_candidates: list[RepoCandidate],
    ) -> None:
        """Updating status should be reflected in filtered queries."""
        async with pool_manager:
            pool = await pool_manager.create_pool(sample_query, sample_candidates)

            success = await pool_manager.update_candidate_status(
                pool.pool_id,
                "pallets/flask",
                CandidateStatus.GATE1_PASSED,
            )
            assert success is True

            # Get candidates with status filter
            screened = await pool_manager.get_candidates(
                pool.pool_id,
                status=CandidateStatus.GATE1_PASSED,
            )
            assert len(screened) == 1
            assert screened[0].full_name == "pallets/flask"

    async def test_update_nonexistent_returns_false(
        self,
        pool_manager: PoolManager,
        sample_query: DiscoveryQuery,
        sample_candidates: list[RepoCandidate],
    ) -> None:
        """Updating a non-existent candidate should return False."""
        async with pool_manager:
            pool = await pool_manager.create_pool(sample_query, sample_candidates)

            success = await pool_manager.update_candidate_status(
                pool.pool_id,
                "nonexistent/repo",
                CandidateStatus.GATE1_PASSED,
            )
            assert success is False


class TestGetCandidates:
    """Tests for candidate retrieval with filtering."""

    async def test_get_candidates_with_status_filter(
        self,
        pool_manager: PoolManager,
        sample_query: DiscoveryQuery,
        sample_candidates: list[RepoCandidate],
    ) -> None:
        """Filtering by status should return only matching candidates."""
        async with pool_manager:
            pool = await pool_manager.create_pool(sample_query, sample_candidates)

            # All start as DISCOVERED
            discovered = await pool_manager.get_candidates(
                pool.pool_id,
                status=CandidateStatus.DISCOVERED,
            )
            assert len(discovered) == 5

    async def test_get_candidates_pagination(
        self,
        pool_manager: PoolManager,
        sample_query: DiscoveryQuery,
        sample_candidates: list[RepoCandidate],
    ) -> None:
        """Pagination with limit/offset should work."""
        async with pool_manager:
            pool = await pool_manager.create_pool(sample_query, sample_candidates)

            page1 = await pool_manager.get_candidates(pool.pool_id, limit=2, offset=0)
            page2 = await pool_manager.get_candidates(pool.pool_id, limit=2, offset=2)

            assert len(page1) == 2
            assert len(page2) == 2
            # No overlap (ordered by discovery_score DESC)
            names1 = {c.full_name for c in page1}
            names2 = {c.full_name for c in page2}
            assert names1.isdisjoint(names2)


class TestPoolStats:
    """Tests for pool statistics."""

    async def test_get_pool_stats(
        self,
        pool_manager: PoolManager,
        sample_query: DiscoveryQuery,
        sample_candidates: list[RepoCandidate],
    ) -> None:
        """Stats should reflect correct status distribution."""
        async with pool_manager:
            pool = await pool_manager.create_pool(sample_query, sample_candidates)

            # Update some statuses
            await pool_manager.update_candidate_status(
                pool.pool_id,
                "pallets/flask",
                CandidateStatus.GATE1_PASSED,
            )
            await pool_manager.update_candidate_status(
                pool.pool_id,
                "fastapi/fastapi",
                CandidateStatus.RANKED,
            )

            stats = await pool_manager.get_pool_stats(pool.pool_id)
            assert stats["total"] == 5
            assert stats["discovered"] == 3  # 3 still discovered
            assert stats["screened"] == 1  # flask = gate1_passed
            assert stats["ranked"] == 1  # fastapi = ranked


class TestDeletePool:
    """Tests for pool deletion."""

    async def test_delete_pool(
        self,
        pool_manager: PoolManager,
        sample_query: DiscoveryQuery,
        sample_candidates: list[RepoCandidate],
    ) -> None:
        """Deleting a pool should make it unretrievable."""
        async with pool_manager:
            pool = await pool_manager.create_pool(sample_query, sample_candidates)

            success = await pool_manager.delete_pool(pool.pool_id)
            assert success is True

            result = await pool_manager.get_pool(pool.pool_id)
            assert result is None


class TestContextManager:
    """Tests for async context manager."""

    async def test_close_cleans_up(
        self,
        tmp_path: Path,
    ) -> None:
        """Close should not raise errors."""
        pm = PoolManager(db_path=tmp_path / "test.db")
        async with pm:
            pass  # Should not raise
