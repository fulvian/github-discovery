"""Tests for Wave 4 report generation helpers."""

from __future__ import annotations

import json
from pathlib import Path

from github_discovery.feasibility.report_generation import (
    BenchmarkSummary,
    CalibrationSummary,
    generate_wave4_reports,
    render_benchmark_report,
    render_calibration_report,
)


def test_render_calibration_report_contains_metrics() -> None:
    summary = CalibrationSummary(
        dataset_size=200,
        min_raters_per_repo=3,
        cohen_kappa_pairwise={"r1-r2": 0.7, "r1-r3": 0.65},
        fleiss_kappa=0.68,
        ndcg_at_10=0.77,
        ndcg_at_25=0.75,
        spearman=0.62,
        notes=["stable labels"],
    )

    content = render_calibration_report(summary)
    assert "Calibration Report" in content
    assert "0.680" in content
    assert "0.770" in content
    assert "stable labels" in content


def test_render_benchmark_report_contains_significance() -> None:
    summary = BenchmarkSummary.model_validate(
        {
            "methods": [
                {
                    "name": "github-discovery",
                    "ndcg_at_10": 0.80,
                    "ndcg_at_25": 0.78,
                    "spearman": 0.60,
                    "pairwise_accuracy": 0.70,
                },
                {
                    "name": "star-only",
                    "ndcg_at_10": 0.60,
                    "ndcg_at_25": 0.58,
                    "spearman": 0.30,
                    "pairwise_accuracy": 0.52,
                },
            ],
            "baseline_name": "star-only",
            "wilcoxon_p_value_vs_baseline": 0.01,
            "notes": ["significant improvement"],
        },
    )

    content = render_benchmark_report(summary)
    assert "Benchmark Report" in content
    assert "star-only" in content
    assert "0.0100" in content
    assert "yes" in content


def test_generate_wave4_reports_writes_markdown_files(tmp_path: Path) -> None:
    calibration_json = tmp_path / "calibration.json"
    benchmark_json = tmp_path / "benchmark.json"
    calibration_md = tmp_path / "calibration_report.md"
    benchmark_md = tmp_path / "benchmark_report.md"

    calibration_json.write_text(
        json.dumps(
            {
                "dataset_size": 200,
                "min_raters_per_repo": 3,
                "cohen_kappa_pairwise": {"r1-r2": 0.7},
                "fleiss_kappa": 0.66,
                "ndcg_at_10": 0.76,
                "ndcg_at_25": 0.74,
                "spearman": 0.61,
                "notes": ["ok"],
            },
        ),
        encoding="utf-8",
    )
    benchmark_json.write_text(
        json.dumps(
            {
                "methods": [
                    {
                        "name": "github-discovery",
                        "ndcg_at_10": 0.80,
                        "ndcg_at_25": 0.78,
                        "spearman": 0.60,
                        "pairwise_accuracy": 0.70,
                    },
                    {
                        "name": "star-only",
                        "ndcg_at_10": 0.59,
                        "ndcg_at_25": 0.57,
                        "spearman": 0.28,
                        "pairwise_accuracy": 0.51,
                    },
                ],
                "baseline_name": "star-only",
                "wilcoxon_p_value_vs_baseline": 0.02,
                "notes": ["ok"],
            },
        ),
        encoding="utf-8",
    )

    generate_wave4_reports(
        calibration_json=calibration_json,
        benchmark_json=benchmark_json,
        calibration_report_md=calibration_md,
        benchmark_report_md=benchmark_md,
    )

    assert calibration_md.exists()
    assert benchmark_md.exists()
    assert "Calibration Report" in calibration_md.read_text(encoding="utf-8")
    assert "Benchmark Report" in benchmark_md.read_text(encoding="utf-8")
