---
Title: Phase 2 Audit Remediation — Decision Log
Topic: architecture
Sources: Fase 2 Implementation Plan (docs/plans/fase2_plan.md); Audit reports (docs/audit/); Phase 5 implementation (src/github_discovery/scoring/)
Raw: [fase2_plan.md](../../../plans/fase2_plan.md); [audit_1_claude.md](../../../audit/audit_1_claude.md)
Updated: 2026-04-26
Confidence: high
---

# Phase 2 Audit Remediation — Decision Log

Post-independent audit remediation (4 LLM auditors: Claude, Gemini, ChatGPT, Perplexity).
Average scoring logic rating: 5.5–6.5/10. Fase 2 addresses all critical and high-priority issues.

**Status: Waves 0–3, 5 COMPLETE + COMMITTED. Wave 4 infrastructure ready (external labeling pending).**

## Wave Summary

| Wave | Tasks | Priority | Status | Tests Added |
|------|-------|----------|--------|-------------|
| Wave 0 | Audit setup | — | Done | — |
| Wave 1 | T1.1–T1.4 | P0 Critical | Done | +120 |
| Wave 2 | T2.1–T2.5 | P0/P1 Hardening | Done | +36 |
| Wave 3 | T3.1–T3.7 | P1 Robustness | Done | +72 |
| Wave 4 | T4.1–T4.4 | P0 Methodological | Infrastructure ready | External work |
| Wave 5 | T5.1–T5.5 | P2 Architectural | Done (T5.4 skipped) | +30 |

**Test count**: 1326 → 1587 (+261 from Fase 2)

## Key Decisions

### D1: Single-source hidden_gem thresholds (T1.1)

**Decision**: Remove hardcoded `_HIDDEN_GEM_MAX_STARS=100` and `_HIDDEN_GEM_MIN_QUALITY=0.5` from `models/scoring.py`. `ScoringSettings` is the single source of truth.

**Rationale**: Dual-source constants diverged from settings defaults (100 vs 500 stars, 0.5 vs 0.7 quality). Moving to settings makes thresholds configurable via env vars and eliminates inconsistency.

### D2: Deterministic tie-breaking with blake2b (T1.2)

**Decision**: Replace Python `hash()` with `hashlib.blake2b(digest_size=8)`.

**Rationale**: `hash()` is salted per process (`PYTHONHASHSEED`), making ranking non-deterministic across runs. blake2b is deterministic, fast, and has no collision risk for short strings.

### D3: Coverage damping formula (T1.3)

**Decision**: `quality_score = raw * (0.5 + 0.5 * coverage)`. Expose both `raw_quality_score` and `coverage` on `ScoreResult`.

**Rationale**: Dimensions with no data (confidence=0.0) previously contributed 0.5 defaults, inflating quality. Excluding them from weighted average is correct but produces coverage-dependent scores. The damping formula ensures partial-coverage repos get proportionally damped scores (max 50% damping at coverage=0).

### D4: Empty ARCHITECTURE derivation (T2.1)

**Decision**: Set `ARCHITECTURE: []` in `_DERIVATION_MAP`. Not derivable from Gate 1+2 metadata.

**Rationale**: Cyclomatic complexity ≠ architectural quality. Directory structure is an unreliable proxy. Architecture requires understanding coupling, abstraction layers, API surface — only Gate 3 (LLM) can assess this honestly.

### D5: CODE_QUALITY rebalanced — product over process (T2.1)

**Decision**: `complexity(0.35) + test_footprint(0.25) + review_practice(0.25) + ci_cd(0.15)`.

**Rationale**: Product signals (complexity, test footprint) measure what the code IS. Process signals (review practice, CI) measure how it's MADE. Structural quality is weighted higher because it directly measures the artifact.

### D6: Per-profile derivation map with merge semantics (T5.1)

**Decision**: `_resolve_derivation_map()` starts with `_DERIVATION_MAP` defaults, then overlays profile-specific entries. Dimensions not specified in the profile keep defaults.

**Rationale**: Full replacement would force profiles to specify ALL dimensions (including empty ones like ARCHITECTURE). Merge semantics allow profiles to override only the dimensions they care about, with safe defaults for the rest.

### D7: Case-insensitive domain_type in YAML/TOML (T5.3)

**Decision**: `_parse_profile_entry()` lowercases `domain_type` before parsing enum.

**Rationale**: YAML/TOML authors naturally write `ML_LIB` or `CLI` (screaming snake case), but enum values are lowercase (`ml_lib`, `cli`). Case-insensitive matching improves UX without breaking existing code.

### D8: T5.4 is_hidden_gem removal — SKIPPED

**Decision**: Skip `is_hidden_gem` removal from `ScoreResult`. It's a `@computed_field` property that reads from `ScoringSettings`, not a stored field. Removal is a breaking change for MCP/API/CLI consumers.

**Rationale**: The original audit flagged this as "service logic in a model," which is architecturally valid. But the fix (move to `ValueScoreCalculator` only) breaks 11 consumers across the codebase. Marking as optional/pending user discussion.

### D9: Custom profiles auto-load from settings (T5.3 wiring)

**Decision**: `ProfileRegistry.__init__` accepts optional `custom_profiles_path`. Both `ScoringEngine` and `ScreeningOrchestrator` pass `ScoringSettings.custom_profiles_path` to registry.

**Rationale**: Users set `GHDISC_SCORING_CUSTOM_PROFILES_PATH=/path/to/profiles.yaml` once. All pipeline components that create a `ProfileRegistry` automatically load custom profiles. No manual wiring needed.

### D10: Profiles CLI subcommand (T5.3)

**Decision**: Added `ghdisc profiles list`, `ghdisc profiles show <domain>`, `ghdisc profiles validate <path>` commands.

**Rationale**: Users need to inspect loaded profiles (including custom ones) and validate profile files before deployment. The `list` command shows all profiles with thresholds in tabular form. The `show` command gives full detail (weights, derivation map, thresholds). The `validate` command checks YAML/TOML files without loading.

## Acceptance Criteria Status

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Single source of truth for hidden_gem | ✅ Done |
| 2 | Deterministic ranking cross-process | ✅ Done |
| 3 | coverage field in API/CLI/MCP | ✅ Done |
| 4 | SCORING_METHODOLOGY.md with citations | ✅ Done |
| 5 | Weighted confidence from profile weights | ✅ Done |
| 6 | Heuristic fallback confidence ≤ 0.25 | ✅ Done |
| 7 | Typed GitHub API errors + retry | ✅ Done |
| 8 | Orphan clone cleanup at startup | ✅ Done |
| 9 | FeatureStore TTL + `ghdisc db prune` | ✅ Done |
| 10 | Property-based tests (1000+ cases) | ✅ Done |
| 11 | Golden dataset 200 repos, κ ≥ 0.6 | ⏳ External |
| 12 | NDCG@10 ≥ 0.75, p<0.05 vs star-only | ⏳ External |
| 13 | make ci green | ✅ Done (1587 tests) |
| 14 | Wiki updated | ✅ Done |
| 15 | CHANGELOG for v0.2.0-beta | ⏳ Pending |

## Files Modified

### Source files
- `src/github_discovery/models/scoring.py` — derivation_map field, gate_thresholds on all profiles
- `src/github_discovery/models/screening.py` — SubScore validators, degraded_count field
- `src/github_discovery/scoring/engine.py` — _resolve_derivation_map merge, coverage damping, _MAPPING_ENTRY_LENGTH
- `src/github_discovery/scoring/profiles.py` — YAML/TOML loading, case-insensitive domain_type, auto-load
- `src/github_discovery/scoring/confidence.py` — weighted confidence, per-dimension caps
- `src/github_discovery/scoring/value_score.py` — star-neutral compute
- `src/github_discovery/scoring/ranker.py` — blake2b tie-breaking, star-neutral sort
- `src/github_discovery/scoring/feature_store.py` — TTL semantics, prune_expired
- `src/github_discovery/scoring/cross_domain.py` — deduplicated normalization
- `src/github_discovery/scoring/types.py` — HeuristicFallback model
- `src/github_discovery/screening/orchestrator.py` — ProfileRegistry thresholds
- `src/github_discovery/screening/gate1_metadata.py` — typed error handling, degraded tracking
- `src/github_discovery/screening/gate2_static.py` — orphan cleanup
- `src/github_discovery/assessment/llm_provider.py` — AsyncOpenAI lifecycle, async context manager
- `src/github_discovery/assessment/orchestrator.py` — provider nullification after close
- `src/github_discovery/assessment/types.py` — HeuristicFallback model
- `src/github_discovery/assessment/heuristics.py` — path-based test detection
- `src/github_discovery/exceptions.py` — GitHubFetchError hierarchy (Auth, RateLimit, Server)
- `src/github_discovery/discovery/github_client.py` — tenacity fetch, Retry-After, typed error mapping
- `src/github_discovery/config.py` — ScoringSettings fields (custom_profiles_path, etc.)
- `src/github_discovery/cli/app.py` — profiles command registration
- `src/github_discovery/cli/profiles.py` — NEW: ghdisc profiles list/show/validate
- `src/github_discovery/cli/db.py` — prune command
- `src/github_discovery/mcp/server.py` — orphan cleanup at startup

### Documentation
- `docs/foundation/SCORING_METHODOLOGY.md` — NEW (T2.1)
- `docs/foundation/labeling_guidelines.md` — NEW (T4.1 infrastructure)

### Test files
- `tests/unit/scoring/test_wave5_architectural.py` — NEW (19 tests)
- `tests/unit/scoring/test_hidden_gem_consistency.py` — NEW (112 tests)
- `tests/unit/scoring/test_scoring_hardening.py` — NEW (24 tests)
- `tests/unit/scoring/test_property_based.py` — NEW (11 tests)
- Plus updates to 15+ existing test files

## See Also

- [Phase 5 Scoring Implementation](../patterns/phase5-scoring-implementation.md)
- [Scoring Dimensions](../domain/scoring-dimensions.md)
- [Screening Gates Detail](../domain/screening-gates.md)
- [Star-Neutral Quality Scoring](anti-star-bias.md)
- [Operational Rules](../patterns/operational-rules.md)
