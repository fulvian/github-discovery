#!/usr/bin/env python3
"""Wave 2: Screening smoke test against real GitHub API.

Tests Gate 1 and Gate 2 screening on a single well-known repo
to verify the pipeline works with real API responses.

Usage:
    GITHUB_TOKEN=ghp_xxx python scripts/smoke_screening.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

# Ensure package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from datetime import UTC, datetime

from github_discovery.config import Settings
from github_discovery.discovery.github_client import GitHubRestClient
from github_discovery.models.candidate import RepoCandidate
from github_discovery.screening.gate1_metadata import Gate1MetadataScreener
from github_discovery.screening.gate2_static import Gate2StaticScreener
from github_discovery.screening.orchestrator import ScreeningOrchestrator
from github_discovery.screening.types import ScreeningContext
from github_discovery.models.enums import DiscoveryChannel, DomainType, GateLevel


def make_candidate(full_name: str, stars: int = 0, language: str | None = None) -> RepoCandidate:
    """Create a minimal RepoCandidate for testing."""
    owner, repo = full_name.split("/", 1)
    return RepoCandidate(
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        html_url=f"https://github.com/{full_name}",
        api_url=f"https://api.github.com/repos/{full_name}",
        owner_login=owner,
        description="",
        stars=stars,
        language=language,
        topics=[],
        source_channel=DiscoveryChannel.SEARCH,
        discovery_score=0.5,
        created_at=datetime(2020, 1, 1, tzinfo=UTC),
        updated_at=datetime.now(UTC),
    )


async def test_gate1_single():
    """Test Gate 1 screening on a single well-known repo."""
    settings = Settings()  # reads from env vars
    print(f"GitHub token configured: {bool(settings.github.token)}")
    print(f"API base URL: {settings.github.api_base_url}")

    rest_client = GitHubRestClient(settings.github)
    gate1 = Gate1MetadataScreener(rest_client=rest_client, settings=settings.screening)

    # Pick a well-known, high-quality repo
    test_repo = "astral-sh/ruff"
    candidate = make_candidate(test_repo, stars=30000, language="Python")
    print(f"\n{'=' * 60}")
    print(f"Gate 1 Screening: {test_repo}")
    print(f"{'=' * 60}")

    start = time.perf_counter()
    try:
        result = await gate1.screen(candidate)
        elapsed = time.perf_counter() - start
        print(f"\nElapsed: {elapsed:.1f}s")
        print(f"Gate 1 Total: {result.gate1_total:.3f}")
        print(f"Gate 1 Pass:  {result.gate1_pass}")
        print(f"Threshold:    {result.threshold_used}")

        # Print sub-scores
        if result.hygiene:
            print(
                f"  hygiene:            {result.hygiene.value:.3f} (conf: {result.hygiene.confidence:.2f})"
            )
        if result.maintenance:
            print(
                f"  maintenance:        {result.maintenance.value:.3f} (conf: {result.maintenance.confidence:.2f})"
            )
        if result.release_discipline:
            print(
                f"  release_discipline: {result.release_discipline.value:.3f} (conf: {result.release_discipline.confidence:.2f})"
            )
        if result.review_practice:
            print(
                f"  review_practice:    {result.review_practice.value:.3f} (conf: {result.review_practice.confidence:.2f})"
            )
        if result.test_footprint:
            print(
                f"  test_footprint:     {result.test_footprint.value:.3f} (conf: {result.test_footprint.confidence:.2f})"
            )
        if result.ci_cd:
            print(
                f"  ci_cd:              {result.ci_cd.value:.3f} (conf: {result.ci_cd.confidence:.2f})"
            )
        if result.dependency_quality:
            print(
                f"  dependency_quality: {result.dependency_quality.value:.3f} (conf: {result.dependency_quality.confidence:.2f})"
            )
    except Exception as e:
        elapsed = time.perf_counter() - start
        print(f"\nERROR after {elapsed:.1f}s: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()

    await rest_client.close()


async def test_gate2_single():
    """Test Gate 2 screening on a single well-known repo (Gate 1 must pass first)."""
    settings = Settings()
    rest_client = GitHubRestClient(settings.github)
    gate1 = Gate1MetadataScreener(rest_client=rest_client, settings=settings.screening)
    gate2 = Gate2StaticScreener(
        rest_client=rest_client,
        settings=settings.screening,
        github_settings=settings.github,
    )

    test_repo = "astral-sh/ruff"
    candidate = make_candidate(test_repo, stars=30000, language="Python")
    print(f"\n{'=' * 60}")
    print(f"Gate 2 Screening: {test_repo}")
    print(f"{'=' * 60}")

    start = time.perf_counter()
    try:
        # Must pass Gate 1 first
        gate1_result = await gate1.screen(candidate)
        print(f"Gate 1 result: {gate1_result.gate1_total:.3f} (pass={gate1_result.gate1_pass})")

        if not gate1_result.gate1_pass:
            print("Gate 1 FAILED — cannot proceed to Gate 2")
            return

        gate2_result = await gate2.screen(candidate, gate1_result)
        elapsed = time.perf_counter() - start
        print(f"\nElapsed: {elapsed:.1f}s")
        print(f"Gate 2 Total: {gate2_result.gate2_total:.3f}")
        print(f"Gate 2 Pass:  {gate2_result.gate2_pass}")

        # Print sub-scores
        if gate2_result.security_hygiene:
            print(f"  security_hygiene: {gate2_result.security_hygiene.value:.3f}")
        if gate2_result.vulnerability:
            print(f"  vulnerability:    {gate2_result.vulnerability.value:.3f}")
        if gate2_result.secret_hygiene:
            print(f"  secret_hygiene:   {gate2_result.secret_hygiene.value:.3f}")
        if gate2_result.complexity:
            print(f"  complexity:       {gate2_result.complexity.value:.3f}")
    except Exception as e:
        elapsed = time.perf_counter() - start
        print(f"\nERROR after {elapsed:.1f}s: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()

    await rest_client.close()


async def test_orchestrator_batch():
    """Test the full ScreeningOrchestrator on a small batch of repos."""
    settings = Settings()
    rest_client = GitHubRestClient(settings.github)
    gate1 = Gate1MetadataScreener(rest_client=rest_client, settings=settings.screening)
    gate2 = Gate2StaticScreener(
        rest_client=rest_client,
        settings=settings.screening,
        github_settings=settings.github,
    )
    orchestrator = ScreeningOrchestrator(
        settings=settings,
        gate1_screener=gate1,
        gate2_screener=gate2,
    )

    candidates = [
        make_candidate("astral-sh/ruff", stars=30000, language="Python"),
        make_candidate("pallets/flask", stars=68000, language="Python"),
        make_candidate("fastapi/fastapi", stars=80000, language="Python"),
    ]

    context = ScreeningContext(
        pool_id="smoke-test",
        candidates=candidates,
        gate_level=GateLevel.STATIC_SECURITY,  # Run both Gate 1 + Gate 2
    )

    print(f"\n{'=' * 60}")
    print(f"Orchestrator Batch Test: {len(candidates)} repos")
    print(f"{'=' * 60}")

    start = time.perf_counter()
    try:
        results = await orchestrator.screen(context)
        elapsed = time.perf_counter() - start
        print(f"\nTotal elapsed: {elapsed:.1f}s")
        print(f"Results: {len(results)}")

        for r in results:
            g1 = f"{r.gate1.gate1_total:.3f}" if r.gate1 else "N/A"
            g1p = "PASS" if r.gate1 and r.gate1.gate1_pass else "FAIL"
            g2 = f"{r.gate2.gate2_total:.3f}" if r.gate2 else "N/A"
            g2p = "PASS" if r.gate2 and r.gate2.gate2_pass else ("FAIL" if r.gate2 else "SKIP")
            print(f"  {r.full_name:30s}  G1={g1} ({g1p})  G2={g2} ({g2p})")
    except Exception as e:
        elapsed = time.perf_counter() - start
        print(f"\nERROR after {elapsed:.1f}s: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()

    await rest_client.close()


async def main():
    """Run all screening smoke tests."""
    print("=" * 60)
    print("Wave 2: Screening Smoke Tests (Real GitHub API)")
    print("=" * 60)

    # Test 1: Gate 1 single repo
    await test_gate1_single()

    # Test 2: Gate 2 single repo
    await test_gate2_single()

    # Test 3: Full orchestrator batch (3 repos, Gate 1+2)
    # Note: This may take 2-3 minutes due to shallow cloning for Gate 2
    print("\n\n⚠️  Note: Batch test may take 2-3 minutes (includes shallow cloning for Gate 2)")
    await test_orchestrator_batch()

    print("\n\n✅ Wave 2 screening smoke tests complete")


if __name__ == "__main__":
    asyncio.run(main())
