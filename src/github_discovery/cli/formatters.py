"""CLI output formatters — JSON, Table (Rich), Markdown, YAML-like."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from rich.console import Console
from rich.table import Table

from github_discovery.cli.app import cli_state


def format_output(
    data: Any,
    fmt: str,
    output_type: str,
) -> str:
    """Format data for CLI output.

    Args:
        data: Data to format (Pydantic model, dict, or list).
        fmt: Output format (json, table, markdown, yaml).
        output_type: Type hint for table builders (discovery, screening,
            assessment, ranking, session, session_list, export).

    Returns:
        Formatted string for console output.
    """
    normalized = _normalize_data(data)

    if fmt == "json":
        return _format_json(normalized)
    if fmt == "table":
        return _format_table(normalized, output_type)
    if fmt == "markdown":
        return _format_markdown(normalized, output_type)
    if fmt == "yaml":
        return _format_yaml(normalized)
    msg = f"Unknown output format: {fmt}"
    raise ValueError(msg)


def _normalize_data(data: Any) -> dict[str, Any] | list[Any]:
    """Convert Pydantic models or other data to dicts."""
    if hasattr(data, "model_dump"):
        return data.model_dump(mode="json")  # type: ignore[no-any-return]
    if isinstance(data, list):
        return [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in data
        ]
    return data  # type: ignore[no-any-return]


def _format_json(data: Any) -> str:
    """Format as indented JSON."""
    return json.dumps(data, indent=2, default=str)


def _format_table(data: Any, output_type: str) -> str:
    """Format as Rich Table rendered to string."""
    buf = io.StringIO()
    console = Console(file=buf, no_color=cli_state.no_color, width=120)

    table_builders: dict[str, Any] = {
        "discovery": _build_discovery_table,
        "screening": _build_screening_table,
        "assessment": _build_assessment_table,
        "ranking": _build_ranking_table,
        "session": _build_session_table,
        "session_list": _build_session_list_table,
    }

    builder = table_builders.get(output_type, _build_generic_table)
    table = builder(data)
    console.print(table)

    return buf.getvalue()


def _build_ranking_table(data: dict[str, Any] | list[Any]) -> Table:
    """Build Rich Table for ranking results."""
    table = Table(title="Repository Ranking", show_lines=True)
    table.add_column("#", style="bold cyan", width=4)
    table.add_column("Repository", style="bold", width=40)
    table.add_column("Value Score", style="green", width=12)
    table.add_column("Quality", width=10)
    table.add_column("Stars", justify="right", width=8)
    table.add_column("Domain", width=12)
    table.add_column("Gem", width=6)

    repos = data if isinstance(data, list) else data.get("ranked_repos", data.get("repos", []))
    for i, repo in enumerate(repos, 1):
        is_gem = repo.get("is_hidden_gem", False)
        gem_marker = "💎" if is_gem else ""
        table.add_row(
            str(i),
            str(repo.get("full_name", repo.get("repo", ""))),
            f"{repo.get('value_score', 0.0):.3f}",
            f"{repo.get('quality_score', repo.get('overall_score', 0.0)):.2f}",
            str(repo.get("stars", 0)),
            str(repo.get("domain", "")),
            gem_marker,
        )
    return table


def _build_discovery_table(data: dict[str, Any] | list[Any]) -> Table:
    """Build Rich Table for discovery results."""
    table = Table(title="Discovered Candidates", show_lines=True)
    table.add_column("#", style="bold cyan", width=4)
    table.add_column("Repository", style="bold", width=40)
    table.add_column("Score", width=8)
    table.add_column("Language", width=12)
    table.add_column("Stars", justify="right", width=8)
    table.add_column("Channel", width=12)

    candidates = data.get("candidates", data) if isinstance(data, dict) else data
    if isinstance(candidates, list):
        for i, c in enumerate(candidates[:50], 1):
            table.add_row(
                str(i),
                str(c.get("full_name", "")),
                f"{c.get('discovery_score', 0.0):.2f}",
                str(c.get("language", "")),
                str(c.get("stars", 0)),
                str(c.get("source_channel", "")),
            )
    return table


def _build_screening_table(data: dict[str, Any] | list[Any]) -> Table:
    """Build Rich Table for screening results."""
    table = Table(title="Screening Results", show_lines=True)
    table.add_column("Repository", style="bold", width=40)
    table.add_column("Gate 1", width=10)
    table.add_column("Gate 1 Score", width=12)
    table.add_column("Gate 2", width=10)
    table.add_column("Gate 2 Score", width=12)
    table.add_column("Pass", width=8)

    results = data if isinstance(data, list) else data.get("results", [])
    if isinstance(results, list):
        for r in results:
            gate1_pass = "✅" if r.get("gate1_passed", False) else "❌"
            gate2_pass = "✅" if r.get("gate2_passed", False) else "❌"
            overall_pass = "✅" if r.get("can_proceed_to_gate3", False) else "❌"
            table.add_row(
                str(r.get("full_name", "")),
                gate1_pass,
                f"{r.get('gate1_score', 0.0):.2f}",
                gate2_pass,
                f"{r.get('gate2_score', 0.0):.2f}",
                overall_pass,
            )
    return table


def _build_assessment_table(data: dict[str, Any] | list[Any]) -> Table:
    """Build Rich Table for deep assessment results."""
    table = Table(title="Deep Assessment Results", show_lines=True)
    table.add_column("#", style="bold cyan", width=4)
    table.add_column("Repository", style="bold", width=35)
    table.add_column("Overall", width=10)
    table.add_column("Confidence", width=10)
    table.add_column("Gate 3", width=8)
    table.add_column("Top Dim", width=15)
    table.add_column("Weak Dim", width=15)

    results = data if isinstance(data, list) else data.get("results", [])
    if isinstance(results, list):
        for i, r in enumerate(results, 1):
            dimensions = r.get("dimension_scores", [])
            top_dim = (
                max(dimensions, key=lambda d: d.get("score", 0))["dimension"] if dimensions else ""
            )
            weak_dim = (
                min(dimensions, key=lambda d: d.get("score", 0))["dimension"] if dimensions else ""
            )
            gate3 = "✅" if r.get("passed", True) else "❌"
            table.add_row(
                str(i),
                str(r.get("full_name", "")),
                f"{r.get('overall_score', 0.0):.2f}",
                f"{r.get('confidence', 0.0):.2f}",
                gate3,
                str(top_dim),
                str(weak_dim),
            )
    return table


def _build_session_table(data: dict[str, Any] | list[Any]) -> Table:
    """Build Rich Table for session details."""
    table = Table(title="Session Details", show_lines=False)
    table.add_column("Property", style="bold cyan", width=20)
    table.add_column("Value", width=60)
    if isinstance(data, dict):
        table.add_row("Session ID", str(data.get("session_id", "")))
        table.add_row("Name", str(data.get("name", "")))
        table.add_row("Status", str(data.get("status", "")))
        table.add_row("Discovered", str(data.get("discovered_repo_count", 0)))
        table.add_row("Screened", str(data.get("screened_repo_count", 0)))
        table.add_row("Assessed", str(data.get("assessed_repo_count", 0)))
        table.add_row("Created", str(data.get("created_at", "")))
    return table


def _build_session_list_table(data: dict[str, Any] | list[Any]) -> Table:
    """Build Rich Table for session list."""
    table = Table(title="Sessions", show_lines=True)
    table.add_column("Session ID", style="bold", width=36)
    table.add_column("Name", width=20)
    table.add_column("Status", width=12)
    table.add_column("Discovered", justify="right", width=12)
    table.add_column("Screened", justify="right", width=10)
    table.add_column("Assessed", justify="right", width=10)
    table.add_column("Created", width=20)

    sessions: list[Any] = data if isinstance(data, list) else data.get("sessions", [])
    for s in sessions:
        table.add_row(
            str(s.get("session_id", "")),
            str(s.get("name", "")),
            str(s.get("status", "")),
            str(s.get("discovered_repo_count", 0)),
            str(s.get("screened_repo_count", 0)),
            str(s.get("assessed_repo_count", 0)),
            str(s.get("created_at", "")),
        )
    return table


def _build_generic_table(data: Any) -> Table:
    """Fallback table builder for unknown data types."""
    table = Table(title="Results")
    if isinstance(data, dict):
        for key in data:
            table.add_column(str(key))
        table.add_row(*[str(v) for v in data.values()])
    return table


def _format_markdown(data: Any, output_type: str) -> str:
    """Format as Markdown table or document."""
    lines: list[str] = []
    if isinstance(data, dict):
        lines.append(f"# {output_type.replace('_', ' ').title()}")
        lines.append("")
        for key, value in data.items():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                headers = list(value[0].keys())
                lines.append(f"## {key}")
                lines.append("")
                lines.append("| " + " | ".join(str(h) for h in headers) + " |")
                lines.append("| " + " | ".join("---" for _ in headers) + " |")
                for item in value:
                    lines.append(
                        "| " + " | ".join(str(item.get(h, "")) for h in headers) + " |",
                    )
                lines.append("")
            else:
                lines.append(f"- **{key}**: {value}")
    elif isinstance(data, list):
        lines.append(f"# {output_type.replace('_', ' ').title()}")
        lines.append("")
        for item in data:
            if isinstance(item, dict):
                for k, v in item.items():
                    lines.append(f"- **{k}**: {v}")
                lines.append("")
    return "\n".join(lines)


def _format_yaml(data: Any) -> str:
    """Format as YAML-like output (no pyyaml dependency).

    Produces a simple indented output that looks like YAML
    but uses json.dumps for complex values.
    """
    return json.dumps(data, indent=2, default=str)


def format_csv(data: list[dict[str, Any]], columns: list[str] | None = None) -> str:
    """Format data as CSV.

    Args:
        data: List of dicts to format.
        columns: Optional column names. If None, uses keys from first item.

    Returns:
        CSV string with header row.
    """
    if not data:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=columns or list(data[0].keys()),
        extrasaction="ignore",
    )
    writer.writeheader()
    for row in data:
        writer.writerow(row)
    return output.getvalue()
