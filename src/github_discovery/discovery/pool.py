"""Candidate pool persistence with SQLite backend.

Manages the lifecycle of candidate pools: create, retrieve,
add candidates (with dedup), update status, query by status.
Uses aiosqlite for non-blocking operations.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import aiosqlite
import structlog

from github_discovery.discovery.types import DiscoveryQuery
from github_discovery.models.candidate import CandidatePool, RepoCandidate

if TYPE_CHECKING:
    from github_discovery.models.enums import CandidateStatus

logger = structlog.get_logger("github_discovery.discovery.pool")

_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS pools (
    pool_id TEXT PRIMARY KEY,
    query_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    total_candidates INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS candidates (
    pool_id TEXT NOT NULL,
    full_name TEXT NOT NULL,
    data_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'discovered',
    discovery_score REAL NOT NULL DEFAULT 0.0,
    source_channels TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    PRIMARY KEY (pool_id, full_name),
    FOREIGN KEY (pool_id) REFERENCES pools(pool_id)
);
"""


class PoolManager:
    """Manages candidate pool persistence using SQLite.

    Provides CRUD operations for pools and candidates with
    deduplication by (pool_id, full_name).
    """

    def __init__(self, db_path: str = "github_discovery.db") -> None:
        """Initialize with path to SQLite database file."""
        self._db_path = str(db_path)
        self._db: aiosqlite.Connection | None = None

    async def _get_db(self) -> aiosqlite.Connection:
        """Get or create the database connection."""
        if self._db is None:
            self._db = await aiosqlite.connect(self._db_path)
            self._db.row_factory = aiosqlite.Row
            await self._db.executescript(_CREATE_TABLES_SQL)
            await self._db.commit()
        return self._db

    async def create_pool(
        self,
        query: DiscoveryQuery,
        candidates: list[RepoCandidate],
    ) -> CandidatePool:
        """Create a new pool with initial candidates."""
        db = await self._get_db()
        pool_id = str(uuid4())
        now = datetime.now(tz=UTC).isoformat()

        await db.execute(
            "INSERT INTO pools (pool_id, query_json, created_at, updated_at, total_candidates) "
            "VALUES (?, ?, ?, ?, ?)",
            (pool_id, query.model_dump_json(), now, now, len(candidates)),
        )

        for candidate in candidates:
            await self._insert_candidate(db, pool_id, candidate)

        await db.commit()

        return CandidatePool(
            pool_id=pool_id,
            query=query.query,
            candidates=candidates,
        )

    async def get_pool(self, pool_id: str) -> CandidatePool | None:
        """Retrieve a pool by ID. Returns None if not found."""
        db = await self._get_db()

        cursor = await db.execute(
            "SELECT pool_id, query_json, created_at, updated_at, total_candidates "
            "FROM pools WHERE pool_id = ?",
            (pool_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        candidates = await self._get_candidates_for_pool(db, pool_id)

        query_data = json.loads(row["query_json"])
        query = DiscoveryQuery.model_validate(query_data)

        return CandidatePool(
            pool_id=row["pool_id"],
            query=query.query,
            candidates=candidates,
        )

    async def add_candidates(
        self,
        pool_id: str,
        candidates: list[RepoCandidate],
    ) -> int:
        """Add candidates to existing pool. Returns count of new (non-duplicate) adds."""
        db = await self._get_db()
        new_count = 0

        for candidate in candidates:
            # Check if candidate already exists in this pool
            cursor = await db.execute(
                "SELECT full_name FROM candidates WHERE pool_id = ? AND full_name = ?",
                (pool_id, candidate.full_name),
            )
            existing = await cursor.fetchone()
            if existing is not None:
                continue  # Skip duplicate

            await self._insert_candidate(db, pool_id, candidate)
            new_count += 1

        if new_count > 0:
            await db.execute(
                "UPDATE pools SET total_candidates = "
                "(SELECT COUNT(*) FROM candidates WHERE pool_id = ?), "
                "updated_at = ? WHERE pool_id = ?",
                (pool_id, datetime.now(tz=UTC).isoformat(), pool_id),
            )

        await db.commit()
        return new_count

    async def update_candidate_status(
        self,
        pool_id: str,
        full_name: str,
        status: CandidateStatus,
    ) -> bool:
        """Update the status of a specific candidate in a pool."""
        db = await self._get_db()

        cursor = await db.execute(
            "UPDATE candidates SET status = ? WHERE pool_id = ? AND full_name = ?",
            (status.value, pool_id, full_name),
        )
        await db.commit()

        return cursor.rowcount > 0

    async def get_candidates(
        self,
        pool_id: str,
        *,
        status: CandidateStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RepoCandidate]:
        """Get candidates from a pool, optionally filtered by status."""
        db = await self._get_db()

        if status is not None:
            cursor = await db.execute(
                "SELECT data_json FROM candidates "
                "WHERE pool_id = ? AND status = ? "
                "ORDER BY discovery_score DESC LIMIT ? OFFSET ?",
                (pool_id, status.value, limit, offset),
            )
        else:
            cursor = await db.execute(
                "SELECT data_json FROM candidates "
                "WHERE pool_id = ? "
                "ORDER BY discovery_score DESC LIMIT ? OFFSET ?",
                (pool_id, limit, offset),
            )

        rows = await cursor.fetchall()
        return [RepoCandidate.model_validate_json(row["data_json"]) for row in rows]

    async def get_pool_stats(self, pool_id: str) -> dict[str, int]:
        """Return status-based stats for a pool."""
        db = await self._get_db()

        cursor = await db.execute(
            "SELECT status, COUNT(*) as cnt FROM candidates WHERE pool_id = ? GROUP BY status",
            (pool_id,),
        )
        rows = await cursor.fetchall()

        stats: dict[str, int] = {
            "total": 0,
            "discovered": 0,
            "screened": 0,
            "assessed": 0,
            "ranked": 0,
            "excluded": 0,
        }
        for row in rows:
            status = row["status"]
            count = row["cnt"]
            stats["total"] += count
            # Map status to simplified categories
            if status in ("discovered",):
                stats["discovered"] += count
            elif status in (
                "screening_gate1",
                "screening_gate2",
                "gate1_passed",
                "gate1_failed",
                "gate2_passed",
                "gate2_failed",
            ):
                stats["screened"] += count
            elif status in ("assessing", "assessed"):
                stats["assessed"] += count
            elif status in ("ranked",):
                stats["ranked"] += count
            elif status in ("excluded",):
                stats["excluded"] += count

        return stats

    async def delete_pool(self, pool_id: str) -> bool:
        """Delete a pool and all its candidates."""
        db = await self._get_db()

        await db.execute("DELETE FROM candidates WHERE pool_id = ?", (pool_id,))
        cursor = await db.execute("DELETE FROM pools WHERE pool_id = ?", (pool_id,))
        await db.commit()

        return cursor.rowcount > 0

    async def close(self) -> None:
        """Close the database connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def __aenter__(self) -> PoolManager:
        """Enter async context."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context."""
        await self.close()

    # --- Private helpers ---

    async def _insert_candidate(
        self,
        db: aiosqlite.Connection,
        pool_id: str,
        candidate: RepoCandidate,
    ) -> None:
        """Insert a candidate into the database (INSERT OR IGNORE for dedup)."""
        now = datetime.now(tz=UTC).isoformat()
        await db.execute(
            "INSERT OR IGNORE INTO candidates "
            "(pool_id, full_name, data_json, status, "
            "discovery_score, source_channels, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                pool_id,
                candidate.full_name,
                candidate.model_dump_json(),
                candidate.status.value,
                candidate.discovery_score,
                json.dumps([candidate.source_channel.value]),
                now,
            ),
        )

    async def _get_candidates_for_pool(
        self,
        db: aiosqlite.Connection,
        pool_id: str,
    ) -> list[RepoCandidate]:
        """Get all candidates for a pool."""
        cursor = await db.execute(
            "SELECT data_json FROM candidates WHERE pool_id = ? ORDER BY discovery_score DESC",
            (pool_id,),
        )
        rows = await cursor.fetchall()
        return [RepoCandidate.model_validate_json(row["data_json"]) for row in rows]
