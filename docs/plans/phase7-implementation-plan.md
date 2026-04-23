# GitHub Discovery — Phase 7 Implementation Plan

## Meta

- **Stato**: Draft v1
- **Data**: 2026-04-23
- **Riferimento roadmap**: `docs/roadmaps/github-discovery_foundation_roadmap.md` — Phase 7
- **Riferimento blueprint**: `docs/foundation/github-discovery_foundation_blueprint.md` — §21 (Agentic Integration Architecture)
- **Riferimento wiki**: `docs/llm-wiki/wiki/` — articoli su MCP-native design, MCP tools, MCP SDK verification, session workflow, agent workflows
- **Durata stimata**: 2-3 settimane
- **Milestone**: M6 — MCP-Native (MCP primaria con tools granulari, progressive deepening, session management, composable con GitHub MCP)
- **Dipendenza**: Phase 0+1+2+3+4+5+6 completate (990 tests passing, `make ci` verde)
- **Context7 verification**: MCP Python SDK v1.x (FastMCP, tools, resources, prompts, Context, progress notifications, transport, structured content) + GitHub MCP Server (toolsets, read-only, lockdown, dynamic-toolsets)

---

## Indice

1. [Obiettivo](#1-obiettivo)
2. [Task Overview](#2-task-overview)
3. [Architettura generale](#3-architettura-generale)
4. [Nuove dipendenze](#4-nuove-dipendenze)
5. [Codice esistente — placeholder e modelli](#5-codice-esistente--placeholder-e-modelli)
6. [Configurazione — MCPSettings](#6-configurazione--mcpsettings)
7. [Task 7.1 — MCP Server Setup (FastMCP)](#7-task-71--mcp-server-setup-fastmcp)
8. [Task 7.2 — MCP Tools: Discovery](#8-task-72--mcp-tools-discovery)
9. [Task 7.3 — MCP Tools: Screening](#9-task-73--mcp-tools-screening)
10. [Task 7.4 — MCP Tools: Assessment](#10-task-74--mcp-tools-assessment)
11. [Task 7.5 — MCP Tools: Ranking & Explainability](#11-task-75--mcp-tools-ranking--explainability)
12. [Task 7.6 — MCP Tools: Session Management](#12-task-76--mcp-tools-session-management)
13. [Task 7.7 — MCP Resources](#13-task-77--mcp-resources)
14. [Task 7.8 — MCP Prompts (Agent Skill Definitions)](#14-task-78--mcp-prompts-agent-skill-definitions)
15. [Task 7.9 — GitHub MCP Server Composition](#15-task-79--github-mcp-server-composition)
16. [Task 7.10 — Progress Notifications & Streaming](#16-task-710--progress-notifications--streaming)
17. [Task 7.11 — Context-Efficient Output Design](#17-task-711--context-efficient-output-design)
18. [Task 7.12 — Transport & Security](#18-task-712--transport--security)
19. [Task 7.13 — MCP Configuration per Ambiente](#19-task-713--mcp-configuration-per-ambiente)
20. [Sequenza di implementazione — Waves](#20-sequenza-di-implementazione--waves)
21. [Test plan](#21-test-plan)
22. [Criteri di accettazione](#22-criteri-di-accettazione)
23. [Rischi e mitigazioni](#23-rischi-e-mitigazioni)
24. [Verifica Context7](#24-verifica-context7)

---

## 1) Obiettivo

Implementare l'interfaccia primaria MCP (Model Context Protocol) che espone discovery, screening, assessment e scoring come tools composable, resources strutturate, e prompts come agent skill definitions. MCP è l'interfaccia primaria del sistema — la REST API (Phase 6) è consumer secondario degli stessi servizi core.

Al completamento della Phase 7:

- **FastMCP server** operativo con nome `github-discovery`, transport configurabile (stdio, streamable-http)
- **16 tool MCP granulari**: 3 discovery, 3 screening, 3 assessment, 3 ranking, 4 session management
- **Progressive deepening**: ogni gate è invocabile singolarmente, l'agente ordestra il flusso
- **5 prompt skill**: `discover_underrated`, `quick_quality_check`, `compare_for_adoption`, `domain_deep_dive`, `security_audit`
- **4 resource URI**: repo score, pool candidates, domain ranking, session status
- **Session management**: persistenza cross-sessione con SQLite backend, progressive deepening cross-invocazione
- **Progress notifications**: streaming per operazioni lunghe (discovery, screening, assessment)
- **Context-efficient output**: summary-first (< 2000 token default), dettaglio on-demand
- **GitHub MCP composition**: non duplicazione, solo scoring/ranking, read-only di default

### Principi architetturali (Blueprint §21.2)

1. **MCP-First**: MCP tools/resources/prompts sono l'interfaccia primaria. L'API REST è consumer secondario.
2. **Progressive Deepening**: Ogni gate è un tool MCP indipendente. Il flusso lineare è solo uno dei possibili workflow.
3. **Agent-Driven Policy**: Le soglie di gating sono parametri dei tool MCP, non costanti hardcoded.
4. **Session-Aware**: `session_id` per workflow cross-sessione e progressive deepening.
5. **Context-Efficient**: Summary-first default, dettaglio on-demand. Reference (pool_id, session_id, repo_url) invece di dati completi.

---

## 2) Task Overview

| Task ID | Task | Output | Dipende da |
|---------|------|--------|------------|
| 7.1 | MCP server setup (FastMCP) | `mcp/server.py` con lifespan, AppContext | — |
| 7.2 | MCP tools — Discovery | `mcp/tools/discovery.py` (3 tools) | 7.1, 7.10, 7.11 |
| 7.3 | MCP tools — Screening | `mcp/tools/screening.py` (3 tools) | 7.1, 7.10, 7.11 |
| 7.4 | MCP tools — Assessment | `mcp/tools/assessment.py` (3 tools) | 7.1, 7.10, 7.11 |
| 7.5 | MCP tools — Ranking & Explainability | `mcp/tools/ranking.py` (3 tools) | 7.1, 7.11 |
| 7.6 | MCP tools — Session Management | `mcp/tools/session.py` (4 tools) | 7.1, 7.13 |
| 7.7 | MCP resources | `mcp/resources/*.py` (4 resources) | 7.1 |
| 7.8 | MCP prompts (agent skill definitions) | `mcp/prompts.py` (5 prompts) | 7.1 |
| 7.9 | GitHub MCP Server composition | `mcp/github_client.py` | 7.1, 7.12 |
| 7.10 | Progress notifications & streaming | `mcp/progress.py` | — |
| 7.11 | Context-efficient output design | `mcp/output_format.py` | — |
| 7.12 | Transport & security | `mcp/transport.py` | 7.1 |
| 7.13 | MCP configuration per ambiente | `mcp/config.py` | — |

---

## 3) Architettura generale

### Struttura moduli

```
src/github_discovery/mcp/
├── __init__.py                  # Exports: create_server, serve
├── server.py                    # FastMCP server factory + lifespan + AppContext
├── config.py                    # MCPSettings helpers, runtime setup, tool filtering
├── session.py                   # SessionManager — SQLite-backed session persistence
├── progress.py                  # Progress notification helpers (ctx.report_progress wrappers)
├── output_format.py             # Context-efficient output formatting (summary-first)
├── prompts.py                   # 5 MCP prompt skill definitions
├── github_client.py             # GitHub MCP composition client (delegate standard ops)
├── transport.py                 # Transport configuration (stdio + streamable-http)
├── tools/
│   ├── __init__.py              # Tool registration helper — register_all_tools()
│   ├── discovery.py             # discover_repos, get_candidate_pool, expand_seeds
│   ├── screening.py             # screen_candidates, get_shortlist, quick_screen
│   ├── assessment.py            # deep_assess, quick_assess, get_assessment
│   ├── ranking.py               # rank_repos, explain_repo, compare_repos
│   └── session.py               # create_session, get_session, list_sessions, export_session
└── resources/
    ├── __init__.py              # Resource registration helper — register_all_resources()
    ├── repo_score.py            # repo://{owner}/{name}/score
    ├── pool_candidates.py       # pool://{id}/candidates
    ├── domain_ranking.py        # rank://{domain}/top
    └── session_status.py        # session://{id}/status
```

### Flusso tool invocation (progressive deepening)

```
Agent (Kilocode/OpenClaude/Claude Code)
    │
    ├── Pattern 1: Quick Assessment
    │   ├── discover_repos(query="static analysis python", max_candidates=50)
    │   ├── quick_screen(repo_url) or screen_candidates(gate_level="1")
    │   └── Result: fast quality signal
    │
    ├── Pattern 2: Deep Discovery (Progressive Deepening)
    │   ├── create_session(name="ml-search")
    │   ├── discover_repos(query="ml framework", session_id=...)
    │   ├── screen_candidates(gate_level="both", session_id=...)
    │   ├── deep_assess(repo_urls=[...], session_id=...)
    │   ├── rank_repos(domain="ml_lib", session_id=...)
    │   └── explain_repo(repo_url=..., detail_level="full")
    │
    └── Pattern 3: Comparison for Adoption
        ├── screen_candidates → quick_assess → compare_repos
        └── Result: side-by-side comparison
```

### Server lifecycle

```python
@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    # Startup:
    # 1. Initialize Settings
    # 2. Initialize SessionManager (SQLite)
    # 3. Initialize orchestrators (discovery, screening, assessment)
    # 4. Initialize ScoringEngine, Ranker, FeatureStore
    # 5. Initialize PoolManager
    yield AppContext(
        settings=...,
        session_manager=...,
        discovery_orch=...,
        screening_orch=...,
        assessment_orch=...,
        scoring_engine=...,
        ranker=...,
        pool_manager=...,
    )
    # Shutdown:
    # 1. Close SessionManager (SQLite)
    # 2. Close httpx clients (via orchestrators)
    # 3. Close FeatureStore
```

---

## 4) Nuove dipendenze

Da aggiungere a `pyproject.toml`:

| Package | Versione | Purpose |
|---------|----------|---------|
| `mcp` | `>=1.6` | MCP Python SDK — FastMCP, tools, resources, prompts, Context, transports |

**Non servono nuove dipendenze per**:
- Session management: `aiosqlite` (già presente)
- JSON serialization: `pydantic` (già presente)
- Logging: `structlog` (già presente)
- GitHub API: `httpx` (già presente)
- Output formatting: stdlib (`json`, `csv`, `io`)

**Nota**: Il package MCP SDK è `mcp` su PyPI. Contiene `mcp.server.fastmcp`, `mcp.server.session`, `mcp.types`, ecc.

---

## 5) Codice esistente — placeholder e modelli

I seguenti file sono **placeholder** (stub creati in Phase 0) che saranno rimpiazzati:

| File | Stato attuale | Diventa |
|------|--------------|---------|
| `mcp/server.py` | `create_server() → object()` | FastMCP server factory con lifespan |
| `mcp/session.py` | Docstring only | SessionManager con SQLite backend |
| `mcp/progress.py` | Docstring only | Progress notification helpers |
| `mcp/output_format.py` | Docstring only | Context-efficient output formatters |
| `mcp/prompts.py` | Docstring only | 5 prompt skill definitions |
| `mcp/transport.py` | Docstring only | Transport configuration (stdio + streamable-http) |
| `mcp/github_client.py` | Docstring only | GitHub MCP composition client |
| `mcp/tools/__init__.py` | Docstring only | Tool registration helper |
| `mcp/resources/__init__.py` | Docstring only | Resource registration helper |

I seguenti modelli sono **già definiti** in Phase 1 e verranno utilizzati:

| Modello | File | Utilizzo Phase 7 |
|---------|------|-----------------|
| `SessionState` | `models/session.py` | Session persistence |
| `SessionConfig` | `models/session.py` | Per-session configuration overrides |
| `SessionStatus` | `models/session.py` | Session lifecycle states |
| `ProgressInfo` | `models/session.py` | Progress notification structure |
| `MCPToolResult` | `models/agent.py` | Context-efficient output wrapper |
| `DiscoverySession` | `models/agent.py` | Aggregated session view |
| `MCPToolSpec` | `models/mcp_spec.py` | Tool specification metadata |
| `AgentWorkflowConfig` | `models/mcp_spec.py` | Workflow definitions |
| `WorkflowStep` | `models/mcp_spec.py` | Workflow step definitions |
| `MCPSettings` | `config.py` | MCP configuration (transport, host, port, etc.) |

---

## 6) Configurazione — MCPSettings

`MCPSettings` è già definito in `config.py` (Phase 0). Sarà esteso:

```python
class MCPSettings(BaseSettings):
    """MCP server settings."""

    model_config = SettingsConfigDict(
        env_prefix="GHDISC_MCP_",
        env_file=".env",
    )

    transport: str = Field(default="stdio", description="MCP transport: stdio or http")
    host: str = Field(default="127.0.0.1", description="MCP HTTP host")
    port: int = Field(default=8080, description="MCP HTTP port")
    max_context_tokens: int = Field(default=2000, description="Max tokens per tool invocation output")
    session_backend: str = Field(default="sqlite", description="Session backend: sqlite or redis")
    read_only: bool = Field(default=True, description="Read-only mode for analysis pipelines")

    # --- Nuovi campi Phase 7 ---
    session_store_path: str = Field(
        default=".ghdisc/sessions.db",
        description="SQLite database path for session persistence",
    )
    enabled_toolsets: list[str] = Field(
        default_factory=lambda: ["discovery", "screening", "assessment", "ranking", "session"],
        description="Enabled MCP tool categories",
    )
    exclude_tools: list[str] = Field(
        default_factory=list,
        description="Specific tool names to exclude",
    )
    json_response: bool = Field(
        default=True,
        description="Use JSON structured content for tool responses",
    )
    stateless_http: bool = Field(
        default=False,
        description="Use stateless HTTP mode (for production deployment)",
    )
    streamable_http_path: str = Field(
        default="/mcp",
        description="Path for streamable HTTP transport endpoint",
    )
```

---

## 7) Task 7.1 — MCP Server Setup (FastMCP)

### mcp/server.py

FastMCP server factory con lifespan management tipizzato.

```python
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import structlog
from mcp.server.fastmcp import FastMCP

from github_discovery.config import Settings
from github_discovery.discovery.orchestrator import DiscoveryOrchestrator
from github_discovery.discovery.pool import PoolManager
from github_discovery.screening.orchestrator import ScreeningOrchestrator
from github_discovery.assessment.orchestrator import AssessmentOrchestrator
from github_discovery.scoring.engine import ScoringEngine
from github_discovery.scoring.ranker import Ranker
from github_discovery.scoring.feature_store import FeatureStore

logger = structlog.get_logger("github_discovery.mcp.server")


@dataclass
class AppContext:
    """Typed application context for MCP server lifespan.

    Provides all services needed by MCP tools via ctx.request_context.lifespan_context.
    """

    settings: Settings
    session_manager: SessionManager
    discovery_orch: DiscoveryOrchestrator
    screening_orch: ScreeningOrchestrator
    assessment_orch: AssessmentOrchestrator
    scoring_engine: ScoringEngine
    ranker: Ranker
    pool_manager: PoolManager
    feature_store: FeatureStore


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage MCP server lifecycle with type-safe context."""
    settings = Settings()
    logger.info("mcp_server_starting", transport=settings.mcp.transport)

    # Initialize session manager
    session_manager = SessionManager(settings.mcp.session_store_path)
    await session_manager.initialize()

    # Initialize orchestrators (reuse same pattern as API lifespan in Phase 6)
    pool_manager = PoolManager()
    discovery_orch = DiscoveryOrchestrator(settings, pool_manager)
    screening_orch = ScreeningOrchestrator(settings)
    assessment_orch = AssessmentOrchestrator(settings)
    scoring_engine = ScoringEngine()
    ranker = Ranker(settings.scoring)
    feature_store = FeatureStore()

    try:
        yield AppContext(
            settings=settings,
            session_manager=session_manager,
            discovery_orch=discovery_orch,
            screening_orch=screening_orch,
            assessment_orch=assessment_orch,
            scoring_engine=scoring_engine,
            ranker=ranker,
            pool_manager=pool_manager,
            feature_store=feature_store,
        )
    finally:
        await session_manager.close()
        await feature_store.close()
        logger.info("mcp_server_stopped")


def create_server(settings: Settings | None = None) -> FastMCP:
    """Create and configure the FastMCP server instance.

    Args:
        settings: Optional settings override. If None, loads from env.

    Returns:
        Configured FastMCP server with all tools, resources, and prompts registered.
    """
    _settings = settings or Settings()

    mcp = FastMCP(
        "github-discovery",
        json_response=_settings.mcp.json_response,
        lifespan=app_lifespan,
    )

    # Register tools, resources, and prompts
    register_all_tools(mcp, _settings)
    register_all_resources(mcp)
    register_all_prompts(mcp)

    return mcp


def serve(settings: Settings | None = None) -> None:
    """Start the MCP server with configured transport.

    Entry point for CLI: `python -m github_discovery.mcp serve`
    """
    _settings = settings or Settings()
    server = create_server(_settings)

    if _settings.mcp.transport == "stdio":
        server.run(transport="stdio")
    elif _settings.mcp.transport == "http":
        server.run(
            transport="streamable-http",
            host=_settings.mcp.host,
            port=_settings.mcp.port,
            streamable_http_path=_settings.mcp.streamable_http_path,
            stateless_http=_settings.mcp.stateless_http,
            json_response=_settings.mcp.json_response,
        )
    else:
        msg = f"Unknown MCP transport: {_settings.mcp.transport}"
        raise ValueError(msg)
```

### Helper: ottenere AppContext dai tool handlers

```python
from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession


def get_app_context(ctx: Context[ServerSession, AppContext]) -> AppContext:
    """Extract typed AppContext from MCP Context."""
    return ctx.request_context.lifespan_context
```

---

## 8) Task 7.2 — MCP Tools: Discovery

### mcp/tools/discovery.py

3 tool: `discover_repos`, `get_candidate_pool`, `expand_seeds`.

```python
from __future__ import annotations

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from github_discovery.mcp.output_format import format_tool_result
from github_discovery.mcp.progress import report_discovery_progress
from github_discovery.mcp.server import AppContext, get_app_context
from github_discovery.mcp.session import SessionManager


def register_discovery_tools(mcp: FastMCP) -> None:
    """Register discovery MCP tools."""

    @mcp.tool()
    async def discover_repos(
        query: str,
        channels: list[str] | None = None,
        max_candidates: int = 50,
        session_id: str | None = None,
        ctx: Context[ServerSession, AppContext] | None = None,
    ) -> dict[str, object]:
        """Find candidate repositories matching a query across multiple channels.

        Returns a summary of discovered candidates with discovery_score.
        Use get_candidate_pool for detailed filtering and sorting.

        Args:
            query: Search query for repositories (e.g., "static analysis python")
            channels: Discovery channels to use (default: search, registry, curated)
            max_candidates: Maximum candidates to discover (default: 50)
            session_id: Optional session ID for workflow continuity
        """
        app_ctx = get_app_context(ctx)
        session_mgr = app_ctx.session_manager

        # Resolve or create session
        session = await session_mgr.get_or_create(session_id, name="discovery")

        if ctx:
            await ctx.info("Starting discovery", extra={"query": query, "channels": channels})

        # Call DiscoveryOrchestrator
        result = await app_ctx.discovery_orch.discover(
            query=query,
            channels=channels or app_ctx.settings.discovery.default_channels,
            max_candidates=max_candidates,
        )

        # Update session
        session.pool_ids.append(result.pool_id)
        session.discovered_repo_count += result.total_count
        session.status = SessionStatus.SCREENING if session.status == SessionStatus.CREATED else session.status
        await session_mgr.update(session)

        # Progress notification
        if ctx:
            await ctx.report_progress(1.0, 1.0, f"Discovered {result.total_count} candidates")

        return format_tool_result(
            summary=f"Discovered {result.total_count} candidates across {len(result.channels_used)} channels",
            data={
                "pool_id": result.pool_id,
                "total_candidates": result.total_count,
                "channels_used": result.channels_used,
                "top_5": [  # Summary-first: only top 5
                    {"repo": c.full_name, "discovery_score": round(c.discovery_score, 2)}
                    for c in result.candidates[:5]
                ],
            },
            references={
                "pool": f"get_candidate_pool(pool_id='{result.pool_id}')",
                "screen": f"screen_candidates(pool_id='{result.pool_id}', gate_level='both')",
            },
            session_id=session.session_id,
        )

    @mcp.tool()
    async def get_candidate_pool(
        pool_id: str,
        sort_by: str = "discovery_score",
        limit: int = 20,
        offset: int = 0,
        ctx: Context[ServerSession, AppContext] | None = None,
    ) -> dict[str, object]:
        """Get candidates from a pool with filtering and sorting.

        Args:
            pool_id: Candidate pool ID from discover_repos
            sort_by: Sort field (discovery_score, name, stars)
            limit: Max candidates to return (default: 20)
            offset: Pagination offset
        """
        app_ctx = get_app_context(ctx)
        pool = await app_ctx.pool_manager.get_pool(pool_id)

        if not pool:
            return format_tool_result(success=False, error_message=f"Pool {pool_id} not found")

        candidates = pool.candidates[offset : offset + limit]
        return format_tool_result(
            summary=f"Pool {pool_id}: {pool.total_count} candidates, showing {len(candidates)}",
            data={
                "pool_id": pool_id,
                "total_count": pool.total_count,
                "candidates": [
                    {
                        "repo": c.full_name,
                        "discovery_score": round(c.discovery_score, 2),
                        "language": c.language,
                        "stars": c.stars,
                    }
                    for c in candidates
                ],
            },
            detail_available_via=f"get_candidate_pool(pool_id='{pool_id}', limit={pool.total_count})",
        )

    @mcp.tool()
    async def expand_seeds(
        seed_urls: list[str],
        expansion_strategy: str = "co_contributor",
        max_depth: int = 2,
        session_id: str | None = None,
        ctx: Context[ServerSession, AppContext] | None = None,
    ) -> dict[str, object]:
        """Expand from seed repository URLs to discover related repos.

        Args:
            seed_urls: List of known repository URLs as starting points
            expansion_strategy: Strategy (co_contributor, org_adjacency, co_dependency)
            max_depth: Maximum expansion depth (default: 2)
            session_id: Optional session ID for workflow continuity
        """
        app_ctx = get_app_context(ctx)
        session = await app_ctx.session_manager.get_or_create(session_id, name="seed-expansion")

        result = await app_ctx.discovery_orch.expand_seeds(
            seed_urls=seed_urls,
            strategy=expansion_strategy,
            max_depth=max_depth,
        )

        session.pool_ids.append(result.pool_id)
        session.discovered_repo_count += result.total_count
        await app_ctx.session_manager.update(session)

        return format_tool_result(
            summary=f"Expanded {len(seed_urls)} seeds into {result.total_count} candidates",
            data={
                "pool_id": result.pool_id,
                "seed_count": len(seed_urls),
                "total_candidates": result.total_count,
                "strategy": expansion_strategy,
            },
            session_id=session.session_id,
        )
```

---

## 9) Task 7.3 — MCP Tools: Screening

### mcp/tools/screening.py

3 tool: `screen_candidates`, `get_shortlist`, `quick_screen`.

```python
def register_screening_tools(mcp: FastMCP) -> None:
    """Register screening MCP tools."""

    @mcp.tool()
    async def screen_candidates(
        pool_id: str,
        gate_level: str = "both",
        min_gate1_score: float | None = None,
        min_gate2_score: float | None = None,
        session_id: str | None = None,
        ctx: Context[ServerSession, AppContext] | None = None,
    ) -> dict[str, object]:
        """Screen candidate repositories at specified gate level(s).

        Progressive deepening: run Gate 1, Gate 2, or both. Agent decides
        thresholds and depth.

        Args:
            pool_id: Candidate pool ID to screen
            gate_level: Screening level — "1", "2", or "both" (default: "both")
            min_gate1_score: Override Gate 1 threshold (default: from config)
            min_gate2_score: Override Gate 2 threshold (default: from config)
            session_id: Optional session ID for workflow continuity
        """
        app_ctx = get_app_context(ctx)
        session = await app_ctx.session_manager.get_or_create(session_id)

        # Resolve thresholds (agent-driven policy)
        gate1_threshold = min_gate1_score or app_ctx.settings.screening.min_gate1_score
        gate2_threshold = min_gate2_score or app_ctx.settings.screening.min_gate2_score

        # Call ScreeningOrchestrator
        results = await app_ctx.screening_orch.screen_pool(
            pool_id=pool_id,
            gate_level=gate_level,
            gate1_threshold=gate1_threshold,
            gate2_threshold=gate2_threshold,
        )

        # Update session
        session.screened_repo_count += results.total_screened
        await app_ctx.session_manager.update(session)

        # Progress notification
        if ctx:
            passed = results.gate1_passed if gate_level == "1" else results.gate2_passed
            total = results.total_screened
            await ctx.report_progress(1.0, 1.0, f"Screened {total} candidates, {passed} passed")

        return format_tool_result(
            summary=(
                f"Screened {results.total_screened} candidates: "
                f"{results.gate1_passed} passed Gate 1, {results.gate2_passed} passed Gate 2"
            ),
            data={
                "pool_id": pool_id,
                "total_screened": results.total_screened,
                "gate1_passed": results.gate1_passed,
                "gate2_passed": results.gate2_passed,
                "gate_level": gate_level,
                "shortlist_top_5": results.top_5_summary,
            },
            references={
                "shortlist": f"get_shortlist(pool_id='{pool_id}')",
                "assess": f"deep_assess(repo_urls=[...], session_id='{session.session_id}')",
            },
            session_id=session.session_id,
        )

    @mcp.tool()
    async def get_shortlist(
        pool_id: str,
        min_score: float = 0.5,
        domain: str | None = None,
        limit: int = 20,
        ctx: Context[ServerSession, AppContext] | None = None,
    ) -> dict[str, object]:
        """Get shortlisted candidates that passed screening.

        Args:
            pool_id: Candidate pool ID
            min_score: Minimum composite score (default: 0.5)
            domain: Filter by domain type (e.g., "library", "cli")
            limit: Max results to return (default: 20)
        """
        # ... similar pattern: get shortlist from screening_orch

    @mcp.tool()
    async def quick_screen(
        repo_url: str,
        gate_levels: str = "1",
        ctx: Context[ServerSession, AppContext] | None = None,
    ) -> dict[str, object]:
        """Quick quality check on a single repository.

        Fast screening without pool context. Useful for ad-hoc checks.

        Args:
            repo_url: GitHub repository URL (e.g., "https://github.com/owner/repo")
            gate_levels: Which gates to run — "1" or "1,2" (default: "1")
        """
        # ... calls screening_orch directly on single repo
```

---

## 10) Task 7.4 — MCP Tools: Assessment

### mcp/tools/assessment.py

3 tool: `deep_assess`, `quick_assess`, `get_assessment`.

```python
def register_assessment_tools(mcp: FastMCP) -> None:
    """Register assessment MCP tools."""

    @mcp.tool()
    async def deep_assess(
        repo_urls: list[str],
        dimensions: list[str] | None = None,
        budget_tokens: int | None = None,
        session_id: str | None = None,
        ctx: Context[ServerSession, AppContext] | None = None,
    ) -> dict[str, object]:
        """Deep LLM assessment of top candidates (Gate 3).

        HARD GATE ENFORCEMENT (Blueprint §16.5): Only repos that passed
        Gate 1+2 can be deep-assessed. Returns error for unqualified repos.

        Args:
            repo_urls: Repository URLs to assess
            dimensions: Subset of dimensions to evaluate (default: all 8)
            budget_tokens: Override token budget for this assessment
            session_id: Optional session ID for workflow continuity
        """
        app_ctx = get_app_context(ctx)
        session = await app_ctx.session_manager.get_or_create(session_id)

        # Hard gate enforcement: verify candidates passed Gate 1+2
        qualified, rejected = await app_ctx.screening_orch.verify_gate_pass(repo_urls)
        if rejected:
            return format_tool_result(
                success=False,
                error_message=(
                    f"Hard gate violation: {len(rejected)} repos have not passed Gate 1+2. "
                    f"Run screen_candidates first. Rejected: {rejected[:5]}"
                ),
            )

        # Budget control
        token_budget = budget_tokens or session.config.max_tokens_per_repo * len(qualified)

        # Progress notifications during assessment
        if ctx:
            await ctx.report_progress(0.0, len(qualified), "Starting deep assessment...")

        results = []
        for i, repo_url in enumerate(qualified):
            result = await app_ctx.assessment_orch.assess_single(
                repo_url=repo_url,
                dimensions=dimensions,
                budget_tokens=token_budget // len(qualified),
            )
            results.append(result)

            if ctx:
                await ctx.report_progress(
                    i + 1,
                    len(qualified),
                    f"Assessed {i + 1}/{len(qualified)} repos",
                )

        # Update session
        session.assessed_repo_count += len(results)
        await app_ctx.session_manager.update(session)

        return format_tool_result(
            summary=f"Deep assessed {len(results)} repos, {sum(1 for r in results if r.gate3_pass)} passed Gate 3",
            data={
                "total_assessed": len(results),
                "gate3_passed": sum(1 for r in results if r.gate3_pass),
                "top_5": [
                    {
                        "repo": r.repo_url,
                        "overall_score": round(r.overall_score, 2),
                        "confidence": round(r.confidence, 2),
                    }
                    for r in sorted(results, key=lambda x: x.overall_score, reverse=True)[:5]
                ],
            },
            references={
                "cached": f"get_assessment(repo_url='<url>')",
                "rank": f"rank_repos(session_id='{session.session_id}')",
            },
            session_id=session.session_id,
        )

    @mcp.tool()
    async def quick_assess(
        repo_url: str,
        dimensions: list[str] | None = None,
        ctx: Context[ServerSession, AppContext] | None = None,
    ) -> dict[str, object]:
        """Quick assessment on a subset of dimensions.

        Lower cost than deep_assess. Does not require Gate 1+2 pass
        (uses heuristic fallback for non-LLM dimensions).

        Args:
            repo_url: GitHub repository URL
            dimensions: Subset of dimensions (e.g., ["code_quality", "testing"])
        """
        # ... calls assessment_orch with limited dimensions

    @mcp.tool()
    async def get_assessment(
        repo_url: str,
        session_id: str | None = None,
        ctx: Context[ServerSession, AppContext] | None = None,
    ) -> dict[str, object]:
        """Get cached assessment result for a repository.

        Avoids expensive recalculation. Returns None if no cached result.

        Args:
            repo_url: GitHub repository URL
            session_id: Optional session ID for session-scoped cache
        """
        # ... looks up from assessment_orch cache or feature_store
```

---

## 11) Task 7.5 — MCP Tools: Ranking & Explainability

### mcp/tools/ranking.py

3 tool: `rank_repos`, `explain_repo`, `compare_repos`.

```python
def register_ranking_tools(mcp: FastMCP) -> None:
    """Register ranking and explainability MCP tools."""

    @mcp.tool()
    async def rank_repos(
        domain: str | None = None,
        min_confidence: float = 0.3,
        min_value_score: float = 0.0,
        max_results: int = 20,
        session_id: str | None = None,
        ctx: Context[ServerSession, AppContext] | None = None,
    ) -> dict[str, object]:
        """Rank repositories using anti-star bias scoring.

        Intra-domain ranking: repos are ranked within their domain.
        Hidden gems (low stars, high quality) rank above popular mediocrity.

        Args:
            domain: Domain type for ranking (e.g., "library", "cli")
            min_confidence: Minimum confidence to include (default: 0.3)
            min_value_score: Minimum value score filter (default: 0.0)
            max_results: Max results to return (default: 20)
            session_id: Optional session ID for workflow continuity
        """
        app_ctx = get_app_context(ctx)

        # Load scored repos from feature store / assessment results
        scored_repos = await app_ctx.feature_store.get_scored_repos(
            session_id=session_id,
            domain=domain,
            min_confidence=min_confidence,
        )

        # Rank
        ranked = await app_ctx.ranker.rank(
            scored_repos=scored_repos,
            domain=domain,
            max_results=max_results,
        )

        # Filter by value score
        filtered = [r for r in ranked if r.value_score >= min_value_score]

        return format_tool_result(
            summary=f"Ranked {len(filtered)} repos in domain '{domain or 'all'}'",
            data={
                "domain": domain,
                "total_ranked": len(filtered),
                "hidden_gems": sum(1 for r in filtered if r.is_hidden_gem),
                "top_10": [
                    {
                        "repo": r.repo.full_name,
                        "value_score": round(r.value_score, 3),
                        "quality_score": round(r.quality_score, 2),
                        "stars": r.repo.stars,
                        "is_hidden_gem": r.is_hidden_gem,
                    }
                    for r in filtered[:10]
                ],
            },
            references={
                "explain": "explain_repo(repo_url='<url>', detail_level='full')",
                "compare": "compare_repos(repo_urls=[...])",
            },
            session_id=session_id,
        )

    @mcp.tool()
    async def explain_repo(
        repo_url: str,
        detail_level: str = "summary",
        session_id: str | None = None,
        ctx: Context[ServerSession, AppContext] | None = None,
    ) -> dict[str, object]:
        """Generate explainability report for a repository.

        Summary-first by default. Use detail_level='full' for complete breakdown.

        Args:
            repo_url: GitHub repository URL
            detail_level: "summary" or "full" (default: "summary")
            session_id: Optional session ID
        """
        # ... calls ExplainabilityGenerator

    @mcp.tool()
    async def compare_repos(
        repo_urls: list[str],
        dimensions: list[str] | None = None,
        session_id: str | None = None,
        ctx: Context[ServerSession, AppContext] | None = None,
    ) -> dict[str, object]:
        """Compare repositories side-by-side on specified dimensions.

        Emits cross-domain warning when repos span different domains.

        Args:
            repo_urls: Repository URLs to compare (2-5 recommended)
            dimensions: Dimensions to compare (default: all scored)
            session_id: Optional session ID
        """
        # ... loads scores, generates comparison matrix, cross-domain guard
```

---

## 12) Task 7.6 — MCP Tools: Session Management

### mcp/tools/session.py

4 tool: `create_session`, `get_session`, `list_sessions`, `export_session`.

```python
def register_session_tools(mcp: FastMCP) -> None:
    """Register session management MCP tools."""

    @mcp.tool()
    async def create_session(
        name: str = "",
        config_overrides: dict[str, object] | None = None,
        ctx: Context[ServerSession, AppContext] | None = None,
    ) -> dict[str, object]:
        """Start a discovery session for cross-workflow state management.

        Sessions enable progressive deepening: discover in one invocation,
        screen in the next, assess in a third — all sharing the same session.

        Args:
            name: Human-readable session name
            config_overrides: Override session thresholds, budget, domains
        """
        app_ctx = get_app_context(ctx)
        config = SessionConfig(**(config_overrides or {}))
        session = await app_ctx.session_manager.create(name=name, config=config)

        return format_tool_result(
            summary=f"Created session '{name}' ({session.session_id})",
            data={
                "session_id": session.session_id,
                "name": session.name,
                "status": session.status,
                "config": session.config.model_dump(),
            },
            references={
                "discover": f"discover_repos(query='...', session_id='{session.session_id}')",
            },
            session_id=session.session_id,
        )

    @mcp.tool()
    async def get_session(
        session_id: str,
        ctx: Context[ServerSession, AppContext] | None = None,
    ) -> dict[str, object]:
        """Get session state, progress, and results.

        For resuming interrupted workflows or checking session progress.

        Args:
            session_id: Session identifier
        """
        app_ctx = get_app_context(ctx)
        session = await app_ctx.session_manager.get(session_id)

        if not session:
            return format_tool_result(success=False, error_message=f"Session {session_id} not found")

        discovery_session = DiscoverySession(
            session_id=session.session_id,
            name=session.name,
            status=session.status,
            pool_ids=session.pool_ids,
            total_discovered=session.discovered_repo_count,
            total_screened=session.screened_repo_count,
            total_assessed=session.assessed_repo_count,
        )

        return discovery_session.to_mcp_result().model_dump()

    @mcp.tool()
    async def list_sessions(
        status: str | None = None,
        limit: int = 10,
        ctx: Context[ServerSession, AppContext] | None = None,
    ) -> dict[str, object]:
        """List active or completed sessions.

        Args:
            status: Filter by status (created, screening, assessing, completed)
            limit: Max sessions to return (default: 10)
        """
        # ... queries session_manager

    @mcp.tool()
    async def export_session(
        session_id: str,
        format: str = "json",
        ctx: Context[ServerSession, AppContext] | None = None,
    ) -> dict[str, object]:
        """Export session results in JSON, CSV, or Markdown format.

        Args:
            session_id: Session identifier
            format: Export format — "json", "csv", or "markdown"
        """
        # ... loads session + associated results, formats output
```

---

## 13) Task 7.7 — MCP Resources

### mcp/resources/*.py

4 resources con URI template parameters.

```python
# mcp/resources/repo_score.py
@mcp.resource("repo://{owner}/{name}/score")
async def get_repo_score(owner: str, name: str) -> dict[str, object]:
    """Get the score for a specific repository.

    URI pattern: repo://owner/repo-name/score
    """
    repo_url = f"https://github.com/{owner}/{name}"
    # Load from FeatureStore
    features = await feature_store.get(repo_url)
    return features or {"error": f"No score found for {owner}/{name}"}


# mcp/resources/pool_candidates.py
@mcp.resource("pool://{pool_id}/candidates")
async def get_pool_candidates_resource(pool_id: str) -> dict[str, object]:
    """Get candidates in a pool."""
    pool = await pool_manager.get_pool(pool_id)
    return pool or {"error": f"Pool {pool_id} not found"}


# mcp/resources/domain_ranking.py
@mcp.resource("rank://{domain}/top")
async def get_domain_top_ranking(domain: str) -> dict[str, object]:
    """Get top-ranked repos for a domain."""
    ranked = await ranker.get_top(domain=domain, limit=10)
    return {"domain": domain, "top_repos": ranked}


# mcp/resources/session_status.py
@mcp.resource("session://{session_id}/status")
async def get_session_status_resource(session_id: str) -> dict[str, object]:
    """Get session state."""
    session = await session_manager.get(session_id)
    return session or {"error": f"Session {session_id} not found"}
```

---

## 14) Task 7.8 — MCP Prompts (Agent Skill Definitions)

### mcp/prompts.py

5 prompt skill definitions (Blueprint §21.7). Ogni prompt guida l'agente attraverso un workflow multi-step strutturato.

```python
from mcp.server.fastmcp import FastMCP


def register_all_prompts(mcp: FastMCP) -> None:
    """Register all MCP prompt skill definitions."""

    @mcp.prompt()
    def discover_underrated(
        query: str,
        domain: str = "",
        max_candidates: int = 100,
    ) -> str:
        """Find technically excellent repos that are underrated by star count.

        This skill guides you through a 5-step progressive deepening workflow:
        discover → screen → deep assess → rank → explain.

        Args:
            query: What to search for (e.g., "python static analysis")
            domain: Domain focus (e.g., "library", "cli", "ml_lib")
            max_candidates: How many candidates to discover (default: 100)
        """
        return f"""You are looking for technically excellent GitHub repositories
that are underrated by star count. Follow this workflow:

**Step 1: Discover** — Create a session and discover candidates:
- create_session(name="underrated-{query}")
- discover_repos(query="{query}", max_candidates={max_candidates}, session_id=<from_above>)

**Step 2: Screen** — Progressive screening through Gate 1 and Gate 2:
- screen_candidates(pool_id=<from_discover>, gate_level="both", session_id=<session_id>)

**Step 3: Deep Assess** — Evaluate top candidates (only repos that passed Gate 1+2):
- deep_assess(repo_urls=<top_10_from_shortlist>, session_id=<session_id>)

**Step 4: Rank** — Anti-star bias ranking to find hidden gems:
- rank_repos(domain="{domain}", max_results=20, session_id=<session_id>)

**Step 5: Explain** — Understand why top repos scored high:
- explain_repo(repo_url=<top_repo>, detail_level="full", session_id=<session_id>)

Key principle: Stars are context only. The value_score (quality_score / log10(stars + 10))
identifies repos that are technically excellent but not yet widely known.
"""

    @mcp.prompt()
    def quick_quality_check(repo_url: str) -> str:
        """Quick quality check on a specific repository.

        Args:
            repo_url: GitHub repository URL to check
        """
        return f"""Perform a quick quality check on: {repo_url}

1. quick_screen(repo_url="{repo_url}", gate_levels="1,2")
2. If passed, quick_assess(repo_url="{repo_url}", dimensions=["code_quality", "testing", "security"])
3. Summarize findings: what's good, what needs improvement
"""

    @mcp.prompt()
    def compare_for_adoption(
        repo_urls: str,
        key_dimensions: str = "code_quality,architecture,testing,maintenance",
    ) -> str:
        """Compare multiple repos for an adoption decision.

        Args:
            repo_urls: Comma-separated repository URLs
            key_dimensions: Comma-separated dimensions to evaluate
        """
        return f"""Compare these repositories for adoption: {repo_urls}

1. Screen each: quick_screen(repo_url=<url>) for each repo
2. Assess key dimensions: quick_assess(repo_url=<url>, dimensions=[{key_dimensions}])
3. Compare: compare_repos(repo_urls=[{repo_urls}], dimensions=[{key_dimensions}])
4. Provide a recommendation with rationale
"""

    @mcp.prompt()
    def domain_deep_dive(
        domain: str,
        query: str = "",
    ) -> str:
        """Deep exploration of a specific domain.

        Args:
            domain: Domain to explore (e.g., "web_framework", "data_tool")
            query: Optional specific search query
        """
        return f"""Deep exploration of domain: {domain}

1. Discover: discover_repos(query="{query or domain}", max_candidates=200)
2. Screen: screen_candidates(pool_id=<pool>, gate_level="both")
3. Deep assess: deep_assess(repo_urls=<top_15_from_shortlist>)
4. Domain rank: rank_repos(domain="{domain}", max_results=30)
5. For each hidden gem: explain_repo(repo_url=<url>, detail_level="full")
"""

    @mcp.prompt()
    def security_audit(repo_urls: str) -> str:
        """Security-first assessment of repositories.

        Args:
            repo_urls: Comma-separated repository URLs to audit
        """
        return f"""Perform a security-first assessment on: {repo_urls}

1. Heavy Gate 2 screening: screen_candidates with strict security thresholds
2. Security-focused assessment: deep_assess with dimensions ["security", "code_quality"]
3. For each repo: explain_repo(repo_url=<url>, detail_level="full")
4. Provide security report with risk ratings
"""
```

---

## 15) Task 7.9 — GitHub MCP Server Composition

### mcp/github_client.py

Questo modulo **non è un MCP client**, ma un modulo di configurazione e documentazione che facilita la composizione con il GitHub MCP Server ufficiale. GitHub Discovery **non delega** chiamate API a GitHub MCP — usa i propri client (`httpx`) per API calls. Il modulo serve per:

1. Documentare le regole di composizione (Blueprint §21.5)
2. Fornire template di configurazione per multi-MCP setup
3. Definire quali operazioni vanno delegate al GitHub MCP

```python
"""GitHub MCP Server composition module.

Provides configuration templates and rules for composing GitHub Discovery
with the official GitHub MCP Server in agent clients.

Rules (Blueprint §21.5):
1. No duplication: GitHub Discovery does not expose tools for standard
   operations (list repos, read files, create issues) already in GitHub MCP.
2. Minimal toolset: GitHub Discovery exposes only discovery/scoring tools.
3. Read-only default: both servers operate in read-only for analysis.
4. Shared auth: same GHDISC_GITHUB_TOKEN can be used for both servers.
"""

from __future__ import annotations

from github_discovery.config import Settings


def get_composition_config(settings: Settings, target: str = "kilo") -> dict[str, object]:
    """Generate MCP composition configuration for multi-server setup.

    Returns a dict suitable for serialization to MCP client config files.

    Args:
        settings: Application settings
        target: Target agent platform ("kilo", "opencode", "claude")

    Returns:
        MCP configuration dict with github + github-discovery servers.
    """
    if target == "kilo":
        return {
            "github": {
                "type": "remote",
                "url": "https://api.githubcopilot.com/mcp/",
                "headers": {
                    "X-MCP-Toolsets": "repos,issues,pull_requests,context",
                    "X-MCP-Readonly": "true",
                },
            },
            "github-discovery": {
                "type": "local",
                "command": ["python", "-m", "github_discovery.mcp", "serve", "--transport", "stdio"],
                "environment": {
                    "GHDISC_GITHUB_TOKEN": "{env:GITHUB_TOKEN}",
                    "GHDISC_SESSION_BACKEND": "sqlite",
                },
            },
        }
    elif target == "opencode":
        return {
            "github": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"},
            },
            "github-discovery": {
                "command": "python",
                "args": ["-m", "github_discovery.mcp", "serve", "--transport", "stdio"],
                "env": {
                    "GHDISC_GITHUB_TOKEN": "${GITHUB_TOKEN}",
                    "GHDISC_SESSION_BACKEND": "sqlite",
                },
            },
        }
    elif target == "claude":
        return {
            "github-discovery": {
                "command": "python",
                "args": ["-m", "github_discovery.mcp", "serve", "--transport", "stdio"],
                "env": {
                    "GHDISC_GITHUB_TOKEN": "${GITHUB_TOKEN}",
                },
            },
        }
    else:
        msg = f"Unknown target: {target}"
        raise ValueError(msg)


# Tools that GitHub Discovery does NOT provide (delegated to GitHub MCP)
DELEGATED_TOOLS = [
    "list_repos", "get_repo", "read_file", "create_issue",
    "list_issues", "get_pull_request", "create_pull_request",
    "search_code", "list_commits", "get_readme",
]

# Tools that GitHub Discovery provides (unique capability)
DISCOVERY_TOOLS = [
    "discover_repos", "get_candidate_pool", "expand_seeds",
    "screen_candidates", "get_shortlist", "quick_screen",
    "deep_assess", "quick_assess", "get_assessment",
    "rank_repos", "explain_repo", "compare_repos",
    "create_session", "get_session", "list_sessions", "export_session",
]
```

---

## 16) Task 7.10 — Progress Notifications & Streaming

### mcp/progress.py

Helper wrappers per `ctx.report_progress()` con formattazione specifica per fase.

```python
"""Progress notification helpers for MCP tools.

Wraps Context.report_progress() with domain-specific formatting.
Uses ctx.report_progress(progress, total, message) — NOT the deprecated
mcp.shared.progress module (removed in SDK v1.x).
"""

from __future__ import annotations

from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession

from github_discovery.mcp.server import AppContext


async def report_discovery_progress(
    ctx: Context[ServerSession, AppContext] | None,
    current: int,
    total: int,
    channel: str = "",
) -> None:
    """Report progress during discovery operations."""
    if ctx is None:
        return
    msg = f"Discovering via {channel}: {current} candidates found" if channel else f"Discovery: {current} candidates found"
    await ctx.report_progress(progress=current, total=total, message=msg)


async def report_screening_progress(
    ctx: Context[ServerSession, AppContext] | None,
    current: int,
    total: int,
    gate_level: str = "",
) -> None:
    """Report progress during screening operations."""
    if ctx is None:
        return
    msg = f"Screening ({gate_level}): {current}/{total} repos processed"
    await ctx.report_progress(progress=current, total=total, message=msg)


async def report_assessment_progress(
    ctx: Context[ServerSession, AppContext] | None,
    current: int,
    total: int,
    tokens_used: int = 0,
    budget_remaining: int = 0,
) -> None:
    """Report progress during deep assessment."""
    if ctx is None:
        return
    msg = f"Assessing: {current}/{total} repos complete"
    if tokens_used > 0:
        msg += f", {tokens_used} tokens used, {budget_remaining} remaining"
    await ctx.report_progress(progress=current, total=total, message=msg)
```

---

## 17) Task 7.11 — Context-Efficient Output Design

### mcp/output_format.py

Formatter per output context-efficient (Blueprint §21.8). Ogni tool restituisce summary-first.

```python
"""Context-efficient output formatting for MCP tools.

Blueprint §21.8: output parsimonioso di default, dettaglio on-demand.
Default: < 2000 tokens per invocation (configurable via GHDISC_MCP_MAX_CONTEXT_TOKENS).
"""

from __future__ import annotations

from github_discovery.models.agent import MCPToolResult


def format_tool_result(
    success: bool = True,
    summary: str = "",
    data: dict[str, object] | None = None,
    references: dict[str, str] | None = None,
    detail_available_via: str = "",
    session_id: str | None = None,
    error_message: str | None = None,
    confidence: float = 1.0,
) -> dict[str, object]:
    """Format an MCP tool result with context-efficient design.

    Returns a dict (not MCPToolResult directly) because FastMCP serializes
    the return value. Using dict ensures consistent JSON output.

    Design principles:
    - Summary-first: concise human-readable summary
    - Reference-based: IDs for on-demand detail retrieval
    - Confidence indicators: agent decides whether to deepen
    - Token budget: respect max_context_tokens limit
    """
    result = MCPToolResult(
        success=success,
        summary=summary[:500],  # Truncate summary to avoid context overflow
        data=data or {},
        references=references or {},
        detail_available_via=detail_available_via,
        session_id=session_id,
        error_message=error_message,
        confidence=confidence,
    )
    return result.model_dump()


def truncate_for_context(
    items: list[dict[str, object]],
    max_tokens: int = 2000,
    estimated_tokens_per_item: int = 50,
) -> tuple[list[dict[str, object]], bool]:
    """Truncate a list of items to fit within token budget.

    Returns:
        Tuple of (truncated_list, was_truncated)
    """
    max_items = max(1, max_tokens // estimated_tokens_per_item)
    if len(items) <= max_items:
        return items, False
    return items[:max_items], True
```

---

## 18) Task 7.12 — Transport & Security

### mcp/transport.py

Configurazione transport STDIO (default per agent locali) e streamable-http (per deployment).

```python
"""MCP transport configuration.

Supports:
- stdio: Default for Kilocode CLI, OpenCode, Claude Code local integration
- streamable-http: Recommended for production deployment (MCP SDK v1.x)
"""

from __future__ import annotations

import structlog
from mcp.server.fastmcp import FastMCP

from github_discovery.config import MCPSettings

logger = structlog.get_logger("github_discovery.mcp.transport")


def configure_transport(mcp: FastMCP, settings: MCPSettings) -> None:
    """Configure MCP server transport based on settings.

    This is called by server.serve() to start the server with the
    appropriate transport.

    Args:
        mcp: Configured FastMCP server instance
        settings: MCP transport settings
    """
    logger.info(
        "configuring_mcp_transport",
        transport=settings.transport,
        host=settings.host,
        port=settings.port,
    )


def get_transport_args(settings: MCPSettings) -> dict[str, object]:
    """Get transport arguments for mcp.run().

    Returns:
        Dict of keyword arguments for FastMCP.run()
    """
    if settings.transport == "stdio":
        return {"transport": "stdio"}
    elif settings.transport == "http":
        return {
            "transport": "streamable-http",
            "host": settings.host,
            "port": settings.port,
            "streamable_http_path": settings.streamable_http_path,
            "stateless_http": settings.stateless_http,
            "json_response": settings.json_response,
        }
    else:
        msg = f"Unknown MCP transport: {settings.transport}"
        raise ValueError(msg)
```

---

## 19) Task 7.13 — MCP Configuration per Ambiente

### mcp/config.py

Configurazione runtime, tool filtering, environment setup.

```python
"""GitHub Discovery MCP configuration helpers.

Runtime configuration for MCP server: tool filtering, environment setup,
and settings validation. Base MCPSettings is in config.py (Phase 0).
"""

from __future__ import annotations

import structlog
from mcp.server.fastmcp import FastMCP

from github_discovery.config import Settings

logger = structlog.get_logger("github_discovery.mcp.config")


def get_enabled_tools(settings: Settings) -> list[str]:
    """Get list of enabled MCP tools based on configuration.

    Respects GHDISC_MCP_ENABLED_TOOLSETS and GHDISC_MCP_EXCLUDE_TOOLS.
    """
    all_tools = [
        # Discovery
        "discover_repos", "get_candidate_pool", "expand_seeds",
        # Screening
        "screen_candidates", "get_shortlist", "quick_screen",
        # Assessment
        "deep_assess", "quick_assess", "get_assessment",
        # Ranking
        "rank_repos", "explain_repo", "compare_repos",
        # Session
        "create_session", "get_session", "list_sessions", "export_session",
    ]

    # Filter by enabled toolsets
    enabled_toolsets = set(settings.mcp.enabled_toolsets)
    exclude = set(settings.mcp.exclude_tools)

    # Map toolsets to tool names
    toolset_map = {
        "discovery": {"discover_repos", "get_candidate_pool", "expand_seeds"},
        "screening": {"screen_candidates", "get_shortlist", "quick_screen"},
        "assessment": {"deep_assess", "quick_assess", "get_assessment"},
        "ranking": {"rank_repos", "explain_repo", "compare_repos"},
        "session": {"create_session", "get_session", "list_sessions", "export_session"},
    }

    enabled = set[str]()
    for toolset in enabled_toolsets:
        if toolset in toolset_map:
            enabled.update(toolset_map[toolset])

    # Apply exclusions
    result = [t for t in all_tools if t in enabled and t not in exclude]

    logger.info("mcp_tools_configured", total=len(all_tools), enabled=len(result), excluded=len(exclude))
    return result


def should_register_tool(tool_name: str, settings: Settings) -> bool:
    """Check if a specific tool should be registered."""
    return tool_name in get_enabled_tools(settings)
```

---

## 20) Sequenza di implementazione — Waves

### Wave A — Foundation (Tasks 7.1 + 7.10 + 7.11 + 7.13 + 7.12)

**Obiettivo**: Infrastruttura base — server, lifespan, output format, progress, config, transport.

**File da rimpiazzare (stub → implementation)**:
1. `mcp/server.py` — FastMCP server factory + AppContext + lifespan
2. `mcp/output_format.py` — format_tool_result, truncate_for_context
3. `mcp/progress.py` — report_*_progress helpers
4. `mcp/config.py` — get_enabled_tools, should_register_tool
5. `mcp/transport.py` — configure_transport, get_transport_args
6. `mcp/session.py` — SessionManager (SQLite CRUD)
7. `config.py` — Extend MCPSettings with new fields

**File da creare**:
1. `mcp/tools/__init__.py` — register_all_tools() dispatcher
2. `mcp/resources/__init__.py` — register_all_resources() dispatcher
3. `tests/unit/mcp/conftest.py` — MCP test fixtures

**Test**: ~25 test
- `tests/unit/mcp/test_server.py` — Server creation, lifespan context
- `tests/unit/mcp/test_output_format.py` — format_tool_result, truncate
- `tests/unit/mcp/test_progress.py` — Progress notification helpers
- `tests/unit/mcp/test_config.py` — Tool filtering, enabled tools
- `tests/unit/mcp/test_session.py` — SessionManager CRUD
- `tests/unit/mcp/test_transport.py` — Transport arg configuration

**Verifica**: Server creato senza errori, SessionManager CRUD funzionante, output format valido, tool filtering corretto.

### Wave B — Tools: Discovery + Screening (Tasks 7.2 + 7.3)

**Obiettivo**: 6 MCP tools per discovery e screening.

**File da creare**:
1. `mcp/tools/discovery.py` — discover_repos, get_candidate_pool, expand_seeds
2. `mcp/tools/screening.py` — screen_candidates, get_shortlist, quick_screen

**Test**: ~25 test
- `tests/unit/mcp/tools/test_discovery.py` — 3 discovery tools
- `tests/unit/mcp/tools/test_screening.py` — 3 screening tools

**Verifica**: Tool registration OK, mock orchestrator invocato correttamente, output context-efficient, session_id propagato.

### Wave C — Tools: Assessment + Ranking + Session (Tasks 7.4 + 7.5 + 7.6)

**Obiettivo**: 10 MCP tools per assessment, ranking e session management.

**File da creare**:
1. `mcp/tools/assessment.py` — deep_assess, quick_assess, get_assessment
2. `mcp/tools/ranking.py` — rank_repos, explain_repo, compare_repos
3. `mcp/tools/session.py` — create_session, get_session, list_sessions, export_session

**Test**: ~35 test
- `tests/unit/mcp/tools/test_assessment.py` — 3 assessment tools + hard gate enforcement
- `tests/unit/mcp/tools/test_ranking.py` — 3 ranking tools
- `tests/unit/mcp/tools/test_session.py` — 4 session tools

**Verifica**: Hard gate enforcement in deep_assess, cross-domain warning in compare_repos, session CRUD, export format.

### Wave D — Resources + Prompts + Composition (Tasks 7.7 + 7.8 + 7.9)

**Obiettivo**: 4 resources, 5 prompts, GitHub MCP composition.

**File da creare**:
1. `mcp/resources/repo_score.py` — repo://{owner}/{name}/score
2. `mcp/resources/pool_candidates.py` — pool://{id}/candidates
3. `mcp/resources/domain_ranking.py` — rank://{domain}/top
4. `mcp/resources/session_status.py` — session://{id}/status
5. `mcp/prompts.py` — 5 prompt skill definitions
6. `mcp/github_client.py` — Composition config + DELEGATED/DISCOVERY_TOOLS

**Test**: ~25 test
- `tests/unit/mcp/resources/test_repo_score.py`
- `tests/unit/mcp/resources/test_pool_candidates.py`
- `tests/unit/mcp/resources/test_domain_ranking.py`
- `tests/unit/mcp/resources/test_session_status.py`
- `tests/unit/mcp/test_prompts.py` — Prompt registration and content
- `tests/unit/mcp/test_github_client.py` — Composition config generation

**Verifica**: Resources accessibili, prompts invocabili, composition config valida per 3 target (kilo, opencode, claude).

### Wave E — Integration & CLI Entry Point

**Obiettivo**: Server avviabile end-to-end, CLI integration, update `__main__.py`.

**File da aggiornare**:
1. `mcp/__init__.py` — Export `create_server`, `serve`
2. `__main__.py` — Add `mcp serve` subcommand support
3. `.kilo/mcp.json.template` — Update with verified config

**Test**: ~10 test
- `tests/integration/test_mcp_server.py` — Server startup/shutdown, tool listing
- `tests/agentic/test_mcp_client.py` — Basic MCP client integration test

**Verifica**: `python -m github_discovery.mcp serve --transport stdio` avvia senza errori. Tool listing ritorna 16 tools + 4 resources + 5 prompts.

---

## 21) Test plan

### Test files structure

```
tests/
├── unit/
│   └── mcp/
│       ├── conftest.py                    # FastMCP test fixtures, mock AppContext
│       ├── test_server.py                 # Server creation, lifespan, AppContext
│       ├── test_output_format.py          # format_tool_result, truncate_for_context
│       ├── test_progress.py               # Progress notification helpers
│       ├── test_config.py                 # Tool filtering, enabled tools
│       ├── test_session.py                # SessionManager CRUD
│       ├── test_transport.py              # Transport configuration
│       ├── test_prompts.py                # Prompt registration and content
│       ├── test_github_client.py          # Composition config
│       ├── tools/
│       │   ├── conftest.py                # Mock orchestrators, mock AppContext
│       │   ├── test_discovery.py          # 3 discovery tools
│       │   ├── test_screening.py          # 3 screening tools
│       │   ├── test_assessment.py         # 3 assessment tools + hard gate
│       │   ├── test_ranking.py            # 3 ranking tools
│       │   └── test_session.py            # 4 session tools
│       └── resources/
│           ├── conftest.py                # Mock feature store, pool manager
│           ├── test_repo_score.py
│           ├── test_pool_candidates.py
│           ├── test_domain_ranking.py
│           └── test_session_status.py
├── integration/
│   └── test_mcp_server.py                 # Server startup/shutdown, tool listing
└── agentic/
    └── test_mcp_client.py                 # Basic MCP client integration test
```

### Test approach

| Layer | Tool | Pattern |
|-------|------|---------|
| Tool handlers | `pytest-asyncio` + mock orchestrators | Verify orchestrator calls, output format, session propagation |
| SessionManager | In-memory SQLite (`:memory:`) | Direct CRUD testing |
| Progress helpers | Mock `Context` object | Verify report_progress calls |
| Output format | Direct function calls | Verify MCPToolResult serialization |
| Resources | Mock FastMCP + mock services | Verify URI template parsing, data loading |
| Prompts | Direct prompt function calls | Verify content contains workflow steps |
| Integration | FastMCP server start/stop | Verify tool/resource/prompt listing |
| Agentic | MCP client library | Tool invocation end-to-end (when available) |

### Key test scenarios

1. **Progressive deepening**: create_session → discover → screen(gate_level="1") → screen(gate_level="2") → deep_assess → rank → explain
2. **Hard gate enforcement**: deep_assess without Gate 1+2 → error
3. **Session cross-invocation**: create_session in call 1, discover with session_id in call 2
4. **Agent-driven policy**: screen_candidates with custom min_gate1_score=0.3
5. **Context efficiency**: tool output < 2000 tokens by default
6. **Cross-domain warning**: compare_repos with repos in different domains
7. **Session export**: JSON, CSV, Markdown format correctness
8. **Tool filtering**: exclude specific tools via config
9. **Progress notifications**: verify ctx.report_progress called during discovery/screening/assessment
10. **Composition config**: generate valid config for kilo, opencode, claude targets

### Coverage target

>80% su `mcp/` module, coerente con il target del progetto.

---

## 22) Criteri di accettazione

| Criterio | Misura | Target |
|----------|--------|--------|
| **FastMCP server operativo** | `create_server()` ritorna FastMCP instance | ✅ |
| **16 MCP tools registrati** | `mcp.list_tools()` ritorna 16 tools | ✅ |
| **4 MCP resources registrate** | `mcp.list_resources()` ritorna 4 resources | ✅ |
| **5 MCP prompts registrati** | `mcp.list_prompts()` ritorna 5 prompts | ✅ |
| **Progressive deepening** | Ogni gate invocabile singolarmente | ✅ |
| **Hard gate enforcement** | deep_assess senza Gate 1+2 → errore | ✅ |
| **Agent-driven policy** | Soglie configurabili per tool invocation | ✅ |
| **Session persistence** | CRUD cross-sessione via SQLite | ✅ |
| **Progress notifications** | ctx.report_progress chiamato durante operazioni lunghe | ✅ |
| **Context-efficient output** | Output default < 2000 token | ✅ |
| **Transport stdio** | `python -m github_discovery.mcp serve --transport stdio` funziona | ✅ |
| **Transport http** | `python -m github_discovery.mcp serve --transport http --port 8080` funziona | ✅ |
| **GitHub MCP composition** | Config generata per kilo, opencode, claude | ✅ |
| **Tool filtering** | exclude_tools rispettato | ✅ |
| **make ci verde** | ruff + mypy --strict + pytest | ✅ |
| **Test count** | ~120 nuovi test | ✅ |
| **Type safety** | mypy --strict 0 errori | ✅ |

---

## 23) Rischi e mitigazioni

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| **MCP SDK breaking changes** | Alto — integrazione fragile | Pin `mcp>=1.6,<2.0` in pyproject.toml, test con client reale in Phase 9 |
| **Context overflow per tool troppo verbosi** | Medio — agent dismiss tool per limite contesto | Context-efficient design (summary-first, reference-based, detail on-demand, truncate_for_context) |
| **Composizione con GitHub MCP non funzionante** | Medio — agent non può usare tool di scoperta + GitHub insieme | Test integrazione con multi-MCP in Phase 9, configurazione composizionale documentata |
| **Progress notifications non supportate da tutti i client** | Basso — agent non riceve aggiornamenti progressivi | Fallback a polling (tool `get_session`), documentation per client senza streaming |
| **Session SQLite contention in multi-session** | Basso — single-writer bottleneck | WAL mode, write-through singleton, evolvibile a Redis |
| **Orchestrator API incompatibilità** | Alto — tool handlers break | Type-safe AppContext, mock orchestrators nei test, interface contracts definiti |
| **Lifespan context non accessibile** | Alto — tool handlers non possono usare servizi | Verificato pattern FastMCP lifespan via Context7, `ctx.request_context.lifespan_context` |

---

## 24) Verifica Context7

| Libreria | Library ID | Pattern verificati |
|----------|-----------|-------------------|
| MCP Python SDK | `/modelcontextprotocol/python-sdk` | FastMCP setup (json_response, lifespan), @mcp.tool() con Context, @mcp.resource() con URI templates, @mcp.prompt() con argomenti, ctx.report_progress(progress, total, message), ctx.info/debug/warning/error(), transport stdio e streamable-http, structured output con Pydantic models, lifespan con @asynccontextmanager → AsyncIterator[AppContext], read_resource(), elicit() per user input |
| GitHub MCP Server | `/github/github-mcp-server` | X-MCP-Toolsets header, X-MCP-Readonly header, X-MCP-Lockdown header, dynamic-toolsets CLI flag, remote server JSON configuration |

### MCP SDK patterns verified (Context7)

1. **FastMCP setup**: `FastMCP("name", json_response=True, lifespan=app_lifespan)` — confirmed
2. **Tool definition**: `@mcp.tool()` with async functions, Pydantic return types for structured output
3. **Context parameter**: `ctx: Context[ServerSession, AppContext]` — logging, progress, read_resource, elicit
4. **Progress notifications**: `await ctx.report_progress(progress, total, message)` — NOT deprecated `mcp.shared.progress`
5. **Logging**: `await ctx.info/debug/warning/error()` with optional `extra={}` for structured data
6. **Resource templates**: `@mcp.resource("uri://{param}")` with URI path parameters
7. **Prompts**: `@mcp.prompt()` with typed arguments, returns string
8. **Lifespan**: `@asynccontextmanager async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]`
9. **Transport**: `mcp.run(transport="stdio")` or `mcp.run(transport="streamable-http", host=, port=, stateless_http=, json_response=)`
10. **Structured output**: Return Pydantic BaseModel from tool → automatic JSON schema + structured content

### GitHub MCP Server patterns verified (Context7)

1. **Remote configuration**: `{"type": "http", "url": "https://api.githubcopilot.com/mcp/", "headers": {"X-MCP-Toolsets": "repos,issues", "X-MCP-Readonly": "true"}}`
2. **Read-only mode**: `X-MCP-Readonly: true` header disables all non-read-only tools
3. **Lockdown mode**: `X-MCP-Lockdown: true` limits content to users with push access
4. **Dynamic toolsets**: `--dynamic-toolsets` flag enables runtime toolset discovery

---

*Stato documento: Draft v1 — Phase 7 Implementation Plan*
*Autore: General Manager (orchestrator)*
*Approvazione richiesta: Milestone M6 (HitL)*
