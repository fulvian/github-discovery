"""GitHub Code Search discovery channel.

Finds repos by quality signal patterns in their files.
Lower popularity bias than Search API — discovers by practices,
not stars. Code search matches file content/names, not metadata.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from github_discovery.discovery.types import ChannelResult, DiscoveryQuery
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel

if TYPE_CHECKING:
    from github_discovery.discovery.github_client import GitHubRestClient

logger = structlog.get_logger("github_discovery.discovery.code_search_channel")

# --- Constants ---

_CODE_SEARCH_ENDPOINT = "/search/code"
_MAX_PAGES_CODE_SEARCH = 1  # Code search rate limit: only 10 req/min
_PER_PAGE_CODE_SEARCH = 30  # Lower per_page to stay within rate budget
_BASE_DISCOVERY_SCORE = 0.5  # Base score for code-search-discovered repos
_MULTI_SIGNAL_BONUS = 0.1  # Bonus per additional signal category matched

# Quality signal patterns per category — these are GitHub code search qualifiers
# that indicate good engineering practices.
QUALITY_SIGNAL_PATTERNS: dict[str, list[str]] = {
    "testing": [
        "filename:conftest.py",
        "filename:pytest.ini",
        "filename:.mocharc",
    ],
    "ci_cd": [
        "filename:.github/workflows path:.github",
        "filename:Jenkinsfile",
        "filename:.gitlab-ci.yml",
    ],
    "security": [
        "filename:SECURITY.md",
        "filename:security.txt",
    ],
    "documentation": [
        "filename:CONTRIBUTING.md",
        "filename:CHANGELOG.md",
    ],
}


class CodeSearchChannel:
    """GitHub Code Search discovery channel.

    Finds repos by quality signal patterns in their files.
    Lower popularity bias than Search API — finds by practices, not stars.
    """

    def __init__(self, client: GitHubRestClient) -> None:
        """Initialize with a GitHub REST client.

        Args:
            client: Configured GitHubRestClient for API calls.
        """
        self._client = client

    async def search(self, query: DiscoveryQuery) -> ChannelResult:
        """Search for repos using quality signals + query keywords.

        Builds code search queries that combine the user's keyword query
        with quality signal patterns. Deduplicates by full_name within
        the channel (same repo can match multiple patterns).

        Args:
            query: Discovery query specifying search term and filters.

        Returns:
            ChannelResult with discovered candidates and metadata.
        """
        start_time = time.monotonic()

        # Collect all patterns into a single combined query approach
        all_items, _seen, total_count = await self._execute_queries(
            keywords=query.query,
            language=query.language,
            max_candidates=query.max_candidates,
        )

        # Apply max_candidates limit
        candidates = all_items[: query.max_candidates]

        elapsed = time.monotonic() - start_time

        return ChannelResult(
            channel=DiscoveryChannel.CODE_SEARCH,
            candidates=candidates,
            total_found=total_count,
            has_more=total_count > len(candidates),
            rate_limit_remaining=self._client.search_rate_limit_remaining,
            elapsed_seconds=elapsed,
        )

    async def search_quality_signals(
        self,
        language: str | None = None,
        signals: list[str] | None = None,
    ) -> ChannelResult:
        """Search for repos with specific quality signal patterns.

        Queries each signal category independently and aggregates
        results with deduplication across categories.

        Args:
            language: Optional language qualifier to filter results.
            signals: Optional list of signal categories to query.
                     None = query all categories.

        Returns:
            Aggregated ChannelResult with deduplicated candidates.
        """
        start_time = time.monotonic()

        categories = self._filter_categories(signals)

        seen_full_names: dict[str, tuple[RepoCandidate, int]] = {}
        total_count = 0

        for category, patterns in categories.items():
            # Combine all patterns for this category into one query
            combined_pattern = " ".join(patterns)
            query_str = self._build_query(combined_pattern, language=language)

            try:
                items, count = await self._client.search(
                    endpoint=_CODE_SEARCH_ENDPOINT,
                    query=query_str,
                    max_pages=_MAX_PAGES_CODE_SEARCH,
                    per_page=_PER_PAGE_CODE_SEARCH,
                )
            except Exception:
                logger.warning(
                    "code_search_query_failed",
                    category=category,
                    query=query_str,
                )
                continue

            total_count += count

            for item in items:
                candidate = self._map_item(item)
                if candidate.full_name not in seen_full_names:
                    seen_full_names[candidate.full_name] = (candidate, 1)
                else:
                    # Track multi-signal matches for score boost
                    existing_candidate, signal_count = seen_full_names[candidate.full_name]
                    seen_full_names[candidate.full_name] = (
                        existing_candidate,
                        signal_count + 1,
                    )

        # Apply multi-signal bonus to discovery scores
        candidates = self._apply_signal_bonuses(seen_full_names)

        elapsed = time.monotonic() - start_time

        return ChannelResult(
            channel=DiscoveryChannel.CODE_SEARCH,
            candidates=candidates,
            total_found=total_count,
            has_more=False,
            elapsed_seconds=elapsed,
        )

    # --- Private helpers ---

    async def _execute_queries(
        self,
        keywords: str,
        language: str | None = None,
        max_candidates: int = 500,
    ) -> tuple[list[RepoCandidate], set[str], int]:
        """Execute code search queries with deduplication.

        Combines keywords with quality signal patterns and deduplicates
        results by full_name.

        Args:
            keywords: Search keywords from the query.
            language: Optional language filter.
            max_candidates: Maximum candidates to collect.

        Returns:
            Tuple of (candidates, seen_full_names, total_count).
        """
        seen_full_names: set[str] = set()
        candidates: list[RepoCandidate] = []
        total_count = 0

        # Query 1: keywords alone (broadest match)
        query_str = self._build_query(keywords, language=language)
        try:
            items, count = await self._client.search(
                endpoint=_CODE_SEARCH_ENDPOINT,
                query=query_str,
                max_pages=_MAX_PAGES_CODE_SEARCH,
                per_page=_PER_PAGE_CODE_SEARCH,
            )
            total_count += count

            for item in items:
                candidate = self._map_item(item)
                if candidate.full_name not in seen_full_names:
                    seen_full_names.add(candidate.full_name)
                    candidates.append(candidate)
        except Exception:
            logger.warning(
                "code_search_keyword_query_failed",
                keywords=keywords,
            )

        # Query 2: keywords + quality signal patterns (quality-filtered)
        if len(candidates) < max_candidates:
            signal_query = self._build_signal_query(keywords, language=language)
            try:
                items, count = await self._client.search(
                    endpoint=_CODE_SEARCH_ENDPOINT,
                    query=signal_query,
                    max_pages=_MAX_PAGES_CODE_SEARCH,
                    per_page=_PER_PAGE_CODE_SEARCH,
                )
                total_count += count

                for item in items:
                    candidate = self._map_item(item)
                    if candidate.full_name not in seen_full_names:
                        seen_full_names.add(candidate.full_name)
                        candidates.append(candidate)
            except Exception:
                logger.warning(
                    "code_search_signal_query_failed",
                    keywords=keywords,
                )

        return candidates, seen_full_names, total_count

    def _build_query(
        self,
        keywords: str,
        *,
        language: str | None = None,
    ) -> str:
        """Build a code search query string.

        Args:
            keywords: Search keywords.
            language: Optional language qualifier.

        Returns:
            GitHub code search query string.
        """
        parts: list[str] = [keywords]

        if language:
            parts.append(f"language:{language}")

        return " ".join(parts)

    def _build_signal_query(
        self,
        keywords: str,
        *,
        language: str | None = None,
    ) -> str:
        """Build a query combining keywords with quality signal patterns.

        Uses the first pattern from each category to keep the query
        concise while covering all quality dimensions.

        Args:
            keywords: Search keywords.
            language: Optional language qualifier.

        Returns:
            Combined code search query string.
        """
        parts: list[str] = [keywords]

        # Pick one representative pattern per category
        for patterns in QUALITY_SIGNAL_PATTERNS.values():
            if patterns:
                parts.append(patterns[0])

        if language:
            parts.append(f"language:{language}")

        return " ".join(parts)

    @staticmethod
    def _filter_categories(
        signals: list[str] | None,
    ) -> dict[str, list[str]]:
        """Filter quality signal patterns by requested signal categories.

        Args:
            signals: Categories to include, or None for all.

        Returns:
            Filtered subset of QUALITY_SIGNAL_PATTERNS.
        """
        if signals is None:
            return dict(QUALITY_SIGNAL_PATTERNS)

        return {
            cat: patterns for cat, patterns in QUALITY_SIGNAL_PATTERNS.items() if cat in signals
        }

    @staticmethod
    def _map_item(item: dict[str, Any]) -> RepoCandidate:
        """Convert a code search result item to RepoCandidate.

        Code search results have a `repository` sub-object instead of
        top-level repo fields (unlike /search/repositories).

        Args:
            item: Single item dict from /search/code response.

        Returns:
            RepoCandidate with fields populated from the repository sub-object.
        """
        repo = item.get("repository", {})
        full_name = repo.get("full_name", "")
        html_url = repo.get("html_url", f"https://github.com/{full_name}")
        api_url = repo.get("url", f"https://api.github.com/repos/{full_name}")
        owner = full_name.split("/")[0] if "/" in full_name else full_name

        # Normalize score from GitHub code search
        raw_score = item.get("score", 1.0)
        discovery_score = min(raw_score / 100.0, 1.0)
        # Ensure a minimum base score for code-search-discovered repos
        discovery_score = max(discovery_score, _BASE_DISCOVERY_SCORE)

        now = datetime.now(UTC)

        return RepoCandidate(
            full_name=full_name,
            url=html_url,
            html_url=html_url,
            api_url=api_url,
            description=repo.get("description") or "",
            language=repo.get("language"),
            topics=repo.get("topics") or [],
            stars=repo.get("stargazers_count", 0),
            forks_count=repo.get("forks_count", 0),
            open_issues_count=repo.get("open_issues_count", 0),
            size_kb=repo.get("size", 0),
            license_info=repo.get("license"),
            default_branch=repo.get("default_branch", "main"),
            archived=repo.get("archived", False),
            disabled=repo.get("disabled", False),
            created_at=repo.get("created_at", now),
            updated_at=repo.get("updated_at", now),
            pushed_at=repo.get("pushed_at"),
            owner_login=owner,
            source_channel=DiscoveryChannel.CODE_SEARCH,
            discovery_score=discovery_score,
        )

    @staticmethod
    def _apply_signal_bonuses(
        seen: dict[str, tuple[RepoCandidate, int]],
    ) -> list[RepoCandidate]:
        """Apply multi-signal discovery score bonuses.

        Repos matching multiple signal categories get a higher score.

        Args:
            seen: Mapping of full_name to (candidate, signal_count).

        Returns:
            List of candidates with updated discovery scores.
        """
        results: list[RepoCandidate] = []
        for candidate, signal_count in seen.values():
            if signal_count > 1:
                bonus = min(
                    (signal_count - 1) * _MULTI_SIGNAL_BONUS,
                    0.5,  # Cap bonus at 0.5
                )
                new_score = min(candidate.discovery_score + bonus, 1.0)
                # Create updated candidate (model_copy_update for immutability)
                updated = candidate.model_copy(
                    update={"discovery_score": new_score},
                )
                results.append(updated)
            else:
                results.append(candidate)
        return results
