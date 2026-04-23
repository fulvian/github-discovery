"""Abstract base class for language-specific quality analyzers.

Each analyzer targets a specific programming language and uses external
tools (linters, type checkers, etc.) to produce a DimensionScore for
code quality assessment in Gate 3 deep evaluation.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from github_discovery.models.assessment import DimensionScore


class LanguageAnalyzer(abc.ABC):
    """Abstract base for language-specific quality analyzers.

    Subclasses implement ``language()`` to declare which language they
    handle and ``analyze()`` to run an external tool against a cloned
    repository directory.  Analyzers must **never** raise exceptions
    from ``analyze()`` — return ``None`` on any failure instead.
    """

    @abc.abstractmethod
    def language(self) -> str:
        """Return the language this analyzer handles (e.g. ``"python"``)."""

    @abc.abstractmethod
    async def analyze(self, clone_dir: str) -> DimensionScore | None:
        """Run language-specific analysis on a cloned repository.

        Args:
            clone_dir: Absolute or relative path to the cloned repo.

        Returns:
            A ``DimensionScore`` on success, or ``None`` if the
            analyzer is not applicable / not available / encounters
            an error.
        """
