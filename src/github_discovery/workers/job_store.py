"""SQLite-backed job persistence for background workers.

Provides async CRUD operations for Job records with status-based
filtering and stale-job recovery support.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import aiosqlite
import structlog

if TYPE_CHECKING:
    from github_discovery.workers.types import Job, JobStatus, JobType

logger = structlog.get_logger("github_discovery.workers.job_store")

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    input_data TEXT NOT NULL DEFAULT '{}',
    result TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_type ON jobs(job_type);
"""


def _job_to_row(job: Job) -> tuple[object, ...]:
    """Convert a Job model to a database row tuple."""
    return (
        job.job_id,
        job.job_type.value,
        job.status.value,
        json.dumps(job.input_data),
        json.dumps(job.result) if job.result is not None else None,
        job.error_message,
        job.created_at.isoformat(),
        job.started_at.isoformat() if job.started_at is not None else None,
        job.completed_at.isoformat() if job.completed_at is not None else None,
    )


def _row_to_job(row: aiosqlite.Row) -> Job:
    """Convert a database row to a Job model."""
    from datetime import datetime  # noqa: PLC0415

    from github_discovery.workers.types import (  # noqa: PLC0415
        Job as _Job,
        JobStatus as _JobStatus,
        JobType as _JobType,
    )

    result_data = json.loads(row["result"]) if row["result"] is not None else None

    return _Job(
        job_id=row["job_id"],
        job_type=_JobType(row["job_type"]),
        status=_JobStatus(row["status"]),
        input_data=json.loads(row["input_data"]),
        result=result_data,
        error_message=row["error_message"],
        created_at=datetime.fromisoformat(row["created_at"]),
        started_at=(
            datetime.fromisoformat(row["started_at"]) if row["started_at"] is not None else None
        ),
        completed_at=(
            datetime.fromisoformat(row["completed_at"])
            if row["completed_at"] is not None
            else None
        ),
    )


class JobStore:
    """SQLite-backed persistence for background jobs.

    Provides async CRUD with status/type filtering and stale-job
    recovery support for the worker queue.
    """

    def __init__(self, db_path: str = ".ghdisc/jobs.db") -> None:
        """Initialize with path to SQLite database file.

        Args:
            db_path: Path to the SQLite database. Use ``:memory:`` for testing.
        """
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def _get_db(self) -> aiosqlite.Connection:
        """Get or create the database connection."""
        if self._db is None:
            self._db = await aiosqlite.connect(self._db_path)
            self._db.row_factory = aiosqlite.Row
            await self._db.executescript(_CREATE_TABLE_SQL)
            await self._db.commit()
        return self._db

    async def initialize(self) -> None:
        """Create tables and indexes if they don't exist."""
        await self._get_db()
        logger.debug("job_store_initialized", db_path=self._db_path)

    async def create(self, job: Job) -> Job:
        """Insert a new job and return it.

        Args:
            job: Job to persist.

        Returns:
            The persisted Job (unchanged).
        """
        db = await self._get_db()
        await db.execute(
            "INSERT INTO jobs "
            "(job_id, job_type, status, input_data, result, error_message, "
            "created_at, started_at, completed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _job_to_row(job),
        )
        await db.commit()
        logger.debug("job_created", job_id=job.job_id, job_type=job.job_type.value)
        return job

    async def get(self, job_id: str) -> Job | None:
        """Retrieve a job by ID.

        Args:
            job_id: Unique job identifier.

        Returns:
            Job if found, None otherwise.
        """
        db = await self._get_db()
        cursor = await db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_job(row)

    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        **kwargs: object,
    ) -> Job | None:
        """Update job status and optional fields.

        Args:
            job_id: Job to update.
            status: New status.
            **kwargs: Optional fields to update (result, error_message,
                started_at, completed_at). Datetime values are auto-serialized.

        Returns:
            Updated Job if found, None otherwise.
        """
        db = await self._get_db()

        # Build SET clause dynamically
        set_parts: list[str] = ["status = ?"]
        values: list[object] = [status.value]

        if "result" in kwargs:
            result_val = kwargs["result"]
            set_parts.append("result = ?")
            values.append(
                json.dumps(result_val) if result_val is not None else None,
            )
        if "error_message" in kwargs:
            set_parts.append("error_message = ?")
            values.append(kwargs["error_message"])

        if "started_at" in kwargs:
            set_parts.append("started_at = ?")
            sa = kwargs["started_at"]
            values.append(sa.isoformat() if sa is not None else None)  # type: ignore[attr-defined]

        if "completed_at" in kwargs:
            set_parts.append("completed_at = ?")
            ca = kwargs["completed_at"]
            values.append(ca.isoformat() if ca is not None else None)  # type: ignore[attr-defined]

        values.append(job_id)

        query = f"UPDATE jobs SET {', '.join(set_parts)} WHERE job_id = ?"  # noqa: S608
        cursor = await db.execute(query, values)
        await db.commit()

        if cursor.rowcount == 0:
            return None

        return await self.get(job_id)

    async def list_jobs(
        self,
        *,
        job_type: JobType | None = None,
        status: JobStatus | None = None,
        limit: int = 50,
    ) -> list[Job]:
        """List jobs with optional type/status filters.

        Args:
            job_type: Filter by job type (None = all).
            status: Filter by status (None = all).
            limit: Max number of jobs to return.

        Returns:
            List of matching Jobs, ordered by created_at descending.
        """
        db = await self._get_db()

        conditions: list[str] = []
        params: list[object] = []

        if job_type is not None:
            conditions.append("job_type = ?")
            params.append(job_type.value)
        if status is not None:
            conditions.append("status = ?")
            params.append(status.value)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM jobs {where_clause} ORDER BY created_at DESC LIMIT ?"  # noqa: S608
        params.append(limit)

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [_row_to_job(row) for row in rows]

    async def delete(self, job_id: str) -> bool:
        """Delete a job by ID.

        Args:
            job_id: Job to delete.

        Returns:
            True if a job was deleted, False if not found.
        """
        db = await self._get_db()
        cursor = await db.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        await db.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.debug("job_deleted", job_id=job_id)
        return deleted

    async def close(self) -> None:
        """Close the database connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None
            logger.debug("job_store_closed")
