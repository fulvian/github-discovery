"""GitHub Discovery API module — FastAPI REST interface."""

from __future__ import annotations

from github_discovery.api.app import create_app

__all__ = ["create_app"]
