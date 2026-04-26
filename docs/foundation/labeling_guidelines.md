# Labeling Guidelines — Golden Dataset for Empirical Calibration

> **Document ID:** T4.1-infra
> **Phase:** Wave 4 — Audit Remediation (Fase 2)
> **Status:** Active
> **Audience:** Senior human raters, calibration reviewers

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-04-26 | GitHub Discovery Team | Initial guidelines for 200-repo golden dataset |

---

## Table of Contents

1. [Purpose](#1-purpose)
2. [Rater Qualifications](#2-rater-qualifications)
3. [Rating Scale](#3-rating-scale)
4. [Per-Dimension Rating Criteria](#4-per-dimension-rating-criteria)
5. [Domain-Specific Considerations](#5-domain-specific-considerations)
6. [Rating Process](#6-rating-process)
7. [Calibration Procedure](#7-calibration-procedure)
8. [Data Format](#8-data-format)
9. [Bias Mitigation](#9-bias-mitigation)
10. [Sample Dataset Structure](#10-sample-dataset-structure)
11. [Appendix A — Quick-Reference Scorecard](#appendix-a--quick-reference-scorecard)
12. [Appendix B — Common Pitfalls](#appendix-b--common-pitfalls)

---

## 1. Purpose

GitHub Discovery is an MCP-native agentic engine that finds high-quality GitHub repositories independent of popularity signals (stars, social buzz). To validate that the automated scoring pipeline produces meaningful rankings, we need a **golden dataset** of human-rated repositories against which automated scores can be calibrated and evaluated.

### How This Dataset Will Be Used

| Use Case | Description |
|----------|-------------|
| **Weight calibration** | Human ratings determine optimal weights for the 8 scoring dimensions across different domain types. |
| **NDCG evaluation** | Rankings produced by the automated pipeline are compared against a ground-truth ordering derived from aggregated human ratings using Normalized Discounted Cumulative Gain (NDCG). |
| **Gate threshold tuning** | Gate 1 and Gate 2 pass/fail thresholds are calibrated so that repos humans rate as Very Poor (1) or Poor (2) are reliably filtered. |
| **Inter-rater reliability** | Cohen's κ ≥ 0.6 ensures the ground truth is sufficiently consistent to serve as a calibration target. |
| **Anti-star bias validation** | Confirms that the pipeline surfaces high-quality, low-star ("hidden gem") repositories that human experts also rate highly. |

### Scope

- **200 repositories** across **12 domain types**.
- Each repo rated by **3 independent senior raters** on **8 quality dimensions**.
- Ratings use a **1–5 integer scale** per dimension.

---

## 2. Rater Qualifications

All raters must meet the following minimum requirements before participating:

| Requirement | Minimum Threshold |
|-------------|-------------------|
| Professional software development experience | 3+ years |
| GitHub ecosystem familiarity | Active GitHub account; experience with issues, PRs, CI, releases |
| Software quality concepts | Understanding of testing, code review, documentation, security practices |
| Programming language breadth | Proficient in at least 2 of: Python, JavaScript/TypeScript, Go, Rust, Java, C/C++ |
| Bias awareness | Completion of this guidelines document and the calibration pilot |

### Preferred (Not Required)

- Experience conducting code reviews in a professional setting.
- Familiarity with static analysis tools (linters, type checkers, SAST).
- Prior participation in software quality assessments or academic reproducibility studies.

---

## 3. Rating Scale

Every dimension is rated on a **1–5 integer scale**. Half-point scores (e.g., 3.5) are **not permitted** — force a decision.

| Score | Label | Meaning |
|-------|-------|---------|
| **1** | Very Poor | Absent or critically deficient. No evidence of the quality attribute. |
| **2** | Poor | Minimal or substandard. Present but severely lacking in scope, rigor, or correctness. |
| **3** | Adequate | Meets basic expectations. Functional but unremarkable. |
| **4** | Good | Above average. Well-executed with clear effort and competence. |
| **5** | Excellent | Exemplary, best-in-class. Sets a standard others should follow. |

### Decision Heuristics

- **When in doubt between two adjacent scores**, choose the lower one. It is better to underestimate slightly than to inflate ratings.
- **A score of 3 is explicitly "good enough"** — it is not a negative rating. Most well-maintained open-source projects will cluster around 3–4.
- **Reserve 5 for genuinely exceptional cases.** If you cannot articulate why a repo is best-in-class, do not give it a 5.

---

## 4. Per-Dimension Rating Criteria

### 4.1 CODE_QUALITY — Code Style, Complexity, Static Analysis Signals

Evaluate readability, consistency, complexity management, and adherence to language-idiomatic patterns.

| Score | Criteria |
|-------|----------|
| **1** | No discernible code style; extremely high complexity (cyclomatic > 30 per function); critical linting errors unaddressed; copy-paste duplication throughout. |
| **2** | Inconsistent style; high complexity in multiple functions (cyclomatic 15–30); linting warnings pervasive; significant code duplication; non-idiomatic patterns. |
| **3** | Consistent style enforced (linter present, some deviations); moderate complexity (cyclomatic 10–15 typical); some duplication; largely idiomatic code. |
| **4** | Strict style enforcement (CI-gated linting); low complexity (cyclomatic < 10); minimal duplication; idiomatic patterns throughout; meaningful variable/function names. |
| **5** | All of 4 plus: automated complexity tracking; refactoring evident from git history; consistent design patterns; code reads as self-documenting; static analysis integrated into CI with zero warnings on main branch. |

**Observable signals to check:**

- Presence of linter config (`.eslintrc`, `ruff.toml`, `.flake8`, `golangci.yml`).
- Cyclomatic complexity of sampled functions (use `lizard`, `radon`, or equivalent).
- Naming conventions: consistent, descriptive, language-appropriate.
- Import organization and module boundaries.

---

### 4.2 ARCHITECTURE — Directory Structure, Coupling, Abstraction Layers

Evaluate modularity, separation of concerns, dependency management, and structural coherence.

| Score | Criteria |
|-------|----------|
| **1** | Flat file dump with no organization; circular dependencies; god objects/functions (500+ lines); no separation of concerns. |
| **2** | Minimal directory structure; tight coupling between modules; some separation attempted but inconsistent; dependency soup (imports from everywhere). |
| **3** | Reasonable directory structure following domain conventions; moderate coupling; clear public/internal boundaries; dependency graph is navigable. |
| **4** | Well-structured with clear layers (e.g., core/adapters/infrastructure); low coupling via interfaces/protocols; dependency injection or composition root; dependency graph is clean and acyclic. |
| **5** | All of 4 plus: architecture decision records (ADRs); explicit dependency graph documentation; plugin/extension points where appropriate; hexagonal or clean architecture evident; migration strategy documented. |

**Observable signals to check:**

- Directory tree: does it follow domain conventions for the language/framework?
- Count of cross-module imports (coupling indicator).
- Presence of `__init__.py` / `index.ts` / `mod.rs` boundary markers.
- Dependency management: lockfiles, version pinning, minimal transitive dependencies.

---

### 4.3 TESTING — Test Presence, Coverage, Test Quality

Evaluate whether the project has tests, their coverage, quality, and integration with CI.

| Score | Criteria |
|-------|----------|
| **1** | No tests at all. No test framework configured. |
| **2** | < 10% file coverage; no coherent test framework (or framework present but barely used); tests are smoke tests that assert trivially; no CI integration. |
| **3** | 10–40% coverage; established test framework (pytest, Jest, Go testing, etc.); unit tests present for core logic; some tests may be brittle or overly coupled to implementation; CI runs tests but may not gate merges. |
| **4** | 40–70% coverage; unit + integration tests; CI-gated merges require passing tests; test utilities/fixtures present; tests are mostly independent and repeatable; mocking used appropriately. |
| **5** | > 70% coverage; unit + integration + end-to-end tests; mutation testing or property-based testing present; CI-gated with coverage enforcement; test code follows same quality standards as production code; performance/load tests where applicable. |

**Observable signals to check:**

- Test directory presence and structure (`tests/`, `test/`, `*_test.go`, `__tests__/`).
- Coverage reports or CI badges.
- Test-to-source file ratio.
- Quality of assertions: specific vs. overly broad.
- Test independence: can tests run in any order?

---

### 4.4 DOCUMENTATION — README, API Docs, Guides, Onboarding

Evaluate the breadth, depth, and accuracy of written documentation.

| Score | Criteria |
|-------|----------|
| **1** | No README or README is a one-liner. No API documentation. No installation instructions. |
| **2** | Minimal README (project name, brief description); installation instructions present but incomplete; no API docs; no usage examples; no contribution guide. |
| **3** | Structured README with installation, basic usage, and configuration; API documentation generated or partially written; some code examples; changelog present. |
| **4** | Comprehensive README with quickstart, advanced usage, FAQ; full API reference (auto-generated or hand-written); architecture overview; contribution guide; migration guides between versions. |
| **5** | All of 4 plus: interactive documentation (playground, storybook); video or walkthrough tutorials; decision records; documentation tested for accuracy (e.g., doc tests passing); multilingual documentation; accessibility considerations documented. |

**Observable signals to check:**

- README structure: does it answer "what, why, how" in the first screen?
- Docstrings / comments in public API surfaces.
- Presence of `docs/` directory or hosted documentation site.
- Code examples: do they work? Are they current?
- Changelog: is it machine-parseable (e.g., Keep a Changelog format)?

---

### 4.5 MAINTENANCE — Commit Cadence, Release Discipline, Issue Management

Evaluate the project's ongoing health, responsiveness, and release practices.

| Score | Criteria |
|-------|----------|
| **1** | Abandoned or archived. No commits in 12+ months. Open issues with no response. No releases ever. |
| **2** | Sporadic commits (months between bursts); releases are rare and unversioned; issues receive responses but slowly (weeks); no contributing guidelines; breaking changes undocumented. |
| **3** | Regular commits (at least monthly); semantic versioning used; issues triaged within a week; PRs reviewed; CHANGELOG maintained; CI running. |
| **4** | Frequent commits (weekly+); automated release pipeline; issue templates and response SLA evident; PR review turnaround < 48 hours; deprecation notices provided; backward compatibility maintained. |
| **5** | All of 4 plus: release notes include migration guides; community contributions actively encouraged and mentored; governance model documented; long-term support branches maintained; automated dependency updates (Dependabot/Renovate) with timely reviews. |

**Observable signals to check:**

- GitHub Insights → Pulse / Contributors / Commits tabs.
- Release history: frequency, versioning scheme, release notes quality.
- Issue response time (sample 5 open + 5 closed issues).
- PR merge time and review quality.
- Branch protection and CI status.

---

### 4.6 SECURITY — Vulnerability Scanning, Secret Hygiene, Dependency Pinning

Evaluate the project's security posture and practices.

| Score | Criteria |
|-------|----------|
| **1** | No security practices whatsoever. Secrets committed to repository. No dependency management. Known critical vulnerabilities unpatched. No `.gitignore` for sensitive files. |
| **2** | Basic `.gitignore` present; dependencies listed but not pinned; no vulnerability scanning; some sensitive config in repo; no security policy. |
| **3** | Dependencies pinned (lockfile present); basic vulnerability scanning configured (Dependabot alerts, Snyk, etc.); no secrets detected in recent history; SECURITY.md present but minimal. |
| **4** | All of 3 plus: automated vulnerability scanning in CI; dependency pinning with hash verification; secret scanning pre-commit hooks; security policy with responsible disclosure process; dependencies regularly updated. |
| **5** | All of 4 plus: signed commits; SLSA/SBOM provenance; fuzz testing infrastructure; security audit reports published; CVE response process documented and tested; minimal dependency surface (low attack vector). |

**Observable signals to check:**

- `.gitignore` comprehensiveness (IDE files, env files, secrets).
- Lockfile presence: `package-lock.json`, `poetry.lock`, `go.sum`, `Cargo.lock`.
- GitHub Security tab: Dependabot alerts, advisory credits.
- History check (use `git log --all --full-history -- '*.env' '*.key' '*.pem'`).
- Pre-commit hooks or CI steps for secret scanning (e.g., `gitleaks`, `trufflehog`).

---

### 4.7 FUNCTIONALITY — Fit to Use-Case, Feature Coverage, API Completeness

Evaluate whether the project effectively solves the problem it claims to solve and how complete its feature set is relative to its stated scope.

| Score | Criteria |
|-------|----------|
| **1** | Core functionality broken or absent. Claims to do X but cannot demonstrate X. Unusable in its current state. |
| **2** | Core functionality present but buggy or incomplete. Major features listed in README are missing or broken. API has significant gaps. |
| **3** | Core functionality works as advertised. Features listed in documentation are implemented and functional. API covers common use cases. Some edge cases may be unhandled. |
| **4** | Comprehensive feature set covering stated scope and common edge cases. API is well-designed and intuitive. Backward compatibility maintained. Examples demonstrate real-world usage. |
| **5** | All of 4 plus: exceeds stated scope with thoughtful extensions; API designed for extensibility; performance benchmarks published; feature parity or advantage vs. competing tools; graceful degradation documented. |

**Observable signals to check:**

- Does the demo/quickstart actually work end-to-end?
- Are features listed in README present and functional?
- API surface: are there obvious missing operations?
- Error handling: does the project fail gracefully?
- Sample projects or real-world usage evidence.

---

### 4.8 INNOVATION — Novel Approaches, Unique Positioning

Evaluate the degree to which the project introduces novel ideas, approaches, or solutions. This is the most subjective dimension — anchor carefully.

| Score | Criteria |
|-------|----------|
| **1** | Direct clone or fork of an existing project with no differentiation. No original contribution. |
| **2** | Minor variation of existing approaches. Small incremental improvement. Largely follows established patterns without adding new ideas. |
| **3** | Competent implementation of known approaches. Some unique combination of existing ideas. Solid but not groundbreaking. |
| **4** | Novel approach to an existing problem. Unique combination of techniques that provides clear advantage. Published or blogged rationale for design decisions. |
| **5** | Breakthrough approach or entirely new category of tool. Published research or significant community recognition for innovation. Influences other projects in the space. |

**Observable signals to check:**

- README and docs: do they articulate what is new or different?
- Comparison tables with competing tools.
- Citation of research papers or novel algorithms.
- Git history: evidence of iterative innovation vs. straightforward implementation.
- Community reception: are other projects adopting the same patterns?

> **Caution:** A well-executed but conventional project should score 2–3. Do not confuse quality with novelty. A perfectly coded CRUD app scores 5 on CODE_QUALITY but likely 1–2 on INNOVATION.

---

## 5. Domain-Specific Considerations

The relative importance and interpretation of dimensions varies by domain type. Use the following guidance to adjust your evaluation focus.

### 5.1 Dimension Weight Guidance by Domain

| Domain | Primary Dimensions | Secondary Dimensions | Notes |
|--------|--------------------|----------------------|-------|
| `cli` | FUNCTIONALITY, DOCUMENTATION, CODE_QUALITY | MAINTENANCE, TESTING | Usability is critical: help text, error messages, exit codes, shell completion. |
| `web_framework` | ARCHITECTURE, TESTING, SECURITY | DOCUMENTATION, MAINTENANCE | Performance benchmarks, middleware design, plugin ecosystem. |
| `data_tool` | FUNCTIONALITY, CODE_QUALITY, TESTING | ARCHITECTURE, DOCUMENTATION | Data validation, schema handling, error messages for malformed input. |
| `ml_lib` | FUNCTIONALITY, ARCHITECTURE, TESTING | DOCUMENTATION, SECURITY | Model serving quality, training pipeline reproducibility, experiment tracking. |
| `devops_tool` | SECURITY, MAINTENANCE, FUNCTIONALITY | ARCHITECTURE, DOCUMENTATION | Infrastructure-as-code quality, idempotency, rollback safety. |
| `library` | ARCHITECTURE, TESTING, DOCUMENTATION | CODE_QUALITY, MAINTENANCE | API design, backward compatibility, semver adherence, public surface area. |
| `backend` | SECURITY, ARCHITECTURE, TESTING | MAINTENANCE, DOCUMENTATION | Authentication, authorization, data validation, rate limiting. |
| `security_tool` | SECURITY, CODE_QUALITY, TESTING | ARCHITECTURE, DOCUMENTATION | Crypto implementation correctness, false positive/negative rates, audit logging. |
| `lang_tool` | ARCHITECTURE, CODE_QUALITY, TESTING | FUNCTIONALITY, DOCUMENTATION | Parser correctness, language spec compliance, error recovery, incremental processing. |
| `test_tool` | TESTING, ARCHITECTURE, FUNCTIONALITY | CODE_QUALITY, DOCUMENTATION | The tool must practice what it preaches — test the test tool thoroughly. |
| `doc_tool` | DOCUMENTATION, FUNCTIONALITY, ARCHITECTURE | CODE_QUALITY, MAINTENANCE | Output quality, format support, template system, accessibility. |
| `other` | Balanced across all dimensions | — | Use general software engineering judgment. |

### 5.2 Domain-Specific FUNCTIONALITY Interpretations

| Domain | FUNCTIONALITY Focus Areas |
|--------|---------------------------|
| `cli` | Command parsing, subcommand structure, flag handling, exit codes, piping support, shell completion, progress indicators, colored output |
| `web_framework` | Routing, middleware, request/response lifecycle, template engine, database integration, authentication hooks |
| `data_tool` | Input format support, data validation, transformation pipeline, streaming/large dataset handling, export formats |
| `ml_lib` | Model training API, inference pipeline, data loading, experiment tracking, model serialization, GPU/TPU support |
| `devops_tool` | Deployment automation, rollback capability, health checks, configuration management, multi-environment support |
| `library` | Public API surface, type annotations, convenience functions, extension points, error types, async support |
| `backend` | API endpoints, authentication flows, database operations, caching, background jobs, rate limiting |
| `security_tool` | Detection accuracy, scan coverage, reporting formats, rule customizability, false positive management |
| `lang_tool` | Parser accuracy, language spec compliance, syntax highlighting, code formatting, linting rules, auto-fix capability |
| `test_tool` | Assertion library, test runner features, mocking, snapshot testing, parallel execution, reporting formats |
| `doc_tool` | Output formats (HTML, PDF, man pages), search, cross-referencing, API doc generation, template customization |

### 5.3 Domain-Specific SECURITY Interpretations

| Domain | SECURITY Focus Areas |
|--------|---------------------|
| `cli` | Input sanitization, credential handling, file permissions, supply chain (dependency trust) |
| `web_framework` | XSS prevention, CSRF protection, SQL injection, secure defaults, helmet-equivalent middleware |
| `ml_lib` | Model poisoning resistance, data privacy, adversarial robustness, secure model serving |
| `security_tool` | Cryptographic correctness, timing attack resistance, secure default configurations, audit logging |
| `devops_tool` | Secret management, least-privilege execution, container security, network policies |

---

## 6. Rating Process

Each repository must be evaluated through a systematic process. **Minimum time per repo: 15 minutes.** Rushed ratings will be detected during calibration and rejected.

### 6.1 Step-by-Step Evaluation

```
Step 1: READ THE README (3 min)
   → What does this project claim to do?
   → Who is the target audience?
   → What are the stated features?
   → Does the quickstart work?

Step 2: EXAMINE DIRECTORY STRUCTURE (2 min)
   → Does it follow conventions for the language/domain?
   → Are there clear module boundaries?
   → Is there a logical separation of concerns?

Step 3: SAMPLE CODE FILES (5 min)
   → Read 3–5 representative source files (not auto-generated)
   → Evaluate naming, complexity, idiomatic usage
   → Check for code duplication, antipatterns

Step 4: CHECK TESTING INFRASTRUCTURE (2 min)
   → Test directory structure and framework
   → Run `--help` or equivalent on test runner (if possible)
   → Estimate coverage from file presence (test-to-source ratio)

Step 5: REVIEW GITHUB INSIGHTS (3 min)
   → Contributors tab: bus factor, contributor diversity
   → Issues tab: response time, label usage, stale issue handling
   → PRs tab: review practices, merge strategy, CI enforcement
   → Releases: frequency, versioning, release notes

Step 6: SECURITY QUICK CHECK (2 min)
   → GitHub Security tab: alerts, advisories
   → Lockfile presence and freshness
   → `.gitignore` for sensitive patterns
```

### 6.2 Recording Observations

For **each dimension**, record:

1. **Score** (1–5 integer)
2. **Evidence** — at least one specific observation supporting the score
3. **Caveat** — any uncertainty or condition that affected the rating

Example:

```
TESTING: 3
Evidence: pytest configured, 23 test files for 41 source files (~56% file coverage).
          Unit tests present for core module. No integration tests found.
          CI badge present but no coverage enforcement.
Caveat: Could not run tests locally (dependency conflict).
        Coverage estimate is by file count, not line coverage.
```

> **Critical:** Ratings without specific observations will be rejected during quality review. The observations are as valuable as the scores themselves — they enable disagreement resolution and guideline refinement.

### 6.3 Handling Edge Cases

| Situation | Action |
|-----------|--------|
| Repo is a monorepo with multiple projects | Rate the primary project as identified by the README root. Note this in observations. |
| Repo is primarily generated code (e.g., protobuf outputs) | Focus on the hand-written source. Note the generated-code proportion. |
| Repo is a fork with modifications | Rate the fork's additions/modifications, not the upstream code. Identify the upstream in notes. |
| Repo has no source code (documentation-only, config-only) | Rate FUNCTIONALITY as 1. Other dimensions may still apply. |
| Repo requires specific hardware/environment to test | Do not penalize for inability to run. Note what you could not verify. |
| Language unfamiliar to rater | Focus on structural and process signals over syntax. Flag in observations. Request reassignment if severely limited. |

---

## 7. Calibration Procedure

### 7.1 Pilot Phase (10 Repositories)

Before rating the full 200-repo dataset, all 3 raters independently rate the same **10-repo pilot set**.

**Pilot set composition:**

| Category | Count | Purpose |
|----------|-------|---------|
| Known high quality (e.g., popular, well-maintained) | 3 | Establish upper-bound anchors |
| Known low quality (e.g., abandoned, minimal) | 3 | Establish lower-bound anchors |
| Ambiguous / mixed quality | 4 | Test discrimination in the middle range |

The pilot set covers at least 6 different domain types.

### 7.2 Agreement Measurement

After all 3 raters complete the pilot set, compute **pairwise Cohen's κ** for each dimension:

```
κ = (P_o - P_e) / (1 - P_e)

where:
  P_o = observed agreement proportion
  P_e = expected agreement by chance
```

**Targets:**

| Metric | Threshold | Action if Not Met |
|--------|-----------|-------------------|
| Overall κ (averaged across dimensions) | ≥ 0.60 | Refine guidelines, discuss, relabel |
| Per-dimension κ | ≥ 0.50 for 6+ of 8 dimensions | Focus discussion on low-κ dimensions |
| No single dimension κ | < 0.30 | Major guideline revision for that dimension |

### 7.3 Disagreement Resolution

For each rating pair where raters disagree by **≥ 2 points** on any dimension:

1. Both raters present their evidence.
2. Discuss whether the disagreement stems from:
   - **Guideline ambiguity** → Update this document.
   - **Different evaluation depth** → One rater missed observable signals; extend evaluation time.
   - **Genuine subjective difference** → Accept both ratings; note the tension.
3. Re-rate the specific dimension independently after discussion.
4. Do NOT negotiate to a compromise score. Each rater maintains independent judgment.

### 7.4 Proceeding to Full Dataset

The team proceeds to the full 200-repo dataset when:

- [ ] Overall κ ≥ 0.60 on the pilot set.
- [ ] At least 6 of 8 dimensions have κ ≥ 0.50.
- [ ] No dimension has κ < 0.30.
- [ ] All ≥ 2-point disagreements have been discussed and documented.
- [ ] All raters confirm they understand the guidelines as refined.

If κ < 0.60, repeat the pilot phase (same or revised 10 repos) up to **3 iterations**. If agreement is still insufficient after 3 iterations, escalate to the project lead for rater replacement or guideline overhaul.

### 7.5 Ongoing Quality Monitoring

During the full rating phase:

- **Spot-check** 5% of ratings (random sample) by having a second rater independently re-rate.
- **Track κ over time** — if agreement degrades in later batches, pause for recalibration.
- **Batch boundary reviews** — after every 40 repos (5 batches of 8), compute interim κ and verify it remains ≥ 0.55.

---

## 8. Data Format

### 8.1 Individual Rating Record

Each rater produces one JSON file per repository. Files are stored in the dataset repository under:

```
golden-dataset/
├── ratings/
│   ├── r1/
│   │   ├── owner--repo-001.json
│   │   ├── owner--repo-002.json
│   │   └── ...
│   ├── r2/
│   └── r3/
├── pilot/
│   └── (same structure, pilot repos only)
└── metadata.json
```

### 8.2 JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": [
    "repo_url",
    "domain_type",
    "rater_id",
    "ratings",
    "notes",
    "rated_at"
  ],
  "properties": {
    "repo_url": {
      "type": "string",
      "format": "uri",
      "description": "HTTPS URL of the GitHub repository",
      "examples": ["https://github.com/owner/repo"]
    },
    "domain_type": {
      "type": "string",
      "enum": [
        "cli",
        "web_framework",
        "data_tool",
        "ml_lib",
        "devops_tool",
        "library",
        "backend",
        "security_tool",
        "lang_tool",
        "test_tool",
        "doc_tool",
        "other"
      ],
      "description": "Pre-assigned domain type for stratified analysis"
    },
    "rater_id": {
      "type": "string",
      "enum": ["r1", "r2", "r3"],
      "description": "Anonymous rater identifier"
    },
    "ratings": {
      "type": "object",
      "required": [
        "code_quality",
        "architecture",
        "testing",
        "documentation",
        "maintenance",
        "security",
        "functionality",
        "innovation"
      ],
      "properties": {
        "code_quality": {
          "type": "integer",
          "minimum": 1,
          "maximum": 5
        },
        "architecture": {
          "type": "integer",
          "minimum": 1,
          "maximum": 5
        },
        "testing": {
          "type": "integer",
          "minimum": 1,
          "maximum": 5
        },
        "documentation": {
          "type": "integer",
          "minimum": 1,
          "maximum": 5
        },
        "maintenance": {
          "type": "integer",
          "minimum": 1,
          "maximum": 5
        },
        "security": {
          "type": "integer",
          "minimum": 1,
          "maximum": 5
        },
        "functionality": {
          "type": "integer",
          "minimum": 1,
          "maximum": 5
        },
        "innovation": {
          "type": "integer",
          "minimum": 1,
          "maximum": 5
        }
      },
      "additionalProperties": false
    },
    "notes": {
      "type": "string",
      "minLength": 50,
      "description": "Specific observations supporting each rating. Must include at least one observation per dimension."
    },
    "rated_at": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 timestamp of when the rating was completed"
    },
    "evaluation_duration_minutes": {
      "type": "integer",
      "minimum": 15,
      "description": "Self-reported time spent evaluating this repository"
    },
    "language_difficulty": {
      "type": "boolean",
      "description": "True if the rater has limited familiarity with the repo's primary language"
    }
  },
  "additionalProperties": false
}
```

### 8.3 Example Rating

```json
{
  "repo_url": "https://github.com/psf/requests",
  "domain_type": "library",
  "rater_id": "r1",
  "ratings": {
    "code_quality": 5,
    "architecture": 4,
    "testing": 4,
    "documentation": 5,
    "maintenance": 5,
    "security": 4,
    "functionality": 5,
    "innovation": 2
  },
  "notes": "CODE_QUALITY: Extremely readable codebase. Consistent style throughout. Pylint/flake8 integrated. Low complexity functions. ARCHITECTURE: Clean separation between sessions, adapters, and models. Well-defined public API. Some coupling between auth and session modules. TESTING: ~85% coverage estimate. Unit + integration tests. CI-gated. Missing property-based tests. DOCUMENTATION: Exemplary README. Full API reference on readthedocs. Multiple guides. Changelog maintained. MAINTENANCE: Active development (commits this week). Timely issue response. Regular releases. SECURITY: HTTPS default, cert verification enabled. Dependabot active. No secret scanning pre-commit hooks visible. FUNCTIONALITY: Complete HTTP client API. Covers all common use cases. Graceful handling of edge cases. INNOVATION: Well-executed but conventional HTTP client. Established patterns (not novel). The API design was influential at launch but now standard.",
  "rated_at": "2026-04-26T14:30:00Z",
  "evaluation_duration_minutes": 22,
  "language_difficulty": false
}
```

### 8.4 Aggregated Dataset

After all ratings are collected, an aggregation script produces the final dataset:

```json
{
  "repo_url": "https://github.com/psf/requests",
  "domain_type": "library",
  "star_stratum": "high",
  "aggregated_ratings": {
    "code_quality": { "mean": 4.67, "std": 0.47, "scores": [5, 4, 5] },
    "architecture": { "mean": 4.00, "std": 0.82, "scores": [4, 3, 5] },
    "testing": { "mean": 4.00, "std": 0.00, "scores": [4, 4, 4] },
    "documentation": { "mean": 4.67, "std": 0.47, "scores": [5, 4, 5] },
    "maintenance": { "mean": 4.67, "std": 0.47, "scores": [5, 4, 5] },
    "security": { "mean": 3.67, "std": 0.47, "scores": [4, 3, 4] },
    "functionality": { "mean": 4.67, "std": 0.47, "scores": [5, 4, 5] },
    "innovation": { "mean": 2.33, "std": 0.47, "scores": [2, 2, 3] }
  },
  "overall_quality": { "mean": 4.08 },
  "is_hidden_gem": false,
  "kappa_per_dimension": {
    "code_quality": 0.72,
    "architecture": 0.58,
    "testing": 1.00,
    "documentation": 0.72,
    "maintenance": 0.72,
    "security": 0.65,
    "functionality": 0.72,
    "innovation": 0.58
  }
}
```

---

## 9. Bias Mitigation

Human ratings are susceptible to systematic biases. The following protocols are **mandatory**.

### 9.1 Star Count Blindness

- **Do NOT look at the star count** before or during rating.
- Use the repo URL provided in the assignment — do not browse GitHub search results to find it.
- If you recognize the repo and know its approximate popularity, note this in `notes` and flag for potential bias review.
- The assignment system strips star counts from repo URLs.

### 9.2 Randomized Presentation Order

- Repos are assigned in **randomized order**, not alphabetical, not by star count, not by domain cluster.
- Do not re-order your assignment list.
- If you suspect the ordering is biased (e.g., all high-quality repos first), report to the coordinator.

### 9.3 Halo Effect Reduction

- **Rate one dimension at a time across repos** rather than all dimensions for one repo.
- Batch protocol: Rate CODE_QUALITY for 8 repos → then ARCHITECTURE for those same 8 repos → etc.
- This prevents a strong impression on one dimension from anchoring all other dimensions.
- Exception: During the initial clone/exploration phase, you may gather observations for all dimensions. But the final score assignment must follow the one-dimension-at-a-time protocol.

### 9.4 Batch Fatigue Management

- Rate in batches of **no more than 20 repos** per session.
- Take a **minimum 30-minute break** between batches.
- Do not rate for more than **4 hours total in a single day**.
- Self-report fatigue level after each batch. If fatigue is high, extend the break.

### 9.5 Recency and Familiarity Bias

- If you have **previously used or contributed to** a repo, disclose this in the `notes` field.
- If you are the **author or maintainer** of a repo in the dataset, recuse yourself from rating it.
- Alternate between familiar and unfamiliar languages/frameworks to prevent fatigue-induced leniency on unfamiliar stacks.

### 9.6 Anchoring Prevention

- The pilot set deliberately includes both clearly excellent and clearly terrible repos to establish the full range.
- After the pilot, periodically re-rate one pilot repo to verify your calibration hasn't drifted.
- If your re-rating of a pilot repo shifts by ≥ 2 points from your original, pause for recalibration.

---

## 10. Sample Dataset Structure

### 10.1 Target Composition

| Parameter | Target | Rationale |
|-----------|--------|-----------|
| Total repos | 200 | Sufficient for statistical significance per stratum |
| Domain types | 12 | Coverage of the project's domain taxonomy |
| Repos per domain | ~17 (12 × 17 = 204) | Minimum 15 per domain for per-domain analysis |
| Raters per repo | 3 | Enables κ calculation with majority resolution |
| Star strata | 3 levels, ~33% each | Ensures quality is evaluated independently of popularity |

### 10.2 Star Count Stratification

| Stratum | Star Range | Target Count | Target % |
|---------|------------|--------------|----------|
| Low | 0–100 stars | ~66 repos | 33% |
| Medium | 100–1,000 stars | ~66 repos | 33% |
| High | 1,000+ stars | ~66 repos | 33% |

### 10.3 Hidden Gem Target

At least **30% of the total dataset** (≥ 60 repos) should be **hidden gems**: repositories that receive a high aggregated quality score (≥ 3.5 mean across dimensions) but fall in the low-star stratum (0–100 stars).

This proportion ensures the calibration dataset adequately represents the anti-star-bias goal of the GitHub Discovery project.

### 10.4 Domain Allocation

| Domain Type | Target Repos | Low Stars | Medium Stars | High Stars |
|-------------|-------------|-----------|--------------|------------|
| `cli` | 17 | 6 | 6 | 5 |
| `web_framework` | 17 | 6 | 6 | 5 |
| `data_tool` | 17 | 5 | 6 | 6 |
| `ml_lib` | 17 | 6 | 5 | 6 |
| `devops_tool` | 17 | 5 | 6 | 6 |
| `library` | 17 | 6 | 5 | 6 |
| `backend` | 17 | 5 | 6 | 6 |
| `security_tool` | 17 | 6 | 6 | 5 |
| `lang_tool` | 17 | 6 | 5 | 6 |
| `test_tool` | 17 | 5 | 6 | 6 |
| `doc_tool` | 16 | 5 | 6 | 5 |
| `other` | 16 | 5 | 5 | 6 |
| **Total** | **204** | **66** | **68** | **70** |

> **Note:** 204 repos slightly exceeds the 200 target to ensure per-domain minimums. The extra 4 repos may be trimmed during final analysis if needed.

### 10.5 Selection Criteria for Candidate Repos

Candidate repos for the dataset are selected by the project coordinator (not by raters) using the following criteria:

1. **Domain relevance** — The repo's primary purpose matches the assigned domain type.
2. **Language diversity** — At least 5 different primary languages represented across the dataset.
3. **Age diversity** — Mix of established (3+ years) and newer (< 1 year) projects.
4. **Star stratum compliance** — Confirmed star count falls within the assigned stratum.
5. **No duplicate purpose** — Avoid including two repos that solve the exact same problem unless comparing approaches.
6. **Accessibility** — Repo is publicly accessible, not archived, and has sufficient content to rate.

---

## Appendix A — Quick-Reference Scorecard

Print this section for use during rating sessions.

```
┌────────────────────────────────────────────────────────────────────┐
│                    RATING QUICK-REFERENCE CARD                     │
├────────────────────────────────────────────────────────────────────┤
│  1 = Very Poor    │ Absent or critically deficient                 │
│  2 = Poor         │ Minimal / substandard                          │
│  3 = Adequate     │ Meets basic expectations                       │
│  4 = Good         │ Above average, well-executed                   │
│  5 = Excellent    │ Exemplary, best-in-class                       │
├────────────────────────────────────────────────────────────────────┤
│ DIMENSION          │ KEY SIGNALS                                   │
├────────────────────────────────────────────────────────────────────┤
│ CODE_QUALITY       │ Linter config, complexity, naming, idioms     │
│ ARCHITECTURE       │ Directory structure, coupling, layers, DI     │
│ TESTING            │ Coverage, framework, CI-gating, test quality  │
│ DOCUMENTATION      │ README, API docs, examples, changelog        │
│ MAINTENANCE        │ Commit cadence, releases, issue response      │
│ SECURITY           │ Scanning, lockfile, secrets, .gitignore       │
│ FUNCTIONALITY      │ Features work, API complete, edge cases       │
│ INNOVATION         │ Novel approaches, unique positioning          │
├────────────────────────────────────────────────────────────────────┤
│ REMINDERS                                                         │
│ • Minimum 15 minutes per repo                                     │
│ • Record evidence for every dimension                             │
│ • Do NOT look at star count                                       │
│ • When in doubt, choose the lower adjacent score                  │
│ • Reserve 5 for genuinely exceptional cases                       │
│ • Take breaks every 20 repos                                      │
└────────────────────────────────────────────────────────────────────┘
```

---

## Appendix B — Common Pitfalls

### Rating Errors to Avoid

| Pitfall | Description | Prevention |
|---------|-------------|------------|
| **Leniency bias** | Tendency to avoid low scores, clustering around 3–4. | The pilot set includes deliberately poor repos to anchor the lower end. |
| **Central tendency** | Reluctance to use 1 or 5, clustering around 3. | Force yourself to use the full range. If nothing deserves a 1 or 5, recalibrate. |
| **Halo effect** | A high score on one dimension inflates scores on others. | Rate one dimension at a time across repos. |
| **Recency bias** | Recent repos influence the rating of the current one. | Randomized order and batch breaks mitigate this. |
| **Star-count bias** | Unconsciously rating popular repos higher. | Star count is hidden; use only code-quality signals. |
| **Documentation over-weighting** | Good docs create a positive impression that inflates other scores. | Explicitly evaluate each dimension independently. |
| **Language familiarity bias** | Rating unfamiliar languages lower due to inability to judge idiomatic code. | Focus on structural signals. Flag unfamiliar languages. |
| **Fatigue degradation** | Ratings become less careful in later batches. | Mandatory breaks. Self-report fatigue. |
| **Anchoring to pilot** | Over-relying on pilot repos as reference points. | Pilot is a calibration tool, not a scoring template. Each repo stands on its own. |
| **Confusing effort with quality** | Rewarding visible effort (many files, long README) over actual quality. | Evaluate outcomes, not effort. A short, correct solution beats a long, buggy one. |

---

*End of labeling guidelines. For questions or clarifications, contact the GitHub Discovery project lead.*
