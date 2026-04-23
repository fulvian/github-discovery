"""API error handlers — maps domain exceptions to HTTP responses.

Registers exception handlers on a FastAPI app to convert
GitHubDiscoveryError subclasses into structured JSON responses
with appropriate HTTP status codes.
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI  # noqa: TC002
from fastapi.responses import JSONResponse
from starlette.requests import Request  # noqa: TC002

from github_discovery.exceptions import (
    BudgetExceededError,
    ConfigurationError,
    GitHubDiscoveryError,
    HardGateViolationError,
    RateLimitError,
)

logger = structlog.get_logger("github_discovery.api.errors")


def _map_exception_to_status(exc: GitHubDiscoveryError) -> int:
    """Map a domain exception to an appropriate HTTP status code.

    Args:
        exc: The domain exception to map.

    Returns:
        HTTP status code integer.
    """
    if isinstance(exc, HardGateViolationError):
        return 422
    if isinstance(exc, BudgetExceededError | RateLimitError):
        return 429
    if isinstance(exc, ConfigurationError):
        return 500
    return 400


def register_error_handlers(app: FastAPI) -> None:
    """Register error handlers on a FastAPI application.

    Args:
        app: FastAPI app to register handlers on.
    """

    @app.exception_handler(GitHubDiscoveryError)
    async def domain_error_handler(
        request: Request,
        exc: GitHubDiscoveryError,
    ) -> JSONResponse:
        """Handle domain exceptions with structured error responses."""
        status_code = _map_exception_to_status(exc)
        logger.warning(
            "domain_error",
            error_type=type(exc).__name__,
            message=str(exc),
            status_code=status_code,
            context=exc.context,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=status_code,
            content={
                "error": type(exc).__name__,
                "message": str(exc),
                "context": exc.context,
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Handle unexpected exceptions with 500 responses."""
        logger.error(
            "unhandled_error",
            error_type=type(exc).__name__,
            message=str(exc),
            path=request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred",
            },
        )
