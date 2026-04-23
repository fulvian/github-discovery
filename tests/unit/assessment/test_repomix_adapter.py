"""Tests for RepomixAdapter — repository packing with mocked repomix.

Uses unittest.mock to mock RepoProcessor since repomix is an external
dependency that requires network access for cloning.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from github_discovery.assessment.repomix_adapter import RepomixAdapter
from github_discovery.assessment.types import RepoContent
from github_discovery.exceptions import AssessmentError


@dataclass
class FakeRepomixResult:
    """Fake result object returned by RepoProcessor.process()."""

    output_content: str
    total_files: int
    total_tokens: int
    total_chars: int


class TestPack:
    """Tests for RepomixAdapter.pack()."""

    async def test_pack_returns_repo_content(self) -> None:
        """pack() returns RepoContent with packed data."""
        adapter = RepomixAdapter(max_tokens=40_000, compression=True)

        fake_result = FakeRepomixResult(
            output_content="src/main.py\ndef hello(): pass",
            total_files=5,
            total_tokens=100,
            total_chars=400,
        )

        with patch(
            "github_discovery.assessment.repomix_adapter.RepoProcessor",
        ) as mock_processor_cls:
            mock_processor = MagicMock()
            mock_processor.process.return_value = fake_result
            mock_processor_cls.return_value = mock_processor

            result = await adapter.pack(
                "https://github.com/test/repo",
                "test/repo",
            )

        assert isinstance(result, RepoContent)
        assert result.full_name == "test/repo"
        assert result.total_files == 5
        assert result.total_tokens == 100
        assert result.total_chars == 400
        assert result.compressed is True
        assert result.truncated is False
        assert result.clone_url == "https://github.com/test/repo"

    async def test_pack_applies_truncation_when_content_large(self) -> None:
        """pack() truncates content when it exceeds token budget."""
        adapter = RepomixAdapter(max_tokens=10, compression=True)

        # 100 chars * ~4 chars/token = ~25 tokens > max_tokens=10
        large_content = "x" * 100
        fake_result = FakeRepomixResult(
            output_content=large_content,
            total_files=5,
            total_tokens=25,
            total_chars=100,
        )

        with patch(
            "github_discovery.assessment.repomix_adapter.RepoProcessor",
        ) as mock_processor_cls:
            mock_processor = MagicMock()
            mock_processor.process.return_value = fake_result
            mock_processor_cls.return_value = mock_processor

            result = await adapter.pack(
                "https://github.com/test/repo",
                "test/repo",
            )

        assert result.truncated is True
        # Truncated content: 10 tokens * 4 chars/token = 40 chars
        assert len(result.content) == 40

    async def test_pack_no_truncation_within_budget(self) -> None:
        """pack() does not truncate when content fits budget."""
        adapter = RepomixAdapter(max_tokens=10_000, compression=True)

        small_content = "small content"
        fake_result = FakeRepomixResult(
            output_content=small_content,
            total_files=1,
            total_tokens=3,
            total_chars=13,
        )

        with patch(
            "github_discovery.assessment.repomix_adapter.RepoProcessor",
        ) as mock_processor_cls:
            mock_processor = MagicMock()
            mock_processor.process.return_value = fake_result
            mock_processor_cls.return_value = mock_processor

            result = await adapter.pack(
                "https://github.com/test/repo",
                "test/repo",
            )

        assert result.truncated is False
        assert result.content == small_content

    async def test_pack_raises_assessment_error_on_repomix_failure(self) -> None:
        """pack() raises AssessmentError when RepoProcessor fails."""
        adapter = RepomixAdapter()

        with patch(
            "github_discovery.assessment.repomix_adapter.RepoProcessor",
        ) as mock_processor_cls:
            mock_processor = MagicMock()
            mock_processor.process.side_effect = RuntimeError("Clone failed")
            mock_processor_cls.return_value = mock_processor

            with pytest.raises(AssessmentError) as exc_info:
                await adapter.pack(
                    "https://github.com/test/repo",
                    "test/repo",
                )

        assert "Repomix packing failed" in str(exc_info.value)

    async def test_pack_without_compression(self) -> None:
        """pack() with compression=False sets compressed=False."""
        adapter = RepomixAdapter(max_tokens=10_000, compression=False)

        fake_result = FakeRepomixResult(
            output_content="content",
            total_files=1,
            total_tokens=1,
            total_chars=7,
        )

        with patch(
            "github_discovery.assessment.repomix_adapter.RepoProcessor",
        ) as mock_processor_cls:
            mock_processor = MagicMock()
            mock_processor.process.return_value = fake_result
            mock_processor_cls.return_value = mock_processor

            result = await adapter.pack(
                "https://github.com/test/repo",
                "test/repo",
            )

        assert result.compressed is False

    async def test_pack_preserves_original_token_count(self) -> None:
        """pack() preserves original total_tokens even when truncated."""
        adapter = RepomixAdapter(max_tokens=10, compression=True)

        large_content = "x" * 200
        fake_result = FakeRepomixResult(
            output_content=large_content,
            total_files=20,
            total_tokens=50,
            total_chars=200,
        )

        with patch(
            "github_discovery.assessment.repomix_adapter.RepoProcessor",
        ) as mock_processor_cls:
            mock_processor = MagicMock()
            mock_processor.process.return_value = fake_result
            mock_processor_cls.return_value = mock_processor

            result = await adapter.pack(
                "https://github.com/test/repo",
                "test/repo",
            )

        # original token count preserved in metadata
        assert result.total_tokens == 50
        assert result.truncated is True


class TestTruncateContent:
    """Tests for RepomixAdapter._truncate_content."""

    def test_within_budget_not_truncated(self) -> None:
        """Content within budget is not truncated."""
        adapter = RepomixAdapter(max_tokens=10_000)
        content = "short content"
        result, was_truncated = adapter._truncate_content(content, 10_000)

        assert result == content
        assert was_truncated is False

    def test_exceeds_budget_is_truncated(self) -> None:
        """Content exceeding budget is truncated."""
        adapter = RepomixAdapter()
        content = "x" * 400  # 400 chars = ~100 tokens
        result, was_truncated = adapter._truncate_content(content, 50)  # 50 tokens = 200 chars

        assert was_truncated is True
        assert len(result) == 200  # 50 * 4 = 200
        assert result == content[:200]

    def test_exact_budget_not_truncated(self) -> None:
        """Content exactly at budget boundary is not truncated."""
        adapter = RepomixAdapter()
        max_tokens = 10
        content = "x" * (max_tokens * 4)  # exactly 40 chars
        result, was_truncated = adapter._truncate_content(content, max_tokens)

        assert was_truncated is False
        assert result == content

    def test_empty_content_not_truncated(self) -> None:
        """Empty content is not truncated."""
        adapter = RepomixAdapter()
        result, was_truncated = adapter._truncate_content("", 10)

        assert result == ""
        assert was_truncated is False


class TestBuildConfig:
    """Tests for RepomixAdapter._build_config."""

    def test_compression_enabled(self) -> None:
        """_build_config with compression=True sets compression flags."""
        adapter = RepomixAdapter(max_tokens=10_000, compression=True)
        config = adapter._build_config()

        assert config.compression.enabled is True
        assert config.compression.keep_signatures is True
        assert config.compression.keep_docstrings is True
        assert config.compression.keep_interfaces is True

    def test_compression_disabled(self) -> None:
        """_build_config with compression=False does not enable compression."""
        adapter = RepomixAdapter(max_tokens=10_000, compression=False)
        config = adapter._build_config()

        assert config.compression.enabled is False

    def test_config_sets_token_counting(self) -> None:
        """_build_config enables token counting."""
        adapter = RepomixAdapter()
        config = adapter._build_config()

        assert config.output.calculate_tokens is True
        assert config.token_count.encoding == "o200k_base"
