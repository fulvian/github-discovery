---
Title: Scoring Dimensions and Weight Profiles
Topic: domain
Sources: Foundation Blueprint §7, §10; Roadmap Phase 3-5; Star-neutral redesign (2026-04-25)
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md)
Updated: 2026-04-25
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
- `CLI` — Command-line tools
- `web_framework` — Web frameworks and servers
- `data_tool` — Data processing and analysis
- `ml_lib` — Machine learning libraries
- `devops_tool` — DevOps and infrastructure tools
- `library` — General-purpose libraries
- `backend` — Backend services and APIs
- `other` — Catch-all

## Confidence Score

Each score includes a `confidence` indicator (0.0-1.0) based on:
- **Data completeness**: How many dimensions have actual data vs. defaults
- **Signal quality**: API data (high) vs. heuristic (medium) vs. LLM assessment (variable)
- **Assessment depth**: Gate 1 metadata vs. Gate 2 static vs. Gate 3 deep
- **Gate coverage bonus**: additional confidence when all gates are represented

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

An informational label (NOT a score modifier):

| Condition | Threshold |
|-----------|-----------|
| `quality_score >=` | `_HIDDEN_GEM_MIN_QUALITY = 0.5` |
| `stars <` | `_HIDDEN_GEM_MAX_STARS = 100` |

## Implementation Status

**Phase 5 (Layer D) COMPLETE + Star-Neutral Redesign**: The scoring engine is fully implemented in `src/github_discovery/scoring/`. Key implementation modules:
- `engine.py` — ScoringEngine combining Gate 1+2+3 into composite multi-dimensional scores
- `profiles.py` — ProfileRegistry with 11 domain profiles (7 new in Phase 5)
- `value_score.py` — ValueScoreCalculator (star-neutral: returns quality_score unchanged)
- `confidence.py` — ConfidenceCalculator with per-dimension confidence and gate coverage bonus
- `ranker.py` — Ranker with star-neutral intra-domain ranking (quality DESC, confidence DESC)
- `feature_store.py` — SQLite-backed persistence with TTL

See [Phase 5 Implementation](../patterns/phase5-scoring-implementation.md) for full details.

## See Also

- [Star-Neutral Quality Scoring](../architecture/anti-star-bias.md)
- [Tiered Pipeline](../architecture/tiered-pipeline.md)
- [Screening Gates Detail](screening-gates.md)
- [Phase 5 Implementation](../patterns/phase5-scoring-implementation.md)
