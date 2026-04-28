---
Title: Screening Gates Detail
Topic: domain
Sources: Foundation Blueprint §16.2-16.5; Roadmap Phase 3
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md)
Updated: 2026-04-27
Confidence: high
---

# Screening Gates Detail

Gate 1 and Gate 2 are the pre-LLM screening layers. They reduce the candidate pool cheaply, ensuring only the most promising repos reach expensive Gate 3 deep assessment.

## Key Points

- **Gate 1** (Metadata Screening): Zero LLM cost. Uses repository metadata from GitHub API.
- **Gate 2** (Static/Security Screening): Zero to low cost. Uses automated tools on shallow clone.
- **Hard rule**: No candidate reaches Gate 3 without passing Gate 1 + Gate 2
- Both gates are configurable per-domain via Policy Engine

## Gate 1 — Metadata Screening

### Sub-scores (each 0.0-1.0)

| Sub-score | Module | What It Checks |
|-----------|--------|----------------|
| `HygieneScore` | `screening/hygiene.py` | Presence and quality of LICENSE (SPDX valid), CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md, CHANGELOG.md, README.md |
| `MaintenanceScore` | `screening/maintenance.py` | Commit recency, cadence, bus factor proxy (via PyDriller), issue resolution |
| `ReviewPracticeScore` | `screening/practices.py` | PR template, review presence, label usage, response latency proxy |
| `TestFootprintScore` | `screening/test_footprint.py` | Test directories/pattern presence, test config (pytest.ini, conftest.py), test/source file ratio |
| `CiCdScore` | `screening/ci_cd.py` | `.github/workflows/` presence, CI badge, configuration validity |
| `ReleaseDisciplineScore` | `screening/release_discipline.py` | Semver tagging, release cadence, changelog per release |
| `DependencyQualityScore` | `screening/dependency_quality.py` | Lockfile presence, dependency pinning, update signals (dependabot/renovate config) |

### Output Model

```python
class MetadataScreenResult(BaseModel):
    hygiene: HygieneScore
    maintenance: MaintenanceScore
    review_practice: ReviewPracticeScore
    test_footprint: TestFootprintScore
    ci_cd: CiCdScore
    release_discipline: ReleaseDisciplineScore
    dependency_quality: DependencyQualityScore
    gate1_pass: bool
    gate1_total: float  # weighted composite
```

## Gate 2 — Static/Security Screening

### Sub-scores (each 0.0-1.0)

| Sub-score | Module | What It Checks | Tool Used |
|-----------|--------|----------------|-----------|
| `SecurityHygieneScore` | `screening/scorecard_adapter.py` | OpenSSF Scorecard results, branch protection, workflow security | OpenSSF Scorecard |
| `VulnerabilityScore` | `screening/osv_adapter.py` | Known vulnerabilities in declared dependencies | OSV API |
| `ComplexityScore` | `screening/complexity.py` | LOC, language breakdown, complexity metrics | scc/cloc |
| `SecretHygieneScore` | `screening/secrets_check.py` | Secret detection in repo | gitleaks |

### Screening Tools Integration

| Tool | Purpose | Integration Method |
|------|---------|-------------------|
| PyDriller | Process metrics (commit churn, contributor concentration) | Python library |
| scc / cloc | LOC, language, complexity counts | Subprocess with JSON output |
| Semgrep CE | Static checks multi-language | Subprocess |
| gitleaks | Secret detection | Subprocess, SARIF output |
| OSV scanner/API | Dependency vulnerability scanning | HTTP API |
| OpenSSF Scorecard | Security posture standard assessment | HTTP API (scorecard.dev) |

### Output Model

```python
class StaticScreenResult(BaseModel):
    security_hygiene: SecurityHygieneScore
    vulnerability: VulnerabilityScore
    complexity: ComplexityScore
    secret_hygiene: SecretHygieneScore
    gate2_pass: bool
    gate2_total: float  # weighted composite
```

## Hard Gate Enforcement

The Policy Engine enforces:
- `gate1_pass` must be `True` before Gate 2 screening
- `gate2_pass` must be `True` before Gate 3 deep assessment
- Thresholds configurable per-domain and per-session via MCP tool parameters
- This is implemented as a **hard constraint** in code, not just a configuration option

## Graceful Degradation

If external tools are unavailable (Scorecard, gitleaks, scc):
- Fall back to heuristic estimates where possible
- Mark affected sub-scores with lower confidence
- Never block the entire pipeline on a single tool failure
- **Scorecard fallback aligned**: `ScorecardAdapter._FALLBACK_SCORE = 0.3` (same as `gate2_static._FALLBACK_SCORE`). Previously was 0.5 which inflated Gate 2 scores when repos weren't in the Scorecard DB.

## Gate 2 → Gate 3 Hard Gate in MCP Tools (2026-04-27 fix)

The MCP tool `deep_assess` performs hard gate screening before Gate 3 assessment:
- **deep_assess**: Uses Gate 1 only (metadata, zero cost) to avoid double-clone overhead. Gate 3 already clones via repomix, so running Gate 2 (which also clones) would double the I/O and cause batch timeouts.
- **quick_assess**: Uses Gate 1+2 (full screening) since it's a single repo and the overhead is acceptable.
- Both tools now enrich `RepoCandidate` with real GitHub metadata before screening, fixing inaccurate Gate 1 scores from empty metadata.

## Wave 3 Hardening (Fase 2)

- Gate 1 context collection now tracks degraded API fetches explicitly via `degraded_count`
- GitHub API failures are typed (`GitHubAuthError`, `GitHubRateLimitError`, `GitHubServerError`, `GitHubFetchError`) and logged with error class
- Retry/backoff is enforced in the REST client for retryable classes (rate limit + 5xx)
- Gate 2 startup performs orphan clone cleanup (`cleanup_orphan_clones`) to reduce temp-dir leaks after interrupted runs

## ScoreResult.degraded Flag (Production Readiness v1)

`ScoreResult.degraded: bool | None` signals when Gate 3 scores may be unreliable:

- Set to `True` when `ContentTruncationHeuristic` detects truncation via content similarity drop
- Set to `None` when no deep assessment was performed (Gate 3 not reached)
- Set to `False` when full content was available and assessment was complete
- Surface in CLI `rank` command `degraded` column — analysts can filter or weight results accordingly
- Produced by `ScoringEngine.score()` from `assessment.degraded` field

## See Also

- [Tiered Pipeline](../architecture/tiered-pipeline.md)
- [Scoring Dimensions](scoring-dimensions.md)
- [MCP Tool Specs](../apis/mcp-tools.md)
