"""Tests for LLMProvider — NanoGPT LLM provider with instructor.

Uses unittest.mock.AsyncMock to mock the instructor client
since LLM calls are external dependencies.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github_discovery.assessment.llm_provider import LLMProvider
from github_discovery.assessment.types import LLMBatchOutput, LLMDimensionOutput
from github_discovery.exceptions import AssessmentError
from github_discovery.models.enums import ScoreDimension


def _make_provider() -> LLMProvider:
    """Create an LLMProvider with mocked instructor client."""
    with patch("github_discovery.assessment.llm_provider.instructor") as mock_instructor:
        mock_client = MagicMock()
        mock_client.chat = MagicMock()
        mock_client.chat.completions = MagicMock()
        mock_client.chat.completions.create = AsyncMock()
        mock_client.close = AsyncMock()
        mock_instructor.from_openai.return_value = mock_client

        provider = LLMProvider(
            api_key="test-key",
            base_url="https://test.api/v1",
            model="gpt-4o",
        )
        # Store reference for test assertions
        provider._mock_client = mock_client  # type: ignore[attr-defined]
        return provider


class TestAssessDimension:
    """Tests for LLMProvider.assess_dimension."""

    async def test_returns_llm_dimension_output(self) -> None:
        """assess_dimension returns LLMDimensionOutput with score."""
        provider = _make_provider()
        expected = LLMDimensionOutput(
            score=0.85,
            explanation="Good code quality.",
            evidence=["Type hints present"],
            confidence=0.8,
        )
        provider._mock_client.chat.completions.create.return_value = expected

        result = await provider.assess_dimension(
            ScoreDimension.CODE_QUALITY,
            "Assess code quality.",
            "repo content here",
        )

        assert isinstance(result, LLMDimensionOutput)
        assert result.score == 0.85
        assert result.explanation == "Good code quality."

    async def test_passes_correct_messages(self) -> None:
        """assess_dimension passes system prompt and user content correctly."""
        provider = _make_provider()
        provider._mock_client.chat.completions.create.return_value = LLMDimensionOutput(
            score=0.5,
        )

        await provider.assess_dimension(
            ScoreDimension.TESTING,
            "Assess testing practices.",
            "test content",
        )

        call_args = provider._mock_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")

        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "Assess testing practices."
        assert messages[1]["role"] == "user"
        assert "testing" in messages[1]["content"]

    async def test_uses_correct_response_model(self) -> None:
        """assess_dimension uses LLMDimensionOutput as response_model."""
        provider = _make_provider()
        provider._mock_client.chat.completions.create.return_value = LLMDimensionOutput(
            score=0.5,
        )

        await provider.assess_dimension(
            ScoreDimension.SECURITY,
            "Assess security.",
            "content",
        )

        call_args = provider._mock_client.chat.completions.create.call_args
        assert call_args.kwargs.get("response_model") == LLMDimensionOutput

    async def test_raises_assessment_error_on_failure(self) -> None:
        """assess_dimension raises AssessmentError when LLM call fails."""
        provider = _make_provider()
        provider._mock_client.chat.completions.create.side_effect = Exception("API error")

        with pytest.raises(AssessmentError) as exc_info:
            await provider.assess_dimension(
                ScoreDimension.CODE_QUALITY,
                "prompt",
                "content",
            )

        assert "LLM assessment failed" in str(exc_info.value)

    async def test_sets_max_retries(self) -> None:
        """assess_dimension passes max_retries to client."""
        provider = _make_provider()
        provider._mock_client.chat.completions.create.return_value = LLMDimensionOutput(
            score=0.5,
        )

        await provider.assess_dimension(
            ScoreDimension.CODE_QUALITY,
            "prompt",
            "content",
        )

        call_args = provider._mock_client.chat.completions.create.call_args
        assert call_args.kwargs.get("max_retries") == 3


class TestAssessBatch:
    """Tests for LLMProvider.assess_batch."""

    async def test_returns_llm_batch_output(self) -> None:
        """assess_batch returns LLMBatchOutput with dimensions."""
        provider = _make_provider()
        expected = LLMBatchOutput(
            dimensions={
                "code_quality": LLMDimensionOutput(score=0.8),
            },
            overall_explanation="Good overall.",
        )
        provider._mock_client.chat.completions.create.return_value = expected

        result = await provider.assess_batch(
            [ScoreDimension.CODE_QUALITY, ScoreDimension.TESTING],
            "Assess all dimensions.",
            "content",
        )

        assert isinstance(result, LLMBatchOutput)
        assert "code_quality" in result.dimensions

    async def test_passes_dimension_names_in_prompt(self) -> None:
        """assess_batch includes dimension names in user message."""
        provider = _make_provider()
        provider._mock_client.chat.completions.create.return_value = LLMBatchOutput()

        await provider.assess_batch(
            [ScoreDimension.CODE_QUALITY],
            "system prompt",
            "content",
        )

        call_args = provider._mock_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        user_content = messages[1]["content"]

        assert "code_quality" in user_content

    async def test_uses_batch_response_model(self) -> None:
        """assess_batch uses LLMBatchOutput as response_model."""
        provider = _make_provider()
        provider._mock_client.chat.completions.create.return_value = LLMBatchOutput()

        await provider.assess_batch(
            [ScoreDimension.CODE_QUALITY],
            "prompt",
            "content",
        )

        call_args = provider._mock_client.chat.completions.create.call_args
        assert call_args.kwargs.get("response_model") == LLMBatchOutput

    async def test_raises_assessment_error_on_failure(self) -> None:
        """assess_batch raises AssessmentError when LLM call fails."""
        provider = _make_provider()
        provider._mock_client.chat.completions.create.side_effect = Exception("timeout")

        with pytest.raises(AssessmentError):
            await provider.assess_batch(
                [ScoreDimension.CODE_QUALITY],
                "prompt",
                "content",
            )

    async def test_handles_multiple_dimensions(self) -> None:
        """assess_batch correctly passes multiple dimensions."""
        provider = _make_provider()
        provider._mock_client.chat.completions.create.return_value = LLMBatchOutput()

        dimensions = [ScoreDimension.CODE_QUALITY, ScoreDimension.ARCHITECTURE]
        await provider.assess_batch(dimensions, "prompt", "content")

        call_args = provider._mock_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        user_content = messages[1]["content"]

        assert "code_quality" in user_content
        assert "architecture" in user_content


class TestClose:
    """Tests for LLMProvider.close()."""

    async def test_close_calls_client_close(self) -> None:
        """close() calls the underlying client close method."""
        provider = _make_provider()
        await provider.close()

        provider._mock_client.close.assert_awaited_once()

    async def test_close_is_idempotent(self) -> None:
        """close() can be called multiple times without error."""
        provider = _make_provider()
        await provider.close()
        await provider.close()

        assert provider._mock_client.close.await_count == 2


class TestLastTokenUsage:
    """Tests for LLMProvider.last_token_usage property."""

    def test_initially_none(self) -> None:
        """last_token_usage is None before any LLM call."""
        provider = _make_provider()
        assert provider.last_token_usage is None

    async def test_updated_after_dimension_call(self) -> None:
        """last_token_usage is updated after assess_dimension."""
        provider = _make_provider()

        # Create a proper LLMDimensionOutput with attached raw_response
        mock_usage = SimpleNamespace(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        mock_raw = SimpleNamespace(usage=mock_usage)
        llm_output = LLMDimensionOutput(score=0.8, confidence=0.7)
        # Attach raw_response to the Pydantic model's __dict__
        # (instructor returns the model with raw_response attached)
        object.__setattr__(llm_output, "raw_response", mock_raw)

        provider._mock_client.chat.completions.create.return_value = llm_output

        await provider.assess_dimension(
            ScoreDimension.CODE_QUALITY,
            "prompt",
            "content",
        )

        usage = provider.last_token_usage
        assert usage is not None
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150

    async def test_none_when_no_usage_in_response(self) -> None:
        """last_token_usage is estimated from content when response has no usage info."""
        provider = _make_provider()

        # Response without usage info — use a proper LLMDimensionOutput
        llm_output = LLMDimensionOutput(score=0.8, confidence=0.7)
        object.__setattr__(llm_output, "raw_response", SimpleNamespace(usage=None))

        provider._mock_client.chat.completions.create.return_value = llm_output

        await provider.assess_dimension(
            ScoreDimension.CODE_QUALITY,
            "prompt",
            "content",
        )

        # When API doesn't return usage, we estimate from content length
        assert provider.last_token_usage is not None
        assert provider.last_token_usage.completion_tokens > 0
        assert provider.last_token_usage.prompt_tokens == 0  # Unknown without API data


class TestUpdateTokenUsage:
    """Tests for LLMProvider._update_token_usage."""

    def test_extracts_usage_from_raw_response(self) -> None:
        """_update_token_usage extracts usage from raw_response attribute."""
        provider = _make_provider()

        mock_usage = SimpleNamespace(
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
        )
        mock_raw = SimpleNamespace(usage=mock_usage)
        response = SimpleNamespace(raw_response=mock_raw)

        provider._update_token_usage(response)

        assert provider.last_token_usage is not None
        assert provider.last_token_usage.total_tokens == 300
        assert provider.last_token_usage.model_used == "gpt-4o"
        assert provider.last_token_usage.provider == "nanogpt"

    def test_handles_missing_raw_response(self) -> None:
        """_update_token_usage estimates tokens when response has no raw_response."""
        provider = _make_provider()

        # Response without raw_response attribute — falls back to response itself
        response = SimpleNamespace(usage=None)
        provider._update_token_usage(response)

        # Should estimate tokens from content rather than staying None
        assert provider.last_token_usage is not None
        assert provider.last_token_usage.completion_tokens >= 1

    def test_handles_none_usage_attributes(self) -> None:
        """_update_token_usage treats None attributes as 0."""
        provider = _make_provider()

        mock_usage = SimpleNamespace(
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
        )
        mock_raw = SimpleNamespace(usage=mock_usage)
        response = SimpleNamespace(raw_response=mock_raw)

        provider._update_token_usage(response)

        assert provider.last_token_usage is not None
        assert provider.last_token_usage.prompt_tokens == 0
        assert provider.last_token_usage.completion_tokens == 0
        assert provider.last_token_usage.total_tokens == 0
