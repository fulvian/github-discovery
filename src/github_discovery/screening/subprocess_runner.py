"""Async subprocess execution utility for screening tools.

Wraps asyncio.create_subprocess_exec with configurable timeout,
stdout/stderr capture, return code checking, and structured logging.
Used by Gate 2 tools (gitleaks, scc) that need subprocess execution.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from pathlib import Path

from github_discovery.screening.types import SubprocessResult

logger = structlog.get_logger("github_discovery.screening.subprocess_runner")

_DEFAULT_TIMEOUT = 60.0


class SubprocessRunner:
    """Async subprocess execution utility with timeout and error handling.

    Wraps asyncio.create_subprocess_exec with:
    - Configurable timeout (default 60 seconds)
    - stdout/stderr capture as strings
    - Return code checking
    - Structured logging
    """

    async def run(
        self,
        command: list[str],
        *,
        timeout: float = _DEFAULT_TIMEOUT,
        cwd: str | Path | None = None,
    ) -> SubprocessResult:
        """Execute a command and return structured result.

        Args:
            command: Command and arguments to execute.
            timeout: Maximum execution time in seconds.
            cwd: Working directory for the command.

        Returns:
            SubprocessResult with returncode, stdout, stderr, timed_out.
        """
        logger.debug(
            "subprocess_executing",
            command=" ".join(command),
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
        )

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                logger.warning(
                    "subprocess_timeout",
                    command=" ".join(command),
                    timeout=timeout,
                )
                return SubprocessResult(
                    returncode=-1,
                    stdout="",
                    stderr=f"Command timed out after {timeout}s",
                    timed_out=True,
                )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            if process.returncode != 0:
                logger.debug(
                    "subprocess_nonzero_exit",
                    command=" ".join(command),
                    returncode=process.returncode,
                    stderr=stderr[:500],
                )

            return SubprocessResult(
                returncode=process.returncode or 0,
                stdout=stdout,
                stderr=stderr,
            )

        except FileNotFoundError:
            logger.info(
                "subprocess_not_found",
                command=command[0],
            )
            return SubprocessResult(
                returncode=-1,
                stdout="",
                stderr=f"Command not found: {command[0]}",
            )
