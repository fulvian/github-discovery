"""GitHub Discovery CLI entry point for `python -m github_discovery`.

Enables running the CLI via:
    python -m github_discovery --help
    python -m github_discovery version
"""

from __future__ import annotations

from github_discovery.cli import app

if __name__ == "__main__":
    app()
