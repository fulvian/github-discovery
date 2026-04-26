"""OpenSSF Scorecard API integration for Gate 2.

Queries scorecard.dev for security posture assessment.
Falls back gracefully if API is unavailable or repo
has not been scored.
"""

from __future__ import annotations

import httpx
import structlog

from github_discovery.models.candidate import RepoCandidate  # noqa: TC001
from github_discovery.models.screening import SecurityHygieneScore

logger = structlog.get_logger("github_discovery.screening.scorecard")

_SCORECARD_API_BASE = "https://api.scorecard.dev"
_SCORECARD_ENDPOINT = "/projects/github.com/{owner}/{repo}"
_SCORECARD_TIMEOUT = 30.0
_HTTP_NOT_FOUND = 404


class ScorecardAdapter:
    """OpenSSF Scorecard API integration."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        """Initialize with optional shared HTTP client."""
        self._client = http_client
        self._owns_client = False

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=_SCORECARD_TIMEOUT)
            self._owns_client = True
        return self._client

    async def score(self, candidate: RepoCandidate) -> SecurityHygieneScore:
        """Query Scorecard API and return SecurityHygieneScore."""
        url = (
            f"{_SCORECARD_API_BASE}"
            f"{_SCORECARD_ENDPOINT.format(owner=candidate.owner_name, repo=candidate.repo_name)}"
        )

        try:
            client = await self._get_client()
            response = await client.get(url)

            if response.status_code == _HTTP_NOT_FOUND:
                logger.info("scorecard_not_scored", repo=candidate.full_name)
                return SecurityHygieneScore(
                    value=0.5,
                    confidence=0.0,
                    notes=["Scorecard: repo not scored"],
                )

            response.raise_for_status()
            data = response.json()

            score_raw = float(data.get("score", 0.0))
            value = min(score_raw / 10.0, 1.0)

            checks = data.get("checks", [])
            check_details: dict[str, int] = {
                str(check["name"]): int(check.get("score", 0))
                for check in checks
                if isinstance(check, dict)
            }

            return SecurityHygieneScore(
                value=value,
                confidence=1.0,
                details={
                    "scorecard_score": score_raw,
                    **check_details,
                },
                notes=[f"Scorecard score: {score_raw}/10"],
            )

        except httpx.TimeoutException:
            logger.warning("scorecard_timeout", repo=candidate.full_name)
            return SecurityHygieneScore(
                value=0.5,
                confidence=0.0,
                notes=["Scorecard: request timed out"],
            )
        except Exception as e:
            logger.warning("scorecard_error", repo=candidate.full_name, error=str(e))
            return SecurityHygieneScore(
                value=0.5,
                confidence=0.0,
                notes=[f"Scorecard: {e}"],
            )

    async def close(self) -> None:
        """Close the HTTP client if we own it."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
