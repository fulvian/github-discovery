"""Context-efficient output formatting for MCP tools.

Blueprint §21.8: output parsimonioso di default, dettaglio on-demand.
Default: < 2000 tokens per invocation (configurable via GHDISC_MCP_MAX_CONTEXT_TOKENS).
"""

from __future__ import annotations

from github_discovery.models.agent import MCPToolResult


def format_tool_result(
    success: bool = True,
    summary: str = "",
    data: dict[str, object] | None = None,
    references: dict[str, str] | None = None,
    detail_available_via: str = "",
    session_id: str | None = None,
    error_message: str | None = None,
    confidence: float = 1.0,
) -> dict[str, object]:
    """Format an MCP tool result with context-efficient design.

    Returns a dict (not MCPToolResult directly) because FastMCP serializes
    the return value. Using dict ensures consistent JSON output.

    Design principles:
    - Summary-first: concise human-readable summary
    - Reference-based: IDs for on-demand detail retrieval
    - Confidence indicators: agent decides whether to deepen
    - Token budget: respect max_context_tokens limit
    """
    result = MCPToolResult(
        success=success,
        summary=summary[:500],
        data=data or {},
        references=references or {},
        detail_available_via=detail_available_via,
        session_id=session_id,
        error_message=error_message,
        confidence=confidence,
    )
    return result.model_dump()


def truncate_for_context(
    items: list[dict[str, object]],
    max_tokens: int = 2000,
    estimated_tokens_per_item: int = 50,
) -> tuple[list[dict[str, object]], bool]:
    """Truncate a list of items to fit within token budget.

    Returns:
        Tuple of (truncated_list, was_truncated)
    """
    max_items = max(1, max_tokens // estimated_tokens_per_item)
    if len(items) <= max_items:
        return items, False
    return items[:max_items], True
