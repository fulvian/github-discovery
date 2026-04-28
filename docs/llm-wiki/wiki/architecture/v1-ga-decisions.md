---
Title: v1.0.0 GA Decisions & Wave G-N Outcomes
Topic: architecture
Sources: docs/plans/discovery_final_deployment_plan.md
Raw: docs/plans/discovery_final_deployment_plan.md
Updated: 2026-04-28
Confidence: high
---

# v1.0.0 GA Decisions & Wave G-N Outcomes

## Summary of Wave Implementation

The final production deployment plan (Waves G-O) transforms GitHub Discovery from
v0.3.0-beta to v1.0.0 GA. Below documents the decisions made during implementation.

**Current CI state**: 1773 tests passing, ruff clean, mypy --strict clean (145 files).

### Wave G — Empirical Validation

- **G4 — Anti-bias contract tests**: 28 tests enforcing all 10 INV invariants.
  - INV-1 through INV-10 from the philosophy preservation contract.
  - Uses Hypothesis property-based testing for star-neutrality invariants.
  - New `pytest.mark.invariant` marker for CI badge separation.
  - File: `tests/invariants/test_anti_bias_contract.py`
  - Acceptance: all 28 tests passing.

### Wave J — MCP Server GA Hardening

- **J2 — Health endpoint**: Custom `/health` route via `@mcp.custom_route`.
  - Returns `{"status": "ok", "version": "...", "service": "...", "transport": "..."}`
  - Deep mode via `?deep=true` includes fast doctor checks.
  
- **J4 — API key auth**: Bearer token validation via Starlette middleware.
  - Configurable via `GHDISC_MCP_API_KEYS` environment variable (comma-separated).
  - `GET /health` bypasses auth for monitoring.
  - Default: empty (no auth) for stdio/local development.

- **J5 — Graceful shutdown**: SIGTERM handler on POSIX systems.
  - Clone cleanup runs on shutdown (in addition to startup).
  - 30s drain period for in-flight tools.

- **J8 — Session pruning**: `SessionManager.prune()` via `json_extract` on SQLite.
  - Deletes sessions older than 30 days or idle for 7 days (configurable).
  - Runs on MCP server startup + via CLI `ghdisc db sessions` command.

### Wave K — Distribution

- **K1 — Version alignment**: Bumped from `0.1.0-alpha` to `0.3.0-beta`.
  - `src/github_discovery/__init__.py` and `pyproject.toml` in sync.
  
- **K2 — CLI aliases**: `github-discovery` and `github-discovery-mcp` console scripts.
  
- **K3 — PyPI release workflow**: GitHub Actions release pipeline.
  - Trusted Publisher (OIDC) for PyPI uploads.
  - Pre-release quality gate: lint, type-check, tests, invariant tests.
  - Multi-arch Docker build (amd64 + arm64) via buildx.

- **K4 — Dockerfile**: Multi-stage build with distroless runtime.
  - Stage 1: `python:3.13-slim` + `uv` for build.
  - Stage 2: `gcr.io/distroless/python3-debian12:nonroot` for runtime.
  - Entrypoint: MCP server over stdio.

### Wave L — Deployment

- **L1 — Reference configs**: UVX-based `.mcp.json.example` and `.kilo/mcp.json.example`.
  - Portable across machines (no absolute paths).
  - Available for both Claude Code (`.mcp.json.example`) and Kilocode (`.kilo/mcp.json.example`).

### Wave H — Discovery Robustness (all 7 tasks)

- **H1 — Adaptive activity filter**: Domain-aware `pushed:>` inactivity threshold. LANG_TOOL=365d, SECURITY_TOOL=90d, DEVOPS_TOOL=90d, default=180d. Override via `GHDISC_DISCOVERY_ACTIVITY_DAYS`.
- **H2 — Recency boost**: Repos pushed within 30 days get `discovery_score += 0.05` (capped at 1.0).
- **H3 — Curated channel resilience**: GitHub Topic search fallback (`topic:awesome-<lang>`) when no awesome list matches. In-memory cache with 24h TTL for parsed READMEs. `_MAX_CURATED_PER_LIST=200` cap.
- **H4 — Registry channels**: crates.io (`/api/v1/crates?q=...&sort=recent-updates`) and Maven Central (`search.maven.org/solrsearch/select`) endpoints added alongside existing PyPI/npm. All 4 registries run concurrently.
- **H6 — Auto-seed**: `DiscoveryQuery.auto_seed=True` runs a quick GitHub search to discover seed URLs when none provided.
- **H7 — Channel observability**: `ChannelResult.errors` field, per-channel structured logging, `DiscoveryResult.errors_per_channel`.

### Wave I — Screening & Assessment Resilience (partial)

- **I3 — Clone reuse**: `CloneManager` singleton provides refcounted shallow clones shared across Gate 2 (screening) and Gate 3 (repomix assessment). 60s grace period cleanup. Periodic background sweep. 6 tests.
- **I4 — OSV batch query**: Replaced per-package `GET /v1/query` with batch `POST /v1/querybatch` supporting up to 1000 packages per request (P95 ≤ 6s). Tenacity retry on 5xx. Auto-split batches exceeding 32 MiB payload. 38 tests.

### Wave N — Security Essentials

- **N1 — pip-audit**: CI step added to `.github/workflows/ci.yml`. Runs on every push/PR.
- **N4 — Token scope check**: `doctor` CLI inspects `X-OAuth-Scopes` header and warns if token grants more than `public_repo` scope.
- **N5 — SECURITY.md + CODEOWNERS**: Security policy with disclosure instructions. `.github/CODEOWNERS` with `@fulvio` as default owner for sensitive paths.

### Wave O — Documentation Essentials

- **O1 — README rewrite**: 60-second Quick Start with `uvx` command. Anti-bias philosophy section. Architecture overview (4-gate pipeline). Installation matrix (uvx/pip/Docker). Agent platform configs (Claude Code, Kilocode). Usage examples. MCP tools reference table.
- **O5 — CHANGELOG.md**: Conventional-commits style changelog covering v0.3.0-beta and v0.1.0-alpha releases.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| API-key auth instead of OAuth 2.1 | OAuth deferred to v1.1; API-key sufficient for v1.0 GA (most users use stdio) |
| SQLite-only session backend | Redis deferred to v1.1; SQLite sufficient for single-user |
| Distroless Docker image | Minimizes attack surface, ~80MB runtime |
| UVX-based config as default | Portable across machines, no venv setup needed |
| Stateless HTTP opt-in | Default remains stateful for session continuity; stateless for horizontal scaling |
| version 0.3.0-beta (not 1.0.0) | Reflects current state before final GA cut |
