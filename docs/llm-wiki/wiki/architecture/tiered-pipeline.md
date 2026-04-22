---
Title: Tiered Scoring Pipeline
Topic: architecture
Sources: Foundation Blueprint §6, §16; Roadmap Phase 2-5
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md)
Updated: 2026-04-22
Confidence: high
---

# Tiered Scoring Pipeline

The core architecture of GitHub Discovery is a **4-gate tiered pipeline** that progressively filters candidates from broad discovery to deep technical assessment. Each gate introduces more expensive analysis, ensuring LLM costs are only incurred on the most promising candidates.

## Key Points

- **Gate 0 — Candidate Discovery**: Multichannel collection of candidate repos (GitHub Search, Code Search, dependency graphs, package registries, awesome lists, seed expansion)
- **Gate 1 — Metadata Screening**: Zero LLM cost. Repository-level signals from API: activity, hygiene files, release discipline, review evidence, test footprint, CI/CD, dependency quality
- **Gate 2 — Static/Security Screening**: Zero or low cost. Automated tools on shallow clone: OpenSSF Scorecard, gitleaks, OSV vulnerability scan, scc/cloc complexity metrics
- **Gate 3 — LLM Deep Assessment**: Expensive. Only for top 10-15% percentile. Repomix + LLM structured evaluation across 8 dimensions, with budget control and caching
- **Hard rule**: Never send a candidate to Gate 3 without passing Gate 1 + Gate 2

## Gate Architecture

```
Gate 0 (Discovery)     → Pool of candidates with discovery_score
Gate 1 (Metadata)      → Filter with zero LLM cost, metadata signals only
Gate 2 (Static/Sec)    → Further filter with automated tool signals
Gate 3 (Deep LLM)      → Only top percentile, expensive deep assessment
Layer D (Scoring)       → Anti-star bias ranking + explainability
```

### Gate 1 Feature Set (Zero LLM)

| Sub-score | Signals |
|-----------|---------|
| Hygiene Score | LICENSE (SPDX), CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md, CHANGELOG.md, README.md quality |
| Maintenance Score | Commit recency/cadence, release cadence, bus factor proxy |
| Review Practice Score | PR activity, review presence, label usage |
| Test Footprint Score | Test directories/patterns ratio, test config presence |
| CI/CD Score | `.github/workflows/` presence, CI badges, config validity |
| Release Discipline Score | Semver tagging, release cadence, changelog per release |
| Dependency Quality Score | Lockfile presence, dependency pinning, update signals (dependabot/renovate) |

### Gate 2 Feature Set (Zero/Low Cost)

| Sub-score | Signals |
|-----------|---------|
| Security Hygiene Score | OpenSSF Scorecard results, branch protection, workflow security |
| Vulnerability Score | OSV API scan on declared dependencies |
| Complexity Score | scc/cloc LOC, language breakdown, complexity metrics |
| Secret Hygiene Score | gitleaks scan on shallow clone |

### Gate 3 Feature Set (Expensive)

| Dimension | Weight (default) |
|-----------|-------------------|
| Code Quality | 20% |
| Architecture & Modularity | 15% |
| Testability & Verification | 15% |
| Documentation & DX | 10% |
| Maintenance & Operations | 15% |
| Security & Supply Chain | 10% |
| Functional Completeness | 10% |
| Innovation & Distinctiveness | 5% |

**Note**: Weights are domain-dependent (see [Domain Strategy](../domain/domain-strategy.md)).

## LLM Budget Policy (Hard Rules)

1. No deep-scan below Gate 1+2 threshold
2. Maximum token budget per day and per repo
3. Timeout and early-stop on repos too large or unparseable
4. Mandatory caching of intermediate results and dedup by commit SHA

## Output Per Gate

| Gate | Output |
|------|--------|
| Gate 0 | `RepoCandidate` pool with `discovery_score` |
| Gate 1 | `MetadataScreenResult` with sub-scores (0.0-1.0) and `gate1_pass: bool` |
| Gate 2 | `StaticScreenResult` with sub-scores (0.0-1.0) and `gate2_pass: bool` |
| Gate 3 | `DeepAssessmentResult` with 8 `DimensionScore` entries + `explanation`, `evidence`, `confidence` |
| Layer D | `ScoreResult` → `RankedRepo` with `value_score`, intra-domain rank, `ExplainabilityReport` |

## See Also

- [Anti-Star Bias](anti-star-bias.md)
- [Screening Gates Detail](../domain/screening-gates.md)
- [MCP-Native Design](mcp-native-design.md)
- [Session & Workflow Patterns](../patterns/session-workflow.md)