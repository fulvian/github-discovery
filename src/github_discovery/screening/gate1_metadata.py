"""Gate 1 — Metadata screening engine (zero LLM cost).

Orchestrates 7 sub-score checkers using repository metadata from
GitHub API. All checks are zero-cost (API calls only, no LLM,
no clone, no external tools).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, TypeVar

import structlog

from github_discovery.config import ScreeningSettings  # noqa: TC001
from github_discovery.discovery.github_client import GitHubRestClient  # noqa: TC001
from github_discovery.models.candidate import RepoCandidate  # noqa: TC001
from github_discovery.models.screening import (
    CiCdScore,
    DependencyQualityScore,
    HygieneScore,
    MaintenanceScore,
    MetadataScreenResult,
    ReleaseDisciplineScore,
    ReviewPracticeScore,
    SubScore,
    TestFootprintScore,
)
from github_discovery.screening.ci_cd import CiCdDetector
from github_discovery.screening.dependency_quality import DependencyQualityScorer
from github_discovery.screening.hygiene import HygieneChecker
from github_discovery.screening.maintenance import MaintenanceAnalyzer
from github_discovery.screening.practices import PracticesScorer
from github_discovery.screening.release_discipline import ReleaseDisciplineScorer
from github_discovery.screening.test_footprint import TestFootprintAnalyzer
from github_discovery.screening.types import RepoContext

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger("github_discovery.screening.gate1")

_MAX_CONCURRENT = 5

_SubScoreT = TypeVar("_SubScoreT", bound=SubScore)


class Gate1MetadataScreener:
    """Gate 1 — Metadata screening engine (zero LLM cost).

    Orchestrates 7 sub-score checkers using repository metadata
    from GitHub API. All checks are zero-cost (API calls only,
    no LLM, no clone, no external tools).
    """

    def __init__(
        self,
        rest_client: GitHubRestClient,
        settings: ScreeningSettings,
    ) -> None:
        """Initialize with GitHub REST client and screening settings."""
        self._client = rest_client
        self._settings = settings
        self._hygiene = HygieneChecker()
        self._ci_cd = CiCdDetector()
        self._test_footprint = TestFootprintAnalyzer()
        self._release_discipline = ReleaseDisciplineScorer()
        self._dependency_quality = DependencyQualityScorer()
        self._practices = PracticesScorer()
        self._maintenance = MaintenanceAnalyzer()

    async def gather_context(
        self,
        candidate: RepoCandidate,
    ) -> RepoContext:
        """Gather all metadata needed for Gate 1 scoring.

        Makes parallel API calls to collect: repo contents,
        releases, commits, issues, PRs, languages.
        """
        api_base = f"/repos/{candidate.full_name}"
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

        async def _fetch(
            url: str,
            params: dict[str, str | int] | None = None,
        ) -> object:
            async with semaphore:
                try:
                    result = await self._client.get_json(url, params=params)
                    return result or {}
                except Exception:
                    logger.warning("gate1_context_fetch_failed", url=url)
                    return {}

        # Parallel context gathering (6 API calls)
        contents_raw, releases, commits, issues, prs, languages = await asyncio.gather(
            _fetch(f"{api_base}/contents"),
            _fetch(f"{api_base}/releases", params={"per_page": 10}),
            _fetch(f"{api_base}/commits", params={"per_page": 30}),
            _fetch(f"{api_base}/issues", params={"per_page": 30, "state": "all"}),
            _fetch(f"{api_base}/pulls", params={"per_page": 30, "state": "all"}),
            _fetch(f"{api_base}/languages"),
        )

        # Extract filenames from contents listing
        repo_contents: list[str] = []
        if isinstance(contents_raw, list):
            repo_contents = [
                str(item.get("name", "")) for item in contents_raw if isinstance(item, dict)
            ]
        elif isinstance(contents_raw, dict):
            # Single file response
            repo_contents = [str(contents_raw.get("name", ""))]

        return RepoContext(
            candidate=candidate,
            repo_metadata={},  # Already in RepoCandidate from discovery
            repo_contents=repo_contents,
            recent_releases=releases if isinstance(releases, list) else [],
            recent_commits=commits if isinstance(commits, list) else [],
            recent_issues=issues if isinstance(issues, list) else [],
            recent_prs=prs if isinstance(prs, list) else [],
            languages=languages if isinstance(languages, dict) else {},
            topics=candidate.topics,
        )

    async def screen(
        self,
        candidate: RepoCandidate,
        *,
        threshold: float | None = None,
    ) -> MetadataScreenResult:
        """Screen a single candidate through Gate 1."""
        # 1. Gather context
        ctx = await self.gather_context(candidate)

        # 2. Check archived/disabled repos — auto-fail
        if candidate.is_archived_or_disabled:
            return MetadataScreenResult(
                full_name=candidate.full_name,
                commit_sha=candidate.commit_sha,
                gate1_total=0.0,
                gate1_pass=False,
                threshold_used=threshold or self._settings.min_gate1_score,
            )

        # 3. Run all 7 sub-score checkers with error isolation
        hygiene = self._safe_score("hygiene", self._hygiene.score, ctx, HygieneScore)
        maintenance = self._safe_score(
            "maintenance",
            self._maintenance.score,
            ctx,
            MaintenanceScore,
        )
        release_discipline = self._safe_score(
            "release_discipline",
            self._release_discipline.score,
            ctx,
            ReleaseDisciplineScore,
        )
        review_practice = self._safe_score(
            "review_practice",
            self._practices.score,
            ctx,
            ReviewPracticeScore,
        )
        test_footprint = self._safe_score(
            "test_footprint",
            self._test_footprint.score,
            ctx,
            TestFootprintScore,
        )
        ci_cd = self._safe_score("ci_cd", self._ci_cd.score, ctx, CiCdScore)
        dependency_quality = self._safe_score(
            "dependency_quality",
            self._dependency_quality.score,
            ctx,
            DependencyQualityScore,
        )

        # 4. Build result
        threshold_val = threshold or self._settings.min_gate1_score
        result = MetadataScreenResult(
            full_name=candidate.full_name,
            commit_sha=candidate.commit_sha,
            hygiene=hygiene,
            maintenance=maintenance,
            release_discipline=release_discipline,
            review_practice=review_practice,
            test_footprint=test_footprint,
            ci_cd=ci_cd,
            dependency_quality=dependency_quality,
            threshold_used=threshold_val,
        )

        # 5. Compute total and apply threshold
        result.gate1_total = result.compute_total()
        result.gate1_pass = result.gate1_total >= threshold_val

        return result

    @staticmethod
    def _safe_score(
        name: str,
        score_fn: Callable[[RepoContext], _SubScoreT],
        ctx: RepoContext,
        default_cls: type[_SubScoreT],
    ) -> _SubScoreT:
        """Run a sub-score checker with error isolation.

        If the checker raises, return a zero-value instance of
        ``default_cls`` with low confidence instead of propagating.
        """
        try:
            return score_fn(ctx)
        except Exception as e:
            logger.warning(
                "gate1_subscore_error",
                checker=name,
                repo=ctx.candidate.full_name,
                error=str(e),
            )
            return default_cls(
                value=0.0,
                confidence=0.0,
                notes=[f"Error: {e}"],
            )

    async def screen_batch(
        self,
        candidates: list[RepoCandidate],
        *,
        threshold: float | None = None,
        max_concurrent: int = _MAX_CONCURRENT,
    ) -> list[MetadataScreenResult]:
        """Screen a batch of candidates with concurrency control."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _screen_one(candidate: RepoCandidate) -> MetadataScreenResult:
            async with semaphore:
                return await self.screen(candidate, threshold=threshold)

        return list(await asyncio.gather(*[_screen_one(c) for c in candidates]))
