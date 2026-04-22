"""Shared fixtures for discovery unit tests."""

from __future__ import annotations

import pytest

from github_discovery.config import GitHubSettings

# --- Sample API responses ---


@pytest.fixture
def github_settings() -> GitHubSettings:
    """GitHub settings with test token and API URL."""
    return GitHubSettings(
        token="ghp_test_token_12345",  # noqa: S106
        api_base_url="https://api.github.com",
        request_timeout=10,
    )


@pytest.fixture
def sample_repo_json() -> dict[str, object]:
    """Sample GitHub API /repos/{owner}/{repo} JSON response."""
    return {
        "full_name": "python/cpython",
        "url": "https://api.github.com/repos/python/cpython",
        "html_url": "https://github.com/python/cpython",
        "clone_url": "https://github.com/python/cpython.git",
        "description": "The Python programming language",
        "language": "Python",
        "topics": ["python", "c", "interpreter"],
        "stargazers_count": 60000,
        "forks_count": 15000,
        "open_issues_count": 1000,
        "size": 500000,
        "default_branch": "main",
        "license": {
            "key": "psf-2.0",
            "name": "Python Software Foundation License Version 2",
            "spdx_id": "PSF-2.0",
        },
        "created_at": "2012-01-02T00:00:00Z",
        "updated_at": "2024-12-01T12:00:00Z",
        "pushed_at": "2024-12-15T10:30:00Z",
        "archived": False,
        "disabled": False,
    }


@pytest.fixture
def sample_search_response() -> dict[str, object]:
    """Sample GitHub /search/repositories response with 3 items."""
    return {
        "total_count": 3,
        "incomplete_results": False,
        "items": [
            {
                "full_name": "pallets/flask",
                "html_url": "https://github.com/pallets/flask",
                "url": "https://api.github.com/repos/pallets/flask",
                "clone_url": "https://github.com/pallets/flask.git",
                "description": "The Python micro framework",
                "language": "Python",
                "topics": ["python", "flask", "web"],
                "stargazers_count": 67000,
                "forks_count": 16000,
                "open_issues_count": 10,
                "size": 5000,
                "default_branch": "main",
                "license": {
                    "key": "bsd-3-clause",
                    "name": "BSD 3-Clause",
                    "spdx_id": "BSD-3-Clause",
                },
                "created_at": "2010-04-08T00:00:00Z",
                "updated_at": "2024-11-01T00:00:00Z",
                "pushed_at": "2024-12-01T00:00:00Z",
                "archived": False,
                "disabled": False,
                "score": 15.2,
            },
            {
                "full_name": "fastapi/fastapi",
                "html_url": "https://github.com/fastapi/fastapi",
                "url": "https://api.github.com/repos/fastapi/fastapi",
                "clone_url": "https://github.com/fastapi/fastapi.git",
                "description": "Modern, fast web framework for Python",
                "language": "Python",
                "topics": ["python", "fastapi", "async"],
                "stargazers_count": 75000,
                "forks_count": 6000,
                "open_issues_count": 200,
                "size": 8000,
                "default_branch": "main",
                "license": {"key": "mit", "name": "MIT License", "spdx_id": "MIT"},
                "created_at": "2018-12-01T00:00:00Z",
                "updated_at": "2024-12-01T00:00:00Z",
                "pushed_at": "2024-12-10T00:00:00Z",
                "archived": False,
                "disabled": False,
                "score": 12.1,
            },
            {
                "full_name": "django/django",
                "html_url": "https://github.com/django/django",
                "url": "https://api.github.com/repos/django/django",
                "clone_url": "https://github.com/django/django.git",
                "description": "The Web framework for perfectionists",
                "language": "Python",
                "topics": ["python", "django", "web"],
                "stargazers_count": 78000,
                "forks_count": 31000,
                "open_issues_count": 250,
                "size": 30000,
                "default_branch": "main",
                "license": {
                    "key": "bsd-3-clause",
                    "name": "BSD 3-Clause",
                    "spdx_id": "BSD-3-Clause",
                },
                "created_at": "2012-04-28T00:00:00Z",
                "updated_at": "2024-12-01T00:00:00Z",
                "pushed_at": "2024-12-12T00:00:00Z",
                "archived": False,
                "disabled": False,
                "score": 10.5,
            },
        ],
    }


@pytest.fixture
def sample_code_search_response() -> dict[str, object]:
    """Sample GitHub /search/code response."""
    return {
        "total_count": 2,
        "incomplete_results": False,
        "items": [
            {
                "name": "conftest.py",
                "path": "tests/conftest.py",
                "sha": "abc123",
                "url": "https://api.github.com/repos/user/repo1/contents/tests/conftest.py",
                "html_url": "https://github.com/user/repo1/blob/main/tests/conftest.py",
                "repository": {
                    "full_name": "user/repo1",
                    "url": "https://api.github.com/repos/user/repo1",
                    "html_url": "https://github.com/user/repo1",
                },
                "score": 1.0,
            },
            {
                "name": "conftest.py",
                "path": "test/conftest.py",
                "sha": "def456",
                "url": "https://api.github.com/repos/user/repo2/contents/test/conftest.py",
                "html_url": "https://github.com/user/repo2/blob/main/test/conftest.py",
                "repository": {
                    "full_name": "user/repo2",
                    "url": "https://api.github.com/repos/user/repo2",
                    "html_url": "https://github.com/user/repo2",
                },
                "score": 0.8,
            },
        ],
    }


@pytest.fixture
def sample_graphql_repo_response() -> dict[str, object]:
    """Sample GraphQL repository query response."""
    return {
        "data": {
            "repository": {
                "name": "flask",
                "owner": {"login": "pallets"},
                "url": "https://github.com/pallets/flask",
                "description": "The Python micro framework",
                "stargazerCount": 67000,
                "primaryLanguage": {"name": "Python"},
                "repositoryTopics": {
                    "nodes": [{"topic": {"name": "python"}}],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                },
            },
        },
    }


@pytest.fixture
def sample_pypi_response() -> dict[str, object]:
    """Sample PyPI package JSON API response."""
    return {
        "info": {
            "name": "flask",
            "summary": "A simple framework for building complex web applications.",
            "home_page": "https://github.com/pallets/flask",
            "project_urls": {
                "Source": "https://github.com/pallets/flask",
                "Homepage": "https://palletsprojects.com/p/flask/",
            },
        },
    }


@pytest.fixture
def sample_npm_response() -> dict[str, object]:
    """Sample npm registry search response."""
    return {
        "objects": [
            {
                "package": {
                    "name": "express",
                    "description": "Fast, unopinionated, minimalist web framework",
                    "links": {
                        "repository": "https://github.com/expressjs/express",
                    },
                },
            },
        ],
        "total": 1,
    }


@pytest.fixture
def awesome_readme_content() -> str:
    """Sample awesome list README markdown."""
    return """# Awesome Python

A curated list of awesome Python frameworks and libraries.

## Web Frameworks

- [Flask](https://github.com/pallets/flask) - A microframework
- [Django](https://github.com/django/django) - The web framework for perfectionists
- [FastAPI](https://github.com/fastapi/fastapi) - Modern, fast web framework

## Testing

- [pytest](https://github.com/pytest-dev/pytest) - Testing framework
- [unittest](https://docs.python.org/3/library/unittest.html) - Standard library

## Not a repo link

- [Python docs](https://docs.python.org/) - Official docs (not a repo)
- [Some issue](https://github.com/pallets/flask/issues/1) - Issue link (not a repo)
"""
