"""Tests for worker job types."""

from __future__ import annotations

from datetime import UTC, datetime

from github_discovery.workers.types import Job, JobStatus, JobType, WorkerResult


class TestJobType:
    """Tests for JobType enum."""

    def test_job_type_values(self) -> None:
        """All three job types should exist."""
        assert JobType.DISCOVERY == "discovery"
        assert JobType.SCREENING == "screening"
        assert JobType.ASSESSMENT == "assessment"
        assert len(JobType) == 3

    def test_job_status_values(self) -> None:
        """All five status values should exist."""
        assert JobStatus.PENDING == "pending"
        assert JobStatus.RUNNING == "running"
        assert JobStatus.COMPLETED == "completed"
        assert JobStatus.FAILED == "failed"
        assert JobStatus.CANCELLED == "cancelled"
        assert len(JobStatus) == 5


class TestJob:
    """Tests for Job model."""

    def test_job_default_values(self) -> None:
        """Job should have auto-generated defaults."""
        job = Job(job_type=JobType.DISCOVERY)

        assert job.job_id  # Auto-generated UUID
        assert len(job.job_id) == 36  # UUID format
        assert job.job_type == JobType.DISCOVERY
        assert job.status == JobStatus.PENDING
        assert job.input_data == {}
        assert job.result is None
        assert job.error_message is None
        assert job.created_at is not None
        assert job.started_at is None
        assert job.completed_at is None

    def test_job_custom_values(self) -> None:
        """Job should accept custom values."""
        now = datetime.now(UTC)
        job = Job(
            job_type=JobType.SCREENING,
            status=JobStatus.RUNNING,
            input_data={"query": "python"},
            result={"score": 0.9},
            error_message=None,
            created_at=now,
            started_at=now,
        )

        assert job.job_type == JobType.SCREENING
        assert job.status == JobStatus.RUNNING
        assert job.input_data["query"] == "python"
        assert job.result["score"] == 0.9
        assert job.started_at == now

    def test_job_serialization(self) -> None:
        """Job should round-trip through model_dump/model_validate."""
        original = Job(
            job_type=JobType.ASSESSMENT,
            input_data={"repo": "test/repo"},
        )

        data = original.model_dump()
        restored = Job.model_validate(data)

        assert restored.job_id == original.job_id
        assert restored.job_type == original.job_type
        assert restored.status == original.status
        assert restored.input_data == original.input_data

    def test_job_json_round_trip(self) -> None:
        """Job should round-trip through JSON serialization."""
        original = Job(
            job_type=JobType.DISCOVERY,
            input_data={"query": "test"},
        )

        json_str = original.model_dump_json()
        restored = Job.model_validate_json(json_str)

        assert restored.job_id == original.job_id
        assert restored.job_type == original.job_type
        assert restored.input_data == original.input_data


class TestWorkerResult:
    """Tests for WorkerResult model."""

    def test_worker_result_success(self) -> None:
        """WorkerResult should represent a successful result."""
        result = WorkerResult(
            success=True,
            data={"score": 0.95},
        )

        assert result.success is True
        assert result.data["score"] == 0.95
        assert result.error is None

    def test_worker_result_failure(self) -> None:
        """WorkerResult should represent a failure."""
        result = WorkerResult(
            success=False,
            error="Something went wrong",
        )

        assert result.success is False
        assert result.data == {}
        assert result.error == "Something went wrong"
