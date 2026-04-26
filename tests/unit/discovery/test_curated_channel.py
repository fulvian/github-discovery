"""Tests for CuratedChannel — awesome lists & curated sources channel.

TDD Red phase: test the full contract of CuratedChannel including
URL extraction from markdown, README parsing, multi-list aggregation,
and query-based search with language mapping.
"""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock

from github_discovery.discovery.curated_channel import CuratedChannel
from github_discovery.discovery.types import ChannelResult, DiscoveryQuery
from github_discovery.models.enums import DiscoveryChannel

# --- extract_github_urls ---


class TestExtractGithubUrls:
    """Tests for the static URL extraction method."""

    def test_extract_github_urls_basic(self) -> None:
        """Markdown link [Flask](https://github.com/pallets/flask) → extracts URL."""
        md = "Check out [Flask](https://github.com/pallets/flask) — a microframework."
        result = CuratedChannel.extract_github_urls(md)
        assert result == ["https://github.com/pallets/flask"]

    def test_extract_github_urls_multiple(self) -> None:
        """Multiple repo links in one document → all extracted."""
        md = (
            "- [Flask](https://github.com/pallets/flask)\n"
            "- [Django](https://github.com/django/django)\n"
            "- [FastAPI](https://github.com/fastapi/fastapi)\n"
        )
        result = CuratedChannel.extract_github_urls(md)
        assert len(result) == 3
        assert "https://github.com/pallets/flask" in result
        assert "https://github.com/django/django" in result
        assert "https://github.com/fastapi/fastapi" in result

    def test_extract_github_urls_ignores_non_repo(self) -> None:
        """Links to /issues, /pull, /blob, /tree → filtered out."""
        md = (
            "- [Issue](https://github.com/pallets/flask/issues/1)\n"
            "- [PR](https://github.com/pallets/flask/pull/42)\n"
            "- [File](https://github.com/pallets/flask/blob/main/setup.py)\n"
            "- [Tree](https://github.com/pallets/flask/tree/main/src)\n"
            "- [Wiki](https://github.com/pallets/flask/wiki)\n"
            "- [Actions](https://github.com/pallets/flask/actions)\n"
            "- [Releases](https://github.com/pallets/flask/releases)\n"
            "- [Compare](https://github.com/pallets/flask/compare/v1...v2)\n"
            "- [Commit](https://github.com/pallets/flask/commit/abc123)\n"
            "- [Archive](https://github.com/pallets/flask/archive/main.zip)\n"
        )
        result = CuratedChannel.extract_github_urls(md)
        assert result == []

    def test_extract_github_urls_ignores_github_com_non_repo(self) -> None:
        """https://github.com (no owner/repo) → ignored."""
        md = "Visit [GitHub](https://github.com) for more info."
        result = CuratedChannel.extract_github_urls(md)
        assert result == []

    def test_extract_github_urls_deduplicates(self) -> None:
        """Same repo URL appears twice → only once in result."""
        md = (
            "- [Flask](https://github.com/pallets/flask)\n"
            "- [Flask again](https://github.com/pallets/flask)\n"
        )
        result = CuratedChannel.extract_github_urls(md)
        assert result == ["https://github.com/pallets/flask"]

    def test_extract_github_urls_handles_bare_urls(self) -> None:
        """Bare https://github.com/owner/repo in text → extracted."""
        md = "Check out https://github.com/pallets/flask for details."
        result = CuratedChannel.extract_github_urls(md)
        assert result == ["https://github.com/pallets/flask"]

    def test_extract_github_urls_ignores_non_github(self) -> None:
        """Non-GitHub URLs → ignored."""
        md = "[Docs](https://docs.python.org/3/library/unittest.html)"
        result = CuratedChannel.extract_github_urls(md)
        assert result == []

    def test_extract_github_urls_ignores_github_enterprise(self) -> None:
        """GitHub Enterprise URLs (non-github.com) → ignored."""
        md = "See https://gitlab.com/owner/repo for details."
        result = CuratedChannel.extract_github_urls(md)
        assert result == []

    def test_extract_github_urls_ignores_fragment_urls(self) -> None:
        """URLs with fragments pointing to non-repo pages → filtered by path."""
        md = "[Readme](https://github.com/owner/repo#readme)"
        result = CuratedChannel.extract_github_urls(md)
        # /owner/repo with fragment is still a valid repo URL (path is /owner/repo)
        assert result == ["https://github.com/owner/repo"]


# --- parse_awesome_list ---


class TestParseAwesomeList:
    """Tests for parsing a single awesome list README."""

    async def test_parse_awesome_list_fetches_readme(
        self,
        awesome_readme_content: str,
    ) -> None:
        """Mock README API (base64 encoded content) → ChannelResult with candidates."""
        client = AsyncMock()
        encoded = base64.b64encode(awesome_readme_content.encode()).decode()
        client.get_json = AsyncMock(
            return_value={
                "content": encoded,
                "encoding": "base64",
            },
        )

        channel = CuratedChannel(client)
        result = await channel.parse_awesome_list(
            "https://github.com/sindresorhus/awesome-python",
        )

        assert isinstance(result, ChannelResult)
        assert result.channel == DiscoveryChannel.AWESOME_LIST
        assert len(result.candidates) == 4  # flask, django, fastapi, pytest
        names = {c.full_name for c in result.candidates}
        assert "pallets/flask" in names
        assert "django/django" in names
        assert "fastapi/fastapi" in names
        assert "pytest-dev/pytest" in names

        # Verify discovery_score is the curated default
        for candidate in result.candidates:
            assert candidate.source_channel == DiscoveryChannel.AWESOME_LIST
            assert candidate.discovery_score == 0.6

    async def test_parse_awesome_list_handles_api_error(self) -> None:
        """Mock 404 / API error → empty result (no exception)."""
        client = AsyncMock()
        client.get_json = AsyncMock(side_effect=Exception("HTTP 404"))

        channel = CuratedChannel(client)
        result = await channel.parse_awesome_list(
            "https://github.com/nonexistent/awesome-list",
        )

        assert isinstance(result, ChannelResult)
        assert result.channel == DiscoveryChannel.AWESOME_LIST
        assert result.candidates == []
        assert result.total_found == 0

    async def test_parse_awesome_list_handles_none_response(self) -> None:
        """Mock None response (304 Not Modified) → empty result."""
        client = AsyncMock()
        client.get_json = AsyncMock(return_value=None)

        channel = CuratedChannel(client)
        result = await channel.parse_awesome_list(
            "https://github.com/sindresorhus/awesome",
        )

        assert isinstance(result, ChannelResult)
        assert result.candidates == []


# --- parse_multiple ---


class TestParseMultiple:
    """Tests for parsing multiple awesome lists with deduplication."""

    async def test_parse_multiple_deduplicates(self) -> None:
        """Same repo in 2 lists → 1 candidate."""
        client = AsyncMock()

        readme_a = "- [Flask](https://github.com/pallets/flask)\n"
        readme_b = "- [Flask](https://github.com/pallets/flask)\n- [Django](https://github.com/django/django)\n"

        encoded_a = base64.b64encode(readme_a.encode()).decode()
        encoded_b = base64.b64encode(readme_b.encode()).decode()

        # get_json is called twice — once per list
        client.get_json = AsyncMock(
            side_effect=[
                {"content": encoded_a, "encoding": "base64"},
                {"content": encoded_b, "encoding": "base64"},
            ],
        )

        channel = CuratedChannel(client)
        result = await channel.parse_multiple(
            [
                "https://github.com/user/awesome-a",
                "https://github.com/user/awesome-b",
            ]
        )

        assert isinstance(result, ChannelResult)
        names = {c.full_name for c in result.candidates}
        assert names == {"pallets/flask", "django/django"}
        assert len(result.candidates) == 2

    async def test_parse_multiple_continues_on_error(self) -> None:
        """One list fails → still returns candidates from the other."""
        client = AsyncMock()

        readme_ok = "- [Flask](https://github.com/pallets/flask)\n"
        encoded_ok = base64.b64encode(readme_ok.encode()).decode()

        client.get_json = AsyncMock(
            side_effect=[
                Exception("HTTP 404"),  # First list fails
                {"content": encoded_ok, "encoding": "base64"},  # Second succeeds
            ],
        )

        channel = CuratedChannel(client)
        result = await channel.parse_multiple(
            [
                "https://github.com/user/broken-list",
                "https://github.com/user/working-list",
            ]
        )

        assert len(result.candidates) == 1
        assert result.candidates[0].full_name == "pallets/flask"


# --- search ---


class TestSearch:
    """Tests for the query-based search method."""

    async def test_search_uses_language_mapping(self) -> None:
        """Query with language='python' → fetches awesome-python list."""
        client = AsyncMock()

        readme = "- [Flask](https://github.com/pallets/flask)\n"
        encoded = base64.b64encode(readme.encode()).decode()
        client.get_json = AsyncMock(
            return_value={"content": encoded, "encoding": "base64"},
        )

        channel = CuratedChannel(client)
        query = DiscoveryQuery(query="web framework", language="python")
        result = await channel.search(query)

        assert isinstance(result, ChannelResult)
        assert len(result.candidates) >= 1
        # Verify the README API was called for the python awesome list
        client.get_json.assert_called()
        call_url = client.get_json.call_args[0][0]
        assert "vinta/awesome-python" in call_url

    async def test_search_returns_empty_when_no_match(self) -> None:
        """Query without language/topic match → empty result (no mega-list fallback)."""
        client = AsyncMock()

        channel = CuratedChannel(client)
        query = DiscoveryQuery(query="something cool")
        result = await channel.search(query)

        assert isinstance(result, ChannelResult)
        assert result.candidates == []
        assert result.total_found == 0
        # No API call should be made when no awesome list matches
        client.get_json.assert_not_called()

    async def test_search_respects_max_candidates(self) -> None:
        """Search truncates candidates to min(max_candidates, _MAX_CURATED_CANDIDATES)."""
        client = AsyncMock()

        readme = (
            "- [A](https://github.com/a/a)\n"
            "- [B](https://github.com/b/b)\n"
            "- [C](https://github.com/c/c)\n"
        )
        encoded = base64.b64encode(readme.encode()).decode()
        client.get_json = AsyncMock(
            return_value={"content": encoded, "encoding": "base64"},
        )

        channel = CuratedChannel(client)
        query = DiscoveryQuery(query="test", language="python", max_candidates=2)
        result = await channel.search(query)

        assert len(result.candidates) <= 2

    async def test_search_caps_at_max_curated_candidates(self) -> None:
        """Curated channel caps results at _MAX_CURATED_CANDIDATES (50)."""
        client = AsyncMock()

        # Generate a README with 100 repos
        lines = [f"- [Repo{i}](https://github.com/user/repo{i})" for i in range(100)]
        readme = "\n".join(lines)
        encoded = base64.b64encode(readme.encode()).decode()
        client.get_json = AsyncMock(
            return_value={"content": encoded, "encoding": "base64"},
        )

        channel = CuratedChannel(client)
        # max_candidates=500 but curated caps at 50
        query = DiscoveryQuery(query="test", language="python", max_candidates=500)
        result = await channel.search(query)

        assert len(result.candidates) == 50
        assert result.has_more is True

    async def test_search_with_topic_match(self) -> None:
        """Query with topic keyword matching _TOPIC_AWESOME_MAP → returns results."""
        client = AsyncMock()

        readme = "- [MLLib](https://github.com/user/mllib)\n"
        encoded = base64.b64encode(readme.encode()).decode()
        client.get_json = AsyncMock(
            return_value={"content": encoded, "encoding": "base64"},
        )

        channel = CuratedChannel(client)
        query = DiscoveryQuery(query="machine learning framework", topics=["machine-learning"])
        result = await channel.search(query)

        assert isinstance(result, ChannelResult)
        assert len(result.candidates) >= 1
        call_url = client.get_json.call_args[0][0]
        assert "josephmisiti/awesome-machine-learning" in call_url

    async def test_search_matches_language_from_query_text(self) -> None:
        """Query 'static analysis python' with no explicit language → matches python list."""
        client = AsyncMock()

        readme = "- [Flask](https://github.com/pallets/flask)\n"
        encoded = base64.b64encode(readme.encode()).decode()
        client.get_json = AsyncMock(
            return_value={"content": encoded, "encoding": "base64"},
        )

        channel = CuratedChannel(client)
        # No language set — "python" is embedded in the query text
        query = DiscoveryQuery(query="static analysis python")
        result = await channel.search(query)

        assert isinstance(result, ChannelResult)
        assert len(result.candidates) >= 1
        # Verify the README API was called for the python awesome list
        call_url = client.get_json.call_args[0][0]
        assert "vinta/awesome-python" in call_url

    async def test_search_matches_topic_from_query_text(self) -> None:
        """Query 'security scanner' with no topics → matches security topic map."""
        client = AsyncMock()

        readme = "- [Gitleaks](https://github.com/gitleaks/gitleaks)\n"
        encoded = base64.b64encode(readme.encode()).decode()
        client.get_json = AsyncMock(
            return_value={"content": encoded, "encoding": "base64"},
        )

        channel = CuratedChannel(client)
        query = DiscoveryQuery(query="security scanner")
        result = await channel.search(query)

        assert isinstance(result, ChannelResult)
        assert len(result.candidates) >= 1
        call_url = client.get_json.call_args[0][0]
        assert "sbilly/awesome-security" in call_url
