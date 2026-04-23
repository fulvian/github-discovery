---
Title: Phase 5 Scoring & Ranking Implementation
Topic: patterns
Sources: Roadmap Phase 5; Blueprint §7 (Layer D), §10 (Domain Strategy), §3 (Anti-Star Bias); Phase 5 implementation plan
Raw: [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md); [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [phase5-plan.md](../../../plans/phase5-implementation-plan.md)
Updated: 2026-04-23
Confidence: high
---

# Phase 5 Scoring & Ranking Implementation

Phase 5 implements Layer D (Scoring & Ranking) — the final pipeline stage that combines Gate 1+2+3 outputs into composite multi-dimensional scores, applies domain profiles, computes anti-star-bias Value Scores, and produces ranked, explainable results.

**Status: COMPLETE + VERIFIED** — `make ci` green: ruff + ruff format + mypy --strict + pytest.
810 total project tests pass (110 scoring tests).

## Key Architecture Decisions

### ScoringEngine: Composite Multi-Dimensional Scoring

- Combines Gate 1 (metadata sub-scores), Gate 2 (static/security sub-scores), and Gate 3 (deep assessment dimension scores) into a unified `ScoreResult`
- Per-dimension scoring uses the best available signal: Gate 3 (LLM) > Gate 2 (static) > Gate 1 (metadata) > default
- Composite `quality_score` computed as domain-weighted average of dimension scores
- `DimensionScoreInfo` tracks source gate and confidence for each dimension

### ProfileRegistry: 11 Domain Profiles

- Pre-existing 4 profiles from Phase 1 models: CLI, DEVOPS, LIBRARY, BACKEND
- 7 new profiles added in Phase 5: WEB_FRAMEWORK, DATA_TOOL, ML_LIB, SECURITY_TOOL, LANG_TOOL, TEST_TOOL, DOC_TOOL
- Each profile has domain-specific dimension weights, gate pass thresholds, and relevance indicators
- Profiles are looked up by `DomainType` enum value

### ValueScoreCalculator: Anti-Star Bias Implementation

- Implements the core formula: `quality_score / log10(stars + 10)`
- Hidden gem detection: repos with `value_score > hidden_gem_threshold` (default 1.5× median)
- Batch normalization: min-max scaling across a set of repos for relative comparison
- `ValueScore` is also a `@computed_field` on `ScoreResult` in Phase 1 models (dual implementation)

### ConfidenceCalculator: Per-Dimension Confidence

- Per-dimension confidence based on which gate provided the signal
- Gate coverage bonus: confidence boost when all gates are represented
- Overall confidence: weighted average of dimension confidences
- Confidence levels: HIGH (≥0.8), MEDIUM (≥0.5), LOW (<0.5)

### Ranker: Intra-Domain Ranking

- Ranks repos within domain categories (never across domains)
- Deterministic tie-breaking: value_score → quality_score → alphabetical
- Hidden gem identification based on ValueScoreCalculator thresholds
- `RankingResult` contains ranked list + metadata (domain, total count, hidden gems)

### CrossDomainGuard: Cross-Domain Comparison

- Min-max normalization for cross-domain comparisons
- Warning generation when cross-domain ranking is attempted
- Normalized scores with guard rails against domain-specific bias

### ExplainabilityGenerator: Why-Not Explanations

- Summary reports: key strengths, weaknesses, overall assessment
- Full reports: per-dimension breakdown with source gate, score, confidence, and narrative
- Improvement suggestions based on weakest dimensions
- Markdown-formatted output for agent/CLI consumption

### FeatureStore: SQLite-Backed Feature Persistence

- SQLite backend with TTL-based expiry (configurable, default 24h)
- CRUD operations: store, retrieve, delete features by repo + key
- Batch operations: bulk store and retrieve
- Statistics: count, coverage metrics
- Async-first with aiosqlite

## Dependencies

No new dependencies added in Phase 5 — uses existing: `pydantic`, `aiosqlite`, `structlog`.

## Module Structure

```
scoring/
├── __init__.py               # Public API exports
├── types.py                  # ScoringInput, DimensionScoreInfo, RankingResult, ExplainReport, etc.
├── engine.py                 # ScoringEngine — composite scoring across gates
├── profiles.py               # ProfileRegistry — 11 domain weight profiles
├── value_score.py            # ValueScoreCalculator — anti-star bias formula
├── confidence.py             # ConfidenceCalculator — per-dimension confidence
├── ranker.py                 # Ranker — intra-domain ranking + hidden gems
├── cross_domain.py           # CrossDomainGuard — normalization + warnings
├── explainability.py         # ExplainabilityGenerator — summary/full reports
└── feature_store.py          # FeatureStore — SQLite-backed persistence
```

## Configuration (ScoringSettings)

Added to `config.py` with env prefix `GHDISC_SCORING_`:

| Setting | Default | Description |
|---------|---------|-------------|
| `default_gate_pass_threshold` | `0.5` | Default threshold for gate pass |
| `hidden_gem_threshold_multiplier` | `1.5` | Value score multiplier for hidden gem detection |
| `cross_domain_warning` | `True` | Enable cross-domain comparison warnings |
| `feature_store_ttl_hours` | `24` | Feature store TTL |
| `feature_store_db_path` | `.ghdisc/features.db` | SQLite database path |

## Test Coverage

- 110 unit tests across 9 test files in `tests/unit/scoring/`
- `conftest.py` with shared fixtures
- All modules tested with mocked gate inputs
- Test files:
  - `test_types.py` (9) — ScoringInput, DimensionScoreInfo, RankingResult serialization
  - `test_engine.py` (13) — ScoringEngine composite scoring, missing gates, dimension mapping
  - `test_profiles.py` (10) — ProfileRegistry lookup, all 11 profiles, unknown domain
  - `test_value_score.py` (20) — Value Score formula, hidden gem detection, batch normalization
  - `test_confidence.py` (13) — Per-dimension confidence, gate coverage bonus, overall confidence
  - `test_ranker.py` (13) — Intra-domain ranking, tie-breaking, hidden gem identification
  - `test_cross_domain.py` (8) — Normalization, warnings, cross-domain guard
  - `test_explainability.py` (14) — Summary/full reports, improvement suggestions
  - `test_feature_store.py` (10) — SQLite CRUD, TTL expiry, batch ops, stats

## Key Implementation Patterns

### Pydantic + `from __future__ import annotations`

Pydantic model fields need runtime imports, NOT `TYPE_CHECKING` blocks. Using TYPE_CHECKING causes `PydanticUserError: is not fully defined`. Solution: `# noqa: TC001` on runtime imports in model files.

### StrEnum `__members__` Gotcha

`ScoreDimension.__members__` returns uppercase names (`CODE_QUALITY`), NOT values (`code_quality`). For JSON deserialization, use `try: ScoreDimension(k) except ValueError: pass` instead of checking `__members__`.

### FeatureStore Async Fixture

pytest async fixtures with `yield` need `# noqa: ANN001` since the return type annotation conflicts with generator behavior.

## Bugs Fixed During Implementation

1. **Pre-existing ruff PLW0108** in `test_budget_controller.py`: unnecessary lambda — replaced with direct reference
2. **Pre-existing ruff F841** in `test_orchestrator.py`: unused variable — removed
3. **Pre-existing ruff PLC0415** in `test_orchestrator.py`: misplaced import — moved to top-level

## See Also

- [Anti-Star Bias Philosophy](../architecture/anti-star-bias.md)
- [Scoring Dimensions](../domain/scoring-dimensions.md)
- [Domain Strategy](../domain/domain-strategy.md)
- [Tiered Pipeline](../architecture/tiered-pipeline.md)
- [Phase 4 Implementation](phase4-assessment-implementation.md)
- [Tech Stack](tech-stack.md)
