"""Tests for the ranking API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from github_discovery.models.enums import DomainType
from github_discovery.models.scoring import RankedRepo, ScoreResult
from github_discovery.scoring.types import RankingResult


def _make_score_result(full_name: str = "owner/repo") -> ScoreResult:
    """Create a sample ScoreResult for testing."""

    return ScoreResult(
        full_name=full_name,
        commit_sha="abc123",
        domain=DomainType.LIBRARY,
        quality_score=0.82,
        confidence=0.78,
        stars=100,
        gate1_total=0.7,
        gate2_total=0.6,
        gate3_available=True,
    )


def _make_ranking_result() -> RankingResult:
    """Create a sample RankingResult for testing."""
    from datetime import UTC, datetime

    score_result = _make_score_result()
    ranked = RankedRepo(
        rank=1,
        full_name="owner/repo",
        domain=DomainType.LIBRARY,
        score_result=score_result,
    )
    return RankingResult(
        domain=DomainType.LIBRARY,
        ranked_repos=[ranked],
        total_candidates=1,
        hidden_gems=[ranked],
        generated_at=datetime.now(UTC),
    )


def test_rank_returns_200(client: TestClient) -> None:
    """GET /api/v1/rank should return 200 with empty results."""
    response = client.get("/api/v1/rank")
    assert response.status_code == 200
    data = response.json()
    assert "ranked_repos" in data
    assert "pagination" in data


def test_rank_with_domain_filter(
    client: TestClient,
    mock_scoring_engine: MagicMock,
    mock_ranker: MagicMock,
) -> None:
    """GET /api/v1/rank should accept domain filter parameter."""
    ranking = _make_ranking_result()
    mock_ranker.rank = MagicMock(return_value=ranking)

    response = client.get("/api/v1/rank", params={"domain": "library"})
    assert response.status_code == 200
    data = response.json()
    assert data["domain"] == "library"


def test_rank_with_results(
    client: TestClient,
    mock_scoring_engine: MagicMock,
    mock_ranker: MagicMock,
) -> None:
    """GET /api/v1/rank should return ranked repos when data exists."""
    score_result = _make_score_result()
    mock_scoring_engine.feature_store.get_by_domain = AsyncMock(
        return_value=[score_result],
    )
    ranking = _make_ranking_result()
    mock_ranker.rank = MagicMock(return_value=ranking)

    response = client.get("/api/v1/rank", params={"domain": "library"})
    assert response.status_code == 200
    data = response.json()
    assert data["domain"] == "library"
    assert len(data["ranked_repos"]) == 1
    assert data["ranked_repos"][0]["repo"] == "owner/repo"
    assert data["ranked_repos"][0]["rank"] == 1
    assert data["pagination"]["total_count"] == 1


def test_rank_with_custom_params(
    client: TestClient,
    mock_scoring_engine: MagicMock,
    mock_ranker: MagicMock,
) -> None:
    """GET /api/v1/rank should accept custom scoring parameters."""
    ranking = _make_ranking_result()
    mock_ranker.rank = MagicMock(return_value=ranking)

    response = client.get(
        "/api/v1/rank",
        params={
            "domain": "library",
            "min_confidence": 0.5,
            "min_value_score": 0.1,
            "max_results": 10,
            "session_id": "sess-123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["domain"] == "library"
    assert data["min_confidence"] == 0.5
    assert data["min_value_score"] == 0.1
    assert data["max_results"] == 10
    assert data["session_id"] == "sess-123"


def test_get_repo_detail_no_data(client: TestClient) -> None:
    """GET /api/v1/rank/{owner}/{repo} returns scoring=None when no data."""
    response = client.get("/api/v1/rank/owner/repo")
    assert response.status_code == 200
    data = response.json()
    assert data["repo"] == "owner/repo"
    assert data["scoring"] is None


def test_get_repo_detail_with_nesting(client: TestClient) -> None:
    """GET /api/v1/rank/{repo:path} should handle nested org/repo paths."""
    response = client.get("/api/v1/rank/my-org/my-awesome-repo")
    assert response.status_code == 200
    data = response.json()
    assert data["repo"] == "my-org/my-awesome-repo"


def test_get_repo_detail_with_data(
    client: TestClient,
    mock_scoring_engine: MagicMock,
) -> None:
    """GET /api/v1/rank/{owner}/{repo} returns scoring data when available."""
    score_result = _make_score_result()
    mock_scoring_engine.feature_store.get_latest = AsyncMock(
        return_value=score_result,
    )

    response = client.get("/api/v1/rank/owner/repo")
    assert response.status_code == 200
    data = response.json()
    assert data["repo"] == "owner/repo"
    assert data["scoring"] is not None
    assert data["scoring"]["quality_score"] == 0.82
    assert data["scoring"]["domain"] == "library"


def test_explain_repo_no_data(client: TestClient) -> None:
    """GET /api/v1/explain/{owner}/{repo} returns report=None when no data."""
    response = client.get("/api/v1/explain/owner/repo")
    assert response.status_code == 200
    data = response.json()
    assert data["repo"] == "owner/repo"
    assert data["report"] is None
    assert data["detail_level"] == "summary"


def test_explain_repo_with_detail_level(client: TestClient) -> None:
    """GET /api/v1/explain/{repo} should accept detail_level parameter."""
    response = client.get(
        "/api/v1/explain/owner/repo",
        params={"detail_level": "full"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["detail_level"] == "full"


def test_explain_repo_with_data(
    client: TestClient,
    mock_scoring_engine: MagicMock,
) -> None:
    """GET /api/v1/explain/{owner}/{repo} returns report when data exists."""
    score_result = _make_score_result()
    mock_scoring_engine.feature_store.get_latest = AsyncMock(
        return_value=score_result,
    )

    response = client.get("/api/v1/explain/owner/repo")
    assert response.status_code == 200
    data = response.json()
    assert data["repo"] == "owner/repo"
    assert data["report"] is not None
    assert "overall_quality" in data["report"]
    assert "strengths" in data["report"]


def test_rank_pagination(client: TestClient) -> None:
    """GET /api/v1/rank should accept pagination parameters."""
    response = client.get(
        "/api/v1/rank",
        params={"page": 2, "page_size": 10},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 2
    assert data["page_size"] == 10
    assert data["pagination"]["page"] == 2
    assert data["pagination"]["page_size"] == 10
