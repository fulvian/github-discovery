"""Tests for DependencyChannel — dependency graph traversal channel.

TDD Red phase: test the full contract of DependencyChannel including
URL parsing, SBOM-based dependency discovery, dependent discovery
(MVP fallback), and query-based search.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from github_discovery.discovery.dependency_channel import DependencyChannel
from github_discovery.discovery.types import ChannelResult, DiscoveryQuery
from github_discovery.models.enums import DiscoveryChannel

# --- _parse_owner_repo ---


class TestParseOwnerRepo:
    """Tests for the URL parsing helper."""

    def test_parse_owner_repo_from_url(self) -> None:
        """Standard https://github.com/owner/repo → (owner, repo)."""
        result = DependencyChannel._parse_owner_repo("https://github.com/pallets/flask")
        assert result == ("pallets", "flask")

    def test_parse_owner_repo_from_url_trailing_slash(self) -> None:
        """URL with trailing slash → (owner, repo)."""
        result = DependencyChannel._parse_owner_repo("https://github.com/pallets/flask/")
        assert result == ("pallets", "flask")

    def test_parse_owner_repo_from_url_git_suffix(self) -> None:
        """URL ending in .git → (owner, repo) without .git."""
        result = DependencyChannel._parse_owner_repo("https://github.com/pallets/flask.git")
        assert result == ("pallets", "flask")

    def test_parse_owner_repo_from_api_url(self) -> None:
        """API URL https://api.github.com/repos/owner/repo → (owner, repo)."""
        result = DependencyChannel._parse_owner_repo("https://api.github.com/repos/pallets/flask")
        assert result == ("pallets", "flask")

    def test_parse_owner_repo_from_short_form(self) -> None:
        """Short form owner/repo → (owner, repo)."""
        result = DependencyChannel._parse_owner_repo("pallets/flask")
        assert result == ("pallets", "flask")

    def test_parse_owner_repo_invalid_url(self) -> None:
        """Invalid URL → returns None."""
        result = DependencyChannel._parse_owner_repo("not-a-valid-url")
        assert result is None

    def test_parse_owner_repo_empty_string(self) -> None:
        """Empty string → returns None."""
        result = DependencyChannel._parse_owner_repo("")
        assert result is None

    def test_parse_owner_repo_single_name(self) -> None:
        """Single name (no slash) → returns None."""
        result = DependencyChannel._parse_owner_repo("flask")
        assert result is None

    def test_parse_owner_repo_with_sub_path(self) -> None:
        """URL with sub-path /owner/repo/issues → (owner, repo)."""
        result = DependencyChannel._parse_owner_repo(
            "https://github.com/pallets/flask/issues/1",
        )
        assert result == ("pallets", "flask")


# --- discover_dependencies ---


class TestDiscoverDependencies:
    """Tests for SBOM-based dependency discovery."""

    async def test_discover_dependencies_from_seed(self) -> None:
        """Mock SBOM response with GitHub packages → candidates found."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        sbom_response = {
            "sbom": {
                "SPDXID": "SPDXRef-DOCUMENT",
                "packages": [
                    {
                        "SPDXID": "SPDXRef-Package-pip-flask",
                        "name": "flask",
                        "versionInfo": "3.0.0",
                        "externalRefs": [
                            {
                                "referenceCategory": "PACKAGE_MANAGER",
                                "referenceType": "purl",
                                "referenceLocator": "pkg:pip/flask@3.0.0",
                            },
                        ],
                        "sourceInfo": "acr:https://github.com/pallets/flask",
                    },
                    {
                        "SPDXID": "SPDXRef-Package-pip-click",
                        "name": "click",
                        "versionInfo": "8.1.0",
                        "externalRefs": [
                            {
                                "referenceCategory": "PACKAGE_MANAGER",
                                "referenceType": "purl",
                                "referenceLocator": "pkg:pip/click@8.1.0",
                            },
                        ],
                        "sourceInfo": "acr:https://github.com/pallets/click",
                    },
                ],
            },
        }
        rest_client.get_json = AsyncMock(return_value=sbom_response)

        channel = DependencyChannel(rest_client, graphql_client)
        result = await channel.discover_dependencies(
            seed_urls=["https://github.com/pallets/flask"],
        )

        assert isinstance(result, ChannelResult)
        assert result.channel == DiscoveryChannel.DEPENDENCY
        assert len(result.candidates) == 2
        names = {c.full_name for c in result.candidates}
        assert "pallets/flask" in names
        assert "pallets/click" in names

    async def test_discover_dependencies_depth_1(self) -> None:
        """Only direct dependencies are returned (depth 1 = default)."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        sbom_response = {
            "sbom": {
                "SPDXID": "SPDXRef-DOCUMENT",
                "packages": [
                    {
                        "SPDXID": "SPDXRef-Package-pip-jinja2",
                        "name": "jinja2",
                        "versionInfo": "3.1.0",
                        "externalRefs": [],
                        "sourceInfo": "acr:https://github.com/pallets/jinja",
                    },
                ],
            },
        }
        rest_client.get_json = AsyncMock(return_value=sbom_response)

        channel = DependencyChannel(rest_client, graphql_client)
        result = await channel.discover_dependencies(
            seed_urls=["https://github.com/pallets/flask"],
            max_depth=1,
        )

        assert len(result.candidates) == 1
        assert result.candidates[0].full_name == "pallets/jinja"

    async def test_discover_dependencies_skips_non_github(self) -> None:
        """SBOM packages without GitHub URLs → excluded from results."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        sbom_response = {
            "sbom": {
                "SPDXID": "SPDXRef-DOCUMENT",
                "packages": [
                    {
                        "SPDXID": "SPDXRef-Package-pip-flask",
                        "name": "flask",
                        "versionInfo": "3.0.0",
                        "externalRefs": [
                            {
                                "referenceCategory": "PACKAGE_MANAGER",
                                "referenceType": "purl",
                                "referenceLocator": "pkg:pip/flask@3.0.0",
                            },
                        ],
                        "sourceInfo": "acr:https://github.com/pallets/flask",
                    },
                    {
                        "SPDXID": "SPDXRef-Package-pip-openssl",
                        "name": "openssl",
                        "versionInfo": "3.0.0",
                        "externalRefs": [
                            {
                                "referenceCategory": "PACKAGE_MANAGER",
                                "referenceType": "purl",
                                "referenceLocator": "pkg:generic/openssl@3.0.0",
                            },
                        ],
                    },
                ],
            },
        }
        rest_client.get_json = AsyncMock(return_value=sbom_response)

        channel = DependencyChannel(rest_client, graphql_client)
        result = await channel.discover_dependencies(
            seed_urls=["https://github.com/example/project"],
        )

        assert len(result.candidates) == 1
        assert result.candidates[0].full_name == "pallets/flask"

    async def test_discover_dependencies_deduplicates(self) -> None:
        """Same dep from 2 seed repos → 1 candidate."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        sbom_response = {
            "sbom": {
                "SPDXID": "SPDXRef-DOCUMENT",
                "packages": [
                    {
                        "SPDXID": "SPDXRef-Package-pip-click",
                        "name": "click",
                        "versionInfo": "8.1.0",
                        "externalRefs": [],
                        "sourceInfo": "acr:https://github.com/pallets/click",
                    },
                ],
            },
        }
        # Both seed repos return the same SBOM (same dependency)
        rest_client.get_json = AsyncMock(return_value=sbom_response)

        channel = DependencyChannel(rest_client, graphql_client)
        result = await channel.discover_dependencies(
            seed_urls=[
                "https://github.com/pallets/flask",
                "https://github.com/pallets/jinja",
            ],
        )

        assert len(result.candidates) == 1
        assert result.candidates[0].full_name == "pallets/click"

    async def test_discover_dependencies_handles_api_error(self) -> None:
        """Mock exception for SBOM endpoint → empty result (no exception raised)."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        rest_client.get_json = AsyncMock(side_effect=Exception("HTTP 404"))

        channel = DependencyChannel(rest_client, graphql_client)
        result = await channel.discover_dependencies(
            seed_urls=["https://github.com/nonexistent/repo"],
        )

        assert isinstance(result, ChannelResult)
        assert result.candidates == []
        assert result.total_found == 0

    async def test_discover_dependencies_handles_none_response(self) -> None:
        """Mock None response (304 Not Modified) → empty result."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        rest_client.get_json = AsyncMock(return_value=None)

        channel = DependencyChannel(rest_client, graphql_client)
        result = await channel.discover_dependencies(
            seed_urls=["https://github.com/pallets/flask"],
        )

        assert result.candidates == []
        assert result.total_found == 0

    async def test_discover_dependencies_empty_sbom(self) -> None:
        """SBOM with empty packages list → no candidates."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        sbom_response = {
            "sbom": {
                "SPDXID": "SPDXRef-DOCUMENT",
                "packages": [],
            },
        }
        rest_client.get_json = AsyncMock(return_value=sbom_response)

        channel = DependencyChannel(rest_client, graphql_client)
        result = await channel.discover_dependencies(
            seed_urls=["https://github.com/pallets/flask"],
        )

        assert result.candidates == []

    async def test_discover_dependencies_invalid_seed_url(self) -> None:
        """Invalid seed URL → skipped, returns empty for that seed."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        channel = DependencyChannel(rest_client, graphql_client)
        result = await channel.discover_dependencies(
            seed_urls=["not-a-valid-url"],
        )

        assert result.candidates == []
        assert result.total_found == 0

    async def test_discover_dependencies_discovery_score(self) -> None:
        """Candidates have discovery_score reflecting seed quality weighting."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        sbom_response = {
            "sbom": {
                "SPDXID": "SPDXRef-DOCUMENT",
                "packages": [
                    {
                        "SPDXID": "SPDXRef-Package-pip-flask",
                        "name": "flask",
                        "versionInfo": "3.0.0",
                        "externalRefs": [],
                        "sourceInfo": "acr:https://github.com/pallets/flask",
                    },
                ],
            },
        }
        rest_client.get_json = AsyncMock(return_value=sbom_response)

        channel = DependencyChannel(rest_client, graphql_client)
        result = await channel.discover_dependencies(
            seed_urls=["https://github.com/example/project"],
        )

        assert len(result.candidates) == 1
        assert result.candidates[0].discovery_score == 0.7
        assert result.candidates[0].source_channel == DiscoveryChannel.DEPENDENCY


# --- discover_dependents ---


class TestDiscoverDependents:
    """Tests for dependent discovery (MVP fallback)."""

    async def test_discover_dependents_returns_empty(self) -> None:
        """Dependent API not available → empty result with log message."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        channel = DependencyChannel(rest_client, graphql_client)
        result = await channel.discover_dependents(
            seed_urls=["https://github.com/pallets/flask"],
        )

        assert isinstance(result, ChannelResult)
        assert result.channel == DiscoveryChannel.DEPENDENCY
        assert result.candidates == []
        assert result.total_found == 0

    async def test_discover_dependents_max_results_param(self) -> None:
        """Method accepts max_results parameter without error."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        channel = DependencyChannel(rest_client, graphql_client)
        result = await channel.discover_dependents(
            seed_urls=["https://github.com/pallets/flask"],
            max_results=100,
        )

        assert result.candidates == []


# --- search ---


class TestSearch:
    """Tests for the query-based search method."""

    async def test_search_uses_seed_urls(self) -> None:
        """Query with seed_urls → discovers dependencies from seeds."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        sbom_response = {
            "sbom": {
                "SPDXID": "SPDXRef-DOCUMENT",
                "packages": [
                    {
                        "SPDXID": "SPDXRef-Package-pip-click",
                        "name": "click",
                        "versionInfo": "8.1.0",
                        "externalRefs": [],
                        "sourceInfo": "acr:https://github.com/pallets/click",
                    },
                ],
            },
        }
        rest_client.get_json = AsyncMock(return_value=sbom_response)

        channel = DependencyChannel(rest_client, graphql_client)
        query = DiscoveryQuery(
            query="web framework",
            seed_urls=["https://github.com/pallets/flask"],
        )
        result = await channel.search(query)

        assert isinstance(result, ChannelResult)
        assert result.channel == DiscoveryChannel.DEPENDENCY
        assert len(result.candidates) == 1
        assert result.candidates[0].full_name == "pallets/click"

    async def test_search_without_seeds_returns_empty(self) -> None:
        """Query without seeds → empty result (dependency channel needs seeds)."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        channel = DependencyChannel(rest_client, graphql_client)
        query = DiscoveryQuery(query="web framework")
        result = await channel.search(query)

        assert isinstance(result, ChannelResult)
        assert result.candidates == []
        assert result.total_found == 0

    async def test_search_handles_sbom_api_error(self) -> None:
        """Mock 404 for SBOM → empty result (no exception)."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        rest_client.get_json = AsyncMock(side_effect=Exception("HTTP 404"))

        channel = DependencyChannel(rest_client, graphql_client)
        query = DiscoveryQuery(
            query="test",
            seed_urls=["https://github.com/pallets/flask"],
        )
        result = await channel.search(query)

        assert isinstance(result, ChannelResult)
        assert result.candidates == []
        assert result.total_found == 0

    async def test_search_respects_max_candidates(self) -> None:
        """Search truncates candidates to max_candidates."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        sbom_response = {
            "sbom": {
                "SPDXID": "SPDXRef-DOCUMENT",
                "packages": [
                    {
                        "SPDXID": "SPDXRef-Package-pip-a",
                        "name": "a",
                        "versionInfo": "1.0",
                        "externalRefs": [],
                        "sourceInfo": "acr:https://github.com/owner/a",
                    },
                    {
                        "SPDXID": "SPDXRef-Package-pip-b",
                        "name": "b",
                        "versionInfo": "1.0",
                        "externalRefs": [],
                        "sourceInfo": "acr:https://github.com/owner/b",
                    },
                    {
                        "SPDXID": "SPDXRef-Package-pip-c",
                        "name": "c",
                        "versionInfo": "1.0",
                        "externalRefs": [],
                        "sourceInfo": "acr:https://github.com/owner/c",
                    },
                ],
            },
        }
        rest_client.get_json = AsyncMock(return_value=sbom_response)

        channel = DependencyChannel(rest_client, graphql_client)
        query = DiscoveryQuery(
            query="test",
            seed_urls=["https://github.com/owner/project"],
            max_candidates=2,
        )
        result = await channel.search(query)

        assert len(result.candidates) <= 2

    async def test_search_with_empty_seed_urls_list(self) -> None:
        """Query with empty seed_urls list → empty result."""
        rest_client = AsyncMock()
        graphql_client = AsyncMock()

        channel = DependencyChannel(rest_client, graphql_client)
        query = DiscoveryQuery(
            query="test",
            seed_urls=[],
        )
        result = await channel.search(query)

        assert isinstance(result, ChannelResult)
        assert result.candidates == []
        assert result.total_found == 0
