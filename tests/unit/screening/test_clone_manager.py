"""Tests for the refcounted CloneManager (Wave I3).

Verifies:
1. acquire returns a valid path
2. Acquiring the same repo increments refcount and reuses path
3. release decrements refcount
4. Cleanup only happens after grace period
5. cleanup_all removes all clones
6. Singleton pattern works
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel, DomainType
from github_discovery.screening.clone_manager import CloneManager, get_clone_manager


def _make_candidate(full_name: str = "owner/repo") -> RepoCandidate:
    """Create a minimal RepoCandidate for testing."""
    dt = datetime(2024, 1, 1)
    return RepoCandidate(
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        html_url=f"https://github.com/{full_name}",
        api_url=f"https://api.github.com/repos/{full_name}",
        description="test repo",
        language="Python",
        domain=DomainType.OTHER,
        stars=0,
        default_branch="main",
        source_channel=DiscoveryChannel.SEARCH,
        created_at=dt,
        updated_at=dt,
        owner_login=full_name.split("/", maxsplit=1)[0],
    )


class TestCloneManager:
    """Test refcounted CloneManager operations."""

    async def test_acquire_returns_path(self) -> None:
        """acquire returns a valid directory path."""
        mgr = CloneManager()
        candidate = _make_candidate("test/acquire")

        with patch.object(mgr, "_do_clone", AsyncMock(return_value=Path("/tmp/ghdisc_test"))):  # noqa: S108
            path = await mgr.acquire(candidate)
            assert path is not None
            assert isinstance(path, Path)

    async def test_acquire_reuses_clone_on_second_call(self) -> None:
        """Acquiring same repo twice reuses the path and increments refcount."""
        mgr = CloneManager()
        candidate = _make_candidate("test/reuse")

        with patch.object(mgr, "_do_clone", AsyncMock(return_value=Path("/tmp/ghdisc_reuse"))):  # noqa: S108
            path1 = await mgr.acquire(candidate)
            path2 = await mgr.acquire(candidate)
            assert path1 == path2
            assert path1 is not None
            # _do_clone should be called only once
            mgr._do_clone.assert_awaited_once()  # type: ignore[attr-defined]

    async def test_release_decrements_refcount(self) -> None:
        """release decreases refcount."""
        mgr = CloneManager()
        candidate = _make_candidate("test/release")

        with patch.object(mgr, "_do_clone", AsyncMock(return_value=Path("/tmp/ghdisc_release"))):  # noqa: S108
            await mgr.acquire(candidate)
            await mgr.acquire(candidate)

            async with mgr._lock:
                entry = mgr._clones[candidate.full_name]
                assert entry.refcount == 2

            await mgr.release(candidate.full_name)
            async with mgr._lock:
                assert mgr._clones[candidate.full_name].refcount == 1

    async def test_cleanup_all_removes_clones(self) -> None:
        """cleanup_all removes all tracked clones."""
        mgr = CloneManager()
        candidate = _make_candidate("test/cleanup-all")

        with (
            patch.object(mgr, "_do_clone", AsyncMock(return_value=Path("/tmp/ghdisc_cleanup"))),  # noqa: S108
            patch.object(mgr, "_rm_tree") as mock_rm,
        ):
            await mgr.acquire(candidate)
            count = await mgr.cleanup_all()
            assert count == 1
            mock_rm.assert_called_once()

    async def test_singleton_returns_same_instance(self) -> None:
        """get_clone_manager() returns the same instance across calls."""
        mgr1 = get_clone_manager()
        mgr2 = get_clone_manager()
        assert mgr1 is mgr2

    async def test_close_cleans_up(self) -> None:
        """close() should call cleanup_all."""
        mgr = CloneManager()
        with patch.object(mgr, "cleanup_all", AsyncMock(return_value=0)):
            await mgr.close()
            mgr.cleanup_all.assert_awaited_once()  # type: ignore[attr-defined]
