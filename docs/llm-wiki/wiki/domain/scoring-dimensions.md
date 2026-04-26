---
Title: Scoring Dimensions and Weight Profiles
Topic: domain
Sources: Foundation Blueprint §7, §10; Roadmap Phase 3-5; Star-neutral redesign (2026-04-25); Fase 2 Audit Remediation (2026-04-26)
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md)
Updated: 2026-04-26
Confidence: high
---

# Scoring Dimensions and Weight Profiles

GitHub Discovery evaluates repos across 8 dimensions with domain-dependent weighting. The scoring is multi-dimensional — there is never a single aggregate score without per-dimension breakdown. **Stars are never used as a scoring signal** — they are metadata for corroboration level only.

## The 8 Evaluation Dimensions

| # | Dimension | Default Weight | Description |
|---|-----------|---------------|-------------|
| 1 | Code Quality | 20% | Code style, complexity, test coverage signals, static analysis |
| 2 | Architecture & Modularity | 15% | Directory structure, coupling, abstraction layers, API surface |
| 3 | Testability & Verification | 15% | Test presence, coverage, test quality, CI integration |
| 4 | Documentation & Developer Experience | 10% | README quality, API docs, guides, onboarding friction |
| 5 | Maintenance & Project Operations | 15% | Commit cadence, release discipline, issue management, bus factor |
| 6 | Security & Supply Chain Hygiene | 10% | OpenSSF Scorecard, vulnerability scanning, secret hygiene, dependency pinning |
| 7 | Functional Completeness | 10% | Fit to use-case, feature coverage, API completeness |
| 8 | Innovation & Distinctiveness | 5% | Novel approaches, unique positioning vs alternatives |

## Domain-Dependent Weights

Default weights are **not universal**. Each domain has specific weight profiles:

| Domain | Testing | Docs | Maintenance | Security | Notes |
|--------|---------|------|-------------|----------|-------|
| CLI tools | 20% | 10% | 20% | 10% | Maintenance and reliability matter most |
| Web frameworks | 15% | 15% | 15% | 10% | Documentation critical for adoption |
| Data tools | 10% | 15% | 15% | 10% | Functional completeness > testing |
| ML libraries | 10% | 10% | 15% | 5% | Innovation weight may increase |
| DevOps tools | 20% | 10% | 15% | 15% | Security and reliability paramount |
| Backend services | 15% | 10% | 20% | 15% | Architecture weighted at 20%, highest |

## Domain Taxonomy

`DomainType` enum:
- `cli` — Command-line tools
- `web_framework` — Web frameworks and servers
- `data_tool` — Data processing and analysis
- `ml_lib` — Machine learning libraries
- `devops_tool` — DevOps and infrastructure tools
- `library` — General-purpose libraries
- `backend` — Backend services and APIs
- `security_tool` — Security analysis and tooling
- `lang_tool` — Language servers, linters, formatters
- `test_tool` — Testing frameworks and utilities
- `doc_tool` — Documentation generators and tools
- `other` — Catch-all (default)

## Confidence Score

Each score includes a `confidence` indicator (0.0-1.0) based on:
- **Data completeness**: How many dimensions have actual data vs. defaults
- **Signal quality**: API data (high) vs. heuristic (medium) vs. LLM assessment (variable)
- **Assessment depth**: Gate 1 metadata vs. Gate 2 static vs. Gate 3 deep
- **Gate coverage bonus**: additional confidence when all gates are represented

### Per-Dimension Confidence from Gate 1+2 (Fase 2 T2.3)

Dimensions assessed purely from Gate 1+2 signals have pre-set confidence caps:

| Dimension | Gate 1+2 Confidence Cap | Rationale |
|-----------|------------------------|-----------|
| TESTING | 0.55 | Test presence/count is a strong proxy |
| MAINTENANCE | 0.50 | Release cadence and issue activity are moderate signals |
| SECURITY | 0.50 | Scorecard + OSV give moderate confidence |
| DOCUMENTATION | 0.40 | README presence is weak proxy for quality |
| CODE_QUALITY | 0.40 | Complexity metrics without deep review |
| ARCHITECTURE | 0.0 | Cannot assess without LLM |
| FUNCTIONALITY | 0.0 | Cannot assess without LLM |
| INNOVATION | 0.0 | Cannot assess without LLM |

Gate 3 (LLM deep assessment) overrides these caps with LLM-reported confidence.

### Missing Critical Dimension Penalty (Fase 2 T2.2)

`ConfidenceCalculator.compute()` applies a **-0.10 penalty** for each missing critical dimension (TESTING, SECURITY, MAINTENANCE). This prevents high confidence when essential quality signals are absent.

### Weighted Confidence (Fase 2 T2.2)

Confidence is computed as a **weighted average** using the domain profile weights, not a simple mean. Dimensions with higher weight in the domain profile contribute more to overall confidence. Missing dimensions still contribute via the penalty mechanism.

### Coverage Field (Fase 2 T1.3)

`ScoreResult` now includes:
- `coverage: float` — fraction of dimensions with non-zero scores (0.0–1.0)
- `raw_quality_score: float` — quality before coverage damping

**Quality damping**: `quality_score = raw * (0.5 + 0.5 * coverage)` — repos assessed on fewer dimensions get proportionally damped quality scores.

## Star-Neutral Value Score (2026-04-25 redesign)

```
value_score = quality_score   (stars are NOT used)
```

The `value_score` is kept for backward compatibility but now simply equals `quality_score`. Stars are classified into corroboration levels (new/unvalidated/emerging/validated/widely_adopted) and displayed as separate metadata.

See [Star-Neutral Quality Scoring](../architecture/anti-star-bias.md) for full details.

## Corroboration Level

Stars are classified into informational buckets:

| Stars | Level | Threshold Constant |
|-------|-------|-------------------|
| 0 | `new` | — |
| 1–49 | `unvalidated` | `_CORROBORATION_UNVALIDATED = 50` |
| 50–499 | `emerging` | `_CORROBORATION_EMERGING = 500` |
| 500–4,999 | `validated` | `_CORROBORATION_VALIDATED = 5000` |
| 5,000+ | `widely_adopted` | — |

## Hidden Gem Label

An informational label (NOT a score modifier). Thresholds are single-sourced from `ScoringSettings`:

| Condition | Setting | Default |
|-----------|---------|---------|
| `quality_score >=` | `hidden_gem_min_quality` | 0.7 |
| `stars <` | `hidden_gem_star_threshold` | 500 |

**Fase 2 T1.1 fix**: Previously, `models/scoring.py` had hardcoded constants (`_HIDDEN_GEM_MAX_STARS=100`, `_HIDDEN_GEM_MIN_QUALITY=0.5`) that diverged from `ScoringSettings` defaults (`hidden_gem_star_threshold=500`, `hidden_gem_min_quality=0.7`). The model-level constants were removed — `ScoreResult.is_hidden_gem` now reads `ScoringSettings` as the single source of truth. The `RankedRepo` model also gained an `is_hidden_gem` field.

## Dimension Derivation Map (Fase 2 T2.1)

`ScoringEngine._DERIVATION_MAP` controls how dimensions are composed from screening sub-scores when Gate 3 (LLM) data is unavailable:

| Dimension | Sub-score Sources & Weights |
|-----------|---------------------------|
| ARCHITECTURE | *(empty — requires Gate 3)* |
| CODE_QUALITY | complexity(0.35) + test_footprint(0.25) + review_practice(0.25) + ci_cd(0.15) |
| DOCUMENTATION | hygiene(0.7) + release_discipline(0.3) |
| TESTING | test_footprint(0.7) + ci_cd(0.3) |
| MAINTENANCE | maintenance(0.45) + release_discipline(0.35) + ci_cd(0.10) + hygiene(0.10) |
| SECURITY | security_hygiene(0.35) + vulnerability(0.25) + secret_hygiene(0.25) + dependency_quality(0.15) |
| FUNCTIONALITY | *(empty — requires Gate 3)* |
| INNOVATION | *(empty — requires Gate 3)* |

Key changes from Fase 2 audit: ARCHITECTURE derivation cleared (was using weak proxies), CODE_QUALITY rebalanced (complexity now 0.35, was too low), DOCUMENTATION uses release_discipline instead of review_practice.

### Per-Profile Derivation Maps (Fase 2 T5.1)

Each `DomainProfile` can override the default derivation map via its `derivation_map` field. The engine merges profile-specific entries with the module-level defaults — dimensions specified in the profile override defaults, unspecified dimensions keep the default mapping.

### Custom Profile Loading (Fase 2 T5.3)

`ProfileRegistry` supports loading custom profiles from YAML/TOML files:
- `load_from_yaml()` / `load_from_toml()` / `load_custom_profiles()` (auto-detects format)
- Case-insensitive domain_type matching (YAML `ML_LIB` → enum `ml_lib`)
- Supports custom derivation_map and gate_thresholds
- `ScoringSettings.custom_profiles_path` auto-loads on registry initialization

## Implementation Status

**Phase 5 (Layer D) COMPLETE + Star-Neutral Redesign + Fase 2 Audit Remediation (Wave 1–3, 5)**: The scoring engine is fully implemented in `src/github_discovery/scoring/`. Key implementation modules:
- `engine.py` — ScoringEngine combining Gate 1+2+3 into composite multi-dimensional scores, revised `_DERIVATION_MAP` (Fase 2 T2.1), quality damping via coverage (Fase 2 T1.3), per-profile derivation map merging (T5.1)
- `profiles.py` — ProfileRegistry with 12 domain profiles, custom YAML/TOML loading (T5.3), case-insensitive domain_type matching, auto-load from ScoringSettings
- `value_score.py` — ValueScoreCalculator (star-neutral: returns quality_score unchanged)
- `confidence.py` — ConfidenceCalculator with per-dimension confidence (Fase 2 T2.3), weighted average (Fase 2 T2.2), missing critical dimension penalty (Fase 2 T2.2), gate coverage bonus
- `ranker.py` — Ranker with star-neutral intra-domain ranking (quality DESC, confidence DESC), deterministic `hashlib.blake2b` tie-breaking (Fase 2 T1.2)
- `feature_store.py` — SQLite-backed persistence with TTL

**Fase 2 additional modules:**
- `assessment/types.py` — `HeuristicFallback` model with confidence capped at 0.25 (Fase 2 T2.4)
- `assessment/heuristics.py` — Repomix header-based test detection, `_TEST_DIR_PATTERNS`/`_TEST_FRAMEWORK_PATTERNS` split (Fase 2 T2.5)

**Test count**: 1326 → 1587 (+261 new tests from Fase 2)

See [Phase 5 Implementation](../patterns/phase5-scoring-implementation.md) for full details.

## See Also

- [Star-Neutral Quality Scoring](../architecture/anti-star-bias.md)
- [Tiered Pipeline](../architecture/tiered-pipeline.md)
- [Screening Gates Detail](screening-gates.md)
- [Phase 5 Implementation](../patterns/phase5-scoring-implementation.md)
