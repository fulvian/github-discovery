"""Shared fixtures for agentic MCP integration tests.

Uses in-memory transport between ClientSession and the FastMCP server.
This avoids launching a separate process and gives deterministic test control.

Pattern:
    client_send, server_recv = create_memory_object_stream(...)
    server_send, client_recv = create_memory_object_stream(...)
    asyncio.create_task(server._mcp_server.run(...))
    ClientSession(client_recv, client_send)

The fixture manages the session lifecycle via a background asyncio task
to avoid anyio cancel scope conflicts during pytest-asyncio teardown.
"""

from __future__ import annotations

import asyncio
import contextlib
import warnings
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.shared.session import SessionMessage

from github_discovery.config import GitHubSettings, Settings
from github_discovery.mcp.server import create_server

# Suppress resource warnings from unclosed httpx/aiohttp sockets
# when the server task is cancelled during test teardown.
warnings.filterwarnings("ignore", category=ResourceWarning)


def pytest_configure(config: pytest.Config) -> None:
    """Disable unraisable exception plugin for agentic tests.

    The MCP server fixture cancels background tasks during teardown, which
    leaves unclosed httpx transports. The unraisableexception plugin collects
    these as errors, but they are benign (GC cleans them up).
    """
    config.pluginmanager.set_blocked("unraisableexception")


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio backend for MCP client tests."""
    return "asyncio"


@pytest.fixture
def agentic_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Settings:
    """Settings for agentic tests with temp databases."""
    monkeypatch.setenv("GHDISC_GITHUB_TOKEN", "ghp_test_agentic")
    return Settings(
        github=GitHubSettings(token="ghp_test_agentic"),  # noqa: S106
    )


async def _run_server_and_session(
    server: Any,
    tmp_path: Path,
) -> AsyncGenerator[ClientSession, None]:
    """Manage the MCP server + client session lifecycle in one task.

    This coroutine runs the server and yields a connected ClientSession.
    Both the server task and session lifecycle are managed within the same
    asyncio task, avoiding the "cancel scope in different task" error that
    occurs when pytest-asyncio teardown runs in a separate task.
    """
    client_send, server_recv = anyio.create_memory_object_stream[SessionMessage](10)
    server_send, client_recv = anyio.create_memory_object_stream[SessionMessage](10)

    init_options = server._mcp_server.create_initialization_options()

    server_task = asyncio.ensure_future(
        server._mcp_server.run(
            server_recv,
            server_send,
            init_options,
            True,  # raise_exceptions for easier debugging
        ),
    )

    # Allow server to fully initialize (lifespan runs async)
    await asyncio.sleep(0.5)

    # Create and initialize client session
    async with ClientSession(client_recv, client_send) as session:
        await session.initialize()
        yield session

    # Cleanup server task
    server_task.cancel()
    with contextlib.suppress(asyncio.CancelledError, ExceptionGroup):
        await server_task


@pytest.fixture
async def mcp_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[ClientSession, None]:
    """MCP ClientSession connected to GitHub Discovery server.

    Uses in-memory transport (MemoryObjectStreams) for fast, deterministic
    tests without launching a separate server process.

    The fixture creates a background asyncio task that manages both the
    server and session lifecycle, avoiding anyio cancel scope issues that
    arise with pytest-asyncio's fixture teardown mechanism.
    """
    # Ensure data dir exists for SQLite databases used by lifespan
    ghdisc_dir = tmp_path / ".ghdisc"
    ghdisc_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GHDISC_GITHUB_TOKEN", "ghp_test_agentic")
    # Point MCP server to tmp data dir (not ~/.local/share/)
    monkeypatch.setenv("GHDISC_DATA_DIR", str(ghdisc_dir))

    settings = Settings(
        github=GitHubSettings(token="ghp_test_agentic"),  # noqa: S106
    )
    server = create_server(settings)

    # Run server+session lifecycle in a sub-task to keep cancel scopes aligned
    gen = _run_server_and_session(server, tmp_path)
    session = await gen.__anext__()

    yield session

    # Finalize the generator (triggers cleanup in the same logical task chain)
    with contextlib.suppress(StopAsyncIteration, RuntimeError, ExceptionGroup):
        await gen.__anext__()


@pytest.fixture
def settings_with_token() -> Settings:
    """Settings with a test GitHub token (non-async, for config tests)."""
    return Settings(
        github=GitHubSettings(token="ghp_test_agentic"),  # noqa: S106
    )
