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
        extra="ignore",
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
        extra="ignore",
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
        extra="ignore",
    )

    min_gate1_score: float = Field(default=0.4, description="Minimum Gate 1 score to pass")
    min_gate2_score: float = Field(default=0.5, description="Minimum Gate 2 score to pass")
    hard_gate_enforcement: bool = Field(
        default=True,
        description="Hard gate: no Gate 3 without Gate 1+2 pass",
    )


class AssessmentSettings(BaseSettings):
    """Deep assessment (Gate 3) settings.

    Uses NanoGPT as the LLM provider with OpenAI-compatible API.
    SDK stack: openai SDK (custom base_url) + instructor for structured output.
    """

    model_config = SettingsConfigDict(
        env_prefix="GHDISC_ASSESSMENT_",
        env_file=".env",
        extra="ignore",
    )

    max_tokens_per_repo: int = Field(
        default=100000,
        description="Max LLM tokens per repo assessment (hard limit, within model context window)",
    )
    daily_soft_limit: int = Field(
        default=2000000,
        description="Soft daily token limit for monitoring (warning only, not blocking)",
    )

    # NanoGPT provider settings
    nanogpt_api_key: str = Field(
        default="",
        description="NanoGPT API key for LLM assessment",
    )
    nanogpt_base_url: str = Field(
        default="https://nano-gpt.com/api/subscription/v1",
        description="NanoGPT API base URL (OpenAI-compatible)",
    )
    llm_model: str = Field(
        default="gpt-4o",
        description="LLM model identifier for NanoGPT",
    )
    llm_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="LLM temperature for assessment (low = consistent)",
    )
    llm_max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Max retries for LLM API calls via instructor",
    )
    llm_fallback_model: str = Field(
        default="anthropic/claude-sonnet-4-20250514",
        description="Fallback model if primary fails",
    )
    llm_subscription_mode: bool = Field(
        default=True,
        description="Use NanoGPT subscription endpoint",
    )

    # Repomix packing settings
    repomix_max_tokens: int = Field(
        default=80000,
        description="Max tokens for repomix packed output",
    )
    repomix_compression: bool = Field(
        default=True,
        description="Enable repomix interface-mode compression",
    )

    cache_ttl_hours: int = Field(
        default=24,
        description="Cache TTL for assessment results (hours)",
    )
    gate3_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum Gate 3 score to pass",
    )

    @property
    def effective_base_url(self) -> str:
        """Return subscription or paygo endpoint based on subscription mode.

        When ``llm_subscription_mode`` is True (default), the configured
        ``nanogpt_base_url`` (subscription endpoint) is returned as-is.
        When False, the ``/subscription`` path segment is stripped to
        produce the pay-per-use endpoint.
        """
        if self.llm_subscription_mode:
            return self.nanogpt_base_url
        return self.nanogpt_base_url.replace("/subscription", "")


class ScoringSettings(BaseSettings):
    """Scoring and ranking settings (Layer D)."""

    model_config = SettingsConfigDict(
        env_prefix="GHDISC_SCORING_",
        env_file=".env",
        extra="ignore",
    )

    min_confidence: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum confidence to include in ranking",
    )
    hidden_gem_star_threshold: int = Field(
        default=500,
        description="Max stars for a repo to be considered 'hidden gem'",
    )
    hidden_gem_min_quality: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Min quality_score to qualify as hidden gem",
    )
    feature_store_ttl_hours: int = Field(
        default=48,
        description="Feature store TTL in hours",
    )
    ranking_seed: int = Field(
        default=42,
        description="Seed for deterministic tie-breaking in ranking",
    )
    cross_domain_warning: bool = Field(
        default=True,
        description="Emit warning on cross-domain comparisons",
    )
    custom_profiles_path: str = Field(
        default="",
        description="Path to YAML file with custom domain profiles",
    )


class MCPSettings(BaseSettings):
    """MCP server settings."""

    model_config = SettingsConfigDict(
        env_prefix="GHDISC_MCP_",
        env_file=".env",
        extra="ignore",
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

    # --- Phase 7 new fields ---
    session_store_path: str = Field(
        default=".ghdisc/sessions.db",
        description="SQLite database path for session persistence",
    )
    enabled_toolsets: list[str] = Field(
        default_factory=lambda: ["discovery", "screening", "assessment", "ranking", "session"],
        description="Enabled MCP tool categories",
    )
    exclude_tools: list[str] = Field(
        default_factory=list,
        description="Specific tool names to exclude",
    )
    json_response: bool = Field(
        default=True,
        description="Use JSON structured content for tool responses",
    )
    stateless_http: bool = Field(
        default=False,
        description="Use stateless HTTP mode (for production deployment)",
    )
    streamable_http_path: str = Field(
        default="/mcp",
        description="Path for streamable HTTP transport endpoint",
    )


class APISettings(BaseSettings):
    """API server settings."""

    model_config = SettingsConfigDict(
        env_prefix="GHDISC_API_",
        env_file=".env",
        extra="ignore",
    )

    host: str = Field(default="127.0.0.1", description="API server host")
    port: int = Field(default=8000, description="API server port")
    workers: int = Field(default=1, description="Number of worker tasks per type")
    rate_limit_per_minute: int = Field(
        default=60,
        description="Rate limit per IP per minute",
    )
    api_key: str = Field(default="", description="API key for auth (empty = no auth)")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed CORS origins",
    )
    job_store_path: str = Field(
        default=".ghdisc/jobs.db",
        description="SQLite database path for job persistence",
    )


class Settings(BaseSettings):
    """Root application settings composing all sub-settings."""

    model_config = SettingsConfigDict(
        env_prefix="GHDISC_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    app_name: str = "github-discovery"
    version: str = "0.1.0-alpha"
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Log level (DEBUG, INFO, WARNING, ERROR)")

    github: GitHubSettings = Field(default_factory=GitHubSettings)
    discovery: DiscoverySettings = Field(default_factory=DiscoverySettings)
    screening: ScreeningSettings = Field(default_factory=ScreeningSettings)
    assessment: AssessmentSettings = Field(default_factory=AssessmentSettings)
    scoring: ScoringSettings = Field(default_factory=ScoringSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)
    api: APISettings = Field(default_factory=APISettings)
