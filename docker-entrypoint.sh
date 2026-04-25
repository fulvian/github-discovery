#!/usr/bin/env bash
# =============================================================================
# GitHub Discovery — Docker Entrypoint
# =============================================================================
# Dispatches to the appropriate runtime mode based on the first argument:
#
#   mcp   (default) — MCP stdio server for agent integration
#   api              — FastAPI REST server with uvicorn
#   worker           — Background scoring worker
#   <anything else>  — Passed through to ghdisc CLI
# =============================================================================

set -euo pipefail

MODE="${1:-mcp}"
# Shift only if we recognized the mode; otherwise pass all args to CLI
case "${MODE}" in
    mcp)
        exec python -m github_discovery.mcp serve --transport stdio
        ;;
    api)
        shift || true
        exec python -m uvicorn \
            github_discovery.api.app:create_app \
            --factory \
            --host "${GHDISC_API_HOST:-0.0.0.0}" \
            --port "${GHDISC_API_PORT:-8000}" \
            "$@"
        ;;
    worker)
        shift || true
        # Worker mode runs the async task processor.
        # Falls back to CLI discover command as the long-running worker
        # until a dedicated worker entry point is implemented.
        exec python -c "
import asyncio
from github_discovery.config import Settings
from github_discovery.workers.queue import AsyncTaskQueue
from github_discovery.workers.job_store import JobStore
from github_discovery.workers.worker_manager import WorkerManager
from github_discovery.discovery.pool import PoolManager
from github_discovery.discovery.orchestrator import DiscoveryOrchestrator
from github_discovery.screening.orchestrator import ScreeningOrchestrator
from github_discovery.screening.gate1_metadata import Gate1MetadataScreener
from github_discovery.screening.gate2_static import Gate2StaticScreener
from github_discovery.discovery.github_client import GitHubRestClient
from github_discovery.assessment.orchestrator import AssessmentOrchestrator

async def main():
    settings = Settings()
    job_store = JobStore(settings.api.job_store_path)
    await job_store.initialize()
    pool_manager = PoolManager(':memory:')
    discovery_orch = DiscoveryOrchestrator(settings, pool_manager)
    rest_client = GitHubRestClient(settings.github)
    gate1 = Gate1MetadataScreener(rest_client, settings.screening)
    gate2 = Gate2StaticScreener(rest_client, settings.screening, settings.github)
    screening_orch = ScreeningOrchestrator(settings, gate1, gate2)
    assessment_orch = AssessmentOrchestrator(settings)
    queue = AsyncTaskQueue(job_store)
    manager = WorkerManager(
        queue=queue,
        job_store=job_store,
        discovery_orch=discovery_orch,
        screening_orch=screening_orch,
        assessment_orch=assessment_orch,
        workers_per_type=settings.api.workers,
    )
    await manager.start()
    print('Worker started. Waiting for jobs...')
    try:
        # Block forever
        import signal
        signal.pause()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await manager.stop()
        await pool_manager.close()
        await job_store.close()
        await assessment_orch.close()

asyncio.run(main())
"
        ;;
    *)
        # Pass through to ghdisc CLI
        exec ghdisc "$@"
        ;;
esac
