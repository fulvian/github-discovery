"""Session and progress models for agentic workflow support.

These models enable cross-session progressive deepening (Blueprint §21.4):
an agent can create a session, discover candidates, screen them,
and resume in a later session without losing state.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class SessionStatus(StrEnum):
    """Status of a discovery session."""

    CREATED = "created"
    DISCOVERING = "discovering"
    SCREENING = "screening"
    ASSESSING = "assessing"
    RANKING = "ranking"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SessionConfig(BaseModel):
    """Per-session configuration that overrides global defaults.

    Agents can configure session-specific thresholds, budgets,
    and domain preferences.
    """

    min_gate1_score: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Minimum Gate 1 score threshold for this session",
    )
    min_gate2_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum Gate 2 score threshold for this session",
    )
    max_tokens_per_repo: int = Field(
        default=50000,
        gt=0,
        description="Max LLM tokens per repo assessment for this session",
    )
    max_tokens_per_day: int = Field(
        default=500000,
        gt=0,
        description="Max LLM tokens per day budget for this session",
    )
    preferred_domains: list[str] = Field(
        default_factory=list,
        description="Preferred domain types for ranking",
    )
    excluded_channels: list[str] = Field(
        default_factory=list,
        description="Discovery channels to exclude",
    )
    hard_gate_enforcement: bool = Field(
        default=True,
        description="Hard gate: noGate3 without Gate1+2 pass",
    )


class ProgressInfo(BaseModel):
    """Progress notification for long-running operations.

    Used by MCP tools to emit progress notifications (Blueprint §21.6).
    """

    progress_token: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique token for this progress stream",
    )
    progress: float = Field(
        default=0.0,
        ge=0.0,
        description="Current progress value",
    )
    total: float = Field(
        default=100.0,
        ge=0.0,
        description="Total value for progress calculation",
    )
    message: str = Field(
        default="",
        description="Human-readable progress message",
    )
    session_id: str | None = Field(
        default=None,
        description="Associated session ID",
    )


class SessionState(BaseModel):
    """Persistent session state for cross-invocation agentic workflows.

    Session state tracks the progress of a discovery workflow across
    multiple MCP tool invocations and even across sessions.
    """

    session_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique session identifier",
    )
    name: str = Field(
        default="",
        description="Human-readable session name",
    )
    status: SessionStatus = Field(
        default=SessionStatus.CREATED,
        description="Current session status",
    )
    config: SessionConfig = Field(
        default_factory=SessionConfig,
        description="Per-session configuration overrides",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Session creation timestamp (UTC)",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Session last update timestamp (UTC)",
    )
    pool_ids: list[str] = Field(
        default_factory=list,
        description="IDs of candidate pools in this session",
    )
    discovered_repo_count: int = Field(
        default=0,
        ge=0,
        description="Total repos discovered in this session",
    )
    screened_repo_count: int = Field(
        default=0,
        ge=0,
        description="Total repos screened in this session",
    )
    assessed_repo_count: int = Field(
        default=0,
        ge=0,
        description="Total repos deep-assessed in this session",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if session failed",
    )

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(UTC)
