"""Language-specific quality analyzers for deep assessment."""

from __future__ import annotations

from github_discovery.assessment.lang_analyzers.base import LanguageAnalyzer
from github_discovery.assessment.lang_analyzers.python_analyzer import PythonAnalyzer

__all__ = ["LanguageAnalyzer", "PythonAnalyzer"]
