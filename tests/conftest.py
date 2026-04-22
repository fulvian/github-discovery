"""Shared test fixtures for GitHub Discovery."""

from __future__ import annotations

import pytest

from github_discovery.config import GitHubSettings, Settings


@pytest.fixture
def settings() -> Settings:
    """Provide default application settings for tests."""
    return Settings()


@pytest.fixture
def settings_with_token() -> Settings:
    """Provide settings with a test GitHub token."""
    return Settings(
        github=GitHubSettings(token="ghp_test_token")  # noqa: S106
    )
