"""Test session cross-invocation workflow.

Validates that sessions persist state across multiple MCP tool calls.
Sessions enable the progressive deepening pattern where an agent can
discover, screen, assess, and rank across multiple tool invocations.
"""

from __future__ import annotations

import json

import pytest
from mcp.client.session import ClientSession
from mcp.types import CallToolResult, TextContent

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def _extract_text(result: CallToolResult) -> str:
    """Extract first text content from a CallToolResult."""
    for item in result.content:
        if isinstance(item, TextContent):
            return item.text
    return ""


class TestSessionWorkflow:
    """Session cross-invocation state management."""

    async def test_create_and_get_session(
        self,
        mcp_client: ClientSession,
    ) -> None:
        """Create session, then retrieve it by ID."""
        # Create
        create_result = await mcp_client.call_tool(
            "create_session",
            arguments={"name": "get-test"},
        )
        create_text = _extract_text(create_result)
        create_data = json.loads(create_text)
        session_id = create_data["data"]["session_id"]

        # Get
        get_result = await mcp_client.call_tool(
            "get_session",
            arguments={"session_id": session_id},
        )
        get_text = _extract_text(get_result)
        get_data = json.loads(get_text)
        assert get_data["success"] is True
        assert get_data["data"]["session_id"] == session_id

    async def test_list_sessions(self, mcp_client: ClientSession) -> None:
        """Create multiple sessions, list them."""
        # Create two sessions
        await mcp_client.call_tool(
            "create_session",
            arguments={"name": "list-test-1"},
        )
        await mcp_client.call_tool(
            "create_session",
            arguments={"name": "list-test-2"},
        )

        # List all
        list_result = await mcp_client.call_tool(
            "list_sessions",
            arguments={},
        )
        list_text = _extract_text(list_result)
        list_data = json.loads(list_text)
        assert list_data["success"] is True
        assert list_data["data"]["total"] >= 2

        session_names = {s["name"] for s in list_data["data"]["sessions"]}
        assert "list-test-1" in session_names
        assert "list-test-2" in session_names

    async def test_export_session(self, mcp_client: ClientSession) -> None:
        """Create session, export it in JSON format."""
        # Create
        create_result = await mcp_client.call_tool(
            "create_session",
            arguments={"name": "export-test"},
        )
        create_text = _extract_text(create_result)
        create_data = json.loads(create_text)
        session_id = create_data["data"]["session_id"]

        # Export as JSON
        export_result = await mcp_client.call_tool(
            "export_session",
            arguments={
                "session_id": session_id,
                "export_format": "json",
            },
        )
        export_text = _extract_text(export_result)
        export_data = json.loads(export_text)
        assert export_data["success"] is True
        assert "session_id" in export_data["data"]

    async def test_sessions_independent(
        self,
        mcp_client: ClientSession,
    ) -> None:
        """Multiple sessions have independent state."""
        # Create two sessions
        s1_result = await mcp_client.call_tool(
            "create_session",
            arguments={"name": "independent-1"},
        )
        s1_text = _extract_text(s1_result)
        s1_data = json.loads(s1_text)
        s1_id = s1_data["data"]["session_id"]

        s2_result = await mcp_client.call_tool(
            "create_session",
            arguments={"name": "independent-2"},
        )
        s2_text = _extract_text(s2_result)
        s2_data = json.loads(s2_text)
        s2_id = s2_data["data"]["session_id"]

        # Verify different IDs
        assert s1_id != s2_id

        # Verify each can be retrieved independently
        g1 = await mcp_client.call_tool(
            "get_session",
            arguments={"session_id": s1_id},
        )
        g1_text = _extract_text(g1)
        g1_data = json.loads(g1_text)
        assert g1_data["data"]["session_id"] == s1_id

        g2 = await mcp_client.call_tool(
            "get_session",
            arguments={"session_id": s2_id},
        )
        g2_text = _extract_text(g2)
        g2_data = json.loads(g2_text)
        assert g2_data["data"]["session_id"] == s2_id
