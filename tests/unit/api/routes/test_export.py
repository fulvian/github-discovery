"""Tests for the export endpoints."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from github_discovery.api.deps import get_job_store
from github_discovery.api.routes.export import router as export_router
from github_discovery.workers.types import Job, JobStatus, JobType


def _make_export_app(
    mock_job_store: AsyncMock | None = None,
) -> FastAPI:
    """Create a minimal FastAPI app with export router for testing."""
    app = FastAPI()
    app.include_router(export_router, prefix="/api/v1")

    if mock_job_store is not None:
        app.dependency_overrides[get_job_store] = lambda: mock_job_store

    return app


def _make_completed_job(
    *,
    job_id: str = "completed-1",
    job_type: JobType = JobType.DISCOVERY,
) -> Job:
    """Create a completed job for testing."""
    return Job(
        job_id=job_id,
        job_type=job_type,
        status=JobStatus.COMPLETED,
        input_data={"query": "test"},
        result={"total_candidates": 5},
    )


class TestExportJson:
    """Tests for JSON export format."""

    def test_export_json_empty(self) -> None:
        """JSON export with no completed jobs returns empty array."""
        store = AsyncMock()
        store.list_jobs = AsyncMock(return_value=[])
        app = _make_export_app(store)

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/export",
                json={"session_id": "test-session", "format": "json"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["format"] == "json"
            assert data["total_repos"] == 0
            assert data["content"] == "[]"

    def test_export_json_with_data(self) -> None:
        """JSON export with completed jobs returns structured data."""
        jobs = [
            _make_completed_job(job_id="job-1"),
            _make_completed_job(job_id="job-2", job_type=JobType.SCREENING),
        ]
        store = AsyncMock()
        store.list_jobs = AsyncMock(return_value=jobs)
        app = _make_export_app(store)

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/export",
                json={"session_id": "test-session", "format": "json"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["format"] == "json"
            assert data["total_repos"] == 2
            content = json.loads(data["content"])
            assert len(content) == 2
            assert content[0]["job_id"] == "job-1"


class TestExportCsv:
    """Tests for CSV export format."""

    def test_export_csv_empty(self) -> None:
        """CSV export with no data returns empty string."""
        store = AsyncMock()
        store.list_jobs = AsyncMock(return_value=[])
        app = _make_export_app(store)

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/export",
                json={"session_id": "test-session", "format": "csv"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["format"] == "csv"
            assert data["total_repos"] == 0
            assert data["content"] == ""

    def test_export_csv_with_data(self) -> None:
        """CSV export with data returns CSV-formatted content."""
        jobs = [_make_completed_job(job_id="job-csv-1")]
        store = AsyncMock()
        store.list_jobs = AsyncMock(return_value=jobs)
        app = _make_export_app(store)

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/export",
                json={"session_id": "test-session", "format": "csv"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["format"] == "csv"
            assert data["total_repos"] == 1
            # Should contain CSV header and data row
            assert "job_id" in data["content"]
            assert "job-csv-1" in data["content"]


class TestExportMarkdown:
    """Tests for Markdown export format."""

    def test_export_markdown_empty(self) -> None:
        """Markdown export with no data returns empty message."""
        store = AsyncMock()
        store.list_jobs = AsyncMock(return_value=[])
        app = _make_export_app(store)

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/export",
                json={"session_id": "test-session", "format": "markdown"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["format"] == "markdown"
            assert data["total_repos"] == 0
            assert data["content"] == "No results to export."

    def test_export_markdown_with_data(self) -> None:
        """Markdown export with data returns a markdown table."""
        jobs = [_make_completed_job(job_id="job-md-1")]
        store = AsyncMock()
        store.list_jobs = AsyncMock(return_value=jobs)
        app = _make_export_app(store)

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/export",
                json={"session_id": "test-session", "format": "markdown"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["format"] == "markdown"
            assert data["total_repos"] == 1
            # Should contain markdown table formatting
            assert "|" in data["content"]
            assert "---" in data["content"]
            assert "job-md-1" in data["content"]


class TestExportGeneral:
    """General export endpoint tests."""

    def test_export_default_format_is_json(self) -> None:
        """Export without specifying format defaults to JSON."""
        store = AsyncMock()
        store.list_jobs = AsyncMock(return_value=[])
        app = _make_export_app(store)

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/export",
                json={"session_id": "test-session"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["format"] == "json"

    def test_export_response_has_format_field(self) -> None:
        """Export response always includes the format field."""
        store = AsyncMock()
        store.list_jobs = AsyncMock(return_value=[])
        app = _make_export_app(store)

        with TestClient(app) as client:
            for fmt in ["json", "csv", "markdown"]:
                resp = client.post(
                    "/api/v1/export",
                    json={"session_id": "test-session", "format": fmt},
                )
                assert resp.status_code == 200
                assert resp.json()["format"] == fmt
