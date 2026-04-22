"""Tests for API request/response models."""

from __future__ import annotations

import pytest

from github_discovery.models.api import (
    AssessmentRequest,
    DiscoveryQuery,
    ExportFormat,
    PaginatedResponse,
    PaginationParams,
    ScreeningRequest,
)
from github_discovery.models.enums import DomainType


class TestDiscoveryQuery:
    """Test discovery query model."""

    def test_minimal_query(self) -> None:
        """Query requires only the query string."""
        q = DiscoveryQuery(query="python static analysis")
        assert q.query == "python static analysis"
        assert q.max_candidates == 100

    def test_query_with_filters(self) -> None:
        """Query can specify channels, domain, languages."""
        q = DiscoveryQuery(
            query="rust cli tools",
            max_candidates=500,
            domain=DomainType.CLI,
            languages=["Rust"],
        )
        assert q.max_candidates == 500

    def test_query_validation(self) -> None:
        """Query string must be non-empty."""
        with pytest.raises(Exception):  # noqa: B017
            DiscoveryQuery(query="")


class TestPaginationParams:
    """Test pagination model."""

    def test_defaults(self) -> None:
        """Default pagination is page 1, 20 items."""
        p = PaginationParams()
        assert p.page == 1
        assert p.page_size == 20

    def test_custom_pagination(self) -> None:
        """Custom pagination values."""
        p = PaginationParams(page=3, page_size=50)
        assert p.page == 3
        assert p.page_size == 50


class TestPaginatedResponse:
    """Test paginated response model."""

    def test_response_fields(self) -> None:
        """Response includes all pagination metadata."""
        r = PaginatedResponse(
            total_count=100,
            page=2,
            page_size=20,
            total_pages=5,
            has_next=True,
            has_prev=True,
        )
        assert r.has_next is True
        assert r.has_prev is True


class TestExportFormat:
    """Test export format enum."""

    def test_supported_formats(self) -> None:
        """Three formats supported: JSON, CSV, Markdown."""
        assert ExportFormat.JSON == "json"
        assert ExportFormat.CSV == "csv"
        assert ExportFormat.MARKDOWN == "markdown"


class TestAssessmentRequest:
    """Test assessment request model."""

    def test_minimal_request(self) -> None:
        """Request requires only repo_urls."""
        req = AssessmentRequest(repo_urls=["https://github.com/test/repo"])
        assert len(req.repo_urls) == 1

    def test_max_50_repos(self) -> None:
        """Request validates max 50 repos."""
        with pytest.raises(Exception):  # noqa: B017
            AssessmentRequest(repo_urls=["https://github.com/test/repo"] * 51)


class TestScreeningRequest:
    """Test screening request model."""

    def test_minimal_request(self) -> None:
        """Request requires pool_id."""
        req = ScreeningRequest(pool_id="pool-123")
        assert req.pool_id == "pool-123"
