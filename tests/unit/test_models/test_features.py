"""Tests for feature store models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from github_discovery.models.features import FeatureStoreKey, RepoFeatures
from github_discovery.models.screening import MetadataScreenResult


class TestFeatureStoreKey:
    """Test feature store composite key."""

    def test_key_creation(self) -> None:
        """Key can be created with full_name and commit_sha."""
        key = FeatureStoreKey(full_name="test/repo", commit_sha="abc123")
        assert key.full_name == "test/repo"
        assert key.commit_sha == "abc123"

    def test_key_equality(self) -> None:
        """Keys with same values are equal."""
        key1 = FeatureStoreKey(full_name="test/repo", commit_sha="abc123")
        key2 = FeatureStoreKey(full_name="test/repo", commit_sha="abc123")
        assert key1 == key2

    def test_key_inequality_sha(self) -> None:
        """Keys with different SHA are not equal."""
        key1 = FeatureStoreKey(full_name="test/repo", commit_sha="abc123")
        key2 = FeatureStoreKey(full_name="test/repo", commit_sha="def456")
        assert key1 != key2


class TestRepoFeatures:
    """Test cached feature set."""

    def test_empty_features(self) -> None:
        """Empty features have no gate results."""
        features = RepoFeatures(full_name="test/repo", commit_sha="abc123")
        assert features.highest_gate_completed == 0
        assert features.is_fully_assessed is False

    def test_features_with_gate1(self) -> None:
        """Features with only Gate 1 result."""
        features = RepoFeatures(
            full_name="test/repo",
            commit_sha="abc123",
            gate1_result=MetadataScreenResult(
                full_name="test/repo",
                gate1_total=0.7,
                gate1_pass=True,
            ),
        )
        assert features.highest_gate_completed == 1
        assert features.is_fully_assessed is False

    def test_is_expired(self) -> None:
        """Features check TTL expiry."""
        # Not expired: computed now
        fresh = RepoFeatures(full_name="test/repo", commit_sha="abc123")
        assert fresh.is_expired is False

        # Expired: computed 48 hours ago with 24h TTL
        expired = RepoFeatures(
            full_name="test/repo",
            commit_sha="abc123",
            computed_at=datetime.now(UTC) - timedelta(hours=48),
            ttl_hours=24,
        )
        assert expired.is_expired is True

    def test_store_key(self) -> None:
        """Features provide their cache key."""
        features = RepoFeatures(full_name="test/repo", commit_sha="abc123")
        key = features.store_key
        assert key.full_name == "test/repo"
        assert key.commit_sha == "abc123"

    def test_json_round_trip(self) -> None:
        """RepoFeatures serializes to/from JSON."""
        features = RepoFeatures(full_name="test/repo", commit_sha="abc123")
        json_str = features.model_dump_json()
        restored = RepoFeatures.model_validate_json(json_str)
        assert restored.full_name == features.full_name
        assert restored.commit_sha == features.commit_sha
