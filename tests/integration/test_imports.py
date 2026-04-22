"""Smoke test: all modules are importable."""

from __future__ import annotations

from github_discovery import __version__
from github_discovery.cli import app
from github_discovery.config import Settings
from github_discovery.exceptions import GitHubDiscoveryError
from github_discovery.logging import configure_logging, get_logger
from github_discovery.models.enums import DomainType
from github_discovery.models.mcp_spec import MCPToolSpec
from github_discovery.models.session import SessionState


def test_import_main_package() -> None:
    """Main package is importable."""
    assert __version__ == "0.1.0-alpha"


def test_import_config() -> None:
    """Config module is importable."""
    assert Settings is not None


def test_import_exceptions() -> None:
    """Exceptions module is importable."""
    assert GitHubDiscoveryError is not None


def test_import_logging() -> None:
    """Logging module is importable."""
    assert configure_logging is not None
    assert get_logger is not None


def test_import_session_models() -> None:
    """Session models are importable."""
    assert SessionState is not None


def test_import_mcp_spec_models() -> None:
    """MCP spec models are importable."""
    assert MCPToolSpec is not None


def test_import_enums() -> None:
    """Enum models are importable."""
    assert DomainType is not None


def test_import_cli() -> None:
    """CLI module is importable."""
    assert app is not None
