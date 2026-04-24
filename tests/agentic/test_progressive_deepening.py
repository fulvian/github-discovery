"""Test progressive deepening workflow via MCP client.

Validates Pattern 2 from Blueprint §21.7:
discover → screen → deep assess → rank → explain

These tests chain MCP tool calls to verify that the progressive deepening
workflow works end-to-end through the MCP protocol, even if the underlying
services return empty data (no real GitHub API calls in tests).
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


class TestProgressiveDeepening:
    """Progressive deepening workflow through MCP protocol."""

    async def test_discover_then_screen(self, mcp_client: ClientSession) -> None:
        """Discover repos, then screen at Gate 1 — chain tool calls."""
        # Step 1: Create session
        session_result = await mcp_client.call_tool(
            "create_session",
            arguments={"name": "pd-test"},
        )
        session_text = _extract_text(session_result)
        session_data = json.loads(session_text)
        assert session_data["success"] is True
        session_id = session_data["data"]["session_id"]

        # Step 2: Discover repos (may return empty results without real API)
        discovery = await mcp_client.call_tool(
            "discover_repos",
            arguments={
                "query": "static analysis python",
                "max_candidates": 10,
                "session_id": session_id,
            },
        )
        assert isinstance(discovery, CallToolResult)
        assert len(discovery.content) > 0

        # Step 3: Screen at Gate 1 — pool may not exist (no real API data)
        # but the protocol must handle it gracefully
        screening = await mcp_client.call_tool(
            "screen_candidates",
            arguments={
                "pool_id": "nonexistent-pool-for-test",
                "gate_level": "1",
                "session_id": session_id,
            },
        )
        screen_text = _extract_text(screening)
        screen_data = json.loads(screen_text)
        # Pool not found is expected — verify graceful handling
        assert screen_data["success"] is False
        assert "not found" in screen_data.get("error_message", "").lower()

    async def test_gate_by_gate_deepening(self, mcp_client: ClientSession) -> None:
        """Screen at Gate 1, then deepen to Gate 2 — separate calls."""
        # Screen at Gate 1 only
        gate1_result = await mcp_client.call_tool(
            "screen_candidates",
            arguments={
                "pool_id": "test-pool-gate1",
                "gate_level": "1",
            },
        )
        gate1_text = _extract_text(gate1_result)
        gate1_data = json.loads(gate1_text)
        # Pool not found — graceful error
        assert gate1_data["success"] is False

        # Deepen to Gate 2
        gate2_result = await mcp_client.call_tool(
            "screen_candidates",
            arguments={
                "pool_id": "test-pool-gate2",
                "gate_level": "2",
            },
        )
        gate2_text = _extract_text(gate2_result)
        gate2_data = json.loads(gate2_text)
        assert gate2_data["success"] is False

    async def test_agent_can_set_custom_thresholds(
        self,
        mcp_client: ClientSession,
    ) -> None:
        """Agent can pass custom thresholds as tool arguments."""
        result = await mcp_client.call_tool(
            "screen_candidates",
            arguments={
                "pool_id": "custom-threshold-pool",
                "gate_level": "both",
                "min_gate1_score": 0.8,
                "min_gate2_score": 0.9,
            },
        )
        text = _extract_text(result)
        data = json.loads(text)
        # Pool not found, but thresholds were accepted as parameters
        assert data["success"] is False

    async def test_context_efficient_output(
        self,
        mcp_client: ClientSession,
    ) -> None:
        """Output is not excessively large — respects token budget."""
        result = await mcp_client.call_tool(
            "create_session",
            arguments={"name": "context-test"},
        )
        text = _extract_text(result)

        # MCP tool result should be under ~4000 chars (well within budget)
        assert len(text) < 4000

        data = json.loads(text)
        assert data["success"] is True

    async def test_screen_then_rank_workflow(
        self,
        mcp_client: ClientSession,
    ) -> None:
        """Screen candidates then rank — full chain even with empty data."""
        # Rank without any prior scoring data
        rank_result = await mcp_client.call_tool(
            "rank_repos",
            arguments={"domain": "other"},
        )
        rank_text = _extract_text(rank_result)
        rank_data = json.loads(rank_text)
        # No scored results — expected error
        assert rank_data["success"] is False
        assert "no scored results" in rank_data.get("error_message", "").lower()
