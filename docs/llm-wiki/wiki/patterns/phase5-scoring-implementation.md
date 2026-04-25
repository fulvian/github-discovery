---
Title: Phase 5 Scoring & Ranking Implementation
Topic: patterns
Sources: Roadmap Phase 5; Blueprint §7 (Layer D), §10 (Domain Strategy), §3 (Star-Neutral Quality); Phase 5 implementation plan; Star-neutral redesign (2026-04-25)
Raw: [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md); [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [phase5-plan.md](../../../plans/phase5-implementation-plan.md)
Updated: 2026-04-25
Confidence: high
---

# Phase 5 Scoring & Ranking Implementation

Phase 5 implements Layer D (Scoring & Ranking) — the final pipeline stage that combines Gate 1+2+3 outputs into composite multi-dimensional scores, applies domain profiles, computes star-neutral quality scores, and produces ranked, explainable results.

**Status: COMPLETE + VERIFIED + STAR-NEUTRAL REDESIGN** — `make ci` green: ruff + ruff format + mypy --strict + pytest.
1326 total project tests pass (136 scoring tests).

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
- `_HIDDEN_GEM_MAX_STARS = 100`
- `_HIDDEN_GEM_MIN_QUALITY = 0.5`

## Key Architecture Decisions

### ScoringEngine: Composite Multi-Dimensional Scoring

- Combines Gate 1 (metadata sub-scores), Gate 2 (static/security sub-scores), and Gate 3 (deep assessment dimension scores) into a unified `ScoreResult`
- Per-dimension scoring uses the best available signal: Gate 3 (LLM) > Gate 2 (static) > Gate 1 (metadata) > default
- Composite `quality_score` computed as domain-weighted average of dimension scores
- **Phantom score fix (2026-04-25)**: `_apply_weights()` now excludes dimensions with `confidence <= 0.0` from the weighted average. Previously, `default_neutral (0.5, confidence=0.0)` for FUNCTIONALITY and INNOVATION was included, inflating quality_score with data that was never actually evaluated
- `DimensionScoreInfo` tracks source gate and confidence for each dimension
- **FeatureStore integration**: Optional `store` parameter in constructor. `score()` remains sync (backward compatible); new `async score_cached()` checks store before computing and writes results back after

### ProfileRegistry: 11 Domain Profiles

- Pre-existing 4 profiles from Phase 1 models: CLI, DEVOPS, LIBRARY, BACKEND
- 7 new profiles added in Phase 5: WEB_FRAMEWORK, DATA_TOOL, ML_LIB, SECURITY_TOOL, LANG_TOOL, TEST_TOOL, DOC_TOOL
- Each profile has domain-specific dimension weights, gate pass thresholds, and relevance indicators

### ValueScoreCalculator: Star-Neutral Implementation

- `compute()`: returns `quality_score` unchanged (stars explicitly unused via `_ = stars`)
- `is_hidden_gem()`: checks quality threshold + star threshold (informational label)
- `star_context()`: generates corroboration-level description strings
- `normalize_batch()`: normalizes quality only (stars ignored)

### ConfidenceCalculator: Per-Dimension Confidence

- Per-dimension confidence based on which gate provided the signal
- Gate coverage bonus: confidence boost when all gates are represented
- Overall confidence: weighted average of dimension confidences

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

- 136 unit tests across 9 test files in `tests/unit/scoring/`
- 10 new tests added for star-neutral redesign:
  - `TestCorroborationLevel` (5 tests): new, unvalidated, emerging, validated, widely_adopted
  - `TestIsHiddenGem` (5 tests): high quality + low stars, high quality + high stars, low quality, boundary quality, boundary stars
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
