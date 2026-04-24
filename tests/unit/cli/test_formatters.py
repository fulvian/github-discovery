"""Tests for CLI output formatters."""

from __future__ import annotations

import json

import pytest

from github_discovery.cli.formatters import (
    _format_json,
    _format_table,
    format_csv,
    format_output,
)


class TestFormatOutput:
    """Tests for the format_output dispatcher."""

    def test_unknown_format_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown output format"):
            format_output({}, "xml", "discovery")

    def test_json_format(self) -> None:
        result = format_output({"key": "value"}, "json", "discovery")
        parsed = json.loads(result)
        assert parsed["key"] == "value"

    def test_table_format_discovery(self, sample_discovery_result: dict) -> None:
        result = format_output(sample_discovery_result, "table", "discovery")
        assert "org/repo1" in result
        assert "Discovered Candidates" in result

    def test_markdown_format(self, sample_discovery_result: dict) -> None:
        result = format_output(sample_discovery_result, "markdown", "discovery")
        assert "# Discovery" in result

    def test_yaml_format_is_valid_json(self, sample_discovery_result: dict) -> None:
        result = format_output(sample_discovery_result, "yaml", "discovery")
        # YAML-like output is actually JSON with indent
        parsed = json.loads(result)
        assert parsed["pool_id"] == "pool-abc123"


class TestFormatJson:
    """Tests for _format_json."""

    def test_simple_dict(self) -> None:
        result = _format_json({"a": 1})
        assert json.loads(result) == {"a": 1}

    def test_list(self) -> None:
        result = _format_json([1, 2, 3])
        assert json.loads(result) == [1, 2, 3]

    def test_nested(self) -> None:
        data = {"outer": {"inner": [1, 2]}}
        result = _format_json(data)
        assert json.loads(result) == data


class TestFormatTable:
    """Tests for _format_table."""

    def test_ranking_table(self, sample_ranking_result: dict) -> None:
        result = _format_table(sample_ranking_result, "ranking")
        assert "Repository Ranking" in result
        assert "org/hidden-gem" in result
        assert "💎" in result

    def test_screening_table(self, sample_screening_result: dict) -> None:
        result = _format_table(sample_screening_result, "screening")
        assert "Screening Results" in result
        assert "org/repo1" in result

    def test_session_table(self, sample_session_data: dict) -> None:
        result = _format_table(sample_session_data, "session")
        assert "Session Details" in result
        assert "sess-abc123" in result

    def test_session_list_table(self, sample_session_list: list) -> None:
        result = _format_table(sample_session_list, "session_list")
        assert "Sessions" in result
        assert "sess-abc123" in result

    def test_generic_table_for_unknown_type(self) -> None:
        result = _format_table({"key1": "val1"}, "unknown_type")
        assert "Results" in result

    def test_empty_data_no_crash(self) -> None:
        """Table builders should not crash on empty data."""
        result = _format_table({}, "ranking")
        assert isinstance(result, str)


class TestFormatCsv:
    """Tests for format_csv."""

    def test_basic_csv(self) -> None:
        data = [{"name": "a", "score": 1}, {"name": "b", "score": 2}]
        result = format_csv(data)
        assert "name,score" in result
        assert "a,1" in result

    def test_empty_data(self) -> None:
        result = format_csv([])
        assert result == ""

    def test_custom_columns(self) -> None:
        data = [{"name": "a", "score": 1, "extra": "x"}]
        result = format_csv(data, columns=["name", "score"])
        assert "name,score" in result
        assert "extra" not in result
