---
Title: Phase 5 Scoring & Ranking Implementation
Topic: patterns
Sources: Roadmap Phase 5; Blueprint §7 (Layer D), §10 (Domain Strategy), §3 (Star-Neutral Quality); Phase 5 implementation plan; Star-neutral redesign (2026-04-25)
Raw: [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md); [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [phase5-plan.md](../../../plans/phase5-implementation-plan.md)
Updated: 2026-04-26
Confidence: high
---

# Phase 5 Scoring & Ranking Implementation

Phase 5 implements Layer D (Scoring & Ranking) — the final pipeline stage that combines Gate 1+2+3 outputs into composite multi-dimensional scores, applies domain profiles, computes star-neutral quality scores, and produces ranked, explainable results.

**Status: COMPLETE + VERIFIED + STAR-NEUTRAL REDESIGN + FASE 2 AUDIT REMEDIATION** — `make ci` green: ruff + ruff format + mypy --strict + pytest.
1587 total project tests pass (187 scoring tests).

## Star-Neutral Redesign (2026-04-25)

The scoring system was redesigned from anti-star bias to star-neutral:

### What Changed
- `ScoreResult.value_score`: was `quality_score / log10(stars + 10)`, now equals `quality_score`
- `ScoreResult.corroboration_level`: NEW computed_field — classifies stars into informational buckets
- `ScoreResult.is_hidden_gem`: NEW computed_field — informational label (quality ≥ 0.5 AND stars < 100)
- `Ranker._sort_key()`: was `(-value_score, -quality_score, ...)`, now `(-quality_score, -confidence, ...)`
- `ValueScoreCalculator.compute()`: returns `quality_score` unchanged (stars explicitly unused)
- All "anti-star bias" references updated to "star-neutral" across 18 files

### What Stayed the Same
- ScoringEngine composite scoring (Gate 1+2+3 → quality_score)
- Domain weight profiles (11 profiles)
- ConfidenceCalculator (per-dimension confidence + gate coverage)
- FeatureStore persistence (SQLite)
- Intra-domain ranking (never cross-domain without normalization)

### Constants Added (models/scoring.py)
- `_CORROBORATION_UNVALIDATED = 50`
- `_CORROBORATION_EMERGING = 500`
- `_CORROBORATION_VALIDATED = 5000`
- `_HIDDEN_GEM_MAX_STARS` and `_HIDDEN_GEM_MIN_QUALITY` **removed in Fase 2 Wave 1 (T1.1)** — now uses `ScoringSettings` as single source of truth

## Fase 2 Audit Remediation (2026-04-26)

Post-independent audit by 4 LLM auditors (Claude, Gemini, ChatGPT, Perplexity). Average scoring logic rating: 5.5–6.5/10. Fase 2 addresses all critical and high-priority issues.

### Wave 1 — P0 Critical Bugs (T1.1–T1.4)

- **T1.1 — Single-source hidden_gem thresholds**: Removed `_HIDDEN_GEM_MAX_STARS=100` and `_HIDDEN_GEM_MIN_QUALITY=0.5` from `models/scoring.py`. `ScoreResult.is_hidden_gem` now reads `ScoringSettings` defaults (star_threshold=500, min_quality=0.7). Added `is_hidden_gem` computed_field to `RankedRepo`.
- **T1.2 — Deterministic tie-breaking**: Replaced `hash()` with `hashlib.blake2b(digest_size=8)` in `Ranker._seeded_hash()`. Cross-process deterministic regardless of `PYTHONHASHSEED`.
- **T1.3 — Coverage field + quality damping**: Added `coverage: float` and `raw_quality_score: float` to `ScoreResult`. `_apply_weights()` returns `tuple[float, float]` (raw_score, coverage). Quality damping: `quality_score = raw * (0.5 + 0.5 * coverage)`.
- **T1.4 — Stricter SubScore validators**: `SubScore.weight`: `gt=0.0` → `ge=0.0, le=10.0`. `SubScore.details`: `dict[str, object]` → `dict[str, str | int | float | bool | None]` (JSON-compatible). Fixed 7 screening modules for type compatibility.

### Wave 2 — Scoring Logic Hardening (T2.1–T2.5)

- **T2.1 — Revised `_DERIVATION_MAP`**: ARCHITECTURE now empty (not derivable from Gate 1+2). CODE_QUALITY rebalanced to weight product (complexity, test) over process (review). DOCUMENTATION removed review_practice, added release_discipline. All non-empty derivation weights sum to 1.0.
- **T2.2 — Weighted confidence**: `ConfidenceCalculator.compute()` accepts optional `profile` parameter. When provided: weighted average using profile dimension weights instead of simple average. Missing critical dimension penalty: -0.10 if any dimension with profile weight ≥ 0.15 has confidence 0.0.
- **T2.3 — Per-dimension confidence**: New `_DIMENSION_CONFIDENCE_FROM_GATE12` map: TESTING=0.55, MAINTENANCE=0.50, SECURITY=0.50, DOCUMENTATION=0.40, CODE_QUALITY=0.40, ARCHITECTURE/FUNCTIONALITY/INNOVATION=0.0.
- **T2.4 — HeuristicFallback model**: New `HeuristicFallback` in `assessment/types.py` with confidence capped at 0.25. Explicit ignorance signal: `note` warns "LLM unavailable; heuristic fallback only — interpret with caution".
- **T2.5 — Path-based test detection**: `_extract_file_paths()` parses Repomix file headers. `_has_test_dir()` checks file paths against known test directories. Prevents false positives from README prose mentions.

### Wave 3 — Robustness & Resource Safety (gap-fix pass)

- **T3.1/T3.2 — Typed fetch + retry wiring fixed**: `GitHubRestClient.get()/get_all_pages()/search()` now use typed `_tenacity_fetch()` path. Status mapping happens before retry decisions; 304 is handled as non-error for ETag requests.
- **T3.2 — Retry-After honored**: when GitHub returns `Retry-After`, retry loop waits bounded seconds before retrying.
- **T3.4 — LLM lifecycle hardening**: `LLMProvider` now keeps a direct `AsyncOpenAI` handle and closes it explicitly, avoiding reliance on instructor wrapper internals.
- **T3.5 — TTL semantics fixed**: `FeatureStore` read/stats/cleanup paths now consistently use `expires_at` (with legacy fallback for pre-migration rows).
- **T3.7 — Value normalization deduplicated**: cross-domain normalization now mirrors `normalized_value_score` to `normalized_quality` (star-neutral invariant).

### Wave 5 — Architectural Refactoring (T5.1–T5.3, T5.5)

- **T5.1 — Per-DomainProfile derivation_map**: New `derivation_map: dict[str, list[list[float | str]]] | None` field on `DomainProfile`. `ScoringEngine._resolve_derivation_map()` merges profile entries with module-level `_DERIVATION_MAP` defaults (profile overrides specific dimensions, others fall through to default).
- **T5.2 — Per-DomainProfile gate_thresholds**: All 12 built-in profiles now have explicit `gate_thresholds` dict. `ScreeningOrchestrator._get_threshold()` reads from `ProfileRegistry.get(domain).gate_thresholds` first, with fallback to legacy `_DOMAIN_THRESHOLDS`.
- **T5.3 — Custom profiles YAML/TOML loading**: `ProfileRegistry` gains `load_from_yaml()`, `load_from_toml()`, `load_custom_profiles()` (auto-detects format). `_parse_profile_entry()` parses YAML/TOML dicts into `DomainProfile` with case-insensitive domain_type matching, derivation_map support, weight validation.
- **T5.3 wiring**: `custom_profiles_path` in `ScoringSettings` auto-loads into both `ScoringEngine._registry` and `ScreeningOrchestrator._profile_registry`.
- **T5.4 — DEPRECATED**: `is_hidden_gem` on `ScoreResult` and `RankedRepo` marked `.. deprecated:: 0.2.0` with removal planned for v0.3.0. Not removed because (1) bug already fixed in T1.1 (single source of truth achieved), (2) 11 consumers would break, (3) standard deprecation pattern is deprecate-first, remove-next-major. Canonical source is `ValueScoreCalculator.is_hidden_gem()`.
- **T5.5 — Property-Based Tests (Hypothesis)**

11 Hypothesis-based tests covering 1000+ generated inputs:
- ScoreResult bounds: quality_score, confidence, coverage ∈ [0,1]
- Star neutrality: value_score == quality_score regardless of stars
- Coverage damping: quality_score ≤ raw_quality_score when coverage < 1
- Profile weight sum: all 12 domain profiles sum to ~1.0
- Profile completeness: all profiles cover all 8 dimensions
- Determinism: identical inputs produce identical outputs

## Key Architecture Decisions

### ScoringEngine: Composite Multi-Dimensional Scoring

- Combines Gate 1 (metadata sub-scores), Gate 2 (static/security sub-scores), and Gate 3 (deep assessment dimension scores) into a unified `ScoreResult`
- Per-dimension scoring uses the best available signal: Gate 3 (LLM) > Gate 2 (static) > Gate 1 (metadata) > default
- Composite `quality_score` computed as domain-weighted average of dimension scores
- **Phantom score fix (2026-04-25)**: `_apply_weights()` now excludes dimensions with `confidence <= 0.0` from the weighted average. Previously, `default_neutral (0.5, confidence=0.0)` for FUNCTIONALITY and INNOVATION was included, inflating quality_score with data that was never actually evaluated
- `DimensionScoreInfo` tracks source gate and confidence for each dimension
- **FeatureStore integration**: Optional `store` parameter in constructor. `score()` remains sync (backward compatible); new `async score_cached()` checks store before computing and writes results back after

### ProfileRegistry: 12 Domain Profiles + Custom Loading

- Pre-existing 5 profiles from Phase 1 models: CLI, DEVOPS, LIBRARY, BACKEND, OTHER (DEFAULT)
- 7 new profiles added in Phase 5: WEB_FRAMEWORK, DATA_TOOL, ML_LIB, SECURITY_TOOL, LANG_TOOL, TEST_TOOL, DOC_TOOL
- Each profile has domain-specific dimension weights, gate pass thresholds, and relevance indicators
- **T5.1**: Each profile can override derivation_map (dimension→sub-score mappings)
- **T5.2**: All 12 profiles have explicit gate_thresholds (gate1, gate2, gate3)
- **T5.3**: YAML/TOML custom profile loading with case-insensitive domain_type matching
- **T5.3 wiring**: `ScoringSettings.custom_profiles_path` auto-loads into ProfileRegistry

### ValueScoreCalculator: Star-Neutral Implementation

- `compute()`: returns `quality_score` unchanged (stars explicitly unused via `_ = stars`)
- `is_hidden_gem()`: checks quality threshold + star threshold (informational label)
- `star_context()`: generates corroboration-level description strings
- `normalize_batch()`: normalizes quality only (stars ignored)

### ConfidenceCalculator: Per-Dimension Confidence

- Per-dimension confidence based on which gate provided the signal
- **Variable confidence per dimension (T2.3)**: `_DIMENSION_CONFIDENCE_FROM_GATE12` map — TESTING=0.55, MAINTENANCE=0.50, SECURITY=0.50, DOCUMENTATION=0.40, CODE_QUALITY=0.40, non-derivable dims=0.0
- Gate coverage bonus: confidence boost when all gates are represented
- **Weighted average (T2.2)**: when profile provided, uses profile dimension weights instead of simple average
- **Missing critical dimension penalty (T2.2)**: -0.10 if any dim with weight ≥ 0.15 has confidence 0.0

### Ranker: Intra-Domain Star-Neutral Ranking

- Ranks repos within domain categories (never across domains)
- **Star-neutral sort key**: 4-tuple `(-quality_score, -confidence, -seeded_hash, full_name)`
- Stars are NOT part of the sort key — ranking is purely quality-based
- `ScoringSettings.ranking_seed: int = 42` — consumed for reproducible but seed-dependent tie-breaking
- Hidden gem identification: quality_score ≥ min_quality AND stars < threshold

### CrossDomainGuard: Cross-Domain Comparison

- Min-max normalization for cross-domain comparisons
- Warning generation when cross-domain ranking is attempted

### ExplainabilityGenerator: Why-Not Explanations

- Summary reports: key strengths, weaknesses, overall assessment
- Full reports: per-dimension breakdown with source gate, score, confidence, and narrative
- `_star_baseline_comparison()`: uses "corroboration" language (not "penalty")
- Markdown-formatted output for agent/CLI consumption

### FeatureStore: SQLite-Backed Feature Persistence

- SQLite backend with TTL-based expiry (configurable, default 24h)
- CRUD operations: store, retrieve, delete features by repo + key
- `gate3_available` column for tracking Gate 3 assessment state
- Async-first with aiosqlite

## Bug Fix: Star Count Preservation (2026-04-25)

`deep_eval.py` was losing star counts during Gate 3 re-scoring. When candidates were created from `--repo-urls`, they had `stars=0`. The re-scoring via ScoringEngine would overwrite the FeatureStore entry, losing the previously stored star count.

**Fix**: Before re-scoring, check FeatureStore for existing star data:
```python
if candidate.stars == 0:
    prev_score = await store.get_latest(candidate.full_name)
    if prev_score is not None and prev_score.stars > 0:
        scored_candidate = candidate.model_copy(update={"stars": prev_score.stars})
```

## Module Structure

```
scoring/
├── __init__.py               # Public API exports (star-neutral docstrings)
├── types.py                  # ScoringInput, DimensionScoreInfo, RankingResult, etc.
├── engine.py                 # ScoringEngine — composite scoring across gates
├── profiles.py               # ProfileRegistry — 11 domain weight profiles
├── value_score.py            # ValueScoreCalculator — star-neutral (quality unchanged)
├── confidence.py             # ConfidenceCalculator — per-dimension confidence
├── ranker.py                 # Ranker — star-neutral intra-domain ranking
├── cross_domain.py           # CrossDomainGuard — normalization + warnings
├── explainability.py         # ExplainabilityGenerator — corroboration language
└── feature_store.py          # FeatureStore — SQLite-backed persistence
```

## Configuration (ScoringSettings)

Added to `config.py` with env prefix `GHDISC_SCORING_`:

| Setting | Default | Description |
|---------|---------|-------------|
| `default_gate_pass_threshold` | `0.5` | Default threshold for gate pass |
| `hidden_gem_star_threshold` | `500` | Star count threshold for hidden gem label |
| `hidden_gem_min_quality` | `0.7` | Minimum quality for hidden gem label |
| `ranking_seed` | `42` | Seed for deterministic tie-breaking |
| `min_confidence` | `0.3` | Default minimum confidence for ranking |
| `cross_domain_warning` | `True` | Enable cross-domain comparison warnings |
| `feature_store_ttl_hours` | `24` | Feature store TTL |
| `feature_store_db_path` | `.ghdisc/features.db` | SQLite database path |

## Test Coverage

- 187 unit tests across 14 test files in `tests/unit/scoring/`
- Phase 5 original: 136 tests across 9 files
- Star-neutral redesign: +10 tests (corroboration, hidden gem, value_score)
- Fase 2 Wave 1: +120 tests (hidden_gem_consistency=112, deterministic_ranking=4, coverage_field=5, -1 updated)
- Fase 2 Wave 2: +36 tests (scoring_hardening=24, heuristic_hardening=12)
- Fase 2 Wave 5: +19 tests (per-profile derivation=6, per-profile thresholds=4, YAML/TOML loading=9)
- T5.5 Hypothesis: +11 property-based tests (1000+ generated inputs)
- Updated tests:
  - `test_value_score.py`: rewritten for star-neutral expectations
  - `test_scoring.py`: rewritten with pytest import, new test classes
  - `test_ranker.py`: `test_ranking_star_neutral` (renamed from `test_ranking_anti_star_bias`)

## See Also

- [Star-Neutral Quality Scoring](../architecture/anti-star-bias.md)
- [Scoring Dimensions](../domain/scoring-dimensions.md)
- [Domain Strategy](../domain/domain-strategy.md)
- [Tiered Pipeline](../architecture/tiered-pipeline.md)
- [Phase 4 Implementation](phase4-assessment-implementation.md)
- [Tech Stack](tech-stack.md)
