"""Tests for LLM provider async context manager lifecycle — T3.4."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from github_discovery.assessment.llm_provider import LLMProvider


class TestProviderLifecycle:
    """Tests for async context manager protocol on LLMProvider."""

    def _make_provider(self) -> LLMProvider:
        """Create a provider with mocked instructor client."""
        with patch("github_discovery.assessment.llm_provider.instructor") as mock_instructor:
            mock_client = MagicMock()
            mock_client.close = AsyncMock()
            mock_instructor.from_openai.return_value = mock_client
            return LLMProvider(
                api_key="test-key",
                base_url="https://test.api/v1",
                model="test-model",
            )

    async def test_aenter_returns_self(self) -> None:
        """__aenter__ returns the provider instance."""
        provider = self._make_provider()
        result = await provider.__aenter__()
        assert result is provider

    async def test_aexit_closes_client(self) -> None:
        """__aexit__ calls close() on the underlying client."""
        provider = self._make_provider()
        await provider.__aexit__(None, None, None)
        # close() was called — the mock client's close should have been called
        provider._client.close.assert_awaited_once()

    async def test_context_manager_protocol(self) -> None:
        """Provider works as async context manager."""
        provider = self._make_provider()
        async with provider as p:
            assert p is provider
            assert p._model == "test-model"
        # After exiting, close should have been called
        provider._client.close.assert_awaited_once()

    async def test_aexit_with_exception(self) -> None:
        """__aexit__ still closes when an exception occurred."""
        provider = self._make_provider()
        await provider.__aexit__(ValueError, ValueError("test"), None)
        provider._client.close.assert_awaited_once()

    async def test_close_sets_none(self) -> None:
        """After close, orchestrator sets provider to None."""
        from github_discovery.assessment.orchestrator import AssessmentOrchestrator
        from github_discovery.config import Settings

        settings = Settings()
        orch = AssessmentOrchestrator(settings)

        # Provider is None initially
        assert orch._provider is None

        # Simulate provider being set
        mock_provider = AsyncMock(spec=LLMProvider)
        orch._provider = mock_provider

        await orch.close()
        assert orch._provider is None
        mock_provider.close.assert_awaited_once()

    async def test_close_idempotent(self) -> None:
        """Close can be called multiple times without error."""
        from github_discovery.assessment.orchestrator import AssessmentOrchestrator
        from github_discovery.config import Settings

        settings = Settings()
        orch = AssessmentOrchestrator(settings)

        mock_provider = AsyncMock(spec=LLMProvider)
        orch._provider = mock_provider

        await orch.close()
        await orch.close()  # Should not raise
        assert orch._provider is None
