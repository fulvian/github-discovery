"""Tests for assessment dimension prompt templates.

Verifies that all 8 dimension prompts:
- Are registered in DIMENSION_PROMPTS
- Contain required structural elements (evaluation criteria, scoring, output schema)
- Return non-empty strings
- Accept optional domain parameter for domain-specific focus notes
"""

from __future__ import annotations

from github_discovery.assessment.prompts import (
    _DOMAIN_FOCUS,
    DIMENSION_PROMPTS,
    get_prompt,
)
from github_discovery.models.enums import DomainType, ScoreDimension


class TestDimensionPromptsRegistry:
    """Tests for the DIMENSION_PROMPTS registry."""

    def test_all_dimensions_registered(self) -> None:
        """All 8 ScoreDimension values have a registered prompt."""
        for dim in ScoreDimension:
            assert dim in DIMENSION_PROMPTS, f"Missing prompt for {dim.value}"

    def test_registry_count(self) -> None:
        """Registry has exactly 8 prompts (one per dimension)."""
        assert len(DIMENSION_PROMPTS) == len(ScoreDimension)

    def test_all_prompts_are_callable(self) -> None:
        """All registered prompts are callable."""
        for dim, prompt_fn in DIMENSION_PROMPTS.items():
            assert callable(prompt_fn), f"Prompt for {dim.value} is not callable"


class TestDimensionPromptsContent:
    """Tests for prompt content structure across all dimensions."""

    @staticmethod
    def _get_prompt(dim: ScoreDimension) -> str:
        return get_prompt(dim)

    def test_all_prompts_non_empty(self) -> None:
        """All prompts return non-empty strings."""
        for dim in ScoreDimension:
            prompt = self._get_prompt(dim)
            assert isinstance(prompt, str)
            assert len(prompt) > 100, f"Prompt for {dim.value} is too short"

    def test_all_prompts_contain_evaluation_criteria(self) -> None:
        """All prompts contain 'Evaluation Criteria' section."""
        for dim in ScoreDimension:
            prompt = self._get_prompt(dim)
            assert "## Evaluation Criteria" in prompt, (
                f"Prompt for {dim.value} missing 'Evaluation Criteria'"
            )

    def test_all_prompts_contain_scoring_guidelines(self) -> None:
        """All prompts contain 'Scoring Guidelines' section."""
        for dim in ScoreDimension:
            prompt = self._get_prompt(dim)
            assert "## Scoring Guidelines" in prompt, (
                f"Prompt for {dim.value} missing 'Scoring Guidelines'"
            )

    def test_all_prompts_contain_output_requirements(self) -> None:
        """All prompts contain 'Output Requirements' section."""
        for dim in ScoreDimension:
            prompt = self._get_prompt(dim)
            assert "## Output Requirements" in prompt, (
                f"Prompt for {dim.value} missing 'Output Requirements'"
            )

    def test_all_prompts_mention_score_field(self) -> None:
        """All prompts specify the 'score' output field."""
        for dim in ScoreDimension:
            prompt = self._get_prompt(dim)
            assert '"score"' in prompt, (
                f"Prompt for {dim.value} missing 'score' field in output schema"
            )

    def test_all_prompts_mention_explanation_field(self) -> None:
        """All prompts specify the 'explanation' output field."""
        for dim in ScoreDimension:
            prompt = self._get_prompt(dim)
            assert '"explanation"' in prompt, f"Prompt for {dim.value} missing 'explanation' field"

    def test_all_prompts_mention_evidence_field(self) -> None:
        """All prompts specify the 'evidence' output field."""
        for dim in ScoreDimension:
            prompt = self._get_prompt(dim)
            assert '"evidence"' in prompt, f"Prompt for {dim.value} missing 'evidence' field"

    def test_all_prompts_mention_confidence_field(self) -> None:
        """All prompts specify the 'confidence' output field."""
        for dim in ScoreDimension:
            prompt = self._get_prompt(dim)
            assert '"confidence"' in prompt, f"Prompt for {dim.value} missing 'confidence' field"

    def test_all_prompts_mention_dimension_name(self) -> None:
        """Each prompt mentions its dimension name (e.g., 'CODE QUALITY')."""
        dimension_labels: dict[ScoreDimension, str] = {
            ScoreDimension.CODE_QUALITY: "CODE QUALITY",
            ScoreDimension.ARCHITECTURE: "ARCHITECTURE",
            ScoreDimension.TESTING: "TESTING",
            ScoreDimension.DOCUMENTATION: "DOCUMENTATION",
            ScoreDimension.SECURITY: "SECURITY",
            ScoreDimension.MAINTENANCE: "MAINTENANCE",
            ScoreDimension.FUNCTIONALITY: "FUNCTIONAL",
            ScoreDimension.INNOVATION: "INNOVATION",
        }
        for dim, label in dimension_labels.items():
            prompt = self._get_prompt(dim)
            assert label in prompt.upper(), (
                f"Prompt for {dim.value} missing dimension label '{label}'"
            )

    def test_all_prompts_contain_score_range(self) -> None:
        """All prompts mention the 0.0-1.0 score range."""
        for dim in ScoreDimension:
            prompt = self._get_prompt(dim)
            assert "0.0" in prompt and "1.0" in prompt, (
                f"Prompt for {dim.value} missing score range (0.0-1.0)"
            )

    def test_all_prompts_contain_json_example(self) -> None:
        """All prompts contain a JSON output example."""
        for dim in ScoreDimension:
            prompt = self._get_prompt(dim)
            assert "```json" in prompt, f"Prompt for {dim.value} missing JSON example"


class TestGetPromptFunction:
    """Tests for the get_prompt() function."""

    def test_returns_string(self) -> None:
        """get_prompt returns a string."""
        result = get_prompt(ScoreDimension.CODE_QUALITY)
        assert isinstance(result, str)

    def test_returns_different_prompts_for_different_dimensions(self) -> None:
        """Different dimensions return different prompts."""
        prompt_cq = get_prompt(ScoreDimension.CODE_QUALITY)
        prompt_sec = get_prompt(ScoreDimension.SECURITY)
        assert prompt_cq != prompt_sec

    def test_domain_none_returns_base_prompt(self) -> None:
        """get_prompt with domain=None returns the base prompt."""
        base = get_prompt(ScoreDimension.CODE_QUALITY)
        with_none = get_prompt(ScoreDimension.CODE_QUALITY, domain=None)
        assert base == with_none


class TestDomainFocus:
    """Tests for domain-specific prompt focus adjustments."""

    def test_domain_focus_appended_for_known_pair(self) -> None:
        """Known (domain, dimension) pair appends focus note."""
        # CLI + CODE_QUALITY has a domain focus entry
        prompt_base = get_prompt(ScoreDimension.CODE_QUALITY)
        prompt_cli = get_prompt(ScoreDimension.CODE_QUALITY, domain=DomainType.CLI)
        assert len(prompt_cli) > len(prompt_base)
        assert "Domain Focus" in prompt_cli
        assert "CLI Tool" in prompt_cli

    def test_domain_focus_not_appended_for_unknown_pair(self) -> None:
        """Unknown (domain, dimension) pair returns base prompt unchanged."""
        # WEB_FRAMEWORK has no specific focus entries
        prompt_base = get_prompt(ScoreDimension.CODE_QUALITY)
        prompt_web = get_prompt(
            ScoreDimension.CODE_QUALITY,
            domain=DomainType.WEB_FRAMEWORK,
        )
        assert prompt_base == prompt_web

    def test_ml_lib_innovation_has_focus(self) -> None:
        """ML_LIB + INNOVATION has domain-specific focus."""
        prompt = get_prompt(ScoreDimension.INNOVATION, domain=DomainType.ML_LIB)
        assert "ML Library" in prompt

    def test_security_tool_security_has_focus(self) -> None:
        """SECURITY_TOOL + SECURITY has domain-specific focus."""
        prompt = get_prompt(ScoreDimension.SECURITY, domain=DomainType.SECURITY_TOOL)
        assert "Security Tool" in prompt

    def test_devops_maintenance_has_focus(self) -> None:
        """DEVOPS_TOOL + MAINTENANCE has domain-specific focus."""
        prompt = get_prompt(ScoreDimension.MAINTENANCE, domain=DomainType.DEVOPS_TOOL)
        assert "DevOps Tool" in prompt

    def test_domain_focus_registry_has_entries(self) -> None:
        """_DOMAIN_FOCUS registry contains at least some entries."""
        assert len(_DOMAIN_FOCUS) > 0

    def test_all_domain_focus_keys_are_valid(self) -> None:
        """All keys in _DOMAIN_FOCUS are valid (DomainType, ScoreDimension) pairs."""
        for domain, dim in _DOMAIN_FOCUS:
            assert isinstance(domain, DomainType)
            assert isinstance(dim, ScoreDimension)

    def test_all_domain_focus_values_are_non_empty(self) -> None:
        """All domain focus values are non-empty strings."""
        for key, focus_text in _DOMAIN_FOCUS.items():
            assert isinstance(focus_text, str)
            assert len(focus_text) > 20, f"Focus for {key} is too short: {focus_text!r}"

    def test_domain_focus_is_not_added_to_unrelated_dimension(self) -> None:
        """A domain focus for dimension X is not added to dimension Y."""
        # CLI has focus for CODE_QUALITY but not for INNOVATION
        prompt_innovation_cli = get_prompt(
            ScoreDimension.INNOVATION,
            domain=DomainType.CLI,
        )
        prompt_innovation_base = get_prompt(ScoreDimension.INNOVATION)
        assert prompt_innovation_cli == prompt_innovation_base
