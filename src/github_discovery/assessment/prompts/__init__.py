"""Assessment dimension prompt templates."""

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
from github_discovery.models.enums import ScoreDimension

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


def get_prompt(dimension: ScoreDimension) -> str:
    """Get the system prompt for an assessment dimension."""
    prompt_fn = DIMENSION_PROMPTS[dimension]
    return prompt_fn()
