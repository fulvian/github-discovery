"""Tests for OSV API dependency vulnerability scanning."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx

from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel, DomainType
from github_discovery.models.screening import VulnerabilityScore
from github_discovery.screening.osv_adapter import OsvAdapter


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


def _make_mock_client(
    status_code: int = 200,
    json_data: dict[str, object] | None = None,
) -> AsyncMock:
    """Create a mock httpx.AsyncClient with canned responses.

    Uses MagicMock for the response so .status_code and .json() are
    synchronous (as they are in real httpx.Response).
    """
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = json_data or {}

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.aclose = AsyncMock()
    return mock_client


class TestOsvAdapter:
    """Tests for OsvAdapter."""

    async def test_python_ecosystem_detected(self) -> None:
        """Python language → PyPI ecosystem."""
        adapter = OsvAdapter()
        assert adapter._detect_ecosystem("Python") == "PyPI"

    async def test_javascript_ecosystem_detected(self) -> None:
        """JavaScript language → npm ecosystem."""
        adapter = OsvAdapter()
        assert adapter._detect_ecosystem("JavaScript") == "npm"

    async def test_no_language_no_ecosystem(self) -> None:
        """No language → None ecosystem."""
        adapter = OsvAdapter()
        assert adapter._detect_ecosystem(None) is None

    async def test_rust_ecosystem_detected(self) -> None:
        """Rust language → crates.io ecosystem."""
        adapter = OsvAdapter()
        assert adapter._detect_ecosystem("Rust") == "crates.io"

    async def test_returns_clean_score_when_no_vulns_found(self) -> None:
        """score() returns clean score when API responds with no vulns data.

        An API 200 with empty response body ({}) means the query succeeded
        but found no matching vulnerabilities — that's a clean score with
        high confidence.
        """
        mock_client = _make_mock_client(status_code=200, json_data={})
        adapter = OsvAdapter(http_client=mock_client)
        candidate = _make_candidate(language="Python")
        result = await adapter.score(candidate)

        assert isinstance(result, VulnerabilityScore)
        # Empty response → no vulns found → clean score
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
        """Details include vulnerability counts when API returns empty response."""
        mock_client = _make_mock_client(status_code=200, json_data={})
        adapter = OsvAdapter(http_client=mock_client)
        candidate = _make_candidate(language="Python")
        result = await adapter.score(candidate)

        assert result.details.get("vuln_count") == 0
        assert result.details.get("critical_count") == 0
        assert result.details.get("high_count") == 0
        # API was checked (200 response) so osv_packages_checked = 1
        assert result.details.get("osv_packages_checked") == 1

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
        """OSV API returns non-200 status → neutral score."""
        mock_client = _make_mock_client(status_code=500, json_data={})
        adapter = OsvAdapter(http_client=mock_client)
        result = await adapter.score(_make_candidate(language="Python"))

        assert result.value == 0.5
        assert result.confidence == 0.0

    async def test_no_language_returns_clean(self) -> None:
        """No language → ecosystem is None, still returns clean score if API succeeds."""
        mock_client = _make_mock_client(status_code=200, json_data={})
        adapter = OsvAdapter(http_client=mock_client)
        result = await adapter.score(_make_candidate(language=None))

        # API succeeded (200) but found no vulns → clean score
        assert result.value == 1.0
        assert result.confidence == 1.0
        assert result.details.get("ecosystem") is None

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
        # _owns_client defaults to False when client is provided
        await adapter.close()

        mock_client.aclose.assert_not_awaited()
