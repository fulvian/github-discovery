# Scoring Methodology

> **Document ID**: T2.1 — Scoring Methodology with Derivation Map Rationale
> **Project**: GitHub Discovery — MCP-Native Agentic Discovery Engine
> **Status**: Approved

| Revision | Date       | Author              | Description                         |
|----------|------------|---------------------|-------------------------------------|
| 1.0      | 2025-04-26 | GitHub Discovery    | Initial derivation map and rationale |

---

## 1. Overview

GitHub Discovery evaluates repositories across **8 quality dimensions** using a tiered pipeline that progressively deepens assessment while controlling cost:

| Gate | Layer | Cost        | Data Sources                          | Sub-Scores |
|------|-------|-------------|---------------------------------------|------------|
| 0    | A     | Free        | GitHub Search, registries, awesome lists | — |
| 1    | B     | API only    | GitHub REST API (metadata)            | 7 sub-scores |
| 2    | B     | Low         | Shallow clone, OSV API, OpenSSF Scorecard | 4 sub-scores |
| 3    | C     | Expensive   | LLM deep assessment                   | 8 dimensions |

The scoring engine (Layer D) combines results from Gates 1+2+3 into a composite `quality_score` ∈ [0.0, 1.0] with per-dimension breakdowns, confidence tracking, and coverage damping.

**Core principle**: Stars are metadata only — never a primary scoring signal, never a penalty. The `quality_score` is a pure technical assessment.

---

## 2. Eight Quality Dimensions

The scoring dimensions are aligned with the project's Foundation Blueprint §7:

| # | Dimension         | Description                                          | Default Weight |
|---|-------------------|------------------------------------------------------|----------------|
| 1 | CODE_QUALITY      | Code structure, complexity, review practices         | 20%            |
| 2 | ARCHITECTURE      | Modularity, coupling, abstraction layers             | 15%            |
| 3 | TESTING           | Test presence, coverage culture, CI integration      | 15%            |
| 4 | DOCUMENTATION     | README, contributing guides, changelogs              | 10%            |
| 5 | MAINTENANCE       | Commit cadence, issue closure, release regularity    | 15%            |
| 6 | SECURITY          | Vulnerability management, secret hygiene, supply chain | 10%          |
| 7 | FUNCTIONALITY     | Feature completeness, API surface, usefulness        | 10%            |
| 8 | INNOVATION        | Novelty, differentiation from alternatives           | 5%             |

Default weights are per the `DEFAULT_PROFILE` (DomainType.OTHER). Each domain profile can override these weights — see §6.

---

## 3. Gate 1 — Metadata Sub-Scores

Gate 1 produces **7 sub-scores** from GitHub REST API metadata alone. No cloning, no LLM calls, no external tools. All values are ∈ [0.0, 1.0].

| Sub-Score            | Source                      | Signals                                                           |
|----------------------|-----------------------------|-------------------------------------------------------------------|
| `hygiene`            | Repo contents listing       | README, LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY.md, changelog presence |
| `maintenance`        | Commits, issues, contributors | Commit cadence (30-day window), issue closure ratio, contributor bus factor |
| `release_discipline` | Releases, tags              | Semantic versioning, release tag count, changelog updates         |
| `review_practice`    | Pull requests               | PR review ratio, required reviewers, CODEOWNERS file presence     |
| `test_footprint`     | Repo contents, languages    | Test file ratio, test directory presence, test framework files    |
| `ci_cd`              | Repo contents               | GitHub Actions workflows, CI config files, build status badges    |
| `dependency_quality` | Lockfiles, manifests        | Lockfile presence, dependency pinning, outdated dependency ratio  |

**Implementation reference**: `src/github_discovery/screening/gate1_metadata.py` — `Gate1MetadataScreener`

---

## 4. Gate 2 — Static/Security Sub-Scores

Gate 2 produces **4 sub-scores** using external tools and a shallow clone (`git clone --depth=1`). Only runs on candidates that passed Gate 1 (hard gate enforcement). All values ∈ [0.0, 1.0].

| Sub-Score          | Tool/Source              | Signals                                                    |
|--------------------|--------------------------|------------------------------------------------------------|
| `complexity`       | `scc` (subprocess)       | Cyclomatic complexity from AST analysis                    |
| `security_hygiene` | OpenSSF Scorecard API    | Security policy, branch protection, token permissions      |
| `vulnerability`    | OSV API                  | Known CVEs, vulnerability count and severity               |
| `secret_hygiene`   | `gitleaks` (subprocess)  | Detected secrets/credentials in repository                 |

Tool failures produce graceful degradation: a fallback score of 0.3 with confidence 0.0, rather than blocking the pipeline.

**Implementation reference**: `src/github_discovery/screening/gate2_static.py` — `Gate2StaticScreener`

---

## 5. Derivation Map

### 5.1 Purpose

When Gate 3 (LLM deep assessment) data is unavailable — which is the common case for most candidates — dimension scores must be **derived** from Gate 1+2 sub-scores. The derivation map defines which sub-scores contribute to each dimension and with what weight.

### 5.2 The Map

```python
_DERIVATION_MAP = {
    CODE_QUALITY: [
        ("complexity", 0.35),       # Gate 2: cyclomatic complexity
        ("test_footprint", 0.25),   # Gate 1: test file presence/ratio
        ("review_practice", 0.25),  # Gate 1: PR review culture
        ("ci_cd", 0.15),           # Gate 1: CI/CD configuration
    ],
    ARCHITECTURE: [],               # Empty — not derivable from metadata
    TESTING: [
        ("test_footprint", 0.7),   # Gate 1: test presence
        ("ci_cd", 0.3),           # Gate 1: CI integration
    ],
    DOCUMENTATION: [
        ("hygiene", 0.7),              # Gate 1: README/LICENSE/contributing
        ("release_discipline", 0.3),   # Gate 1: changelog/tag cadence
    ],
    MAINTENANCE: [
        ("maintenance", 0.45),          # Gate 1: commit cadence, issue closure
        ("release_discipline", 0.35),   # Gate 1: release regularity
        ("ci_cd", 0.10),               # Gate 1: CI maturity
        ("hygiene", 0.10),             # Gate 1: project hygiene
    ],
    SECURITY: [
        ("security_hygiene", 0.35),     # Gate 2: security policy/audit
        ("vulnerability", 0.25),        # Gate 2: known CVEs (OSV)
        ("secret_hygiene", 0.25),       # Gate 2: secret detection
        ("dependency_quality", 0.15),   # Gate 1: dependency pinning
    ],
    FUNCTIONALITY: [],              # Empty — requires LLM
    INNOVATION: [],                 # Empty — requires LLM
}
```

**Implementation reference**: `src/github_discovery/scoring/engine.py` — `_DERIVATION_MAP`

### 5.3 Derivation Formula

For a dimension *d* with mapping entries `{(s₁, w₁), (s₂, w₂), ...}`:

```
derived_score(d) = Σ(sᵢ × wᵢ) / Σ(wᵢ)
```

where *sᵢ* is the value of sub-score *i* (only if available), and *wᵢ* is its weight. If a sub-score is unavailable (e.g., Gate 2 not run), its contribution is excluded and the denominator adjusts. This prevents missing sub-scores from being treated as zero.

If no sub-scores are available for a dimension, the result is the **neutral default**: value 0.5, confidence 0.0, source `default_neutral`.

### 5.4 Priority Chain

For each dimension, the engine applies this priority:

1. **Gate 3 (LLM) score** — if available, use directly (confidence from LLM, typically 0.6–0.9)
2. **Gate 1+2 derived** — if derivation map has entries and screening data exists (confidence 0.4)
3. **Neutral default** — value 0.5, confidence 0.0 (excluded from weighted average)

---

## 6. Per-Profile Override (T5.1)

Each `DomainProfile` can override the default derivation map via its `derivation_map` field. The engine merges profile-specific entries with defaults:

- **Dimensions specified in the profile** → override the default mapping entirely
- **Dimensions not specified** → keep the default `_DERIVATION_MAP` entry

### Example

A hypothetical ML_LIB profile could override CODE_QUALITY to weight complexity higher:

```yaml
profiles:
  - domain_type: ml_lib
    display_name: "ML Library"
    derivation_map:
      code_quality:
        - ["complexity", 0.45]
        - ["test_footprint", 0.20]
        - ["review_practice", 0.20]
        - ["ci_cd", 0.15]
```

This is useful because ML code quality is heavily influenced by code complexity — long notebook cells, deeply nested model architectures, and complex data pipelines are common anti-patterns in ML repos.

**Implementation reference**: `src/github_discovery/scoring/engine.py` — `_resolve_derivation_map()`

---

## 7. Design Decisions and Rationale

### 7.1 ARCHITECTURE — Empty Derivation

**Decision**: ARCHITECTURE has an empty derivation map. It cannot be scored without Gate 3.

**Rationale**: Cyclomatic complexity is a measure of code path density, not architectural quality. A well-architected system can have complex individual modules; conversely, a flat directory structure does not imply good separation of concerns. True architectural assessment requires understanding:

- Coupling between modules
- Abstraction layer boundaries
- API surface design
- Dependency direction (acyclicity)

These properties are not derivable from metadata alone. Representing ARCHITECTURE as an empty derivation map is honest — it yields a neutral default (0.5, confidence 0.0) that is excluded from the weighted average, rather than a misleading proxy.

**Confidence when derived**: 0.0 (not derivable from Gate 1+2)

### 7.2 CODE_QUALITY — Product Over Process

**Decision**: Structural signals (complexity 0.35, test_footprint 0.25) are weighted higher than process signals (review_practice 0.25, ci_cd 0.15).

**Rationale**: There is a meaningful distinction between what the code *is* (product quality) and how the code is *made* (process quality). Structural signals directly measure the artifact:

- **Complexity** (from `scc` AST analysis) reflects code path density — a direct indicator of readability, maintainability, and defect probability. McCabe's cyclomatic complexity has been validated as a defect predictor across multiple studies [1].
- **Test footprint** (test file ratio) reflects whether the codebase has test infrastructure — a strong proxy for testability and regression safety.

Process signals are valuable but indirect:

- **Review practice** measures process discipline, not code quality directly. Reviewed code can still be complex or poorly structured.
- **CI/CD** measures automation maturity — a process metric that correlates with but does not guarantee code quality.

The 0.35/0.25/0.25/0.15 split gives 60% weight to structural (product) and 40% to process signals.

**Confidence when derived**: 0.40

### 7.3 DOCUMENTATION — Causal Chain Correction

**Decision**: `review_practice` was removed; `release_discipline` was added.

**Rationale**: The original derivation included `review_practice` for DOCUMENTATION. However, PR review culture has no causal relationship with documentation quality — reviewers assess code changes, not prose quality. The sub-scores that actually reflect documentation are:

- **Hygiene** (0.70) — directly checks for README, CONTRIBUTING, CODE_OF_CONDUCT, and other documentation files. This is the strongest available signal.
- **Release discipline** (0.30) — changelogs, semantic versioning, and release notes are forms of change documentation. Projects with good release discipline document what changed and why.

**Confidence when derived**: 0.40

### 7.4 TESTING — Unchanged

**Decision**: `test_footprint` (0.7) + `ci_cd` (0.3) is a reasonable proxy.

**Rationale**: Test footprint directly measures whether test infrastructure exists — test directories, test files, and test frameworks. CI/CD configuration indicates whether tests are actually run automatically. The 0.7/0.3 split reflects that test *presence* is the stronger signal; CI integration is corroborative.

This is a quantity proxy, not a quality proxy — it cannot assess test effectiveness or coverage depth. Gate 3 is needed for that.

**Confidence when derived**: 0.55 (strongest Gate 1+2 derivation due to direct causal link)

### 7.5 MAINTENANCE — Double-Counting Avoidance

**Decision**: maintenance (0.45) + release_discipline (0.35) + ci_cd (0.10) + hygiene (0.10).

**Rationale**: The maintenance dimension is the most signal-rich from Gate 1 — four sub-scores contribute. The weight distribution avoids double-counting:

- **maintenance** (0.45) — primary signal: commit cadence, issue closure ratio, contributor bus factor. These directly measure ongoing project health.
- **release_discipline** (0.35) — captures release regularity, which is a distinct aspect of maintenance (predictable delivery cadence).
- **ci_cd** (0.10) — CI maturity contributes to maintenance confidence but is a minor factor. Kept low because ci_cd already contributes to CODE_QUALITY and TESTING.
- **hygiene** (0.10) — project hygiene (README, LICENSE) is a weak maintenance proxy. Kept minimal to avoid double-counting with DOCUMENTATION.

The low weights for ci_cd and hygiene (0.10 each) prevent these signals from being overrepresented in the composite score, since they already contribute to other dimensions.

**Confidence when derived**: 0.50

### 7.6 SECURITY — Well-Structured

**Decision**: security_hygiene (0.35) + vulnerability (0.25) + secret_hygiene (0.25) + dependency_quality (0.15).

**Rationale**: The four sub-scores cover distinct security aspects:

| Sub-Score           | Aspect            | What It Measures                                  |
|---------------------|-------------------|---------------------------------------------------|
| security_hygiene    | Policy            | Security policy presence, branch protection       |
| vulnerability       | Exposure          | Known CVEs from OSV database                      |
| secret_hygiene      | Leakage           | Accidentally committed secrets/credentials        |
| dependency_quality  | Supply chain      | Dependency pinning, lockfile presence             |

The 0.35 weight on security_hygiene reflects that security *policy* presence is the most actionable leading indicator — projects with explicit security policies (SECURITY.md, vulnerability reporting process) tend to be more proactive about security overall [3].

The 0.15 weight on dependency_quality reflects that it is a supply-chain signal rather than a direct vulnerability signal. Dependency pinning prevents supply chain attacks but does not guarantee the pinned versions are secure.

**Confidence when derived**: 0.50

### 7.7 FUNCTIONALITY and INNOVATION — Empty Derivations

**Decision**: Both dimensions have empty derivation maps. They require Gate 3 (LLM) assessment.

**Rationale**:

- **FUNCTIONALITY** requires understanding what the project does, how complete its feature set is, and how useful it is for its stated purpose. This cannot be inferred from file counts or CI configuration.
- **INNOVATION** requires comparing the project against its alternatives and assessing novelty. Metadata cannot capture whether a project introduces new approaches, solves problems differently, or fills a previously unmet need.

These dimensions represent the "understanding" layer that only LLM assessment can provide. When Gate 3 is unavailable, they default to 0.5 with confidence 0.0 and are excluded from the weighted average.

**Confidence when derived**: 0.0 (not derivable from Gate 1+2)

---

## 8. Composite Score Computation

### 8.1 Weighted Average

The composite `quality_score` is computed as a domain-weighted average:

```
raw_score = Σ(dim_score × dim_weight) / Σ(dim_weight)
```

where `dim_weight` comes from the domain profile's `dimension_weights`, and only dimensions with confidence > 0.0 are included. Dimensions with confidence 0.0 (neutral defaults) are excluded and their weight is redistributed proportionally.

### 8.2 Coverage

Coverage measures the fraction of profile weight backed by real data:

```
coverage = Σ(included_dim_weights) / Σ(all_dim_weights)
```

- coverage = 1.0: all dimensions have actual data
- coverage = 0.6: only 60% of profile weight has real data

### 8.3 Coverage Damping

To conservatively penalize low-coverage scores (maximum 50% damping):

```
quality_score = raw_score × (0.5 + 0.5 × coverage)
```

| Coverage | Damping Factor | Example: raw=0.80 |
|----------|---------------|-------------------|
| 1.0      | 1.00          | 0.80              |
| 0.8      | 0.90          | 0.72              |
| 0.6      | 0.80          | 0.64              |
| 0.4      | 0.70          | 0.56              |
| 0.0      | 0.50          | 0.40              |

This prevents repos with only 2–3 dimensions scored from achieving artificially high composites while maintaining a reasonable floor.

### 8.4 Confidence

Overall confidence is computed as a weighted average of per-dimension confidences (using profile weights), plus a gate coverage bonus and minus a missing-critical-dimension penalty:

```
confidence = weighted_avg(dim_confidences)
           + gate_coverage_bonus
           - missing_critical_penalty
```

**Gate coverage bonus**:

| Gates Completed | Bonus |
|-----------------|-------|
| Gate 1 only     | +0.00 |
| Gate 1 + 2      | +0.05 |
| Gate 1 + 2 + 3  | +0.10 |

**Missing critical dimension penalty**: If any dimension with profile weight ≥ 0.15 has confidence ≤ 0.0, a 0.10 penalty is applied.

**Per-dimension confidence from Gate 1+2**:

| Dimension      | Confidence | Reason                              |
|----------------|------------|--------------------------------------|
| TESTING        | 0.55       | Strong mapping (test_footprint direct) |
| MAINTENANCE    | 0.50       | Multiple contributing sub-scores     |
| SECURITY       | 0.50       | Well-structured mapping              |
| DOCUMENTATION  | 0.40       | hygiene + release_discipline         |
| CODE_QUALITY   | 0.40       | Revised mapping (complexity + test)  |
| ARCHITECTURE   | 0.00       | Empty derivation map                 |
| FUNCTIONALITY  | 0.00       | Not derivable from metadata          |
| INNOVATION     | 0.00       | Not derivable from metadata          |

**Expected confidence ranges**:

| Scenario                        | Range    |
|---------------------------------|----------|
| No data at all                  | 0.00     |
| Solo Gate 1                     | 0.25–0.40|
| Gate 1+2, no Gate 3             | 0.35–0.55|
| Gate 1+2+3 (partial dimensions) | 0.50–0.70|
| Gate 1+2+3 (all 8 dimensions)   | 0.65–0.90|

**Implementation reference**: `src/github_discovery/scoring/confidence.py` — `ConfidenceCalculator`

---

## 9. Star-Neutral Ranking

Stars are **corroboration metadata** — they tell you how many people have validated quality, not what the quality is. The ranking system is star-neutral:

- `quality_score` = pure technical assessment (Gate 1+2+3), no star consideration
- `value_score` = equals `quality_score` (kept for backward compatibility)
- `corroboration_level` = informational label based on star count
- `is_hidden_gem` = informational label (high quality + low stars)

**Corroboration levels**:

| Stars       | Level           | Interpretation                                    |
|-------------|-----------------|---------------------------------------------------|
| 0           | `new`           | No user validation yet                             |
| 1–49        | `unvalidated`   | Few users have tested                              |
| 50–499      | `emerging`      | Some community validation                          |
| 500–4,999   | `validated`     | Moderate community validation                      |
| 5,000+      | `widely_adopted` | Broad community validation                         |

**Implementation reference**: `src/github_discovery/scoring/value_score.py` — `ValueScoreCalculator`

---

## 10. Domain Profiles

Each of the 12 domain types has a specific weight profile that reflects the quality priorities of that domain. Weights must sum to 1.0 (±0.01).

### 10.1 Built-In Profiles

| Domain         | CODE | ARCH | TEST | DOC  | MAINT | SEC  | FUNC | INNO |
|----------------|------|------|------|------|-------|------|------|------|
| LIBRARY        | .20  | .15  | .15  | .15  | .15   | .10  | .05  | .05  |
| CLI            | .15  | .10  | .20  | .10  | .20   | .10  | .10  | .05  |
| WEB_FRAMEWORK  | .15  | .15  | .15  | .15  | .15   | .10  | .10  | .05  |
| DATA_TOOL      | .15  | .10  | .10  | .15  | .15   | .10  | .20  | .05  |
| ML_LIB         | .10  | .10  | .10  | .10  | .15   | .05  | .25  | .15  |
| BACKEND        | .15  | .20  | .15  | .10  | .15   | .15  | .05  | .05  |
| DEVOPS_TOOL    | .15  | .15  | .20  | .10  | .15   | .15  | .05  | .05  |
| SECURITY_TOOL  | .15  | .10  | .15  | .10  | .15   | .20  | .10  | .05  |
| LANG_TOOL      | .20  | .15  | .20  | .10  | .15   | .05  | .10  | .05  |
| TEST_TOOL      | .15  | .10  | .25  | .15  | .15   | .05  | .10  | .05  |
| DOC_TOOL       | .10  | .10  | .10  | .25  | .15   | .05  | .15  | .10  |
| OTHER (default)| .20  | .15  | .15  | .10  | .15   | .10  | .10  | .05  |

Notable design choices:

- **ML_LIB** weights FUNCTIONALITY (0.25) and INNOVATION (0.15) highest across all profiles — ML repos are valued for what they can do and how novel their approaches are.
- **SECURITY_TOOL** gives SECURITY the highest dimension weight (0.20) of any profile — security tools must themselves be secure.
- **TEST_TOOL** gives TESTING the highest weight (0.25) — a test framework that doesn't test itself is suspect.
- **DOC_TOOL** weights DOCUMENTATION at 0.25 — documentation tools should dogfood their own practices.

### 10.2 Custom Profiles

Custom profiles can be loaded from YAML or TOML files at runtime via the `ProfileRegistry`. Custom profiles override built-in profiles for matching domains and can include:

- Custom `dimension_weights` (must sum to 1.0)
- Custom `gate_thresholds` (minimum pass scores per gate)
- Custom `derivation_map` (per-dimension sub-score overrides)
- Custom `star_baseline` (expected star count for the domain)

**Implementation reference**: `src/github_discovery/scoring/profiles.py` — `ProfileRegistry`

---

## 11. Complete Signal Flow

```
                        ┌──────────────────────────────────────────┐
                        │            Gate 1 (API only)              │
                        │                                           │
                        │  hygiene ────────────────────┐            │
                        │  maintenance ────────────────┤            │
                        │  release_discipline ─────────┤ 7 sub-    │
                        │  review_practice ────────────┤ scores    │
                        │  test_footprint ─────────────┤            │
                        │  ci_cd ──────────────────────┤            │
                        │  dependency_quality ─────────┘            │
                        └──────────┬───────────────────────────────┘
                                   │
                        ┌──────────▼───────────────────────────────┐
                        │         Gate 2 (clone + tools)            │
                        │                                           │
                        │  complexity ─────────────────┐            │
                        │  security_hygiene ───────────┤ 4 sub-    │
                        │  vulnerability ──────────────┤ scores    │
                        │  secret_hygiene ─────────────┘            │
                        └──────────┬───────────────────────────────┘
                                   │
                        ┌──────────▼───────────────────────────────┐
                        │      Derivation Map (engine.py)           │
                        │                                           │
                        │  CODE_QUALITY  ← complexity .35           │
                        │                    test_footprint .25     │
                        │                    review_practice .25    │
                        │                    ci_cd .15              │
                        │                                           │
                        │  TESTING      ← test_footprint .70       │
                        │                    ci_cd .30              │
                        │                                           │
                        │  DOCUMENTATION ← hygiene .70              │
                        │                    release_discipline .30 │
                        │                                           │
                        │  MAINTENANCE  ← maintenance .45           │
                        │                    release_discipline .35 │
                        │                    ci_cd .10              │
                        │                    hygiene .10            │
                        │                                           │
                        │  SECURITY    ← security_hygiene .35       │
                        │                   vulnerability .25       │
                        │                   secret_hygiene .25      │
                        │                   dependency_quality .15  │
                        │                                           │
                        │  ARCHITECTURE  → empty (Gate 3 only)      │
                        │  FUNCTIONALITY → empty (Gate 3 only)      │
                        │  INNOVATION    → empty (Gate 3 only)      │
                        └──────────┬───────────────────────────────┘
                                   │
                        ┌──────────▼───────────────────────────────┐
                        │       Domain Profile Weighting            │
                        │                                           │
                        │  quality_score = weighted_avg(dims)       │
                        │  × coverage_damping(0.5 + 0.5 × cov)     │
                        └──────────┬───────────────────────────────┘
                                   │
                        ┌──────────▼───────────────────────────────┐
                        │         ScoreResult (output)              │
                        │                                           │
                        │  quality_score: 0.0–1.0                   │
                        │  confidence:    0.0–1.0                   │
                        │  coverage:      0.0–1.0                   │
                        │  dimension_scores: {dim: value}           │
                        │  stars: metadata only (no scoring effect) │
                        └───────────────────────────────────────────┘
```

---

## 12. References

[1]: N. E. Fenton and M. Neil, "Software metrics: successes, failures and new directions," *Journal of Systems and Software*, vol. 47, no. 2–3, pp. 149–157, 1999. — Validates cyclomatic complexity as a defect predictor and discusses limitations of process metrics as quality proxies.

[2]: T. J. McCabe, "A Complexity Measure," *IEEE Transactions on Software Engineering*, vol. SE-2, no. 4, pp. 308–320, 1976. — Original cyclomatic complexity formulation. GitHub Discovery uses complexity as a structural quality signal in CODE_QUALITY (weight 0.35).

[3]: OpenSSF Scorecard, "Security Scorecards for Open Source," *Open Source Security Foundation*, 2024. Available: https://github.com/ossf/scorecard — Provides the security_hygiene sub-score methodology used in Gate 2. Scorecard evaluates branch protection, security policy, dependency updates, and other security practices.

[4]: CHAOSS Project, "Community Health Analytics in Open Source Software," *Linux Foundation*, 2024. Available: https://chaoss.community — Provides community health metrics including contributor bus factor, issue response time, and change request acceptance rates. Influences the MAINTENANCE dimension design.

[5]: GitHub, "Community Profile Checklist," *GitHub Docs*, 2024. Available: https://docs.github.com/en/communities — GitHub's own community health checks (README, LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, etc.) directly inform the `hygiene` sub-score in Gate 1.

[6]: G. Gousios, "The GHTorrent Dataset and Tool Suite," *Proceedings of MSR 2013*. — Validates commit cadence, issue closure ratio, and PR review metrics as project health indicators. Influences the `maintenance` and `review_practice` sub-scores.

[7]: OSV (Open Source Vulnerabilities), "OSV: A Distributed Vulnerability Database for Open Source," *Google Open Source Programs*, 2024. Available: https://osv.dev — Powers the `vulnerability` sub-score in Gate 2 via API-based CVE lookup.

[8]: zricethezav/gitleaks, "Gitleaks: Find Secrets with Gitleaks," 2024. Available: https://github.com/gricethezav/gitleaks — Powers the `secret_hygiene` sub-score in Gate 2 via shallow clone scanning.

---

## Appendix A: Sub-Score to Dimension Cross-Reference

| Sub-Score            | Gate | CODE_QUALITY | ARCH | TESTING | DOC  | MAINT | SEC  | FUNC | INNO |
|----------------------|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `complexity`         | 2    | .35 |     |     |     |     |     |     |     |
| `test_footprint`     | 1    | .25 |     | .70 |     |     |     |     |     |
| `review_practice`    | 1    | .25 |     |     |     |     |     |     |     |
| `ci_cd`              | 1    | .15 |     | .30 |     | .10 |     |     |     |
| `hygiene`            | 1    |     |     |     | .70 | .10 |     |     |     |
| `release_discipline` | 1    |     |     |     | .30 | .35 |     |     |     |
| `maintenance`        | 1    |     |     |     |     | .45 |     |     |     |
| `security_hygiene`   | 2    |     |     |     |     |     | .35 |     |     |
| `vulnerability`      | 2    |     |     |     |     |     | .25 |     |     |
| `secret_hygiene`     | 2    |     |     |     |     |     | .25 |     |     |
| `dependency_quality` | 1    |     |     |     |     |     | .15 |     |     |

Empty cells indicate no contribution. ARCHITECTURE, FUNCTIONALITY, and INNOVATION have no Gate 1+2 sub-score contributions (Gate 3 only).
