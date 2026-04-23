"""Tests for context-efficient output formatting."""

from __future__ import annotations

from github_discovery.mcp.output_format import format_tool_result, truncate_for_context


class TestFormatToolResult:
    """Tests for format_tool_result function."""

    def test_format_tool_result_success(self) -> None:
        """format_tool_result returns dict with success=True by default."""
        result = format_tool_result(summary="Test summary")
        assert result["success"] is True
        assert result["summary"] == "Test summary"

    def test_format_tool_result_error(self) -> None:
        """format_tool_result returns error dict with success=False."""
        result = format_tool_result(
            success=False,
            error_message="Something went wrong",
        )
        assert result["success"] is False
        assert result["error_message"] == "Something went wrong"

    def test_format_tool_result_truncates_summary(self) -> None:
        """Summary is truncated to 500 characters."""
        long_summary = "x" * 600
        result = format_tool_result(summary=long_summary)
        assert len(result["summary"]) <= 500

    def test_format_tool_result_with_references(self) -> None:
        """References are included in output."""
        refs = {"pool": "get_candidate_pool(pool_id='abc')"}
        result = format_tool_result(
            summary="Test",
            references=refs,
        )
        assert result["references"] == refs

    def test_format_tool_result_with_session_id(self) -> None:
        """Session ID is included when provided."""
        result = format_tool_result(
            summary="Test",
            session_id="sess-123",
        )
        assert result["session_id"] == "sess-123"

    def test_format_tool_result_with_data(self) -> None:
        """Data dict is included in output."""
        data = {"pool_id": "abc", "count": 42}
        result = format_tool_result(summary="Test", data=data)
        assert result["data"] == data

    def test_format_tool_result_default_values(self) -> None:
        """Default values are set correctly."""
        result = format_tool_result()
        assert result["success"] is True
        assert result["summary"] == ""
        assert result["data"] == {}
        assert result["references"] == {}
        assert result["confidence"] == 1.0
        assert result["session_id"] is None
        assert result["error_message"] is None

    def test_format_tool_result_returns_dict(self) -> None:
        """Result is a plain dict, not a Pydantic model."""
        result = format_tool_result(summary="Test")
        assert isinstance(result, dict)


class TestTruncateForContext:
    """Tests for truncate_for_context function."""

    def test_truncate_for_context_no_truncation(self) -> None:
        """No truncation when items fit within budget."""
        items = [{"name": f"item-{i}"} for i in range(5)]
        result, was_truncated = truncate_for_context(
            items, max_tokens=1000, estimated_tokens_per_item=50
        )
        assert result == items
        assert was_truncated is False

    def test_truncate_for_context_with_truncation(self) -> None:
        """Items are truncated when they exceed token budget."""
        items = [{"name": f"item-{i}"} for i in range(100)]
        result, was_truncated = truncate_for_context(
            items, max_tokens=100, estimated_tokens_per_item=50
        )
        assert len(result) < len(items)
        assert was_truncated is True
        # With max_tokens=100 and tokens_per_item=50, max_items = max(1, 100//50) = 2
        assert len(result) == 2

    def test_truncate_for_context_single_item(self) -> None:
        """Always returns at least 1 item even with tiny budget."""
        items = [{"name": "item-1"}, {"name": "item-2"}]
        result, was_truncated = truncate_for_context(
            items, max_tokens=10, estimated_tokens_per_item=100
        )
        assert len(result) == 1
        assert was_truncated is True

    def test_truncate_for_context_empty_list(self) -> None:
        """Empty list returns empty without truncation."""
        result, was_truncated = truncate_for_context([], max_tokens=100)
        assert result == []
        assert was_truncated is False
