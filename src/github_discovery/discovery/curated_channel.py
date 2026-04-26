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

# Regex to extract owner/repo from a GitHub URL.
_OWNER_REPO_RE = re.compile(r"github\.com/([^/]+)/([^/]+)/?$")


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

    async def parse_awesome_list(self, awesome_repo_url: str) -> ChannelResult:
        """Parse an awesome-X list README and extract repo URLs.

        Fetches the README via GitHub API, decodes base64 content,
        and extracts GitHub repository URLs from the markdown.

        Args:
            awesome_repo_url: Full GitHub URL of the awesome list repo.

        Returns:
            ChannelResult with discovered candidates from the list.
        """
        start_time = time.monotonic()

        owner_repo = self._extract_owner_repo(awesome_repo_url)
        if not owner_repo:
            logger.warning(
                "curated_channel_invalid_url",
                url=awesome_repo_url,
                reason="Could not extract owner/repo from URL",
            )
            return self._empty_result(elapsed=time.monotonic() - start_time)

        api_url = _README_API_PATH.format(owner=owner_repo[0], repo=owner_repo[1])

        try:
            readme_data = await self._client.get_json(api_url)
        except Exception:
            logger.warning(
                "curated_channel_readme_fetch_failed",
                url=awesome_repo_url,
                api_path=api_url,
            )
            return self._empty_result(elapsed=time.monotonic() - start_time)

        if readme_data is None:
            logger.debug(
                "curated_channel_readme_not_modified",
                url=awesome_repo_url,
            )
            return self._empty_result(elapsed=time.monotonic() - start_time)

        if not isinstance(readme_data, dict):
            logger.warning(
                "curated_channel_readme_unexpected_type",
                url=awesome_repo_url,
                type=type(readme_data).__name__,
            )
            return self._empty_result(elapsed=time.monotonic() - start_time)
        markdown_content = self._decode_readme(readme_data)
        if not markdown_content:
            logger.warning(
                "curated_channel_readme_decode_failed",
                url=awesome_repo_url,
            )
            return self._empty_result(elapsed=time.monotonic() - start_time)

        urls = self.extract_github_urls(markdown_content)
        candidates = [self._url_to_candidate(url) for url in urls]

        elapsed = time.monotonic() - start_time
        logger.info(
            "curated_channel_parsed",
            url=awesome_repo_url,
            candidates=len(candidates),
            elapsed_seconds=round(elapsed, 3),
        )

        return ChannelResult(
            channel=DiscoveryChannel.AWESOME_LIST,
            candidates=candidates,
            total_found=len(candidates),
            has_more=False,
            elapsed_seconds=elapsed,
        )

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

        Args:
            query: Discovery query with optional language/topic filter.

        Returns:
            ChannelResult with candidates up to _MAX_CURATED_CANDIDATES.
        """
        awesome_urls = self._resolve_awesome_lists(query)

        if not awesome_urls:
            # No relevant awesome list found — return empty rather than
            # flooding the pool with irrelevant results from a mega-list.
            logger.debug(
                "curated_channel_no_match",
                query=query.query,
                language=query.language,
            )
            return self._empty_result()

        result = await self.parse_multiple(awesome_urls)

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

        return RepoCandidate(
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
        2. Topic/query keyword match → topic-specific awesome list
        3. No match → empty list (no fallback to mega-list)

        Args:
            query: Discovery query with optional language/topic filter.

        Returns:
            List of awesome list GitHub URLs (may be empty).
        """
        # 1. Language match
        if query.language and query.language.lower() in _DEFAULT_AWESOME_LISTS:
            return _DEFAULT_AWESOME_LISTS[query.language.lower()]

        # 2. Topic match from query.topics or query keywords
        query_words = [w.lower() for w in query.query.replace("-", " ").split()]

        # Check explicit topics first
        if query.topics:
            for topic in query.topics:
                topic_lower = topic.lower()
                if topic_lower in _TOPIC_AWESOME_MAP:
                    return _TOPIC_AWESOME_MAP[topic_lower]

        # Then check query words against topic map
        for word in query_words:
            if word in _TOPIC_AWESOME_MAP:
                return _TOPIC_AWESOME_MAP[word]

        # 3. No match — return empty instead of mega-list fallback.
        # This prevents curated channel from flooding the pool with
        # thousands of irrelevant results from sindresorhus/awesome.
        return []
