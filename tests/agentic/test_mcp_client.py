"""MCP client integration tests.

Tests that an MCP client can connect to the GitHub Discovery MCP server,
list tools, call tools, and receive structured results.

Uses in-memory transport (MemoryObjectStreams) for deterministic, fast tests
that verify the full MCP protocol stack without launching a separate process.
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


class TestMCPClientIntegration:
    """MCP client integration with real MCP protocol."""

    async def test_client_can_list_tools(self, mcp_client: ClientSession) -> None:
        """MCP client can list all 16 registered tools."""
        result = await mcp_client.list_tools()
        tool_names = {t.name for t in result.tools}

        assert len(result.tools) == 16
        # Verify key tools from each category
        assert "discover_repos" in tool_names
        assert "screen_candidates" in tool_names
        assert "deep_assess" in tool_names
        assert "rank_repos" in tool_names
        assert "create_session" in tool_names
        assert "list_sessions" in tool_names
        assert "export_session" in tool_names

    async def test_client_can_call_create_session(
        self,
        mcp_client: ClientSession,
    ) -> None:
        """MCP client can invoke create_session tool and get structured result."""
        result = await mcp_client.call_tool(
            "create_session",
            arguments={"name": "test-session"},
        )

        assert isinstance(result, CallToolResult)
        assert result.isError is False
        assert len(result.content) > 0

        text = _extract_text(result)
        assert text  # Non-empty response
        # Parse JSON content from the tool
        data = json.loads(text)
        assert data["success"] is True
        assert "session_id" in data["data"]
        assert data["data"]["name"] == "test-session"

    async def test_client_can_list_resource_templates(
        self,
        mcp_client: ClientSession,
    ) -> None:
        """MCP client can list resource templates."""
        result = await mcp_client.list_resource_templates()
        templates = result.resourceTemplates

        assert len(templates) == 4
        uris = {t.uriTemplate for t in templates}
        assert "repo://{owner}/{name}/score" in uris
        assert "pool://{pool_id}/candidates" in uris
        assert "rank://{domain}/top" in uris
        assert "session://{session_id}/status" in uris

    async def test_client_can_list_prompts(self, mcp_client: ClientSession) -> None:
        """MCP client can list prompt skills."""
        result = await mcp_client.list_prompts()
        prompt_names = {p.name for p in result.prompts}

        assert len(result.prompts) == 5
        assert "discover_underrated" in prompt_names
        assert "quick_quality_check" in prompt_names
        assert "compare_for_adoption" in prompt_names
        assert "domain_deep_dive" in prompt_names
        assert "security_audit" in prompt_names

    async def test_client_call_tool_returns_content(
        self,
        mcp_client: ClientSession,
    ) -> None:
        """Tool calls return structured content with TextContent items."""
        result = await mcp_client.call_tool("list_sessions", arguments={})

        assert isinstance(result, CallToolResult)
        assert result.isError is False
        assert len(result.content) > 0
        assert isinstance(result.content[0], TextContent)

    async def test_get_nonexistent_session_handles_gracefully(
        self,
        mcp_client: ClientSession,
    ) -> None:
        """get_session with invalid ID returns error result, not exception."""
        result = await mcp_client.call_tool(
            "get_session",
            arguments={"session_id": "nonexistent-id-12345"},
        )

        assert isinstance(result, CallToolResult)
        assert len(result.content) > 0

        text = _extract_text(result)
        data = json.loads(text)
        # The tool returns a result with success=False, not an exception
        assert data["success"] is False

    async def test_tool_result_has_json_structure(
        self,
        mcp_client: ClientSession,
    ) -> None:
        """Tool results contain valid JSON with expected schema fields."""
        result = await mcp_client.call_tool(
            "create_session",
            arguments={"name": "schema-test"},
        )

        text = _extract_text(result)
        data = json.loads(text)

        # MCPToolResult schema fields
        assert "success" in data
        assert "summary" in data
        assert "data" in data
        assert isinstance(data["success"], bool)

    async def test_list_sessions_empty(self, mcp_client: ClientSession) -> None:
        """list_sessions returns valid result when no sessions exist."""
        result = await mcp_client.call_tool("list_sessions", arguments={})

        text = _extract_text(result)
        data = json.loads(text)
        assert data["success"] is True
        assert data["data"]["total"] == 0

    async def test_create_session_with_custom_thresholds(
        self,
        mcp_client: ClientSession,
    ) -> None:
        """create_session accepts custom threshold overrides."""
        result = await mcp_client.call_tool(
            "create_session",
            arguments={
                "name": "custom-thresholds",
                "min_gate1_score": 0.7,
                "min_gate2_score": 0.8,
            },
        )

        text = _extract_text(result)
        data = json.loads(text)
        assert data["success"] is True
        assert data["data"]["config"]["min_gate1_score"] == 0.7
        assert data["data"]["config"]["min_gate2_score"] == 0.8
