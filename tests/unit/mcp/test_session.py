"""Tests for MCP SessionManager CRUD operations."""

from __future__ import annotations

import pytest

from github_discovery.mcp.session import SessionManager
from github_discovery.models.session import SessionConfig, SessionStatus


@pytest.fixture
def session_manager() -> SessionManager:
    """Create an in-memory SessionManager for testing."""
    return SessionManager(":memory:")


class TestSessionManagerLifecycle:
    """Tests for SessionManager initialization and cleanup."""

    async def test_session_manager_initialize_and_close(self) -> None:
        """SessionManager can initialize and close without error."""
        sm = SessionManager(":memory:")
        await sm.initialize()
        await sm.close()
        # After close, _db should be None
        assert sm._db is None

    async def test_session_manager_not_initialized_raises(self) -> None:
        """Accessing _conn before initialize raises RuntimeError."""
        sm = SessionManager(":memory:")
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = sm._conn


class TestSessionManagerCreate:
    """Tests for session creation."""

    async def test_session_create(self, session_manager: SessionManager) -> None:
        """Create a new session and verify fields."""
        await session_manager.initialize()
        try:
            session = await session_manager.create(name="test-session")
            assert session.name == "test-session"
            assert session.session_id
            assert session.status == SessionStatus.CREATED
        finally:
            await session_manager.close()

    async def test_session_create_with_config(self, session_manager: SessionManager) -> None:
        """Create a session with custom config."""
        await session_manager.initialize()
        try:
            config = SessionConfig(min_gate1_score=0.6, min_gate2_score=0.7)
            session = await session_manager.create(name="custom", config=config)
            assert session.config.min_gate1_score == 0.6
            assert session.config.min_gate2_score == 0.7
        finally:
            await session_manager.close()


class TestSessionManagerGet:
    """Tests for session retrieval."""

    async def test_session_get_existing(self, session_manager: SessionManager) -> None:
        """Get returns the session when it exists."""
        await session_manager.initialize()
        try:
            created = await session_manager.create(name="find-me")
            found = await session_manager.get(created.session_id)
            assert found is not None
            assert found.session_id == created.session_id
            assert found.name == "find-me"
        finally:
            await session_manager.close()

    async def test_session_get_nonexistent(self, session_manager: SessionManager) -> None:
        """Get returns None for nonexistent session."""
        await session_manager.initialize()
        try:
            result = await session_manager.get("nonexistent-id")
            assert result is None
        finally:
            await session_manager.close()


class TestSessionManagerGetOrCreate:
    """Tests for get_or_create."""

    async def test_session_get_or_create_existing(self, session_manager: SessionManager) -> None:
        """Returns existing session when session_id matches."""
        await session_manager.initialize()
        try:
            created = await session_manager.create(name="existing")
            result = await session_manager.get_or_create(created.session_id)
            assert result.session_id == created.session_id
        finally:
            await session_manager.close()

    async def test_session_get_or_create_new(self, session_manager: SessionManager) -> None:
        """Creates new session when session_id is None."""
        await session_manager.initialize()
        try:
            result = await session_manager.get_or_create(None, name="new-one")
            assert result.name == "new-one"
            assert result.session_id
        finally:
            await session_manager.close()


class TestSessionManagerUpdate:
    """Tests for session update."""

    async def test_session_update(self, session_manager: SessionManager) -> None:
        """Update modifies the session state."""
        await session_manager.initialize()
        try:
            session = await session_manager.create(name="update-me")
            session.status = SessionStatus.DISCOVERING
            session.discovered_repo_count = 42
            await session_manager.update(session)

            retrieved = await session_manager.get(session.session_id)
            assert retrieved is not None
            assert retrieved.status == SessionStatus.DISCOVERING
            assert retrieved.discovered_repo_count == 42
        finally:
            await session_manager.close()


class TestSessionManagerDelete:
    """Tests for session deletion."""

    async def test_session_delete(self, session_manager: SessionManager) -> None:
        """Delete removes a session and returns True."""
        await session_manager.initialize()
        try:
            session = await session_manager.create(name="delete-me")
            deleted = await session_manager.delete(session.session_id)
            assert deleted is True
            assert await session_manager.get(session.session_id) is None
        finally:
            await session_manager.close()

    async def test_session_delete_nonexistent(self, session_manager: SessionManager) -> None:
        """Delete returns False for nonexistent session."""
        await session_manager.initialize()
        try:
            deleted = await session_manager.delete("nonexistent-id")
            assert deleted is False
        finally:
            await session_manager.close()


class TestSessionManagerList:
    """Tests for session listing."""

    async def test_session_list_all(self, session_manager: SessionManager) -> None:
        """List returns all sessions."""
        await session_manager.initialize()
        try:
            await session_manager.create(name="s1")
            await session_manager.create(name="s2")
            await session_manager.create(name="s3")
            sessions = await session_manager.list_sessions()
            assert len(sessions) == 3
        finally:
            await session_manager.close()

    async def test_session_list_by_status(self, session_manager: SessionManager) -> None:
        """List filters by status."""
        await session_manager.initialize()
        try:
            _s1 = await session_manager.create(name="created")
            s2 = await session_manager.create(name="discovering")
            s2.status = SessionStatus.DISCOVERING
            await session_manager.update(s2)

            sessions = await session_manager.list_sessions(status=SessionStatus.CREATED)
            assert len(sessions) == 1
            assert sessions[0].name == "created"
        finally:
            await session_manager.close()

    async def test_session_list_respects_limit(self, session_manager: SessionManager) -> None:
        """List respects the limit parameter."""
        await session_manager.initialize()
        try:
            for i in range(5):
                await session_manager.create(name=f"s-{i}")
            sessions = await session_manager.list_sessions(limit=3)
            assert len(sessions) == 3
        finally:
            await session_manager.close()
