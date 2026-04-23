"""Issue/PR practices scorer for Gate 1.

Evaluates PR/issue templates, review presence, label usage,
and response latency proxy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from github_discovery.models.screening import ReviewPracticeScore

if TYPE_CHECKING:
    from github_discovery.screening.types import RepoContext

_ISSUE_TEMPLATE_PATHS: list[str] = [
    ".github/ISSUE_TEMPLATE",
    ".github/ISSUE_TEMPLATE.md",
]
_PR_TEMPLATE_PATHS: list[str] = [
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/PULL_REQUEST_TEMPLATE",
    "PULL_REQUEST_TEMPLATE.md",
]

# Scoring weights
_WEIGHT_TEMPLATES = 0.3
_WEIGHT_REVIEW = 0.3
_WEIGHT_LABELS = 0.2
# Response latency (0.2) is skipped for now — requires deeper API data


def _has_issue_template(contents: list[str]) -> bool:
    """Check for issue template files or directory.

    Directory-based templates match via startswith (e.g.,
    '.github/ISSUE_TEMPLATE/bug_report.yml').
    """
    for path in _ISSUE_TEMPLATE_PATHS:
        for item in contents:
            if item == path or item.startswith(path + "/"):
                return True
    return False


def _has_pr_template(contents: list[str]) -> bool:
    """Check for PR template files."""
    return any(item in contents for item in _PR_TEMPLATE_PATHS)


def _compute_review_rate(prs: list[dict[str, object]]) -> float:
    """Compute fraction of PRs with review activity.

    A PR has review activity if it has review_comments > 0
    or non-empty requested_reviewers.
    """
    if not prs:
        return 0.0

    reviewed = 0
    for pr in prs:
        review_comments = pr.get("review_comments", 0)
        requested_reviewers = pr.get("requested_reviewers", [])
        has_comments = isinstance(review_comments, int) and review_comments > 0
        has_reviewers = isinstance(requested_reviewers, list) and len(requested_reviewers) > 0
        if has_comments or has_reviewers:
            reviewed += 1

    return reviewed / len(prs)


def _compute_label_usage(
    issues: list[dict[str, object]],
    prs: list[dict[str, object]],
) -> float:
    """Compute fraction of issues + PRs with non-empty labels."""
    total_items = len(issues) + len(prs)
    if total_items == 0:
        return 0.0

    labeled = 0
    for item in issues + prs:
        labels = item.get("labels", [])
        if isinstance(labels, list) and len(labels) > 0:
            labeled += 1

    return labeled / total_items


class PracticesScorer:
    """Scores code review practices and PR/issue management."""

    def score(self, ctx: RepoContext) -> ReviewPracticeScore:
        """Score review practices based on templates and PR activity."""
        contents = ctx.repo_contents
        notes: list[str] = []

        # 1. Template detection
        has_issue_tpl = _has_issue_template(contents)
        has_pr_tpl = _has_pr_template(contents)
        templates_present = has_issue_tpl or has_pr_tpl
        template_score = 1.0 if templates_present else 0.0

        if has_pr_tpl:
            notes.append("PR template detected")
        if has_issue_tpl:
            notes.append("Issue template detected")

        # 2. Review presence
        review_rate = _compute_review_rate(ctx.recent_prs)
        if review_rate > 0:
            notes.append(f"Review rate: {review_rate:.0%}")

        # 3. Label usage
        label_usage = _compute_label_usage(ctx.recent_issues, ctx.recent_prs)
        if label_usage > 0:
            notes.append(f"Label usage: {label_usage:.0%}")

        # 4. Composite score (response latency skipped)
        total_weight = _WEIGHT_TEMPLATES + _WEIGHT_REVIEW + _WEIGHT_LABELS
        score = (
            template_score * _WEIGHT_TEMPLATES
            + review_rate * _WEIGHT_REVIEW
            + label_usage * _WEIGHT_LABELS
        ) / total_weight

        return ReviewPracticeScore(
            value=score,
            details={
                "has_pr_template": has_pr_tpl,
                "has_issue_template": has_issue_tpl,
                "review_rate": round(review_rate, 4),
                "label_usage": round(label_usage, 4),
            },
            confidence=1.0,
            notes=notes,
        )
