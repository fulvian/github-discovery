"""Tests for MCP transport configuration."""

from __future__ import annotations

import pytest

from github_discovery.config import MCPSettings
from github_discovery.mcp.transport import get_transport_args


class TestGetTransportArgs:
    """Tests for get_transport_args function."""

    def test_get_transport_args_stdio(self) -> None:
        """stdio transport returns correct args."""
        settings = MCPSettings(transport="stdio")
        args = get_transport_args(settings)
        assert args == {"transport": "stdio"}

    def test_get_transport_args_http(self) -> None:
        """http transport returns streamable-http args."""
        settings = MCPSettings(
            transport="http",
            host="192.168.1.1",
            port=9090,
        )
        args = get_transport_args(settings)
        assert args["transport"] == "streamable-http"
        assert args["host"] == "192.168.1.1"
        assert args["port"] == 9090

    def test_get_transport_args_invalid(self) -> None:
        """Invalid transport raises ValueError."""
        settings = MCPSettings(transport="websocket")
        with pytest.raises(ValueError, match="Unknown MCP transport"):
            get_transport_args(settings)

    def test_get_transport_args_http_default_host_port(self) -> None:
        """http transport uses default host and port from settings."""
        settings = MCPSettings(transport="http")
        args = get_transport_args(settings)
        assert args["host"] == "127.0.0.1"
        assert args["port"] == 8080
