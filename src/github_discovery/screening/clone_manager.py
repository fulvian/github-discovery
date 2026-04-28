"""CloneManager — refcounted shallow clone reuse across Gate 2 + Gate 3.

Singleton that manages shallow git clones shared between screening
(Gate 2) and assessment (Gate 3). Each repo gets a single clone
directory with a reference count. When the refcount drops to 0,
the clone is cleaned up after a 60-second grace period.

Wave I3: Clone reuse across pipeline stages eliminates double-clone
overhead documented in BUG 3.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from github_discovery.models.candidate import RepoCandidate

logger = structlog.get_logger("github_discovery.screening.clone_manager")

_CLONE_PREFIX = "ghdisc_shared_"
_GRACE_PERIOD_SECONDS = 60.0
_CLEANUP_INTERVAL_SECONDS = 30.0


class CloneManager:
    """Refcounted shallow clone manager.

    Provides shared access to shallow git clones across pipeline stages.
    Gate 2 (screening) and Gate 3 (assessment/repomix) share the same
    clone, eliminating redundant ``git clone --depth=1`` operations.

    Usage::

        mgr = CloneManager()
        clone_path = await mgr.acquire(candidate)
        try:
            # Gate 2 uses clone_path for gitleaks/scc
            # Gate 3 passes clone_path to repomix
            ...
        finally:
            await mgr.release(candidate.full_name)
    """

    def __init__(self) -> None:
        """Initialize empty clone manager with no tracked clones."""
        self._clones: dict[str, _CloneEntry] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task[None] | None = None

    async def acquire(self, candidate: RepoCandidate) -> Path | None:
        """Acquire a refcounted shallow clone for a repo.

        If a clone already exists for this repo, increments the
        refcount and returns the existing path. Otherwise, creates
        a new shallow clone.

        Args:
            candidate: Repository to clone.

        Returns:
            Path to the clone directory, or None if cloning fails.
        """
        async with self._lock:
            if candidate.full_name in self._clones:
                entry = self._clones[candidate.full_name]
                entry.refcount += 1
                logger.debug(
                    "clone_reuse",
                    repo=candidate.full_name,
                    refcount=entry.refcount,
                    path=str(entry.path),
                )
                return entry.path

        # Clone outside the lock to avoid blocking other operations
        clone_path = await self._do_clone(candidate)
        if clone_path is None:
            return None

        async with self._lock:
            self._clones[candidate.full_name] = _CloneEntry(
                path=clone_path,
                refcount=1,
                created_at=time.monotonic(),
            )
            logger.info(
                "clone_acquired",
                repo=candidate.full_name,
                path=str(clone_path),
            )
            self._start_cleanup_loop()
            return clone_path

    async def release(self, full_name: str) -> None:
        """Release a clone reference. Cleans up when refcount reaches 0."""
        async with self._lock:
            entry = self._clones.get(full_name)
            if entry is None:
                return

            entry.refcount -= 1
            logger.debug(
                "clone_released",
                repo=full_name,
                refcount=entry.refcount,
            )

            if entry.refcount <= 0:
                entry.grace_until = time.monotonic() + _GRACE_PERIOD_SECONDS
                logger.info(
                    "clone_grace_period",
                    repo=full_name,
                    grace_seconds=_GRACE_PERIOD_SECONDS,
                )

    async def cleanup_expired(self) -> int:
        """Remove clones past their grace period.

        Returns:
            Number of directories cleaned up.
        """
        now = time.monotonic()
        to_remove: list[str] = []

        async with self._lock:
            for full_name, entry in list(self._clones.items()):
                if (
                    entry.refcount <= 0
                    and entry.grace_until is not None
                    and now >= entry.grace_until
                ):
                    to_remove.append(full_name)

            for full_name in to_remove:
                entry = self._clones.pop(full_name)
                self._rm_tree(entry.path)
                logger.info("clone_cleaned", repo=full_name, path=str(entry.path))

        return len(to_remove)

    async def cleanup_all(self) -> int:
        """Force cleanup of all managed clones (for shutdown)."""
        async with self._lock:
            count = len(self._clones)
            for full_name, entry in self._clones.items():
                self._rm_tree(entry.path)
                logger.debug("clone_force_cleaned", repo=full_name, path=str(entry.path))
            self._clones.clear()

        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            self._cleanup_task = None

        return count

    async def close(self) -> None:
        """Close manager and clean up all clones."""
        await self.cleanup_all()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _do_clone(self, candidate: RepoCandidate) -> Path | None:
        """Execute shallow clone to temp directory."""
        clone_dir = Path(tempfile.mkdtemp(prefix=f"{_CLONE_PREFIX}{candidate.repo_name}_"))

        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                "clone",
                "--depth=1",
                candidate.url,
                str(clone_dir),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            returncode = await proc.wait()
            if returncode == 0:
                return clone_dir

            logger.warning(
                "clone_failed",
                repo=candidate.full_name,
                returncode=returncode,
            )
            self._rm_tree(clone_dir)
            return None
        except (OSError, asyncio.CancelledError) as exc:
            logger.warning("clone_error", repo=candidate.full_name, error=str(exc))
            self._rm_tree(clone_dir)
            return None

    def _rm_tree(self, path: Path) -> None:
        """Remove a directory tree."""
        try:
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass

    def _start_cleanup_loop(self) -> None:
        """Start the periodic cleanup task if not already running."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        """Periodic background cleanup of expired clones."""
        try:
            while True:
                await asyncio.sleep(_CLEANUP_INTERVAL_SECONDS)
                cleaned = await self.cleanup_expired()
                if cleaned > 0:
                    logger.debug("periodic_clone_cleanup", cleaned=cleaned)
        except asyncio.CancelledError:
            pass


@dataclass
class _CloneEntry:
    """Internal entry for a managed clone."""

    path: Path
    refcount: int = 0
    created_at: float = 0.0
    grace_until: float | None = None


# Module-level singleton — use get_clone_manager() to access.
# Using a function attribute instead of module global to satisfy PLW0603.
def get_clone_manager() -> CloneManager:
    """Get or create the shared CloneManager singleton.

    Returns:
        The module-level CloneManager instance.
    """
    if not hasattr(get_clone_manager, "_instance") or get_clone_manager._instance is None:  # type: ignore[has-type]
        get_clone_manager._instance = CloneManager()  # type: ignore[attr-defined]
    return get_clone_manager._instance  # type: ignore[return-value]
