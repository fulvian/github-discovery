"""Token budget enforcement for LLM assessment (Blueprint §16.5).

Hard constraints that cannot be overridden:
- Per-repo limit: max_tokens_per_repo (default 50k)
- Per-day limit: max_tokens_per_day (default 500k)

Usage::

    controller = BudgetController(
        max_tokens_per_repo=50_000,
        max_tokens_per_day=500_000,
    )
    controller.check_repo_budget("owner/repo", estimated_tokens=12_000)
    controller.check_daily_budget("owner/repo")
    controller.record_usage(token_usage)
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import structlog

from github_discovery.exceptions import BudgetExceededError

if TYPE_CHECKING:
    from github_discovery.models.assessment import TokenUsage

logger = structlog.get_logger(__name__)


class BudgetController:
    """Token budget enforcement for LLM assessment.

    Hard constraints (Blueprint §16.5):
    - Per-repo limit: max_tokens_per_repo (default 50k)
    - Per-day limit: max_tokens_per_day (default 500k)
    - These are HARD limits — no override possible.
    """

    def __init__(
        self,
        *,
        max_tokens_per_repo: int = 50_000,
        max_tokens_per_day: int = 500_000,
    ) -> None:
        """Initialize BudgetController with per-repo and per-day limits."""
        self._max_tokens_per_repo = max_tokens_per_repo
        self._max_tokens_per_day = max_tokens_per_day
        self._daily_usage: dict[str, int] = {}
        self._repo_usage: dict[str, int] = {}
        self._current_day: str = date.today().isoformat()
        logger.debug(
            "budget_controller_initialized",
            max_tokens_per_repo=max_tokens_per_repo,
            max_tokens_per_day=max_tokens_per_day,
        )

    def _today_key(self) -> str:
        """Return current date as ISO string for daily tracking.

        Automatically detects date change and resets the daily counter
        when a new day is encountered.
        """
        today = date.today().isoformat()
        if today != self._current_day:
            logger.info(
                "daily_budget_auto_reset",
                previous_day=self._current_day,
                new_day=today,
                tokens_used=self._daily_usage.get(self._current_day, 0),
            )
            self._current_day = today
        return today

    def check_repo_budget(
        self,
        full_name: str,
        estimated_tokens: int,
    ) -> None:
        """Check if a repo can be assessed within per-repo budget.

        Args:
            full_name: Repository full name (e.g. "owner/repo").
            estimated_tokens: Estimated tokens needed (from repomix packing).

        Raises:
            BudgetExceededError: If per-repo limit would be exceeded.
        """
        if estimated_tokens > self._max_tokens_per_repo:
            logger.warning(
                "repo_budget_exceeded",
                full_name=full_name,
                estimated_tokens=estimated_tokens,
                max_tokens_per_repo=self._max_tokens_per_repo,
            )
            raise BudgetExceededError(
                f"Per-repo budget exceeded for {full_name}: "
                f"estimated {estimated_tokens} > limit {self._max_tokens_per_repo}",
                budget_type="per_repo",
                budget_limit=self._max_tokens_per_repo,
                budget_used=estimated_tokens,
            )

        already_used = self._repo_usage.get(full_name, 0)
        if already_used + estimated_tokens > self._max_tokens_per_repo:
            logger.warning(
                "repo_budget_exceeded_cumulative",
                full_name=full_name,
                already_used=already_used,
                estimated_tokens=estimated_tokens,
                max_tokens_per_repo=self._max_tokens_per_repo,
            )
            raise BudgetExceededError(
                f"Per-repo budget exceeded for {full_name}: "
                f"{already_used} already used + {estimated_tokens} estimated "
                f"> limit {self._max_tokens_per_repo}",
                budget_type="per_repo",
                budget_limit=self._max_tokens_per_repo,
                budget_used=already_used + estimated_tokens,
            )

        logger.debug(
            "repo_budget_ok",
            full_name=full_name,
            estimated_tokens=estimated_tokens,
            already_used=already_used,
            max_tokens_per_repo=self._max_tokens_per_repo,
        )

    def check_daily_budget(self, full_name: str) -> None:
        """Check if daily budget allows another assessment.

        Args:
            full_name: Repository full name (for logging context).

        Raises:
            BudgetExceededError: If per-day limit would be exceeded.
        """
        today_key = self._today_key()
        used = self._daily_usage.get(today_key, 0)
        if used >= self._max_tokens_per_day:
            logger.warning(
                "daily_budget_exceeded",
                full_name=full_name,
                tokens_used_today=used,
                max_tokens_per_day=self._max_tokens_per_day,
            )
            raise BudgetExceededError(
                f"Daily budget exceeded: {used} used >= limit {self._max_tokens_per_day}",
                budget_type="per_day",
                budget_limit=self._max_tokens_per_day,
                budget_used=used,
            )

        logger.debug(
            "daily_budget_ok",
            full_name=full_name,
            tokens_used_today=used,
            max_tokens_per_day=self._max_tokens_per_day,
        )

    def record_usage(
        self,
        token_usage: TokenUsage,
        *,
        full_name: str = "",
    ) -> None:
        """Record actual token usage after LLM call.

        Updates both daily and per-repo tracking.

        Args:
            token_usage: TokenUsage from the LLM response.
            full_name: Repository full name for per-repo tracking.
        """
        total = token_usage.total_tokens

        # Update daily tracking
        today_key = self._today_key()
        self._daily_usage[today_key] = self._daily_usage.get(today_key, 0) + total

        # Update per-repo tracking
        if full_name:
            self._repo_usage[full_name] = self._repo_usage.get(full_name, 0) + total

        logger.info(
            "token_usage_recorded",
            repo=full_name or "<unknown>",
            prompt_tokens=token_usage.prompt_tokens,
            completion_tokens=token_usage.completion_tokens,
            total_tokens=total,
            daily_total=self._daily_usage.get(today_key, 0),
            repo_total=self._repo_usage.get(full_name, 0) if full_name else 0,
        )

    @property
    def daily_tokens_used(self) -> int:
        """Total tokens consumed today."""
        today_key = self._today_key()
        return self._daily_usage.get(today_key, 0)

    @property
    def remaining_daily_budget(self) -> int:
        """Remaining tokens in today's budget."""
        return max(0, self._max_tokens_per_day - self.daily_tokens_used)

    def reset_daily(self) -> None:
        """Reset daily budget (called at start of new day)."""
        old_day = self._current_day
        self._current_day = self._today_key()
        # Prune old daily entries older than the current day
        self._daily_usage = {k: v for k, v in self._daily_usage.items() if k >= self._current_day}
        logger.info(
            "daily_budget_reset",
            previous_day=old_day,
            new_day=self._current_day,
        )
