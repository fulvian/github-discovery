"""API routes package — aggregates all route modules."""

from __future__ import annotations

from github_discovery.api.routes.assessment import router as assessment_router
from github_discovery.api.routes.discovery import router as discovery_router
from github_discovery.api.routes.export import router as export_router
from github_discovery.api.routes.ranking import router as ranking_router
from github_discovery.api.routes.screening import router as screening_router

__all__ = [
    "assessment_router",
    "discovery_router",
    "export_router",
    "ranking_router",
    "screening_router",
]
