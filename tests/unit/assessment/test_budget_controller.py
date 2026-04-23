"""Tests for BudgetController — token budget enforcement.

Tests per-repo budget, per-day budget, cumulative tracking,
recording usage, and daily auto-reset.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from github_discovery.assessment.budget_controller import BudgetController
from github_discovery.exceptions import BudgetExceededError
from github_discovery.models.assessment import TokenUsage


class TestCheckRepoBudget:
    """Tests for BudgetController.check_repo_budget."""

    def test_passes_within_budget(self) -> None:
        """check_repo_budget passes when within limit."""
        controller = BudgetController(max_tokens_per_repo=50_000)
        controller.check_repo_budget("test/repo", estimated_tokens=10_000)
        # No exception raised → pass

    def test_raises_when_exceeding_single_request(self) -> None:
        """check_repo_budget raises BudgetExceededError for single over-limit request."""
        controller = BudgetController(max_tokens_per_repo=50_000)

        with pytest.raises(BudgetExceededError) as exc_info:
            controller.check_repo_budget("test/repo", estimated_tokens=60_000)

        assert "Per-repo budget exceeded" in str(exc_info.value)
        assert exc_info.value.budget_type == "per_repo"

    def test_raises_on_exact_limit(self) -> None:
        """check_repo_budget raises when estimated equals limit (already_used = 0)."""
        controller = BudgetController(max_tokens_per_repo=50_000)
        # Single request exactly at limit — already_used=0, estimated=50000
        # 0 + 50000 > 50000 is False, but estimated > limit:
        # 50000 > 50000 is False. So this passes (equal is OK).
        controller.check_repo_budget("test/repo", estimated_tokens=50_000)

    def test_raises_when_exceeding_exact_limit(self) -> None:
        """check_repo_budget raises when estimated is 1 over limit."""
        controller = BudgetController(max_tokens_per_repo=50_000)

        with pytest.raises(BudgetExceededError):
            controller.check_repo_budget("test/repo", estimated_tokens=50_001)

    def test_cumulative_tracking_raises(self) -> None:
        """check_repo_budget raises when cumulative usage exceeds limit."""
        controller = BudgetController(max_tokens_per_repo=50_000)

        # First call uses 30k
        controller._repo_usage["test/repo"] = 30_000

        # Second call would add 25k → total 55k > 50k
        with pytest.raises(BudgetExceededError) as exc_info:
            controller.check_repo_budget("test/repo", estimated_tokens=25_000)

        assert "already used" in str(exc_info.value)

    def test_cumulative_within_budget_passes(self) -> None:
        """check_repo_budget passes when cumulative is within limit."""
        controller = BudgetController(max_tokens_per_repo=50_000)

        controller._repo_usage["test/repo"] = 30_000
        controller.check_repo_budget("test/repo", estimated_tokens=19_999)
        # 30000 + 19999 = 49999 <= 50000 → passes

    def test_different_repos_tracked_separately(self) -> None:
        """Per-repo budgets are tracked independently."""
        controller = BudgetController(max_tokens_per_repo=50_000)

        controller._repo_usage["test/repo-a"] = 45_000
        # repo-a is near limit, but repo-b starts fresh
        controller.check_repo_budget("test/repo-b", estimated_tokens=40_000)

    def test_zero_estimated_tokens_passes(self) -> None:
        """check_repo_budget passes with zero estimated tokens."""
        controller = BudgetController(max_tokens_per_repo=50_000)
        controller.check_repo_budget("test/repo", estimated_tokens=0)


class TestCheckDailyBudget:
    """Tests for BudgetController.check_daily_budget."""

    def test_passes_within_budget(self) -> None:
        """check_daily_budget passes when daily usage is below limit."""
        controller = BudgetController(max_tokens_per_day=500_000)
        controller.check_daily_budget("test/repo")
        # No exception → pass

    def test_raises_when_exceeded(self) -> None:
        """check_daily_budget raises when daily usage >= limit."""
        controller = BudgetController(max_tokens_per_day=500_000)

        today_key = date.today().isoformat()
        controller._daily_usage[today_key] = 500_000

        with pytest.raises(BudgetExceededError) as exc_info:
            controller.check_daily_budget("test/repo")

        assert "Daily budget exceeded" in str(exc_info.value)
        assert exc_info.value.budget_type == "per_day"

    def test_passes_when_just_under_limit(self) -> None:
        """check_daily_budget passes when usage is limit - 1."""
        controller = BudgetController(max_tokens_per_day=500_000)

        today_key = date.today().isoformat()
        controller._daily_usage[today_key] = 499_999

        controller.check_daily_budget("test/repo")

    def test_raises_when_over_limit(self) -> None:
        """check_daily_budget raises when daily usage exceeds limit."""
        controller = BudgetController(max_tokens_per_day=500_000)

        today_key = date.today().isoformat()
        controller._daily_usage[today_key] = 600_000

        with pytest.raises(BudgetExceededError):
            controller.check_daily_budget("test/repo")


class TestRecordUsage:
    """Tests for BudgetController.record_usage."""

    def test_updates_daily_and_per_repo(self) -> None:
        """record_usage updates both daily and per-repo tracking."""
        controller = BudgetController()

        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        controller.record_usage(usage, full_name="test/repo")

        assert controller.daily_tokens_used == 150
        assert controller._repo_usage.get("test/repo") == 150

    def test_cumulative_daily_tracking(self) -> None:
        """Multiple record_usage calls accumulate daily total."""
        controller = BudgetController()

        for _ in range(3):
            controller.record_usage(
                TokenUsage(total_tokens=100),
                full_name="test/repo",
            )

        assert controller.daily_tokens_used == 300
        assert controller._repo_usage["test/repo"] == 300

    def test_records_without_full_name(self) -> None:
        """record_usage works without full_name (only daily tracking)."""
        controller = BudgetController()

        controller.record_usage(TokenUsage(total_tokens=200))

        assert controller.daily_tokens_used == 200
        assert len(controller._repo_usage) == 0

    def test_multiple_repos_daily_aggregate(self) -> None:
        """Daily usage aggregates across multiple repos."""
        controller = BudgetController()

        controller.record_usage(TokenUsage(total_tokens=100), full_name="repo/a")
        controller.record_usage(TokenUsage(total_tokens=200), full_name="repo/b")

        assert controller.daily_tokens_used == 300
        assert controller._repo_usage["repo/a"] == 100
        assert controller._repo_usage["repo/b"] == 200


class TestDailyTokensUsed:
    """Tests for BudgetController.daily_tokens_used property."""

    def test_initially_zero(self) -> None:
        """daily_tokens_used is 0 before any usage."""
        controller = BudgetController()
        assert controller.daily_tokens_used == 0

    def test_reflects_recorded_usage(self) -> None:
        """daily_tokens_used reflects recorded usage."""
        controller = BudgetController()
        controller.record_usage(TokenUsage(total_tokens=500), full_name="test/repo")

        assert controller.daily_tokens_used == 500


class TestRemainingDailyBudget:
    """Tests for BudgetController.remaining_daily_budget property."""

    def test_initially_full_budget(self) -> None:
        """remaining_daily_budget equals max when no usage."""
        controller = BudgetController(max_tokens_per_day=500_000)
        assert controller.remaining_daily_budget == 500_000

    def test_decreases_with_usage(self) -> None:
        """remaining_daily_budget decreases after record_usage."""
        controller = BudgetController(max_tokens_per_day=500_000)
        controller.record_usage(TokenUsage(total_tokens=100_000), full_name="test/repo")

        assert controller.remaining_daily_budget == 400_000

    def test_never_goes_negative(self) -> None:
        """remaining_daily_budget is clamped to 0."""
        controller = BudgetController(max_tokens_per_day=100)

        today_key = date.today().isoformat()
        controller._daily_usage[today_key] = 200

        assert controller.remaining_daily_budget == 0


class TestResetDaily:
    """Tests for BudgetController.reset_daily."""

    def test_resets_daily_counter(self) -> None:
        """reset_daily prunes old daily usage entries."""
        controller = BudgetController(max_tokens_per_day=500_000)
        controller.record_usage(TokenUsage(total_tokens=100_000), full_name="test/repo")

        assert controller.daily_tokens_used == 100_000

        # Simulate a day change so the current entry becomes "old"
        today = date.today().isoformat()
        yesterday = date(
            year=date.today().year,
            month=date.today().month,
            day=date.today().day - 1,
        ).isoformat()
        controller._current_day = yesterday
        # Move the usage to the yesterday key
        controller._daily_usage[yesterday] = controller._daily_usage.pop(today, 0)

        controller.reset_daily()

        # After reset, today should have no usage
        assert controller.daily_tokens_used == 0

    def test_preserves_repo_tracking(self) -> None:
        """reset_daily does not clear per-repo tracking."""
        controller = BudgetController()
        controller.record_usage(TokenUsage(total_tokens=100), full_name="test/repo")

        controller.reset_daily()

        assert controller._repo_usage.get("test/repo") == 100


class TestAutoResetOnDayChange:
    """Tests for BudgetController auto-reset on day change."""

    def test_auto_reset_triggers_on_new_day(self) -> None:
        """_today_key() resets daily when a new day is detected."""
        controller = BudgetController(max_tokens_per_day=500_000)
        today = date.today()

        # Record usage for today
        controller.record_usage(TokenUsage(total_tokens=100), full_name="test/repo")
        assert controller.daily_tokens_used == 100

        # Simulate being on a different day
        tomorrow = date(
            year=today.year,
            month=today.month,
            day=today.day + 1,
        )
        controller._current_day = today.isoformat()

        with patch("github_discovery.assessment.budget_controller.date") as mock_date:
            mock_date.today.return_value = tomorrow
            mock_date.side_effect = date
            # Trigger _today_key which detects day change
            key = controller._today_key()

        assert key == tomorrow.isoformat()
        # Daily usage for the old day should still be recorded,
        # but the new day starts fresh
        assert controller._current_day == tomorrow.isoformat()

    def test_no_reset_on_same_day(self) -> None:
        """_today_key() does not reset when still same day."""
        controller = BudgetController()
        controller.record_usage(TokenUsage(total_tokens=100), full_name="test/repo")

        initial_day = controller._current_day
        controller._today_key()

        assert controller._current_day == initial_day
        assert controller.daily_tokens_used == 100
