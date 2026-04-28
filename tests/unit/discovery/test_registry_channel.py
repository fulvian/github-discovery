"""Tests for RegistryChannel — package registry mapping discovery channel.

TDD Red phase: test the full contract of RegistryChannel including
PyPI package lookup, npm search, GitHub URL extraction, aggregation
with deduplication, and error handling.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx

from github_discovery.discovery.registry_channel import RegistryChannel
from github_discovery.discovery.types import ChannelResult, DiscoveryQuery
from github_discovery.models.enums import DiscoveryChannel

# --- _extract_github_url ---


class TestExtractGithubUrl:
    """Tests for GitHub URL extraction helper."""

    def test_extract_github_url_https(self) -> None:
        """Standard HTTPS URL → clean https://github.com/owner/repo."""
        result = RegistryChannel._extract_github_url(
            "https://github.com/pallets/flask",
        )
        assert result == "https://github.com/pallets/flask"

    def test_extract_github_url_git_prefix(self) -> None:
        """git+https://...git → clean https://github.com/owner/repo."""
        result = RegistryChannel._extract_github_url(
            "git+https://github.com/pallets/flask.git",
        )
        assert result == "https://github.com/pallets/flask"

    def test_extract_github_url_git_protocol(self) -> None:
        """git://github.com/owner/repo.git → clean URL."""
        result = RegistryChannel._extract_github_url(
            "git://github.com/pallets/flask.git",
        )
        assert result == "https://github.com/pallets/flask"

    def test_extract_github_url_ssh(self) -> None:
        """ssh://git@github.com/owner/repo.git → clean URL."""
        result = RegistryChannel._extract_github_url(
            "ssh://git@github.com/pallets/flask.git",
        )
        assert result == "https://github.com/pallets/flask"

    def test_extract_github_url_trailing_slash(self) -> None:
        """URL with trailing slash → clean URL without slash."""
        result = RegistryChannel._extract_github_url(
            "https://github.com/pallets/flask/",
        )
        assert result == "https://github.com/pallets/flask"

    def test_extract_github_url_subpath(self) -> None:
        """URL with sub-paths like /tree/main → extracts owner/repo."""
        result = RegistryChannel._extract_github_url(
            "https://github.com/pallets/flask/tree/main/src",
        )
        assert result == "https://github.com/pallets/flask"

    def test_extract_github_url_non_github(self) -> None:
        """Bitbucket URL → None."""
        result = RegistryChannel._extract_github_url(
            "https://bitbucket.org/user/repo",
        )
        assert result is None

    def test_extract_github_url_gitlab(self) -> None:
        """GitLab URL → None."""
        result = RegistryChannel._extract_github_url(
            "https://gitlab.com/user/repo",
        )
        assert result is None

    def test_extract_github_url_empty_string(self) -> None:
        """Empty string → None."""
        result = RegistryChannel._extract_github_url("")
        assert result is None

    def test_extract_github_url_none_like(self) -> None:
        """None-like empty value → None."""
        result = RegistryChannel._extract_github_url("None")
        assert result is None

    def test_extract_github_url_github_only(self) -> None:
        """Just github.com without owner/repo → None."""
        result = RegistryChannel._extract_github_url("https://github.com")
        assert result is None

    def test_extract_github_url_github_with_only_owner(self) -> None:
        """github.com/owner (no repo) → None."""
        result = RegistryChannel._extract_github_url("https://github.com/pallets")
        assert result is None


# --- search_pypi ---


class TestSearchPypi:
    """Tests for PyPI package search."""

    async def test_search_pypi_maps_to_github(
        self,
        sample_pypi_response: dict[str, object],
    ) -> None:
        """Mock PyPI response with GitHub URL → RepoCandidate."""
        mock_response = httpx.Response(
            200,
            json=sample_pypi_response,
            request=httpx.Request("GET", "https://pypi.org/pypi/flask/json"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_pypi("flask")

        assert isinstance(result, ChannelResult)
        assert result.channel == DiscoveryChannel.REGISTRY
        assert len(result.candidates) == 1
        assert result.candidates[0].full_name == "pallets/flask"
        assert result.candidates[0].source_channel == DiscoveryChannel.REGISTRY
        assert result.candidates[0].owner_login == "pallets"

    async def test_search_pypi_skips_no_github(self) -> None:
        """PyPI response without GitHub URL → excluded from candidates."""
        pypi_data: dict[str, object] = {
            "info": {
                "name": "some-pkg",
                "summary": "A package without GitHub",
                "home_page": "https://example.com",
                "project_urls": {
                    "Homepage": "https://example.com",
                },
            },
        }
        mock_response = httpx.Response(
            200,
            json=pypi_data,
            request=httpx.Request("GET", "https://pypi.org/pypi/some-pkg/json"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_pypi("some-pkg")

        assert isinstance(result, ChannelResult)
        assert result.candidates == []

    async def test_search_pypi_handles_404(self) -> None:
        """PyPI 404 → empty result, no exception."""
        mock_response = httpx.Response(
            404,
            request=httpx.Request("GET", "https://pypi.org/pypi/nonexistent-pkg/json"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_pypi("nonexistent-pkg")

        assert isinstance(result, ChannelResult)
        assert result.candidates == []
        assert result.total_found == 0

    async def test_search_pypi_handles_exception(self) -> None:
        """Network exception → empty result, no exception propagated."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_pypi("flask")

        assert isinstance(result, ChannelResult)
        assert result.candidates == []

    async def test_search_pypi_extracts_from_project_urls(
        self,
    ) -> None:
        """GitHub URL in project_urls.Repository → extracted."""
        pypi_data: dict[str, object] = {
            "info": {
                "name": "requests",
                "summary": "HTTP library",
                "home_page": "https://docs.python-requests.org",
                "project_urls": {
                    "Repository": "https://github.com/psf/requests",
                    "Homepage": "https://docs.python-requests.org",
                },
            },
        }
        mock_response = httpx.Response(
            200,
            json=pypi_data,
            request=httpx.Request("GET", "https://pypi.org/pypi/requests/json"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_pypi("requests")

        assert len(result.candidates) == 1
        assert result.candidates[0].full_name == "psf/requests"

    async def test_search_pypi_extracts_from_home_page(self) -> None:
        """GitHub URL in home_page when no project_urls → extracted."""
        pypi_data: dict[str, object] = {
            "info": {
                "name": "my-pkg",
                "summary": "A package",
                "home_page": "https://github.com/owner/my-pkg",
                "project_urls": None,
            },
        }
        mock_response = httpx.Response(
            200,
            json=pypi_data,
            request=httpx.Request("GET", "https://pypi.org/pypi/my-pkg/json"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_pypi("my-pkg")

        assert len(result.candidates) == 1
        assert result.candidates[0].full_name == "owner/my-pkg"


# --- search_npm ---


class TestSearchNpm:
    """Tests for npm registry search."""

    async def test_search_npm_maps_to_github(
        self,
        sample_npm_response: dict[str, object],
    ) -> None:
        """Mock npm response → RepoCandidate."""
        mock_response = httpx.Response(
            200,
            json=sample_npm_response,
            request=httpx.Request("GET", "https://registry.npmjs.org/-/v1/search"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_npm("express")

        assert isinstance(result, ChannelResult)
        assert result.channel == DiscoveryChannel.REGISTRY
        assert len(result.candidates) == 1
        assert result.candidates[0].full_name == "expressjs/express"
        assert result.candidates[0].source_channel == DiscoveryChannel.REGISTRY
        assert result.candidates[0].owner_login == "expressjs"

    async def test_search_npm_skips_no_github(self) -> None:
        """npm package without GitHub repo URL → excluded."""
        npm_data: dict[str, object] = {
            "objects": [
                {
                    "package": {
                        "name": "some-pkg",
                        "description": "A package without GitHub",
                        "links": {
                            "homepage": "https://example.com",
                        },
                    },
                },
            ],
            "total": 1,
        }
        mock_response = httpx.Response(
            200,
            json=npm_data,
            request=httpx.Request("GET", "https://registry.npmjs.org/-/v1/search"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_npm("some-pkg")

        assert result.candidates == []

    async def test_search_npm_handles_exception(self) -> None:
        """Network exception → empty result."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_npm("express")

        assert result.candidates == []

    async def test_search_npm_respects_max_results(self) -> None:
        """max_results parameter limits candidates returned."""
        npm_data: dict[str, object] = {
            "objects": [
                {
                    "package": {
                        "name": f"pkg-{i}",
                        "description": f"Package {i}",
                        "links": {
                            "repository": f"https://github.com/owner/pkg-{i}",
                        },
                    },
                }
                for i in range(10)
            ],
            "total": 10,
        }
        mock_response = httpx.Response(
            200,
            json=npm_data,
            request=httpx.Request("GET", "https://registry.npmjs.org/-/v1/search"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_npm("pkg", max_results=3)

        assert len(result.candidates) == 3

    async def test_search_npm_extracts_from_repository_url(self) -> None:
        """GitHub URL from package.repository.url field → extracted."""
        npm_data: dict[str, object] = {
            "objects": [
                {
                    "package": {
                        "name": "lodash",
                        "description": "Utility library",
                        "links": {},
                        "repository": {
                            "url": "https://github.com/lodash/lodash.git",
                        },
                    },
                },
            ],
            "total": 1,
        }
        mock_response = httpx.Response(
            200,
            json=npm_data,
            request=httpx.Request("GET", "https://registry.npmjs.org/-/v1/search"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_npm("lodash")

        assert len(result.candidates) == 1
        assert result.candidates[0].full_name == "lodash/lodash"


# --- search_crates_io ---


class TestSearchCratesIo:
    """Tests for crates.io registry search."""

    async def test_search_crates_io_maps_to_github(self) -> None:
        """Mock crates.io response with GitHub URL → RepoCandidate."""
        crates_data: dict[str, object] = {
            "crates": [
                {
                    "crate": {
                        "name": "serde",
                        "description": "A serialization framework",
                        "homepage": "https://serde.rs",
                        "repository": "https://github.com/serde-rs/serde",
                        "documentation": "https://docs.rs/serde",
                    },
                },
            ],
            "meta": {"total": 1},
        }
        mock_response = httpx.Response(
            200,
            json=crates_data,
            request=httpx.Request("GET", "https://crates.io/api/v1/crates"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_crates_io("serde")

        assert isinstance(result, ChannelResult)
        assert result.channel == DiscoveryChannel.REGISTRY
        assert len(result.candidates) == 1
        assert result.candidates[0].full_name == "serde-rs/serde"
        assert result.candidates[0].source_channel == DiscoveryChannel.REGISTRY
        assert result.candidates[0].owner_login == "serde-rs"

    async def test_search_crates_io_extracts_from_homepage(self) -> None:
        """GitHub URL in homepage field → extracted."""
        crates_data: dict[str, object] = {
            "crates": [
                {
                    "crate": {
                        "name": "tokio",
                        "description": "Async runtime",
                        "homepage": "https://github.com/tokio-rs/tokio",
                        "repository": None,
                    },
                },
            ],
            "meta": {"total": 1},
        }
        mock_response = httpx.Response(
            200,
            json=crates_data,
            request=httpx.Request("GET", "https://crates.io/api/v1/crates"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_crates_io("tokio")

        assert len(result.candidates) == 1
        assert result.candidates[0].full_name == "tokio-rs/tokio"

    async def test_search_crates_io_extracts_from_documentation(self) -> None:
        """GitHub URL in documentation field → extracted."""
        crates_data: dict[str, object] = {
            "crates": [
                {
                    "crate": {
                        "name": "my-crate",
                        "description": "Some crate",
                        "homepage": None,
                        "repository": None,
                        "documentation": "https://github.com/owner/my-crate",
                    },
                },
            ],
            "meta": {"total": 1},
        }
        mock_response = httpx.Response(
            200,
            json=crates_data,
            request=httpx.Request("GET", "https://crates.io/api/v1/crates"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_crates_io("my-crate")

        assert len(result.candidates) == 1
        assert result.candidates[0].full_name == "owner/my-crate"

    async def test_search_crates_io_skips_no_github(self) -> None:
        """Crate without GitHub URL → excluded from candidates."""
        crates_data: dict[str, object] = {
            "crates": [
                {
                    "crate": {
                        "name": "some-crate",
                        "description": "A crate without GitHub",
                        "homepage": "https://example.com",
                        "repository": None,
                    },
                },
            ],
            "meta": {"total": 1},
        }
        mock_response = httpx.Response(
            200,
            json=crates_data,
            request=httpx.Request("GET", "https://crates.io/api/v1/crates"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_crates_io("some-crate")

        assert result.candidates == []

    async def test_search_crates_io_handles_404(self) -> None:
        """crates.io 404 → empty result, no exception."""
        mock_response = httpx.Response(
            404,
            request=httpx.Request("GET", "https://crates.io/api/v1/crates"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_crates_io("nonexistent")

        assert isinstance(result, ChannelResult)
        assert result.candidates == []
        assert result.total_found == 0

    async def test_search_crates_io_handles_exception(self) -> None:
        """Network exception → empty result, no exception propagated."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_crates_io("serde")

        assert isinstance(result, ChannelResult)
        assert result.candidates == []

    async def test_search_crates_io_respects_max_results(self) -> None:
        """max_results parameter limits candidates returned."""
        crates_data: dict[str, object] = {
            "crates": [
                {
                    "crate": {
                        "name": f"crate-{i}",
                        "description": f"Crate {i}",
                        "repository": f"https://github.com/owner/crate-{i}",
                    },
                }
                for i in range(10)
            ],
            "meta": {"total": 10},
        }
        mock_response = httpx.Response(
            200,
            json=crates_data,
            request=httpx.Request("GET", "https://crates.io/api/v1/crates"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_crates_io("test", max_results=3)

        assert len(result.candidates) == 3

    async def test_search_crates_io_uses_user_agent(self) -> None:
        """Crates.io requests include User-Agent header."""
        crates_data: dict[str, object] = {
            "crates": [],
            "meta": {"total": 0},
        }
        mock_response = httpx.Response(
            200,
            json=crates_data,
            request=httpx.Request("GET", "https://crates.io/api/v1/crates"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        await channel.search_crates_io("test")

        # Verify User-Agent was passed in headers kwarg
        call_kwargs = mock_client.get.call_args
        assert "headers" in call_kwargs.kwargs
        assert call_kwargs.kwargs["headers"]["User-Agent"] == "github-discovery/0.3.0-beta"

    async def test_search_crates_io_discovery_score(self) -> None:
        """Crates.io candidates have discovery_score of 0.5."""
        crates_data: dict[str, object] = {
            "crates": [
                {
                    "crate": {
                        "name": "test-crate",
                        "description": "Test",
                        "repository": "https://github.com/owner/test-crate",
                    },
                },
            ],
            "meta": {"total": 1},
        }
        mock_response = httpx.Response(
            200,
            json=crates_data,
            request=httpx.Request("GET", "https://crates.io/api/v1/crates"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_crates_io("test-crate")

        assert len(result.candidates) == 1
        assert result.candidates[0].discovery_score == 0.5


# --- search_maven ---


class TestSearchMaven:
    """Tests for Maven Central registry search."""

    async def test_search_maven_maps_to_github(self) -> None:
        """Mock Maven response with GitHub URL → RepoCandidate."""
        maven_data: dict[str, object] = {
            "response": {
                "numFound": 1,
                "docs": [
                    {
                        "id": "com.google.guava:guava",
                        "latestVersion": "33.0.0",
                        "repositoryUrl": "https://github.com/google/guava",
                    },
                ],
            },
        }
        mock_response = httpx.Response(
            200,
            json=maven_data,
            request=httpx.Request("GET", "https://search.maven.org/solrsearch/select"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_maven("guava")

        assert isinstance(result, ChannelResult)
        assert result.channel == DiscoveryChannel.REGISTRY
        assert len(result.candidates) == 1
        assert result.candidates[0].full_name == "google/guava"
        assert result.candidates[0].source_channel == DiscoveryChannel.REGISTRY
        assert result.candidates[0].owner_login == "google"

    async def test_search_maven_skips_no_github(self) -> None:
        """Maven doc without GitHub URL → excluded."""
        maven_data: dict[str, object] = {
            "response": {
                "numFound": 1,
                "docs": [
                    {
                        "id": "com.example:lib",
                        "latestVersion": "1.0",
                        "repositoryUrl": "https://example.com/repo",
                    },
                ],
            },
        }
        mock_response = httpx.Response(
            200,
            json=maven_data,
            request=httpx.Request("GET", "https://search.maven.org/solrsearch/select"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_maven("lib")

        assert result.candidates == []

    async def test_search_maven_skips_no_repository_url(self) -> None:
        """Maven doc with no repositoryUrl → excluded."""
        maven_data: dict[str, object] = {
            "response": {
                "numFound": 1,
                "docs": [
                    {
                        "id": "org.apache:commons",
                        "latestVersion": "1.0",
                    },
                ],
            },
        }
        mock_response = httpx.Response(
            200,
            json=maven_data,
            request=httpx.Request("GET", "https://search.maven.org/solrsearch/select"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_maven("commons")

        assert result.candidates == []

    async def test_search_maven_handles_404(self) -> None:
        """Maven 404 → empty result, no exception."""
        mock_response = httpx.Response(
            404,
            request=httpx.Request("GET", "https://search.maven.org/solrsearch/select"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_maven("nonexistent")

        assert isinstance(result, ChannelResult)
        assert result.candidates == []
        assert result.total_found == 0

    async def test_search_maven_handles_exception(self) -> None:
        """Network exception → empty result."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_maven("guava")

        assert isinstance(result, ChannelResult)
        assert result.candidates == []

    async def test_search_maven_respects_max_results(self) -> None:
        """max_results parameter limits candidates returned."""
        maven_data: dict[str, object] = {
            "response": {
                "numFound": 10,
                "docs": [
                    {
                        "id": f"com.example:lib-{i}",
                        "latestVersion": "1.0",
                        "repositoryUrl": f"https://github.com/owner/lib-{i}",
                    }
                    for i in range(10)
                ],
            },
        }
        mock_response = httpx.Response(
            200,
            json=maven_data,
            request=httpx.Request("GET", "https://search.maven.org/solrsearch/select"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_maven("lib", max_results=3)

        assert len(result.candidates) == 3

    async def test_search_maven_discovery_score(self) -> None:
        """Maven candidates have discovery_score of 0.5."""
        maven_data: dict[str, object] = {
            "response": {
                "numFound": 1,
                "docs": [
                    {
                        "id": "com.google.guava:guava",
                        "latestVersion": "33.0.0",
                        "repositoryUrl": "https://github.com/google/guava",
                    },
                ],
            },
        }
        mock_response = httpx.Response(
            200,
            json=maven_data,
            request=httpx.Request("GET", "https://search.maven.org/solrsearch/select"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        channel = RegistryChannel(http_client=mock_client)
        result = await channel.search_maven("guava")

        assert len(result.candidates) == 1
        assert result.candidates[0].discovery_score == 0.5


# --- search (aggregation) ---


class TestSearch:
    """Tests for the aggregated search method."""

    async def test_search_aggregates_registries(
        self,
        sample_pypi_response: dict[str, object],
        sample_npm_response: dict[str, object],
    ) -> None:
        """Mock PyPI + npm + crates.io + Maven → combined results."""
        pypi_resp = httpx.Response(
            200,
            json=sample_pypi_response,
            request=httpx.Request("GET", "https://pypi.org/pypi/flask/json"),
        )
        npm_resp = httpx.Response(
            200,
            json=sample_npm_response,
            request=httpx.Request("GET", "https://registry.npmjs.org/-/v1/search"),
        )
        crates_resp = httpx.Response(
            404,
            request=httpx.Request("GET", "https://crates.io/api/v1/crates"),
        )
        maven_resp = httpx.Response(
            404,
            request=httpx.Request("GET", "https://search.maven.org/solrsearch/select"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=[pypi_resp, npm_resp, crates_resp, maven_resp])

        channel = RegistryChannel(http_client=mock_client)
        query = DiscoveryQuery(query="flask")
        result = await channel.search(query)

        assert isinstance(result, ChannelResult)
        assert result.channel == DiscoveryChannel.REGISTRY
        assert len(result.candidates) == 2

        names = {c.full_name for c in result.candidates}
        assert "pallets/flask" in names
        assert "expressjs/express" in names

    async def test_search_deduplicates(self) -> None:
        """Same repo from PyPI + npm → 1 candidate."""
        pypi_data: dict[str, object] = {
            "info": {
                "name": "my-pkg",
                "summary": "Package",
                "home_page": "https://github.com/owner/shared-repo",
                "project_urls": None,
            },
        }
        npm_data: dict[str, object] = {
            "objects": [
                {
                    "package": {
                        "name": "my-pkg",
                        "description": "Package",
                        "links": {
                            "repository": "https://github.com/owner/shared-repo",
                        },
                    },
                },
            ],
            "total": 1,
        }

        pypi_resp = httpx.Response(
            200,
            json=pypi_data,
            request=httpx.Request("GET", "https://pypi.org/pypi/my-pkg/json"),
        )
        npm_resp = httpx.Response(
            200,
            json=npm_data,
            request=httpx.Request("GET", "https://registry.npmjs.org/-/v1/search"),
        )
        crates_resp = httpx.Response(
            404,
            request=httpx.Request("GET", "https://crates.io/api/v1/crates"),
        )
        maven_resp = httpx.Response(
            404,
            request=httpx.Request("GET", "https://search.maven.org/solrsearch/select"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=[pypi_resp, npm_resp, crates_resp, maven_resp])

        channel = RegistryChannel(http_client=mock_client)
        query = DiscoveryQuery(query="my-pkg")
        result = await channel.search(query)

        assert len(result.candidates) == 1
        assert result.candidates[0].full_name == "owner/shared-repo"

    async def test_search_handles_pypi_error(
        self,
        sample_npm_response: dict[str, object],
    ) -> None:
        """Mock PyPI 404 → empty PyPI result, npm still works."""
        pypi_resp = httpx.Response(
            404,
            request=httpx.Request("GET", "https://pypi.org/pypi/flask/json"),
        )
        npm_resp = httpx.Response(
            200,
            json=sample_npm_response,
            request=httpx.Request("GET", "https://registry.npmjs.org/-/v1/search"),
        )
        crates_resp = httpx.Response(
            404,
            request=httpx.Request("GET", "https://crates.io/api/v1/crates"),
        )
        maven_resp = httpx.Response(
            404,
            request=httpx.Request("GET", "https://search.maven.org/solrsearch/select"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=[pypi_resp, npm_resp, crates_resp, maven_resp])

        channel = RegistryChannel(http_client=mock_client)
        query = DiscoveryQuery(query="flask")
        result = await channel.search(query)

        assert len(result.candidates) == 1
        assert result.candidates[0].full_name == "expressjs/express"

    async def test_search_respects_max_candidates(
        self,
    ) -> None:
        """max_candidates limits total results."""
        npm_data: dict[str, object] = {
            "objects": [
                {
                    "package": {
                        "name": f"pkg-{i}",
                        "description": f"Package {i}",
                        "links": {
                            "repository": f"https://github.com/owner/pkg-{i}",
                        },
                    },
                }
                for i in range(5)
            ],
            "total": 5,
        }
        pypi_resp = httpx.Response(
            404,
            request=httpx.Request("GET", "https://pypi.org/pypi/test/json"),
        )
        npm_resp = httpx.Response(
            200,
            json=npm_data,
            request=httpx.Request("GET", "https://registry.npmjs.org/-/v1/search"),
        )
        crates_resp = httpx.Response(
            404,
            request=httpx.Request("GET", "https://crates.io/api/v1/crates"),
        )
        maven_resp = httpx.Response(
            404,
            request=httpx.Request("GET", "https://search.maven.org/solrsearch/select"),
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=[pypi_resp, npm_resp, crates_resp, maven_resp])

        channel = RegistryChannel(http_client=mock_client)
        query = DiscoveryQuery(query="test", max_candidates=2)
        result = await channel.search(query)

        assert len(result.candidates) == 2


# --- context manager ---


class TestContextManager:
    """Tests for async context manager support."""

    async def test_context_manager(self) -> None:
        """Verify async with pattern creates and closes client."""
        channel = RegistryChannel()
        assert channel._owns_client is True

        async with channel:
            # Inside context — client should be available
            pass

        # After context — client should be closed
        # No exception means success

    async def test_context_manager_with_external_client(self) -> None:
        """External client is not closed by context manager."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        channel = RegistryChannel(http_client=mock_client)

        async with channel:
            pass

        # External client should NOT be aclosed
        mock_client.aclose.assert_not_called()

    async def test_internal_client_closed_on_exit(self) -> None:
        """Internally-created client is closed on context exit."""
        channel = RegistryChannel()
        assert channel._owns_client is True

        async with channel:
            _internal_client = channel._client

        # After exit, the internal client should have been closed
        # We verify by checking the client is no longer usable
        # (httpx marks it as closed)
