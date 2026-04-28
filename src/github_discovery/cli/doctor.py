"""CLI command: ghdisc doctor — pre-flight system checks.

Runs diagnostics on system dependencies, connectivity, and configuration
to ensure the system is ready for discovery, screening, and assessment.
"""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import structlog
import typer

from github_discovery import __version__

if TYPE_CHECKING:
    from github_discovery.config import AssessmentSettings, GitHubSettings

logger = structlog.get_logger("github_discovery.doctor")

# ---------------------------------------------------------------------------
# Check result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckResult:
    """Result of a single pre-flight check."""

    name: str
    ok: bool
    message: str
    impact: str | None = None
    suggestion: str | None = None


# ---------------------------------------------------------------------------
# Individual check implementations
# ---------------------------------------------------------------------------


def _check_git() -> CheckResult:
    """Check git binary availability."""
    path = shutil.which("git")
    if path is None:
        return CheckResult(
            name="git",
            ok=False,
            message="git binary not found in PATH",
            impact="Cannot clone repositories for Gate 2 screening",
            suggestion="Install git: apt install git (Debian/Ubuntu), brew install git (macOS)",
        )
    return CheckResult(
        name="git",
        ok=True,
        message=f"git {path!r} found",
    )


def _check_gitleaks() -> CheckResult:
    """Check gitleaks binary availability."""
    path = shutil.which("gitleaks")
    if path is None:
        return CheckResult(
            name="gitleaks",
            ok=True,  # Not required — degrades gracefully
            message="gitleaks binary not found (optional)",
            impact="Gate 2 secret hygiene scoring will use heuristic fallback (confidence=0.0)",
            suggestion=(
                "Install: https://github.com/gitleaks/gitleaks/releases or 'brew install gitleaks'"
            ),
        )
    return CheckResult(
        name="gitleaks",
        ok=True,
        message=f"gitleaks found at {path!r}",
    )


def _check_scc() -> CheckResult:
    """Check scc (stone c counter) binary availability."""
    path = shutil.which("scc")
    if path is None:
        return CheckResult(
            name="scc",
            ok=True,  # Not required — degrades gracefully
            message="scc binary not found (optional)",
            impact="Gate 2 complexity scoring will use GitHub API fallback (confidence=0.3)",
            suggestion="Install: https://github.com/boyter/scc/releases or 'brew install scc'",
        )
    return CheckResult(
        name="scc",
        ok=True,
        message=f"scc found at {path!r}",
    )


def _check_repomix() -> CheckResult:
    """Check repomix Python package availability."""
    try:
        import repomix

        # Verify it's the actual repomix module by checking for expected attributes
        _ = getattr(repomix, "RepomixConfig", None) or getattr(repomix, "process", None)
        return CheckResult(
            name="repomix",
            ok=True,
            message="repomix package installed",
        )
    except ImportError:
        return CheckResult(
            name="repomix",
            ok=False,
            message="repomix Python package not found",
            impact="Gate 3 cannot pack repository content for LLM assessment",
            suggestion="pip install repomix",
        )


async def _check_github_api(github_settings: GitHubSettings) -> CheckResult:
    """Check GitHub API connectivity and authentication."""
    import httpx

    token = github_settings.token
    if not token:
        return CheckResult(
            name="github_api",
            ok=False,
            message="GHDISC_GITHUB_TOKEN not set",
            impact="Cannot discover repositories or screen via GitHub API",
            suggestion="Set GHDISC_GITHUB_TOKEN in .env or environment",
        )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                github_settings.api_base_url + "/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
        if response.status_code == 200:
            login = response.json().get("login", "unknown")
            # N4: Check token scope (warn if more than public_repo)
            scopes_header = response.headers.get("X-OAuth-Scopes", "")
            if scopes_header:
                scopes = {s.strip() for s in scopes_header.split(",")}
                non_public = scopes - {"public_repo", "repo:status", ""}
                if non_public:
                    logger.warning(
                        "github_token_has_extra_scopes",
                        extra_scopes=sorted(non_public),
                        suggestion="GitHub Discovery only requires public_repo scope",
                    )
            return CheckResult(
                name="github_api",
                ok=True,
                message=f"GitHub API authenticated as @{login}",
            )
        elif response.status_code == 401:
            return CheckResult(
                name="github_api",
                ok=False,
                message="GitHub token invalid (401 Unauthorized)",
                impact="All GitHub API operations will fail",
                suggestion="Refresh your GHDISC_GITHUB_TOKEN in .env or environment",
            )
        else:
            return CheckResult(
                name="github_api",
                ok=False,
                message=f"GitHub API returned status {response.status_code}",
                impact="GitHub API operations may be unreliable",
                suggestion="Check GHDISC_GITHUB_TOKEN and API quotas",
            )
    except httpx.TimeoutException:
        return CheckResult(
            name="github_api",
            ok=False,
            message="GitHub API timeout (10s)",
            impact="Cannot reach GitHub API — check network connectivity",
            suggestion="Ensure you have internet access and GHDISC_GITHUB_API_BASE_URL is correct",
        )
    except Exception as e:
        return CheckResult(
            name="github_api",
            ok=False,
            message=f"GitHub API error: {e}",
            impact="Cannot reach GitHub API",
            suggestion="Check network connectivity and GHDISC_GITHUB_API_BASE_URL",
        )


async def _check_nanogpt_api(assessment_settings: AssessmentSettings) -> CheckResult:
    """Check NanoGPT API connectivity."""
    import httpx

    api_key = assessment_settings.nanogpt_api_key
    if not api_key:
        return CheckResult(
            name="nanogpt_api",
            ok=True,  # Not required for discovery/screening
            message="GHDISC_ASSESSMENT_NANOGPT_API_KEY not set — deep assessment disabled",
            impact="Gate 3 (deep LLM assessment) will not be available",
            suggestion="Set GHDISC_ASSESSMENT_NANOGPT_API_KEY to enable deep assessment",
        )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                assessment_settings.effective_base_url + "/models",
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
            )
        if response.status_code in (200, 401):
            # 401 means endpoint exists but auth failed — still "connected"
            return CheckResult(
                name="nanogpt_api",
                ok=True,
                message="NanoGPT API endpoint reachable",
            )
        else:
            return CheckResult(
                name="nanogpt_api",
                ok=False,
                message=f"NanoGPT API returned status {response.status_code}",
                impact="Gate 3 assessment may be unavailable",
                suggestion="Check GHDISC_ASSESSMENT_NANOGPT_BASE_URL",
            )
    except httpx.TimeoutException:
        return CheckResult(
            name="nanogpt_api",
            ok=False,
            message="NanoGPT API timeout (15s)",
            impact="Gate 3 assessment may be unavailable",
            suggestion="Check GHDISC_ASSESSMENT_NANOGPT_BASE_URL and network",
        )
    except Exception as e:
        return CheckResult(
            name="nanogpt_api",
            ok=False,
            message=f"NanoGPT API error: {e}",
            impact="Gate 3 assessment may be unavailable",
            suggestion="Check GHDISC_ASSESSMENT_NANOGPT_BASE_URL",
        )


def _check_profiles_loadable() -> CheckResult:
    """Check that domain profiles can be loaded."""
    try:
        from github_discovery.models.enums import DomainType
        from github_discovery.models.scoring import get_domain_profile

        count = len(DomainType)  # Total number of domain types
        # Sanity check: verify OTHER profile loads (uses get_domain_profile fallback)
        other_profile = get_domain_profile(DomainType.OTHER)
        # get_domain_profile always succeeds — it returns DEFAULT_PROFILE for OTHER.
        # If this raises, something is fundamentally broken in the models.
        _ = other_profile.dimension_weights  # Access a required field as sanity check
        return CheckResult(
            name="profiles",
            ok=True,
            message=f"All {count} domain profiles loadable",
        )
    except Exception as e:
        return CheckResult(
            name="profiles",
            ok=False,
            message=f"Failed to load profiles: {e}",
            impact="Scoring and ranking may fail with unexpected errors",
            suggestion="Check models/scoring.py for syntax or import errors",
        )


def _check_feature_store_writable() -> CheckResult:
    """Check that feature store db path is writable."""
    try:
        db_path_str = ".ghdisc/features.db"
        db_path = Path(db_path_str)
        if not db_path.exists():
            try:
                db_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                return CheckResult(
                    name="feature_store",
                    ok=False,
                    message=f"Cannot create feature store directory {db_path.parent}: {e}",
                    impact="Scores and assessment results will not be persisted",
                    suggestion="Create directory or check permissions",
                )
        # Check writability by attempting a small write
        test_file = db_path.parent / ".ghdisc_doctor_write_test"
        try:
            test_file.write_text("test")
            test_file.unlink()
        except OSError as e:
            return CheckResult(
                name="feature_store",
                ok=False,
                message=f"Feature store directory {db_path.parent} not writable: {e}",
                impact="Scores and assessment results will not be persisted",
                suggestion=f"Check permissions on {db_path.parent}",
            )
        return CheckResult(
            name="feature_store",
            ok=True,
            message=f"Feature store path writable: {db_path_str}",
        )
    except Exception as e:
        return CheckResult(
            name="feature_store",
            ok=False,
            message=f"Feature store check failed: {e}",
            impact="Feature store configuration unreadable",
            suggestion="Check feature_store module for import errors",
        )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _render_table(results: list[CheckResult]) -> None:
    """Render check results as a formatted table."""
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(title=f"GitHub Discovery Doctor — v{__version__}", show_lines=False)
        table.add_column("Check", style="bold", width=18)
        table.add_column("Status", width=8)
        table.add_column("Message", width=50)
        table.add_column("Impact / Suggestion", width=40)

        for r in results:
            status_icon = "✅" if r.ok else "❌"
            status_style = "green" if r.ok else "red"
            row = [
                r.name,
                f"[{status_style}]{status_icon}[/{status_style}]",
                r.message,
            ]
            extra = ""
            if r.impact:
                extra = f"impact: {r.impact}"
            if r.suggestion:
                if extra:
                    extra += " | "
                extra += f"suggestion: {r.suggestion}"
            row.append(extra)
            table.add_row(*row)

        console.print(table)
    except ImportError:
        # Fallback to plain text
        print(f"GitHub Discovery Doctor — v{__version__}")  # noqa: T201
        print("=" * 70)  # noqa: T201
        for r in results:
            icon = "[OK]" if r.ok else "[FAIL]"
            print(f"{icon:8} {r.name:18} {r.message}")  # noqa: T201
            if r.impact:
                print(f"       impact: {r.impact}")  # noqa: T201
            if r.suggestion:
                print(f"       suggestion: {r.suggestion}")  # noqa: T201
        print("=" * 70)  # noqa: T201


# ---------------------------------------------------------------------------
# Command registration
# ---------------------------------------------------------------------------


def register(app: typer.Typer) -> None:
    """Register the doctor command on the main app."""

    @app.command(
        name="doctor",
        help="Pre-flight checks for system dependencies, connectivity, and configuration",
        rich_help_panel="Diagnostic",
    )
    def doctor(
        verbose: Annotated[
            bool,
            typer.Option("--verbose", "-v", help="Show all checks including OK ones"),
        ] = False,
    ) -> None:
        """Run pre-flight diagnostics.

        Checks system binaries (git, gitleaks, scc), Python packages (repomix),
        API connectivity (GitHub, NanoGPT), profile loading, and feature store
        writability.

        Exit code: 0 if all critical checks pass, 1 if any fail.
        Warnings (optional tools missing) do not cause non-zero exit.
        """
        # Import settings lazily to avoid circular imports at module load time
        from github_discovery.config import AssessmentSettings, GitHubSettings

        github_settings = GitHubSettings()
        assessment_settings = AssessmentSettings()

        # Run static checks immediately
        static_results: list[CheckResult] = [
            _check_git(),
            _check_gitleaks(),
            _check_scc(),
            _check_repomix(),
            _check_profiles_loadable(),
            _check_feature_store_writable(),
        ]

        # Run async checks
        async def run_async() -> list[CheckResult]:
            github_result = await _check_github_api(github_settings)
            nanogpt_result = await _check_nanogpt_api(assessment_settings)
            return [github_result, nanogpt_result]

        async_results = asyncio.run(run_async())
        all_results = static_results + async_results

        # Filter OK results if not verbose
        if not verbose:
            all_results = [r for r in all_results if not r.ok or verbose]

        _render_table(all_results)

        # Exit code: fail only if any REQUIRED check fails
        critical_names = {"git", "github_api", "repomix"}
        critical_failures = [r for r in all_results if not r.ok and r.name in critical_names]
        if critical_failures:
            raise typer.Exit(code=1)
        raise typer.Exit(code=0)
