"""Shared test fixtures for API tests."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from github_discovery.api.app import create_app
from github_discovery.config import APISettings, Settings


@pytest.fixture
def app() -> Generator[FastAPI]:
    """Create a FastAPI app for testing with in-memory SQLite."""
    settings = Settings(
        api=APISettings(
            job_store_path=":memory:",
        ),
    )
    application = create_app(settings)
    yield application


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient]:
    """Create a TestClient wrapping the test app (triggers lifespan)."""
    with TestClient(app) as c:
        yield c
