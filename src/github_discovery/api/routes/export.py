"""Export endpoints for session results."""

from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends

from github_discovery.api.deps import get_job_store
from github_discovery.models.api import ExportFormat, ExportRequest, ExportResponse
from github_discovery.workers.job_store import JobStore  # noqa: TC001

router = APIRouter(tags=["export"])


@router.post(
    "/export",
    response_model=ExportResponse,
    summary="Export session results",
    description="Export session results in JSON, CSV, or Markdown format.",
)
async def export_results(
    request: ExportRequest,
    job_store: JobStore = Depends(get_job_store),  # noqa: B008
) -> ExportResponse:
    """Export session results in the requested format."""
    # Look up completed jobs for this session
    jobs = await job_store.list_jobs(limit=100)

    # Filter to completed jobs
    completed_jobs = [j for j in jobs if j.status == "completed"]

    if not completed_jobs:
        return ExportResponse(
            format=request.format,
            total_repos=0,
            content=_format_empty(request.format),
        )

    # Format results based on requested format
    results_data: list[dict[str, object]] = [
        {"job_id": j.job_id, "type": j.job_type.value, "status": j.status.value}
        for j in completed_jobs
    ]

    if request.format == ExportFormat.JSON:
        content = json.dumps(results_data, indent=2)
    elif request.format == ExportFormat.CSV:
        content = _format_csv(results_data)
    else:
        content = _format_markdown(results_data)

    return ExportResponse(
        format=request.format,
        total_repos=len(results_data),
        content=content,
    )


def _format_csv(results: list[dict[str, object]]) -> str:
    """Format results as CSV.

    Args:
        results: List of row dictionaries to format.

    Returns:
        CSV string with headers and data rows.
    """
    if not results:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)
    return output.getvalue()


def _format_markdown(results: list[dict[str, object]]) -> str:
    """Format results as Markdown table.

    Args:
        results: List of row dictionaries to format.

    Returns:
        Markdown-formatted table string.
    """
    if not results:
        return "No results to export."
    headers = list(results[0].keys())
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in results:
        lines.append(
            "| " + " | ".join(str(row.get(h, "")) for h in headers) + " |",
        )
    return "\n".join(lines)


def _format_empty(fmt: ExportFormat) -> str:
    """Return empty content message for the given format.

    Args:
        fmt: The export format to generate empty content for.

    Returns:
        Format-appropriate empty content string.
    """
    if fmt == ExportFormat.CSV:
        return ""
    if fmt == ExportFormat.MARKDOWN:
        return "No results to export."
    return "[]"
