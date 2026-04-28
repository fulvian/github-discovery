"""OSV API dependency vulnerability scanning for Gate 2.

Queries OSV.dev for known vulnerabilities in declared dependencies.
Uses the batch query endpoint (POST /v1/querybatch) for efficient
multi-package scanning — up to 1000 packages per request with P95 ≤ 6s.

Falls back gracefully if no manifest data is available.

The adapter detects the ecosystem from the candidate's language and
makes an OSV API batch query when possible. When no ecosystem can be
determined or the API is unavailable, returns a neutral score with
confidence=0.0.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from github_discovery.models.candidate import RepoCandidate  # noqa: TC001
from github_discovery.models.screening import VulnerabilityScore

logger = structlog.get_logger("github_discovery.screening.osv")

_OSV_API_BASE = "https://api.osv.dev"
_OSV_BATCH_URL = f"{_OSV_API_BASE}/v1/querybatch"
_MAX_BATCH_SIZE = 1000  # Max packages per batch request
_MAX_BATCH_BYTES = 32 * 1024 * 1024  # 32 MiB payload limit
_OSV_TIMEOUT = 30.0
_HTTP_SUCCESS = 200
_HTTP_SERVER_ERROR = 500

# Transient HTTP exceptions that should trigger retry
_TRANSIENT_ERRORS: tuple[type[Exception], ...] = (
    httpx.TimeoutException,
    httpx.HTTPStatusError,
    httpx.ConnectError,
)

# Severity scoring thresholds — lower value = worse security posture
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


@dataclass
class _PackageQuery:
    """Internal model for a single package query in a batch."""

    package_name: str
    ecosystem: str  # "PyPI", "npm", "Go", "RubyGems", etc.
    full_name: str  # Repo full_name for context/logging


class OsvAdapter:
    """OSV API dependency vulnerability scanning.

    Queries OSV.dev for known vulnerabilities using the batch endpoint
    (POST /v1/querybatch). For screening purposes, falls back gracefully
    when the API is unavailable or no ecosystem can be detected.
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

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def score(self, candidate: RepoCandidate) -> VulnerabilityScore:
        """Query OSV for vulnerabilities for a single candidate.

        Delegates to ``score_batch()`` internally for backward
        compatibility.  Returns a neutral score with confidence=0.0 when
        no useful query can be made or the API is unavailable.
        """
        ecosystem = self._detect_ecosystem(candidate.language)
        if not ecosystem:
            return self._neutral_score(ecosystem=None)

        # Derive package name from repo name (last path segment)
        repo_name = candidate.full_name.split("/")[-1]
        results = await self.score_batch([(candidate, [repo_name])])
        return results[0]

    async def score_batch(
        self,
        items: list[tuple[RepoCandidate, list[str]]],
    ) -> list[VulnerabilityScore]:
        """Batch-query OSV for vulnerabilities across multiple candidates.

        Args:
            items: List of ``(candidate, package_names)`` tuples.  Each
                tuple pairs a :class:`RepoCandidate` with the list of
                package names to query in the candidate's ecosystem.

        Returns:
            List of :class:`VulnerabilityScore`, one per input item, in
            the same order.
        """
        if not items:
            return []

        # Build per-query metadata ------------------------------------
        all_queries: list[_PackageQuery] = []
        # Maps each query index → (candidate_index, ecosystem)
        query_to_item: list[tuple[int, str]] = []

        for idx, (candidate, packages) in enumerate(items):
            ecosystem = self._detect_ecosystem(candidate.language)
            if not ecosystem or not packages:
                continue
            for pkg in packages:
                all_queries.append(
                    _PackageQuery(
                        package_name=pkg,
                        ecosystem=ecosystem,
                        full_name=candidate.full_name,
                    ),
                )
                query_to_item.append((idx, ecosystem))

        # No valid queries possible → neutral for all ---------------
        if not all_queries:
            return [
                self._neutral_score(
                    self._detect_ecosystem(items[i][0].language),
                )
                for i in range(len(items))
            ]

        # Execute batch queries --------------------------------------
        all_vulns = self._execute_batches(all_queries)

        # Map results back to per-candidate scores ------------------
        return self._aggregate_results(
            items=items,
            all_vulns=await all_vulns,
            all_queries=all_queries,
            query_to_item=query_to_item,
        )

    # ------------------------------------------------------------------
    # Batch execution & aggregation
    # ------------------------------------------------------------------

    async def _execute_batches(
        self,
        all_queries: list[_PackageQuery],
    ) -> list[list[dict[str, object]] | None]:
        """Execute all batch queries and return raw vulnerability lists.

        *None* entries indicate the query failed (transient error after
        retries).  Empty lists indicate the query succeeded but found no
        vulnerabilities.
        """
        batches = self._split_batches(all_queries)
        # None = "not yet fetched"; empty list = "fetched, no vulns"
        all_vulns: list[list[dict[str, object]] | None] = [None] * len(all_queries)

        for batch_start, batch_queries in batches:
            payload = self._build_batch_payload(batch_queries)
            try:
                data = await self._batch_query(payload)
                results_raw: object = data.get("results", [])
                results_list = results_raw if isinstance(results_raw, list) else []
                for i, result in enumerate(results_list):
                    global_idx = batch_start + i
                    if isinstance(result, dict):
                        vulns = result.get("vulns")
                        all_vulns[global_idx] = vulns if isinstance(vulns, list) else []
                    else:
                        # null result → no vulns
                        all_vulns[global_idx] = []
            except _TRANSIENT_ERRORS as exc:
                logger.warning("osv_batch_failed", error=str(exc))

        return all_vulns

    def _aggregate_results(
        self,
        *,
        items: list[tuple[RepoCandidate, list[str]]],
        all_vulns: list[list[dict[str, object]] | None],
        all_queries: list[_PackageQuery],
        query_to_item: list[tuple[int, str]],
    ) -> list[VulnerabilityScore]:
        """Map batch vulnerability results back to per-candidate scores."""
        # Start with neutral scores for all candidates
        candidate_results: list[VulnerabilityScore] = [
            self._neutral_score(
                self._detect_ecosystem(items[i][0].language),
            )
            for i in range(len(items))
        ]

        # Aggregate vulns per candidate
        candidate_vulns: dict[int, list[dict[str, object]]] = {}
        candidate_ecosystems: dict[int, str | None] = {}
        candidate_pkg_counts: dict[int, int] = {}

        for query_idx, (cand_idx, ecosystem) in enumerate(query_to_item):
            candidate_ecosystems[cand_idx] = ecosystem
            candidate_pkg_counts[cand_idx] = candidate_pkg_counts.get(cand_idx, 0) + 1
            vulns = all_vulns[query_idx]
            if vulns is not None:
                candidate_vulns.setdefault(cand_idx, []).extend(vulns)

        for cand_idx, vulns in candidate_vulns.items():
            eco: str | None = candidate_ecosystems.get(cand_idx)
            packages_checked = candidate_pkg_counts.get(cand_idx, 1)
            candidate_results[cand_idx] = self._score_vulnerabilities(
                vulns,
                eco,
                packages_checked=packages_checked,
            )

        return candidate_results

    # ------------------------------------------------------------------
    # Batch helpers
    # ------------------------------------------------------------------

    def _split_batches(
        self,
        queries: list[_PackageQuery],
    ) -> list[tuple[int, list[_PackageQuery]]]:
        """Split queries into batches respecting size limits.

        Returns:
            List of ``(start_index, batch_queries)`` tuples where
            *start_index* maps back into the original *queries* list.
        """
        if not queries:
            return []

        batches: list[tuple[int, list[_PackageQuery]]] = []
        current_batch: list[_PackageQuery] = []
        current_size = 0
        start_idx = 0

        for i, query in enumerate(queries):
            entry = {"package": {"name": query.package_name, "ecosystem": query.ecosystem}}
            entry_bytes = len(json.dumps(entry).encode("utf-8"))

            if (
                len(current_batch) >= _MAX_BATCH_SIZE
                or (current_batch and current_size + entry_bytes > _MAX_BATCH_BYTES)
            ):
                batches.append((start_idx, current_batch))
                current_batch = []
                current_size = 0
                start_idx = i

            current_batch.append(query)
            current_size += entry_bytes

        if current_batch:
            batches.append((start_idx, current_batch))

        return batches

    def _build_batch_payload(self, queries: list[_PackageQuery]) -> dict[str, object]:
        """Build the POST payload for ``/v1/querybatch``."""
        return {
            "queries": [
                {
                    "package": {
                        "name": q.package_name,
                        "ecosystem": q.ecosystem,
                    },
                }
                for q in queries
            ],
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(_TRANSIENT_ERRORS),
        reraise=True,
    )
    async def _batch_query(self, payload: dict[str, object]) -> dict[str, object]:
        """Execute a batch query against OSV API with retry on transient errors.

        Retries up to 3 times on 5xx server errors, timeouts, and
        connection failures.  4xx errors are returned as empty results
        (not retried).
        """
        client = await self._get_client()
        response = await client.post(_OSV_BATCH_URL, json=payload)

        # Transient server error → raise to trigger tenacity retry
        if response.status_code >= _HTTP_SERVER_ERROR:
            raise httpx.HTTPStatusError(
                f"OSV server error: {response.status_code}",
                request=response.request,
                response=response,
            )

        if response.status_code == _HTTP_SUCCESS:
            data: dict[str, object] = response.json()
            return data

        # Non-retryable client errors (4xx)
        logger.warning("osv_batch_client_error", status=response.status_code)
        return {"results": []}

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    def _neutral_score(self, ecosystem: str | None) -> VulnerabilityScore:
        """Return neutral score when no meaningful query is possible."""
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

    def _score_vulnerabilities(
        self,
        vulns: list[dict[str, object]],
        ecosystem: str | None,
        *,
        packages_checked: int = 1,
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
                    "osv_packages_checked": packages_checked,
                    "ecosystem": ecosystem,
                },
            )

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
                "osv_packages_checked": packages_checked,
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
