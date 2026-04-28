# Calibration Report — Wave 4 (Phase 2)

Status: **Pending external labeling completion**
Date: 2026-04-26

## Scope

This report tracks T4.2/T4.3 outcomes from `docs/plans/fase2_plan.md`:

- Inter-rater agreement (Cohen's κ pairwise, Fleiss' κ multi-rater)
- Calibration of domain profile weights against expert ratings
- Hold-out validation (NDCG@10 target ≥ 0.75)

## Blocking Dependencies

1. `tests/feasibility/golden_dataset.json` with 200 labeled repositories (T4.1)
2. 3 rater evaluations per repository according to `docs/foundation/labeling_guidelines.md`

## Required Outputs

### 1) Inter-rater Agreement (T4.2)

- Pairwise Cohen's κ table
- Fleiss' κ global table
- Disagreement analysis and guideline refinement notes

### 2) Weight Calibration (T4.3)

- Baseline profile weights (pre-calibration)
- Calibrated weights per domain
- Objective metrics (Spearman vs expert ranking)
- Hold-out NDCG@10/NDCG@25

## Reproducibility Notes

All computations must be generated from versioned inputs:

- Dataset commit SHA
- Calibration script commit SHA
- Configuration snapshot (search space, seed, split strategy)

---

This file is intentionally committed as a structured placeholder to keep
Phase 2 deliverables explicit and auditable while external labeling is in progress.
