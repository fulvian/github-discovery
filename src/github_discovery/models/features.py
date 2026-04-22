"""Feature store models for caching computed repository features.

The feature store avoids expensive recomputation by caching results
per repo + commit SHA. Results are invalidated when a new commit
is detected (Blueprint §16.5: mandatory caching by commit SHA).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

from github_discovery.models.assessment import DeepAssessmentResult  # noqa: TC001
from github_discovery.models.enums import DomainType
from github_discovery.models.screening import (  # noqa: TC001
    MetadataScreenResult,
    StaticScreenResult,
)


class FeatureStoreKey(BaseModel):
    """Composite key for feature store lookups.

    Features are keyed by repo full name + commit SHA to enable:
    - Dedup: same repo at same SHA = same features
    - Invalidation: new commit SHA = features need recomputation
    - Cross-session reuse: any session can reuse cached features
    """

    full_name: str = Field(description="Repository full name (owner/repo)")
    commit_sha: str = Field(description="Git commit SHA for dedup")


class RepoFeatures(BaseModel):
    """Cached feature set for a repository at a specific commit.

    Stores the complete set of computed features for a repo at a
    given commit SHA. This includes all gate results and metadata.

    TTL is configurable (default 24 hours). Features are automatically
    invalidated when the commit SHA changes.
    """

    # --- Identity ---
    full_name: str = Field(description="Repository full name (owner/repo)")
    commit_sha: str = Field(description="Git commit SHA for dedup")
    domain: DomainType = Field(
        default=DomainType.OTHER,
        description="Inferred domain type",
    )

    # --- Gate Results (populated progressively) ---
    gate1_result: MetadataScreenResult | None = Field(
        default=None,
        description="Gate 1 metadata screening result (None = not yet screened)",
    )
    gate2_result: StaticScreenResult | None = Field(
        default=None,
        description="Gate 2 static/security screening result (None = not yet screened)",
    )
    gate3_result: DeepAssessmentResult | None = Field(
        default=None,
        description="Gate 3 deep assessment result (None = not yet assessed)",
    )

    # --- Metadata ---
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When features were last computed",
    )
    ttl_hours: int = Field(
        default=24,
        gt=0,
        description="Cache TTL in hours",
    )
    source_session_id: str | None = Field(
        default=None,
        description="Session that computed these features",
    )
    computation_version: str = Field(
        default="1.0",
        description="Version of computation logic (for cache invalidation on logic changes)",
    )

    @property
    def is_expired(self) -> bool:
        """Check if cached features have exceeded TTL."""
        expiry = self.computed_at + timedelta(hours=self.ttl_hours)
        return datetime.now(UTC) > expiry

    @property
    def highest_gate_completed(self) -> int:
        """Return the highest gate level with results (0 = none)."""
        if self.gate3_result is not None:
            return 3
        if self.gate2_result is not None:
            return 2
        if self.gate1_result is not None:
            return 1
        return 0

    @property
    def is_fully_assessed(self) -> bool:
        """Check if all gates have been completed."""
        return (
            self.gate1_result is not None
            and self.gate2_result is not None
            and self.gate3_result is not None
        )

    @property
    def store_key(self) -> FeatureStoreKey:
        """Get the cache key for this feature set."""
        return FeatureStoreKey(full_name=self.full_name, commit_sha=self.commit_sha)
