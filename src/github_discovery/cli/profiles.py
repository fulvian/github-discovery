"""CLI commands for profile management — T5.3.

Provides ``ghdisc profiles list``, ``ghdisc profiles show <domain>``,
and ``ghdisc profiles validate <path>`` commands.
"""

from __future__ import annotations

from typing import Annotated

import typer


def register(app: typer.Typer) -> None:  # noqa: PLR0915
    """Register profiles commands with the parent Typer app."""
    profiles_app = typer.Typer(
        name="profiles",
        help="Domain profile management commands",
        no_args_is_help=True,
    )
    app.add_typer(profiles_app, name="profiles")

    @profiles_app.command("list")
    def list_profiles() -> None:
        """List all registered domain profiles.

        Shows domain type, display name, and gate thresholds for each
        profile currently loaded (built-in + custom if configured).
        """
        from github_discovery.config import Settings
        from github_discovery.scoring.profiles import ProfileRegistry

        settings = Settings()
        registry = ProfileRegistry(
            custom_profiles_path=settings.scoring.custom_profiles_path or None,
        )

        typer.echo(f"{'Domain':<20} {'Display Name':<20} {'Gate1':>6} {'Gate2':>6}")
        typer.echo("-" * 56)
        for domain, profile in sorted(registry.all_profiles().items()):
            g1 = profile.gate_thresholds.get("gate1", 0.0)
            g2 = profile.gate_thresholds.get("gate2", 0.0)
            typer.echo(
                f"{domain.value:<20} {profile.display_name:<20} {g1:>6.2f} {g2:>6.2f}",
            )

    @profiles_app.command("show")
    def show_profile(
        domain: Annotated[
            str,
            typer.Argument(help="Domain type to show (e.g., library, cli, ml_lib)"),
        ],
    ) -> None:
        """Show detailed information for a specific domain profile.

        Displays dimension weights, gate thresholds, derivation map,
        and other profile properties.
        """
        from github_discovery.config import Settings
        from github_discovery.models.enums import DomainType
        from github_discovery.scoring.profiles import ProfileRegistry

        settings = Settings()
        registry = ProfileRegistry(
            custom_profiles_path=settings.scoring.custom_profiles_path or None,
        )

        # Case-insensitive domain matching
        try:
            domain_type = DomainType(domain.lower())
        except ValueError:
            valid = ", ".join(d.value for d in DomainType)
            typer.echo(f"Unknown domain type: {domain!r}", err=True)
            typer.echo(f"Valid types: {valid}", err=True)
            raise typer.Exit(code=1) from None

        profile = registry.get(domain_type)

        typer.echo(f"Domain:        {profile.domain_type.value}")
        typer.echo(f"Display Name:  {profile.display_name}")
        if profile.description:
            typer.echo(f"Description:   {profile.description}")
        typer.echo(f"Star Baseline: {profile.star_baseline}")
        typer.echo()
        typer.echo("Dimension Weights:")
        for dim, weight in profile.dimension_weights.items():
            bar = "█" * int(weight * 40)
            typer.echo(f"  {dim.value:<20} {weight:>5.2f}  {bar}")
        typer.echo()
        typer.echo("Gate Thresholds:")
        for gate, threshold in profile.gate_thresholds.items():
            typer.echo(f"  {gate:<10} {threshold:>5.2f}")
        if profile.derivation_map is not None:
            typer.echo()
            typer.echo("Custom Derivation Map:")
            for dim_name, mappings in profile.derivation_map.items():
                parts = ", ".join(f"{name}({w:.2f})" for name, w in mappings)
                typer.echo(f"  {dim_name:<20} {parts}")

    @profiles_app.command("validate")
    def validate_profile(
        path: Annotated[
            str,
            typer.Argument(help="Path to YAML or TOML profiles file to validate"),
        ],
    ) -> None:
        """Validate a custom profiles file without loading it.

        Checks that all profiles have valid domain types, dimension weights
        sum to ~1.0, gate thresholds are in range, and derivation maps
        reference known sub-scores.
        """
        from pathlib import Path

        from github_discovery.scoring.profiles import ProfileRegistry, validate_profile

        file_path = Path(path)
        if not file_path.exists():
            typer.echo(f"File not found: {file_path}", err=True)
            raise typer.Exit(code=1)

        registry = ProfileRegistry()
        suffix = file_path.suffix.lower()

        if suffix in (".yaml", ".yml"):
            count = registry.load_from_yaml(file_path)
        elif suffix == ".toml":
            count = registry.load_from_toml(file_path)
        else:
            typer.echo(
                f"Unsupported format: {suffix} (expected .yaml, .yml, or .toml)",
                err=True,
            )
            raise typer.Exit(code=1)

        if count == 0:
            typer.echo("No valid profiles found in file.", err=True)
            raise typer.Exit(code=1)

        # Validate each loaded profile
        errors = 0
        for domain, profile in registry.all_profiles().items():
            try:
                validate_profile(profile)
            except ValueError as e:
                typer.echo(f"  ❌ {domain.value}: {e}", err=True)
                errors += 1

        if errors > 0:
            typer.echo(f"\n{errors} profile(s) had validation errors.", err=True)
            raise typer.Exit(code=1)

        typer.echo(f"✓ {count} profile(s) validated successfully.")
