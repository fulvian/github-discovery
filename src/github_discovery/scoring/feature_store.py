"""SQLite-backed feature store for caching computed scores.

Stores ScoreResult per repo+SHA. Avoids expensive recomputation
when the same repo at the same commit is scored again.

Key: full_name + commit_sha (same as models/features.py)
TTL: configurable (default 48 hours)
Invalidation: automatic on new commit_sha or TTL expiry

Consistent with discovery/pool.py SQLite pattern.
"""

from __future__ import annotations

import contextlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite
import structlog

from github_discovery.models.enums import DomainType, ScoreDimension
from github_discovery.models.scoring import ScoreResult
from github_discovery.scoring.types import FeatureStoreStats

logger = structlog.get_logger("github_discovery.scoring.feature_store")

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS score_features (
    full_name TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    domain TEXT NOT NULL DEFAULT 'other',
    quality_score REAL NOT NULL,
    value_score REAL NOT NULL,
    confidence REAL NOT NULL,
    stars INTEGER NOT NULL DEFAULT 0,
    gate1_total REAL NOT NULL DEFAULT 0.0,
    gate2_total REAL NOT NULL DEFAULT 0.0,
    gate3_available INTEGER NOT NULL DEFAULT 0,
    dimension_scores TEXT NOT NULL DEFAULT '{}',
    scored_at TEXT NOT NULL,
    ttl_hours INTEGER NOT NULL DEFAULT 48,
    expires_at TEXT,
    PRIMARY KEY (full_name, commit_sha)
);

CREATE INDEX IF NOT EXISTS idx_score_features_domain
    ON score_features(domain);
CREATE INDEX IF NOT EXISTS idx_score_features_scored_at
    ON score_features(scored_at);
"""

# Indexes added post-migration (require expires_at column)
_POST_MIGRATION_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_score_features_expires_at
    ON score_features(expires_at);
"""

# Migration SQL: add expires_at column to existing databases
_MIGRATION_SQL = """
ALTER TABLE score_features ADD COLUMN expires_at TEXT;
"""


class FeatureStore:
    """SQLite-backed feature store for caching computed scores.

    Stores ScoreResult per repo+SHA. Avoids expensive recomputation
    when the same repo at the same commit is scored again.

    Usage:
        store = FeatureStore(db_path="scores.db", ttl_hours=48)
        await store.initialize()
        await store.put(score_result)
        cached = await store.get("owner/repo", "abc123")
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        ttl_hours: int = 48,
    ) -> None:
        """Initialize FeatureStore with database path and TTL."""
        self._db_path = db_path
        self._ttl_hours = ttl_hours
        self._db: aiosqlite.Connection | None = None

    async def _get_db(self) -> aiosqlite.Connection:
        """Get or create the database connection."""
        if self._db is None:
            # Ensure parent directory exists for file-based databases
            db_path = Path(self._db_path)
            if db_path.parent and not db_path.parent.exists():
                db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db = await aiosqlite.connect(self._db_path)
            self._db.row_factory = aiosqlite.Row
            await self._db.executescript(_CREATE_TABLE_SQL)
            # Run migration for existing databases missing expires_at column
            with contextlib.suppress(Exception):
                await self._db.execute(_MIGRATION_SQL)
            # Create index on expires_at (safe after migration)
            with contextlib.suppress(Exception):
                await self._db.executescript(_POST_MIGRATION_INDEX_SQL)
            await self._db.commit()
        return self._db

    async def initialize(self) -> None:
        """Create tables if not exist."""
        await self._get_db()

    async def get(
        self,
        full_name: str,
        commit_sha: str,
    ) -> ScoreResult | None:
        """Get cached score result. Returns None if not found or expired."""
        db = await self._get_db()
        now_iso = datetime.now(UTC).isoformat()
        cursor = await db.execute(
            (
                "SELECT * FROM score_features "
                "WHERE full_name = ? AND commit_sha = ? "
                "AND (expires_at IS NULL OR expires_at > ?)"
            ),
            (full_name, commit_sha, now_iso),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        return self._row_to_result(row)

    async def put(self, result: ScoreResult) -> None:
        """Store a score result. Upsert on full_name + commit_sha."""
        db = await self._get_db()
        dim_json = self._serialize_dimensions(result.dimension_scores)

        # Compute expires_at from scored_at + ttl
        scored_at_dt = result.scored_at
        expires_at_dt = scored_at_dt + timedelta(hours=self._ttl_hours)
        expires_at_iso = expires_at_dt.isoformat()

        await db.execute(
            """
            INSERT OR REPLACE INTO score_features
                (full_name, commit_sha, domain, quality_score, value_score,
                 confidence, stars, gate1_total, gate2_total, gate3_available,
                 dimension_scores, scored_at, ttl_hours, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.full_name,
                result.commit_sha,
                result.domain.value,
                result.quality_score,
                result.value_score,
                result.confidence,
                result.stars,
                result.gate1_total,
                result.gate2_total,
                1 if result.gate3_available else 0,
                dim_json,
                result.scored_at.isoformat(),
                self._ttl_hours,
                expires_at_iso,
            ),
        )
        await db.commit()

    async def get_batch(
        self,
        keys: list[tuple[str, str]],
    ) -> dict[tuple[str, str], ScoreResult | None]:
        """Get multiple cached results at once.

        Args:
            keys: List of (full_name, commit_sha) tuples.

        Returns:
            Dict keyed by (full_name, commit_sha) tuple with ScoreResult or None.
        """
        results: dict[tuple[str, str], ScoreResult | None] = {}
        for full_name, commit_sha in keys:
            results[(full_name, commit_sha)] = await self.get(full_name, commit_sha)
        return results

    async def put_batch(self, results: list[ScoreResult]) -> None:
        """Store multiple results at once using a single transaction."""
        db = await self._get_db()
        rows = [
            (
                result.full_name,
                result.commit_sha,
                result.domain.value,
                result.quality_score,
                result.value_score,
                result.confidence,
                result.stars,
                result.gate1_total,
                result.gate2_total,
                1 if result.gate3_available else 0,
                self._serialize_dimensions(result.dimension_scores),
                result.scored_at.isoformat(),
                self._ttl_hours,
                (result.scored_at + timedelta(hours=self._ttl_hours)).isoformat(),
            )
            for result in results
        ]
        await db.executemany(
            """
            INSERT OR REPLACE INTO score_features
                (full_name, commit_sha, domain, quality_score, value_score,
                 confidence, stars, gate1_total, gate2_total, gate3_available,
                 dimension_scores, scored_at, ttl_hours, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        await db.commit()

    async def delete(self, full_name: str, commit_sha: str) -> bool:
        """Delete a cached result. Returns True if existed."""
        db = await self._get_db()
        cursor = await db.execute(
            "DELETE FROM score_features WHERE full_name = ? AND commit_sha = ?",
            (full_name, commit_sha),
        )
        await db.commit()
        return cursor.rowcount > 0

    async def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        db = await self._get_db()

        # Calculate cutoff based on max TTL
        cutoff = datetime.now(UTC) - timedelta(hours=self._ttl_hours)
        cutoff_str = cutoff.isoformat()

        cursor = await db.execute(
            "DELETE FROM score_features WHERE scored_at < ?",
            (cutoff_str,),
        )
        await db.commit()
        removed = cursor.rowcount
        if removed > 0:
            logger.info("feature_store_cleanup", removed=removed)
        return removed

    async def prune_expired(self, dry_run: bool = False) -> int:
        """Remove entries past their expires_at timestamp.

        Uses the expires_at column for precise expiry. Falls back to
        scored_at + ttl_hours for rows where expires_at is NULL.

        Args:
            dry_run: If True, count but don't delete.

        Returns:
            Number of expired entries (deleted or counted).
        """
        db = await self._get_db()
        now_iso = datetime.now(UTC).isoformat()

        if dry_run:
            cursor = await db.execute(
                (
                    "SELECT COUNT(*) as cnt FROM score_features "
                    "WHERE (expires_at IS NOT NULL AND expires_at <= ?) "
                    "OR (expires_at IS NULL AND scored_at < ?)"
                ),
                (now_iso, (datetime.now(UTC) - timedelta(hours=self._ttl_hours)).isoformat()),
            )
            row = await cursor.fetchone()
            return row["cnt"] if row else 0

        cursor = await db.execute(
            (
                "DELETE FROM score_features "
                "WHERE (expires_at IS NOT NULL AND expires_at <= ?) "
                "OR (expires_at IS NULL AND scored_at < ?)"
            ),
            (now_iso, (datetime.now(UTC) - timedelta(hours=self._ttl_hours)).isoformat()),
        )
        await db.commit()
        removed = cursor.rowcount
        if removed > 0:
            logger.info("feature_store_prune_expired", removed=removed)
        return removed

    async def get_stats(self) -> FeatureStoreStats:
        """Get store statistics (total entries, expired, by domain)."""
        db = await self._get_db()

        # Total count
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM score_features")
        row = await cursor.fetchone()
        total = row["cnt"] if row else 0

        # Expired count
        cutoff = (datetime.now(UTC) - timedelta(hours=self._ttl_hours)).isoformat()
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM score_features WHERE scored_at < ?",
            (cutoff,),
        )
        row = await cursor.fetchone()
        expired = row["cnt"] if row else 0

        # By domain
        cursor = await db.execute(
            "SELECT domain, COUNT(*) as cnt FROM score_features GROUP BY domain",
        )
        domains: dict[str, int] = {}
        async for row in cursor:
            domains[row["domain"]] = row["cnt"]

        # Oldest/newest
        cursor = await db.execute(
            "SELECT MIN(scored_at) as oldest, MAX(scored_at) as newest FROM score_features",
        )
        row = await cursor.fetchone()
        oldest = datetime.fromisoformat(row["oldest"]) if row and row["oldest"] else None
        newest = datetime.fromisoformat(row["newest"]) if row and row["newest"] else None

        return FeatureStoreStats(
            total_entries=total,
            expired_entries=expired,
            domains=domains,
            oldest_entry=oldest,
            newest_entry=newest,
        )

    async def get_by_domain(
        self,
        domain: DomainType,
    ) -> list[ScoreResult]:
        """Get all non-expired score results for a domain.

        Args:
            domain: Domain type to filter by.

        Returns:
            List of ScoreResult for the given domain.
        """
        db = await self._get_db()
        cutoff = (datetime.now(UTC) - timedelta(hours=self._ttl_hours)).isoformat()
        cursor = await db.execute(
            "SELECT * FROM score_features WHERE domain = ? AND scored_at >= ?",
            (domain.value, cutoff),
        )
        rows = await cursor.fetchall()
        return [self._row_to_result(row) for row in rows]

    async def get_latest(
        self,
        full_name: str,
    ) -> ScoreResult | None:
        """Get the most recent score result for a repo.

        Args:
            full_name: Repository full name (owner/repo).

        Returns:
            Most recent ScoreResult or None if not found or expired.
        """
        db = await self._get_db()
        cutoff = (datetime.now(UTC) - timedelta(hours=self._ttl_hours)).isoformat()
        cursor = await db.execute(
            "SELECT * FROM score_features WHERE full_name = ? AND scored_at >= ? "
            "ORDER BY scored_at DESC LIMIT 1",
            (full_name, cutoff),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_result(row)

    async def close(self) -> None:
        """Close database connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    def _serialize_dimensions(self, dims: dict[ScoreDimension, float]) -> str:
        """Serialize dimension scores to JSON string."""
        return json.dumps({k.value: v for k, v in dims.items()})

    def _row_to_result(self, row: aiosqlite.Row) -> ScoreResult:
        """Convert a database row to ScoreResult."""
        dim_raw = json.loads(row["dimension_scores"])
        dimension_scores: dict[ScoreDimension, float] = {}
        for k, v in dim_raw.items():
            with contextlib.suppress(ValueError):
                dimension_scores[ScoreDimension(k)] = v

        return ScoreResult(
            full_name=row["full_name"],
            commit_sha=row["commit_sha"],
            domain=DomainType(row["domain"]),
            quality_score=row["quality_score"],
            dimension_scores=dimension_scores,
            confidence=row["confidence"],
            stars=row["stars"],
            gate1_total=row["gate1_total"],
            gate2_total=row["gate2_total"],
            gate3_available=bool(row["gate3_available"]),
            scored_at=datetime.fromisoformat(row["scored_at"]),
        )
