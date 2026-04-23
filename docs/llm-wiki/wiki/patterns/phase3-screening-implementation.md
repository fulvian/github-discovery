# Phase 3: Lightweight Quality Screening Implementation

**Title**: Phase 3 Screening Implementation
**Topic**: patterns
**Sources**:
- `docs/plans/phase3-implementation-plan.md` (master plan, 1615 lines)
- `src/github_discovery/screening/` (16 implemented modules)
- `tests/unit/screening/` (18 test files)
**Raw**:
- `docs/plans/phase3-implementation-plan.md`
- `docs/llm-wiki/raw/` (Context7 verification from planning phase)
**Updated**: 2026-04-23
**Confidence**: high

## Summary

Phase 3 implements Layer B of the GitHub Discovery pipeline — the Lightweight Quality Screening layer.
It contains Gate 1 (metadata screening, zero LLM cost) and Gate 2 (static/security screening, zero/low cost),
with a hard enforcement rule: **no candidate reaches Gate 3 (deep assessment) without passing both gates**.

All 14 tasks from the implementation plan are complete. 500 total project tests pass (180 screening tests).
`make ci` green: ruff check + ruff format + mypy --strict + pytest.

## Verification Session (2026-04-23)

A systematic verification against blueprint §16.2-16.5 and roadmap tasks 3.1-3.14 identified and fixed 7 bugs:

### Critical Fixes
1. **Shallow clone management**: `gate2_static.py` now performs `git clone --depth=1` via `SubprocessRunner`, passes `clone_dir` to `SecretsChecker` and `ComplexityAnalyzer`, and cleans up temp dirs in a `finally` block.
2. **SubprocessRunner wiring**: `Gate2StaticScreener` now creates and passes a `SubprocessRunner` to both subprocess-dependent tools (`SecretsChecker`, `ComplexityAnalyzer`).
3. **OSV adapter actual API integration**: Replaced complete stub (always returned value=0.5, confidence=0.0) with real httpx-based OSV.dev API calls with severity scoring, vulnerability counting, and graceful error handling.
4. **`hard_gate_enforcement` setting honored**: `ScreeningSettings.hard_gate_enforcement` (default=True) is now checked in `Gate2StaticScreener.screen()`. When disabled, Gate 1 failures are silently skipped instead of raising `HardGateViolationError`.

### High/Medium Fixes
5. **GateLevel comparison**: Changed from fragile string comparison to `int()` conversion for robust enum comparison.
6. **Missing domain thresholds**: Added WEB_FRAMEWORK, DATA_TOOL, LANG_TOOL, TEST_TOOL, DOC_TOOL to `_DOMAIN_THRESHOLDS` (was only 6 of 12 DomainType values).
7. **Resource cleanup**: Added `close()` method to `Gate2StaticScreener` for httpx client cleanup; OsvAdapter also supports shared/owned client pattern.

### Test Updates
- `test_gate2_static.py`: Added 9 new tests (clone management, hard_gate toggle, cleanup, close)
- `test_osv_adapter.py`: Rewrote with 16 properly mocked tests (was 7 tests making real API calls)
- `test_orchestrator.py`: Added parametrized `TestAllDomainThresholds` (22 test cases covering all 11 domains × 2 gates)
- Total test count: 500 (was 459)

## Architecture

### Gate 1: Metadata Screening (7 sub-score checkers)

| Checker | Module | What it checks |
|---------|--------|---------------|
| HygieneChecker | `hygiene.py` | README, LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, CHANGELOG presence |
| CiCdDetector | `ci_cd.py` | CI/CD system detection (GitHub Actions, Travis, CircleCI, GitLab CI, Jenkins) |
| TestFootprintAnalyzer | `test_footprint.py` | Test directories, config files (pytest, jest, vitest), test file ratio |
| ReleaseDisciplineScorer | `release_discipline.py` | Semver tags, release cadence, release notes quality |
| DependencyQualityScorer | `dependency_quality.py` | Lockfile presence, Dependabot/Renovate config |
| PracticesScorer | `practices.py` | Issue/PR templates, review culture, label usage |
| MaintenanceAnalyzer | `maintenance.py` | Activity recency, commit cadence, bus factor, issue resolution rate |

**Gate 1 engine**: `gate1_metadata.py` — `Gate1MetadataScreener`
- Gathers context from GitHub API via `GitHubRestClient`
- Runs all 7 checkers in parallel
- Computes weighted composite via `MetadataScreenResult.compute_total()`
- Supports custom thresholds per call
- Error isolation: one checker failure doesn't prevent others from scoring
- Auto-fails archived repos (gate1_total=0.0)

### Gate 2: Static/Security Screening (4 adapters)

| Adapter | Module | External Tool |
|---------|--------|--------------|
| ScorecardAdapter | `scorecard_adapter.py` | OpenSSF Scorecard API (HTTPS) |
| OsvAdapter | `osv_adapter.py` | OSV API (HTTPS) — queries for known vulnerabilities with severity scoring |
| SecretsChecker | `secrets_check.py` | gitleaks (subprocess) |
| ComplexityAnalyzer | `complexity.py` | scc (subprocess) |

**Gate 2 engine**: `gate2_static.py` — `Gate2StaticScreener`
- Performs shallow clone (`git clone --depth=1`) for subprocess tools, cleans up temp dirs in finally block
- Runs all 4 adapters in parallel (graceful degradation when tools not installed)
- Hard gate enforcement configurable via `ScreeningSettings.hard_gate_enforcement`
- Batch screening filters out Gate 1 failures automatically
- `close()` method for httpx client resource cleanup

### Policy Engine: `orchestrator.py` — `ScreeningOrchestrator`

- Domain-specific thresholds (e.g., SECURITY domain → stricter Gate 2 threshold)
- `_context_override` helper detects explicit user overrides vs Pydantic field defaults
- `quick_screen()` for single-repo fast quality checks
- `screen_batch()` for bulk screening with error recovery

## Key Implementation Decisions

1. **SubprocessRunner pattern**: Async subprocess execution with timeout, error capture, and structured results
2. **Graceful degradation**: External tools (gitleaks, scc) may not be installed — adapters return neutral scores with confidence=0.0-0.3
3. **PyDriller deferred**: Maintenance analyzer uses API-based heuristics (confidence=0.7) by default. PyDriller requires local clone
4. **OSV API integration**: OsvAdapter queries OSV.dev for vulnerabilities by repo URL, scores by severity (CRITICAL=0.1, HIGH=0.3, MEDIUM=0.5, LOW=0.8), supports shared/owned httpx client pattern
5. **TypeVar pattern**: `TypeVar("_SubScoreT", bound=SubScore)` for type-safe sub-score collection in Gate 1
6. **Dict dispatch**: Mock client in tests uses dict-based URL routing instead of multiple return statements (PLR0911 compliance)

## Test Coverage

- 180 unit tests across 18 test files (500 total project tests)
- `conftest.py` with 16 shared fixtures
- All sub-score checkers tested independently with mock data
- Gate engines tested for threshold enforcement, error isolation, batch processing
- Orchestrator tested for all 11 domain-specific thresholds via parametrized tests
- Gate 2 clone management tested (success, failure, cleanup on error)
- Hard gate enforcement toggle tested (enabled/disabled configurations)
- OSV adapter tested with mocked httpx client (success, timeout, error, severity levels)

## Files Created

### Source (16 modules in `src/github_discovery/screening/`)
`__init__.py`, `types.py`, `subprocess_runner.py`, `hygiene.py`, `ci_cd.py`, `test_footprint.py`, `release_discipline.py`, `dependency_quality.py`, `practices.py`, `maintenance.py`, `gate1_metadata.py`, `scorecard_adapter.py`, `osv_adapter.py`, `secrets_check.py`, `complexity.py`, `gate2_static.py`, `orchestrator.py`

### Tests (18 files in `tests/unit/screening/`)
`__init__.py`, `conftest.py`, `test_types.py`, `test_subprocess_runner.py`, `test_hygiene.py`, `test_ci_cd.py`, `test_test_footprint.py`, `test_release_discipline.py`, `test_dependency_quality.py`, `test_practices.py`, `test_maintenance.py`, `test_gate1_metadata.py`, `test_scorecard_adapter.py`, `test_osv_adapter.py`, `test_secrets_check.py`, `test_complexity.py`, `test_gate2_static.py`, `test_orchestrator.py`

## See Also

- [Screening Gates Detail](domain/screening-gates.md)
- [Tiered Scoring Pipeline](architecture/tiered-pipeline.md)
- [Phase 2 Discovery Engine](patterns/phase2-discovery-plan.md)
