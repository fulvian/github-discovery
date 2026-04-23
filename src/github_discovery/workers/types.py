"""Worker job types for background processing."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class JobType(StrEnum):
    """Types of background jobs."""

    DISCOVERY = "discovery"
    SCREENING = "screening"
    ASSESSMENT = "assessment"


class JobStatus(StrEnum):
    """Job lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(BaseModel):
    """Background job representation."""

    job_id: str = Field(default_factory=lambda: str(uuid4()))
    job_type: JobType
    status: JobStatus = Field(default=JobStatus.PENDING)
    input_data: dict[str, object] = Field(default_factory=dict)
    result: dict[str, object] | None = Field(default=None)
    error_message: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)


class WorkerResult(BaseModel):
    """Result from a worker processing a job."""

    success: bool
    data: dict[str, object] = Field(default_factory=dict)
    error: str | None = None
