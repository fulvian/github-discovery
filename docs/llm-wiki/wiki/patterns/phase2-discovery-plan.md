---
Title: Phase 2 Discovery Engine Implementation
Topic: patterns
Sources: Phase 2 implementation plan (docs/plans/phase2-implementation-plan.md); Foundation Blueprint §6, §8, §16.2, §18; Context7 verification (httpx, pytest-httpx, GitHub REST/GraphQL API)
Raw: [phase2-plan.md](../../../plans/phase2-implementation-plan.md); [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md)
Updated: 2026-04-22
Confidence: high
---

# Phase 2 Discovery Engine Implementation

## Status: COMPLETE

All 10 tasks (2.1–2.10) implemented and verified. 320 tests passing, `make ci` green.

## Implementation Summary

### Infrastructure (Phase A)

| Task | Module | Description | Tests |
|------|--------|-------------|-------|
| 2.1 | `github_client.py` | REST API client with Bearer auth, rate limit tracking, conditional requests (ETag/304), Link-header pagination, search-specific rate limits | 16 |
| 2.2 | `graphql_client.py` | GraphQL client with cursor-based pagination (first/after + pageInfo), cost monitoring, rate limit enforcement | 13 |
| 2.10 | `pool.py` | SQLite-backed pool persistence via aiosqlite, CRUD operations, status tracking, SELECT-before-INSERT dedup | 13 |

### Discovery Channels (Phase B & C)

| Task | Module | Description | Tests |
|------|--------|-------------|-------|
| 2.3 | `search_channel.py` | GitHub Search API with query builder (language, topic, pushed date, archived filter), sort by updated (anti-star bias) | 11 |
| 2.7 | `curated_channel.py` | Awesome-list README parser, base64 decode, markdown URL extraction, language→awesome-list mapping | 17 |
| 2.4 | `code_search_channel.py` | Code search with quality signal patterns (testing, CI/CD, security, documentation), strict 10 req/min rate limit | 13 |
| 2.6 | `registry_channel.py` | PyPI + npm registry search, GitHub URL extraction from package metadata, concurrent registry queries | 30 |
| 2.5 | `dependency_channel.py` | SBOM endpoint traversal, GitHub URL extraction from SPDX packages, seed exclusion, MVP dependents placeholder | 25 |
| 2.8 | `seed_expansion.py` | Org adjacency (org/user repos), co-contributor analysis, fork exclusion, multi-strategy dedup | 25 |

### Integration (Phase D)

| Task | Module | Description | Tests |
|------|--------|-------------|-------|
| 2.9 | `orchestrator.py` | Coordinates 6 channels with asyncio.gather, deduplicates by full_name, calculates discovery_score (breadth + channel quality bonuses), persists pool | 15 |

## Key Implementation Decisions

### Client Architecture
- `_BearerAuth(httpx.Auth)` subclass with `auth_flow` yielding `Generator[Request, Response, None]` (not `Iterator`) for mypy strict compatibility with httpx's base class
- HTTP status codes extracted to named constants (`_HTTP_FORBIDDEN = 403`, `_HTTP_NOT_MODIFIED = 304`) to satisfy ruff PLR2004
- `contextlib.suppress(ValueError, OSError)` replaces try/except/pass blocks (ruff SIM105)
- `response.json()` wrapped in `dict()` call to avoid `Any` return type (mypy no-any-return)

### Pool Persistence
- `INSERT OR IGNORE` silently succeeds with 0 rows affected — changed to explicit SELECT-before-INSERT for proper dedup counting
- `CandidatePool.total_count` is a `@property` (computed), NOT a constructor parameter

### Test Infrastructure
- `pytest-httpx` v0.36.2: `url__startswith` parameter does NOT exist — use exact `url=` matching or omit URL
- httpx `raise_for_status()` treats 304 as error — skip `raise_for_status()` for 304 responses
- Pydantic models with TYPE_CHECKING imports fail at runtime — use `# noqa: TC001` instead for runtime imports

### Discovery Scoring
- Base score from channel (0.0–1.0)
- Breadth bonus: +0.1 per additional channel that found the repo
- Channel quality bonuses: AWESOME_LIST +0.1, DEPENDENCY +0.1, CODE_SEARCH +0.05
- Capped at 1.0

### Channel-Specific Patterns
- `DiscoveryChannel.AWESOME_LIST` (not `CURATED`) — matches the StrEnum value `"awesome_list"`
- `RegistryChannel` creates its own `httpx.AsyncClient` (no GitHub auth needed for PyPI/npm)
- `SeedExpansion.expand()` takes `seed_urls` not a `DiscoveryQuery` — orchestrator special-cases it
- `DependencyChannel.discover_dependents()` returns empty results (MVP — no public API available)

## Module Exports

`discovery/__init__.py` exports: `GitHubRestClient`, `GitHubGraphQLClient`, `SearchChannel`, `CodeSearchChannel`, `CuratedChannel`, `RegistryChannel`, `DependencyChannel`, `SeedExpansion`, `DiscoveryOrchestrator`, `PoolManager`, `DiscoveryQuery`, `ChannelResult`, `DiscoveryResult`

## See Also
- [Phase 0 Implementation](phase0-implementation.md)
- [Phase 1 Models Implementation](phase1-models-implementation.md)
- [GitHub API Patterns](../apis/github-api-patterns.md)
- [Discovery Channels](../domain/discovery-channels.md)
