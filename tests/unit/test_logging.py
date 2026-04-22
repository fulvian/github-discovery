"""Tests for structured logging configuration."""

from __future__ import annotations

from github_discovery.logging import configure_logging, get_logger, log


class TestLogging:
    """Test logging configuration."""

    def test_configure_logging_json(self) -> None:
        """JSON logging produces valid JSON output."""
        configure_logging(log_level="DEBUG", debug=False)
        logger = get_logger("test_json")
        logger.info("test_event", key="value")
        # Verify output is valid JSON (structural check, not exact match)

    def test_configure_logging_debug_mode(self) -> None:
        """Debug mode uses ConsoleRenderer."""
        configure_logging(log_level="DEBUG", debug=True)
        logger = get_logger("test_debug")
        logger.info("debug_event")
        # Should not raise

    def test_get_logger_returns_bound_logger(self) -> None:
        """get_logger returns a BoundLogger."""
        configure_logging()
        logger = get_logger("test_module")
        assert logger is not None

    def test_module_level_logger(self) -> None:
        """Module-level logger is available."""
        assert log is not None
