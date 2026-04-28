"""Token budget enforcement for LLM assessment (Blueprint §16.5).

Hard constraints (per-repo, within model context window):
- Per-repo limit: max_tokens_per_repo (default 100k) — hard block.

Soft constraints (monitoring only):
- Daily soft limit: daily_soft_limit (default 2M) — warning log only, never blocks.

The daily limit was intentionally converted from hard to soft because:
1. With NanoGPT subscription mode, token costs are covered by the plan.
2. A 500k/day limit would allow only ~11 full repo assessments, blocking
   normal discovery workflows after a single session.
3. Industry tools (CodeRabbit, Greptile) use per-seat/per-review pricing
   without exposing token budgets to users — they internalize LLM costs.

Usage::

    controller = BudgetController(
        max_tokens_per_repo=100_000,
        daily_soft_limit=2_000_000,
    )
    controller.check_repo_budget("owner/repo", estimated_tokens=12_000)
    controller.check_daily_soft_limit("owner/repo")  # Warning only
    controller.record_usage(token_usage, full_name="owner/repo")
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

    Hard constraints:
    - Per-repo limit: max_tokens_per_repo (default 100k).
      This is a hard block — repos exceeding the model context window
      cannot be assessed meaningfully.

    Soft constraints (monitoring only):
    - Daily soft limit: daily_soft_limit (default 2M).
      Emits a warning log when exceeded but NEVER blocks assessment.
      Useful for cost monitoring and anomaly detection.
    """

    def __init__(
        self,
        *,
        max_tokens_per_repo: int = 100_000,
        daily_soft_limit: int = 2_000_000,
        hard_daily_limit: int = 0,
    ) -> None:
        """Initialize BudgetController with per-repo hard limit and daily soft limit.

        Args:
            max_tokens_per_repo: Hard per-repo token limit (default 100k).
            daily_soft_limit: Soft daily token limit for monitoring (default 2M).
            hard_daily_limit: Hard daily token limit that blocks assessments (default 0=disabled).
        """
        self._max_tokens_per_repo = max_tokens_per_repo
        self._daily_soft_limit = daily_soft_limit
        self._hard_daily_limit = hard_daily_limit
        self._daily_usage: dict[str, int] = {}
        self._repo_usage: dict[str, int] = {}
        self._current_day: str = date.today().isoformat()
        self._daily_soft_limit_warned: bool = False
        logger.debug(
            "budget_controller_initialized",
            max_tokens_per_repo=max_tokens_per_repo,
            daily_soft_limit=daily_soft_limit,
            hard_daily_limit=hard_daily_limit,
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
            self._daily_soft_limit_warned = False
        return today

    def check_repo_budget(
        self,
        full_name: str,
        estimated_tokens: int,
    ) -> None:
        """Check if a repo can be assessed within per-repo budget.

        This is a HARD limit — repos exceeding the model context window
        cannot be assessed meaningfully.

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

    def check_daily_soft_limit(self, full_name: str) -> None:
        """Check daily limits — hard limit blocks, soft limit warns.

        The hard daily limit raises BudgetExceededError when exceeded.
        The soft daily limit emits a warning log only, never blocks.

        Args:
            full_name: Repository full name (for logging context).

        Raises:
            BudgetExceededError: If hard_daily_limit is set and daily usage exceeds it.
        """
        today_key = self._today_key()
        used = self._daily_usage.get(today_key, 0)

        # Check hard daily limit first (blocks assessment)
        if self._hard_daily_limit > 0 and used >= self._hard_daily_limit:
            logger.error(
                "daily_hard_limit_exceeded",
                full_name=full_name,
                tokens_used_today=used,
                hard_daily_limit=self._hard_daily_limit,
            )
            raise BudgetExceededError(
                f"Daily token budget exhausted: {used} tokens used today "
                f"(hard limit: {self._hard_daily_limit}). "
                "Assessment blocked. Set GHDISC_ASSESSMENT_HARD_DAILY_LIMIT to adjust.",
                budget_type="daily_hard",
                budget_limit=self._hard_daily_limit,
                budget_used=used,
            )

        # Soft limit: warning only, never blocks
        if used >= self._daily_soft_limit and not self._daily_soft_limit_warned:
            logger.warning(
                "daily_soft_limit_exceeded",
                full_name=full_name,
                tokens_used_today=used,
                daily_soft_limit=self._daily_soft_limit,
                note="This is a monitoring warning — assessment continues normally. "
                "Set GHDISC_ASSESSMENT_DAILY_SOFT_LIMIT to adjust the threshold.",
            )
            self._daily_soft_limit_warned = True
        else:
            logger.debug(
                "daily_soft_limit_ok",
                full_name=full_name,
                tokens_used_today=used,
                daily_soft_limit=self._daily_soft_limit,
                hard_daily_limit=self._hard_daily_limit,
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

        # Emit soft limit warning after recording if threshold crossed
        daily_total = self._daily_usage.get(today_key, 0)
        if daily_total >= self._daily_soft_limit and not self._daily_soft_limit_warned:
            logger.warning(
                "daily_soft_limit_exceeded_post_record",
                tokens_used_today=daily_total,
                daily_soft_limit=self._daily_soft_limit,
            )
            self._daily_soft_limit_warned = True

    @property
    def daily_tokens_used(self) -> int:
        """Total tokens consumed today."""
        today_key = self._today_key()
        return self._daily_usage.get(today_key, 0)

    @property
    def remaining_daily_budget(self) -> int:
        """Remaining tokens before daily soft limit warning."""
        return max(0, self._daily_soft_limit - self.daily_tokens_used)

    def reset_daily(self) -> None:
        """Reset daily tracking (called at start of new day)."""
        old_day = self._current_day
        self._current_day = self._today_key()
        # Prune old daily entries older than the current day
        self._daily_usage = {k: v for k, v in self._daily_usage.items() if k >= self._current_day}
        self._daily_soft_limit_warned = False
        logger.info(
            "daily_budget_reset",
            previous_day=old_day,
            new_day=self._current_day,
        )
