"""Shared types for the screening package.

Defines RepoContext (gathered metadata for screening), ScreeningContext
(pool-level context for batch screening), and SubprocessResult (async
subprocess execution output).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from github_discovery.models.candidate import RepoCandidate  # noqa: TC001
from github_discovery.models.enums import GateLevel


class RepoContext(BaseModel):
    """Context gathered about a repo for screening decisions.

    Collected via GitHub API calls before/during screening.
    Contains all metadata needed by Gate 1 sub-score checkers.
    """

    candidate: RepoCandidate
    repo_metadata: dict[str, object] = Field(
        default_factory=dict,
        description="Raw /repos/{owner}/{repo} response",
    )
    repo_contents: list[str] = Field(
        default_factory=list,
        description="Root directory listing (filenames)",
    )
    recent_releases: list[dict[str, object]] = Field(
        default_factory=list,
        description="Last 10 releases from API",
    )
    recent_commits: list[dict[str, object]] = Field(
        default_factory=list,
        description="Last 30 commits from API",
    )
    recent_issues: list[dict[str, object]] = Field(
        default_factory=list,
        description="Last 30 issues from API",
    )
    recent_prs: list[dict[str, object]] = Field(
        default_factory=list,
        description="Last 30 PRs from API",
    )
    languages: dict[str, int] = Field(
        default_factory=dict,
        description="Language breakdown {name: bytes}",
    )
    topics: list[str] = Field(
        default_factory=list,
        description="Repository topics",
    )


class ScreeningContext(BaseModel):
    """Full context for a screening operation on a pool."""

    pool_id: str = Field(description="Pool identifier")
    candidates: list[RepoCandidate] = Field(
        default_factory=list,
        description="Candidates to screen",
    )
    gate_level: GateLevel = Field(
        default=GateLevel.METADATA,
        description="Gate level to screen at",
    )
    min_gate1_score: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Minimum Gate 1 score threshold",
    )
    min_gate2_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum Gate 2 score threshold",
    )
    session_id: str | None = Field(
        default=None,
        description="Optional session ID for cross-session workflows",
    )


class SubprocessResult(BaseModel):
    """Result of an async subprocess execution."""

    returncode: int = Field(description="Process exit code")
    stdout: str = Field(default="", description="Captured stdout")
    stderr: str = Field(default="", description="Captured stderr")
    timed_out: bool = Field(default=False, description="Whether execution timed out")
