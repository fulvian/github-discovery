"""Tests for configuration module."""

from __future__ import annotations

import pytest

from github_discovery.config import GitHubSettings, MCPSettings, ScreeningSettings, Settings


class TestSettings:
    """Test configuration loading."""

    def test_default_settings_instantiable(self) -> None:
        """Settings can be instantiated with defaults."""
        settings = Settings()
        assert settings.app_name == "github-discovery"
        assert settings.debug is False
        assert settings.log_level == "INFO"

    def test_github_settings_defaults(self) -> None:
        """GitHub settings have sensible defaults."""
        settings = GitHubSettings()
        assert settings.api_base_url == "https://api.github.com"
        assert settings.request_timeout == 30
        assert settings.max_concurrent_requests == 10

    def test_settings_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings can be loaded from environment variables."""
        monkeypatch.setenv("GHDISC_DEBUG", "true")
        monkeypatch.setenv("GHDISC_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("GHDISC_GITHUB_TOKEN", "ghp_test123")
        settings = Settings()
        assert settings.debug is True
        assert settings.log_level == "DEBUG"
        test_token = "ghp_test123"  # noqa: S105
        assert settings.github.token == test_token

    def test_mcp_settings_defaults(self) -> None:
        """MCP settings default to stdio transport."""
        settings = MCPSettings()
        assert settings.transport == "stdio"
        assert settings.max_context_tokens == 2000
        assert settings.read_only is True

    def test_screening_settings_hard_gate(self) -> None:
        """Hard gate enforcement is True by default."""
        settings = ScreeningSettings()
        assert settings.hard_gate_enforcement is True
        assert settings.min_gate1_score == 0.4
        assert settings.min_gate2_score == 0.5
