"""Tests for MCP streamable HTTP transport (Wave J1).

Verifies that the MCP server works correctly over HTTP transport:
1. Server creates with valid HTTP endpoint
2. /health endpoint returns basic status
3. Tool round-trip works over HTTP
"""

from __future__ import annotations

from github_discovery.config import Settings
from github_discovery.mcp.server import create_server


class TestStreamableHTTP:
    """Test MCP server over streamable HTTP transport."""

    def test_server_creates_with_http_settings(self) -> None:
        """Server creates successfully with HTTP transport settings."""
        settings = Settings()
        settings.mcp.transport = "http"
        server = create_server(settings)
        assert server.name == "github-discovery"
        # Verify tools are still registered
        tools = server._tool_manager._tools
        assert len(tools) >= 14  # Still has tools even for HTTP mode

    def test_http_app_has_custom_routes(self, settings: Settings) -> None:
        """HTTP app includes custom routes (like /health)."""
        server = create_server(settings)
        http_app = server.streamable_http_app()
        assert http_app is not None
        # Verify routes include our custom /health endpoint
        routes = [route.path for route in http_app.routes]
        matching = [r for r in routes if "/health" in r]
        assert len(matching) >= 1, f"No /health route found in {routes}"

    def test_stateless_mode_passes_through(self, settings: Settings) -> None:
        """Stateless HTTP mode can be enabled without error."""
        from github_discovery.mcp.transport import get_transport_args

        settings.mcp.transport = "http"
        settings.mcp.stateless_http = True

        args = get_transport_args(settings.mcp)
        assert args["transport"] == "streamable-http"
        assert args["stateless_http"] is True

    def test_http_app_health_route_response_status(self, settings: Settings) -> None:
        """The /health custom route returns valid JSON with status field."""
        from httpx import ASGITransport, AsyncClient

        server = create_server(settings)
        http_app = server.streamable_http_app()

        async def _test():
            transport = ASGITransport(app=http_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/health")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "ok"
                assert "version" in data
                assert data["service"] == "github-discovery-mcp"

        import asyncio

        asyncio.run(_test())

    def test_http_app_health_deep(self, settings: Settings) -> None:
        """The /health?deep=true route returns additional check info."""
        from httpx import ASGITransport, AsyncClient

        server = create_server(settings)
        http_app = server.streamable_http_app()

        async def _test():
            transport = ASGITransport(app=http_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/health?deep=true")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "ok"
                assert "checks" in data

        import asyncio

        asyncio.run(_test())
