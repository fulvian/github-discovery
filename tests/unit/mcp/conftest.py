"""Shared test fixtures for MCP module tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

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
    mock_pool_manager = AsyncMock()
    mock_discovery_orch = AsyncMock()
    mock_screening_orch = AsyncMock()
    mock_assessment_orch = AsyncMock()
    mock_scoring_engine = MagicMock()
    mock_ranker = MagicMock()
    mock_feature_store = AsyncMock()

    return AppContext(
        settings=settings,
        session_manager=mock_session_manager,
        pool_manager=mock_pool_manager,
        discovery_orch=mock_discovery_orch,
        screening_orch=mock_screening_orch,
        assessment_orch=mock_assessment_orch,
        scoring_engine=mock_scoring_engine,
        ranker=mock_ranker,
        feature_store=mock_feature_store,
    )
