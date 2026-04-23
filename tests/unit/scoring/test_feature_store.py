"""Tests for SQLite-backed feature store."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from github_discovery.models.enums import DomainType, ScoreDimension
from github_discovery.scoring.feature_store import FeatureStore
from tests.unit.scoring.conftest import _make_score_result


@pytest.fixture
async def feature_store(tmp_path):
    """FeatureStore with temp SQLite database."""
    db_path = str(tmp_path / "test_scores.db")
    store = FeatureStore(db_path=db_path, ttl_hours=48)
    await store.initialize()
    yield store
    await store.close()


class TestFeatureStoreCRUD:
    """Tests for basic CRUD operations."""

    async def test_put_and_get(self, feature_store) -> None:
        """Put a result and retrieve it."""
        result = _make_score_result(full_name="test/repo", commit_sha="abc123")
        await feature_store.put(result)
        cached = await feature_store.get("test/repo", "abc123")
        assert cached is not None
        assert cached.full_name == "test/repo"
        assert cached.quality_score == result.quality_score

    async def test_get_not_found(self, feature_store) -> None:
        """Get returns None for non-existent entry."""
        cached = await feature_store.get("nonexistent/repo", "noshsha")
        assert cached is None

    async def test_upsert_replaces(self, feature_store) -> None:
        """Second put with same key replaces the first."""
        result_v1 = _make_score_result(full_name="test/repo", quality_score=0.5)
        result_v2 = _make_score_result(full_name="test/repo", quality_score=0.9)
        await feature_store.put(result_v1)
        await feature_store.put(result_v2)
        cached = await feature_store.get("test/repo", "abc123")
        assert cached is not None
        assert cached.quality_score == 0.9

    async def test_delete(self, feature_store) -> None:
        """Delete removes an entry."""
        result = _make_score_result(full_name="test/repo")
        await feature_store.put(result)
        deleted = await feature_store.delete("test/repo", "abc123")
        assert deleted is True
        cached = await feature_store.get("test/repo", "abc123")
        assert cached is None

    async def test_delete_nonexistent(self, feature_store) -> None:
        """Delete returns False for non-existent entry."""
        deleted = await feature_store.delete("no/repo", "nosha")
        assert deleted is False


class TestFeatureStoreBatch:
    """Tests for batch operations."""

    async def test_put_batch(self, feature_store) -> None:
        """put_batch stores multiple results."""
        results = [
            _make_score_result(full_name=f"test/repo{i}", commit_sha=f"sha{i}") for i in range(5)
        ]
        await feature_store.put_batch(results)
        for i in range(5):
            cached = await feature_store.get(f"test/repo{i}", f"sha{i}")
            assert cached is not None

    async def test_get_batch(self, feature_store) -> None:
        """get_batch retrieves multiple results."""
        results = [
            _make_score_result(full_name=f"test/repo{i}", commit_sha=f"sha{i}") for i in range(3)
        ]
        await feature_store.put_batch(results)
        keys = [(f"test/repo{i}", f"sha{i}") for i in range(3)]
        batch = await feature_store.get_batch(keys)
        assert len(batch) == 3
        assert all(v is not None for v in batch.values())

    async def test_get_batch_missing(self, feature_store) -> None:
        """get_batch returns None for missing entries."""
        keys = [("no/repo", "nosha")]
        batch = await feature_store.get_batch(keys)
        assert batch[("no/repo", "nosha")] is None


class TestFeatureStoreTTL:
    """Tests for TTL expiration."""

    async def test_expired_entry_not_returned(self, feature_store) -> None:
        """Expired entries are not returned by get()."""
        result = _make_score_result(full_name="test/expired")
        await feature_store.put(result)

        # Manually update scored_at to be expired
        db = feature_store._db
        assert db is not None
        expired_time = (datetime.now(UTC) - timedelta(hours=50)).isoformat()
        await db.execute(
            "UPDATE score_features SET scored_at = ? WHERE full_name = ?",
            (expired_time, "test/expired"),
        )
        await db.commit()

        cached = await feature_store.get("test/expired", "abc123")
        assert cached is None


class TestFeatureStoreCleanup:
    """Tests for cleanup and stats."""

    async def test_cleanup_expired(self, feature_store) -> None:
        """cleanup_expired removes expired entries."""
        result = _make_score_result(full_name="test/old")
        await feature_store.put(result)

        db = feature_store._db
        assert db is not None
        expired_time = (datetime.now(UTC) - timedelta(hours=50)).isoformat()
        await db.execute(
            "UPDATE score_features SET scored_at = ? WHERE full_name = ?",
            (expired_time, "test/old"),
        )
        await db.commit()

        removed = await feature_store.cleanup_expired()
        assert removed >= 1

    async def test_get_stats(self, feature_store) -> None:
        """get_stats returns store statistics."""
        results = [
            _make_score_result(
                full_name=f"test/repo{i}",
                commit_sha=f"sha{i}",
                domain=DomainType.LIBRARY,
            )
            for i in range(3)
        ]
        await feature_store.put_batch(results)
        stats = await feature_store.get_stats()
        assert stats.total_entries >= 3
        assert stats.domains.get("library", 0) >= 3

    async def test_get_stats_empty(self, feature_store) -> None:
        """get_stats on empty store."""
        stats = await feature_store.get_stats()
        assert stats.total_entries == 0
        assert stats.oldest_entry is None

    async def test_stats_newest_oldest(self, feature_store) -> None:
        """Stats track oldest and newest entries."""
        result = _make_score_result(full_name="test/repo")
        await feature_store.put(result)
        stats = await feature_store.get_stats()
        assert stats.oldest_entry is not None
        assert stats.newest_entry is not None


class TestFeatureStoreSerialization:
    """Tests for dimension score serialization/deserialization."""

    async def test_dimension_scores_roundtrip(self, feature_store) -> None:
        """Dimension scores survive serialization to/from SQLite."""
        dims = {
            ScoreDimension.CODE_QUALITY: 0.85,
            ScoreDimension.ARCHITECTURE: 0.72,
            ScoreDimension.TESTING: 0.90,
            ScoreDimension.DOCUMENTATION: 0.55,
            ScoreDimension.MAINTENANCE: 0.68,
            ScoreDimension.SECURITY: 0.61,
            ScoreDimension.FUNCTIONALITY: 0.77,
            ScoreDimension.INNOVATION: 0.42,
        }
        result = _make_score_result(dimension_scores=dims)
        await feature_store.put(result)
        cached = await feature_store.get("test/repo", "abc123")
        assert cached is not None
        for dim, expected in dims.items():
            assert cached.dimension_scores[dim] == pytest.approx(expected, abs=0.01)

    async def test_domain_preserved(self, feature_store) -> None:
        """Domain type is preserved through serialization."""
        result = _make_score_result(domain=DomainType.WEB_FRAMEWORK)
        await feature_store.put(result)
        cached = await feature_store.get("test/repo", "abc123")
        assert cached is not None
        assert cached.domain == DomainType.WEB_FRAMEWORK

    async def test_gate3_available_preserved(self, feature_store) -> None:
        """gate3_available flag is preserved."""
        result = _make_score_result()
        result.gate3_available = True
        await feature_store.put(result)
        cached = await feature_store.get("test/repo", "abc123")
        assert cached is not None
        assert cached.gate3_available is True
