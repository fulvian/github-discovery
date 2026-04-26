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
    """Disable unraisableexception plugin for agentic tests only."""
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
    server: object,
) -> AsyncGenerator[ClientSession, None]:
    """Manage MCP server + client session in one task chain."""
    client_send, server_recv = anyio.create_memory_object_stream[SessionMessage](10)
    server_send, client_recv = anyio.create_memory_object_stream[SessionMessage](10)
    init_options = server._mcp_server.create_initialization_options()  # type: ignore[attr-defined]

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

    async with ClientSession(client_recv, client_send) as session:
        await session.initialize()
        yield session

    # Signal EOF so server can exit gracefully and run lifespan shutdown.
    await client_send.aclose()
    await client_recv.aclose()
    await server_send.aclose()
    await server_recv.aclose()

    try:
        await asyncio.wait_for(server_task, timeout=10.0)
    except TimeoutError:
        server_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, ExceptionGroup):
            await server_task


@pytest.fixture
async def mcp_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[ClientSession, None]:
    """MCP ClientSession connected to GitHub Discovery server."""
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

    gen = _run_server_and_session(server)
    session = await gen.__anext__()
    try:
        yield session
    finally:
        with contextlib.suppress(RuntimeError, StopAsyncIteration, ExceptionGroup):
            await gen.aclose()


@pytest.fixture
def settings_with_token() -> Settings:
    """Settings with a test GitHub token (non-async, for config tests)."""
    return Settings(
        github=GitHubSettings(token="ghp_test_agentic"),  # noqa: S106
    )
