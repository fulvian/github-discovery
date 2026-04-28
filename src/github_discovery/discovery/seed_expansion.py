"""Seed-based candidate pool expansion channel.

Expands the candidate pool from seed repositories using two strategies:
- **Org adjacency**: Find repos from the same organization as seed repos.
- **Contributor analysis**: Find repos from top contributors to seed repos.

Both strategies produce candidates with a proximity signal — repos connected
to known high-quality seeds are likely worth evaluating.
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog

from github_discovery.discovery.domain_classifier import classify_candidate
from github_discovery.discovery.types import ChannelResult
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel

if TYPE_CHECKING:
    from github_discovery.discovery.github_client import GitHubRestClient
    from github_discovery.discovery.graphql_client import GitHubGraphQLClient

logger = structlog.get_logger("github_discovery.discovery.seed_expansion")

# --- Constants ---

_ORG_DISCOVERY_SCORE = 0.65  # Org adjacency signal — strong relationship
_CONTRIBUTOR_DISCOVERY_SCORE = 0.55  # Co-contributor signal — weaker than org adjacency
_MAX_DEPTH_MVP = 1  # MVP only supports depth 1 (direct expansion)
_MIN_PATH_SEGMENTS = 2  # Minimum path segments for owner/repo extraction
_DEFAULT_STRATEGIES: list[str] = ["org", "contributors"]

# Regex patterns for URL parsing (shared with dependency_channel)
_GITHUB_URL_RE = re.compile(
    r"https?://github\.com/([a-zA-Z0-9_.\-]+)/([a-zA-Z0-9_.\-]+)",
)
_OWNER_REPO_FROM_URL_RE = re.compile(
    r"github\.com/([a-zA-Z0-9_.\-]+)/([a-zA-Z0-9_.\-]+?)(?:\.git)?/?$",
)
_SHORT_FORM_RE = re.compile(r"^([a-zA-Z0-9_.\-]+)/([a-zA-Z0-9_.\-]+)$")


class SeedExpansion:
    """Expand candidate pool from seed repositories.

    Strategies: co-contributor analysis, org adjacency.
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

    async def expand_by_org(
        self,
        seed_urls: list[str],
        max_per_org: int = 20,
    ) -> ChannelResult:
        """Find repos from the same org as seed repos.

        For each seed URL, extracts the owner and fetches repos from that
        org (or user). Tries the org endpoint first; falls back to user
        endpoint if the org endpoint fails (e.g., 404 for personal accounts).

        Args:
            seed_urls: List of GitHub repository URLs to use as seeds.
            max_per_org: Maximum number of repos to return per org.

        Returns:
            ChannelResult with discovered candidates from org adjacency.
        """
        start_time = time.monotonic()
        seen: dict[str, RepoCandidate] = {}
        seen_owners: set[str] = set()

        seed_names = self._extract_seed_names(seed_urls)

        for seed_url in seed_urls:
            owner_repo = self._parse_owner_repo(seed_url)
            if owner_repo is None:
                logger.warning(
                    "seed_expansion_invalid_url",
                    url=seed_url,
                    reason="Could not extract owner/repo",
                )
                continue

            owner, _repo = owner_repo

            # Deduplicate across seeds — same owner, same results
            if owner in seen_owners:
                continue
            seen_owners.add(owner)

            org_repos = await self._fetch_org_or_user_repos(owner)
            # Sort by updated_at desc, take most recent
            org_repos.sort(
                key=lambda r: r.get("updated_at", ""),
                reverse=True,
            )
            org_repos = org_repos[:max_per_org]

            for repo_data in org_repos:
                candidate = self._map_repo(repo_data, discovery_score=_ORG_DISCOVERY_SCORE)
                if candidate.full_name not in seed_names and candidate.full_name not in seen:
                    seen[candidate.full_name] = candidate

        elapsed = time.monotonic() - start_time
        logger.info(
            "seed_expansion_org_complete",
            seed_count=len(seed_urls),
            candidates=len(seen),
            elapsed_seconds=round(elapsed, 3),
        )

        return ChannelResult(
            channel=DiscoveryChannel.SEED_EXPANSION,
            candidates=list(seen.values()),
            total_found=len(seen),
            has_more=False,
            elapsed_seconds=elapsed,
        )

    async def expand_by_contributors(
        self,
        seed_urls: list[str],
        max_contributors: int = 10,
        max_repos_per_contributor: int = 5,
    ) -> ChannelResult:
        """Find repos from contributors to seed repos.

        For each seed URL, fetches the top contributors (sorted by number
        of contributions), then fetches each contributor's public repos.
        Forks are excluded from results.

        Args:
            seed_urls: List of GitHub repository URLs to use as seeds.
            max_contributors: Maximum number of top contributors to analyze.
            max_repos_per_contributor: Max repos per contributor to include.

        Returns:
            ChannelResult with discovered candidates from contributor analysis.
        """
        start_time = time.monotonic()
        seen: dict[str, RepoCandidate] = {}

        seed_names = self._extract_seed_names(seed_urls)

        for seed_url in seed_urls:
            owner_repo = self._parse_owner_repo(seed_url)
            if owner_repo is None:
                logger.warning(
                    "seed_expansion_invalid_url",
                    url=seed_url,
                    reason="Could not extract owner/repo",
                )
                continue

            owner, repo = owner_repo
            contributors = await self._fetch_contributors(owner, repo)

            # Take top contributors sorted by contributions
            contributors = contributors[:max_contributors]

            for contributor in contributors:
                username = contributor.get("login", "")
                if not username:
                    continue

                user_repos = await self._fetch_user_repos(username)
                # Sort by updated_at desc
                user_repos.sort(
                    key=lambda r: r.get("updated_at", ""),
                    reverse=True,
                )
                user_repos = user_repos[:max_repos_per_contributor]

                for repo_data in user_repos:
                    # Exclude forks
                    if repo_data.get("fork", False):
                        continue

                    candidate = self._map_repo(
                        repo_data, discovery_score=_CONTRIBUTOR_DISCOVERY_SCORE
                    )
                    if candidate.full_name not in seed_names and candidate.full_name not in seen:
                        seen[candidate.full_name] = candidate

        elapsed = time.monotonic() - start_time
        logger.info(
            "seed_expansion_contributors_complete",
            seed_count=len(seed_urls),
            candidates=len(seen),
            elapsed_seconds=round(elapsed, 3),
        )

        return ChannelResult(
            channel=DiscoveryChannel.SEED_EXPANSION,
            candidates=list(seen.values()),
            total_found=len(seen),
            has_more=False,
            elapsed_seconds=elapsed,
        )

    async def auto_discover_seeds(
        self,
        query_text: str,
        max_seeds: int = 3,
    ) -> list[str]:
        """Auto-discover seed repo URLs from a search query.

        Runs a quick GitHub search and returns the top N repo URLs.
        Used when seed_urls is empty and auto_seed is enabled.

        Args:
            query_text: Search query to find seed repositories.
            max_seeds: Maximum number of seed URLs to return.

        Returns:
            List of GitHub repository HTML URLs.
        """
        try:
            items, _ = await self._rest_client.search(
                "/search/repositories",
                query_text,
                sort="stars",
                order="desc",
                max_pages=1,
                per_page=max_seeds,
            )
            return [
                item.get("html_url", "")
                for item in items[:max_seeds]
                if item.get("html_url")
            ]
        except Exception:
            logger.warning("auto_seed_search_failed", query=query_text)
            return []

    async def expand(
        self,
        seed_urls: list[str],
        strategies: list[str] | None = None,
        max_depth: int = 1,
        auto_seed_query: str | None = None,
    ) -> ChannelResult:
        """Run expansion strategies on seed repos.

        Runs selected strategies concurrently, merges results with
        deduplication by ``full_name``, and excludes seed repos.

        When ``seed_urls`` is empty and ``auto_seed_query`` is provided,
        auto-discovers seeds via GitHub search first.

        Args:
            seed_urls: List of GitHub repository URLs to use as seeds.
            strategies: Expansion strategies to run. Default: ``["org", "contributors"]``.
            max_depth: Traversal depth (MVP only supports depth 1).
            auto_seed_query: When set and seed_urls is empty, auto-discover seeds.

        Returns:
            ChannelResult with aggregated, deduplicated candidates.
        """
        start_time = time.monotonic()

        seed_urls = await self._resolve_seeds(seed_urls, auto_seed_query)

        if not seed_urls:
            return self._empty_result()

        if max_depth > _MAX_DEPTH_MVP:
            logger.info(
                "seed_expansion_depth_limited",
                requested_depth=max_depth,
                effective_depth=_MAX_DEPTH_MVP,
                note="MVP only supports depth 1",
            )

        active_strategies = strategies if strategies is not None else _DEFAULT_STRATEGIES

        # Run selected strategies concurrently
        tasks: list[asyncio.Task[ChannelResult]] = []
        for strategy in active_strategies:
            if strategy == "org":
                tasks.append(
                    asyncio.create_task(self.expand_by_org(seed_urls)),
                )
            elif strategy == "contributors":
                tasks.append(
                    asyncio.create_task(
                        self.expand_by_contributors(seed_urls),
                    ),
                )
            else:
                logger.warning(
                    "seed_expansion_unknown_strategy",
                    strategy=strategy,
                )

        if not tasks:
            return self._empty_result()

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge with dedup by full_name
        merged: dict[str, RepoCandidate] = {}
        for result in results:
            if isinstance(result, BaseException):
                logger.warning(
                    "seed_expansion_strategy_failed",
                    error=str(result),
                )
                continue
            for candidate in result.candidates:
                if candidate.full_name not in merged:
                    merged[candidate.full_name] = candidate

        elapsed = time.monotonic() - start_time
        logger.info(
            "seed_expansion_expand_complete",
            strategies=active_strategies,
            seed_count=len(seed_urls),
            candidates=len(merged),
            elapsed_seconds=round(elapsed, 3),
        )

        return ChannelResult(
            channel=DiscoveryChannel.SEED_EXPANSION,
            candidates=list(merged.values()),
            total_found=len(merged),
            has_more=False,
            elapsed_seconds=elapsed,
        )

    # --- Private helpers ---

    async def _resolve_seeds(
        self,
        seed_urls: list[str],
        auto_seed_query: str | None,
    ) -> list[str]:
        """Resolve seed URLs, auto-discovering if needed.

        When seed_urls is empty and auto_seed_query is provided,
        runs a GitHub search to discover seed repos automatically.

        Args:
            seed_urls: Explicit seed URLs (may be empty).
            auto_seed_query: Query text for auto-discovery, or None.

        Returns:
            Resolved list of seed URLs (may be empty).
        """
        if seed_urls or not auto_seed_query:
            return seed_urls

        discovered = await self.auto_discover_seeds(auto_seed_query)
        if discovered:
            logger.info(
                "seed_expansion_auto_seed_discovered",
                query=auto_seed_query,
                seeds=discovered,
            )
        else:
            logger.info(
                "seed_expansion_auto_seed_empty",
                query=auto_seed_query,
                note="No seeds found, returning empty result",
            )
        return discovered

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

        # Try github.com/owner/repo
        url_match = _OWNER_REPO_FROM_URL_RE.search(url)
        if url_match:
            return url_match.group(1), url_match.group(2)

        # Fallback: find github.com/owner/repo anywhere in URL
        github_match = _GITHUB_URL_RE.search(url)
        if github_match:
            return github_match.group(1), github_match.group(2)

        return None

    @staticmethod
    def _extract_seed_names(seed_urls: list[str]) -> set[str]:
        """Extract full_name set from seed URLs for exclusion filtering.

        Args:
            seed_urls: List of GitHub repository URLs.

        Returns:
            Set of ``owner/repo`` strings parsed from seed URLs.
        """
        names: set[str] = set()
        for url in seed_urls:
            parsed = SeedExpansion._parse_owner_repo(url)
            if parsed is not None:
                names.add(f"{parsed[0]}/{parsed[1]}")
        return names

    @staticmethod
    def _map_repo(
        repo_data: dict[str, Any],
        *,
        discovery_score: float = _ORG_DISCOVERY_SCORE,
    ) -> RepoCandidate:
        """Convert a GitHub API repo JSON object to RepoCandidate.

        Args:
            repo_data: Repo dict from GitHub API (org repos or user repos endpoint).
            discovery_score: Discovery score for the candidate.

        Returns:
            RepoCandidate with fields populated from the API data.
        """
        full_name = repo_data.get("full_name", "")
        html_url = repo_data.get("html_url", f"https://github.com/{full_name}")

        # Parse datetime fields (GitHub returns ISO 8601 with Z suffix)
        created_at_raw = repo_data.get("created_at", "2022-01-01T00:00:00Z")
        updated_at_raw = repo_data.get("updated_at", "2022-01-01T00:00:00Z")
        pushed_at_raw = repo_data.get("pushed_at")

        created_at = datetime.fromisoformat(created_at_raw)
        updated_at = datetime.fromisoformat(updated_at_raw)
        pushed_at = datetime.fromisoformat(pushed_at_raw) if pushed_at_raw else None

        owner_data = repo_data.get("owner", {})
        owner_login = (
            owner_data.get("login", full_name.split("/")[0])
            if isinstance(owner_data, dict)
            else full_name.split("/")[0]
        )

        candidate = RepoCandidate(
            full_name=full_name,
            url=html_url,
            html_url=html_url,
            api_url=repo_data.get("url", f"https://api.github.com/repos/{full_name}"),
            description=repo_data.get("description") or "",
            language=repo_data.get("language"),
            topics=repo_data.get("topics") or [],
            stars=repo_data.get("stargazers_count", 0),
            forks_count=repo_data.get("forks_count", 0),
            open_issues_count=repo_data.get("open_issues_count", 0),
            size_kb=repo_data.get("size", 0),
            license_info=repo_data.get("license"),
            default_branch=repo_data.get("default_branch", "main"),
            archived=repo_data.get("archived", False),
            disabled=repo_data.get("disabled", False),
            created_at=created_at,
            updated_at=updated_at,
            pushed_at=pushed_at,
            owner_login=owner_login,
            source_channel=DiscoveryChannel.SEED_EXPANSION,
            discovery_score=discovery_score,
        )
        # TA3: Classify domain for scoring profile selection
        candidate.domain = classify_candidate(candidate)
        return candidate

    async def _fetch_org_or_user_repos(
        self,
        owner: str,
    ) -> list[dict[str, Any]]:
        """Fetch repos from an org or user account.

        Tries the org endpoint first; if it fails, falls back to the
        user endpoint. Returns an empty list on error.

        Args:
            owner: Organization or user login.

        Returns:
            List of repo dicts from GitHub API.
        """
        # Try org endpoint first
        org_url = f"/orgs/{owner}/repos"
        try:
            repos = await self._rest_client.get_all_pages(org_url)
            return list(repos)
        except Exception:
            logger.debug(
                "seed_expansion_org_endpoint_failed",
                owner=owner,
                note="Falling back to user endpoint",
            )

        # Fallback: user endpoint
        user_url = f"/users/{owner}/repos"
        try:
            repos = await self._rest_client.get_all_pages(user_url)
            return list(repos)
        except Exception:
            logger.warning(
                "seed_expansion_user_endpoint_failed",
                owner=owner,
                note="Both org and user endpoints failed",
            )
            return []

    async def _fetch_contributors(
        self,
        owner: str,
        repo: str,
    ) -> list[dict[str, Any]]:
        """Fetch contributors for a repository.

        Args:
            owner: Repository owner login.
            repo: Repository name.

        Returns:
            List of contributor dicts sorted by contributions.
        """
        url = f"/repos/{owner}/{repo}/contributors"
        try:
            contributors = await self._rest_client.get_all_pages(url)
            return list(contributors)
        except Exception:
            logger.warning(
                "seed_expansion_contributors_failed",
                owner=owner,
                repo=repo,
            )
            return []

    async def _fetch_user_repos(
        self,
        username: str,
    ) -> list[dict[str, Any]]:
        """Fetch public repos for a user.

        Args:
            username: GitHub user login.

        Returns:
            List of repo dicts for the user.
        """
        url = f"/users/{username}/repos"
        try:
            repos = await self._rest_client.get_all_pages(url)
            return list(repos)
        except Exception:
            logger.warning(
                "seed_expansion_user_repos_failed",
                username=username,
            )
            return []

    @staticmethod
    def _empty_result() -> ChannelResult:
        """Create an empty ChannelResult for the seed expansion channel.

        Returns:
            Empty ChannelResult with SEED_EXPANSION channel.
        """
        return ChannelResult(
            channel=DiscoveryChannel.SEED_EXPANSION,
            candidates=[],
            total_found=0,
            has_more=False,
            elapsed_seconds=0.0,
        )
