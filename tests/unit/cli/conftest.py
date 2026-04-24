"""Shared fixtures for CLI tests."""

from __future__ import annotations

from io import StringIO
from unittest.mock import AsyncMock

import pytest
from rich.console import Console

from github_discovery.cli.app import _CliState, cli_state


@pytest.fixture
def reset_cli_state() -> _CliState:
    """Reset CLI state to defaults for each test."""
    cli_state.verbose = False
    cli_state.config_file = ".env"
    cli_state.output_format = "table"
    cli_state.log_level = "INFO"
    cli_state.no_color = False
    return cli_state


@pytest.fixture
def capture_console() -> Console:
    """Console that captures output to StringIO for assertions."""
    buf = StringIO()
    return Console(file=buf, no_color=True, width=120)


@pytest.fixture
def mock_settings() -> AsyncMock:
    """Mock Settings object."""
    settings = AsyncMock()
    settings.discovery.default_channels = ["search"]
    settings.mcp.transport = "stdio"
    settings.mcp.host = "127.0.0.1"
    settings.mcp.port = 8080
    return settings


@pytest.fixture
def sample_discovery_result() -> dict[str, object]:
    """Sample discovery result data for formatter tests."""
    return {
        "pool_id": "pool-abc123",
        "total_count": 3,
        "channels_used": ["search", "registry"],
        "candidates": [
            {
                "full_name": "org/repo1",
                "discovery_score": 0.85,
                "language": "Python",
                "stars": 500,
                "source_channel": "search",
            },
            {
                "full_name": "org/repo2",
                "discovery_score": 0.72,
                "language": "Rust",
                "stars": 200,
                "source_channel": "registry",
            },
            {
                "full_name": "org/repo3",
                "discovery_score": 0.60,
                "language": "Go",
                "stars": 50,
                "source_channel": "search",
            },
        ],
    }


@pytest.fixture
def sample_ranking_result() -> dict[str, object]:
    """Sample ranking result data for formatter tests."""
    return {
        "ranked_repos": [
            {
                "full_name": "org/hidden-gem",
                "value_score": 0.92,
                "quality_score": 0.88,
                "stars": 15,
                "domain": "library",
                "is_hidden_gem": True,
            },
            {
                "full_name": "org/popular",
                "value_score": 0.45,
                "quality_score": 0.75,
                "stars": 10000,
                "domain": "library",
                "is_hidden_gem": False,
            },
        ],
    }


@pytest.fixture
def sample_screening_result() -> dict[str, object]:
    """Sample screening result data for formatter tests."""
    return {
        "results": [
            {
                "full_name": "org/repo1",
                "gate1_passed": True,
                "gate1_score": 0.78,
                "gate2_passed": True,
                "gate2_score": 0.65,
                "can_proceed_to_gate3": True,
            },
            {
                "full_name": "org/repo2",
                "gate1_passed": True,
                "gate1_score": 0.55,
                "gate2_passed": False,
                "gate2_score": 0.30,
                "can_proceed_to_gate3": False,
            },
        ],
    }


@pytest.fixture
def sample_session_data() -> dict[str, object]:
    """Sample session data for formatter tests."""
    return {
        "session_id": "sess-abc123",
        "name": "test-session",
        "status": "screening",
        "discovered_repo_count": 150,
        "screened_repo_count": 80,
        "assessed_repo_count": 10,
        "created_at": "2026-04-24T10:00:00Z",
    }


@pytest.fixture
def sample_session_list() -> list[dict[str, object]]:
    """Sample session list data for formatter tests."""
    return [
        {
            "session_id": "sess-abc123",
            "name": "test-session",
            "status": "screening",
            "discovered_repo_count": 150,
            "screened_repo_count": 80,
            "assessed_repo_count": 10,
            "created_at": "2026-04-24T10:00:00Z",
        },
        {
            "session_id": "sess-def456",
            "name": "ml-search",
            "status": "completed",
            "discovered_repo_count": 300,
            "screened_repo_count": 200,
            "assessed_repo_count": 50,
            "created_at": "2026-04-23T14:00:00Z",
        },
    ]
