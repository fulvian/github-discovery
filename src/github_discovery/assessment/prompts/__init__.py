"""Assessment dimension prompt templates.

Provides per-dimension system prompts for LLM assessment, with optional
domain-specific focus adjustments (Blueprint §21 — progressive deepening).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from github_discovery.assessment.prompts.architecture import (
    get_system_prompt as architecture_prompt,
)
from github_discovery.assessment.prompts.code_quality import (
    get_system_prompt as code_quality_prompt,
)
from github_discovery.assessment.prompts.documentation import (
    get_system_prompt as documentation_prompt,
)
from github_discovery.assessment.prompts.functionality import (
    get_system_prompt as functionality_prompt,
)
from github_discovery.assessment.prompts.innovation import (
    get_system_prompt as innovation_prompt,
)
from github_discovery.assessment.prompts.maintenance import (
    get_system_prompt as maintenance_prompt,
)
from github_discovery.assessment.prompts.security import (
    get_system_prompt as security_prompt,
)
from github_discovery.assessment.prompts.testing import (
    get_system_prompt as testing_prompt,
)
from github_discovery.models.enums import DomainType, ScoreDimension

if TYPE_CHECKING:
    from collections.abc import Callable

DIMENSION_PROMPTS: dict[ScoreDimension, Callable[[], str]] = {
    ScoreDimension.CODE_QUALITY: code_quality_prompt,
    ScoreDimension.ARCHITECTURE: architecture_prompt,
    ScoreDimension.TESTING: testing_prompt,
    ScoreDimension.DOCUMENTATION: documentation_prompt,
    ScoreDimension.SECURITY: security_prompt,
    ScoreDimension.MAINTENANCE: maintenance_prompt,
    ScoreDimension.FUNCTIONALITY: functionality_prompt,
    ScoreDimension.INNOVATION: innovation_prompt,
}

# Domain-specific focus notes appended to dimension prompts.
# Keys are (DomainType, ScoreDimension); values are focus instructions.
# Only entries that add meaningful domain-specific context are listed.
_DOMAIN_FOCUS: dict[tuple[DomainType, ScoreDimension], str] = {
    # CLI tools — user-facing quality matters most
    (DomainType.CLI, ScoreDimension.CODE_QUALITY): (
        "\n\n## Domain Focus: CLI Tool\n"
        "Pay special attention to argument parsing quality, help text clarity, "
        "and exit-code conventions. CLI users interact with error messages more "
        "than API consumers."
    ),
    (DomainType.CLI, ScoreDimension.TESTING): (
        "\n\n## Domain Focus: CLI Tool\n"
        "Prioritize testing of command-line argument combinations, edge cases "
        "in flag parsing, and output formatting tests. Integration tests that "
        "invoke the CLI as a subprocess are especially valuable."
    ),
    # ML libraries — innovation and correctness matter most
    (DomainType.ML_LIB, ScoreDimension.INNOVATION): (
        "\n\n## Domain Focus: ML Library\n"
        "Evaluate whether the library introduces novel model architectures, "
        "training techniques, or data processing pipelines. Compare against "
        "established ML frameworks (PyTorch, TensorFlow, scikit-learn)."
    ),
    (DomainType.ML_LIB, ScoreDimension.FUNCTIONALITY): (
        "\n\n## Domain Focus: ML Library\n"
        "Check for complete training loops, data loading abstractions, model "
        "serialization, GPU/TPU support, and common ML workflows (train, "
        "evaluate, predict, export)."
    ),
    # Security tools — security posture is critical
    (DomainType.SECURITY_TOOL, ScoreDimension.SECURITY): (
        "\n\n## Domain Focus: Security Tool\n"
        "Security tools must themselves be secure. Extra scrutiny for: "
        "input sanitization of target URLs/files, secure handling of "
        "credentials/tokens, and avoidance of command injection in tool outputs."
    ),
    # DevOps tools — reliability and maintenance matter most
    (DomainType.DEVOPS_TOOL, ScoreDimension.MAINTENANCE): (
        "\n\n## Domain Focus: DevOps Tool\n"
        "Evaluate release discipline, backwards compatibility guarantees, "
        "configuration migration paths, and deprecation policies. DevOps tools "
        "are often long-lived dependencies in CI pipelines."
    ),
    (DomainType.DEVOPS_TOOL, ScoreDimension.TESTING): (
        "\n\n## Domain Focus: DevOps Tool\n"
        "Integration tests against real infrastructure (or realistic mocks) "
        "are critical. Check for test coverage of failure modes, retries, "
        "and edge cases in environment configuration."
    ),
    # Language tools — code quality and architecture
    (DomainType.LANG_TOOL, ScoreDimension.CODE_QUALITY): (
        "\n\n## Domain Focus: Language Tool\n"
        "Language tools (parsers, linters, formatters) must handle edge cases "
        "in language syntax. Evaluate robustness of parsing, error recovery, "
        "and correctness of AST transformations."
    ),
    (DomainType.LANG_TOOL, ScoreDimension.TESTING): (
        "\n\n## Domain Focus: Language Tool\n"
        "Check for comprehensive test suites with edge-case inputs, fixture-based "
        "testing against real code samples, and differential testing where "
        "applicable. Test coverage should include malformed input handling."
    ),
    # Data tools — testing and documentation
    (DomainType.DATA_TOOL, ScoreDimension.TESTING): (
        "\n\n## Domain Focus: Data Tool\n"
        "Data tools must handle diverse input formats and edge cases (empty "
        "datasets, schema mismatches, encoding issues). Check for property-based "
        "tests and round-trip tests (serialize → deserialize)."
    ),
    (DomainType.DATA_TOOL, ScoreDimension.DOCUMENTATION): (
        "\n\n## Domain Focus: Data Tool\n"
        "API documentation for data tools must cover schema definitions, "
        "supported formats, transformation semantics, and error handling for "
        "invalid data. Examples should include realistic datasets."
    ),
}


def get_prompt(
    dimension: ScoreDimension,
    domain: DomainType | None = None,
) -> str:
    """Get the system prompt for an assessment dimension.

    Args:
        dimension: The scoring dimension to get a prompt for.
        domain: Optional domain type for domain-specific focus adjustments.
            When provided, a domain-specific note is appended to the base
            prompt if one is defined for this (domain, dimension) pair.

    Returns:
        System prompt string, optionally with domain-specific focus notes.
    """
    prompt_fn = DIMENSION_PROMPTS[dimension]
    prompt = prompt_fn()

    if domain is not None:
        focus = _DOMAIN_FOCUS.get((domain, dimension))
        if focus is not None:
            prompt = prompt + focus

    return prompt
