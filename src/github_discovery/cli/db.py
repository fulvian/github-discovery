"""CLI commands for database maintenance — T3.5."""

from __future__ import annotations

from typing import Annotated

import typer


def register(app: typer.Typer) -> None:
    """Register db commands with the parent Typer app."""
    db_app = typer.Typer(
        name="db",
        help="Database maintenance commands",
        no_args_is_help=True,
    )
    app.add_typer(db_app, name="db")

    @db_app.command()
    def prune(
        dry_run: Annotated[
            bool,
            typer.Option("--dry-run", help="Count expired entries without deleting"),
        ] = False,
    ) -> None:
        """Remove expired entries from the feature store database.

        Prunes entries past their expires_at timestamp. Use --dry-run to
        see how many entries would be removed without actually removing them.
        """
        import asyncio

        from github_discovery.config import Settings
        from github_discovery.scoring.feature_store import FeatureStore

        settings = Settings()

        async def _prune() -> int:
            ttl = settings.scoring.feature_store_ttl_hours
            store = FeatureStore(
                db_path=".ghdisc/features.db",
                ttl_hours=ttl,
            )
            await store.initialize()
            try:
                return await store.prune_expired(dry_run=dry_run)
            finally:
                await store.close()

        count = asyncio.run(_prune())

        if dry_run:
            typer.echo(f"Would prune {count} expired entries.")
        else:
            typer.echo(f"Pruned {count} expired entries.")
