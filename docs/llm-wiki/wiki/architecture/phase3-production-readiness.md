# Phase 3 Production Readiness — Decision Log

## Meta

- **Topic**: Architecture
- **Sources**: [Production Readiness Plan v1](../../plans/discovery_production_ready_plan_1.md)
- **Raw**: `docs/plans/discovery_production_ready_plan_1.md`
- **Updated**: 2026-04-27
- **Confidence**: high

## Overview

Phase 3 addresses 5 critical issues blocking v0.3.0-beta production readiness:
1. Discovery star-neutrality not configurable
2. Gate 2 composite not confidence-aware
3. Gate 3 content truncation was hardcoded (4K chars)
4. Heuristic detection fragile on large OSS repos
5. Confidence floor 0.30 hardcoded

All resolved in Waves A–F covering ~18 tasks across the pipeline.

## Wave A — Discovery Star-Neutrality (TA1–TA4)

- **TA1**: `GHDISC_DISCOVERY_MEGA_POPULAR_THRESHOLD` env var replaces hardcoded `100_000` star filter. `None` disables filtering entirely.
- **TA2**: Structured `discovery_query_built` logging per channel exposes the complete query string and qualifiers.
- **TA3**: `DomainClassifier` class in `discovery/domain_classifier.py` maps repos to `DomainType` via topics → language → description rules (3-tier priority). Singletons via `get_classifier()`.
- **TA4**: `GHDISC_DISCOVERY_CODE_SEARCH_MAX_PAGES` env var (default 1) controls Code Search depth.

## Wave B — Gate 2 Confidence-Aware (TB1–TB4)

- **TB1**: `compute_total()` in `MetadataScreenResult` and `StaticScreenResult` now excludes sub-scores with `confidence ≤ 0.0` from the weighted average. Exposes `coverage` field (fraction of weight with real data). Damping formula mirrors Layer D: `raw * (0.5 + 0.5 * coverage)`.
- **TB2**: Fallback constants unified in `screening/constants.py` as `FALLBACK_VALUE=0.5` (neutral) and `FALLBACK_CONFIDENCE=0.0` (marker). All 4 Gate 2 tool handlers use these.
- **TB3**: `ghdisc doctor` CLI command with 8 checks (git, gitleaks, scc, repomix, GitHub API, NanoGPT, profiles, feature store).
- **TB4**: `SubprocessRunner` deduplicates tool-unavailable warnings via `_unavailable_tools` set.

## Wave C — Gate 3 Content + Confidence (TC1–TC6)

- **TC1**: `ContentStrategy` in `assessment/content_strategy.py` provides tier-based char limits: tiny (240K), small (200K), medium (160K), large (120K), huge (80K).
- **TC2**: Pre-pack token estimation via `estimate_token_count()` from `size_kb`. Huge repos (>1M tokens) activate sampling mode.
- **TC3**: `HeuristicFallback.confidence_cap()` (0.20) replaces hardcoded `0.3` literal. `DeepAssessmentResult.degraded` flag set when ≥1 dimension is heuristic.
- **TC4**: `_compute_overall_confidence()` uses domain-weighted average (matched to `ConfidenceCalculator.compute` in Phase 2), not `min(...)`.
- **TC5**: Tenacity retry on `_TRANSIENT_OPENAI_ERRORS` (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError): 3 attempts, random exponential jitter (multiplier=1, max=30). Instructor `max_retries` handles validation errors separately.
- **TC6**: `token_usage_source` field on `TokenUsage` — logs "api" vs "estimated" for transparency.

## Wave D — Heuristic Detection (TD1–TD3)

- **TD1**: `_detect_ci()` uses path-based patterns (`.github/workflows/`, `Jenkinsfile`, etc.) extracted from Repomix file headers as primary detection. Falls back to content substring only when no headers available.
- **TD2**: Same path-based pattern for `_detect_security()` (SECURITY.md, dependabot.yml, renovate.json) and `_detect_docs()` (README, docs/, CONTRIBUTING, CHANGELOG).
- **TD3**: RepomixAdapter `_SIGNAL_INCLUDE_PATTERNS` ensures CI, docs, and security files are included even in truncation.

## Wave E — Operational Hardening (TE1–TE4)

- **TE1**: `_clone_repo` catches specific types (`OSError`, `asyncio.TimeoutError`) with error-level logging for truly unexpected errors.
- **TE2**: `assessment_results` table in FeatureStore with `put_assessment()`/`get_assessment()`. Uses existing `cache_ttl_hours`. Keyed on `(full_name, commit_sha)`.
- **TE3**: `hard_daily_limit` via `GHDISC_ASSESSMENT_HARD_DAILY_LIMIT`. `BudgetController.check_daily_soft_limit` raises `BudgetExceededError` when exceeded.
- **TE4**: `except Exception` in `_assess_candidate` now re-raises `KeyboardInterrupt`, `SystemExit`, and `MemoryError` before wrapping in `AssessmentError`.

## Wave F — Observability (TF1–TF3)

- **TF1**: Rank CLI table includes Coverage, Confidence, Degraded (✓/✗), Gate3, Corroboration columns.
- **TF2**: `scripts/generate_session_report.py` generates deterministic markdown from session JSON.
- **TF3**: Wiki updated with Phase 3 Production Readiness decision log and cross-references.

## Key Acceptance Criteria Met

| # | Criterion | Status |
|---|-----------|--------|
| 1 | `ghdisc doctor` exists | ✅ |
| 2 | MEGA_POPULAR_THRESHOLD configurable | ✅ |
| 3 | Domain classifier ≥70% accuracy | ✅ |
| 4 | Gate 1/2 expose coverage + confidence-aware composite | ✅ |
| 5 | Fallback constants unified | ✅ |
| 6 | Adaptive content strategy | ✅ |
| 7 | Huge repo sampling | ✅ |
| 8 | `degraded` in rank table | ✅ |
| 9 | Weighted confidence (no min) | ✅ |
| 10 | Tenacity retry | ✅ |
| 11 | Path-based CI/security/docs detection | ✅ |
| 12 | Persistent assessment cache | ✅ |
| 13 | BudgetExceededError on hard limit | ✅ |
| 14 | Session report script | ✅ |
| 15 | Wiki updated | ✅ |
| 16 | 1670 tests, 0 lint, 0 mypy errors | ✅ |

## See Also

- [Phase 2 Audit Remediation](phase2-remediation.md) — Previous audit phase
- [Star-Neutral Quality Scoring](anti-star-bias.md) — Anti-star bias design
- [Tiered Scoring Pipeline](tiered-pipeline.md) — Pipeline architecture with coverage
- [Screening Gates Detail](../domain/screening-gates.md) — Gate compositing with confidence
- [Operational Rules](../patterns/operational-rules.md) — Tenacity retry policy
- [Scoring & Ranking Implementation](../patterns/phase5-scoring-implementation.md) — Degraded flag and weighted confidence
