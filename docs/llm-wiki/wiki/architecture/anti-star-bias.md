---
Title: Star-Neutral Quality Scoring
Topic: architecture
Sources: Foundation Blueprint §3, §5, §7; Findings §1; E2E validation (2026-04-25); Fase 2 Audit Remediation (2026-04-26)
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [findings.md](../../../../findings.md)
Updated: 2026-04-26
Confidence: high
---

# Star-Neutral Quality Scoring

The core innovation of GitHub Discovery is separating **technical engineering quality** from **social popularity**. Stars are treated as **corroboration metadata** — they tell you HOW MANY people validated quality, not WHAT the quality is. Stars never change the quality score, never act as a ranking signal, and never penalize a repo.

## Evolution: From Anti-Star Bias to Star-Neutral

**Previous design (Phases 0–9):** The system used a `Value Score = quality_score / log10(stars + 10)` formula that actively penalized popular repos. This replaced one bias (pro-star) with another (anti-star).

**Current design (2026-04-25+):** Redesigned to be truly star-neutral. The `value_score` now simply equals `quality_score`. Stars are pure metadata for corroboration level classification.

**Why the change:** No major ranking system (IMDB, Stack Overflow, Reddit, Google) divides by popularity. The correct approach is quality-first ranking with popularity as separate metadata. Anti-star bias was just bias in the opposite direction.

## Key Principles

1. **Quality score is pure technical assessment** — Gate 1+2+3 signals only, no star consideration
2. **Stars = corroboration metadata** — more stars = more users validated quality, but no score change
3. **Hidden gem = informational label** — high quality + low stars (NOT a score modifier)
4. **Ranking = quality_score DESC, confidence DESC** — star-neutral primary sort
5. **Stars are displayed separately** — as `corroboration_level` alongside quality

## Corroboration Levels

Stars classify repos into informational corroboration levels:

| Stars | Level | Meaning |
|-------|-------|---------|
| 0 | `new` | No users yet — quality assessment is the only signal |
| 1–49 | `unvalidated` | Few users have tested this |
| 50–499 | `emerging` | Some community validation |
| 500–4,999 | `validated` | Moderate community confirms quality |
| 5,000+ | `widely_adopted` | Broad community validation |

These levels are informational only — they never change the quality_score or ranking position.

## Hidden Gem Detection

A repo is flagged as a **hidden gem** when:
- `quality_score >= 0.7` (meaningful technical quality — from `ScoringSettings.hidden_gem_min_quality`)
- `stars < 500` (low visibility — from `ScoringSettings.hidden_gem_star_threshold`)

This is an **informational label** — it does NOT affect ranking, does NOT boost or reduce any score, and is displayed as metadata alongside the quality score.

**Fase 2 T1.1 fix (2026-04-26)**: Previously, `models/scoring.py` had hardcoded `_HIDDEN_GEM_MAX_STARS=100` and `_HIDDEN_GEM_MIN_QUALITY=0.5` that diverged from `ScoringSettings` defaults (`hidden_gem_star_threshold=500`, `hidden_gem_min_quality=0.7`). The model-level constants were removed — `ScoreResult.is_hidden_gem` now reads `ScoringSettings` as the **single source of truth**. The `RankedRepo` model also gained an `is_hidden_gem` field to propagate the label through the ranking pipeline.

### T5.4 Decision — Deprecation, Not Removal (2026-04-26)

`is_hidden_gem` exists in **two places**:
1. `ScoreResult.is_hidden_gem` — `@computed_field` on the data model (reads `ScoringSettings`)
2. `ValueScoreCalculator.is_hidden_gem()` — service method with explicit thresholds (canonical)

**Architectural issue**: A Pydantic model should contain data, not business logic. The hidden gem classification is a service-level evaluation, not intrinsic scoring data.

**Decision: deprecate on `ScoreResult`, remove in v0.3.0.**

Rationale for not removing immediately:
1. **Bug already fixed (T1.1)** — Both sources now read from `ScoringSettings`. No inconsistency.
2. **Breaking change** — 11 consumers (MCP tools, API routes, CLI formatters, feasibility scripts, test fixtures) reference `ScoreResult.is_hidden_gem`. Changing them all in a beta is destabilizing.
3. **Standard deprecation pattern** — Add `.. deprecated::` docstring now, remove field in v0.3.0 after consumers migrate.
4. **Priority** — Wave 4 (empirical validation) is the real gap; time spent migrating 11 consumers is better spent on the golden dataset.

Both `ScoreResult.is_hidden_gem` and `RankedRepo.is_hidden_gem` now carry `.. deprecated:: 0.2.0` docstrings directing consumers to `ValueScoreCalculator.is_hidden_gem()`.

## Domain-Awareness

Star relevance varies by domain:
- A DevOps tool with 200 stars may be excellent
- A web framework with 200 stars is likely immature
- Domain profiles (see [Domain Strategy](../domain/domain-strategy.md)) adjust weight expectations
- Each domain has a `star_baseline` for contextual corroboration comparison

## Intra-Domain Ranking

Ranking is performed **within** domain categories, never across:
- CLI tools ranked separately from ML libraries
- Each `DomainType` has its own weight profile
- Cross-domain comparison requires explicit normalization + warning

## Implementation

Star-neutral scoring is implemented across multiple modules:

### `models/scoring.py` — ScoreResult
- `value_score` computed_field: returns `quality_score` (star-neutral)
- `corroboration_level` computed_field: classifies stars into informational buckets
- `is_hidden_gem` computed_field: **deprecated 0.2.0** — informational label, reads `ScoringSettings`. Will be removed in v0.3.0; use `ValueScoreCalculator.is_hidden_gem()` instead
- `coverage: float` — fraction of dimensions with non-zero scores (Fase 2 T1.3)
- `raw_quality_score: float` — quality before coverage damping (Fase 2 T1.3)
- Constants: `_CORROBORATION_UNVALIDATED=50`, `_CORROBORATION_EMERGING=500`, `_CORROBORATION_VALIDATED=5000`
- **Removed** (Fase 2 T1.1): `_HIDDEN_GEM_MAX_STARS`, `_HIDDEN_GEM_MIN_QUALITY` — now in `ScoringSettings` only

### `scoring/value_score.py` — ValueScoreCalculator
- `compute()`: returns `quality_score` unchanged (stars explicitly unused)
- `is_hidden_gem()`: checks quality threshold + star threshold
- `star_context()`: generates corroboration-level description strings
- `normalize_batch()`: normalizes quality only (stars ignored)

### `scoring/ranker.py` — Ranker
- Sort key: `(-quality_score, -confidence, -seeded_hash, full_name)`
- `seeded_hash` uses `hashlib.blake2b(digest_size=8)` for cross-process determinism (Fase 2 T1.2)
- Stars are NOT part of the sort key
- Hidden gem detection uses `quality_score` (not `value_score`)

### `scoring/explainability.py` — ExplainabilityGenerator
- `_star_baseline_comparison()`: uses "corroboration" language (not "penalty")
- Shows corroboration level relative to domain baseline

### CLI output
- `rank.py`: shows `corroboration_level` alongside quality_score
- `explain.py`: includes `corroboration_level` in report
- `compare.py`: winner determined by `quality_score` (not `value_score`)

## E2E Validation (2026-04-25)

Validated with 20 real MCP office repos discovered via GitHub Search + Registry channels:

| Rank | Repo | Quality | Stars | Corroboration |
|------|------|---------|-------|---------------|
| 1 | PsychQuant/che-word-mcp | 0.703 | 0 | new 💎 |
| 2 | modelcontextprotocol/typescript-sdk | 0.672 | 12,281 | widely_adopted |
| 3 | walksoda/crawl-mcp | 0.653 | 0 | new 💎 |

Key observations:
- Two hidden gems (💎) with 0 stars rank above widely-adopted repos — because Gate 3 deep assessment confirmed their quality
- `modelcontextprotocol/typescript-sdk` (12,281 stars) ranks #2 purely on quality, not boosted by stars
- Star-neutral ranking: same quality → same rank, regardless of popularity

## Origin

The original Value Score pattern came from `chriscarrollsmith/github_repo_classifier`, which uses `quality_score / log10(star_count + 10)`. GitHub Discovery initially adopted this, then evolved to star-neutral after recognizing that anti-star bias is still bias. The current design is influenced by how IMDB, Stack Overflow, and Google handle quality vs. popularity separation.

## See Also

- [Tiered Pipeline](tiered-pipeline.md)
- [Domain Strategy](../domain/domain-strategy.md)
- [Competitive Landscape](../domain/competitive-landscape.md)
- [Scoring Dimensions](../domain/scoring-dimensions.md)
- [Phase 5 Implementation](../patterns/phase5-scoring-implementation.md)
