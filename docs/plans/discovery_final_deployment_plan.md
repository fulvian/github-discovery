# GitHub Discovery — Final Production Deployment Plan

## Meta

- **Status**: Draft v1 — Production GA blueprint
- **Date**: 2026-04-27
- **Type**: End-to-end hardening + distribution + deployment plan
- **Starting baseline**: `v0.3.0-beta` (Phase 3 Production Readiness Waves A–F complete; 1670 tests green; doctor CLI; persistent FeatureStore; adaptive content strategy; tenacity retry; degraded flag; per-profile derivation maps + custom YAML/TOML profiles; smart GitHub rate-limit handling; pipeline bug-fix rounds 1+2 closed)
- **Target**: `v1.0.0` — GA, MCP server published on PyPI + GHCR + Kilo Marketplace, drop-in install on Kilocode CLI / Kilo Code / Claude Code (local stdio + remote streamable-http) and OpenCode, with empirically validated ranking quality (Wave 4 + golden dataset green)
- **Mandatory references (CLAUDE.md)**:
  - Wiki — architecture: `anti-star-bias.md`, `tiered-pipeline.md`, `phase2-remediation.md`, `phase3-production-readiness.md`, `mcp-native-design.md`, `architecture-analysis.md`, `option-c-hybrid.md`
  - Wiki — domain: `discovery-channels.md`, `screening-gates.md`, `scoring-dimensions.md`, `domain-strategy.md`, `competitive-landscape.md`
  - Wiki — patterns: `operational-rules.md`, `agent-workflows.md`, `tech-stack.md`, `phase4-assessment-implementation.md`, `phase5-scoring-implementation.md`, `phase7-mcp-plan.md`, `phase8-cli-plan.md`, `phase9-feasibility-plan.md`, `phase10-alpha-analysis.md`, `marketplace-deployment.md`, `env-isolation-resilience.md`
  - Wiki — apis: `mcp-tools.md`, `mcp-sdk-verification.md`, `agent-integration.md`, `github-api-patterns.md`
  - Foundation: `docs/foundation/github-discovery_foundation_blueprint.md`, `SCORING_METHODOLOGY.md`, `labeling_guidelines.md`, `benchmark_report.md`, `calibration_report.md`
  - Context7 (verify before code): `/prefecthq/fastmcp` (HTTP, streamable-http, stateless, auth, custom_route health), `/andersonby/python-repomix` (RepoProcessor, RepomixConfig, compression, include patterns, token counting), `/websites/python_useinstructor`, `/openai/openai-python`, `/websites/pydantic_dev_validation`, `/modelcontextprotocol/python-sdk`, `pydantic-settings`, `tenacity`, `httpx`, `structlog`, `aiosqlite`, `typer`, `rich`, `hypothesis`
- **Scope guard**: No regression. 1670 tests must stay green. Only additions and surgical fixes.
- **Non-negotiables (CLAUDE.md §Key Rules)**:
  - Stars are **context only**, never primary ranking signal — anti-bias philosophy preserved end-to-end
  - Hard gate: no Gate 3 without Gate 1+2 pass — enforced at code level, not config
  - All public functions fully type-annotated, mypy `--strict` clean
  - structlog only — never `print()` for diagnostics
  - No bare `Exception` raises — use `exceptions.py` hierarchy
  - Python 3.12+, ruff line-length 99, `from __future__ import annotations`

---

## Index

1. [Goal & Quality Bar](#1-goal--quality-bar)
2. [Discovery Philosophy Preservation Contract](#2-discovery-philosophy-preservation-contract)
3. [Gap Analysis vs v1.0.0](#3-gap-analysis-vs-v100)
4. [Wave Structure & Sequencing](#4-wave-structure--sequencing)
5. [Wave G — Empirical Validation of Anti-Bias Claim](#5-wave-g--empirical-validation-of-anti-bias-claim)
6. [Wave H — Discovery Robustness & Channel Diversity Hardening](#6-wave-h--discovery-robustness--channel-diversity-hardening)
7. [Wave I — Screening & Assessment Resilience](#7-wave-i--screening--assessment-resilience)
8. [Wave J — MCP Server GA Hardening](#8-wave-j--mcp-server-ga-hardening)
9. [Wave K — Distribution: PyPI + Docker + UVX](#9-wave-k--distribution-pypi--docker--uvx)
10. [Wave L — Deployment: Claude Code Local + Kilocode + Kilo Marketplace](#10-wave-l--deployment-claude-code-local--kilocode--kilo-marketplace)
11. [Wave M — Observability & Operational SRE](#11-wave-m--observability--operational-sre)
12. [Wave N — Security, Supply Chain & Compliance](#12-wave-n--security-supply-chain--compliance)
13. [Wave O — Documentation, Examples, Onboarding](#13-wave-o--documentation-examples-onboarding)
14. [Test Plan](#14-test-plan)
15. [Acceptance Criteria — v1.0.0 GA](#15-acceptance-criteria--v100-ga)
16. [Rollback & Risk Register](#16-rollback--risk-register)
17. [Context7 + Wiki Cross-References](#17-context7--wiki-cross-references)
18. [Out of Scope](#18-out-of-scope)

---

## 1) Goal & Quality Bar

Bring GitHub Discovery from `v0.3.0-beta` (engineering complete, internally validated) to `v1.0.0` (publicly distributed, externally validated, drop-in installable on every supported agent platform). The plan is structured around **eight waves (G–N + O)** that run sequentially with dependencies, never compromising on:

- **Anti-star-bias philosophy**: hidden gems with 0–500 stars must remain rankable on equal footing with widely-adopted repos when their `quality_score` is competitive (verified empirically, not asserted).
- **Code reality**: only repositories with valid, up-to-date, secure, and maintained code reach Gate 3 — hard gates enforced in code (`HardGateViolationError`).
- **Cost & resource discipline**: per-repo hard token cap (100K) enforced; daily soft monitoring + optional hard cap; no LLM call without prior cache + budget check.
- **Determinism**: blake2b tie-breaking, ranking_seed, deterministic JSON output, snapshot-testable.
- **MCP-first**: every feature reachable via MCP tool before API/CLI; default tool output ≤ 2K tokens; session-aware; progressive deepening.
- **Zero silent failure**: every external call typed-error'd, retried where transient, logged with full context.

GA means: a developer running `uvx github-discovery mcp serve --transport stdio` on a fresh machine with only Python 3.12 + uv installed gets a functional discovery pipeline that auto-detects missing system tools (`git`, `gitleaks`, `scc`, `repomix`) and either uses bundled fallback or surfaces a structured `DegradedMode` warning to the agent. No hidden assumptions.

---

## 2) Discovery Philosophy Preservation Contract

This contract is enforced as code-level invariants and as test assertions. Any change in the codebase that breaks any clause MUST fail CI.

| ID | Invariant | Enforcement |
|----|-----------|-------------|
| INV-1 | `Ranker._sort_key()` does not include `stars` in any tuple position | Property test (`hypothesis`) — generate ranked sets where star order is reversed; `quality_score` rank order must be unchanged |
| INV-2 | `ValueScoreCalculator.compute(quality, stars)` returns `quality` exactly (stars unused) | Existing unit + property test, extended to range `0 ≤ stars ≤ 10⁹` |
| INV-3 | `ScoreResult.value_score == ScoreResult.quality_score` for every produced result | Snapshot test on golden dataset run |
| INV-4 | A repo with `stars=0` and `quality_score ≥ 0.7` MUST surface as `is_hidden_gem=True` | Wave G golden test |
| INV-5 | `DomainProfile.dimension_weights` SUM to 1.0 ± 1e-6 across all 12 built-in profiles, after every change | Property test runs in CI |
| INV-6 | `Discovery.search_channel.build_query()` MUST NOT add `stars:>` lower bound qualifier (only `-stars:>` upper exclusion when `mega_popular_threshold` is set) | Regex-based unit assertion + log-replay test on `discovery_query_built` events |
| INV-7 | Hard gate cannot be bypassed: every code path entering `AssessmentOrchestrator.assess()` raises `HardGateViolationError` if `screening` is None or `screening.gate_passed(GateLevel.STATIC_SECURITY) is False` | Coverage gate — mutation test (`mutmut`) on `_check_hard_gate` must kill ≥ 95% of mutants |
| INV-8 | `quality_score` damping formula `raw * (0.5 + 0.5 * coverage)` always applied — never bypassed even when coverage = 1.0 | Property test |
| INV-9 | Every dimension scored from heuristic fallback has `confidence ≤ 0.25` (HeuristicFallback cap) | Property test |
| INV-10 | `degraded` flag propagates: if any DimensionScore is heuristic-sourced, `DeepAssessmentResult.degraded == True` AND `ScoreResult.degraded == True` | E2E test on synthetic truncation-forced repo |

A new test module `tests/invariants/test_anti_bias_contract.py` collects all INV-* checks. CI fails on any failure regardless of unrelated test status.

---

## 3) Gap Analysis vs v1.0.0

Verified against `git status`, `pyproject.toml`, `docs/llm-wiki/`, and code. Each gap maps to a Wave.

### 3.1 Empirical Validation Gaps

- Wave 4 (calibration) has report stubs (`docs/foundation/benchmark_report.md`, `calibration_report.md`) but no live reproducible run with current pipeline.
- `feasibility/golden_dataset.py` exists, untracked; no labeled corpus committed.
- INV-4 ("0-star + quality≥0.7 → hidden gem") never asserted on a real repo set.
- Domain classifier accuracy claim ≥70% (TA3) is asserted in wiki but not measured against a labeled set.

### 3.2 Discovery Robustness Gaps

- `CuratedChannel` works on a hardcoded list of awesome-X repos. README parsing is regex-only; no rate-limit-aware retry around `/repos/{owner}/{repo}/readme`.
- `RegistryChannel` uses npm `/-/v1/search` — no fallback; PyPI uses single-package JSON API, no batched search.
- `DependencyChannel` uses GitHub SBOM endpoint; on private/disabled dependency-graph repos returns empty silently.
- `SeedExpansion` runs only when `seed_urls` provided; no automatic seed discovery from query.
- No "freshness" channel: a repo updated 1 hour ago with high `pushed_at` recency is not boosted vs. a stale-but-popular one.
- `mega_popular_star_threshold` defaults to 100K but is silently None-able, and the inactivity filter (`pushed:>180d`) interacts with the star filter unpredictably for niche communities (e.g. retro-computing, security tooling) where 6-month pushed cutoff is too aggressive.

### 3.3 Screening Resilience Gaps

- Gate 2 still requires `git`, `gitleaks`, `scc` on PATH. `doctor` reports missing tools but pipeline degrades silently to `confidence=0.0`.
- `ScorecardAdapter` swallows generic `Exception` (line 89 of `scorecard_adapter.py`) — should use typed `httpx` errors.
- `OsvAdapter` (per wiki) is single-package JSON API; OSV `/v1/querybatch` (P95 ≤ 6s) batches up to 1000 packages — unused → screening of monorepos with 100s of deps is N×slower.
- Clone management uses `tempfile.mkdtemp` per repo; no clone reuse across screening + assessment stages → double-clone overhead documented in BUG 3.
- Gate 1 metadata enrichment in MCP tools is duplicated between `_build_candidates_with_metadata` and the discovery pipeline; risk of drift.

### 3.4 Assessment Resilience Gaps

- `RepomixAdapter._truncate_content` uses `_CHARS_PER_TOKEN = 4` approx; for code-heavy repos (Rust/C++) the ratio differs and budget overruns by 10–20%.
- Huge repo sampling (TC2) computes a 5% file sample but does not stratify by directory — risks over-sampling tests, under-sampling `src/`.
- `LLMProvider` `MD_JSON` mode is hardcoded; doesn't fall back to `TOOLS` mode when `MD_JSON` parsing fails on a stricter model.
- `AssessmentOrchestrator._cache` is in-memory dict + persistent FeatureStore; cross-process MCP server (multiple workers) won't share in-memory cache → cache miss spike on warm restart unless persistent cache hit.
- LLM call timeout default (120s) is reasonable but no per-dimension timeout — a single slow model can drag the whole batch.

### 3.5 MCP Server GA Gaps

- HTTP transport not exercised in CI — only stdio. No load test of streamable-http.
- No `/health` endpoint registered (FastMCP docs recommend `mcp.custom_route("/health", methods=["GET"])`).
- No OAuth 2.1 layer for HTTP transport (MCP Nov 2025 spec mandate for public-internet servers).
- `cleanup_orphan_clones()` runs on startup but not on graceful shutdown — long-lived servers accumulate.
- AppContext exposes `_rest_client` but BUG 7 fix made it a typed field; still 4 other places where private attrs leak across modules — needs full audit.

### 3.6 Distribution Gaps

- Package not on PyPI (`uvx github-discovery` will fail today).
- No `Dockerfile` in repo; no GHCR build/push automation.
- `pyproject.toml` version is `0.1.0-alpha` even though wiki states v0.3.0-beta — version drift.
- `[project.scripts]` exposes only `ghdisc = "github_discovery.cli.app:app"` — no `github-discovery` console alias mentioned in `marketplace-deployment.md`.
- No release workflow (`.github/workflows/release.yml`); only `ci.yml`.
- No SBOM publication; no signed releases (cosign / sigstore).

### 3.7 Deployment Gaps

- `.mcp.json` and `.kilo/mcp.json` use absolute path `/home/fulvio/...` to .venv — won't transfer.
- No template `.mcp.json.example` / `.kilo/mcp.json.example` documented in README for end-users.
- Kilo Marketplace PR not submitted (`mcps/github-discovery/MCP.yaml` not in upstream).
- Claude Desktop / Claude Code config snippets present in wiki but not validated end-to-end on a fresh machine.
- OpenCode config present in wiki but no smoke test.

### 3.8 Observability Gaps

- Pure structlog JSON; no OpenTelemetry traces.
- No latency histogram per MCP tool, no token-cost metric, no hard-gate-rejection rate.
- `BudgetController` has logs but no Prometheus-shaped counters.
- E2E session reports (`scripts/generate_session_report.py`) are markdown-only; no CSV/JSON for ingestion.

### 3.9 Security & Supply Chain Gaps

- No bandit/semgrep CI step (ruff-bandit `S` rules cover python but not deps).
- No `pip-audit` / `osv-scanner` step in CI for our own deps.
- GitHub token only required scope-checked at runtime (`GitHubAuthError` catches it) but no doctor-side scope minimum check (e.g. `public_repo` only).
- No CODEOWNERS, no SECURITY.md at repo root, no responsible disclosure flow.

### 3.10 Documentation & Onboarding Gaps

- README.md presence not verified at root of repo.
- No "Quick Start in 60 seconds" section.
- No reference workflow examples for the three target agents (Claude Code / Kilocode / OpenCode).
- No troubleshooting guide for common failures (missing git, no GitHub token, NanoGPT 401).

---

## 4) Wave Structure & Sequencing

Waves run with the following dependency DAG. Critical path: G → I → J → K → L. Waves H and M can run in parallel after G. Waves N and O can run alongside late J onwards.

```
G (validation) ──┬─→ H (discovery) ──┐
                 │                    ├─→ J (mcp ga) ─→ K (dist) ─→ L (deploy) ─→ v1.0.0
                 └─→ I (screen+asses) ┘
                                       └─→ M (obs)  ──┘
                                       └─→ N (sec)   ─→ L
                                       └─→ O (docs)  ─→ v1.0.0
```

| Wave | P | Effort | Dep | Owner suggestion |
|------|---|--------|-----|------------------|
| G — Empirical validation | P0 | 4d | — | data-eng |
| H — Discovery robustness | P0 | 5d | G | platform |
| I — Screening + assessment | P0 | 5d | G | platform |
| J — MCP GA | P0 | 4d | H+I | platform |
| K — Distribution | P0 | 3d | J | release-eng |
| L — Deployment | P0 | 3d | K | release-eng |
| M — Observability | P1 | 3d | J | sre |
| N — Security & supply chain | P1 | 2d | J | sec-eng |
| O — Docs & examples | P1 | 3d | L | dx |

Total critical path: ~24 working days (≈5 weeks one FT dev) or ~3 weeks with two devs.

---

## 5) Wave G — Empirical Validation of Anti-Bias Claim

**Objective**: Prove the philosophy works on real, labeled data before shipping. No marketing claim without measurement.

### G1 — Golden dataset construction (1.5d)

- Curate **300 repos** balanced across 12 domains (25 each), stratified by star bucket: `[0, 50)`, `[50, 500)`, `[500, 5000)`, `[5000+]` — ~6 per bucket per domain.
- Source candidates from existing wave-4 reports + manual additions across niche language communities (Zig, Nim, OCaml, Crystal — known to have hidden quality with low stars).
- Each repo labeled by 2 of {Claude, Gemini, ChatGPT} on the 8 dimensions (0.0–1.0 scale per `labeling_guidelines.md`); inter-rater agreement (Cohen's kappa ≥ 0.6) — disagreements adjudicated by a human pass.
- Persist as `tests/golden/dataset.jsonl` (one JSON per repo with `full_name`, `domain`, `stars_bucket`, expert dimension labels, expected `quality_score` band ±0.1).

### G2 — Reproducible benchmark runner (1d)

- New CLI: `ghdisc benchmark run --golden tests/golden/dataset.jsonl --out reports/benchmark_$(date).json`
- Runs full pipeline (Discovery skipped — repos pre-known; Gate 1+2+3 + Ranking) on each repo, captures per-dimension predicted vs. labeled, computes:
  - **Spearman ρ** between predicted `quality_score` and label
  - **Precision@10**, **Precision@25** for top-quality identification
  - **NDCG@25** (already in `feasibility/metrics.py`)
  - **Hidden-gem recall**: of all repos with `stars < 500 AND label_quality ≥ 0.7`, fraction surfaced in top-25 (target ≥ 0.6)
  - **Anti-bias gap**: mean rank of `stars=0` repos with `label_quality ≥ 0.7` vs. mean rank of all repos with same label band — must be within ±5 ranks
  - **Domain classifier accuracy** (Wave A TA3 claim ≥70%) — measured F1 macro across 12 domains
- Output committed to `reports/benchmark_<date>.json` + markdown summary.
- CI nightly job runs against a smaller smoke subset (30 repos, 1 per bucket per domain) — failures gate releases.

### G3 — Calibration of weights & thresholds (1d)

- For each domain profile, fit dimension weights via constrained linear regression (sum=1, ≥0) on golden data minimizing MSE on `quality_score`.
- Compare with handcrafted weights — if regression weights are within 0.05 of handcrafted, keep handcrafted (interpretability). Otherwise update profile and re-run G2.
- Calibrate Gate 1+2+3 thresholds against golden quality bands (e.g. Gate 3 threshold 0.6 may be too lax for ML_LIB).
- Persist calibration report to `docs/foundation/calibration_report.md`.

### G4 — Anti-bias contract test suite (0.5d)

- Implement `tests/invariants/test_anti_bias_contract.py` — 10 INV tests from §2.
- All run against the golden dataset on `make ci`.
- Add `pytest.mark.invariant` so they run independently and produce a separate CI badge.

**Acceptance**: Spearman ρ ≥ 0.65 vs. label, hidden-gem recall ≥ 0.6, anti-bias gap |ΔRank| ≤ 5, domain classifier F1 macro ≥ 0.70, all 10 INV tests pass.

---

## 6) Wave H — Discovery Robustness & Channel Diversity Hardening

**Objective**: Find more hidden gems with confidence. Reduce false positives, broaden recall in niche communities, kill silent failures.

### H1 — Adaptive activity filter (0.5d)

- Replace fixed `pushed:>180d` with domain-aware threshold from `DomainProfile.activity_threshold_days` (default 180, but `LANG_TOOL`=365, `SECURITY_TOOL`=90).
- Make threshold configurable via `GHDISC_DISCOVERY_ACTIVITY_DAYS` for ad-hoc overrides.
- Add `archived:false` and `disabled:false` qualifiers (already there for archived; add disabled) to all channels.

### H2 — Recency-channel injection (0.5d)

- Add a synthetic `RECENCY` boost: candidates from any channel with `pushed_at >= now - 30d` get `discovery_score += 0.05` (capped at 1.0). Logged as new bonus type alongside breadth/quality bonuses.
- Test: synthetic candidate set with two repos identical except `pushed_at` — recent one ranks higher in pool.

### H3 — Curated channel resilience (1d)

- Replace regex-only README parsing with a tolerant Markdown parser (`mistune` or `markdown-it-py`) — extract URLs from links, headings, lists.
- Cache parsed awesome lists in FeatureStore (`awesome_list_cache` table, TTL 24h) — reduces GitHub API calls.
- Add fallback to GitHub Topic search (`topic:awesome-<lang>`) when the curated map has no entry.
- Add a `_MAX_CURATED_PER_LIST = 200` cap to prevent a single huge list from dominating.

### H4 — Registry channel: PyPI search + crates.io + Maven Central (1.5d)

- PyPI: use the public BigQuery dataset mirror (`pypi.org/simple` for project list, then JSON for top-100 by recent uploads matching keywords).
- Add **crates.io** (`/api/v1/crates?q=...&sort=recent-updates`) and **Maven Central** (`search.maven.org/solrsearch/select`) endpoints.
- Each registry implementation behind a small `RegistryAdapter` Protocol; keep `RegistryChannel` as the orchestrator.
- Rate-limit aware (registry-side limits documented per adapter).

### H5 — Dependency channel: dependents discovery (1d)

- Use GitHub `/repos/{owner}/{repo}/network/dependents` (HTML scraping or graphql `dependencyGraphManifests`) to discover repos that *depend on* a high-quality seed (reverse SBOM).
- Cap depth=1, dedupe with existing seen set, attribute `discovery_score=0.6` (lower than direct seed deps because indirection).

### H6 — Seed expansion: auto-seed from query (0.5d)

- When `query.seed_urls` empty, run a quick top-3 search query first, use those as seeds — opt-in via `query.auto_seed=True`.
- Test: regression on cases without seed_urls — must produce ≥ baseline candidate count.

### H7 — Channel observability (0.5d)

- Each channel emits `discovery_channel_completed` log with `channel`, `query`, `candidates_found`, `rate_limit_remaining`, `elapsed_seconds`, `errors[]`.
- Add `ChannelResult.errors: list[str]` field — surfaced in `DiscoveryResult` for agent visibility.
- Update MCP `discover_repos` output to include `errors_per_channel` summary (≤ 200 tokens added).

**Acceptance**: G2 recall metric for stars<50 bucket ≥ 0.55 (vs. baseline ~0.40), all channels log structured completion, no silent empty results, golden tests still pass.

---

## 7) Wave I — Screening & Assessment Resilience

**Objective**: Pipeline runs on a fresh machine without manual tool install. Quality scores are honest about coverage. Cache shared across processes.

### I1 — Bundled vs system tool resolution (1.5d)

- New module `screening/tool_provider.py` with `ToolProvider` Protocol — implementations:
  - `SystemToolProvider`: current behavior (PATH lookup).
  - `BundledToolProvider`: ships pre-built binaries for `gitleaks`, `scc` via `pip extras` (`github-discovery[bundled-tools]`) — embedded as `package_data` per-platform wheels; doctor instructs install.
  - `PythonShimProvider`: Python-only fallback for `gitleaks` (use `detect-secrets` PyPI package) and `scc` (use `pygount` or in-house line counter) — lower fidelity, marked `confidence_cap=0.5`.
- `Gate2StaticScreener` resolves provider at init via doctor-style detection. Provider result cascades: System → Bundled → Python shim.
- New env var `GHDISC_SCREENING_TOOL_MODE` ∈ `{auto, system, bundled, python_shim}`.
- Provider mode logged at startup; `ScreeningResult.tool_mode_used` field for transparency.

### I2 — Confidence-aware fallback (0.5d)

- Each provider declares its confidence multiplier:
  - System tool → 1.0
  - Bundled binary → 0.95
  - Python shim → 0.50
  - Failed → 0.0 (existing fallback)
- Sub-score `confidence` is multiplied by provider multiplier. `compute_total()` damping (already excludes confidence ≤ 0.0) propagates honestly.
- Test: a screening run with all-shim providers gets gate2_total damped vs. all-system run.

### I3 — Clone reuse across Gate 2 + Gate 3 (1d)

- Introduce `CloneManager` singleton with `acquire(repo_url) -> Path` returning a refcounted shallow clone. Gate 2 and Gate 3 (repomix `repo_url=local_path`) share the same clone.
- Refcount drops to 0 → 60s grace period → cleanup. `cleanup_orphan_clones()` extended to use refcount file.
- Wave G nightly benchmark measures clone time saved (target 40% reduction on full pipeline).

### I4 — OSV batch query adoption (0.5d)

- Replace per-package OSV calls with `POST /v1/querybatch` (up to 1000 packages, P95 ≤ 6s).
- Group queries by ecosystem (PyPI, npm, Go, RubyGems). Wrap with tenacity (transient 5xx).
- Limit single batch payload to 32 MiB (HTTP/1.1) — auto-split larger.

### I5 — Repomix accuracy & sampling (1d)

- Replace `_CHARS_PER_TOKEN=4` heuristic with the actual tokenizer (`tiktoken` for `o200k_base` if available, else fall back to estimate). Already used by repomix internally — re-use the result instead of re-estimating.
- Stratified sampling for huge repos: `compute_sample_size()` extended to use directory weights — `src/`,`lib/`,`pkg/` get 60% of budget, `tests/` 20%, root 10%, `docs/` 10%.
- Add `RepomixAdapter.pack_with_strategy(SizeTier)` — drives `include_patterns` more aggressively for huge tier (only signals + sample of source).

### I6 — LLM provider fallback chain (0.5d)

- `LLMProvider` accepts `models: list[str]` (primary + fallbacks). On persistent failure, walks the chain.
- Add `mode_fallback`: if `MD_JSON` parse fails, retry once with `Mode.TOOLS`.
- Per-dimension timeout (split `call_timeout` across N dimensions in batch mode).

### I7 — Heuristic scoring rigor (0.5d)

- `HeuristicAnalyzer` extended to use the real file-paths emitted by repomix (already done for CI/test detection in TD1) for ALL detection methods (security files, docs, type hints in py, etc.).
- Per `_DIMENSION_CONFIDENCE_FROM_GATE12` (Fase 2 T2.3), each heuristic returns its dimension-specific cap; `confidence_cap=0.25` becomes the upper bound but not always the value.

**Acceptance**: Pipeline succeeds end-to-end on a fresh container with only Python+uv+git installed (no gitleaks/scc on PATH); coverage and degraded flags accurately reflect tool availability; OSV batch latency P95 ≤ 6s for 100-dep monorepo; repomix tier-aware sampling produces stable token count within ±2% of budget.

---

## 8) Wave J — MCP Server GA Hardening

**Objective**: Production-ready MCP server: HTTP/stdio dual mode, health, auth, graceful lifecycle, no foreign-CWD or context-leak surprises.

### J1 — Dual transport CI (0.5d)

- Existing `tests/mcp/` covers stdio. Add `tests/mcp/test_streamable_http.py` exercising tool round-trip via FastMCP's in-process HTTP test client.
- CI matrix: stdio + streamable-http, both must pass.

### J2 — Health endpoint (0.25d)

- Per FastMCP docs, register `mcp.custom_route("/health", methods=["GET"])` returning `{"status": "ok", "version": ..., "doctor_summary": {...}}`.
- Deep health (`/health?deep=true`) runs the doctor checks (subset, fast).

### J3 — Stateless mode for production (0.25d)

- `Settings.mcp.stateless_http: bool` (env `GHDISC_MCP_STATELESS_HTTP`, default `False`).
- When `True`, pass `stateless_http=True` to `FastMCP(...)` constructor; document trade-off (no session continuity across requests, must pass `session_id` explicitly each call).

### J4 — OAuth 2.1 / API key for HTTP (1d)

- Per MCP Nov 2025 spec: HTTP transport on public internet must require auth.
- For v1.0.0 ship API-key bearer (simple, no IdP needed): `Authorization: Bearer <key>` validated against `GHDISC_MCP_API_KEYS` (comma-separated, hashed at rest).
- OAuth 2.1 deferred to v1.1 (post-GA) but document the path.
- Custom middleware on the FastMCP `http_app()` rejects unauthenticated requests except `/health`.

### J5 — Graceful shutdown lifecycle (0.5d)

- Lifespan `finally:` block in `app_lifespan` already closes resources; add explicit `cleanup_orphan_clones()` call on shutdown (not just startup).
- Trap SIGTERM in `serve()` → call `mcp.shutdown()` → drain in-flight tools (max 30s) → close.
- Add `MCP_SERVER_SHUTDOWN` log event with active-tool count.

### J6 — Context-leak audit (0.5d)

- Grep for any `app_ctx.<orch>._<priv>` usage (BUG 7 pattern). Replace each with public field on `AppContext` or method on the orchestrator.
- Test: introduce `mypy-strict` rule that flags private attribute access in `mcp/tools/`.

### J7 — Output-token discipline (0.5d)

- Every tool's main return path must respect `GHDISC_MCP_MAX_CONTEXT_TOKENS=2000` (existing setting).
- Add `format_tool_result()` enhancement: when result exceeds budget, auto-paginate into `summary` + `details_via_resource_uri` pointer (e.g., `pool://{id}/full`).
- Add CI test that runs each tool with a stub-large result and asserts ≤ 2K tokens.

### J8 — Session management TTL + pruning (0.5d)

- `SessionManager` already in SQLite. Add background prune task on lifespan: remove sessions older than 30d, idle > 7d.
- New CLI: `ghdisc db prune sessions --older-than 30d`.

**Acceptance**: Both transports pass CI, /health responds, auth enforced when `GHDISC_MCP_API_KEYS` set, graceful shutdown ≤ 30s, no private attribute access in tools, every tool ≤ 2K tokens.

---

## 9) Wave K — Distribution: PyPI + Docker + UVX

**Objective**: `uvx github-discovery` and `docker run ghcr.io/.../github-discovery` work out of the box.

### K1 — Version alignment (0.25d)

- Bump `pyproject.toml` to `0.3.0-beta` (current state) → planned bumps `0.3.x` for Wave G fixes, `1.0.0` GA cut.
- Add `__version__` constant in `src/github_discovery/__init__.py` driven by `importlib.metadata`.

### K2 — Project scripts & entry points (0.25d)

- `pyproject.toml [project.scripts]`:
  - `ghdisc = "github_discovery.cli.app:app"` (existing)
  - `github-discovery = "github_discovery.cli.app:app"` (new alias for uvx)
  - `github-discovery-mcp = "github_discovery.mcp.__main__:main"` (direct MCP entry — optional)

### K3 — PyPI release workflow (0.5d)

- New `.github/workflows/release.yml`:
  - Trigger: `push: tags: v*.*.*`
  - Steps: ruff, mypy, pytest (full + golden), build (`uv build`), `twine check`, `twine upload` via PyPI Trusted Publisher (OIDC, no token).
- TestPyPI dry-run on `release-candidate*` tags.

### K4 — Docker image (1d)

- `Dockerfile` (multi-stage):
  - Stage 1: `python:3.13-slim` + `uv` + repo source + `uv sync --frozen`
  - Stage 2: `gcr.io/distroless/python3-debian12` + virtualenv + `gitleaks` + `scc` binaries (from official releases) + `git`
  - Entrypoint: `python -m github_discovery.mcp serve`
- `.dockerignore` to keep build context small.
- Multi-arch build (amd64 + arm64) via `docker buildx`.
- CI builds image on every push to `main`, pushes to `ghcr.io/<org>/github-discovery:dev`. On release tag → `:latest` + `:vX.Y.Z`.

### K5 — UVX install validation (0.25d)

- New CI smoke test: in a clean container with only `python:3.13-slim` + `uv`, run `uvx --from github-discovery==<version> ghdisc doctor` and assert exit=0 (or expected non-zero with informative output if external tools missing).

### K6 — Bundled-tools wheel (1d, optional but high-value)

- `github-discovery[bundled-tools]` extra installs `gitleaks-bin`/`scc-bin` PyPI packages (or wraps their releases).
- Allows pure-Python install without container for `confidence ≥ 0.95`.

**Acceptance**: `uvx github-discovery mcp serve --transport stdio` works on a fresh `python:3.13-slim`. `docker run --rm ghcr.io/<org>/github-discovery:latest doctor` exits 0. Multi-arch image published.

---

## 10) Wave L — Deployment: Claude Code Local + Kilocode + Kilo Marketplace

**Objective**: Drop-in installation flows verified on each agent platform.

### L1 — Reference configs (0.5d)

- Replace absolute path in `.mcp.json` and `.kilo/mcp.json` with `uvx` invocation:
  ```json
  // .mcp.json (Claude Code)
  {
    "mcpServers": {
      "github-discovery": {
        "command": "uvx",
        "args": ["github-discovery", "mcp", "serve", "--transport", "stdio"],
        "env": {
          "GHDISC_GITHUB_TOKEN": "${GITHUB_TOKEN}",
          "GHDISC_ASSESSMENT_NANOGPT_API_KEY": "${NANOGPT_API_KEY}",
          "GHDISC_SESSION_BACKEND": "sqlite"
        }
      }
    }
  }
  ```
- Provide both `.mcp.json` (active) and `.mcp.json.example` (for users to copy).
- Same for `.kilo/mcp.json` using array `command` + `environment` + `{env:VAR}` syntax.
- Provide `opencode.json.example`.

### L2 — Claude Code local validation (0.5d)

- Smoke script `scripts/smoke_claude_code.sh`:
  - Spawn Claude Code with project directory containing only `.mcp.json` + `CLAUDE.md`.
  - Issue MCP tool call `discover_repos {"query": "rust async runtime", "max_candidates": 5}`.
  - Assert response within 60s, ≥ 1 candidate.
- Run nightly + on every PR touching `mcp/`.

### L3 — Kilocode CLI / Kilo Code validation (0.5d)

- Smoke script `scripts/smoke_kilocode.sh` mirrors L2 with `kilo` CLI.
- Validates `{env:VAR}` expansion, array `command`, namespaced `github-discovery_discover_repos`.

### L4 — OpenCode validation (0.25d)

- Smoke script `scripts/smoke_opencode.sh` per `opencode.ai/docs/mcp-servers/`.

### L5 — Kilo Marketplace MCP.yaml submission (0.5d)

- Author `mcps/github-discovery/MCP.yaml` per `marketplace-deployment.md` spec — UVX (recommended) + Docker options.
- Open PR on `Kilo-Org/kilo-marketplace` titled "Add GitHub Discovery MCP server".
- Add `id`, `tags`, `prerequisites` per Kilo conventions.

### L6 — Claude Desktop config snippet (0.25d)

- Add to README + wiki the verified `mcpServers` block for Claude Desktop.

### L7 — End-to-end install matrix CI (0.5d)

- New job `e2e-install` in CI matrix:
  - Combinations: (`uvx`, `docker`) × (`stdio`, `streamable-http`) × (3 OS: ubuntu-latest, macos-latest, windows-latest stdio-only)
  - For each: install, start MCP server, run a single tool call, validate.
- Failures gate the release.

**Acceptance**: All 4 platforms (Claude Code, Kilo Code, OpenCode, Claude Desktop) install and run a discovery query within 60s; Kilo Marketplace PR open; install matrix green.

---

## 11) Wave M — Observability & Operational SRE

**Objective**: Production debug-ability without shipping logs blind.

### M1 — OpenTelemetry tracing (1.5d)

- Add `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-httpx` to `pyproject.toml` extras `[otel]`.
- Wrap each MCP tool with a span via `opentelemetry.trace.get_tracer(__name__).start_as_current_span(tool_name)`.
- Span attributes: `mcp.tool`, `mcp.session_id`, `repo.full_name`, `gate.level`, `tokens.used`, `cache.hit`.
- Integrate with structlog: every log record adds `trace_id`/`span_id` from current context.
- OTLP exporter via env `OTEL_EXPORTER_OTLP_ENDPOINT` — no-op if unset (zero overhead).

### M2 — Metrics (Prometheus shape, 1d)

- New module `mcp/metrics.py` — `prometheus_client` (extras `[metrics]`):
  - `ghdisc_mcp_tool_duration_seconds{tool}` (histogram)
  - `ghdisc_mcp_tool_calls_total{tool, status}` (counter)
  - `ghdisc_assessment_tokens_used{model}` (counter)
  - `ghdisc_screening_gate_passed_total{gate}` (counter)
  - `ghdisc_discovery_candidates_total{channel}` (counter)
- Expose `/metrics` GET via `mcp.custom_route` (HTTP transport only; opt-in via `GHDISC_METRICS_ENABLED`).

### M3 — Session report multi-format (0.25d)

- Extend `scripts/generate_session_report.py` with `--format json|csv|md` (md is current).

### M4 — Log sampling for high-volume events (0.25d)

- For `discovery_query_built` and similar high-cardinality events, add structlog sampling processor (1 in 100 by default).

**Acceptance**: OTLP traces visible in any backend (Jaeger, SigNoz, Honeycomb), metrics at `/metrics` when enabled, all observability is opt-in (zero default overhead).

---

## 12) Wave N — Security, Supply Chain & Compliance

**Objective**: Pass an external supply-chain audit without rework.

### N1 — Dependency audit in CI (0.25d)

- Add `pip-audit` step to `.github/workflows/ci.yml`. Fail on HIGH/CRITICAL.
- Add `osv-scanner` step over `pyproject.toml` + lockfile (we should add `uv.lock`).

### N2 — Static analysis (0.5d)

- Add `bandit` (additional to ruff S rules) — fail on MEDIUM+.
- Add `semgrep --config=auto` step.
- All findings logged to GH Code Scanning (SARIF upload).

### N3 — SBOM + signed releases (0.5d)

- Generate CycloneDX SBOM (`cyclonedx-py`) on release; attach to GitHub Release + push to image as `sbom.cdx.json`.
- Sign images with cosign (keyless via OIDC).
- Sign PyPI release with sigstore (Trusted Publisher already covers it).

### N4 — GitHub token scope minimization (0.25d)

- `doctor` checks token via `/user` endpoint and warns if scope > `public_repo` (we only read public).
- Document in README: "GitHub Discovery only requires `public_repo` scope. Do not grant `repo`."

### N5 — Repo-root SECURITY.md + CODEOWNERS (0.25d)

- Add `SECURITY.md` with responsible disclosure email + GPG key.
- Add `.github/CODEOWNERS` for sensitive paths.

### N6 — Secrets scanning (0.25d)

- Enable `gitleaks` action on every PR (we already use gitleaks downstream).

**Acceptance**: CI green with all security steps; SBOM published; signed images.

---

## 13) Wave O — Documentation, Examples, Onboarding

### O1 — README rewrite (1d)

- Top: 60-second Quick Start (uvx + GitHub token + 1 query).
- "What is this" + "Why anti-bias matters" (link to wiki).
- Install matrix per agent platform.
- Troubleshooting (token, system tools, NanoGPT).

### O2 — Example workflows (0.5d)

- `examples/01_find_hidden_python_libs.md` — agent prompt walkthrough.
- `examples/02_screen_then_assess.md` — multi-step MCP composition.
- `examples/03_compare_repos.md` — three-repo head-to-head.

### O3 — Wiki sync (0.5d)

- After Wave G–N completion, regen wiki with updated status, version, test counts.
- Add `architecture/v1-ga-decisions.md` summarizing this plan's outcomes.

### O4 — Migration guide v0.x → v1.0 (0.25d)

- Document any breaking changes (likely: `is_hidden_gem` removal from `ScoreResult` per T5.4 deprecation).

### O5 — CHANGELOG.md (0.25d)

- Generate from git log + this plan's Waves; conventional-commits style.

### O6 — Doctor command UX polish (0.5d)

- Rich table output with per-check pass/fail/warn + remediation hint.
- `--json` flag for agent consumption.
- Linked from every error path that suggests "run `ghdisc doctor` for diagnostics".

**Acceptance**: A new user reading README gets a working install in ≤ 5 min on a clean machine.

---

## 14) Test Plan

### 14.1 Test categories

| Category | Tooling | Where |
|----------|---------|-------|
| Unit | pytest + pytest-asyncio + respx | `tests/unit/` (existing 1670) |
| Integration | pytest + pytest-httpx | `tests/integration/` (new for some) |
| MCP transport | FastMCP test client | `tests/mcp/` (extend) |
| Property-based | hypothesis | `tests/property/` (extend with INV) |
| Invariants | pytest mark | `tests/invariants/` (new) |
| Golden / Benchmark | custom runner | `tests/golden/`, `reports/` |
| E2E install | shell scripts | `scripts/smoke_*.sh` |
| Security | bandit, semgrep, pip-audit, osv | CI step |
| Mutation (selective) | mutmut | local + pre-release |

### 14.2 New tests required

- `tests/invariants/test_anti_bias_contract.py` — 10 INV checks (Wave G)
- `tests/integration/test_full_pipeline_fresh_container.py` — pipeline on missing tools (Wave I)
- `tests/integration/test_osv_batch.py` — batch query mocked (Wave I)
- `tests/integration/test_clone_reuse.py` — Gate 2 + Gate 3 share clone (Wave I)
- `tests/mcp/test_streamable_http.py` — HTTP transport (Wave J)
- `tests/mcp/test_health_endpoint.py` — `/health` (Wave J)
- `tests/mcp/test_auth_middleware.py` — bearer-token enforcement (Wave J)
- `tests/mcp/test_token_budget.py` — every tool ≤ 2K tokens (Wave J)
- `tests/cli/test_benchmark_runner.py` — golden runner (Wave G)
- `tests/discovery/test_recency_boost.py` — Wave H
- `tests/discovery/test_curated_resilience.py` — Wave H
- `tests/discovery/test_registry_adapters.py` — crates + Maven (Wave H)

### 14.3 CI changes

- Add jobs: `golden-smoke`, `e2e-install-matrix`, `security`, `image-build`, `release-dryrun`.
- Required for merge: ruff, mypy strict, pytest unit, pytest invariants, golden-smoke, security.
- Required for release: all of above + image-build + e2e-install-matrix.

### 14.4 Coverage targets

- Line coverage ≥ 88% (from current ~85%).
- Branch coverage ≥ 78%.
- Mutation kill rate on `_check_hard_gate` ≥ 95%.

---

## 15) Acceptance Criteria — v1.0.0 GA

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | All 10 anti-bias contract invariants pass | `pytest -m invariant` |
| 2 | Spearman ρ ≥ 0.65 on golden dataset | `ghdisc benchmark run` report |
| 3 | Hidden-gem recall@25 ≥ 0.6 on golden dataset | benchmark report |
| 4 | Domain classifier F1 macro ≥ 0.70 | benchmark report |
| 5 | `uvx github-discovery mcp serve --transport stdio` works on fresh `python:3.13-slim` | CI `e2e-install` job |
| 6 | `docker run ghcr.io/<org>/github-discovery:latest doctor` exit 0 | CI `image-build` |
| 7 | All 4 agent platforms (Claude Code, Kilo Code, OpenCode, Claude Desktop) load + invoke 1 tool successfully | `scripts/smoke_*.sh` nightly |
| 8 | Kilo Marketplace PR open and accepted | manual |
| 9 | `/health` returns 200 in HTTP transport; deep mode runs doctor | CI |
| 10 | Auth middleware rejects requests without bearer key when `GHDISC_MCP_API_KEYS` set | CI |
| 11 | Pipeline runs end-to-end on container without `gitleaks`/`scc` — produces honest `degraded` flag | CI integration test |
| 12 | OSV batch query active; P95 ≤ 6s on 100-dep monorepo | benchmark |
| 13 | Clone reuse: Gate 2+3 share a single shallow clone | integration test |
| 14 | Repomix tokens within ±2% of budget on tier-aware sampling | unit test |
| 15 | Every MCP tool returns ≤ 2K tokens default | CI |
| 16 | OpenTelemetry traces emit when `OTEL_EXPORTER_OTLP_ENDPOINT` set | manual e2e |
| 17 | `pip-audit` + `osv-scanner` + `bandit` + `semgrep` clean (no HIGH+) | CI |
| 18 | SBOM published with release; container image cosign-signed | release artifacts |
| 19 | Test count ≥ 1670 (no regression); coverage ≥ 88% line | `make ci` |
| 20 | mypy `--strict` clean; ruff clean; ruff-format clean | `make ci` |
| 21 | README "Quick Start in 60 seconds" path works fresh | manual user test |
| 22 | Migration guide published in CHANGELOG.md | repo |

---

## 16) Rollback & Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Golden dataset labeling drift between Claude/Gemini/ChatGPT | Med | Med | Cohen's kappa ≥ 0.6 gate; human adjudication |
| Anti-bias claim measurably weaker than narrative on real data | Med | High | Wave G runs first; ship `degraded` flag honestly; tune weights via G3 calibration before claiming GA |
| Docker image bloat from bundled tools | Med | Low | Multi-stage, distroless base, only essential binaries |
| FastMCP stateless mode breaks in-process session continuity | Low | Med | Default stateful; opt-in only; document `session_id` requirement |
| OAuth 2.1 not needed for v1.0 (most users on stdio) | Low | Low | API-key-only acceptable for GA; OAuth in v1.1 |
| OSV batch returns >32 MiB | Low | Low | Auto-split; HTTP/2 fallback |
| Clone reuse race conditions | Med | Med | Refcount + lock file; orphan cleanup; integration test |
| MCP tool token blow-up regression (> 2K) | Med | Med | CI gate per-tool |
| GitHub API quota exhaustion in CI | Med | Med | Use `GITHUB_TOKEN` from secrets; cache responses in tests via respx |
| Marketplace PR rejection | Low | Low | Follow `marketplace-deployment.md` spec exactly; iterate |

**Rollback plan per Wave**: Each Wave is git-tagged on completion (`wave-G-done`, etc.). On regression, revert to previous tag and re-run `make ci`. The plan reaches `v1.0.0` only when all green simultaneously.

---

## 17) Context7 + Wiki Cross-References

Every implementation task in Waves G–O MUST verify the relevant API via Context7 BEFORE writing code (per CLAUDE.md). Mandatory queries:

| Library | Library ID | Verify |
|---------|-----------|--------|
| FastMCP | `/prefecthq/fastmcp` | http_app, stateless_http, custom_route, lifespan, tool decorator |
| MCP SDK | `/modelcontextprotocol/python-sdk` | transport modes, json_response, progress notifications |
| repomix | `/andersonby/python-repomix` | RepomixConfig.compression, include patterns, encoding, `RepoProcessor(repo_url=local_path)` |
| instructor | `/websites/python_useinstructor` | Mode enum, max_retries, async, response_model |
| openai | `/openai/openai-python` | AsyncOpenAI, base_url, custom client, close lifecycle |
| pydantic | `/websites/pydantic_dev_validation` | computed_field, ConfigDict, field_validator |
| pydantic-settings | `/pydantic/pydantic-settings` | SettingsConfigDict, extra='ignore', env_nested_delimiter |
| httpx | `/encode/httpx` | AsyncClient, timeouts, retries via tenacity, HTTP/2 |
| tenacity | `/jd/tenacity` | retry_if_exception_type, wait_random_exponential, stop_after_attempt |
| structlog | `/hynek/structlog` | processors, OTel integration, sampling |
| hypothesis | `/HypothesisWorks/hypothesis` | composite strategies, settings(deadline=) |
| typer + rich | `/tiangolo/typer`, `/Textualize/rich` | command groups, table rendering |
| aiosqlite | `/omnilib/aiosqlite` | connection pooling, transactions |

Wiki pages MUST be updated as implementation lands (per CLAUDE.md). The relevant pages and what they capture:

- `architecture/phase3-production-readiness.md` → extend with Wave G results
- `architecture/v1-ga-decisions.md` (new, Wave O) → final decision log
- `domain/discovery-channels.md` → Wave H: recency boost, registry adapters, dependents
- `domain/screening-gates.md` → Wave I: tool provider, clone reuse, OSV batch
- `patterns/phase4-assessment-implementation.md` → Wave I: tier-aware sampling, model fallback chain
- `patterns/phase7-mcp-plan.md` → Wave J: HTTP transport, auth, health, metrics
- `patterns/marketplace-deployment.md` → Wave L: validated install matrix
- `apis/agent-integration.md` → Wave L: refresh configs to UVX-based
- `patterns/operational-rules.md` → Wave M: OTel + metrics conventions

---

## 18) Out of Scope (deferred to v1.1+)

- OAuth 2.1 + OIDC Discovery (Nov-2025 spec) — API-key in v1.0
- Redis session backend — SQLite only in v1.0
- Multi-tenant MCP server (one user per process)
- ML-based domain classifier (keyword + topic heuristic in v1.0)
- LLM-based seed expansion (`SeedExpansion` stays heuristic)
- RAG over packed content (repomix-only in v1.0)
- Web UI / dashboard
- Cross-domain ranking with normalization (warning-only stays)
- Custom prompt templates per user (built-in 8 dimensions only)
- Multi-language LLM evaluation (English only)
- gRPC transport (stdio + streamable-http only)

---

## Sources cross-checked

- Existing wiki entries: index.md, architecture (anti-star-bias, phase3-production-readiness, mcp-native-design), domain (discovery-channels, screening-gates, scoring-dimensions), patterns (operational-rules, phase4/5/7/8/9/10, marketplace-deployment, env-isolation-resilience), apis (mcp-tools, agent-integration)
- Existing plans: `discovery_production_ready_plan_1.md`, phase 0–9 implementation plans, fase2_plan
- Code: `src/github_discovery/{discovery,screening,assessment,scoring,mcp,cli}/**`, `pyproject.toml`, `.mcp.json`, `.kilo/mcp.json`
- Web/Context7 research:
  - FastMCP HTTP/stateless/health from gofastmcp.com (Context7 `/prefecthq/fastmcp`)
  - Repomix RepoProcessor + RepomixConfig from python-repomix (Context7 `/andersonby/python-repomix`)
  - OpenSSF Scorecard API (api.securityscorecards.dev), OSV `/v1/querybatch` SLOs (P50≤500ms, P95≤6s)
  - GitHub stars bias: arXiv 2412.13459 "Six Million Suspected Fake Stars" — corroborates anti-bias rationale
  - UVX MCP distribution (Astral docs + Azure MCP Python support)
  - OpenTelemetry MCP instrumentation (signoz, oneuptime guides)
  - Repomix chunking strategies + tree-sitter compression (~70% token reduction)
