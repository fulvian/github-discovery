"""Package registry mapping discovery channel.

Queries PyPI and npm registries for packages matching the query,
maps to their GitHub repository URLs, and produces RepoCandidate
objects. This channel does NOT depend on the GitHub API — it uses
external registry APIs directly via httpx.

Registry sources provide a different signal than GitHub search:
they reveal packages that people publish, which implies active
maintenance and community adoption.
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from github_discovery.discovery.types import ChannelResult, DiscoveryQuery
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel

logger = structlog.get_logger("github_discovery.discovery.registry_channel")

# --- Constants ---

_PYPI_JSON_API = "https://pypi.org/pypi/{package}/json"
_NPM_SEARCH_API = "https://registry.npmjs.org/-/v1/search"
_REGISTRY_DISCOVERY_SCORE = 0.55  # Registry-sourced packages — published, implies some quality
_NPM_DEFAULT_SIZE = 50
_GITHUB_HOST = "github.com"

# PyPI project URL keys that might contain a GitHub URL, in priority order.
_PYPI_URL_KEYS = (
    "Source",
    "Repository",
    "GitHub",
    "Homepage",
    "Bug Tracker",
    "Changelog",
)

# Regex to extract owner/repo from a GitHub URL path.
_OWNER_REPO_RE = re.compile(r"^/([^/]+)/([^/]+?)(?:\.git)?/?$")
_MIN_PATH_SEGMENTS = 3  # leading "/" + owner + repo
_HTTP_OK = 200


def _extract_github_url(url: str | None) -> str | None:
    """Extract a clean GitHub repo URL from various URL formats.

    Handles:
    - https://github.com/owner/repo
    - git+https://github.com/owner/repo.git
    - git://github.com/owner/repo.git
    - ssh://git@github.com/owner/repo.git
    - URLs with sub-paths (extracts owner/repo from first 2 segments)

    Args:
        url: Raw URL string from a package registry.

    Returns:
        Clean ``https://github.com/owner/repo`` URL or None if not GitHub.
    """
    if not url or url == "None":
        return None

    # Strip common Git URL prefixes
    cleaned = url
    for prefix in ("git+", "git://", "ssh://git@"):
        if cleaned.startswith(prefix):
            if prefix in ("ssh://git@", "git://"):
                cleaned = "https://" + cleaned[len(prefix) :]
            else:
                cleaned = cleaned[len(prefix) :]

    # Strip trailing .git
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]

    # Parse the URL
    try:
        parsed = urlparse(cleaned)
    except Exception:
        return None

    # Must be github.com
    host = parsed.hostname or ""
    if host.lower() != _GITHUB_HOST:
        return None

    # Extract owner/repo from path
    path = parsed.path.rstrip("/")
    parts = path.split("/")
    if len(parts) < _MIN_PATH_SEGMENTS:  # leading "/" + owner + repo
        return None

    owner = parts[1]
    repo = parts[2]

    if not owner or not repo:
        return None

    return f"https://github.com/{owner}/{repo}"


class RegistryChannel:
    """Package registry mapping discovery channel.

    Queries PyPI/npm for packages matching the query,
    maps to their GitHub repository URLs.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        """Initialize with optional httpx client (creates one if not provided).

        Args:
            http_client: Optional pre-configured httpx.AsyncClient.
                         If not provided, a default client is created internally.
                         Registry APIs do NOT require Bearer auth.
        """
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={"Accept": "application/json"},
        )

    async def __aenter__(self) -> RegistryChannel:
        """Enter async context manager."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context manager — close internally-owned client."""
        if self._owns_client:
            await self._client.aclose()

    async def search_pypi(
        self,
        query: str,
        *,
        max_results: int = 50,
    ) -> ChannelResult:
        """Search PyPI packages and map to GitHub repos.

        Uses the PyPI JSON API for a direct package lookup. The query
        text is treated as a package name (hyphens and spaces converted).

        Args:
            query: Package name or search term (treated as package name).
            max_results: Maximum results to return (unused for MVP — single lookup).

        Returns:
            ChannelResult with candidates that have GitHub URLs.
        """
        start_time = time.monotonic()

        # Normalize query to a package name (replace spaces with hyphens)
        package_name = query.strip().replace(" ", "-")
        url = _PYPI_JSON_API.format(package=package_name)

        try:
            response = await self._client.get(url)

            if response.status_code != _HTTP_OK:
                logger.debug(
                    "registry_pypi_not_found",
                    package=package_name,
                    status=response.status_code,
                )
                return self._empty_result(elapsed=time.monotonic() - start_time)

            data = response.json()
        except Exception:
            logger.warning(
                "registry_pypi_error",
                package=package_name,
                exc_info=True,
            )
            return self._empty_result(elapsed=time.monotonic() - start_time)

        github_url = self._extract_github_from_pypi(data)
        if not github_url:
            logger.debug(
                "registry_pypi_no_github",
                package=package_name,
            )
            return self._empty_result(elapsed=time.monotonic() - start_time)

        candidate = self._url_to_candidate(github_url, description=self._pypi_summary(data))

        elapsed = time.monotonic() - start_time
        logger.info(
            "registry_pypi_found",
            package=package_name,
            github=candidate.full_name,
            elapsed_seconds=round(elapsed, 3),
        )

        return ChannelResult(
            channel=DiscoveryChannel.REGISTRY,
            candidates=[candidate],
            total_found=1,
            has_more=False,
            elapsed_seconds=elapsed,
        )

    async def search_npm(
        self,
        query: str,
        *,
        max_results: int = 50,
    ) -> ChannelResult:
        """Search npm packages and map to GitHub repos.

        Uses the npm registry search API to find packages matching
        the query, then filters to those with GitHub repository URLs.

        Args:
            query: Search term for npm registry.
            max_results: Maximum results to request from npm API.

        Returns:
            ChannelResult with candidates that have GitHub URLs.
        """
        start_time = time.monotonic()

        params: dict[str, Any] = {
            "text": query,
            "size": min(max_results, _NPM_DEFAULT_SIZE),
        }

        try:
            response = await self._client.get(_NPM_SEARCH_API, params=params)

            if response.status_code != _HTTP_OK:
                logger.debug(
                    "registry_npm_error",
                    query=query,
                    status=response.status_code,
                )
                return self._empty_result(elapsed=time.monotonic() - start_time)

            data = response.json()
        except Exception:
            logger.warning(
                "registry_npm_error",
                query=query,
                exc_info=True,
            )
            return self._empty_result(elapsed=time.monotonic() - start_time)

        objects = data.get("objects", [])
        total = data.get("total", 0)
        candidates: list[RepoCandidate] = []

        for obj in objects:
            pkg = obj.get("package", {})
            github_url = self._extract_github_from_npm(pkg)
            if github_url:
                description = pkg.get("description") or ""
                candidate = self._url_to_candidate(github_url, description=description)
                candidates.append(candidate)

        elapsed = time.monotonic() - start_time
        logger.info(
            "registry_npm_found",
            query=query,
            npm_results=len(objects),
            github_mapped=len(candidates),
            elapsed_seconds=round(elapsed, 3),
        )

        return ChannelResult(
            channel=DiscoveryChannel.REGISTRY,
            candidates=candidates[:max_results],
            total_found=total,
            has_more=total > len(candidates),
            elapsed_seconds=elapsed,
        )

    async def search(self, query: DiscoveryQuery) -> ChannelResult:
        """Search configured registries and aggregate results.

        Runs both ``search_pypi`` and ``search_npm`` concurrently,
        merges results, deduplicates by ``full_name``, and respects
        ``query.max_candidates``.

        Args:
            query: Discovery query with search term and limits.

        Returns:
            Aggregated ChannelResult with deduplicated candidates.
        """
        start_time = time.monotonic()

        # Run both registries concurrently
        pypi_task = self.search_pypi(query.query)
        npm_task = self.search_npm(query.query, max_results=query.max_candidates)

        pypi_result, npm_result = await asyncio.gather(
            pypi_task,
            npm_task,
            return_exceptions=True,
        )

        # Handle exceptions from gather
        if isinstance(pypi_result, Exception):
            logger.warning("registry_pypi_failed", exc_info=pypi_result)
            pypi_result = self._empty_result()
        if isinstance(npm_result, Exception):
            logger.warning("registry_npm_failed", exc_info=npm_result)
            npm_result = self._empty_result()

        # Merge and deduplicate by full_name
        seen: dict[str, RepoCandidate] = {}
        for result in (pypi_result, npm_result):
            if not isinstance(result, ChannelResult):
                continue
            for candidate in result.candidates:
                if candidate.full_name not in seen:
                    seen[candidate.full_name] = candidate

        candidates = list(seen.values())
        total_found = len(candidates)

        # Respect max_candidates
        candidates = candidates[: query.max_candidates]

        elapsed = time.monotonic() - start_time
        logger.info(
            "registry_search_complete",
            query=query.query,
            total_candidates=total_found,
            returned=len(candidates),
            elapsed_seconds=round(elapsed, 3),
        )

        return ChannelResult(
            channel=DiscoveryChannel.REGISTRY,
            candidates=candidates,
            total_found=total_found,
            has_more=total_found > len(candidates),
            elapsed_seconds=elapsed,
        )

    # --- Private helpers ---

    @staticmethod
    def _extract_github_url(url: str | None) -> str | None:
        """Extract clean GitHub URL from various URL formats.

        Public wrapper around the module-level helper for testing.

        Args:
            url: Raw URL string.

        Returns:
            Clean GitHub URL or None.
        """
        return _extract_github_url(url)

    @staticmethod
    def _extract_github_from_pypi(data: dict[str, Any]) -> str | None:
        """Extract GitHub URL from PyPI JSON API response.

        Checks project_urls keys in priority order, then home_page.

        Args:
            data: Parsed JSON from PyPI package endpoint.

        Returns:
            Clean GitHub URL or None.
        """
        info = data.get("info", {})
        if not isinstance(info, dict):
            return None

        # Check project_urls first (higher confidence)
        project_urls = info.get("project_urls")
        if isinstance(project_urls, dict):
            for key in _PYPI_URL_KEYS:
                url = project_urls.get(key)
                github = _extract_github_url(url)
                if github:
                    return github

        # Fall back to home_page
        return _extract_github_url(info.get("home_page"))

    @staticmethod
    def _extract_github_from_npm(pkg: dict[str, Any]) -> str | None:
        """Extract GitHub URL from npm package object.

        Checks links.repository, links.github, then repository.url.

        Args:
            pkg: npm package object from search results.

        Returns:
            Clean GitHub URL or None.
        """
        links = pkg.get("links", {})
        if isinstance(links, dict):
            # links.repository is the most common field
            for key in ("repository", "github"):
                url = links.get(key)
                github = _extract_github_url(url)
                if github:
                    return github

        # Fall back to repository.url
        repo_obj = pkg.get("repository")
        if isinstance(repo_obj, dict):
            return _extract_github_url(repo_obj.get("url"))

        return None

    @staticmethod
    def _pypi_summary(data: dict[str, Any]) -> str:
        """Extract summary from PyPI response data.

        Args:
            data: Parsed JSON from PyPI package endpoint.

        Returns:
            Package summary string or empty string.
        """
        info = data.get("info", {})
        if isinstance(info, dict):
            return info.get("summary") or ""
        return ""

    @staticmethod
    def _url_to_candidate(
        github_url: str,
        *,
        description: str = "",
    ) -> RepoCandidate:
        """Convert a GitHub repo URL to a RepoCandidate.

        Args:
            github_url: Clean GitHub repository URL.
            description: Package description from the registry.

        Returns:
            RepoCandidate with identity fields populated.
        """
        parsed = urlparse(github_url)
        path = parsed.path.strip("/")
        parts = path.split("/")
        owner = parts[0]
        repo = parts[1]
        full_name = f"{owner}/{repo}"
        now = datetime.now(UTC)

        return RepoCandidate(
            full_name=full_name,
            url=github_url,
            html_url=github_url,
            api_url=f"https://api.github.com/repos/{full_name}",
            description=description,
            source_channel=DiscoveryChannel.REGISTRY,
            discovery_score=_REGISTRY_DISCOVERY_SCORE,
            created_at=now,
            updated_at=now,
            owner_login=owner,
        )

    @staticmethod
    def _empty_result(*, elapsed: float = 0.0) -> ChannelResult:
        """Create an empty ChannelResult for the registry channel.

        Args:
            elapsed: Time elapsed in seconds.

        Returns:
            Empty ChannelResult with REGISTRY channel.
        """
        return ChannelResult(
            channel=DiscoveryChannel.REGISTRY,
            candidates=[],
            total_found=0,
            has_more=False,
            elapsed_seconds=elapsed,
        )
