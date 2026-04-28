#!/usr/bin/env python3
"""Generate a markdown report from a discovery session.

Usage:
    .venv/bin/python scripts/generate_session_report.py --session-id <session_id>

Output:
    Writes a markdown report to stdout by default.
    Use --output to specify a file path.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure package is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datetime import UTC, datetime

from github_discovery.models.session import SessionStatus
from github_discovery.mcp.session import SessionManager


def format_datetime(dt: datetime | None) -> str:
    """Format a datetime for display."""
    if dt is None:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")


def format_timedelta(seconds: float | None) -> str:
    """Format a duration in seconds as human-readable."""
    if seconds is None:
        return "N/A"
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    hours = seconds / 3600
    return f"{hours:.1f}h"


def generate_report(session_id: str, manager: SessionManager) -> str:
    """Generate a markdown report for the given session."""
    import asyncio

    session = asyncio.run(manager.get(session_id))
    if session is None:
        return f"# Session Report: {session_id}\n\n**Error: Session not found**\n"

    # Calculate duration
    duration_seconds = None
    if session.created_at and session.updated_at:
        duration_seconds = (session.updated_at - session.created_at).total_seconds()

    lines = [
        f"# Discovery Session Report",
        f"",
        f"## Session: {session.name or session.session_id}",
        f"",
        f"**Session ID:** `{session.session_id}`",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Status | {session.status.value} |",
        f"| Created | {format_datetime(session.created_at)} |",
        f"| Updated | {format_datetime(session.updated_at)} |",
        f"| Duration | {format_timedelta(duration_seconds)} |",
        f"|",
        f"## Pipeline Progress",
        f"|",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Repositories Discovered | {session.discovered_repo_count} |",
        f"| Repositories Screened | {session.screened_repo_count} |",
        f"| Repositories Assessed | {session.assessed_repo_count} |",
        f"|",
        f"## Candidate Pools",
        f"|",
    ]

    if session.pool_ids:
        for pool_id in session.pool_ids:
            lines.append(f"- `{pool_id}`")
    else:
        lines.append("*No pools created in this session*")

    lines.append(f"|")
    lines.append(f"## Configuration Overrides")
    lines.append(f"|")
    lines.append(f"| Setting | Value |")
    lines.append(f"|---------|-------|")

    config = session.config
    if config.min_gate1_score is not None:
        lines.append(f"| min_gate1_score | {config.min_gate1_score} |")
    if config.min_gate2_score is not None:
        lines.append(f"| min_gate2_score | {config.min_gate2_score} |")
    if config.max_tokens_per_repo is not None:
        lines.append(f"| max_tokens_per_repo | {config.max_tokens_per_repo} |")

    if not any([
        config.min_gate1_score is not None,
        config.min_gate2_score is not None,
        config.max_tokens_per_repo is not None,
    ]):
        lines.append("*No configuration overrides (using defaults)*")

    lines.append(f"|")
    lines.append(f"## Error Information")
    lines.append(f"|")

    if session.error_message:
        lines.append(f"**Error:** {session.error_message}")
    else:
        lines.append("*No errors in this session*")

    lines.append(f"|")
    lines.append(f"---")
    lines.append(f"*Report generated at {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S %Z')}*")

    return "\n".join(lines)


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--session-id",
        type=str,
        required=True,
        help="Session ID to generate report for",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path(".ghdisc/sessions.db"),
        help="Path to sessions database (default: .ghdisc/sessions.db)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output file path (default: stdout)",
    )
    args = parser.parse_args()

    manager = SessionManager(db_path=str(args.db_path))

    # Check if database exists
    if not args.db_path.exists():
        print(f"# Error\n\nDatabase not found: {args.db_path}", file=sys.stderr)
        print(f"\nRun a discovery session first to create the database.", file=sys.stderr)
        sys.exit(1)

    report = generate_report(args.session_id, manager)

    if args.output:
        args.output.write_text(report)
        print(f"Report written to: {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
