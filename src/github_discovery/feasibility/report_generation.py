"""Wave 4 report generation from structured metric JSON inputs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003

from pydantic import BaseModel, Field

_SIGNIFICANCE_ALPHA = 0.05


class CalibrationSummary(BaseModel):
    """Structured input used to render calibration_report.md."""

    dataset_size: int = Field(ge=1)
    min_raters_per_repo: int = Field(ge=1)
    cohen_kappa_pairwise: dict[str, float] = Field(default_factory=dict)
    fleiss_kappa: float = Field(ge=-1.0, le=1.0)
    ndcg_at_10: float | None = Field(default=None, ge=0.0, le=1.0)
    ndcg_at_25: float | None = Field(default=None, ge=0.0, le=1.0)
    spearman: float | None = Field(default=None, ge=-1.0, le=1.0)
    notes: list[str] = Field(default_factory=list)


class BenchmarkMethodMetrics(BaseModel):
    """Per-method benchmark metric row."""

    name: str = Field(min_length=1)
    ndcg_at_10: float = Field(ge=0.0, le=1.0)
    ndcg_at_25: float = Field(ge=0.0, le=1.0)
    spearman: float = Field(ge=-1.0, le=1.0)
    pairwise_accuracy: float = Field(ge=0.0, le=1.0)


class BenchmarkSummary(BaseModel):
    """Structured input used to render benchmark_report.md."""

    methods: list[BenchmarkMethodMetrics] = Field(min_length=2)
    baseline_name: str = Field(min_length=1, default="star-only")
    wilcoxon_p_value_vs_baseline: float = Field(ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)


def load_calibration_summary(path: Path) -> CalibrationSummary:
    """Load calibration summary JSON into validated model."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return CalibrationSummary.model_validate(payload)


def load_benchmark_summary(path: Path) -> BenchmarkSummary:
    """Load benchmark summary JSON into validated model."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return BenchmarkSummary.model_validate(payload)


def render_calibration_report(summary: CalibrationSummary) -> str:
    """Render markdown report body for calibration results."""
    generated = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%SZ")

    pairwise_rows = "\n".join(
        f"| {pair} | {kappa:.3f} |" for pair, kappa in sorted(summary.cohen_kappa_pairwise.items())
    )
    if pairwise_rows == "":
        pairwise_rows = "| n/a | n/a |"

    notes = "\n".join(f"- {note}" for note in summary.notes) or "- none"
    ndcg10 = "n/a" if summary.ndcg_at_10 is None else f"{summary.ndcg_at_10:.3f}"
    ndcg25 = "n/a" if summary.ndcg_at_25 is None else f"{summary.ndcg_at_25:.3f}"
    spearman = "n/a" if summary.spearman is None else f"{summary.spearman:.3f}"

    return (
        "# Calibration Report — Wave 4 (Phase 2)\n\n"
        f"Generated: {generated}\n\n"
        "## Dataset Summary\n\n"
        f"- Repositories labeled: **{summary.dataset_size}**\n"
        f"- Minimum raters per repo: **{summary.min_raters_per_repo}**\n\n"
        "## Inter-rater Agreement\n\n"
        "### Pairwise Cohen's κ\n\n"
        "| Pair | Cohen's κ |\n"
        "|------|------------|\n"
        f"{pairwise_rows}\n\n"
        "### Fleiss' κ\n\n"
        f"- Fleiss' κ: **{summary.fleiss_kappa:.3f}**\n\n"
        "## Calibration Quality Metrics\n\n"
        f"- NDCG@10: **{ndcg10}**\n"
        f"- NDCG@25: **{ndcg25}**\n"
        f"- Spearman vs expert ranking: **{spearman}**\n\n"
        "## Notes\n\n"
        f"{notes}\n"
    )


def render_benchmark_report(summary: BenchmarkSummary) -> str:
    """Render markdown report body for benchmark comparison."""
    generated = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%SZ")
    rows = "\n".join(
        (
            f"| {m.name} | {m.ndcg_at_10:.3f} | {m.ndcg_at_25:.3f} | "
            f"{m.spearman:.3f} | {m.pairwise_accuracy:.3f} |"
        )
        for m in summary.methods
    )
    notes = "\n".join(f"- {note}" for note in summary.notes) or "- none"
    significant = "yes" if summary.wilcoxon_p_value_vs_baseline < _SIGNIFICANCE_ALPHA else "no"

    return (
        "# Benchmark Report — Wave 4 (Phase 2)\n\n"
        f"Generated: {generated}\n\n"
        "## Method Comparison\n\n"
        "| Method | NDCG@10 | NDCG@25 | Spearman | Pairwise Accuracy |\n"
        "|--------|---------|---------|----------|-------------------|\n"
        f"{rows}\n\n"
        "## Significance vs Baseline\n\n"
        f"- Baseline: **{summary.baseline_name}**\n"
        f"- Wilcoxon p-value: **{summary.wilcoxon_p_value_vs_baseline:.4f}**\n"
        f"- Significant (p < {_SIGNIFICANCE_ALPHA:.2f}): **{significant}**\n\n"
        "## Notes\n\n"
        f"{notes}\n"
    )


def generate_wave4_reports(
    calibration_json: Path,
    benchmark_json: Path,
    calibration_report_md: Path,
    benchmark_report_md: Path,
) -> None:
    """Generate both Wave 4 report markdown files from JSON summaries."""
    calibration_summary = load_calibration_summary(calibration_json)
    benchmark_summary = load_benchmark_summary(benchmark_json)

    calibration_report_md.write_text(
        render_calibration_report(calibration_summary),
        encoding="utf-8",
    )
    benchmark_report_md.write_text(
        render_benchmark_report(benchmark_summary),
        encoding="utf-8",
    )
