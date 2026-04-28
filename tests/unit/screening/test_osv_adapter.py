"""Tests for OSV API dependency vulnerability scanning."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx

from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel, DomainType
from github_discovery.models.screening import VulnerabilityScore
from github_discovery.screening.osv_adapter import (
    _MAX_BATCH_SIZE,
    OsvAdapter,
    _PackageQuery,
)


def _make_candidate(language: str | None = "Python") -> RepoCandidate:
    """Build a test RepoCandidate."""
    return RepoCandidate(
        full_name="test-org/test-repo",
        url="https://github.com/test-org/test-repo",
        html_url="https://github.com/test-org/test-repo",
        api_url="https://api.github.com/repos/test-org/test-repo",
        description="Test repo",
        language=language,
        domain=DomainType.LIBRARY,
        stars=100,
        created_at=datetime(2023, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        owner_login="test-org",
        source_channel=DiscoveryChannel.SEARCH,
    )


def _make_candidate_js(full_name: str = "org/js-repo") -> RepoCandidate:
    """Build a JS RepoCandidate for multi-ecosystem tests."""
    return RepoCandidate(
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        html_url=f"https://github.com/{full_name}",
        api_url=f"https://api.github.com/repos/{full_name}",
        description="JS repo",
        language="JavaScript",
        domain=DomainType.LIBRARY,
        stars=50,
        created_at=datetime(2023, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        owner_login=full_name.split("/", maxsplit=1)[0],
        source_channel=DiscoveryChannel.SEARCH,
    )


def _make_batch_response(
    results: list[dict[str, object] | None] | None = None,
) -> MagicMock:
    """Create a mock response with batch-style data."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": results or []}
    mock_response.request = MagicMock()
    return mock_response


def _make_mock_client(
    status_code: int = 200,
    json_data: dict[str, object] | None = None,
) -> AsyncMock:
    """Create a mock httpx.AsyncClient with canned responses.

    For backward compatibility with single-query mock style.
    If json_data contains a top-level "results" key, it's used as-is.
    Otherwise, json_data is wrapped in a batch response format.
    """
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.request = MagicMock()

    if json_data is not None and "results" in json_data:
        # Already batch format
        mock_response.json.return_value = json_data
    elif json_data is not None:
        # Legacy single-query format → wrap in batch
        mock_response.json.return_value = {"results": [json_data]}
    else:
        mock_response.json.return_value = {"results": []}

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.aclose = AsyncMock()
    return mock_client


class TestEcosystemDetection:
    """Tests for language → ecosystem mapping."""

    async def test_python_ecosystem_detected(self) -> None:
        adapter = OsvAdapter()
        assert adapter._detect_ecosystem("Python") == "PyPI"

    async def test_javascript_ecosystem_detected(self) -> None:
        adapter = OsvAdapter()
        assert adapter._detect_ecosystem("JavaScript") == "npm"

    async def test_typescript_ecosystem_detected(self) -> None:
        adapter = OsvAdapter()
        assert adapter._detect_ecosystem("TypeScript") == "npm"

    async def test_no_language_no_ecosystem(self) -> None:
        adapter = OsvAdapter()
        assert adapter._detect_ecosystem(None) is None

    async def test_rust_ecosystem_detected(self) -> None:
        adapter = OsvAdapter()
        assert adapter._detect_ecosystem("Rust") == "crates.io"

    async def test_go_ecosystem_detected(self) -> None:
        adapter = OsvAdapter()
        assert adapter._detect_ecosystem("Go") == "Go"

    async def test_ruby_ecosystem_detected(self) -> None:
        adapter = OsvAdapter()
        assert adapter._detect_ecosystem("Ruby") == "RubyGems"


class TestScoreSingleCandidate:
    """Tests for score() single-candidate backward-compatible interface."""

    async def test_returns_clean_score_when_no_vulns_found(self) -> None:
        """score() returns clean score when API responds with no vulns."""
        mock_client = _make_mock_client(status_code=200, json_data={})
        adapter = OsvAdapter(http_client=mock_client)
        candidate = _make_candidate(language="Python")
        result = await adapter.score(candidate)

        assert isinstance(result, VulnerabilityScore)
        assert result.value == 1.0
        assert result.confidence == 1.0

    async def test_details_report_ecosystem(self) -> None:
        """Details include detected ecosystem when language is known."""
        mock_client = _make_mock_client(status_code=200, json_data={})
        adapter = OsvAdapter(http_client=mock_client)
        candidate = _make_candidate(language="Python")
        result = await adapter.score(candidate)

        assert result.details.get("ecosystem") == "PyPI"

    async def test_details_report_vulns(self) -> None:
        """Details include vulnerability counts when API returns empty."""
        mock_client = _make_mock_client(status_code=200, json_data={})
        adapter = OsvAdapter(http_client=mock_client)
        candidate = _make_candidate(language="Python")
        result = await adapter.score(candidate)

        assert result.details.get("vuln_count") == 0
        assert result.details.get("critical_count") == 0
        assert result.details.get("high_count") == 0
        assert result.details.get("osv_packages_checked") >= 1

    async def test_api_returns_no_vulnerabilities(self) -> None:
        """OSV API returns empty vulns list → clean score."""
        mock_client = _make_mock_client(
            status_code=200,
            json_data={"vulns": []},
        )
        adapter = OsvAdapter(http_client=mock_client)
        candidate = _make_candidate(language="Python")
        result = await adapter.score(candidate)

        assert result.value == 1.0
        assert result.confidence == 1.0
        assert result.details["vuln_count"] == 0

    async def test_api_returns_high_severity_vuln(self) -> None:
        """OSV API returns HIGH severity vulnerability."""
        mock_client = _make_mock_client(
            status_code=200,
            json_data={
                "vulns": [
                    {
                        "id": "GHSA-xxxx-xxxx-xxxx",
                        "summary": "Test vuln",
                        "database_specific": {"severity": "HIGH"},
                    },
                ],
            },
        )
        adapter = OsvAdapter(http_client=mock_client)
        candidate = _make_candidate(language="Python")
        result = await adapter.score(candidate)

        assert result.value == 0.3  # HIGH severity score
        assert result.confidence == 1.0
        assert result.details["vuln_count"] == 1
        assert result.details["high_count"] == 1

    async def test_api_returns_critical_severity_vuln(self) -> None:
        """OSV API returns CRITICAL severity vulnerability."""
        mock_client = _make_mock_client(
            status_code=200,
            json_data={
                "vulns": [
                    {
                        "id": "GHSA-critical",
                        "database_specific": {"severity": "CRITICAL"},
                    },
                ],
            },
        )
        adapter = OsvAdapter(http_client=mock_client)
        result = await adapter.score(_make_candidate(language="Python"))

        assert result.value == 0.1  # CRITICAL severity score
        assert result.details["critical_count"] == 1

    async def test_api_timeout_returns_neutral(self) -> None:
        """OSV API timeout → neutral score with confidence=0.0."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.aclose = AsyncMock()

        adapter = OsvAdapter(http_client=mock_client)
        result = await adapter.score(_make_candidate(language="Python"))

        assert result.value == 0.5
        assert result.confidence == 0.0

    async def test_api_error_returns_neutral(self) -> None:
        """OSV API error → neutral score with confidence=0.0."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection failed"))
        mock_client.aclose = AsyncMock()

        adapter = OsvAdapter(http_client=mock_client)
        result = await adapter.score(_make_candidate(language="Python"))

        assert result.value == 0.5
        assert result.confidence == 0.0

    async def test_api_non_200_returns_neutral(self) -> None:
        """OSV API returns 500 → after retries → neutral score."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.request = MagicMock()
        mock_response.json.return_value = {}

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        adapter = OsvAdapter(http_client=mock_client)
        result = await adapter.score(_make_candidate(language="Python"))

        assert result.value == 0.5
        assert result.confidence == 0.0

    async def test_no_language_returns_neutral(self) -> None:
        """No language → no ecosystem → neutral score (cannot query OSV)."""
        mock_client = _make_mock_client(status_code=200, json_data={})
        adapter = OsvAdapter(http_client=mock_client)
        result = await adapter.score(_make_candidate(language=None))

        assert result.value == 0.5
        assert result.confidence == 0.0
        assert result.details.get("ecosystem") is None


class TestScoreBatch:
    """Tests for score_batch() batch interface."""

    async def test_empty_input_returns_empty(self) -> None:
        """Empty input list → empty results list."""
        adapter = OsvAdapter()
        results = await adapter.score_batch([])
        assert results == []

    async def test_single_candidate_batch(self) -> None:
        """Single candidate in batch → one score result."""
        mock_response = _make_batch_response([{"vulns": []}])
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        adapter = OsvAdapter(http_client=mock_client)
        candidate = _make_candidate(language="Python")
        results = await adapter.score_batch([(candidate, ["flask"])])

        assert len(results) == 1
        assert results[0].value == 1.0
        assert results[0].confidence == 1.0

    async def test_multiple_candidates_same_ecosystem(self) -> None:
        """Multiple PyPI packages in one batch."""
        mock_response = _make_batch_response([
            {"vulns": []},
            {
                "vulns": [
                    {"id": "GHSA-1", "database_specific": {"severity": "HIGH"}},
                ],
            },
        ])
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        adapter = OsvAdapter(http_client=mock_client)
        c1 = _make_candidate(language="Python")
        c2 = _make_candidate(language="Python")
        results = await adapter.score_batch([
            (c1, ["pkg-clean"]),
            (c2, ["pkg-vuln"]),
        ])

        assert len(results) == 2
        assert results[0].value == 1.0
        assert results[0].confidence == 1.0
        assert results[1].value == 0.3
        assert results[1].confidence == 1.0

    async def test_multiple_packages_per_candidate(self) -> None:
        """Candidate with multiple packages aggregates vulnerabilities."""
        mock_response = _make_batch_response([
            {"vulns": [{"id": "GHSA-1", "database_specific": {"severity": "HIGH"}}]},
            {"vulns": [{"id": "GHSA-2", "database_specific": {"severity": "CRITICAL"}}]},
        ])
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        adapter = OsvAdapter(http_client=mock_client)
        candidate = _make_candidate(language="Python")
        results = await adapter.score_batch([(candidate, ["pkg-a", "pkg-b"])])

        assert len(results) == 1
        # Aggregated: 1 HIGH + 1 CRITICAL → CRITICAL dominates
        assert results[0].value == 0.1
        assert results[0].details["vuln_count"] == 2
        assert results[0].details["critical_count"] == 1
        assert results[0].details["high_count"] == 1

    async def test_batch_timeout_returns_neutral(self) -> None:
        """Batch API timeout → neutral scores for all candidates."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.aclose = AsyncMock()

        adapter = OsvAdapter(http_client=mock_client)
        c1 = _make_candidate(language="Python")
        c2 = _make_candidate(language="Python")
        results = await adapter.score_batch([(c1, ["pkg1"]), (c2, ["pkg2"])])

        assert len(results) == 2
        for r in results:
            assert r.value == 0.5
            assert r.confidence == 0.0

    async def test_no_ecosystem_in_batch_returns_neutral(self) -> None:
        """Candidate with no ecosystem gets neutral score."""
        mock_client = _make_mock_client(status_code=200, json_data={})
        adapter = OsvAdapter(http_client=mock_client)

        candidate = _make_candidate(language=None)
        results = await adapter.score_batch([(candidate, ["some-pkg"])])

        assert len(results) == 1
        assert results[0].value == 0.5
        assert results[0].confidence == 0.0

    async def test_null_result_treated_as_no_vulns(self) -> None:
        """Null result in batch response → no vulnerabilities."""
        mock_response = _make_batch_response([None])
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        adapter = OsvAdapter(http_client=mock_client)
        candidate = _make_candidate(language="Python")
        results = await adapter.score_batch([(candidate, ["pkg"])])

        assert len(results) == 1
        assert results[0].value == 1.0
        assert results[0].confidence == 1.0

    async def test_batch_payload_format(self) -> None:
        """Verify the POST payload uses correct batch format."""
        mock_response = _make_batch_response([{"vulns": []}])
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        adapter = OsvAdapter(http_client=mock_client)
        candidate = _make_candidate(language="Python")
        await adapter.score_batch([(candidate, ["flask"])])

        # Verify the POST call
        call_args = mock_client.post.call_args
        assert call_args is not None
        # Check it posts to batch URL
        assert "querybatch" in call_args[0][0] or "querybatch" in call_args[1].get("url", "")
        # Check payload structure
        payload = call_args[1].get("json", {})
        assert "queries" in payload
        assert len(payload["queries"]) == 1
        assert payload["queries"][0]["package"]["name"] == "flask"
        assert payload["queries"][0]["package"]["ecosystem"] == "PyPI"


class TestBatchSplitting:
    """Tests for _split_batches size-based splitting."""

    def test_single_query_no_split(self) -> None:
        """Single query fits in one batch."""
        adapter = OsvAdapter()
        queries = [_PackageQuery("pkg", "PyPI", "org/repo")]
        batches = adapter._split_batches(queries)

        assert len(batches) == 1
        assert batches[0][0] == 0  # start index
        assert len(batches[0][1]) == 1

    def test_empty_input_no_batches(self) -> None:
        """Empty queries → no batches."""
        adapter = OsvAdapter()
        batches = adapter._split_batches([])
        assert batches == []

    def test_split_at_max_batch_size(self) -> None:
        """Queries exceeding _MAX_BATCH_SIZE are split."""
        adapter = OsvAdapter()
        queries = [
            _PackageQuery(f"pkg-{i}", "PyPI", f"org/repo-{i}")
            for i in range(_MAX_BATCH_SIZE + 1)
        ]
        batches = adapter._split_batches(queries)

        assert len(batches) == 2
        assert len(batches[0][1]) == _MAX_BATCH_SIZE
        assert len(batches[1][1]) == 1
        assert batches[1][0] == _MAX_BATCH_SIZE

    def test_start_indices_are_correct(self) -> None:
        """Start indices map correctly to original query positions."""
        adapter = OsvAdapter()
        queries = [
            _PackageQuery(f"pkg-{i}", "PyPI", f"org/repo-{i}")
            for i in range(_MAX_BATCH_SIZE * 2 + 5)
        ]
        batches = adapter._split_batches(queries)

        assert len(batches) == 3
        assert batches[0][0] == 0
        assert batches[1][0] == _MAX_BATCH_SIZE
        assert batches[2][0] == _MAX_BATCH_SIZE * 2


class TestBuildBatchPayload:
    """Tests for _build_batch_payload."""

    def test_correct_payload_structure(self) -> None:
        """Payload has correct structure for OSV batch API."""
        adapter = OsvAdapter()
        queries = [
            _PackageQuery("flask", "PyPI", "pallets/flask"),
            _PackageQuery("express", "npm", "expressjs/express"),
        ]
        payload = adapter._build_batch_payload(queries)

        assert "queries" in payload
        assert len(payload["queries"]) == 2
        assert payload["queries"][0] == {
            "package": {"name": "flask", "ecosystem": "PyPI"},
        }
        assert payload["queries"][1] == {
            "package": {"name": "express", "ecosystem": "npm"},
        }


class TestSeverityExtraction:
    """Tests for _extract_severity."""

    def test_database_specific_severity(self) -> None:
        vuln = {"database_specific": {"severity": "HIGH"}}
        assert OsvAdapter._extract_severity(vuln) == "HIGH"

    def test_database_specific_case_insensitive(self) -> None:
        vuln = {"database_specific": {"severity": "critical"}}
        assert OsvAdapter._extract_severity(vuln) == "CRITICAL"

    def test_severity_array_cvss(self) -> None:
        vuln = {"severity": [{"type": "CVSS", "score": "CRITICAL"}]}
        assert OsvAdapter._extract_severity(vuln) == "CRITICAL"

    def test_no_severity_info_defaults_low(self) -> None:
        vuln = {"id": "GHSA-xxx"}
        assert OsvAdapter._extract_severity(vuln) == "LOW"

    def test_empty_severity_array_defaults_low(self) -> None:
        vuln = {"severity": []}
        assert OsvAdapter._extract_severity(vuln) == "LOW"


class TestLifecycle:
    """Tests for adapter lifecycle (close, client ownership)."""

    async def test_close_owned_client(self) -> None:
        """close() cleans up self-owned client."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.aclose = AsyncMock()

        adapter = OsvAdapter(http_client=mock_client)
        adapter._owns_client = True
        await adapter.close()

        mock_client.aclose.assert_awaited_once()

    async def test_close_not_owned_client_noop(self) -> None:
        """close() does nothing when client is shared."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.aclose = AsyncMock()

        adapter = OsvAdapter(http_client=mock_client)
        await adapter.close()

        mock_client.aclose.assert_not_awaited()

    async def test_creates_client_lazily(self) -> None:
        """Client is created lazily when needed."""
        adapter = OsvAdapter()
        assert adapter._client is None

        client = await adapter._get_client()
        assert adapter._client is not None
        assert adapter._owns_client is True
        assert isinstance(client, httpx.AsyncClient)

        # Clean up
        await adapter.close()
