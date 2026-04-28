"""Awesome lists and curated sources discovery channel.

Parses awesome-X README lists and community collections
to extract GitHub repository URLs. Curated sources provide
a human-filtered signal (higher trust than raw search).
"""

from __future__ import annotations

import base64
import re
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import structlog

from github_discovery.discovery.domain_classifier import classify_candidate
from github_discovery.discovery.types import ChannelResult, DiscoveryQuery
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel

if TYPE_CHECKING:
    from github_discovery.discovery.github_client import GitHubRestClient

logger = structlog.get_logger("github_discovery.discovery.curated_channel")

# --- Constants ---

_CURATED_DISCOVERY_SCORE = 0.6  # Default score for curated channel — human-filtered signal
_README_API_PATH = "/repos/{owner}/{repo}/readme"
_REPO_PATH_SEGMENTS = 2  # A valid repo URL has exactly /owner/repo

# Regex to extract GitHub URLs from markdown content.
# Matches `https://github.com/...` stopping at whitespace, brackets, quotes, angle brackets.
_GITHUB_URL_RE = re.compile(
    r"https?://github\.com/[^\s\]\)\"'<>]+",
    re.IGNORECASE,
)

# Regex to validate GitHub owner/repo name components.
_VALID_GITHUB_NAME_RE = re.compile(r"^[a-zA-Z0-9_.\-]+$")

# Predefined mapping of languages/topics to awesome list repos.
_DEFAULT_AWESOME_LISTS: dict[str, list[str]] = {
    "python": ["https://github.com/vinta/awesome-python"],
    "javascript": ["https://github.com/sorrycc/awesome-javascript"],
    "typescript": ["https://github.com/sembrestels/awesome-typescript"],
    "rust": ["https://github.com/rust-unofficial/awesome-rust"],
    "go": ["https://github.com/avelino/awesome-go"],
}

# Topic keywords that map to specific awesome lists beyond language.
_TOPIC_AWESOME_MAP: dict[str, list[str]] = {
    "machine-learning": ["https://github.com/josephmisiti/awesome-machine-learning"],
    "ml": ["https://github.com/josephmisiti/awesome-machine-learning"],
    "deep-learning": ["https://github.com/ChristosChristofidis/awesome-deep-learning"],
    "security": ["https://github.com/sbilly/awesome-security"],
    "static-analysis": ["https://github.com/analysis-tools-dev/static-analysis"],
    "testing": ["https://github.com/TheJambo/awesome-testing"],
    "devops": ["https://github.com/bregman-arie/awesome-devops"],
    "cli": ["https://github.com/agarrharr/awesome-cli-apps"],
    "web": ["https://github.com/rehack7/awesome-web"],
    "data-engineering": ["https://github.com/igorbarinov/awesome-data-engineering"],
    "database": ["https://github.com/numetriclabz/awesome-db"],
    "monitoring": ["https://github.com/crazy-canux/awesome-monitoring"],
    "api": ["https://github.com/Kikobeats/awesome-api"],
}

# Max candidates to return from a single curated channel invocation.
# Prevents curated channel from flooding the pool with irrelevant results.
_MAX_CURATED_CANDIDATES = 50

# Max candidates extracted from a single awesome list before truncation.
# Prevents a single huge list from dominating the pool.
_MAX_CURATED_PER_LIST = 200

# Cache TTL for parsed awesome lists (24 hours in seconds).
_CACHE_TTL_SECONDS = 86400.0

# Regex to extract owner/repo from a GitHub URL.
_OWNER_REPO_RE = re.compile(r"github\.com/([^/]+)/([^/]+)/?$")

# GitHub Search API endpoint for topic search fallback.
_SEARCH_ENDPOINT = "/search/repositories"

# Type alias for cache entries: (expiry_timestamp, list[candidate_urls]).
_CacheEntry = tuple[float, list[str]]


class CuratedChannel:
    """Awesome lists and curated sources discovery channel.

    Parses awesome-X README lists and community collections
    to extract GitHub repository URLs.
    """

    def __init__(self, rest_client: GitHubRestClient) -> None:
        """Initialize with a GitHub REST client.

        Args:
            rest_client: Configured GitHubRestClient for API calls.
        """
        self._client = rest_client
        self._cache: dict[str, _CacheEntry] = {}

    async def parse_awesome_list(self, awesome_repo_url: str) -> ChannelResult:
        """Parse an awesome-X list README and extract repo URLs.

        Fetches the README via GitHub API, decodes base64 content,
        and extracts GitHub repository URLs from the markdown.

        Results are cached in memory with a 24h TTL to avoid repeated
        API calls for the same awesome list within a session.

        Args:
            awesome_repo_url: Full GitHub URL of the awesome list repo.

        Returns:
            ChannelResult with discovered candidates from the list.
        """
        start_time = time.monotonic()

        # Check cache first
        cached_candidates = self._get_cached(awesome_repo_url)
        if cached_candidates is not None:
            return ChannelResult(
                channel=DiscoveryChannel.AWESOME_LIST,
                candidates=cached_candidates,
                total_found=len(cached_candidates),
                has_more=False,
                elapsed_seconds=time.monotonic() - start_time,
            )

        owner_repo = self._extract_owner_repo(awesome_repo_url)
        if not owner_repo:
            logger.warning(
                "curated_channel_invalid_url",
                url=awesome_repo_url,
                reason="Could not extract owner/repo from URL",
            )
            return self._empty_result(elapsed=time.monotonic() - start_time)

        # Fetch and decode README
        markdown_content = await self._fetch_readme_content(awesome_repo_url, owner_repo)
        if not markdown_content:
            return self._empty_result(elapsed=time.monotonic() - start_time)

        urls = self.extract_github_urls(markdown_content)

        # Apply per-list cap to prevent a single huge list from dominating
        truncated_urls = urls[:_MAX_CURATED_PER_LIST]
        was_truncated = len(urls) > _MAX_CURATED_PER_LIST

        # Store in cache with TTL
        self._cache[awesome_repo_url] = (
            time.monotonic() + _CACHE_TTL_SECONDS,
            truncated_urls,
        )

        candidates = [self._url_to_candidate(url) for url in truncated_urls]

        elapsed = time.monotonic() - start_time
        logger.info(
            "curated_channel_parsed",
            url=awesome_repo_url,
            candidates=len(candidates),
            truncated=was_truncated,
            original_count=len(urls),
            elapsed_seconds=round(elapsed, 3),
        )

        return ChannelResult(
            channel=DiscoveryChannel.AWESOME_LIST,
            candidates=candidates,
            total_found=len(candidates),
            has_more=was_truncated,
            elapsed_seconds=elapsed,
        )

    def _get_cached(self, awesome_repo_url: str) -> list[RepoCandidate] | None:
        """Return cached candidates if present and not expired, else None.

        Args:
            awesome_repo_url: Awesome list URL to look up.

        Returns:
            List of RepoCandidate from cache, or None if not cached.
        """
        cached = self._cache.get(awesome_repo_url)
        if cached is None:
            return None

        expiry, cached_urls = cached
        if time.monotonic() < expiry:
            logger.debug(
                "curated_channel_cache_hit",
                url=awesome_repo_url,
                cached_candidates=len(cached_urls),
            )
            return [self._url_to_candidate(url) for url in cached_urls]

        # Cache expired — remove stale entry
        del self._cache[awesome_repo_url]
        return None

    async def _fetch_readme_content(
        self,
        awesome_repo_url: str,
        owner_repo: tuple[str, str],
    ) -> str | None:
        """Fetch and decode README content for an awesome list repo.

        Args:
            awesome_repo_url: Full GitHub URL (for logging).
            owner_repo: Tuple of (owner, repo) extracted from URL.

        Returns:
            Decoded markdown string, or None on any failure.
        """
        api_url = _README_API_PATH.format(owner=owner_repo[0], repo=owner_repo[1])

        try:
            readme_data = await self._client.get_json(api_url)
        except Exception:
            logger.warning(
                "curated_channel_readme_fetch_failed",
                url=awesome_repo_url,
                api_path=api_url,
            )
            return None

        if readme_data is None:
            logger.debug(
                "curated_channel_readme_not_modified",
                url=awesome_repo_url,
            )
            return None

        if not isinstance(readme_data, dict):
            logger.warning(
                "curated_channel_readme_unexpected_type",
                url=awesome_repo_url,
                type=type(readme_data).__name__,
            )
            return None

        markdown_content = self._decode_readme(readme_data)
        if not markdown_content:
            logger.warning(
                "curated_channel_readme_decode_failed",
                url=awesome_repo_url,
            )
            return None

        return markdown_content

    async def parse_multiple(self, awesome_repo_urls: list[str]) -> ChannelResult:
        """Parse multiple awesome lists and aggregate with dedup.

        Calls parse_awesome_list for each URL. Individual failures
        are logged but do not prevent other lists from being parsed.

        Args:
            awesome_repo_urls: List of awesome list GitHub URLs.

        Returns:
            Aggregated ChannelResult with deduplicated candidates.
        """
        start_time = time.monotonic()
        seen: dict[str, RepoCandidate] = {}

        for url in awesome_repo_urls:
            result = await self.parse_awesome_list(url)
            for candidate in result.candidates:
                if candidate.full_name not in seen:
                    seen[candidate.full_name] = candidate

        elapsed = time.monotonic() - start_time
        return ChannelResult(
            channel=DiscoveryChannel.AWESOME_LIST,
            candidates=list(seen.values()),
            total_found=len(seen),
            has_more=False,
            elapsed_seconds=elapsed,
        )

    async def search(self, query: DiscoveryQuery) -> ChannelResult:
        """Search curated sources relevant to the query.

        Uses a predefined mapping of languages and topics to awesome lists.
        Only returns results when a relevant awesome list is found — no
        fallback to the mega-list (sindresorhus/awesome) which returns
        thousands of irrelevant results.

        When awesome list parsing yields 0 candidates, falls back to
        GitHub Topic search (``topic:awesome-<word>``) to discover
        curated repos via the Search API.

        Args:
            query: Discovery query with optional language/topic filter.

        Returns:
            ChannelResult with candidates up to _MAX_CURATED_CANDIDATES.
        """
        awesome_urls = self._resolve_awesome_lists(query)

        if not awesome_urls:
            # No relevant awesome list found — try topic search fallback
            logger.debug(
                "curated_channel_no_match_trying_topic_fallback",
                query=query.query,
                language=query.language,
            )
            return await self._topic_search_fallback(query)

        result = await self.parse_multiple(awesome_urls)

        # If awesome list parsing returned nothing, try topic search fallback
        if not result.candidates:
            logger.debug(
                "curated_channel_empty_parse_trying_topic_fallback",
                query=query.query,
                language=query.language,
            )
            return await self._topic_search_fallback(query)

        # Truncate to max candidates (prevent curated channel from dominating)
        cap = min(query.max_candidates, _MAX_CURATED_CANDIDATES)
        truncated = result.candidates[:cap]
        return ChannelResult(
            channel=result.channel,
            candidates=truncated,
            total_found=result.total_found,
            has_more=len(result.candidates) > cap,
            elapsed_seconds=result.elapsed_seconds,
        )

    async def _topic_search_fallback(self, query: DiscoveryQuery) -> ChannelResult:
        """Fallback: search GitHub for repos with ``topic:awesome-<word>``.

        When awesome list parsing yields no candidates, this method
        queries the GitHub Search API for repositories tagged with
        ``awesome-<language>`` or ``awesome-<query-word>`` topics.

        Args:
            query: Original discovery query.

        Returns:
            ChannelResult with candidates from topic search, capped at
            ``_MAX_CURATED_CANDIDATES``.
        """
        start_time = time.monotonic()

        # Build topic search queries — try language first, then query words
        search_queries = self._build_topic_search_queries(query)
        if not search_queries:
            return self._empty_result(elapsed=time.monotonic() - start_time)

        seen: dict[str, RepoCandidate] = {}
        for topic_query in search_queries:
            try:
                items, total_count = await self._client.search(
                    endpoint=_SEARCH_ENDPOINT,
                    query=topic_query,
                    sort="stars",
                    order="desc",
                    max_pages=1,
                    per_page=min(_MAX_CURATED_CANDIDATES, query.max_candidates),
                )
                logger.debug(
                    "curated_channel_topic_search_result",
                    topic_query=topic_query,
                    items_returned=len(items),
                    total_count=total_count,
                )
                for item in items:
                    full_name = item.get("full_name", "")
                    if full_name and full_name not in seen:
                        seen[full_name] = self._search_item_to_candidate(item)
            except Exception:
                logger.warning(
                    "curated_channel_topic_search_failed",
                    topic_query=topic_query,
                )
                continue

        cap = min(query.max_candidates, _MAX_CURATED_CANDIDATES)
        candidates = list(seen.values())[:cap]
        elapsed = time.monotonic() - start_time

        logger.info(
            "curated_channel_topic_fallback_complete",
            candidates=len(candidates),
            elapsed_seconds=round(elapsed, 3),
        )

        return ChannelResult(
            channel=DiscoveryChannel.AWESOME_LIST,
            candidates=candidates,
            total_found=len(seen),
            has_more=len(seen) > cap,
            elapsed_seconds=elapsed,
        )

    @staticmethod
    def _build_topic_search_queries(query: DiscoveryQuery) -> list[str]:
        """Build GitHub search queries for ``topic:awesome-*`` fallback.

        Generates search queries based on language and query keywords,
        prioritizing language-specific topics over generic query words.

        Args:
            query: Original discovery query.

        Returns:
            List of search query strings to try (may be empty).
        """
        queries: list[str] = []

        # Priority 1: language-based topic
        if query.language:
            queries.append(f"topic:awesome-{query.language.lower()} sort:stars")

        # Priority 2: query word-based topics (first 3 meaningful words)
        _min_word_length = 2
        words = [w for w in query.query.replace("-", " ").split() if len(w) > _min_word_length]
        for word in words[:3]:
            queries.append(f"topic:awesome-{word.lower()} sort:stars")

        return queries

    @staticmethod
    def _search_item_to_candidate(item: dict[str, Any]) -> RepoCandidate:
        """Convert a GitHub search result item to RepoCandidate.

        Args:
            item: Single item dict from /search/repositories response.

        Returns:
            RepoCandidate with fields populated from the search item.
        """
        full_name = item.get("full_name", "")
        html_url = item.get("html_url", f"https://github.com/{full_name}")
        created_at_raw = item.get("created_at")
        updated_at_raw = item.get("updated_at")

        now = datetime.now(UTC)
        created_at = datetime.fromisoformat(created_at_raw) if created_at_raw else now
        updated_at = datetime.fromisoformat(updated_at_raw) if updated_at_raw else now

        candidate = RepoCandidate(
            full_name=full_name,
            url=html_url,
            html_url=html_url,
            api_url=item.get("url", f"https://api.github.com/repos/{full_name}"),
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
            owner_login=full_name.split("/")[0] if "/" in full_name else full_name,
            source_channel=DiscoveryChannel.AWESOME_LIST,
            discovery_score=_CURATED_DISCOVERY_SCORE,
        )
        candidate.domain = classify_candidate(candidate)
        return candidate

    @staticmethod
    def extract_github_urls(markdown_content: str) -> list[str]:
        """Extract GitHub repository URLs from markdown content.

        Finds all github.com URLs and filters to those with exactly
        an owner/repo path (no sub-paths like /issues, /pull, etc.).

        Args:
            markdown_content: Raw markdown text to parse.

        Returns:
            Deduplicated list of clean GitHub repo URLs.
        """
        raw_urls = _GITHUB_URL_RE.findall(markdown_content)
        seen: set[str] = set()
        results: list[str] = []

        for url in raw_urls:
            parsed = urlparse(url)
            # Strip leading/trailing slashes, split into path segments
            path = parsed.path.strip("/")
            parts = path.split("/") if path else []

            # Exactly 2 segments = owner/repo
            if len(parts) != _REPO_PATH_SEGMENTS:
                continue

            owner, repo = parts
            if not owner or not repo:
                continue

            # Validate owner/repo names match GitHub conventions
            if not _VALID_GITHUB_NAME_RE.match(owner) or not _VALID_GITHUB_NAME_RE.match(repo):
                continue

            clean_url = f"https://github.com/{owner}/{repo}"
            if clean_url not in seen:
                seen.add(clean_url)
                results.append(clean_url)

        return results

    # --- Private helpers ---

    @staticmethod
    def _decode_readme(readme_data: dict[str, Any]) -> str | None:
        """Decode base64-encoded README content from GitHub API.

        Args:
            readme_data: JSON response from GET /repos/{owner}/{repo}/readme.

        Returns:
            Decoded markdown string, or None on failure.
        """
        content = readme_data.get("content", "")
        encoding = readme_data.get("encoding", "base64")

        if encoding != "base64" or not content:
            return None

        try:
            return base64.b64decode(content).decode("utf-8")
        except Exception:
            return None

    @staticmethod
    def _url_to_candidate(url: str) -> RepoCandidate:
        """Convert a GitHub repo URL to a minimal RepoCandidate.

        Args:
            url: Clean GitHub repository URL (https://github.com/owner/repo).

        Returns:
            RepoCandidate with identity fields populated.
        """
        path = urlparse(url).path.strip("/")
        parts = path.split("/")
        owner = parts[0]
        repo = parts[1]
        full_name = f"{owner}/{repo}"
        now = datetime.now(UTC)

        candidate = RepoCandidate(
            full_name=full_name,
            url=url,
            html_url=url,
            api_url=f"https://api.github.com/repos/{full_name}",
            source_channel=DiscoveryChannel.AWESOME_LIST,
            discovery_score=_CURATED_DISCOVERY_SCORE,
            created_at=now,
            updated_at=now,
            owner_login=owner,
        )
        # TA3: Classify domain for scoring profile selection
        candidate.domain = classify_candidate(candidate)
        return candidate

    @staticmethod
    def _extract_owner_repo(url: str) -> tuple[str, str] | None:
        """Extract owner and repo from a GitHub URL.

        Args:
            url: GitHub repository URL.

        Returns:
            Tuple of (owner, repo) or None if not parseable.
        """
        match = _OWNER_REPO_RE.search(url)
        if match:
            return match.group(1), match.group(2)
        return None

    @staticmethod
    def _empty_result(*, elapsed: float = 0.0) -> ChannelResult:
        """Create an empty ChannelResult for the curated channel.

        Args:
            elapsed: Time elapsed in seconds.

        Returns:
            Empty ChannelResult with AWESOME_LIST channel.
        """
        return ChannelResult(
            channel=DiscoveryChannel.AWESOME_LIST,
            candidates=[],
            total_found=0,
            has_more=False,
            elapsed_seconds=elapsed,
        )

    @staticmethod
    def _resolve_awesome_lists(query: DiscoveryQuery) -> list[str]:
        """Resolve which awesome lists to use based on query.

        Priority:
        1. Language match → language-specific awesome list
        2. Topic match from query.topics → topic-specific awesome list
        3. Query word match → language or topic awesome list
        4. No match → empty list (no fallback to mega-list)

        Args:
            query: Discovery query with optional language/topic filter.

        Returns:
            List of awesome list GitHub URLs (may be empty).
        """
        # 1. Explicit language match
        if query.language and query.language.lower() in _DEFAULT_AWESOME_LISTS:
            return _DEFAULT_AWESOME_LISTS[query.language.lower()]

        # 2. Topic match from explicit topics
        query_words = [w.lower() for w in query.query.replace("-", " ").split()]

        if query.topics:
            for topic in query.topics:
                topic_lower = topic.lower()
                if topic_lower in _TOPIC_AWESOME_MAP:
                    return _TOPIC_AWESOME_MAP[topic_lower]
                if topic_lower in _DEFAULT_AWESOME_LISTS:
                    return _DEFAULT_AWESOME_LISTS[topic_lower]

        # 3. Query word match against both topic and language maps
        for word in query_words:
            if word in _TOPIC_AWESOME_MAP:
                return _TOPIC_AWESOME_MAP[word]
            if word in _DEFAULT_AWESOME_LISTS:
                return _DEFAULT_AWESOME_LISTS[word]

        # 4. No match — return empty instead of mega-list fallback.
        # This prevents curated channel from flooding the pool with
        # thousands of irrelevant results from sindresorhus/awesome.
        return []
