# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — v0.2.0-beta (Fase 2 Audit Remediation)

### Added

- **Scoring methodology documentation** (`docs/foundation/SCORING_METHODOLOGY.md`) — Full derivation map rationale with citations, per-dimension design decisions, 8 academic/industry references
- **Labeling guidelines** (`docs/foundation/labeling_guidelines.md`) — Rater qualifications, 1-5 rubric for 8 dimensions, calibration procedure, JSON schema for rating data
- **`coverage` field** on `ScoreResult` — Fraction of dimensions with non-zero scores (0.0–1.0), exposed in API/CLI/MCP
- **`raw_quality_score` field** on `ScoreResult` — Quality score before coverage damping
- **Quality damping formula** — `quality_score = raw * (0.5 + 0.5 * coverage)` prevents inflated scores for partially-assessed repos
- **Deterministic tie-breaking** — `hashlib.blake2b(digest_size=8)` replaces `hash()` for cross-process reproducible ranking
- **Weighted confidence** — Overall confidence is weighted average using profile dimension weights (not simple mean)
- **Per-dimension confidence caps** — Gate 1+2 confidence varies by dimension: TESTING=0.55, MAINTENANCE=0.50, SECURITY=0.50, others lower
- **Missing critical dimension penalty** — -0.10 for each high-weight dimension with no data
- **`HeuristicFallback` model** — Explicit ignorance signal when LLM unavailable, confidence capped at 0.25
- **Per-profile derivation map** (T5.1) — `DomainProfile.derivation_map` allows per-domain overrides of dimension→sub-score mappings with merge semantics
- **Per-profile gate thresholds** (T5.2) — All 12 domain profiles have explicit `gate_thresholds` dicts
- **Custom profiles YAML/TOML loading** (T5.3) — `ProfileRegistry.load_from_yaml()`/`load_from_toml()` with case-insensitive domain_type, weight validation, derivation_map support
- **Auto-load custom profiles** — `ScoringSettings.custom_profiles_path` wired to `ProfileRegistry` in both `ScoringEngine` and `ScreeningOrchestrator`
- **Property-based tests** (T5.5) — 11 Hypothesis tests covering 1000+ generated inputs for scoring invariants
- **Typed GitHub API errors** — `GitHubAuthError`, `GitHubRateLimitError`, `GitHubNetworkError`, `GitHubServerError` hierarchy
- **Retry with backoff** — Tenacity-based retry on 429/5xx with jitter and `Retry-After` header honor
- **Orphan clone cleanup** — Automatic removal of stale clone directories at MCP server startup
- **FeatureStore TTL enforcement** — Consistent `expires_at` semantics in read/stats/cleanup with legacy fallback
- **`ghdisc db prune` CLI command** — Remove expired FeatureStore entries (dry-run support)

### Changed

- **Star-neutral redesign** — `value_score = quality_score` (stars explicitly unused). Stars are corroboration metadata only
- **`_DERIVATION_MAP` revised** (T2.1) — ARCHITECTURE cleared (not derivable), CODE_QUALITY rebalanced (product > process), DOCUMENTATION corrected (release_discipline replaces review_practice)
- **Hidden gem thresholds** single-sourced from `ScoringSettings` — removed hardcoded constants from models
- **`SubScore.weight` validator** — `ge=0.0, le=10.0` (was `gt=0.0` only)
- **`SubScore.details` validator** — `dict[str, str | int | float | bool | None]` (JSON-compatible)
- **LLM provider lifecycle** — Explicit `AsyncOpenAI` close to prevent connection leakage
- **Cross-domain normalization** — Deduplicated value_score/quality paths (star-neutral invariant)
- **12 domain profiles** — All have explicit gate_thresholds, complete dimension_weights

### Tests

- 1326 → 1587 tests (+261 from Fase 2)
- Wave 1: +120 tests (hidden_gem_consistency=112, deterministic_ranking=4, coverage_field=5, -1 updated)
- Wave 2: +36 tests (scoring_hardening=24, heuristic_hardening=12)
- Wave 3: +72 tests (typed errors, retry, TTL, lifecycle, normalization)
- Wave 5: +30 tests (per-profile derivation=6, per-profile thresholds=4, YAML/TOML loading=9, property-based=11)
- `make ci` green: ruff + ruff format + mypy --strict + pytest

## [0.1.0-alpha] — 2026-04-24

### Added

- 4-gate progressive discovery pipeline (Discovery → Metadata Screening → Static/Security Screening → LLM Deep Assessment → Ranking)
- 8 quality dimensions with domain-dependent weighting
- 12 domain profiles (CLI, web_framework, data_tool, ml_lib, devops_tool, library, backend, security_tool, lang_tool, test_tool, doc_tool, other)
- Star-neutral quality scoring — stars are corroboration metadata, not a ranking signal
- MCP-native agentic integration (16 tools, 4 resources, 5 prompts)
- FastAPI REST API (secondary interface)
- typer CLI with 6 pipeline commands and Rich output
- SQLite session and feature store backends
- NanoGPT LLM provider with instructor structured output
- Repomix repository packing for Gate 3
- OSV vulnerability scanning integration
- 1326 tests across unit/integration/feasibility/agentic categories
- 118+ source files, 0 lint/type errors
