"""GitHub Discovery MCP configuration helpers.

Runtime configuration for MCP server: tool filtering, environment setup,
and settings validation. Base MCPSettings is in config.py (Phase 0).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from github_discovery.config import Settings

logger = structlog.get_logger("github_discovery.mcp.config")

# All available MCP tools
ALL_TOOLS: list[str] = [
    # Discovery
    "discover_repos",
    "get_candidate_pool",
    "expand_seeds",
    # Screening
    "screen_candidates",
    "get_shortlist",
    "quick_screen",
    # Assessment
    "deep_assess",
    "quick_assess",
    "get_assessment",
    # Ranking
    "rank_repos",
    "explain_repo",
    "compare_repos",
    # Session
    "create_session",
    "get_session",
    "list_sessions",
    "export_session",
]

# Map toolset names to tool names
TOOLSET_MAP: dict[str, set[str]] = {
    "discovery": {"discover_repos", "get_candidate_pool", "expand_seeds"},
    "screening": {"screen_candidates", "get_shortlist", "quick_screen"},
    "assessment": {"deep_assess", "quick_assess", "get_assessment"},
    "ranking": {"rank_repos", "explain_repo", "compare_repos"},
    "session": {"create_session", "get_session", "list_sessions", "export_session"},
}


def get_enabled_tools(settings: Settings, *, log: bool = True) -> list[str]:
    """Get list of enabled MCP tools based on configuration.

    Respects GHDISC_MCP_ENABLED_TOOLSETS and GHDISC_MCP_EXCLUDE_TOOLS.
    """
    enabled_toolsets = set(settings.mcp.enabled_toolsets)
    exclude = set(settings.mcp.exclude_tools)

    enabled: set[str] = set()
    for toolset in enabled_toolsets:
        if toolset in TOOLSET_MAP:
            enabled.update(TOOLSET_MAP[toolset])

    result = [t for t in ALL_TOOLS if t in enabled and t not in exclude]

    if log:
        logger.info(
            "mcp_tools_configured",
            total=len(ALL_TOOLS),
            enabled=len(result),
            excluded=len(exclude),
        )

    return result


def should_register_tool(tool_name: str, settings: Settings) -> bool:
    """Check if a specific tool should be registered."""
    # Use log=False to avoid logging on every tool registration check
    return tool_name in get_enabled_tools(settings, log=False)
