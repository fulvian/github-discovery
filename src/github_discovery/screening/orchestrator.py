"""Screening orchestrator and policy engine.

Coordinates Gate 1 and Gate 2 screening with:
- Hard gate enforcement (no Gate 3 without Gate 1+2 pass)
- Domain-specific thresholds via Policy Engine
- Batch processing with concurrency control
- Graceful error handling and progress tracking
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from github_discovery.exceptions import HardGateViolationError
from github_discovery.models.candidate import RepoCandidate  # noqa: TC001
from github_discovery.models.enums import DomainType, GateLevel
from github_discovery.models.screening import ScreeningResult
from github_discovery.scoring.profiles import ProfileRegistry
from github_discovery.screening.gate1_metadata import Gate1MetadataScreener  # noqa: TC001
from github_discovery.screening.gate2_static import Gate2StaticScreener  # noqa: TC001
from github_discovery.screening.types import ScreeningContext

if TYPE_CHECKING:
    from github_discovery.config import Settings

logger = structlog.get_logger("github_discovery.screening.orchestrator")

# Domain-specific threshold overrides (higher = stricter).
# Covers all DomainType values — uncovered domains fall through to
# global default from settings (0.4 gate1, 0.5 gate2).
_DOMAIN_THRESHOLDS: dict[DomainType, dict[str, float]] = {
    DomainType.LIBRARY: {"gate1": 0.5, "gate2": 0.6},
    DomainType.SECURITY_TOOL: {"gate1": 0.6, "gate2": 0.7},
    DomainType.DEVOPS_TOOL: {"gate1": 0.5, "gate2": 0.6},
    DomainType.ML_LIB: {"gate1": 0.4, "gate2": 0.5},
    DomainType.CLI: {"gate1": 0.4, "gate2": 0.5},
    DomainType.BACKEND: {"gate1": 0.5, "gate2": 0.6},
    DomainType.WEB_FRAMEWORK: {"gate1": 0.5, "gate2": 0.6},
    DomainType.DATA_TOOL: {"gate1": 0.4, "gate2": 0.5},
    DomainType.LANG_TOOL: {"gate1": 0.5, "gate2": 0.6},
    DomainType.TEST_TOOL: {"gate1": 0.5, "gate2": 0.6},
    DomainType.DOC_TOOL: {"gate1": 0.4, "gate2": 0.5},
}

_MAX_CONCURRENT = 5


class ScreeningOrchestrator:
    """Central orchestrator for the screening pipeline.

    Coordinates Gate 1 and Gate 2 screening with:
    - Hard gate enforcement (no Gate 3 without Gate 1+2 pass)
    - Domain-specific thresholds via Policy Engine
    - Batch processing with concurrency control
    - Graceful error handling
    """

    def __init__(
        self,
        settings: Settings,
        gate1_screener: Gate1MetadataScreener,
        gate2_screener: Gate2StaticScreener,
    ) -> None:
        """Initialize with settings and gate screeners."""
        self._settings = settings
        self._gate1 = gate1_screener
        self._gate2 = gate2_screener
        self._profile_registry = ProfileRegistry(
            custom_profiles_path=settings.scoring.custom_profiles_path or None,
        )

    async def screen(
        self,
        context: ScreeningContext,
    ) -> list[ScreeningResult]:
        """Screen a pool of candidates through configured gates.

        For each candidate:
        1. If gate_level >= METADATA: screen through Gate 1
        2. If Gate 1 passed AND gate_level >= STATIC_SECURITY: screen through Gate 2
        3. Apply hard gate enforcement
        4. Return list of ScreeningResult
        """
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

        async def _screen_one(candidate: RepoCandidate) -> ScreeningResult:
            async with semaphore:
                return await self._screen_candidate(candidate, context)

        tasks = [_screen_one(c) for c in context.candidates]
        results = list(await asyncio.gather(*tasks))

        logger.info(
            "screening_complete",
            pool_id=context.pool_id,
            total=len(results),
            gate1_passed=sum(1 for r in results if r.gate1 and r.gate1.gate1_pass),
            gate2_passed=sum(1 for r in results if r.gate2 and r.gate2.gate2_pass),
        )

        return results

    @staticmethod
    def _context_override(context_value: float, field_name: str) -> float | None:
        """Return override only if context value differs from field default.

        This allows domain-specific thresholds to apply when the user
        hasn't explicitly overridden the threshold in the context.
        """
        field_default = ScreeningContext.model_fields[field_name].default
        if context_value != field_default:
            return context_value
        return None

    async def _screen_candidate(
        self,
        candidate: RepoCandidate,
        context: ScreeningContext,
    ) -> ScreeningResult:
        """Screen a single candidate through the configured gates."""
        gate1_result = None
        gate2_result = None

        # Gate 1: run if gate_level is METADATA or higher
        if int(context.gate_level) >= int(GateLevel.METADATA):
            threshold = self._get_threshold(
                GateLevel.METADATA,
                domain=candidate.domain,
                override=self._context_override(context.min_gate1_score, "min_gate1_score"),
            )
            try:
                gate1_result = await self._gate1.screen(candidate, threshold=threshold)
            except Exception as e:
                logger.error(
                    "gate1_screening_error",
                    repo=candidate.full_name,
                    error=str(e),
                )

        # Gate 2: run only if Gate 1 passed AND gate_level is STATIC_SECURITY or higher
        if (
            gate1_result
            and gate1_result.gate1_pass
            and int(context.gate_level) >= int(GateLevel.STATIC_SECURITY)
        ):
            threshold = self._get_threshold(
                GateLevel.STATIC_SECURITY,
                domain=candidate.domain,
                override=self._context_override(context.min_gate2_score, "min_gate2_score"),
            )
            try:
                gate2_result = await self._gate2.screen(
                    candidate,
                    gate1_result,
                    threshold=threshold,
                )
            except HardGateViolationError:
                logger.warning(
                    "gate2_hard_gate_violation",
                    repo=candidate.full_name,
                )
            except Exception as e:
                logger.error(
                    "gate2_screening_error",
                    repo=candidate.full_name,
                    error=str(e),
                )

        return ScreeningResult(
            full_name=candidate.full_name,
            commit_sha=candidate.commit_sha,
            gate1=gate1_result,
            gate2=gate2_result,
        )

    def _get_threshold(
        self,
        gate: GateLevel,
        domain: DomainType | None = None,
        override: float | None = None,
    ) -> float:
        """Get threshold for a gate, considering domain profile and override.

        Priority: override > DomainProfile.gate_thresholds > global default.

        T5.2: reads per-domain thresholds from DomainProfile.gate_thresholds
        instead of the module-level _DOMAIN_THRESHOLDS dict. The old dict
        is kept as fallback for backward compatibility.
        """
        if override is not None:
            return override

        gate_key = "gate1" if gate == GateLevel.METADATA else "gate2"

        # T5.2: Read from DomainProfile first (single source of truth)
        if domain is not None:
            profile = self._profile_registry.get(domain)
            if gate_key in profile.gate_thresholds:
                return profile.gate_thresholds[gate_key]

            # Fallback: legacy _DOMAIN_THRESHOLDS (for profiles without
            # explicit gate_thresholds that somehow still have entries here)
            domain_thresholds = _DOMAIN_THRESHOLDS.get(domain, {})
            if gate_key in domain_thresholds:
                return domain_thresholds[gate_key]

        # Global default from settings
        if gate == GateLevel.METADATA:
            return self._settings.screening.min_gate1_score
        return self._settings.screening.min_gate2_score

    async def quick_screen(
        self,
        candidate: RepoCandidate,
        gate_levels: str = "1",
    ) -> ScreeningResult:
        """Quick screen a single repo without full pool context.

        Used by MCP tool quick_screen for single-repo checks.
        """
        # Screen Gate 1
        gate1_result = await self._gate1.screen(candidate)
        gate2_result = None

        # Optionally screen Gate 2
        if "2" in gate_levels and gate1_result.gate1_pass:
            try:
                gate2_result = await self._gate2.screen(candidate, gate1_result)
            except HardGateViolationError:
                logger.warning(
                    "quick_screen_hard_gate_violation",
                    repo=candidate.full_name,
                )
            except Exception as e:
                logger.error(
                    "quick_screen_gate2_error",
                    repo=candidate.full_name,
                    error=str(e),
                )

        return ScreeningResult(
            full_name=candidate.full_name,
            commit_sha=candidate.commit_sha,
            gate1=gate1_result,
            gate2=gate2_result,
        )
