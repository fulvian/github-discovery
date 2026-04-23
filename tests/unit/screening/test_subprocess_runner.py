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
