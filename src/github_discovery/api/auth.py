"""API key authentication for the REST API."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    request: Request,
    api_key: str | None = Depends(_api_key_header),
) -> None:
    """Verify API key if configured. Skip auth if no key configured.

    When ``settings.api.api_key`` is empty or not set, authentication
    is disabled and all requests are allowed. When configured, the
    ``X-API-Key`` header must match exactly.

    Args:
        request: Incoming HTTP request (used to read settings from app state).
        api_key: API key extracted from the X-API-Key header, or None.

    Raises:
        HTTPException: 401 if the key is configured but missing or incorrect.
    """
    settings = request.app.state.settings
    if not settings.api.api_key:
        return  # Auth disabled

    if api_key != settings.api.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
