"""Tests for orphan clone directory cleanup — T3.3."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from github_discovery.screening.gate2_static import cleanup_orphan_clones


class TestCleanupOrphanClones:
    """Tests for cleanup_orphan_clones utility function."""

    def test_removes_old_clone_dirs(self, tmp_path: Path) -> None:
        """Directories older than max_age_hours are removed."""
        old_dir = tmp_path / "ghdisc_clone_old"
        old_dir.mkdir()
        # Set mtime to 7 hours ago
        old_time = time.time() - (7 * 3600)
        import os

        os.utime(old_dir, (old_time, old_time))

        # Monkey-patch tempfile.gettempdir to use our tmp_path
        original = tempfile.gettempdir
        tempfile.gettempdir = lambda: str(tmp_path)  # type: ignore[assignment]
        try:
            removed = cleanup_orphan_clones(prefix="ghdisc_", max_age_hours=6.0)
        finally:
            tempfile.gettempdir = original  # type: ignore[assignment]

        assert removed == 1
        assert not old_dir.exists()

    def test_keeps_recent_clone_dirs(self, tmp_path: Path) -> None:
        """Directories newer than max_age_hours are kept."""
        recent_dir = tmp_path / "ghdisc_clone_recent"
        recent_dir.mkdir()

        original = tempfile.gettempdir
        tempfile.gettempdir = lambda: str(tmp_path)  # type: ignore[assignment]
        try:
            removed = cleanup_orphan_clones(prefix="ghdisc_", max_age_hours=6.0)
        finally:
            tempfile.gettempdir = original  # type: ignore[assignment]

        assert removed == 0
        assert recent_dir.exists()

    def test_ignores_non_matching_dirs(self, tmp_path: Path) -> None:
        """Directories not matching prefix are ignored."""
        import os

        other_dir = tmp_path / "other_prefix_dir"
        other_dir.mkdir()
        old_time = time.time() - (10 * 3600)
        os.utime(other_dir, (old_time, old_time))

        original = tempfile.gettempdir
        tempfile.gettempdir = lambda: str(tmp_path)  # type: ignore[assignment]
        try:
            removed = cleanup_orphan_clones(prefix="ghdisc_", max_age_hours=6.0)
        finally:
            tempfile.gettempdir = original  # type: ignore[assignment]

        assert removed == 0
        assert other_dir.exists()

    def test_mixed_old_and_new(self, tmp_path: Path) -> None:
        """Only old directories are removed; new ones are kept."""
        import os

        old_dir = tmp_path / "ghdisc_old"
        old_dir.mkdir()
        old_time = time.time() - (8 * 3600)
        os.utime(old_dir, (old_time, old_time))

        new_dir = tmp_path / "ghdisc_new"
        new_dir.mkdir()

        original = tempfile.gettempdir
        tempfile.gettempdir = lambda: str(tmp_path)  # type: ignore[assignment]
        try:
            removed = cleanup_orphan_clones(prefix="ghdisc_", max_age_hours=6.0)
        finally:
            tempfile.gettempdir = original  # type: ignore[assignment]

        assert removed == 1
        assert not old_dir.exists()
        assert new_dir.exists()

    def test_empty_temp_dir(self, tmp_path: Path) -> None:
        """No matching dirs → returns 0."""
        original = tempfile.gettempdir
        tempfile.gettempdir = lambda: str(tmp_path)  # type: ignore[assignment]
        try:
            removed = cleanup_orphan_clones(prefix="ghdisc_", max_age_hours=6.0)
        finally:
            tempfile.gettempdir = original  # type: ignore[assignment]

        assert removed == 0
