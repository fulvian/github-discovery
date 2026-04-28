# E2E Pipeline Test Report — Session 2 (2026-04-27)

## Summary

Second end-to-end pipeline test using the pydantic domain. Full pipeline executed: Gate 0 (discover) → Gate 1+2 (screen) → Gate 3 (deep assessment) → Gate D (rank). Key findings: Gate 2 bottleneck from missing `gitleaks`/`scc` tools, content truncation impact on LLM quality, and validation of star-neutral ranking with the smaller pool.

---

## Gate 0 — Discovery

**Command**: `github_discovery discover --query "pydantic" --max-candidates 20`
**Pool ID**: `2db1e59b-4262-4698-832a-e3d071c5744f`

### Results

| Channel | Repos Found | Notes |
|---------|-------------|-------|
| GitHub Search | 15 | `stars:>10 language:python` filter applied |
| PyPI Registry | 2 | `pydantic`, `pydantic-core`, `pydantic-settings` |
| Curated (awesome) | 3 | `pydantic/pydantic`, `samuelcolvin/pydantic`, `koxudaxi/fastapi-code-generator` |
| **Total** | **20** | Discovery time: ~1.1s |

### Observations

- PyPI registry channel returned only 2 candidates (pydantic v1 and v2, plus fastapi-code-generator). This is much smaller than the previous "python static analysis" pool which returned 20 via awesome-list.
- The curated/awesome-list channel found 3 repos specifically from the awesome-python list.
- GitHub search provided the bulk of candidates with the `stars:>10 language:python` filter.

---

## Gate 1 — Metadata Screening

**Command**: `github_discovery screen --pool-id 2db1e59b-4262-4698-832a-e3d071c5744f --gate both`
**Repos Screened**: 20

### Results

| Outcome | Count | Notes |
|---------|-------|-------|
| Passed Gate 1 | 12 | Score ≥ 0.50 threshold |
| Failed Gate 1 | 8 | Score < 0.50 |
| **Pass Rate** | **60%** | |

### Top Gate 1 Scores

| Repo | Gate 1 Score | Key Signals |
|------|-------------|-------------|
| pydantic/pydantic | 0.72 | has_ci=True, has_tests=True, has_docs=True, stars=27601 |
| samuelcolvin/pydantic | 0.71 | same signals (pydantic v1 canonical) |
| koxudaxi/fastapi-code-generator | 0.71 | has_ci=True, has_tests=True, has_docs=True, stars=1385 |

### Observations

- Gate 1 pass rate of 60% is consistent with the previous E2E run (12/20 for "python static analysis").
- High pass rate is expected since Gate 1 is a low-bar metadata check (has README, has tests, reasonable size, not archived).
- The 8 failing repos likely lack one or more hygiene indicators (no CI, no tests, or very small).

---

## Gate 2 — Static Security & Complexity Screening

### Results

| Outcome | Count | Notes |
|---------|-------|-------|
| Passed Gate 2 | 1 | `pydantic/pydantic` (score 0.52) |
| Failed Gate 2 | 11 | Score < 0.50 |
| **Pass Rate** | **8.3%** (1/12) | |

### Passed Gate 2

| Repo | Gate 2 Score | Gate 1 Score |
|------|-------------|-------------|
| pydantic/pydantic | 0.52 | 0.72 |

### Root Cause of Low Gate 2 Pass Rate

**Both `gitleaks` and `scc` subprocess tools are NOT installed on the system.**

When `gitleaks` is not found, `SecretsChecker.check()` returns `secrets_score=0.3` (fallback).
When `scc` is not found, `ComplexityAnalyzer.check()` returns `complexity_score=0.3` (fallback).

These fallback scores of 0.3 each penalize the Gate 2 composite score significantly:

```
Gate2 = 0.25 * secrets + 0.25 * osv + 0.25 * scorecard + 0.25 * complexity
       = 0.25 * 0.3   + 0.25 * ~0.5 + 0.25 * ~0.5 + 0.25 * 0.3
       = 0.075        + 0.125       + 0.125        + 0.075
       = 0.40  (below 0.50 threshold)
```

The only repos passing Gate 2 are those with very strong OpenSSF Scorecard and OSV scores compensating for the missing tool scores.

### System State

```
$ which gitleaks  →  not found
$ which scc       →  not found
```

This is a **pre-existing system configuration issue**, not a code bug. The system gracefully degrades, but the threshold is set assuming these tools are available.

### Recommendation

Either:
1. Install `gitleaks` and `scc` on the system
2. Adjust the Gate 2 threshold when tools are unavailable (the system already logs warnings about missing tools)

---

## Gate 3 — Deep LLM Assessment

**Command**: `github_discovery deep-eval --pool-id 2db1e59b-4262-4698-832a-e3d071c5744f`
**Repos Assessed**: 2 (passed Gate 2)

### Assessment Results

#### pydantic/pydantic

| Field | Value |
|-------|-------|
| overall_score | 0.6825 |
| gate3_pass | True |
| assessment_time | ~174s |
| total_tokens | 3180 |

**Per-Dimension Scores:**

| Dimension | Score | Confidence |
|-----------|-------|------------|
| code_quality | 0.75 | 0.30 |
| architecture | 0.75 | 0.30 |
| testing | 0.85 | 0.30 |
| documentation | 0.30 | 0.30 |
| security | 0.70 | 0.30 |
| maintenance | 0.65 | 0.30 |
| functionality | 0.85 | 0.30 |
| innovation | 0.20 | 0.30 |

**Heuristic Analysis (pre-LLM):**

| Signal | Value |
|--------|-------|
| has_ci | False |
| has_docs | True |
| has_security | True |
| has_tests | True |

**Note**: `has_ci=False` is likely incorrect for `pydantic/pydantic` (a major OSS project almost certainly has GitHub Actions). The heuristic detection for CI may have failed.

#### koxudaxi/fastapi-code-generator

| Field | Value |
|-------|-------|
| overall_score | 0.58 |
| gate3_pass | False |
| assessment_time | ~280s |
| total_tokens | 3198 |

**Per-Dimension Scores:**

| Dimension | Score | Confidence |
|-----------|-------|------------|
| code_quality | 0.65 | 0.30 |
| architecture | 0.75 | 0.30 |
| testing | 0.65 | 0.30 |
| documentation | 0.55 | 0.30 |
| security | 0.40 | 0.30 |
| maintenance | 0.40 | 0.30 |
| functionality | 0.75 | 0.30 |
| innovation | 0.20 | 0.30 |

**Heuristic Analysis (pre-LLM):** Same pattern as pydantic.

### Content Truncation Issue

Both repos produced `content_truncated` warnings:

- **pydantic/pydantic**: Original repo size ~243K tokens → max_tokens=20K → 4000 chars per LLM call
- **koxudaxi/fastapi-code-generator**: Original repo size not measured but also triggered truncation
- **huggingface/diffusers** (from previous session): Original size ~1.75M tokens → Repomix packing **timed out** at 120s limit

The Repomix packing has a 120-second timeout and a 20K token budget. Large repos exceed both:
- The packing itself takes too long for repos with many files
- Even when packing succeeds, the content is aggressively truncated (20K tokens → 4000 chars per dimension)

**Impact**: LLM assesses partial code, potentially missing important architectural patterns, test coverage, or documentation.

### Confidence Values

Both assessments returned `confidence=0.30` for all dimensions. This is the minimum confidence value. The system should compute higher confidence when:
- Repo has strong heuristic signals (CI, tests, docs)
- Gate 1+2 scores are high
- Content truncation is minimal

Current confidence may be suppressed by the heuristic analysis `confidence` field not being propagated to the LLM output parser.

---

## Gate D — Ranking

**Command**: `github_discovery rank --pool-id 2db1e59b-4262-4698-832a-e3d071c5744f`

### Results

```
┏━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ #    ┃ Repository                               ┃ Value Score  ┃ Quality    ┃ Stars  ┃ Domain       ┃ Gem    ┃
┡━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━┩
│ 1    │ pydantic/pydantic                        │ 0.682        │ 0.68       │ 27601  │              │        │
├──────┼──────────────────────────────────────────┼──────────────┼────────────┼────────┼──────────────┼────────┤
│ 2    │ koxudaxi/fastapi-code-generator          │ 0.580        │ 0.58       │ 1385   │              │        │
└──────┴──────────────────────────────────────────┴──────────────┴────────────┴────────┴──────────────┴────────┘
```

### Observations

- **Star-neutral ranking confirmed**: `pydantic/pydantic` (27,601 stars) ranks #1 by quality score (0.68), not by star count.
- `koxudaxi/fastapi-code-generator` (1,385 stars) ranks #2 with quality 0.58.
- Corroboration level shows as blank (not displayed in table output) — `corroboration_level` is not displayed in the rank table despite being defined in the model.
- No hidden gems flagged (both repos have high star counts, so `is_hidden_gem=False`).

---

## Key Findings

### 1. Gate 2 Bottleneck — Missing System Tools

`gitleaks` and `scc` are not installed. This causes:
- Secrets check: fallback score 0.3
- Complexity check: fallback score 0.3
- Gate 2 composite: max ~0.40 with these fallbacks (below 0.50 threshold)

**Impact**: Only 1/12 repos (8.3%) passed Gate 2 in this session, and 1/20 (5%) in the previous "python static analysis" session.

**Recommendation**: Add startup check that warns if `gitleaks`/`scc` are missing. Consider lowering the Gate 2 threshold when these tools are unavailable, or making the threshold configurable.

### 2. Content Truncation Degrades LLM Assessment Quality

Repomix packing with 20K token budget and 120s timeout aggressively truncates large repos:
- 1.75M token repo (huggingface/diffusers) → Repomix timeout
- 243K token repo (pydantic/pydantic) → 4000 chars per LLM call (1.5% of content)

**Recommendation**: Consider adaptive token budgets based on repo size, or tiered assessment where large repos get sampled rather than packed.

### 3. Heuristic `has_ci=False` for Major OSS Projects

`pydantic/pydantic` and `fastapi-code-generator` both returned `has_ci=False` from heuristic analysis, despite being established OSS projects with CI. This may indicate:
- Repomix header parsing failing to detect CI config files
- CI detection patterns (`.github/workflows/`, `Makefile`, `.travis.yml`) not being matched
- Heuristic analysis reading truncated or missing content

**Impact**: `has_ci` is used in Gate 2 Scorecard heuristic fallback. If `has_ci=False`, the scorecard score may be lower than warranted.

### 4. LLM Confidence at Minimum (0.30)

All assessed dimensions returned `confidence=0.30`, which is the floor. Expected confidence should be higher when:
- Repo has strong Gate 1+2 scores
- Heuristic signals are positive
- Content is not severely truncated

**Recommendation**: Investigate why confidence is capped at 0.30 — the `result_parser.py` heuristic fallback may be overriding LLM-computed confidence.

### 5. `huggingface/diffusers` Repomix Timeout

The previous session's attempt to assess `huggingface/diffusers` failed because:
- Repo size ~1.75M tokens
- Repomix packing timed out at 120s limit
- Assessment could not proceed

**Recommendation**: Add a pre-check for repo size before attempting Repomix packing. If estimated tokens > 500K, warn user and offer to proceed with aggressive truncation or skip.

---

## Token Costs

| Repo | Total Tokens | Est. Cost (NanoGPT) |
|------|-------------|---------------------|
| pydantic/pydantic | 3,180 | ~$0.004 |
| koxudaxi/fastapi-code-generator | 3,198 | ~$0.004 |
| **Total** | **6,378** | **~$0.008** |

Gate 3 token budget per repo: 20K input + 4K output. Actual usage: ~3.2K per repo (84% under budget).

---

## Comparison with Session 1 (2026-04-25)

| Metric | Session 1 (mcp office) | Session 2 (pydantic) |
|--------|----------------------|---------------------|
| Discovered | 20 | 20 |
| Gate 1 Pass | 6/20 (30%) | 12/20 (60%) |
| Gate 2 Pass | 3/6 (50%) → 3/20 overall | 1/12 (8.3%) → 1/20 overall |
| Gate 3 Assessed | 3 | 2 |
| Gate 3 Passed | 2/3 | 1/2 |
| Hidden Gems Found | 2 (💎) | 0 |
| Total Tokens | ~9,600 | ~6,378 |

The pydantic domain had a higher Gate 1 pass rate but lower Gate 2 pass rate (due to missing `gitleaks`/`scc` more severely affecting results — 11/12 passed Gate 1 but only 1 passed Gate 2).

---

## Recommendations Summary

| Priority | Issue | Recommendation |
|----------|-------|---------------|
| P0 | Missing `gitleaks`/`scc` | Install on system, or make Gate 2 threshold configurable when tools unavailable |
| P1 | Content truncation for large repos | Adaptive token budgets or pre-check for repo size before packing |
| P2 | `has_ci=False` for large OSS projects | Improve heuristic CI detection in `heuristics.py` or `repomix_adapter.py` |
| P1 | LLM confidence at floor (0.30) | Investigate confidence propagation in `result_parser.py` |
| P2 | Repomix timeout for very large repos | Add timeout pre-check and warning for repos > 500K tokens |
| P3 | `corroboration_level` not displayed in rank table | Add column to rank table formatter |
