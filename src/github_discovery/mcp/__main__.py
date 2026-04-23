"""MCP server entry point for ``python -m github_discovery.mcp``.

Usage::

    python -m github_discovery.mcp serve --transport stdio
    python -m github_discovery.mcp serve --transport http --port 8080
"""

from __future__ import annotations

from github_discovery.mcp.server import serve

if __name__ == "__main__":
    serve()
