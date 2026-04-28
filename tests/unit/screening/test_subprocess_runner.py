"""Tests for the async subprocess runner utility."""

from __future__ import annotations

import pytest

from github_discovery.screening.subprocess_runner import SubprocessRunner


class TestSubprocessRunner:
    """Tests for SubprocessRunner async execution."""

    @pytest.fixture
    def runner(self) -> SubprocessRunner:
        """Create a SubprocessRunner instance."""
        return SubprocessRunner()

    async def test_run_success(self, runner: SubprocessRunner) -> None:
        """Successful command returns returncode=0 with captured stdout."""
        result = await runner.run(["echo", "hello world"])
        assert result.returncode == 0
        assert "hello world" in result.stdout
        assert result.timed_out is False

    async def test_run_captures_stderr(self, runner: SubprocessRunner) -> None:
        """stderr is captured for failing commands."""
        result = await runner.run(
            ["python3", "-c", "import sys; print('error', file=sys.stderr); sys.exit(1)"],
        )
        assert result.returncode == 1
        assert "error" in result.stderr

    async def test_run_nonzero_exit(self, runner: SubprocessRunner) -> None:
        """Non-zero exit code is captured."""
        result = await runner.run(["python3", "-c", "raise SystemExit(42)"])
        assert result.returncode == 42

    async def test_run_timeout(self, runner: SubprocessRunner) -> None:
        """Commands that exceed timeout are killed."""
        result = await runner.run(
            ["python3", "-c", "import time; time.sleep(10)"],
            timeout=0.5,
        )
        assert result.timed_out is True
        assert result.returncode == -1

    async def test_run_command_not_found(self, runner: SubprocessRunner) -> None:
        """Missing command returns FileNotFoundError result."""
        result = await runner.run(["nonexistent_command_that_does_not_exist_12345"])
        assert result.returncode == -1
        assert "not found" in result.stderr.lower() or "nonexistent" in result.stderr.lower()

    async def test_tool_unavailable_dedup_first_warning(self, runner: SubprocessRunner) -> None:
        """First missing tool call adds tool to _unavailable_tools (TB4)."""
        tool_name = "dedup_test_tool_1"
        assert tool_name not in runner._unavailable_tools

        result = await runner.run([tool_name])
        assert result.returncode == -1
        assert tool_name in runner._unavailable_tools

    async def test_tool_unavailable_dedup_repeat(self, runner: SubprocessRunner) -> None:
        """Second call to same missing tool does NOT add duplicate to set (TB4)."""
        tool_name = "dedup_test_tool_2"

        # First call — adds to set
        await runner.run([tool_name])
        assert tool_name in runner._unavailable_tools
        assert len(runner._unavailable_tools) == 1

        # Second call — still only 1 entry in set
        await runner.run([tool_name])
        assert tool_name in runner._unavailable_tools
        assert len(runner._unavailable_tools) == 1

    async def test_tool_unavailable_dedup_multiple_tools(self, runner: SubprocessRunner) -> None:
        """Multiple different missing tools are tracked independently (TB4)."""
        await runner.run(["missing_tool_a"])
        await runner.run(["missing_tool_b"])
        await runner.run(["missing_tool_c"])

        assert "missing_tool_a" in runner._unavailable_tools
        assert "missing_tool_b" in runner._unavailable_tools
        assert "missing_tool_c" in runner._unavailable_tools
        assert len(runner._unavailable_tools) == 3

    async def test_tool_unavailable_dedup_new_runner_clean_state(self) -> None:
        """A new SubprocessRunner starts with an empty unavailable set."""
        fresh_runner = SubprocessRunner()
        assert len(fresh_runner._unavailable_tools) == 0
        assert fresh_runner._unavailable_tools == set()
