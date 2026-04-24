"""Tests for CLI utility helpers."""

from __future__ import annotations

import pytest

from github_discovery.cli.utils import (
    comma_separated_to_list,
    exit_with_error,
    get_console,
    get_output_console,
    resolve_output_format,
    run_async,
)


class TestCommaSeparatedToList:
    """Tests for comma_separated_to_list."""

    def test_basic_split(self) -> None:
        result = comma_separated_to_list("a,b,c")
        assert result == ["a", "b", "c"]

    def test_strips_whitespace(self) -> None:
        result = comma_separated_to_list(" a , b , c ")
        assert result == ["a", "b", "c"]

    def test_filters_empty(self) -> None:
        result = comma_separated_to_list("a,,b,")
        assert result == ["a", "b"]

    def test_single_value(self) -> None:
        result = comma_separated_to_list("single")
        assert result == ["single"]


class TestResolveOutputFormat:
    """Tests for resolve_output_format."""

    def test_override_takes_precedence(self) -> None:
        result = resolve_output_format("json")
        assert result == "json"

    def test_none_falls_back_to_state(self) -> None:
        from github_discovery.cli.app import cli_state

        cli_state.output_format = "markdown"
        result = resolve_output_format(None)
        assert result == "markdown"

    def test_none_and_empty_state_defaults_table(self) -> None:
        from github_discovery.cli.app import cli_state

        cli_state.output_format = ""
        result = resolve_output_format(None)
        assert result == "table"


class TestExitWithError:
    """Tests for exit_with_error."""

    def test_raises_system_exit(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            exit_with_error("test error")
        assert exc_info.value.code == 1

    def test_custom_exit_code(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            exit_with_error("test error", code=42)
        assert exc_info.value.code == 42


class TestRunAsync:
    """Tests for run_async."""

    def test_runs_coroutine(self) -> None:
        async def sample_coro() -> str:
            return "hello"

        result = run_async(sample_coro())
        assert result == "hello"


class TestConsoleHelpers:
    """Tests for get_console and get_output_console."""

    def test_get_console_is_stderr(self) -> None:
        console = get_console()
        assert console.stderr is True

    def test_get_output_console_is_stdout(self) -> None:
        console = get_output_console()
        assert console.stderr is False
