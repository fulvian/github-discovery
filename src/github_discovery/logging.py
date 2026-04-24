"""Structured logging configuration for GitHub Discovery."""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(log_level: str = "INFO", debug: bool = False) -> None:
    """Configure structlog for structured JSON logging.

    In debug mode (or when stderr is a TTY), uses ConsoleRenderer
    for human-readable output. In production, uses JSONRenderer for
    machine-parseable logs.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        debug: Whether debug mode is enabled (uses pretty console output).
    """
    # Set stdlib logging level
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            },
        ),
    ]

    if debug or sys.stderr.isatty():
        # Pretty console output for development
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        # JSON output for production
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            *shared_processors,
            renderer,
        ],
    )

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Optional logger name (typically module name).

    Returns:
        A structlog BoundLogger for structured, context-aware logging.
    """
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger


# Module-level logger for convenience
log = get_logger("github_discovery")
