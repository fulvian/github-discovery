"""MCP Session Manager — SQLite-backed session persistence.

Provides CRUD operations for SessionState, enabling cross-session
progressive deepening in MCP workflows (Blueprint §21.4).
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import structlog

from github_discovery.models.session import SessionConfig, SessionState, SessionStatus

logger = structlog.get_logger("github_discovery.mcp.session")

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_updated
    ON sessions(updated_at);
"""


class SessionManager:
    """SQLite-backed session persistence for MCP workflows.

    Stores SessionState as JSON in a SQLite database.
    Consistent with discovery/pool.py and scoring/feature_store.py patterns.
    """

    def __init__(self, db_path: str = ".ghdisc/sessions.db") -> None:
        """Initialize SessionManager with a database path."""
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Open database connection and create tables."""
        # Ensure parent directory exists (critical when CWD is not the project dir)
        db_path = Path(self._db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_CREATE_TABLE_SQL)
        await self._db.commit()
        logger.info("session_manager_initialized", db_path=self._db_path)

    async def close(self) -> None:
        """Close database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def _conn(self) -> aiosqlite.Connection:
        if self._db is None:
            msg = "SessionManager not initialized. Call initialize() first."
            raise RuntimeError(msg)
        return self._db

    async def create(
        self,
        *,
        name: str = "",
        config: SessionConfig | None = None,
    ) -> SessionState:
        """Create a new session."""
        session = SessionState(
            name=name,
            config=config or SessionConfig(),
        )
        await self._save(session)
        logger.info("session_created", session_id=session.session_id, name=name)
        return session

    async def get(self, session_id: str) -> SessionState | None:
        """Get a session by ID."""
        cursor = await self._conn.execute(
            "SELECT data FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return SessionState.model_validate_json(row["data"])

    async def get_or_create(
        self,
        session_id: str | None = None,
        *,
        name: str = "",
    ) -> SessionState:
        """Get an existing session or create a new one."""
        if session_id:
            existing = await self.get(session_id)
            if existing:
                return existing
        return await self.create(name=name)

    async def update(self, session: SessionState) -> None:
        """Update an existing session."""
        session.touch()
        await self._save(session)
        logger.debug("session_updated", session_id=session.session_id)

    async def delete(self, session_id: str) -> bool:
        """Delete a session. Returns True if deleted."""
        cursor = await self._conn.execute(
            "DELETE FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        await self._conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("session_deleted", session_id=session_id)
        return deleted

    async def list_sessions(
        self,
        *,
        status: SessionStatus | None = None,
        limit: int = 10,
    ) -> list[SessionState]:
        """List sessions, optionally filtered by status."""
        if status:
            cursor = await self._conn.execute(
                "SELECT data FROM sessions WHERE json_extract(data, '$.status') = ? "
                "ORDER BY updated_at DESC LIMIT ?",
                (status.value, limit),
            )
        else:
            cursor = await self._conn.execute(
                "SELECT data FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
        return [SessionState.model_validate_json(row["data"]) for row in rows]

    async def _save(self, session: SessionState) -> None:
        """Upsert a session into the database."""
        data = session.model_dump_json()
        now = session.updated_at.isoformat()
        await self._conn.execute(
            "INSERT OR REPLACE INTO sessions (session_id, data, updated_at) VALUES (?, ?, ?)",
            (session.session_id, data, now),
        )
        await self._conn.commit()
