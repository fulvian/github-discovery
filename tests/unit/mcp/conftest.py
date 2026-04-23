"""Shared test fixtures for MCP module tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from github_discovery.config import Settings
from github_discovery.mcp.server import AppContext


@pytest.fixture
def settings() -> Settings:
    """Create default test settings."""
    return Settings()


@pytest.fixture
def mcp_server(settings: Settings):
    """Create a FastMCP server instance for testing."""
    from github_discovery.mcp.server import create_server

    return create_server(settings)


@pytest.fixture
def mock_session_manager():
    """Create a mock SessionManager for testing."""
    manager = AsyncMock()
    manager.initialize = AsyncMock()
    manager.close = AsyncMock()
    manager.create = AsyncMock()
    manager.get = AsyncMock(return_value=None)
    manager.get_or_create = AsyncMock()
    manager.update = AsyncMock()
    manager.delete = AsyncMock(return_value=True)
    manager.list_sessions = AsyncMock(return_value=[])
    return manager


@pytest.fixture
def app_context(settings: Settings, mock_session_manager: AsyncMock) -> AppContext:
    """Create an AppContext with mock services."""
    return AppContext(
        settings=settings,
        session_manager=mock_session_manager,
    )
