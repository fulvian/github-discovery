"""Gate 2 — Static/security screening engine (zero or low cost).

Orchestrates 4 sub-score checkers using external tools:
- OpenSSF Scorecard API (HTTP)
- OSV API (HTTP)
- gitleaks (subprocess on shallow clone)
- scc (subprocess for LOC/complexity)

Only runs on candidates that passed Gate 1 (hard gate enforcement).
Implements graceful degradation: tool failures → heuristic fallback.

Clone management (Blueprint §16.3):
When subprocess tools (gitleaks, scc) require a local clone, Gate 2
performs a shallow clone (``git clone --depth=1``) to a temporary
directory and cleans up after screening completes.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from github_discovery.discovery.github_client import GitHubRestClient  # noqa: TC001
from github_discovery.exceptions import HardGateViolationError
from github_discovery.models.candidate import RepoCandidate  # noqa: TC001
from github_discovery.models.screening import (
    ComplexityScore,
    MetadataScreenResult,
    SecretHygieneScore,
    SecurityHygieneScore,
    StaticScreenResult,
    VulnerabilityScore,
)
from github_discovery.screening.complexity import ComplexityAnalyzer
from github_discovery.screening.osv_adapter import OsvAdapter
from github_discovery.screening.scorecard_adapter import ScorecardAdapter
from github_discovery.screening.secrets_check import SecretsChecker
from github_discovery.screening.subprocess_runner import SubprocessRunner

if TYPE_CHECKING:
    from github_discovery.config import GitHubSettings, ScreeningSettings

logger = structlog.get_logger("github_discovery.screening.gate2")

_FALLBACK_SCORE = 0.3
_FALLBACK_CONFIDENCE = 0.0
_CLONE_TIMEOUT = 120.0
_DEFAULT_CLONE_PREFIX = "ghdisc_"


def cleanup_orphan_clones(
    prefix: str = _DEFAULT_CLONE_PREFIX,
    max_age_hours: float = 6.0,
) -> int:
    """Remove orphaned clone directories older than max_age_hours.

    Scans the system temp directory for directories matching the given
    prefix and removes those older than max_age_hours.

    Args:
        prefix: Directory name prefix to match (default: 'ghdisc_').
        max_age_hours: Maximum age in hours before cleanup (default: 6.0).

    Returns:
        Number of directories removed.
    """
    removed = 0
    tmp_dir = Path(tempfile.gettempdir())
    cutoff = time.time() - (max_age_hours * 3600)

    for entry in tmp_dir.iterdir():
        if entry.is_dir() and entry.name.startswith(prefix):
            try:
                mtime = entry.stat().st_mtime
                if mtime < cutoff:
                    shutil.rmtree(entry, ignore_errors=True)
                    removed += 1
                    logger.info(
                        "orphan_clone_cleaned",
                        path=str(entry),
                        age_hours=(time.time() - mtime) / 3600,
                    )
            except OSError:
                logger.debug("orphan_clone_skip", path=str(entry))

    if removed > 0:
        logger.info("orphan_clone_cleanup_complete", removed=removed)
    return removed


class Gate2StaticScreener:
    """Gate 2 — Static/security screening engine.

    Coordinates 4 sub-score checkers with graceful degradation.
    Tool failures produce heuristic fallback scores rather than
    blocking the pipeline.

    When subprocess tools need a local clone, performs a shallow
    ``git clone --depth=1`` to a temporary directory and cleans
    up after screening.
    """

    def __init__(
        self,
        rest_client: GitHubRestClient,
        settings: ScreeningSettings,
        github_settings: GitHubSettings,
    ) -> None:
        """Initialize with GitHub clients and settings."""
        self._settings = settings
        self._github_settings = github_settings
        self._subprocess_runner = SubprocessRunner()
        self._scorecard = ScorecardAdapter()
        self._osv = OsvAdapter()
        self._secrets = SecretsChecker(subprocess_runner=self._subprocess_runner)
        self._complexity = ComplexityAnalyzer(subprocess_runner=self._subprocess_runner)

    async def _clone_repo(
        self,
        candidate: RepoCandidate,
    ) -> str | None:
        """Shallow clone a repository to a temporary directory.

        Returns the clone directory path, or None if cloning fails.
        The caller is responsible for cleanup via ``_cleanup_clone``.
        """
        clone_url = candidate.url
        clone_dir = tempfile.mkdtemp(prefix=f"ghdisc_{candidate.repo_name}_")

        try:
            result = await self._subprocess_runner.run(
                ["git", "clone", "--depth=1", clone_url, clone_dir],
                timeout=_CLONE_TIMEOUT,
            )
            if result.returncode == 0:
                logger.info(
                    "gate2_clone_success",
                    repo=candidate.full_name,
                    clone_dir=clone_dir,
                )
                return clone_dir

            logger.warning(
                "gate2_clone_failed",
                repo=candidate.full_name,
                returncode=result.returncode,
                stderr=result.stderr[:200],
            )
            shutil.rmtree(clone_dir, ignore_errors=True)
            return None
        except Exception as e:
            logger.warning(
                "gate2_clone_error",
                repo=candidate.full_name,
                error=str(e),
            )
            shutil.rmtree(clone_dir, ignore_errors=True)
            return None

    @staticmethod
    def _cleanup_clone(clone_dir: str | None) -> None:
        """Remove temporary clone directory."""
        if clone_dir is not None:
            shutil.rmtree(clone_dir, ignore_errors=True)

    async def screen(
        self,
        candidate: RepoCandidate,
        gate1_result: MetadataScreenResult,
        *,
        threshold: float | None = None,
    ) -> StaticScreenResult:
        """Screen a single candidate through Gate 2.

        Precondition: gate1_result.gate1_pass must be True.
        Raises HardGateViolationError if hard_gate_enforcement is enabled.
        """
        # Hard gate enforcement (configurable via GHDISC_SCREENING_HARD_GATE_ENFORCEMENT)
        if self._settings.hard_gate_enforcement and not gate1_result.gate1_pass:
            raise HardGateViolationError(
                f"Cannot screen {candidate.full_name} through Gate 2: "
                f"Gate 1 not passed (score={gate1_result.gate1_total:.2f})",
                repo_url=candidate.url,
                gate_passed=1,
                gate_required=2,
            )

        # Attempt shallow clone for subprocess tools
        clone_dir: str | None = None
        try:
            clone_dir = await self._clone_repo(candidate)

            tools_used: list[str] = []
            tools_failed: list[str] = []

            async def _run_scorecard() -> SecurityHygieneScore:
                try:
                    score = await self._scorecard.score(candidate)
                    tools_used.append("scorecard")
                    return score
                except Exception as e:
                    logger.warning("gate2_tool_error", tool="scorecard", error=str(e))
                    tools_failed.append("scorecard")
                    return SecurityHygieneScore(
                        value=_FALLBACK_SCORE,
                        confidence=_FALLBACK_CONFIDENCE,
                        notes=[f"Scorecard error: {e}"],
                    )

            async def _run_osv() -> VulnerabilityScore:
                try:
                    score = await self._osv.score(candidate)
                    tools_used.append("osv")
                    return score
                except Exception as e:
                    logger.warning("gate2_tool_error", tool="osv", error=str(e))
                    tools_failed.append("osv")
                    return VulnerabilityScore(
                        value=_FALLBACK_SCORE,
                        confidence=_FALLBACK_CONFIDENCE,
                        notes=[f"OSV error: {e}"],
                    )

            async def _run_secrets() -> SecretHygieneScore:
                try:
                    score = await self._secrets.score(candidate, clone_dir=clone_dir)
                    tools_used.append("gitleaks")
                    return score
                except Exception as e:
                    logger.warning("gate2_tool_error", tool="gitleaks", error=str(e))
                    tools_failed.append("gitleaks")
                    return SecretHygieneScore(
                        value=_FALLBACK_SCORE,
                        confidence=_FALLBACK_CONFIDENCE,
                        notes=[f"Gitleaks error: {e}"],
                    )

            async def _run_complexity() -> ComplexityScore:
                try:
                    score = await self._complexity.score(candidate, clone_dir=clone_dir)
                    tools_used.append("scc")
                    return score
                except Exception as e:
                    logger.warning("gate2_tool_error", tool="scc", error=str(e))
                    tools_failed.append("scc")
                    return ComplexityScore(
                        value=_FALLBACK_SCORE,
                        confidence=_FALLBACK_CONFIDENCE,
                        notes=[f"scc error: {e}"],
                    )

            # Parallel execution of all 4 tools
            sec_result, osv_result, secrets_result, complexity_result = await asyncio.gather(
                _run_scorecard(),
                _run_osv(),
                _run_secrets(),
                _run_complexity(),
            )

            threshold_val = threshold or self._settings.min_gate2_score
            result = StaticScreenResult(
                full_name=candidate.full_name,
                commit_sha=candidate.commit_sha,
                security_hygiene=sec_result,
                vulnerability=osv_result,
                complexity=complexity_result,
                secret_hygiene=secrets_result,
                tools_used=tools_used,
                tools_failed=tools_failed,
                threshold_used=threshold_val,
            )

            result.gate2_total = result.compute_total()
            result.gate2_pass = result.gate2_total >= threshold_val

            return result
        finally:
            self._cleanup_clone(clone_dir)

    async def close(self) -> None:
        """Clean up resources (httpx clients, temp dirs)."""
        await self._scorecard.close()
        await self._osv.close()

    async def screen_batch(
        self,
        candidates: list[tuple[RepoCandidate, MetadataScreenResult]],
        *,
        threshold: float | None = None,
        max_concurrent: int = 3,
    ) -> list[StaticScreenResult]:
        """Screen a batch. Only candidates that passed Gate 1 are screened.

        Candidates that failed Gate 1 get a zero-score failed result
        instead of raising an exception.
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _screen_one(
            pair: tuple[RepoCandidate, MetadataScreenResult],
        ) -> StaticScreenResult:
            candidate, gate1_result = pair
            async with semaphore:
                if not gate1_result.gate1_pass:
                    return StaticScreenResult(
                        full_name=candidate.full_name,
                        commit_sha=candidate.commit_sha,
                        gate2_total=0.0,
                        gate2_pass=False,
                        tools_failed=["gate1_not_passed"],
                    )
                return await self.screen(candidate, gate1_result, threshold=threshold)

        return list(await asyncio.gather(*[_screen_one(p) for p in candidates]))
