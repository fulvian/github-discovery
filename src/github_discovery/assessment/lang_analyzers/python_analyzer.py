"""Python quality analyzer using ruff as an external linter.

Runs ``ruff check --output-format json`` on a cloned repo directory,
computes an issue-density score, and returns a ``DimensionScore`` for
the ``code_quality`` dimension.

Score breakpoints (issues per LOC):
    - 0 issues:   1.0
    - < 0.01:     0.8
    - < 0.05:     0.5
    - > 0.1:      0.2
    Linear interpolation between breakpoints.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

from github_discovery.assessment.lang_analyzers.base import LanguageAnalyzer
from github_discovery.models.assessment import DimensionScore
from github_discovery.models.enums import ScoreDimension

logger = structlog.get_logger(__name__)

# Issue-density breakpoints: (density, score)
_DENSITY_BREAKPOINTS: list[tuple[float, float]] = [
    (0.0, 1.0),
    (0.01, 0.8),
    (0.05, 0.5),
    (0.1, 0.2),
]

_MAX_EVIDENCE_ITEMS = 10
_RUFF_TIMEOUT_SECONDS = 30


def _interpolate_score(density: float) -> float:
    """Linearly interpolate a score from issue density using breakpoints."""
    if density <= 0.0:
        return 1.0

    for i in range(len(_DENSITY_BREAKPOINTS) - 1):
        d_low, s_low = _DENSITY_BREAKPOINTS[i]
        d_high, s_high = _DENSITY_BREAKPOINTS[i + 1]
        if density <= d_high:
            # Linear interpolation between (d_low, s_low) and (d_high, s_high)
            t = (density - d_low) / (d_high - d_low) if d_high != d_low else 0.0
            return s_low + t * (s_high - s_low)

    # density exceeds highest breakpoint
    return _DENSITY_BREAKPOINTS[-1][1]


class PythonAnalyzer(LanguageAnalyzer):
    """Analyzes Python repositories using ``ruff``."""

    def language(self) -> str:
        """Return ``"python"``."""
        return "python"

    async def analyze(self, clone_dir: str) -> DimensionScore | None:
        """Run ruff on *clone_dir* and return a code-quality score.

        Returns ``None`` when ruff is not installed, times out, or
        encounters any unexpected error.
        """
        if not await self._is_ruff_available():
            logger.warning("ruff_not_installed", msg="Skipping Python analysis")
            return None

        try:
            issues = await self._run_ruff(clone_dir)
        except TimeoutError:
            logger.warning("ruff_timeout", clone_dir=clone_dir)
            return None
        except Exception:
            logger.warning("ruff_failed", clone_dir=clone_dir, exc_info=True)
            return None

        loc = await self._count_loc(clone_dir)
        density = issues["total"] / loc if loc > 0 else 0.0
        score = _interpolate_score(density)

        evidence = [
            f"{item['filename']}: [{item['code']}] {item['message']}"
            for item in issues["items"][:_MAX_EVIDENCE_ITEMS]
        ]

        explanation = (
            f"Ruff found {issues['total']} issue(s) "
            f"across ~{loc} LOC (density={density:.4f}). "
            f"Score={score:.2f}."
        )

        return DimensionScore(
            dimension=ScoreDimension.CODE_QUALITY,
            value=score,
            explanation=explanation,
            evidence=evidence,
            confidence=0.6,
            assessment_method="ruff_heuristic",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _is_ruff_available(self) -> bool:
        """Check whether the ``ruff`` binary is on PATH."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ruff",
                "--version",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode == 0
        except FileNotFoundError:
            return False

    async def _run_ruff(self, clone_dir: str) -> dict[str, Any]:
        """Run ``ruff check --output-format json`` and parse the result.

        Returns a dict with ``"total"`` (int) and ``"items"`` (list of
        parsed JSON entries).

        Raises:
            TimeoutError: if ruff exceeds ``_RUFF_TIMEOUT_SECONDS``.
        """
        proc = await asyncio.create_subprocess_exec(
            "ruff",
            "check",
            "--output-format",
            "json",
            clone_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=_RUFF_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise

        if proc.returncode not in (0, 1):
            # ruff returns 1 when issues found, 0 when clean
            return {"total": 0, "items": []}

        raw = stdout.decode().strip()
        if not raw:
            return {"total": 0, "items": []}

        items: list[dict[str, Any]] = json.loads(raw)
        return {"total": len(items), "items": items}

    async def _count_loc(self, clone_dir: str) -> int:
        """Estimate lines of Python code in *clone_dir*.

        Uses ``wc -l`` on ``**/*.py`` files via ``find``.
        Falls back to 0 on any error.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "sh",
                "-c",
                f"find '{clone_dir}' -name '*.py' -exec cat {{}} + | wc -l",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            if proc.returncode == 0:
                return int(stdout.decode().strip())
        except Exception:
            logger.debug("loc_count_failed", clone_dir=clone_dir, exc_info=True)
        return 0
