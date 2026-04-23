"""Deep technical assessment (Layer C) — Gate 3.

Gate 3 is the expensive LLM-based evaluation layer. Only top percentile
candidates that passed Gate 1 + Gate 2 are assessed.

Architecture (Blueprint §6, §16.5):
- RepomixAdapter: packs repos into LLM-friendly content
- LLMProvider: NanoGPT with instructor structured output
- BudgetController: hard token budget enforcement
- HeuristicAnalyzer: non-LLM baseline and fallback
- ResultParser: LLM output → DeepAssessmentResult
- AssessmentOrchestrator: full pipeline coordination

Hard rule (Blueprint §16.5): no candidate reaches Gate 3 without
passing both Gate 1 + Gate 2 (enforced by hard gate check).
"""

from __future__ import annotations

from github_discovery.assessment.budget_controller import BudgetController
from github_discovery.assessment.heuristics import HeuristicAnalyzer
from github_discovery.assessment.llm_provider import LLMProvider
from github_discovery.assessment.orchestrator import AssessmentOrchestrator
from github_discovery.assessment.repomix_adapter import RepomixAdapter
from github_discovery.assessment.result_parser import ResultParser
from github_discovery.assessment.types import (
    AssessmentContext,
    HeuristicScores,
    LLMBatchOutput,
    LLMDimensionOutput,
    RepoContent,
)

__all__ = [
    "AssessmentContext",
    "AssessmentOrchestrator",
    "BudgetController",
    "HeuristicAnalyzer",
    "HeuristicScores",
    "LLMBatchOutput",
    "LLMDimensionOutput",
    "LLMProvider",
    "RepoContent",
    "RepomixAdapter",
    "ResultParser",
]
