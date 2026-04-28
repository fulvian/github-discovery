"""Screening models for Gate 1 (metadata) and Gate 2 (static/security).

Gate 1 uses repository metadata from GitHub API — zero LLM cost.
Gate 2 uses automated tools on shallow clone — zero or low cost.

Both gates produce sub-scores (0.0-1.0) and composite pass/fail results.
Hard rule (Blueprint §16.5): no Gate 3 without Gate 1 + Gate 2 pass.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# --- Sub-Score Base Pattern ---


class SubScore(BaseModel):
    """Base pattern for all gate sub-scores.

    Every sub-score has a value in [0.0, 1.0], a weight for composite
    calculation, details explaining the score breakdown, and a confidence
    indicator for the quality of available data.
    """

    value: float = Field(ge=0.0, le=1.0, description="Score value 0.0-1.0")
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=10.0,
        description="Weight in composite calculation (0.0-10.0)",
    )
    details: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="Scoring breakdown details (JSON-compatible values only)",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Data quality confidence (1.0 = full API data, lower = heuristic)",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Human-readable scoring notes",
    )


# --- Gate 1: Metadata Screening Sub-Scores ---


class HygieneScore(SubScore):
    """Repository hygiene file presence and quality.

    Checks: LICENSE (SPDX valid), CONTRIBUTING.md, CODE_OF_CONDUCT.md,
    SECURITY.md, CHANGELOG.md, README.md (with content minimum).
    """

    details: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description=(
            "Files found: {license, contributing, code_of_conduct, security, changelog, readme}"
        ),
    )


class MaintenanceScore(SubScore):
    """Maintenance signals from commit history and activity.

    Checks: commit recency, commit cadence, bus factor proxy,
    issue resolution rate.
    """

    details: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description=(
            "Signals: {last_commit_days_ago, commit_cadence, bus_factor, issue_resolution_rate}"
        ),
    )


class ReleaseDisciplineScore(SubScore):
    """Release discipline and versioning practices.

    Checks: semver tagging, release cadence, changelog per release,
    release notes quality.
    """

    details: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description=(
            "Signals: {has_semver_tags, release_count, "
            "release_cadence_days, has_changelog_per_release}"
        ),
    )


class ReviewPracticeScore(SubScore):
    """Code review practices and PR management.

    Checks: PR template, review presence, label usage,
    response latency proxy.
    """

    details: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="Signals: {has_pr_template, review_rate, label_usage, avg_response_hours}",
    )


class TestFootprintScore(SubScore):
    """Test infrastructure presence and coverage indicators.

    Checks: test directories/pattern presence, test config files
    (pytest.ini, conftest.py, setup.cfg test section), test/source
    file ratio.
    """

    details: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="Signals: {has_test_dir, test_frameworks, test_file_ratio, has_conftest}",
    )


class CiCdScore(SubScore):
    """CI/CD pipeline presence and configuration quality.

    Checks: .github/workflows presence, CI badge, config validity,
    multi-OS testing, coverage reporting.
    """

    details: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="Signals: {has_github_actions, workflow_count, has_ci_badge, has_coverage}",
    )


class DependencyQualityScore(SubScore):
    """Dependency management quality signals.

    Checks: lockfile presence, dependency pinning, update signals
    (dependabot/renovate config).
    """

    details: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="Signals: {has_lockfile, pinning_ratio, has_dependabot, has_renovate}",
    )


# --- Gate 1: Composite Result ---


class MetadataScreenResult(BaseModel):
    """Gate 1 — Metadata screening result (zero LLM cost).

    Combines 7 sub-scores into a composite gate1_total.
    gate1_pass is determined by comparing gate1_total against
    the configured threshold (default 0.4, configurable per-session).
    """

    full_name: str = Field(description="Repository full name (owner/repo)")
    commit_sha: str = Field(default="", description="Commit SHA at screening time")

    hygiene: HygieneScore = Field(default_factory=lambda: HygieneScore(value=0.0))
    maintenance: MaintenanceScore = Field(default_factory=lambda: MaintenanceScore(value=0.0))
    release_discipline: ReleaseDisciplineScore = Field(
        default_factory=lambda: ReleaseDisciplineScore(value=0.0),
    )
    review_practice: ReviewPracticeScore = Field(
        default_factory=lambda: ReviewPracticeScore(value=0.0),
    )
    test_footprint: TestFootprintScore = Field(
        default_factory=lambda: TestFootprintScore(value=0.0),
    )
    ci_cd: CiCdScore = Field(default_factory=lambda: CiCdScore(value=0.0))
    dependency_quality: DependencyQualityScore = Field(
        default_factory=lambda: DependencyQualityScore(value=0.0),
    )

    gate1_total: float = Field(default=0.0, ge=0.0, le=1.0, description="Weighted composite score")
    gate1_coverage: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Fraction of sub-score weight with confidence > 0 (real data). "
            "Measures how many sub-scores had actual tool/API data vs. "
            "fallback/heuristic values."
        ),
    )
    gate1_pass: bool = Field(default=False, description="Whether candidate passed Gate 1")
    threshold_used: float = Field(default=0.4, description="Threshold applied for pass/fail")
    degraded_count: int = Field(
        default=0,
        description="Number of sub-score fetches that degraded due to API errors",
    )

    def compute_total(self) -> tuple[float, float]:
        """Compute weighted composite score and coverage from sub-scores.

        Returns:
            Tuple of (damped_composite, coverage).
            - damped_composite: coverage-aware weighted average (excludes confidence=0 sub-scores)
            - coverage: fraction of total weight that had real data (confidence > 0)

        Sub-scores with confidence <= 0 are excluded from the average;
        coverage reports the fraction of weight that had real data.
        """
        scores = [
            self.hygiene,
            self.maintenance,
            self.release_discipline,
            self.review_practice,
            self.test_footprint,
            self.ci_cd,
            self.dependency_quality,
        ]
        total_weight_possible = sum(s.weight for s in scores)
        weighted_sum = 0.0
        weight_used = 0.0
        for s in scores:
            if s.confidence <= 0.0:
                continue
            weighted_sum += s.value * s.weight
            weight_used += s.weight
        if weight_used <= 0:
            return 0.0, 0.0
        coverage = weight_used / total_weight_possible
        raw = weighted_sum / weight_used
        # Damping mirroring scoring/engine.py::_apply_weights
        damped = raw * (0.5 + 0.5 * coverage)
        return damped, coverage


# --- Gate 2: Static/Security Screening Sub-Scores ---


class SecurityHygieneScore(SubScore):
    """Security posture from OpenSSF Scorecard.

    Checks: branch protection, workflow security, token permissions,
    dependency update automation, signed releases.
    """

    details: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description=(
            "Scorecard details: {scorecard_score, branch_protection, token_permissions, ...}"
        ),
    )


class VulnerabilityScore(SubScore):
    """Known vulnerability assessment from OSV API.

    Checks: vulnerabilities in declared dependencies (severity,
    count, age of CVEs).
    """

    details: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description=(
            "Vulnerability details: {vuln_count, critical_count, high_count, osv_packages_checked}"
        ),
    )


class ComplexityScore(SubScore):
    """Code complexity and size metrics from scc/cloc.

    Checks: LOC, language breakdown, complexity metrics,
    file count, directory depth.
    """

    details: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="Complexity details: {total_loc, languages, file_count, avg_complexity}",
    )


class SecretHygieneScore(SubScore):
    """Secret detection from gitleaks scan.

    Checks: leaked secrets in git history, SARIF findings count.
    """

    details: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="Secret scan details: {findings_count, scan_tool, sarif_parsed}",
    )


# --- Gate 2: Composite Result ---


class StaticScreenResult(BaseModel):
    """Gate 2 — Static/security screening result (zero or low cost).

    Combines 4 sub-scores into a composite gate2_total.
    gate2_pass is determined by comparing gate2_total against
    the configured threshold (default 0.5, configurable per-session).

    Hard rule (Blueprint §16.5): gate2_pass must be True before
    any Gate 3 deep assessment.
    """

    full_name: str = Field(description="Repository full name (owner/repo)")
    commit_sha: str = Field(default="", description="Commit SHA at screening time")

    security_hygiene: SecurityHygieneScore = Field(
        default_factory=lambda: SecurityHygieneScore(value=0.0),
    )
    vulnerability: VulnerabilityScore = Field(
        default_factory=lambda: VulnerabilityScore(value=0.0),
    )
    complexity: ComplexityScore = Field(
        default_factory=lambda: ComplexityScore(value=0.0),
    )
    secret_hygiene: SecretHygieneScore = Field(
        default_factory=lambda: SecretHygieneScore(value=0.0),
    )

    gate2_total: float = Field(default=0.0, ge=0.0, le=1.0, description="Weighted composite score")
    gate2_coverage: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Fraction of sub-score weight with confidence > 0 (real data). "
            "Measures how many sub-scores had actual tool data vs. fallback."
        ),
    )
    gate2_pass: bool = Field(default=False, description="Whether candidate passed Gate 2")
    threshold_used: float = Field(default=0.5, description="Threshold applied for pass/fail")

    tools_used: list[str] = Field(
        default_factory=list,
        description="External tools invoked (e.g., ['scorecard', 'gitleaks', 'scc', 'osv'])",
    )
    tools_failed: list[str] = Field(
        default_factory=list,
        description="Tools that failed during screening (graceful degradation)",
    )

    def compute_total(self) -> tuple[float, float]:
        """Compute weighted composite score and coverage from sub-scores.

        Returns:
            Tuple of (damped_composite, coverage).
            - damped_composite: coverage-aware weighted average (excludes confidence=0 sub-scores)
            - coverage: fraction of total weight that had real data (confidence > 0)

        Sub-scores with confidence <= 0 are excluded from the average;
        coverage reports the fraction of weight that had real data.
        """
        scores = [
            self.security_hygiene,
            self.vulnerability,
            self.complexity,
            self.secret_hygiene,
        ]
        total_weight_possible = sum(s.weight for s in scores)
        weighted_sum = 0.0
        weight_used = 0.0
        for s in scores:
            if s.confidence <= 0.0:
                continue
            weighted_sum += s.value * s.weight
            weight_used += s.weight
        if weight_used <= 0:
            return 0.0, 0.0
        coverage = weight_used / total_weight_possible
        raw = weighted_sum / weight_used
        # Damping mirroring scoring/engine.py::_apply_weights
        damped = raw * (0.5 + 0.5 * coverage)
        return damped, coverage


# --- Combined Screening Result ---


class ScreeningResult(BaseModel):
    """Combined Gate 1 + Gate 2 screening result for a repository.

    This is the complete screening state used by the screening
    orchestrator (Phase 3) and hard gate enforcement.
    """

    full_name: str = Field(description="Repository full name (owner/repo)")
    commit_sha: str = Field(default="", description="Commit SHA at screening time")

    gate1: MetadataScreenResult | None = Field(
        default=None,
        description="Gate 1 result (None if not yet screened)",
    )
    gate2: StaticScreenResult | None = Field(
        default=None,
        description="Gate 2 result (None if not yet screened)",
    )

    @property
    def can_proceed_to_gate3(self) -> bool:
        """Check hard gate: Gate 1 + Gate 2 must both pass.

        Implements Blueprint §16.5 hard rule:
        no deep-scan LLM below Gate 1+2 threshold.
        """
        if self.gate1 is None or self.gate2 is None:
            return False
        return self.gate1.gate1_pass and self.gate2.gate2_pass
