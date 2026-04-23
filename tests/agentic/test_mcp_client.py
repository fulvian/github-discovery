"""Agentic MCP client integration test stub.

This test verifies that an MCP client can connect to the GitHub Discovery
MCP server, list tools, and invoke a basic tool workflow. It requires
the MCP Python SDK client library.

Marked as integration + slow since it tests the full MCP protocol stack.
These tests require the ``mcp`` client library and are skipped in CI by default.
"""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
]


@pytest.mark.skip(reason="MCP client integration tests require running server")
class TestMCPClientIntegration:
    """Stub for MCP client integration tests.

    These tests will be implemented when the MCP client library
    supports programmatic server connections in test environments.
    """

    async def test_client_can_list_tools(self) -> None:
        """MCP client can list all registered tools."""
        ...

    async def test_client_can_call_create_session(self) -> None:
        """MCP client can invoke create_session tool."""
        ...

    async def test_progressive_deepening_workflow(self) -> None:
        """Full progressive deepening workflow via MCP client."""
        ...
