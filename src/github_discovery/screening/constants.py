"""Shared screening constants.

These values are shared across screening modules to ensure consistent
fallback behavior when external tools (gitleaks, scc, scorecard, osv)
are unavailable.
"""

from __future__ import annotations

# Neutral fallback value — neither penalizes nor rewards when a tool is missing.
# Used for sub-score.value when confidence = 0 (no real data).
FALLBACK_VALUE: float = 0.5

# Fallback confidence — signals "no real data" to compute_total().
# Sub-scores with confidence <= 0 are excluded from coverage-aware average.
FALLBACK_CONFIDENCE: float = 0.0
