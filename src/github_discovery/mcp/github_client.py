"""GitHub MCP Server composition module.

Provides configuration templates and rules for composing GitHub Discovery
with the official GitHub MCP Server in agent clients.

Rules (Blueprint §21.5):
1. No duplication: GitHub Discovery does not expose tools for standard
   operations (list repos, read files, create issues) already in GitHub MCP.
2. Minimal toolset: GitHub Discovery exposes only discovery/scoring tools.
3. Read-only default: both servers operate in read-only for analysis.
4. Shared auth: same GHDISC_GITHUB_TOKEN can be used for both servers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from github_discovery.config import Settings


def get_composition_config(settings: Settings, target: str = "kilo") -> dict[str, object]:
    """Generate MCP composition configuration for multi-server setup.

    Returns a dict suitable for serialization to MCP client config files.

    Args:
        settings: Application settings
        target: Target agent platform ("kilo", "opencode", "claude")

    Returns:
        MCP configuration dict with github + github-discovery servers.

    Raises:
        ValueError: If target is not supported.
    """
    if target == "kilo":
        return {
            "github": {
                "type": "remote",
                "url": "https://api.githubcopilot.com/mcp/",
                "headers": {
                    "X-MCP-Toolsets": "repos,issues,pull_requests,context",
                    "X-MCP-Readonly": "true",
                },
            },
            "github-discovery": {
                "type": "local",
                "command": [
                    "python",
                    "-m",
                    "github_discovery.mcp",
                    "serve",
                    "--transport",
                    "stdio",
                ],
                "environment": {
                    "GHDISC_GITHUB_TOKEN": "{env:GITHUB_TOKEN}",
                    "GHDISC_SESSION_BACKEND": "sqlite",
                },
            },
        }
    elif target == "opencode":
        return {
            "github": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"},
            },
            "github-discovery": {
                "command": "python",
                "args": [
                    "-m",
                    "github_discovery.mcp",
                    "serve",
                    "--transport",
                    "stdio",
                ],
                "env": {
                    "GHDISC_GITHUB_TOKEN": "${GITHUB_TOKEN}",
                    "GHDISC_SESSION_BACKEND": "sqlite",
                },
            },
        }
    elif target == "claude":
        return {
            "github-discovery": {
                "command": "python",
                "args": [
                    "-m",
                    "github_discovery.mcp",
                    "serve",
                    "--transport",
                    "stdio",
                ],
                "env": {
                    "GHDISC_GITHUB_TOKEN": "${GITHUB_TOKEN}",
                },
            },
        }
    else:
        msg = f"Unknown target: {target}"
        raise ValueError(msg)


# Tools that GitHub Discovery does NOT provide (delegated to GitHub MCP)
DELEGATED_TOOLS: list[str] = [
    "list_repos",
    "get_repo",
    "read_file",
    "create_issue",
    "list_issues",
    "get_pull_request",
    "create_pull_request",
    "search_code",
    "list_commits",
    "get_readme",
]

# Tools that GitHub Discovery provides (unique capability)
DISCOVERY_TOOLS: list[str] = [
    "discover_repos",
    "get_candidate_pool",
    "expand_seeds",
    "screen_candidates",
    "get_shortlist",
    "quick_screen",
    "deep_assess",
    "quick_assess",
    "get_assessment",
    "rank_repos",
    "explain_repo",
    "compare_repos",
    "create_session",
    "get_session",
    "list_sessions",
    "export_session",
]
