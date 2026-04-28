"""Tests for SeedExpansion — seed-based candidate pool expansion.

TDD Red phase: test the full contract of SeedExpansion including
URL parsing, org-based expansion, contributor-based expansion,
strategy selection, error handling, and deduplication.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from github_discovery.discovery.seed_expansion import SeedExpansion
from github_discovery.discovery.types import ChannelResult
from github_discovery.models.enums import DiscoveryChannel

# --- Helpers ---


def _make_repo_json(
    full_name: str,
    *,
    fork: bool = False,
    updated_at: str = "2024-12-01T00:00:00Z",
    stargazers_count: int = 100,
    language: str | None = "Python",
) -> dict[str, object]:
    """Build a minimal GitHub repo JSON object for testing."""
    owner = full_name.split("/", maxsplit=1)[0]
    return {
        "full_name": full_name,
        "html_url": f"https://github.com/{full_name}",
        "url": f"https://api.github.com/repos/{full_name}",
        "description": f"Repo {full_name}",
        "language": language,
        "stargazers_count": stargazers_count,
        "forks_count": 10,
        "fork": fork,
        "created_at": "2022-01-01T00:00:00Z",
        "updated_at": updated_at,
        "pushed_at": updated_at,
        "owner": {"login": owner, "type": "Organization"},
        "default_branch": "main",
        "archived": False,
        "disabled": False,
        "open_issues_count": 5,
        "topics": [],
        "size": 1000,
        "has_issues": True,
        "has_wiki": True,
    }


def _make_contributor_json(login: str, contributions: int) -> dict[str, object]:
    """Build a minimal contributor JSON object."""
    return {"login": login, "contributions": contributions, "type": "User"}


# --- _parse_owner_repo ---


class TestParseOwnerRepo:
    """Tests for the URL parsing helper."""

    def test_parse_owner_repo_from_url(self) -> None:
        """Standard https://github.com/owner/repo → (owner, repo)."""
        result = SeedExpansion._parse_owner_repo("https://github.com/pallets/flask")
        assert result == ("pallets", "flask")

    def test_parse_owner_repo_from_url_trailing_slash(self) -> None:
        """URL with trailing slash → (owner, repo)."""
        result = SeedExpansion._parse_owner_repo("https://github.com/pallets/flask/")
        assert result == ("pallets", "flask")

    def test_parse_owner_repo_from_api_url(self) -> None:
        """API URL → (owner, repo)."""
        result = SeedExpansion._parse_owner_repo(
            "https://api.github.com/repos/pallets/flask",
        )
        assert result == ("pallets", "flask")

    def test_parse_owner_repo_from_short_form(self) -> None:
        """Short form owner/repo → (owner, repo)."""
        result = SeedExpansion._parse_owner_repo("pallets/flask")
        assert result == ("pallets", "flask")

    def test_parse_owner_repo_invalid_url(self) -> None:
        """Invalid URL → returns None."""
        result = SeedExpansion._parse_owner_repo("not-a-valid-url")
        assert result is None

    def test_parse_owner_repo_empty_string(self) -> None:
        """Empty string → returns None."""
        result = SeedExpansion._parse_owner_repo("")
        assert result is None

    def test_parse_owner_repo_with_sub_path(self) -> None:
        """URL with sub-path /owner/repo/issues → (owner, repo)."""
        result = SeedExpansion._parse_owner_repo(
            "https://github.com/pallets/flask/issues/1",
        )
        assert result == ("pallets", "flask")


# --- expand_by_org ---


class TestExpandByOrg:
    """Tests for org-based seed expansion."""

    async def test_expand_by_org_finds_same_org_repos(self) -> None:
        """Mock org repos → ChannelResult with candidates."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        org_repos = [
            _make_repo_json("pallets/flask"),
            _make_repo_json("pallets/werkzeug"),
            _make_repo_json("pallets/click"),
        ]
        rest_client.get_all_pages = AsyncMock(return_value=org_repos)

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand_by_org(
            seed_urls=["https://github.com/pallets/jinja"],
        )

        assert isinstance(result, ChannelResult)
        assert result.channel == DiscoveryChannel.SEED_EXPANSION
        assert len(result.candidates) == 3
        names = {c.full_name for c in result.candidates}
        assert "pallets/flask" in names
        assert "pallets/werkzeug" in names
        assert "pallets/click" in names

    async def test_expand_by_org_fallback_to_user(self) -> None:
        """Mock org 404 → tries user endpoint → works."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        # get_json for org endpoint raises 404 (simulated as exception)
        # get_all_pages for user endpoint succeeds
        call_count = 0

        async def _get_all_pages_side_effect(
            url: str,
            **kwargs: object,
        ) -> list[dict[str, object]]:
            nonlocal call_count
            call_count += 1
            if "/orgs/" in url:
                raise Exception("404 Not Found")
            if "/users/" in url:
                return [_make_repo_json("user/personal-repo")]
            return []

        rest_client.get_all_pages = AsyncMock(
            side_effect=_get_all_pages_side_effect,
        )

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand_by_org(
            seed_urls=["https://github.com/user/repo"],
        )

        assert len(result.candidates) >= 1
        assert result.candidates[0].full_name == "user/personal-repo"

    async def test_expand_by_org_excludes_seed_repos(self) -> None:
        """Seed URLs excluded from results."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        org_repos = [
            _make_repo_json("pallets/flask"),
            _make_repo_json("pallets/jinja"),  # seed — should be excluded
            _make_repo_json("pallets/click"),
        ]
        rest_client.get_all_pages = AsyncMock(return_value=org_repos)

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand_by_org(
            seed_urls=["https://github.com/pallets/jinja"],
        )

        names = {c.full_name for c in result.candidates}
        assert "pallets/jinja" not in names
        assert "pallets/flask" in names

    async def test_expand_by_org_respects_max_per_org(self) -> None:
        """Returns at most max_per_org repos."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        org_repos = [_make_repo_json(f"pallets/repo{i}") for i in range(30)]
        rest_client.get_all_pages = AsyncMock(return_value=org_repos)

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand_by_org(
            seed_urls=["https://github.com/pallets/seed"],
            max_per_org=5,
        )

        assert len(result.candidates) <= 5

    async def test_expand_by_org_deduplicates_across_seeds(self) -> None:
        """Two seed URLs from same org → deduped results."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        org_repos = [
            _make_repo_json("pallets/flask"),
            _make_repo_json("pallets/click"),
        ]
        rest_client.get_all_pages = AsyncMock(return_value=org_repos)

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand_by_org(
            seed_urls=[
                "https://github.com/pallets/jinja",
                "https://github.com/pallets/werkzeug",
            ],
        )

        # Same org, so same repos returned twice, but deduped
        names = [c.full_name for c in result.candidates]
        assert len(names) == len(set(names))  # no duplicates

    async def test_expand_by_org_discovery_score(self) -> None:
        """Candidates have correct discovery_score and source_channel."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        rest_client.get_all_pages = AsyncMock(
            return_value=[_make_repo_json("pallets/flask")],
        )

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand_by_org(
            seed_urls=["https://github.com/pallets/jinja"],
        )

        assert len(result.candidates) == 1
        assert result.candidates[0].discovery_score == 0.65
        assert result.candidates[0].source_channel == DiscoveryChannel.SEED_EXPANSION


# --- expand_by_contributors ---


class TestExpandByContributors:
    """Tests for contributor-based seed expansion."""

    async def test_expand_by_contributors_finds_repos(self) -> None:
        """Mock contributors + user repos → candidates."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        contributors = [
            _make_contributor_json("user1", 100),
            _make_contributor_json("user2", 50),
        ]
        user_repos = [
            _make_repo_json("user1/cool-project"),
            _make_repo_json("user1/another-project"),
        ]

        async def _get_all_pages(url: str, **kwargs: object) -> list[dict[str, object]]:
            if "/contributors" in url:
                return contributors
            if "/users/user1/repos" in url:
                return user_repos
            if "/users/user2/repos" in url:
                return [_make_repo_json("user2/repo-alpha")]
            return []

        rest_client.get_all_pages = AsyncMock(side_effect=_get_all_pages)

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand_by_contributors(
            seed_urls=["https://github.com/pallets/flask"],
        )

        assert isinstance(result, ChannelResult)
        assert result.channel == DiscoveryChannel.SEED_EXPANSION
        assert len(result.candidates) >= 1
        names = {c.full_name for c in result.candidates}
        assert "user1/cool-project" in names

    async def test_expand_by_contributors_excludes_forks(self) -> None:
        """Contributor's forked repos excluded."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        contributors = [_make_contributor_json("user1", 100)]

        async def _get_all_pages(url: str, **kwargs: object) -> list[dict[str, object]]:
            if "/contributors" in url:
                return contributors
            if "/users/user1/repos" in url:
                return [
                    _make_repo_json("user1/own-project"),
                    _make_repo_json("user1/forked-project", fork=True),
                ]
            return []

        rest_client.get_all_pages = AsyncMock(side_effect=_get_all_pages)

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand_by_contributors(
            seed_urls=["https://github.com/pallets/flask"],
        )

        names = {c.full_name for c in result.candidates}
        assert "user1/own-project" in names
        assert "user1/forked-project" not in names

    async def test_expand_by_contributors_limits_per_user(self) -> None:
        """Respects max_repos_per_contributor."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        contributors = [_make_contributor_json("user1", 100)]

        async def _get_all_pages(url: str, **kwargs: object) -> list[dict[str, object]]:
            if "/contributors" in url:
                return contributors
            if "/users/user1/repos" in url:
                return [_make_repo_json(f"user1/repo{i}") for i in range(20)]
            return []

        rest_client.get_all_pages = AsyncMock(side_effect=_get_all_pages)

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand_by_contributors(
            seed_urls=["https://github.com/pallets/flask"],
            max_repos_per_contributor=3,
        )

        assert len(result.candidates) <= 3

    async def test_expand_by_contributors_limits_contributors(self) -> None:
        """Respects max_contributors parameter."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        contributors = [_make_contributor_json(f"user{i}", 100 - i) for i in range(20)]

        async def _get_all_pages(url: str, **kwargs: object) -> list[dict[str, object]]:
            if "/contributors" in url:
                return contributors
            if "/users/" in url and "/repos" in url:
                return [_make_repo_json("some/repo")]
            return []

        rest_client.get_all_pages = AsyncMock(side_effect=_get_all_pages)

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand_by_contributors(
            seed_urls=["https://github.com/pallets/flask"],
            max_contributors=5,
        )

        # At most 5 contributors, limited repos per contributor
        assert len(result.candidates) <= 5

    async def test_expand_by_contributors_excludes_seed_repos(self) -> None:
        """Seed repos are excluded from contributor results."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        contributors = [_make_contributor_json("user1", 100)]

        async def _get_all_pages(url: str, **kwargs: object) -> list[dict[str, object]]:
            if "/contributors" in url:
                return contributors
            if "/users/user1/repos" in url:
                return [
                    _make_repo_json("pallets/flask"),  # seed — excluded
                    _make_repo_json("user1/own-project"),
                ]
            return []

        rest_client.get_all_pages = AsyncMock(side_effect=_get_all_pages)

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand_by_contributors(
            seed_urls=["https://github.com/pallets/flask"],
        )

        names = {c.full_name for c in result.candidates}
        assert "pallets/flask" not in names
        assert "user1/own-project" in names

    async def test_expand_by_contributors_discovery_score(self) -> None:
        """Contributor candidates have discovery_score=0.55 (weaker than org 0.65)."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        contributors = [_make_contributor_json("user1", 100)]

        async def _get_all_pages(url: str, **kwargs: object) -> list[dict[str, object]]:
            if "/contributors" in url:
                return contributors
            if "/users/user1/repos" in url:
                return [_make_repo_json("user1/project-x")]
            return []

        rest_client.get_all_pages = AsyncMock(side_effect=_get_all_pages)

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand_by_contributors(
            seed_urls=["https://github.com/org/seed-repo"],
        )

        assert len(result.candidates) == 1
        assert result.candidates[0].discovery_score == 0.55
        assert result.candidates[0].source_channel == DiscoveryChannel.SEED_EXPANSION


# --- expand ---


class TestExpand:
    """Tests for the top-level expand method."""

    async def test_expand_multiple_strategies(self) -> None:
        """Both org + contributors → combined, deduped result."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        async def _get_all_pages(url: str, **kwargs: object) -> list[dict[str, object]]:
            if "/orgs/" in url and "/repos" in url:
                return [_make_repo_json("pallets/werkzeug")]
            if "/users/" in url and "/repos" in url:
                return [_make_repo_json("contrib1/project")]
            if "/contributors" in url:
                return [_make_contributor_json("contrib1", 100)]
            return []

        rest_client.get_all_pages = AsyncMock(side_effect=_get_all_pages)

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand(
            seed_urls=["https://github.com/pallets/flask"],
        )

        assert isinstance(result, ChannelResult)
        assert result.channel == DiscoveryChannel.SEED_EXPANSION
        assert len(result.candidates) >= 2

    async def test_expand_custom_strategies(self) -> None:
        """Only 'org' strategy → only org expansion."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        rest_client.get_all_pages = AsyncMock(
            return_value=[_make_repo_json("pallets/werkzeug")],
        )

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand(
            seed_urls=["https://github.com/pallets/flask"],
            strategies=["org"],
        )

        assert isinstance(result, ChannelResult)
        assert len(result.candidates) >= 1
        # Contributors endpoint should NOT have been called
        for call_args in rest_client.get_all_pages.call_args_list:
            url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
            assert "/contributors" not in str(url)

    async def test_expand_handles_api_errors(self) -> None:
        """Mock 404 for org → empty result, no exception."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        rest_client.get_all_pages = AsyncMock(side_effect=Exception("404 Not Found"))

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand(
            seed_urls=["https://github.com/nonexistent/repo"],
        )

        assert isinstance(result, ChannelResult)
        # Should not raise, just return empty or partial
        assert result.channel == DiscoveryChannel.SEED_EXPANSION

    async def test_expand_deduplicates_across_strategies(self) -> None:
        """Same repo from org + contributor → 1 candidate."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        async def _get_all_pages(url: str, **kwargs: object) -> list[dict[str, object]]:
            if "/orgs/" in url and "/repos" in url:
                return [_make_repo_json("pallets/shared-repo")]
            if "/users/" in url and "/repos" in url:
                return [_make_repo_json("pallets/shared-repo")]  # duplicate
            if "/contributors" in url:
                return [_make_contributor_json("pallets-member", 100)]
            return []

        rest_client.get_all_pages = AsyncMock(side_effect=_get_all_pages)

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand(
            seed_urls=["https://github.com/pallets/flask"],
        )

        names = [c.full_name for c in result.candidates]
        assert names.count("pallets/shared-repo") == 1

    async def test_expand_empty_seed_urls(self) -> None:
        """Empty seed_urls → empty result."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand(seed_urls=[])

        assert isinstance(result, ChannelResult)
        assert result.candidates == []
        assert result.total_found == 0

    async def test_expand_unknown_strategy_ignored(self) -> None:
        """Unknown strategy name → ignored, no error."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand(
            seed_urls=["https://github.com/pallets/flask"],
            strategies=["unknown"],
        )

        assert isinstance(result, ChannelResult)
        assert result.candidates == []
        rest_client.get_all_pages.assert_not_called()


# --- auto_discover_seeds ---


class TestAutoDiscoverSeeds:
    """Tests for the auto-discover seeds method (Wave H6)."""

    async def test_auto_discover_seeds_returns_urls(self) -> None:
        """GitHub search returns top repo URLs."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        search_items = [
            {"html_url": "https://github.com/pallets/flask"},
            {"html_url": "https://github.com/pallets/jinja"},
            {"html_url": "https://github.com/pallets/werkzeug"},
        ]
        rest_client.search = AsyncMock(return_value=(search_items, 3))

        expansion = SeedExpansion(rest_client, graphql_client)
        seeds = await expansion.auto_discover_seeds("python web framework")

        assert len(seeds) == 3
        assert "https://github.com/pallets/flask" in seeds
        rest_client.search.assert_awaited_once_with(
            "/search/repositories",
            "python web framework",
            sort="stars",
            order="desc",
            max_pages=1,
            per_page=3,
        )

    async def test_auto_discover_seeds_respects_max_seeds(self) -> None:
        """Only returns max_seeds URLs."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        search_items = [
            {"html_url": "https://github.com/a/1"},
            {"html_url": "https://github.com/b/2"},
            {"html_url": "https://github.com/c/3"},
            {"html_url": "https://github.com/d/4"},
            {"html_url": "https://github.com/e/5"},
        ]
        rest_client.search = AsyncMock(return_value=(search_items, 5))

        expansion = SeedExpansion(rest_client, graphql_client)
        seeds = await expansion.auto_discover_seeds("test query", max_seeds=2)

        assert len(seeds) == 2

    async def test_auto_discover_seeds_filters_empty_urls(self) -> None:
        """Items without html_url are filtered out."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        search_items = [
            {"html_url": "https://github.com/a/1"},
            {"html_url": ""},
            {"no_url": True},
        ]
        rest_client.search = AsyncMock(return_value=(search_items, 3))

        expansion = SeedExpansion(rest_client, graphql_client)
        seeds = await expansion.auto_discover_seeds("test query")

        assert len(seeds) == 1
        assert seeds[0] == "https://github.com/a/1"

    async def test_auto_discover_seeds_returns_empty_on_error(self) -> None:
        """API failure returns empty list, no exception raised."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        rest_client.search = AsyncMock(side_effect=Exception("API error"))

        expansion = SeedExpansion(rest_client, graphql_client)
        seeds = await expansion.auto_discover_seeds("test query")

        assert seeds == []

    async def test_auto_discover_seeds_empty_results(self) -> None:
        """Empty search results returns empty list."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        rest_client.search = AsyncMock(return_value=([], 0))

        expansion = SeedExpansion(rest_client, graphql_client)
        seeds = await expansion.auto_discover_seeds("obscure nonexistent topic")

        assert seeds == []


# --- expand with auto_seed_query (Wave H6) ---


class TestExpandAutoSeed:
    """Tests for expand() with auto_seed_query parameter."""

    async def test_expand_auto_seed_discovers_and_expands(self) -> None:
        """Empty seed_urls + auto_seed_query → auto-discover seeds, then expand."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        # auto_discover_seeds returns seed URLs
        search_items = [
            {"html_url": "https://github.com/pallets/flask"},
        ]
        rest_client.search = AsyncMock(return_value=(search_items, 1))

        # org expansion returns repos
        org_repos = [_make_repo_json("pallets/werkzeug")]
        rest_client.get_all_pages = AsyncMock(return_value=org_repos)

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand(
            seed_urls=[],
            auto_seed_query="python web framework",
        )

        assert isinstance(result, ChannelResult)
        assert result.channel == DiscoveryChannel.SEED_EXPANSION
        # Should have called search to auto-discover seeds
        rest_client.search.assert_awaited_once()
        # Should have expanded from the discovered seed
        assert len(result.candidates) >= 1
        names = {c.full_name for c in result.candidates}
        assert "pallets/werkzeug" in names

    async def test_expand_auto_seed_empty_query_ignored(self) -> None:
        """auto_seed_query=None with empty seed_urls → empty result (no auto-discovery)."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand(
            seed_urls=[],
            auto_seed_query=None,
        )

        assert result.candidates == []
        rest_client.search.assert_not_called()

    async def test_expand_auto_seed_no_results_returns_empty(self) -> None:
        """Auto-discover finds nothing → empty result, no crash."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        rest_client.search = AsyncMock(return_value=([], 0))

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand(
            seed_urls=[],
            auto_seed_query="obscure topic",
        )

        assert result.candidates == []
        rest_client.search.assert_awaited_once()

    async def test_expand_explicit_seeds_ignore_auto_seed_query(self) -> None:
        """When seed_urls is provided, auto_seed_query is ignored."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        rest_client.get_all_pages = AsyncMock(
            return_value=[_make_repo_json("pallets/werkzeug")],
        )

        expansion = SeedExpansion(rest_client, graphql_client)
        result = await expansion.expand(
            seed_urls=["https://github.com/pallets/flask"],
            auto_seed_query="should be ignored",
        )

        # Should NOT have called search (seeds were provided explicitly)
        rest_client.search.assert_not_called()
        assert len(result.candidates) >= 1
