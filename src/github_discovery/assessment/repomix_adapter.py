"""Adapts python-repomix for programmatic repository packing.

Downloads a GitHub repo via python-repomix's RepoProcessor, packs it into
a single LLM-friendly text, and applies interface-mode compression for
large repos. Enforces a token budget with character-based truncation.
"""

from __future__ import annotations

import asyncio

import structlog
from repomix import RepomixConfig, RepoProcessor

from github_discovery.assessment.types import RepoContent
from github_discovery.exceptions import AssessmentError

logger = structlog.get_logger(__name__)

# Approximate characters per token for o200k_base encoding.
# Used for fast truncation without encoding the full content.
_CHARS_PER_TOKEN: int = 4


class RepomixAdapter:
    """Adapts python-repomix for programmatic repo packing.

    Packs GitHub repos into LLM-friendly text with:
    - Interface-mode compression for large repos
    - Token budget enforcement (truncation + early-stop)
    - Graceful error handling
    """

    def __init__(
        self,
        *,
        max_tokens: int = 40_000,
        compression: bool = True,
        timeout_seconds: int = 120,
    ) -> None:
        """Initialize the adapter.

        Args:
            max_tokens: Maximum token budget for packed content.
            compression: Whether to enable interface-mode compression.
            timeout_seconds: Timeout for repomix processing in seconds.
        """
        self._max_tokens = max_tokens
        self._compression = compression
        self._timeout = timeout_seconds

    async def pack(self, repo_url: str, full_name: str) -> RepoContent:
        """Pack a repository into LLM-friendly content.

        Uses python-repomix RepoProcessor with:
        1. Interface-mode compression if enabled
        2. Token counting (o200k_base encoding)
        3. Truncation if content exceeds max_tokens

        Args:
            repo_url: GitHub clone URL.
            full_name: Repository full name for context.

        Returns:
            RepoContent with packed content and metadata.

        Raises:
            AssessmentError: If packing fails.
        """
        log = logger.bind(repo_url=repo_url, full_name=full_name)
        log.info("packing_repo", max_tokens=self._max_tokens, compression=self._compression)

        config = self._build_config()

        try:
            processor = RepoProcessor(repo_url, config=config)
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    processor.process,
                    False,  # write_output
                ),
                timeout=self._timeout,
            )
        except TimeoutError as exc:
            raise AssessmentError(
                f"Repomix packing timed out for {full_name} (limit {self._timeout}s)",
                repo_url=repo_url,
            ) from exc
        except AssessmentError:
            raise
        except Exception as exc:
            raise AssessmentError(
                f"Repomix packing failed for {full_name}: {exc}",
                repo_url=repo_url,
            ) from exc

        raw_content = result.output_content
        total_files = result.total_files
        total_tokens = result.total_tokens
        total_chars = result.total_chars

        log.info(
            "repomix_result",
            total_files=total_files,
            total_tokens=total_tokens,
            total_chars=total_chars,
        )

        truncated_content, was_truncated = self._truncate_content(
            raw_content,
            self._max_tokens,
        )

        if was_truncated:
            # Estimate truncated token count to avoid inflating downstream
            # budget checks with the original (pre-truncation) count.
            effective_tokens = len(truncated_content) // _CHARS_PER_TOKEN
            log.warning(
                "content_truncated",
                original_tokens=total_tokens,
                estimated_tokens=effective_tokens,
                max_tokens=self._max_tokens,
            )
        else:
            effective_tokens = total_tokens

        return RepoContent(
            full_name=full_name,
            content=truncated_content,
            total_files=total_files,
            total_tokens=effective_tokens,
            total_chars=total_chars,
            compressed=self._compression,
            truncated=was_truncated,
            clone_url=repo_url,
        )

    def _truncate_content(self, content: str, max_tokens: int) -> tuple[str, bool]:
        """Truncate content to fit within token budget.

        Uses character-based approximation (~4 chars per token)
        for fast truncation without encoding the full content.

        Args:
            content: The packed content string.
            max_tokens: Maximum allowed tokens.

        Returns:
            Tuple of (truncated_content, was_truncated).
        """
        max_chars = max_tokens * _CHARS_PER_TOKEN
        if len(content) <= max_chars:
            return content, False

        truncated = content[:max_chars]
        return truncated, True

    def _build_config(self) -> RepomixConfig:
        """Build RepomixConfig with compression and token counting."""
        config = RepomixConfig()

        # Token counting
        config.output.calculate_tokens = True
        config.token_count.encoding = "o200k_base"

        # Interface-mode compression
        if self._compression:
            config.compression.enabled = True
            config.compression.keep_signatures = True
            config.compression.keep_docstrings = True
            config.compression.keep_interfaces = True

        return config
