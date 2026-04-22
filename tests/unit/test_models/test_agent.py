"""Tests for agentic support models."""

from __future__ import annotations

from github_discovery.models.agent import DiscoverySession, MCPToolResult


class TestMCPToolResult:
    """Test MCP tool result model."""

    def test_success_result(self) -> None:
        """Success result with summary."""
        result = MCPToolResult(
            success=True,
            summary="Found 42 candidates from 3 channels",
            data={"total": 42, "channels": 3},
            references={"detail": "get_candidate_pool(pool_id='pool-123')"},
        )
        assert result.success is True
        assert result.confidence == 1.0

    def test_error_result(self) -> None:
        """Error result with message."""
        result = MCPToolResult(
            success=False,
            error_message="GitHub API rate limit exceeded",
        )
        assert result.success is False
        assert "rate limit" in result.error_message

    def test_context_efficiency(self) -> None:
        """Result tracks tokens used."""
        result = MCPToolResult(
            success=True,
            summary="Screened 100 candidates",
            tokens_used=850,
        )
        assert result.tokens_used == 850

    def test_json_round_trip(self) -> None:
        """Result serializes to/from JSON."""
        result = MCPToolResult(
            success=True,
            summary="Test",
            data={"key": "value"},
        )
        json_str = result.model_dump_json()
        restored = MCPToolResult.model_validate_json(json_str)
        assert restored.success is True


class TestDiscoverySession:
    """Test discovery session model."""

    def test_empty_session(self) -> None:
        """Empty session has zero counts."""
        session = DiscoverySession(session_id="sess-123")
        assert session.total_discovered == 0
        assert session.tokens_remaining == session.tokens_budget

    def test_tokens_remaining(self) -> None:
        """Remaining tokens computed correctly."""
        session = DiscoverySession(
            session_id="sess-123",
            tokens_consumed=200000,
            tokens_budget=500000,
        )
        assert session.tokens_remaining == 300000

    def test_budget_utilization(self) -> None:
        """Budget utilization ratio computed correctly."""
        session = DiscoverySession(
            session_id="sess-123",
            tokens_consumed=250000,
            tokens_budget=500000,
        )
        assert session.budget_utilization == 0.5

    def test_screening_yield(self) -> None:
        """Screening yield ratio computed correctly."""
        session = DiscoverySession(
            session_id="sess-123",
            total_screened=100,
            gate2_passed=15,
        )
        assert session.screening_yield == 0.15

    def test_to_mcp_result(self) -> None:
        """Session can convert to context-efficient MCP result."""
        session = DiscoverySession(
            session_id="sess-123",
            name="test-session",
            status="screening",
            total_discovered=500,
            total_screened=200,
            gate2_passed=30,
            total_assessed=5,
            top_findings_count=3,
            tokens_consumed=100000,
            tokens_budget=500000,
        )
        result = session.to_mcp_result()
        assert result.success is True
        assert "500 discovered" in result.summary
        assert result.data["hidden_gems"] == 3
        assert result.session_id == "sess-123"
