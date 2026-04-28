# GitHub Discovery — Final Production Deployment Plan

## Goal

Bring GitHub Discovery from `v0.3.0-beta` to `v1.0.0` (GA) by implementing Waves G–O
from `docs/plans/discovery_final_deployment_plan.md`.

## Current State (2026-04-27)

- **1723 tests passing** (ruff clean, mypy --strict clean, 145 files)
- Version: `0.3.0-beta`
- MCP server with health endpoint, API key auth, graceful shutdown, session pruning
- Dockerfile, release workflow, reference configs
- Anti-bias invariant tests (28 tests, INV-1 through INV-10)
- Adaptive activity filter, recency boost, channel observability
- Clone reuse across Gate 2 + Gate 3

## Progress

### Wave G — Empirical Validation
| # | Task | Status | Notes |
|---|------|--------|-------|
| G4 | Anti-bias contract test suite | ✅ COMPLETE | 28 tests covering INV-1-10 |

### Wave H — Discovery Robustness
| # | Task | Status | Notes |
|---|------|--------|-------|
| H1 | Adaptive activity filter | ✅ COMPLETE | Domain-aware pushed:>; GHDISC_DISCOVERY_ACTIVITY_DAYS |
| H2 | Recency-channel injection | ✅ COMPLETE | +0.05 bonus for repos pushed within 30d |
| H3 | Curated channel resilience | ⬜ NOT STARTED | Markdown parser, cache, topic fallback |
| H4 | Registry channel: crates.io + Maven | ⬜ NOT STARTED | New RegistryAdapter protocol |
| H5 | Dependency channel: dependents | ⬜ NOT STARTED | /network/dependents scraping |
| H6 | Seed expansion: auto-seed | ⬜ NOT STARTED | query.auto_seed=True |
| H7 | Channel observability | ✅ COMPLETE | Structured logging per channel |

### Wave I — Screening & Assessment Resilience
| # | Task | Status | Notes |
|---|------|--------|-------|
| I3 | Clone reuse across Gate 2 + Gate 3 | ✅ COMPLETE | CloneManager singleton, 6 tests |
| I4 | OSV batch query adoption | ⬜ NOT STARTED | POST /v1/querybatch |
| I5 | Repomix accuracy & sampling | ⬜ NOT STARTED | Stratified sampling, tokenizer |

### Wave J — MCP Server GA Hardening
| # | Task | Status | Notes |
|---|------|--------|-------|
| J1 | Dual transport CI | ✅ COMPLETE | 5 HTTP transport tests |
| J2 | Health endpoint | ✅ COMPLETE | @mcp.custom_route("/health") |
| J3 | Stateless mode | ✅ COMPLETE | Settings.mcp.stateless_http |
| J4 | API key auth | ✅ COMPLETE | Bearer token middleware + 5 tests |
| J5 | Graceful shutdown | ✅ COMPLETE | SIGTERM + cleanup on shutdown |
| J8 | Session TTL + pruning | ✅ COMPLETE | SessionManager.prune() + CLI |

### Wave K — Distribution
| # | Task | Status | Notes |
|---|------|--------|-------|
| K1 | Version alignment | ✅ COMPLETE | 0.3.0-beta |
| K2 | Project scripts & entry points | ✅ COMPLETE | github-discovery, github-discovery-mcp |
| K3 | PyPI release workflow | ✅ COMPLETE | .github/workflows/release.yml |
| K4 | Docker image | ✅ COMPLETE | Dockerfile multi-stage distroless |

### Wave L — Deployment
| # | Task | Status | Notes |
|---|------|--------|-------|
| L1 | Reference configs | ✅ COMPLETE | .mcp.json.example, .kilo/mcp.json.example |

### Wave N — Security
| # | Task | Status | Notes |
|---|------|--------|-------|
| N1 | Dependency audit in CI | ⬜ | pip-audit, osv-scanner |
| N5 | SECURITY.md + CODEOWNERS | ⬜ | Repo root files |

### Wave O — Documentation
| # | Task | Status | Notes |
|---|------|--------|-------|
| O1 | README rewrite | ⬜ | Quick Start 60s |
| O5 | CHANGELOG.md | ⬜ | Conventional commits |
| O6 | Doctor UX polish | ⬜ | Rich table, --json |

## Next Priority
1. H3-H6: Discovery channel improvements
2. I4-I5: Screening performance (OSV batch, stratified sampling)
3. N1+N5: Security essentials (pip-audit, CODEOWNERS, SECURITY.md)
4. O1+O5: Documentation essentials
