"""Tests for ghdisc doctor — pre-flight system checks (TB3).

Tests individual check functions and the doctor command rendering.
"""

from __future__ import annotations

from github_discovery.cli.doctor import (
    _check_feature_store_writable,
    _check_git,
    _check_gitleaks,
    _check_profiles_loadable,
    _check_repomix,
    _check_scc,
)


class TestDoctorChecks:
    """Tests for individual doctor check functions."""

    def test_check_git_found(self) -> None:
        """git check returns ok=True when git binary exists."""
        result = _check_git()
        assert result.ok is True
        assert "git" in result.name

    def test_check_gitleaks_always_ok(self) -> None:
        """gitleaks check is ok=True even when binary is missing (optional)."""
        result = _check_gitleaks()
        assert result.ok is True  # Optional — gracefully degrades

    def test_check_scc_always_ok(self) -> None:
        """scc check is ok=True even when binary is missing (optional)."""
        result = _check_scc()
        assert result.ok is True  # Optional — gracefully degrades

    def test_check_repomix_found(self) -> None:
        """repomix check returns ok=True when package is installed."""
        result = _check_repomix()
        assert result.ok is True
        assert "repomix" in result.name

    def test_check_profiles_loadable(self) -> None:
        """Domain profiles are loadable without errors."""
        result = _check_profiles_loadable()
        assert result.ok is True
        assert "profiles" in result.name

    def test_check_feature_store_writable(self) -> None:
        """Feature store path check completes (may not be writable in test env)."""
        result = _check_feature_store_writable()
        # The check should not crash — ok may be False in CI/test envs
        assert result.name == "feature_store"
        assert isinstance(result.ok, bool)
        assert isinstance(result.message, str)

    def test_check_git_result_has_fields(self) -> None:
        """Check result has all expected fields populated."""
        result = _check_git()
        assert hasattr(result, "name")
        assert hasattr(result, "ok")
        assert hasattr(result, "message")
        assert isinstance(result.name, str)
        assert isinstance(result.ok, bool)
        assert isinstance(result.message, str)

    def test_check_repomix_suggestion_when_failing(self) -> None:
        """repomix check suggestion field exists."""
        result = _check_repomix()
        # If ok=True, suggestion may be None
        if not result.ok:
            assert result.suggestion is not None
            assert "pip install" in result.suggestion

    def test_check_profiles_loadable_has_impact(self) -> None:
        """profiles check populates impact field."""
        result = _check_profiles_loadable()
        if not result.ok:
            assert result.impact is not None
