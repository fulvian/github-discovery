"""Backward-compatible CLI entry point.

Imports the app from the new cli/ package.
Will be removed in a future version.
"""

from __future__ import annotations

from github_discovery.cli.app import app  # re-export for backward compat

if __name__ == "__main__":
    app()
