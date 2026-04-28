"""NanoGPT LLM provider with instructor-based structured output.

Provides LLMProvider, which wraps the openai SDK with a custom base_url
(NanoGPT) and instructor for Pydantic-validated structured output with
automatic retries. Used by the Gate 3 deep assessment pipeline.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING, TypeVar

import instructor
import structlog
from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)
from tenacity import (
    after_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from github_discovery.assessment.types import LLMBatchOutput, LLMDimensionOutput
from github_discovery.exceptions import AssessmentError
from github_discovery.models.assessment import TokenUsage

if TYPE_CHECKING:
    from github_discovery.models.enums import ScoreDimension

logger = structlog.get_logger(__name__)

_DEFAULT_MAX_TOKENS = 4096

_T = TypeVar("_T")

# Transient errors that should trigger retry with exponential backoff.
# TC5: tenacity retry on 429/5xx/timeout (3 attempt, jittered exponential).
_TRANSIENT_OPENAI_ERRORS = (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    InternalServerError,
)


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
        fallback_model: str | None = None,
        call_timeout: int = 120,
    ) -> None:
        """Initialize NanoGPT provider with instructor-patched client.

        Args:
            api_key: API key for NanoGPT authentication.
            base_url: NanoGPT API base URL.
            model: Model identifier for LLM calls.
            temperature: Sampling temperature (lower = more deterministic).
            max_retries: Maximum retries for instructor structured output.
            fallback_model: Optional fallback model identifier if primary fails.
            call_timeout: Timeout in seconds for each LLM API call.
        """
        self._model = model
        self._temperature = temperature
        self._max_retries = max_retries
        self._base_url = base_url
        self._fallback_model = fallback_model
        self._call_timeout = call_timeout
        self._token_usage: TokenUsage | None = None

        self._openai_client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
        )
        # MD_JSON mode: GLM-5.1 and similar models serialize nested Pydantic
        # objects as JSON strings in tool_call arguments, causing validation
        # errors with the default TOOLS mode. MD_JSON extracts JSON from
        # markdown code blocks — more tolerant of model quirks.
        self._client = instructor.from_openai(
            self._openai_client,
            mode=instructor.Mode.MD_JSON,
        )

        logger.debug(
            "llm_provider_initialized",
            model=model,
            base_url=base_url,
            temperature=temperature,
            max_retries=max_retries,
            call_timeout=call_timeout,
        )

    # ------------------------------------------------------------------
    # Generic LLM call with timeout + fallback model retry + tenacity
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=1, max=30),
        retry=retry_if_exception_type(_TRANSIENT_OPENAI_ERRORS),
        after=after_log(logger, 30),
        reraise=True,
    )
    async def _call_llm_with_retry(
        self,
        response_model: type[_T],
        messages: list[dict[str, str]],
        model: str,
    ) -> _T:
        """Inner LLM call wrapped with tenacity retry for transient errors.

        This is the inner function called by _call_llm. Retries on
        429/5xx/timeout errors with exponential backoff (3 attempts,
        jittered). Instructor max_retries handles validation errors
        separately (only on ValidationError, not on network errors).
        """
        result = await self._client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            response_model=response_model,  # type: ignore[type-var]
            max_retries=self._max_retries,
            temperature=self._temperature,
            max_tokens=_DEFAULT_MAX_TOKENS,
        )
        return result

    async def _call_llm(
        self,
        response_model: type[_T],
        messages: list[dict[str, str]],
        *,
        context_label: str,
        dimension: str | None = None,
    ) -> _T:
        """Execute an LLM call with tenacity retry, timeout, and optional fallback.

        Wraps the instructor-patched client with tenacity retry for
        transient API errors (429/5xx/timeout), asyncio.wait_for for
        hard timeout, and an optional fallback model on persistent failures.

        Args:
            response_model: Pydantic model class for structured output.
            messages: Chat messages for the LLM.
            context_label: Human-readable label for error messages
                (e.g. ``"dimension 'code_quality'"`` or
                ``"dimensions ['code_quality', 'testing']"``).
            dimension: Optional dimension name forwarded to
                :class:`AssessmentError`.

        Returns:
            Structured response validated against *response_model*.

        Raises:
            AssessmentError: If the LLM call fails after retries and
                optional fallback.
        """
        try:
            result = await asyncio.wait_for(
                self._call_llm_with_retry(
                    response_model,
                    messages,
                    model=self._model,
                ),
                timeout=self._call_timeout,
            )
        except TimeoutError:
            raise AssessmentError(
                f"LLM assessment timed out for {context_label} after {self._call_timeout}s",
                dimension=dimension,
            ) from None
        except Exception as exc:
            original_error = AssessmentError(
                f"LLM assessment failed for {context_label}: {exc}",
                dimension=dimension,
            )
            # Attempt fallback model if configured and different from primary
            if self._fallback_model and self._fallback_model != self._model:
                result = await self._call_llm_fallback(
                    response_model=response_model,
                    messages=messages,
                    original_error=original_error,
                    original_exc=exc,
                    context_label=context_label,
                    dimension=dimension,
                )
            else:
                raise original_error from exc

        return result

    async def _call_llm_fallback(
        self,
        response_model: type[_T],
        messages: list[dict[str, str]],
        *,
        original_error: AssessmentError,
        original_exc: Exception,
        context_label: str,
        dimension: str | None = None,
    ) -> _T:
        """Retry an LLM call with the fallback model.

        Called by :meth:`_call_llm` when the primary model fails and a
        fallback model is configured.  On fallback failure the original
        error is re-raised so that callers always see a consistent error
        chain (primary → original).
        """
        try:
            result = await asyncio.wait_for(
                self._call_llm_with_retry(
                    response_model,
                    messages,
                    model=self._fallback_model,  # type: ignore[arg-type]
                ),
                timeout=self._call_timeout,
            )
            logger.info(
                "llm_assessed_with_fallback",
                context_label=context_label,
                fallback_model=self._fallback_model,
            )
        except TimeoutError:
            raise AssessmentError(
                f"LLM assessment timed out with fallback model "
                f"for {context_label} after {self._call_timeout}s",
                dimension=dimension,
            ) from None
        except Exception:
            raise original_error from original_exc

        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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

        result = await self._call_llm(
            LLMDimensionOutput,
            messages,
            context_label=f"dimension '{dimension.value}'",
            dimension=dimension.value,
        )

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

        result = await self._call_llm(
            LLMBatchOutput,
            messages,
            context_label=f"dimensions {dimension_names}",
        )

        self._update_token_usage(result)
        logger.info(
            "batch_assessed",
            dimensions=dimension_names,
            num_scored=len(result.dimensions),
        )
        return result

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying async client.

        Wrapped in try/except to handle clients that don't expose close().
        """
        close_method = getattr(self._openai_client, "close", None)
        if close_method is None:
            logger.debug("llm_provider_close_not_supported")
            return

        maybe_awaitable = close_method()
        if inspect.isawaitable(maybe_awaitable):
            await maybe_awaitable
        logger.debug("llm_provider_closed")

    async def __aenter__(self) -> LLMProvider:
        """Enter async context — initialize client (already done in __init__)."""
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Exit async context — close the underlying client."""
        await self.close()

    @property
    def last_token_usage(self) -> TokenUsage | None:
        """Token usage from the most recent LLM call."""
        return self._token_usage

    def _update_token_usage(self, response: object) -> None:
        """Extract token usage from the raw LLM response metadata.

        Instructor wraps the response; the underlying raw response
        may carry usage stats accessible via ``.raw_response`` or
        as a direct attribute depending on instructor version.

        When the provider doesn't return usage data (e.g., NanoGPT),
        estimate tokens from content length (~4 chars per token).
        Logs the source (api vs estimated) for transparency.
        """
        raw = getattr(response, "raw_response", response)
        usage = getattr(raw, "usage", None)
        source: str

        if usage is not None:
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            total_tokens = getattr(usage, "total_tokens", 0) or 0
            source = "api"
        else:
            # Estimate from content length when provider omits usage
            # (~4 chars per token for o200k_base encoding)
            completion_chars = 0
            if isinstance(response, LLMBatchOutput | LLMDimensionOutput):
                completion_chars = len(str(response.model_dump()))
            prompt_tokens = 0  # Unknown without API data
            completion_tokens = max(1, completion_chars // 4)
            total_tokens = prompt_tokens + completion_tokens
            source = "estimated"

            logger.debug(
                "token_usage_estimated",
                source=source,
                completion_chars=completion_chars,
                estimated_tokens=total_tokens,
            )

        self._token_usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            model_used=self._model,
            provider="nanogpt",
            token_usage_source=source,
        )
