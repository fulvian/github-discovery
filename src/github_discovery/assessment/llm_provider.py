"""NanoGPT LLM provider with instructor-based structured output.

Provides LLMProvider, which wraps the openai SDK with a custom base_url
(NanoGPT) and instructor for Pydantic-validated structured output with
automatic retries. Used by the Gate 3 deep assessment pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import instructor
import structlog
from openai import AsyncOpenAI

from github_discovery.assessment.types import LLMBatchOutput, LLMDimensionOutput
from github_discovery.exceptions import AssessmentError
from github_discovery.models.assessment import TokenUsage

if TYPE_CHECKING:
    from github_discovery.models.enums import ScoreDimension

logger = structlog.get_logger(__name__)

_DEFAULT_MAX_TOKENS = 4096


class LLMProvider:
    """NanoGPT LLM provider with instructor structured output.

    Uses openai SDK with custom base_url (NanoGPT) and instructor
    for Pydantic-validated structured output with automatic retries.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://nano-gpt.com/api/subscription/v1",
        model: str = "gpt-4o",
        temperature: float = 0.1,
        max_retries: int = 3,
    ) -> None:
        """Initialize NanoGPT provider with instructor-patched client.

        Args:
            api_key: API key for NanoGPT authentication.
            base_url: NanoGPT API base URL.
            model: Model identifier for LLM calls.
            temperature: Sampling temperature (lower = more deterministic).
            max_retries: Maximum retries for instructor structured output.
        """
        self._model = model
        self._temperature = temperature
        self._max_retries = max_retries
        self._base_url = base_url
        self._token_usage: TokenUsage | None = None

        self._client = instructor.from_openai(
            AsyncOpenAI(
                base_url=base_url,
                api_key=api_key,
            ),
        )

        logger.debug(
            "llm_provider_initialized",
            model=model,
            base_url=base_url,
            temperature=temperature,
            max_retries=max_retries,
        )

    async def assess_dimension(
        self,
        dimension: ScoreDimension,
        system_prompt: str,
        repo_content: str,
    ) -> LLMDimensionOutput:
        """Assess a single dimension via LLM.

        Uses instructor for structured Pydantic output with automatic
        retries on validation failures.

        Args:
            dimension: Which dimension to assess.
            system_prompt: Dimension-specific system prompt.
            repo_content: Packed repo content from repomix.

        Returns:
            LLMDimensionOutput with score, explanation, evidence, confidence.

        Raises:
            AssessmentError: If LLM call fails after retries.
        """
        logger.debug(
            "assessing_dimension",
            dimension=dimension.value,
            content_length=len(repo_content),
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Assess the **{dimension.value}** dimension for the "
                    f"following repository.\n\n{repo_content}"
                ),
            },
        ]

        try:
            result = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                response_model=LLMDimensionOutput,
                max_retries=self._max_retries,
                temperature=self._temperature,
                max_tokens=_DEFAULT_MAX_TOKENS,
            )
        except Exception as exc:
            raise AssessmentError(
                f"LLM assessment failed for dimension '{dimension.value}': {exc}",
                dimension=dimension.value,
            ) from exc

        self._update_token_usage(result)
        logger.info(
            "dimension_assessed",
            dimension=dimension.value,
            score=result.score,
            confidence=result.confidence,
        )
        return result

    async def assess_batch(
        self,
        dimensions: list[ScoreDimension],
        system_prompt: str,
        repo_content: str,
    ) -> LLMBatchOutput:
        """Assess all dimensions in a single LLM call.

        More token-efficient than per-dimension calls. Returns
        per-dimension scores keyed by dimension name string.

        Args:
            dimensions: All dimensions to assess.
            system_prompt: Combined system prompt for all dimensions.
            repo_content: Packed repo content.

        Returns:
            LLMBatchOutput with per-dimension scores.

        Raises:
            AssessmentError: If LLM call fails after retries.
        """
        dimension_names = [d.value for d in dimensions]
        logger.debug(
            "assessing_batch",
            dimensions=dimension_names,
            content_length=len(repo_content),
        )

        dimension_list = ", ".join(dimension_names)
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Assess the following dimensions: {dimension_list}.\n\n{repo_content}"
                ),
            },
        ]

        try:
            result = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                response_model=LLMBatchOutput,
                max_retries=self._max_retries,
                temperature=self._temperature,
                max_tokens=_DEFAULT_MAX_TOKENS,
            )
        except Exception as exc:
            raise AssessmentError(
                f"LLM batch assessment failed for dimensions {dimension_names}: {exc}",
            ) from exc

        self._update_token_usage(result)
        logger.info(
            "batch_assessed",
            dimensions=dimension_names,
            num_scored=len(result.dimensions),
        )
        return result

    async def close(self) -> None:
        """Close the underlying async client."""
        await self._client.close()
        logger.debug("llm_provider_closed")

    @property
    def last_token_usage(self) -> TokenUsage | None:
        """Token usage from the most recent LLM call."""
        return self._token_usage

    def _update_token_usage(self, response: object) -> None:
        """Extract token usage from the raw LLM response metadata.

        Instructor wraps the response; the underlying raw response
        may carry usage stats accessible via ``.raw_response`` or
        as a direct attribute depending on instructor version.
        """
        raw = getattr(response, "raw_response", response)
        usage = getattr(raw, "usage", None)
        if usage is not None:
            self._token_usage = TokenUsage(
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                total_tokens=getattr(usage, "total_tokens", 0) or 0,
                model_used=self._model,
                provider="nanogpt",
            )
        else:
            # No usage data available — keep previous or None
            logger.debug("no_token_usage_in_response")
