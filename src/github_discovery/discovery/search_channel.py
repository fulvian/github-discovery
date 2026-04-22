"""GitHub Search API discovery channel.

Uses /search/repositories with structured queries to discover candidate
repositories. Sorts by recency/updated by default to reduce popularity
bias and surface actively maintained projects.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog

from github_discovery.discovery.types import ChannelResult, DiscoveryQuery
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel

if TYPE_CHECKING:
    from github_discovery.discovery.github_client import GitHubRestClient

logger = structlog.get_logger("github_discovery.discovery.search_channel")

# --- Constants ---

_MEGA_POPULAR_STAR_THRESHOLD = 100_000
_INACTIVITY_DAYS = 180  # ~6 months
_SEARCH_ENDPOINT = "/search/repositories"
_DEFAULT_SORT = "updated"
_DEFAULT_ORDER = "desc"
_GITHUB_SCORE_NORMALIZATION_FACTOR = 100.0
_MAX_PER_PAGE = 100


class SearchChannel:
    """GitHub Search API discovery channel.

    Uses /search/repositories with structured queries.
    Sorts by recency/updated by default to reduce popularity bias.
    """

    def __init__(self, client: GitHubRestClient) -> None:
        """Initialize with a GitHub REST client.

        Args:
            client: Configured GitHubRestClient for API calls.
        """
        self._client = client

    def build_query(self, query: DiscoveryQuery) -> str:
        """Build GitHub search query string with qualifiers.

        Constructs the `q` parameter for /search/repositories, adding
        qualifiers for language, topics, activity, and visibility.

        Args:
            query: Discovery query with optional filters.

        Returns:
            GitHub search query string with qualifiers.
        """
        parts: list[str] = [query.query]

        # Language filter
        if query.language:
            parts.append(f"language:{query.language}")

        # Topic filters
        if query.topics:
            for topic in query.topics:
                parts.append(f"topic:{topic}")

        # Exclude inactive repos (pushed within last ~6 months)
        cutoff = datetime.now(UTC) - timedelta(days=_INACTIVITY_DAYS)
        parts.append(f"pushed:>{cutoff.strftime('%Y-%m-%d')}")

        # Exclude archived repos
        parts.append("archived:false")

        # Public repos only
        parts.append("is:public")

        # Exclude mega-popular repos (anti-star bias)
        parts.append(f"-stars:>{_MEGA_POPULAR_STAR_THRESHOLD}")

        return " ".join(parts)

    async def search(self, query: DiscoveryQuery) -> ChannelResult:
        """Execute search and return ChannelResult with RepoCandidate list.

        Builds a structured query, executes it via the GitHub Search API,
        maps results to RepoCandidate objects, and respects max_candidates.

        Args:
            query: Discovery query specifying search term and filters.

        Returns:
            ChannelResult with discovered candidates and metadata.
        """
        start_time = time.monotonic()

        query_string = self.build_query(query)

        # Calculate pagination parameters to avoid over-fetching
        per_page = min(_MAX_PER_PAGE, query.max_candidates)
        max_pages = max(1, (query.max_candidates + per_page - 1) // per_page)

        items, total_count = await self._client.search(
            endpoint=_SEARCH_ENDPOINT,
            query=query_string,
            sort=_DEFAULT_SORT,
            order=_DEFAULT_ORDER,
            max_pages=max_pages,
            per_page=per_page,
        )

        # Map items to RepoCandidate, respecting max_candidates
        candidates = [self._map_item(item) for item in items[: query.max_candidates]]

        # Warn if results appear incomplete
        if total_count > len(items) and len(items) < query.max_candidates:
            logger.warning(
                "search_results_potentially_incomplete",
                total_count=total_count,
                returned=len(items),
                query_text=query.query,
            )

        elapsed = time.monotonic() - start_time

        return ChannelResult(
            channel=DiscoveryChannel.SEARCH,
            candidates=candidates,
            total_found=total_count,
            has_more=total_count > len(candidates),
            rate_limit_remaining=self._client.search_rate_limit_remaining,
            elapsed_seconds=elapsed,
        )

    def _map_item(self, item: dict[str, Any]) -> RepoCandidate:
        """Convert a GitHub API search result item to RepoCandidate.

        Args:
            item: Single item dict from /search/repositories response.

        Returns:
            RepoCandidate with fields populated from the API item.
        """
        full_name = item.get("full_name", "")
        html_url = item.get("html_url", f"https://github.com/{full_name}")

        # Parse datetime fields (GitHub returns ISO 8601 with Z suffix)
        created_at = datetime.fromisoformat(item["created_at"])
        updated_at = datetime.fromisoformat(item["updated_at"])
        pushed_at_raw = item.get("pushed_at")
        pushed_at = datetime.fromisoformat(pushed_at_raw) if pushed_at_raw else None

        # Normalize GitHub search relevance score to 0.0-1.0
        raw_score = item.get("score", 1.0)
        discovery_score = min(raw_score / _GITHUB_SCORE_NORMALIZATION_FACTOR, 1.0)

        return RepoCandidate(
            full_name=full_name,
            url=html_url,
            html_url=html_url,
            api_url=item.get("url", ""),
            description=item.get("description") or "",
            language=item.get("language"),
            topics=item.get("topics") or [],
            stars=item.get("stargazers_count", 0),
            forks_count=item.get("forks_count", 0),
            open_issues_count=item.get("open_issues_count", 0),
            size_kb=item.get("size", 0),
            license_info=item.get("license"),
            default_branch=item.get("default_branch", "main"),
            archived=item.get("archived", False),
            disabled=item.get("disabled", False),
            created_at=created_at,
            updated_at=updated_at,
            pushed_at=pushed_at,
            owner_login=full_name.split("/")[0] if "/" in full_name else full_name,
            source_channel=DiscoveryChannel.SEARCH,
            discovery_score=discovery_score,
        )
