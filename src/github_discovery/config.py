"""GitHub Discovery configuration via environment variables with GHDISC_ prefix."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GitHubSettings(BaseSettings):
    """GitHub API connection settings."""

    model_config = SettingsConfigDict(
        env_prefix="GHDISC_GITHUB_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    token: str = Field(default="", description="GitHub personal access token")
    api_base_url: str = Field(
        default="https://api.github.com",
        description="GitHub API base URL",
    )
    graphql_url: str = Field(
        default="https://api.github.com/graphql",
        description="GitHub GraphQL API URL",
    )
    request_timeout: int = Field(default=30, description="HTTP request timeout in seconds")
    max_concurrent_requests: int = Field(default=10, description="Max concurrent API requests")


class DiscoverySettings(BaseSettings):
    """Discovery channel settings."""

    model_config = SettingsConfigDict(
        env_prefix="GHDISC_DISCOVERY_",
        env_file=".env",
    )

    max_candidates: int = Field(default=1000, description="Max candidates per discovery query")
    default_channels: list[str] = Field(
        default=["search", "registry", "curated"],
        description="Default discovery channels",
    )


class ScreeningSettings(BaseSettings):
    """Screening gate settings."""

    model_config = SettingsConfigDict(
        env_prefix="GHDISC_SCREENING_",
        env_file=".env",
    )

    min_gate1_score: float = Field(default=0.4, description="Minimum Gate 1 score to pass")
    min_gate2_score: float = Field(default=0.5, description="Minimum Gate 2 score to pass")
    hard_gate_enforcement: bool = Field(
        default=True,
        description="Hard gate: no Gate 3 without Gate 1+2 pass",
    )


class AssessmentSettings(BaseSettings):
    """Deep assessment (Gate 3) settings."""

    model_config = SettingsConfigDict(
        env_prefix="GHDISC_ASSESSMENT_",
        env_file=".env",
    )

    max_tokens_per_repo: int = Field(
        default=50000,
        description="Max LLM tokens per repo assessment",
    )
    max_tokens_per_day: int = Field(
        default=500000,
        description="Max LLM tokens per day budget",
    )
    llm_provider: str = Field(
        default="openai",
        description="LLM provider (openai, anthropic, local)",
    )
    llm_model: str = Field(
        default="gpt-4o",
        description="LLM model identifier",
    )
    cache_ttl_hours: int = Field(
        default=24,
        description="Cache TTL for assessment results (hours)",
    )


class MCPSettings(BaseSettings):
    """MCP server settings."""

    model_config = SettingsConfigDict(
        env_prefix="GHDISC_MCP_",
        env_file=".env",
    )

    transport: str = Field(
        default="stdio",
        description="MCP transport: stdio or http",
    )
    host: str = Field(default="127.0.0.1", description="MCP HTTP host")
    port: int = Field(default=8080, description="MCP HTTP port")
    max_context_tokens: int = Field(
        default=2000,
        description="Max tokens per MCP tool invocation output",
    )
    session_backend: str = Field(
        default="sqlite",
        description="Session backend: sqlite or redis",
    )
    read_only: bool = Field(
        default=True,
        description="Read-only mode for analysis pipelines",
    )


class Settings(BaseSettings):
    """Root application settings composing all sub-settings."""

    model_config = SettingsConfigDict(
        env_prefix="GHDISC_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

    app_name: str = "github-discovery"
    version: str = "0.1.0-alpha"
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Log level (DEBUG, INFO, WARNING, ERROR)")

    github: GitHubSettings = Field(default_factory=GitHubSettings)
    discovery: DiscoverySettings = Field(default_factory=DiscoverySettings)
    screening: ScreeningSettings = Field(default_factory=ScreeningSettings)
    assessment: AssessmentSettings = Field(default_factory=AssessmentSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)
