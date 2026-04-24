"""Dependency graph traversal discovery channel.

From seed repos known to be high-quality, discover their
dependencies (what they use) and dependents (what uses them).
Uses GitHub's SBOM endpoint (SPDX format) for dependency resolution.
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from github_discovery.discovery.types import ChannelResult, DiscoveryQuery
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel

if TYPE_CHECKING:
    from github_discovery.discovery.github_client import GitHubRestClient
    from github_discovery.discovery.graphql_client import GitHubGraphQLClient

logger = structlog.get_logger("github_discovery.discovery.dependency_channel")

# --- Constants ---

_DEPENDENCY_DISCOVERY_SCORE = 0.7  # Seed quality weighting — deps from trusted repos
_SBOM_API_PATH = "/repos/{owner}/{repo}/dependency-graph/sbom"
_MAX_DEPTH_MVP = 1  # MVP only supports depth 1 (direct dependencies)
_MIN_PATH_SEGMENTS = 2  # Minimum path segments for owner/repo extraction

# Regex to find GitHub URLs in SBOM package metadata.
# Matches https://github.com/owner/repo in sourceInfo or similar fields.
_GITHUB_URL_RE = re.compile(
    r"https?://github\.com/([a-zA-Z0-9_.\-]+)/([a-zA-Z0-9_.\-]+)",
)

# Regex to parse owner/repo from a GitHub URL.
_OWNER_REPO_FROM_URL_RE = re.compile(
    r"github\.com/([a-zA-Z0-9_.\-]+)/([a-zA-Z0-9_.\-]+?)(?:\.git)?/?$",
)

# Regex to parse short-form owner/repo.
_SHORT_FORM_RE = re.compile(r"^([a-zA-Z0-9_.\-]+)/([a-zA-Z0-9_.\-]+)$")


class DependencyChannel:
    """Dependency graph traversal discovery channel.

    From seed repos known to be high-quality, discover their
    dependencies (what they use) and dependents (what uses them).
    """

    def __init__(
        self,
        rest_client: GitHubRestClient,
        graphql_client: GitHubGraphQLClient,
    ) -> None:
        """Initialize with GitHub REST and GraphQL clients.

        Args:
            rest_client: Configured GitHubRestClient for REST API calls.
            graphql_client: Configured GitHubGraphQLClient for GraphQL queries.
        """
        self._rest_client = rest_client
        self._graphql_client = graphql_client

    async def discover_dependencies(
        self,
        seed_urls: list[str],
        max_depth: int = 1,
    ) -> ChannelResult:
        """Traverse dependencies of seed repos via SBOM endpoint.

        For each seed URL, fetches the SBOM (Software Bill of Materials)
        from GitHub's dependency-graph API. Parses packages looking for
        GitHub source URLs to create RepoCandidate entries.

        Args:
            seed_urls: List of GitHub repository URLs to resolve dependencies for.
            max_depth: Traversal depth (MVP supports only depth 1).

        Returns:
            ChannelResult with discovered dependency candidates, deduplicated.
        """
        start_time = time.monotonic()

        if max_depth > _MAX_DEPTH_MVP:
            logger.info(
                "dependency_channel_depth_limited",
                requested_depth=max_depth,
                effective_depth=_MAX_DEPTH_MVP,
                note="MVP only supports depth 1",
            )

        seen: dict[str, RepoCandidate] = {}

        for seed_url in seed_urls:
            owner_repo = self._parse_owner_repo(seed_url)
            if owner_repo is None:
                logger.warning(
                    "dependency_channel_invalid_seed_url",
                    url=seed_url,
                    reason="Could not extract owner/repo",
                )
                continue

            owner, repo = owner_repo
            sbom_candidates = await self._fetch_sbom_dependencies(owner, repo)

            for candidate in sbom_candidates:
                if candidate.full_name not in seen:
                    seen[candidate.full_name] = candidate

        elapsed = time.monotonic() - start_time
        logger.info(
            "dependency_channel_discovered",
            seed_count=len(seed_urls),
            candidates=len(seen),
            elapsed_seconds=round(elapsed, 3),
        )

        return ChannelResult(
            channel=DiscoveryChannel.DEPENDENCY,
            candidates=list(seen.values()),
            total_found=len(seen),
            has_more=False,
            elapsed_seconds=elapsed,
        )

    async def discover_dependents(
        self,
        seed_urls: list[str],
        max_results: int = 50,
    ) -> ChannelResult:
        """Find repos that depend on seed repos via GraphQL.

        NOTE: GitHub's GraphQL API does not expose a ``dependents``
        connection on Repository objects. The dependents data is only
        available via the web UI (``/network/dependents``). This method
        returns an empty result for the MVP. Future implementation would
        require web scraping or alternative APIs.

        Args:
            seed_urls: List of GitHub repository URLs to find dependents for.
            max_results: Maximum number of dependent repos to return.

        Returns:
            Empty ChannelResult (MVP fallback).
        """
        logger.info(
            "dependency_channel_dependents_not_available",
            seed_count=len(seed_urls),
            note="GitHub GraphQL API does not expose dependents; "
            "future implementation needs web scraping",
        )

        return ChannelResult(
            channel=DiscoveryChannel.DEPENDENCY,
            candidates=[],
            total_found=0,
            has_more=False,
            elapsed_seconds=0.0,
        )

    async def search(self, query: DiscoveryQuery) -> ChannelResult:
        """Run dependency discovery from seed URLs.

        Uses ``query.seed_urls`` as seed repositories for dependency
        traversal. Returns an empty result if no seed URLs are provided
        (the dependency channel requires explicit seeds).

        Args:
            query: Discovery query with optional ``seed_urls``.

        Returns:
            ChannelResult with discovered dependencies.
        """
        seed_urls = query.seed_urls

        if not seed_urls:
            logger.debug(
                "dependency_channel_no_seeds",
                query=query.query,
                note="Dependency channel requires seed URLs",
            )
            return self._empty_result()

        result = await self.discover_dependencies(seed_urls=seed_urls)

        # Truncate to max_candidates
        truncated = result.candidates[: query.max_candidates]
        return ChannelResult(
            channel=result.channel,
            candidates=truncated,
            total_found=result.total_found,
            has_more=len(result.candidates) > query.max_candidates,
            elapsed_seconds=result.elapsed_seconds,
        )

    # --- Private helpers ---

    @staticmethod
    def _parse_owner_repo(url: str) -> tuple[str, str] | None:
        """Extract owner and repo from various GitHub URL formats.

        Handles:
        - ``https://github.com/owner/repo``
        - ``https://github.com/owner/repo.git``
        - ``https://github.com/owner/repo/``
        - ``https://api.github.com/repos/owner/repo``
        - ``owner/repo`` (short form)

        Args:
            url: A GitHub URL or short-form ``owner/repo`` string.

        Returns:
            Tuple of ``(owner, repo)`` or None if not parseable.
        """
        if not url:
            return None

        # Try short form first: owner/repo
        short_match = _SHORT_FORM_RE.match(url)
        if short_match:
            return short_match.group(1), short_match.group(2)

        # Try api.github.com/repos/owner/repo
        if "api.github.com/repos/" in url:
            path = url.rsplit("api.github.com/repos/", maxsplit=1)[-1]
            parts = path.strip("/").split("/")
            if len(parts) >= _MIN_PATH_SEGMENTS:
                return parts[0], parts[1].replace(".git", "")

        # Try github.com/owner/repo — extract from full URL
        url_match = _OWNER_REPO_FROM_URL_RE.search(url)
        if url_match:
            return url_match.group(1), url_match.group(2)

        # Fallback: try to find github.com/owner/repo anywhere in the URL
        github_match = _GITHUB_URL_RE.search(url)
        if github_match:
            return github_match.group(1), github_match.group(2)

        return None

    async def _fetch_sbom_dependencies(
        self,
        owner: str,
        repo: str,
    ) -> list[RepoCandidate]:
        """Fetch and parse SBOM for a single repository.

        Args:
            owner: Repository owner login.
            repo: Repository name.

        Returns:
            List of RepoCandidate entries parsed from the SBOM.
        """
        api_url = _SBOM_API_PATH.format(owner=owner, repo=repo)

        try:
            sbom_data = await self._rest_client.get_json(api_url)
        except Exception:
            logger.warning(
                "dependency_channel_sbom_fetch_failed",
                owner=owner,
                repo=repo,
                api_path=api_url,
            )
            return []

        if sbom_data is None:
            logger.debug(
                "dependency_channel_sbom_not_modified",
                owner=owner,
                repo=repo,
            )
            return []

        if not isinstance(sbom_data, dict):
            logger.warning(
                "dependency_channel_sbom_unexpected_type",
                owner=owner,
                repo=repo,
                type=type(sbom_data).__name__,
            )
            return []
        return self._parse_sbom(sbom_data)

    @staticmethod
    def _parse_sbom(sbom_data: dict[str, Any]) -> list[RepoCandidate]:
        """Parse an SBOM response and extract GitHub-hosted packages.

        Looks for GitHub URLs in each package's ``sourceInfo`` field
        and ``externalRefs`` entries. Packages without identifiable
        GitHub source URLs are skipped.

        Args:
            sbom_data: Parsed JSON from the SBOM API endpoint.

        Returns:
            List of RepoCandidate entries for packages with GitHub URLs.
        """
        sbom = sbom_data.get("sbom", {})
        packages = sbom.get("packages", [])

        if not isinstance(packages, list):
            return []

        candidates: list[RepoCandidate] = []

        for package in packages:
            if not isinstance(package, dict):
                continue

            github_url = DependencyChannel._extract_github_url_from_package(package)
            if github_url is None:
                continue

            owner_repo = DependencyChannel._parse_owner_repo(github_url)
            if owner_repo is None:
                continue

            owner, repo = owner_repo
            full_name = f"{owner}/{repo}"
            now = datetime.now(UTC)

            candidate = RepoCandidate(
                full_name=full_name,
                url=f"https://github.com/{full_name}",
                html_url=f"https://github.com/{full_name}",
                api_url=f"https://api.github.com/repos/{full_name}",
                source_channel=DiscoveryChannel.DEPENDENCY,
                discovery_score=_DEPENDENCY_DISCOVERY_SCORE,
                created_at=now,
                updated_at=now,
                owner_login=owner,
            )
            candidates.append(candidate)

        return candidates

    @staticmethod
    def _extract_github_url_from_package(package: dict[str, Any]) -> str | None:
        """Extract a GitHub source URL from an SBOM package entry.

        Checks multiple fields where GitHub URLs may appear:
        1. ``sourceInfo`` — often contains ``acr:https://github.com/...``
        2. ``externalRefs`` — may contain a ``SOURCE_URL`` reference
        3. ``downloadLocation`` — may be a GitHub URL

        Args:
            package: A single package dict from the SBOM ``packages`` array.

        Returns:
            A clean GitHub repository URL, or None if not found.
        """
        # Check sourceInfo field
        source_info = package.get("sourceInfo", "")
        if isinstance(source_info, str) and "github.com" in source_info:
            match = _GITHUB_URL_RE.search(source_info)
            if match:
                return f"https://github.com/{match.group(1)}/{match.group(2)}"

        # Check externalRefs for SOURCE_URL or similar
        external_refs = package.get("externalRefs", [])
        if isinstance(external_refs, list):
            for ref in external_refs:
                if not isinstance(ref, dict):
                    continue
                locator = ref.get("referenceLocator", "")
                if isinstance(locator, str) and "github.com" in locator:
                    match = _GITHUB_URL_RE.search(locator)
                    if match:
                        return f"https://github.com/{match.group(1)}/{match.group(2)}"

        # Check downloadLocation
        download_location = package.get("downloadLocation", "")
        if isinstance(download_location, str) and "github.com" in download_location:
            match = _GITHUB_URL_RE.search(download_location)
            if match:
                return f"https://github.com/{match.group(1)}/{match.group(2)}"

        return None

    @staticmethod
    def _empty_result() -> ChannelResult:
        """Create an empty ChannelResult for the dependency channel.

        Returns:
            Empty ChannelResult with DEPENDENCY channel.
        """
        return ChannelResult(
            channel=DiscoveryChannel.DEPENDENCY,
            candidates=[],
            total_found=0,
            has_more=False,
            elapsed_seconds=0.0,
        )
