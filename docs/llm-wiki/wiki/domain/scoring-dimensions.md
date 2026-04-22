---
Title: Scoring Dimensions and Weight Profiles
Topic: domain
Sources: Foundation Blueprint §7, §10; Roadmap Phase 3-5
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md)
Updated: 2026-04-22
Confidence: medium
---

# Scoring Dimensions and Weight Profiles

GitHub Discovery evaluates repos across 8 dimensions with domain-dependent weighting. The scoring is multi-dimensional — there is never a single aggregate score without per-dimension breakdown.

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
| Backend services | 15% | 10% | 20% | 15% | Maintenance and security critical |

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

## Value Score Computation

```
ValueScore = quality_score / log10(star_count + 10)
```

Where `quality_score` is the domain-weighted composite of assessed dimensions. See [Anti-Star Bias](../architecture/anti-star-bias.md).

## See Also

- [Anti-Star Bias](../architecture/anti-star-bias.md)
- [Tiered Pipeline](../architecture/tiered-pipeline.md)
- [Screening Gates Detail](screening-gates.md)