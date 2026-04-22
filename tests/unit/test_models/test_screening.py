"""Tests for screening models (Gate 1 and Gate 2)."""

from __future__ import annotations

import pytest

from github_discovery.models.screening import (
    CiCdScore,
    ComplexityScore,
    DependencyQualityScore,
    HygieneScore,
    MaintenanceScore,
    MetadataScreenResult,
    ReleaseDisciplineScore,
    ReviewPracticeScore,
    ScreeningResult,
    SecretHygieneScore,
    SecurityHygieneScore,
    StaticScreenResult,
    SubScore,
    TestFootprintScore as FootprintScore,
    VulnerabilityScore,
)


class TestSubScore:
    """Test SubScore base pattern."""

    def test_valid_score(self) -> None:
        """SubScore accepts valid 0.0-1.0 values."""
        score = SubScore(value=0.75)
        assert score.value == 0.75
        assert score.confidence == 1.0

    def test_score_out_of_range(self) -> None:
        """SubScore rejects values outside 0.0-1.0."""
        with pytest.raises(Exception):  # noqa: B017
            SubScore(value=1.5)
        with pytest.raises(Exception):  # noqa: B017
            SubScore(value=-0.1)

    def test_score_with_details(self) -> None:
        """SubScore carries details dict."""
        score = SubScore(
            value=0.8,
            details={"files_found": ["LICENSE", "README.md"]},
            notes=["LICENSE is MIT", "README has content"],
        )
        assert score.details["files_found"] == ["LICENSE", "README.md"]
        assert len(score.notes) == 2


class TestMetadataScreenResult:
    """Test Gate 1 composite result."""

    def test_default_result(self) -> None:
        """Default result has all scores at 0.0 and fails."""
        result = MetadataScreenResult(full_name="test/repo")
        assert result.gate1_pass is False
        assert result.gate1_total == 0.0

    def test_compute_total_uniform_weights(self) -> None:
        """Compute total averages scores with uniform weights."""
        result = MetadataScreenResult(
            full_name="test/repo",
            hygiene=HygieneScore(value=0.8),
            maintenance=MaintenanceScore(value=0.6),
            release_discipline=ReleaseDisciplineScore(value=0.7),
            review_practice=ReviewPracticeScore(value=0.5),
            test_footprint=FootprintScore(value=0.9),
            ci_cd=CiCdScore(value=0.4),
            dependency_quality=DependencyQualityScore(value=0.6),
        )
        total = result.compute_total()
        assert 0.0 <= total <= 1.0
        # With uniform weights (1.0 each), total should be average
        expected_avg = (0.8 + 0.6 + 0.7 + 0.5 + 0.9 + 0.4 + 0.6) / 7
        assert abs(total - expected_avg) < 0.01

    def test_pass_with_high_scores(self) -> None:
        """Result passes with high scores above threshold."""
        result = MetadataScreenResult(
            full_name="test/repo",
            hygiene=HygieneScore(value=0.9),
            maintenance=MaintenanceScore(value=0.8),
            release_discipline=ReleaseDisciplineScore(value=0.7),
            review_practice=ReviewPracticeScore(value=0.6),
            test_footprint=FootprintScore(value=0.8),
            ci_cd=CiCdScore(value=0.7),
            dependency_quality=DependencyQualityScore(value=0.7),
            gate1_total=0.75,
            gate1_pass=True,
        )
        assert result.gate1_pass is True
        assert result.gate1_total >= result.threshold_used

    def test_json_round_trip(self) -> None:
        """MetadataScreenResult serializes to/from JSON."""
        result = MetadataScreenResult(
            full_name="test/repo",
            hygiene=HygieneScore(value=0.8, details={"files_found": ["LICENSE"]}),
            gate1_total=0.6,
            gate1_pass=True,
        )
        json_str = result.model_dump_json()
        restored = MetadataScreenResult.model_validate_json(json_str)
        assert restored.full_name == "test/repo"
        assert restored.hygiene.value == 0.8
        assert restored.gate1_pass is True

    def test_sub_scores_with_custom_weights(self) -> None:
        """Sub-scores can have custom weights for domain-specific scoring."""
        score = HygieneScore(value=0.8, weight=0.5)
        assert score.weight == 0.5


class TestStaticScreenResult:
    """Test Gate 2 composite result."""

    def test_default_result(self) -> None:
        """Default result has all scores at 0.0 and fails."""
        result = StaticScreenResult(full_name="test/repo")
        assert result.gate2_pass is False
        assert result.gate2_total == 0.0

    def test_compute_total(self) -> None:
        """Compute total averages Gate 2 scores."""
        result = StaticScreenResult(
            full_name="test/repo",
            security_hygiene=SecurityHygieneScore(value=0.8),
            vulnerability=VulnerabilityScore(value=0.9),
            complexity=ComplexityScore(value=0.6),
            secret_hygiene=SecretHygieneScore(value=1.0),
        )
        total = result.compute_total()
        expected = (0.8 + 0.9 + 0.6 + 1.0) / 4
        assert abs(total - expected) < 0.01

    def test_tools_tracking(self) -> None:
        """Result tracks which tools were used and which failed."""
        result = StaticScreenResult(
            full_name="test/repo",
            tools_used=["scorecard", "scc", "osv"],
            tools_failed=["gitleaks"],
        )
        assert "gitleaks" in result.tools_failed


class TestScreeningResult:
    """Test combined Gate 1 + Gate 2 result."""

    def test_can_proceed_to_gate3_both_pass(self) -> None:
        """Can proceed when both gates pass."""
        result = ScreeningResult(
            full_name="test/repo",
            gate1=MetadataScreenResult(
                full_name="test/repo",
                gate1_total=0.7,
                gate1_pass=True,
            ),
            gate2=StaticScreenResult(
                full_name="test/repo",
                gate2_total=0.6,
                gate2_pass=True,
            ),
        )
        assert result.can_proceed_to_gate3 is True

    def test_cannot_proceed_gate1_fail(self) -> None:
        """Cannot proceed when Gate 1 fails (hard gate)."""
        result = ScreeningResult(
            full_name="test/repo",
            gate1=MetadataScreenResult(
                full_name="test/repo",
                gate1_total=0.3,
                gate1_pass=False,
            ),
            gate2=StaticScreenResult(
                full_name="test/repo",
                gate2_total=0.7,
                gate2_pass=True,
            ),
        )
        assert result.can_proceed_to_gate3 is False

    def test_cannot_proceed_gate2_missing(self) -> None:
        """Cannot proceed when Gate 2 not yet done."""
        result = ScreeningResult(
            full_name="test/repo",
            gate1=MetadataScreenResult(
                full_name="test/repo",
                gate1_total=0.7,
                gate1_pass=True,
            ),
            gate2=None,
        )
        assert result.can_proceed_to_gate3 is False

    def test_cannot_proceed_both_missing(self) -> None:
        """Cannot proceed when neither gate done."""
        result = ScreeningResult(full_name="test/repo")
        assert result.can_proceed_to_gate3 is False
