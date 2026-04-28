# Benchmark Report — Wave 4 (Phase 2)

Status: **Pending calibration dataset completion**
Date: 2026-04-26

## Scope

This report tracks T4.4 outcomes from `docs/plans/fase2_plan.md`.

Target comparison set:

1. Random ranking
2. Star-only ranking
3. OpenSSF Scorecard composite
4. GitHub trending order
5. GitHub Discovery pipeline (current)

## Metrics

- NDCG@10
- NDCG@25
- Spearman correlation vs expert ranking
- Pairwise accuracy
- Wilcoxon signed-rank significance (vs star-only baseline)

## Acceptance Target

- GitHub Discovery beats star-only baseline on NDCG@10 with `p < 0.05`.

## Blocking Dependencies

1. `tests/feasibility/golden_dataset.json` (200 labeled repos, T4.1)
2. Completed calibration outputs from `docs/foundation/calibration_report.md` (T4.2/T4.3)

## Reproducibility Checklist

- Fixed random seeds
- Frozen snapshot date for stars/trending
- Versioned benchmark scripts and command lines
- Raw metric outputs stored with run metadata

---

This file is intentionally committed as a structured placeholder so Wave 4
benchmarking remains explicit and ready to execute as soon as labeling closes.
