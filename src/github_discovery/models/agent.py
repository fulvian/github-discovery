"""Agentic support models for MCP integration.

These models bridge domain models with the MCP interface:
- MCPToolResult: Context-efficient output for MCP tool invocations
- DiscoverySession: Aggregated session state with pools and results

Design principles (Blueprint §21.2):
- Context-efficient: summary-first, detail on-demand
- Reference-based: return IDs instead of full data
- Session-aware: all operations can be session-scoped
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from github_discovery.models.enums import DomainType  # noqa: TC001


class MCPToolResult(BaseModel):
    """Context-efficient output for MCP tool invocations.

    Every MCP tool returns this structure to ensure:
    1. Summary-first: top results + counts in < 2000 tokens default
    2. Reference-based: IDs for on-demand detail retrieval
    3. Confidence indicators: agent can decide whether to deepen

    Blueprint §21.8: output parsimonioso di default, dettaglio on-demand.
    """

    success: bool = Field(description="Whether the operation succeeded")
    summary: str = Field(
        default="",
        description="Human-readable summary of results (concise, < 500 chars default)",
    )
    data: dict[str, object] = Field(
        default_factory=dict,
        description="Structured result data (JSON-parseable, context-efficient)",
    )
    references: dict[str, str] = Field(
        default_factory=dict,
        description="References for on-demand detail: {ref_name: tool_call_hint}",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the result quality",
    )
    detail_available_via: str = Field(
        default="",
        description="Hint for getting full detail (e.g., 'get_shortlist(pool_id=..., limit=50)')",
    )
    session_id: str | None = Field(
        default=None,
        description="Associated session ID for cross-session workflows",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if success=False",
    )
    tokens_used: int = Field(
        default=0,
        ge=0,
        description="Approximate context tokens consumed by this result",
    )


class DiscoverySession(BaseModel):
    """Aggregated discovery session state.

    Combines SessionState with concrete pool references, screening
    progress, and assessment results. This is the session's complete
    view for agent workflow management.

    Blueprint §21.4: cross-session progressive deepening support.
    """

    session_id: str = Field(description="Unique session identifier")
    name: str = Field(default="", description="Human-readable session name")

    # --- Pool References ---
    pool_ids: list[str] = Field(
        default_factory=list,
        description="IDs of candidate pools in this session",
    )
    total_discovered: int = Field(
        default=0,
        ge=0,
        description="Total candidates discovered across all pools",
    )

    # --- Screening Progress ---
    total_screened: int = Field(
        default=0,
        ge=0,
        description="Total candidates screened (Gate 1 or Gate 2)",
    )
    gate1_passed: int = Field(default=0, ge=0, description="Candidates that passed Gate 1")
    gate2_passed: int = Field(default=0, ge=0, description="Candidates that passed Gate 2")

    # --- Assessment Progress ---
    total_assessed: int = Field(
        default=0,
        ge=0,
        description="Candidates with deep assessment (Gate 3)",
    )
    tokens_consumed: int = Field(
        default=0,
        ge=0,
        description="Total LLM tokens consumed in this session",
    )
    tokens_budget: int = Field(
        default=500000,
        gt=0,
        description="Total token budget for this session",
    )

    # --- Ranking Progress ---
    domains_ranked: list[DomainType] = Field(
        default_factory=list,
        description="Domains that have been ranked in this session",
    )
    top_findings_count: int = Field(
        default=0,
        ge=0,
        description="Number of repos identified as hidden gems",
    )

    # --- Status ---
    status: str = Field(
        default="created",
        description=(
            "Session status: created, discovering, screening, "
            "assessing, ranking, completed, failed"
        ),
    )
    current_phase: str = Field(
        default="discovery",
        description="Current phase in the workflow",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Session creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Session last update timestamp",
    )

    @property
    def tokens_remaining(self) -> int:
        """Remaining token budget."""
        return max(0, self.tokens_budget - self.tokens_consumed)

    @property
    def budget_utilization(self) -> float:
        """Budget utilization ratio (0.0-1.0)."""
        if self.tokens_budget == 0:
            return 0.0
        return self.tokens_consumed / self.tokens_budget

    @property
    def screening_yield(self) -> float:
        """Yield ratio: Gate 2 passed / total screened."""
        if self.total_screened == 0:
            return 0.0
        return self.gate2_passed / self.total_screened

    def to_mcp_result(self) -> MCPToolResult:
        """Convert to context-efficient MCP tool result."""
        return MCPToolResult(
            success=True,
            summary=(
                f"Session '{self.name}' ({self.status}): "
                f"{self.total_discovered} discovered, "
                f"{self.gate2_passed}/{self.total_screened} passed screening, "
                f"{self.total_assessed} assessed, "
                f"{self.top_findings_count} hidden gems found"
            ),
            data={
                "session_id": self.session_id,
                "status": self.status,
                "discovered": self.total_discovered,
                "gate2_passed": self.gate2_passed,
                "assessed": self.total_assessed,
                "hidden_gems": self.top_findings_count,
                "budget_used_pct": round(self.budget_utilization * 100, 1),
            },
            references={
                "session": f"get_session(session_id='{self.session_id}')",
                "pools": "get_candidate_pool(pool_id='<pool_id>')",
                "rankings": f"rank_repos(session_id='{self.session_id}')",
            },
            session_id=self.session_id,
        )
