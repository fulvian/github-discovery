"""Progress notification helpers for MCP tools.

Wraps Context.report_progress() with domain-specific formatting.
Uses ctx.report_progress(progress, total) — NOT the deprecated
mcp.shared.progress module (removed in SDK v1.x).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import Context
    from mcp.server.session import ServerSession

    from github_discovery.mcp.server import AppContext


async def report_discovery_progress(
    ctx: Context[ServerSession, AppContext] | None,
    current: int,
    total: int,
    channel: str = "",
) -> None:
    """Report progress during discovery operations."""
    if ctx is None:
        return
    await ctx.report_progress(current, total)


async def report_screening_progress(
    ctx: Context[ServerSession, AppContext] | None,
    current: int,
    total: int,
    gate_level: str = "",
) -> None:
    """Report progress during screening operations."""
    if ctx is None:
        return
    await ctx.report_progress(current, total)


async def report_assessment_progress(
    ctx: Context[ServerSession, AppContext] | None,
    current: int,
    total: int,
    tokens_used: int = 0,
    budget_remaining: int = 0,
) -> None:
    """Report progress during deep assessment."""
    if ctx is None:
        return
    await ctx.report_progress(current, total)
