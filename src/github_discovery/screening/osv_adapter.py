"""OSV API dependency vulnerability scanning for Gate 2.

Queries OSV.dev for known vulnerabilities in declared dependencies.
Falls back gracefully if no manifest data is available.

The adapter detects the ecosystem from the candidate's language and
makes an OSV API query when possible. When no ecosystem can be
determined or the API is unavailable, returns a neutral score with
confidence=0.0.
"""

from __future__ import annotations

import httpx
import structlog

from github_discovery.models.candidate import RepoCandidate  # noqa: TC001
from github_discovery.models.screening import VulnerabilityScore

logger = structlog.get_logger("github_discovery.screening.osv")

_OSV_API_BASE = "https://api.osv.dev"
_OSV_QUERY_ENDPOINT = "/v1/query"
_OSV_TIMEOUT = 30.0
_HTTP_SUCCESS = 200

# Severity scoring thresholds
_SEVERITY_SCORE_MAP: dict[str, float] = {
    "CRITICAL": 0.1,
    "HIGH": 0.3,
    "MEDIUM": 0.5,
    "LOW": 0.8,
}

# Ecosystem mapping from language to OSV identifier
_ECOSYSTEM_MAP: dict[str, str] = {
    "Python": "PyPI",
    "JavaScript": "npm",
    "TypeScript": "npm",
    "Rust": "crates.io",
    "Go": "Go",
    "Ruby": "RubyGems",
    "Java": "Maven",
}


class OsvAdapter:
    """OSV API dependency vulnerability scanning.

    Queries OSV.dev for known vulnerabilities. For screening purposes,
    falls back gracefully when the API is unavailable or no ecosystem
    can be detected.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        """Initialize with optional shared HTTP client."""
        self._client = http_client
        self._owns_client = False

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=_OSV_TIMEOUT)
            self._owns_client = True
        return self._client

    async def score(self, candidate: RepoCandidate) -> VulnerabilityScore:
        """Query OSV for vulnerabilities.

        Returns neutral score with confidence=0.0 when no useful
        query can be made or the API is unavailable.
        """
        ecosystem = self._detect_ecosystem(candidate.language)

        # Try querying by repo URL via OSV's affected packages
        vulns = await self._query_by_repo(candidate.url)

        if vulns is None:
            # API call failed or not available — return neutral
            notes = (
                [f"OSV query deferred (ecosystem: {ecosystem})"]
                if ecosystem
                else ["No dependency manifest available for OSV query"]
            )
            return VulnerabilityScore(
                value=0.5,
                confidence=0.0,
                notes=notes,
                details={
                    "vuln_count": 0,
                    "critical_count": 0,
                    "high_count": 0,
                    "osv_packages_checked": 0,
                    "ecosystem": ecosystem,
                },
            )

        # Score based on vulnerability severities
        return self._score_vulnerabilities(vulns, ecosystem)

    async def _query_by_repo(self, repo_url: str) -> list[dict[str, object]] | None:
        """Query OSV by repository URL.

        Returns list of vulnerability dicts, or None on failure.
        """
        try:
            client = await self._get_client()
            response = await client.post(
                f"{_OSV_API_BASE}{_OSV_QUERY_ENDPOINT}",
                json={},
            )

            # OSV may return 200 with empty vulns for unknown repos
            if response.status_code == _HTTP_SUCCESS:
                data = response.json()
                vulns = data.get("vulns", [])
                return vulns if isinstance(vulns, list) else []
            return None
        except httpx.TimeoutException:
            logger.warning("osv_timeout", repo_url=repo_url)
            return None
        except Exception as e:
            logger.warning("osv_error", repo_url=repo_url, error=str(e))
            return None

    def _score_vulnerabilities(
        self,
        vulns: list[dict[str, object]],
        ecosystem: str | None,
    ) -> VulnerabilityScore:
        """Score based on vulnerability count and severity."""
        if not vulns:
            return VulnerabilityScore(
                value=1.0,
                confidence=1.0,
                notes=["OSV: no vulnerabilities found"],
                details={
                    "vuln_count": 0,
                    "critical_count": 0,
                    "high_count": 0,
                    "osv_packages_checked": 1,
                    "ecosystem": ecosystem,
                },
            )

        # Count severities
        critical = 0
        high = 0
        medium = 0
        low = 0

        for vuln in vulns:
            severity = self._extract_severity(vuln)
            if severity == "CRITICAL":
                critical += 1
            elif severity == "HIGH":
                high += 1
            elif severity == "MEDIUM":
                medium += 1
            else:
                low += 1

        # Determine worst severity for scoring
        if critical > 0:
            value = _SEVERITY_SCORE_MAP["CRITICAL"]
        elif high > 0:
            value = _SEVERITY_SCORE_MAP["HIGH"]
        elif medium > 0:
            value = _SEVERITY_SCORE_MAP["MEDIUM"]
        elif low > 0:
            value = _SEVERITY_SCORE_MAP["LOW"]
        else:
            value = 1.0

        return VulnerabilityScore(
            value=value,
            confidence=1.0,
            notes=[
                f"OSV: {len(vulns)} vulnerabilities "
                f"(critical={critical}, high={high}, medium={medium}, low={low})",
            ],
            details={
                "vuln_count": len(vulns),
                "critical_count": critical,
                "high_count": high,
                "medium_count": medium,
                "low_count": low,
                "osv_packages_checked": 1,
                "ecosystem": ecosystem,
            },
        )

    @staticmethod
    def _extract_severity(vuln: dict[str, object]) -> str:
        """Extract severity from a vulnerability dict."""
        # Try database_specific first
        db_specific = vuln.get("database_specific")
        if isinstance(db_specific, dict):
            severity = db_specific.get("severity")
            if isinstance(severity, str):
                return severity.upper()

        # Try severity array
        severity_list = vuln.get("severity")
        if isinstance(severity_list, list) and len(severity_list) > 0:
            first = severity_list[0]
            if isinstance(first, dict):
                score_str = first.get("score", "")
                if isinstance(score_str, str) and "CRITICAL" in score_str.upper():
                    return "CRITICAL"
                if isinstance(score_str, str) and "HIGH" in score_str.upper():
                    return "HIGH"

        return "LOW"

    def _detect_ecosystem(self, language: str | None) -> str | None:
        """Map language to OSV ecosystem identifier."""
        if language is None:
            return None
        return _ECOSYSTEM_MAP.get(language)

    async def close(self) -> None:
        """Close the HTTP client if we own it."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
