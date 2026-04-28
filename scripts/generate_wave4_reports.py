"""Generate Wave 4 markdown reports from JSON metric inputs.

Usage:
    .venv/bin/python scripts/generate_wave4_reports.py \
      --calibration-json path/to/calibration_summary.json \
      --benchmark-json path/to/benchmark_summary.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from github_discovery.feasibility.report_generation import generate_wave4_reports


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration-json", type=Path, required=True)
    parser.add_argument("--benchmark-json", type=Path, required=True)
    parser.add_argument(
        "--calibration-report",
        type=Path,
        default=Path("docs/foundation/calibration_report.md"),
    )
    parser.add_argument(
        "--benchmark-report",
        type=Path,
        default=Path("docs/foundation/benchmark_report.md"),
    )
    args = parser.parse_args()

    generate_wave4_reports(
        calibration_json=args.calibration_json,
        benchmark_json=args.benchmark_json,
        calibration_report_md=args.calibration_report,
        benchmark_report_md=args.benchmark_report,
    )


if __name__ == "__main__":
    main()
