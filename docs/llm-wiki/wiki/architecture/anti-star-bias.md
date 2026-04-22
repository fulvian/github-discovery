---
Title: Anti-Star Bias Philosophy
Topic: architecture
Sources: Foundation Blueprint §3, §5, §7; Findings §1
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [findings.md](../../../../findings.md)
Updated: 2026-04-22
Confidence: high
---

# Anti-Star Bias Philosophy

The core innovation of GitHub Discovery is separating **technical engineering quality** from **social popularity**. Stars are treated as context only, never as a primary scoring signal.

## Key Points

- Stars are **context only**, never a primary ranking signal
- The `Value Score` formula identifies hidden gems: high-quality repos with low star counts
- Intra-domain ranking prevents unfair cross-category comparisons
- Existing discovery tools (search engines, AI agents) systematically over-weight popularity

## The Problem

Current discovery channels overemphasize:
- **Star count** (popularity contest)
- **Social signals** (Reddit, blog discussions, media momentum)
- **Trend dashboards** (velocity-biased)

Result: technically excellent repos with few/no stars remain invisible.

## The Value Score Formula

```
Value Score = quality_score / log10(star_count + 10)
```

- `quality_score`: composite from Gate 1+2+3 scores
- `log10(star_count + 10)`: logarithmic dampening of star influence
- The `+ 10` prevents division issues at zero stars and dampens small star counts
- Repos with high quality but low stars naturally rise in ranking

## Why log10?

- Linear star counts would still heavily bias toward popular repos
- log10 dampening: 100 stars → 2.0, 1000 → 3.0, 10000 → 4.0
- Even a repo with 0 stars has a denominator of 1.0 (log10(10))
- This means a quality repo with 50 stars can outrank a mediocre one with 5000 stars

## Domain-Awareness

Star relevance varies by domain:
- A DevOps tool with 200 stars may be excellent
- A web framework with 200 stars is likely immature
- Domain profiles (see [Domain Strategy](../domain/domain-strategy.md)) adjust weight expectations

## Intra-Domain Ranking

Ranking is performed **within** domain categories, never across:
- CLI tools ranked separately from ML libraries
- Each `DomainType` has its own weight profile
- Cross-domain comparison requires explicit normalization + warning

## Origin

The Value Score pattern was first identified in `chriscarrollsmith/github_repo_classifier`, which uses `quality_score / log10(star_count + 10)`. GitHub Discovery adopts and extends this pattern with domain-aware weighting and multi-gate confidence scores.

## See Also

- [Tiered Pipeline](tiered-pipeline.md)
- [Domain Strategy](../domain/domain-strategy.md)
- [Competitive Landscape](../domain/competitive-landscape.md)