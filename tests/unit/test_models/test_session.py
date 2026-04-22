"""Tests for session and progress models."""

from __future__ import annotations

import pytest

from github_discovery.models.session import (
    ProgressInfo,
    SessionConfig,
    SessionState,
    SessionStatus,
)


class TestSessionConfig:
    """Test SessionConfig model."""

    def test_default_config(self) -> None:
        """Default config has sensible values."""
        config = SessionConfig()
        assert config.min_gate1_score == 0.4
        assert config.min_gate2_score == 0.5
        assert config.hard_gate_enforcement is True

    def test_custom_config(self) -> None:
        """Custom config overrides defaults."""
        config = SessionConfig(
            min_gate1_score=0.3,
            max_tokens_per_repo=30000,
            preferred_domains=["library", "cli"],
        )
        assert config.min_gate1_score == 0.3
        assert config.preferred_domains == ["library", "cli"]

    def test_score_validation(self) -> None:
        """Score must be between 0.0 and 1.0."""
        with pytest.raises(ValueError):
            SessionConfig(min_gate1_score=1.5)

    def test_negative_value_validation(self) -> None:
        """Token counts must be positive."""
        with pytest.raises(ValueError):
            SessionConfig(max_tokens_per_repo=0)


class TestSessionState:
    """Test SessionState model."""

    def test_default_state(self) -> None:
        """Default state is CREATED with auto-generated IDs."""
        state = SessionState(name="test-session")
        assert state.name == "test-session"
        assert state.status == SessionStatus.CREATED
        assert len(state.session_id) > 0
        assert state.pool_ids == []

    def test_state_serialization(self) -> None:
        """Session state can serialize to/from JSON."""
        state = SessionState(name="test")
        json_str = state.model_dump_json()
        restored = SessionState.model_validate_json(json_str)
        assert restored.session_id == state.session_id
        assert restored.name == state.name

    def test_touch_updates_timestamp(self) -> None:
        """touch() updates the updated_at field."""
        state = SessionState(name="test")
        old_updated = state.updated_at
        state.touch()
        assert state.updated_at >= old_updated


class TestProgressInfo:
    """Test ProgressInfo model."""

    def test_default_progress(self) -> None:
        """Default progress starts at 0.0."""
        progress = ProgressInfo(message="Starting discovery")
        assert progress.progress == 0.0
        assert progress.total == 100.0
        assert "Starting discovery" in progress.message

    def test_progress_serialization(self) -> None:
        """Progress info serializes to JSON."""
        progress = ProgressInfo(
            progress=42.0,
            total=100.0,
            message="Screened 42/100 candidates",
            session_id="session-123",
        )
        data = progress.model_dump()
        assert data["progress"] == 42.0
        assert data["session_id"] == "session-123"
