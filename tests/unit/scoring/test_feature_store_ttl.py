"""Tests for FeatureStore TTL with expires_at column — T3.5."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from github_discovery.scoring.feature_store import FeatureStore
from tests.unit.scoring.conftest import _make_score_result


@pytest.fixture
async def feature_store():
    """FeatureStore with in-memory SQLite."""
    store = FeatureStore(db_path=":memory:", ttl_hours=48)
    await store.initialize()
    yield store
    await store.close()


class TestExpiresAtColumn:
    """Tests for expires_at column behavior."""

    async def test_put_sets_expires_at(self, feature_store: FeatureStore) -> None:
        """put() should set expires_at = scored_at + ttl_hours."""
        result = _make_score_result(full_name="test/repo")
        await feature_store.put(result)

        db = feature_store._db
        assert db is not None
        cursor = await db.execute(
            "SELECT expires_at FROM score_features WHERE full_name = ?",
            ("test/repo",),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["expires_at"] is not None

        expires_at = datetime.fromisoformat(row["expires_at"])
        expected = result.scored_at + timedelta(hours=48)
        assert abs((expires_at - expected).total_seconds()) < 2

    async def test_get_returns_non_expired(self, feature_store: FeatureStore) -> None:
        """get() returns result when expires_at is in the future."""
        result = _make_score_result(full_name="test/repo")
        await feature_store.put(result)

        cached = await feature_store.get("test/repo", "abc123")
        assert cached is not None

    async def test_get_returns_none_when_expired(self, feature_store: FeatureStore) -> None:
        """get() returns None when expires_at is in the past."""
        result = _make_score_result(full_name="test/expired")
        await feature_store.put(result)

        # Manually set expires_at to the past
        db = feature_store._db
        assert db is not None
        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        await db.execute(
            "UPDATE score_features SET expires_at = ? WHERE full_name = ?",
            (past, "test/expired"),
        )
        await db.commit()

        cached = await feature_store.get("test/expired", "abc123")
        assert cached is None


class TestPruneExpired:
    """Tests for prune_expired method."""

    async def test_prune_expired_removes_old_entries(
        self,
        feature_store: FeatureStore,
    ) -> None:
        """prune_expired removes entries past their expires_at."""
        result = _make_score_result(full_name="test/old")
        await feature_store.put(result)

        # Set expires_at to the past
        db = feature_store._db
        assert db is not None
        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        await db.execute(
            "UPDATE score_features SET expires_at = ? WHERE full_name = ?",
            (past, "test/old"),
        )
        await db.commit()

        removed = await feature_store.prune_expired()
        assert removed >= 1

        # Verify entry is gone
        cached = await feature_store.get("test/old", "abc123")
        assert cached is None

    async def test_prune_expired_keeps_valid_entries(
        self,
        feature_store: FeatureStore,
    ) -> None:
        """prune_expired keeps entries that haven't expired."""
        result = _make_score_result(full_name="test/valid")
        await feature_store.put(result)

        removed = await feature_store.prune_expired()
        assert removed == 0

        cached = await feature_store.get("test/valid", "abc123")
        assert cached is not None

    async def test_prune_expired_dry_run(
        self,
        feature_store: FeatureStore,
    ) -> None:
        """prune_expired with dry_run=True counts but doesn't delete."""
        result = _make_score_result(full_name="test/old")
        await feature_store.put(result)

        db = feature_store._db
        assert db is not None
        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        await db.execute(
            "UPDATE score_features SET expires_at = ? WHERE full_name = ?",
            (past, "test/old"),
        )
        await db.commit()

        count = await feature_store.prune_expired(dry_run=True)
        assert count >= 1

        # Entry still exists (not deleted)
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM score_features WHERE full_name = ?",
            ("test/old",),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["cnt"] == 1

    async def test_put_batch_sets_expires_at(
        self,
        feature_store: FeatureStore,
    ) -> None:
        """put_batch should set expires_at for all entries."""
        results = [
            _make_score_result(full_name=f"test/repo{i}", commit_sha=f"sha{i}") for i in range(3)
        ]
        await feature_store.put_batch(results)

        db = feature_store._db
        assert db is not None
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM score_features WHERE expires_at IS NOT NULL",
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["cnt"] >= 3


class TestExpiresAtReads:
    """Read paths must honor expires_at and not only scored_at."""

    async def test_get_by_domain_excludes_expired_by_expires_at(
        self,
        feature_store: FeatureStore,
    ) -> None:
        """get_by_domain should filter out rows expired via expires_at."""
        result = _make_score_result(full_name="test/by-domain")
        await feature_store.put(result)

        db = feature_store._db
        assert db is not None
        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        await db.execute(
            "UPDATE score_features SET expires_at = ? WHERE full_name = ?",
            (past, "test/by-domain"),
        )
        await db.commit()

        rows = await feature_store.get_by_domain(result.domain)
        assert all(r.full_name != "test/by-domain" for r in rows)

    async def test_get_latest_excludes_expired_by_expires_at(
        self,
        feature_store: FeatureStore,
    ) -> None:
        """get_latest should return None for entries expired by expires_at."""
        result = _make_score_result(full_name="test/latest")
        await feature_store.put(result)

        db = feature_store._db
        assert db is not None
        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        await db.execute(
            "UPDATE score_features SET expires_at = ? WHERE full_name = ?",
            (past, "test/latest"),
        )
        await db.commit()

        latest = await feature_store.get_latest("test/latest")
        assert latest is None

    async def test_get_stats_counts_expired_from_expires_at(
        self,
        feature_store: FeatureStore,
    ) -> None:
        """get_stats should include expires_at-expired rows in expired_entries."""
        await feature_store.put(_make_score_result(full_name="test/active"))
        await feature_store.put(_make_score_result(full_name="test/expired"))

        db = feature_store._db
        assert db is not None
        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        await db.execute(
            "UPDATE score_features SET expires_at = ? WHERE full_name = ?",
            (past, "test/expired"),
        )
        await db.commit()

        stats = await feature_store.get_stats()
        assert stats.total_entries >= 2
        assert stats.expired_entries >= 1
