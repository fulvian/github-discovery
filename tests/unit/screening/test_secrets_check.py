"""Tests for secret detection using gitleaks subprocess."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel, DomainType
from github_discovery.models.screening import SecretHygieneScore
from github_discovery.screening.secrets_check import SecretsChecker
from github_discovery.screening.types import SubprocessResult


def _make_candidate() -> RepoCandidate:
    """Build a test RepoCandidate."""
    return RepoCandidate(
        full_name="test-org/test-repo",
        url="https://github.com/test-org/test-repo",
        html_url="https://github.com/test-org/test-repo",
        api_url="https://api.github.com/repos/test-org/test-repo",
        description="Test repo",
        language="Python",
        domain=DomainType.LIBRARY,
        stars=100,
        created_at=datetime(2023, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        owner_login="test-org",
        source_channel=DiscoveryChannel.SEARCH,
    )


def _sarif_with_findings(count: int) -> str:
    """Build SARIF JSON with the given number of findings."""
    results = [{"ruleId": f"rule-{i}", "message": {"text": f"Finding {i}"}} for i in range(count)]
    return json.dumps(
        {
            "$schema": "https://sarif.schema.json",
            "version": "2.1.0",
            "runs": [{"results": results}],
        }
    )


def _make_runner(stdout: str, returncode: int = 0, stderr: str = "") -> AsyncMock:
    """Build a mock SubprocessRunner."""
    runner = AsyncMock()
    runner.run = AsyncMock(
        return_value=SubprocessResult(returncode=returncode, stdout=stdout, stderr=stderr),
    )
    return runner


class TestSecretsChecker:
    """Tests for SecretsChecker."""

    async def test_no_secrets_found(self) -> None:
        """SARIF with 0 results → value=1.0."""
        runner = _make_runner(_sarif_with_findings(0))
        checker = SecretsChecker(subprocess_runner=runner)

        result = await checker.score(_make_candidate(), clone_dir="/tmp/repo")  # noqa: S108

        assert isinstance(result, SecretHygieneScore)
        assert result.value == 1.0
        assert result.confidence == 1.0

    async def test_minor_secrets(self) -> None:
        """SARIF with 2 results → value=0.7."""
        runner = _make_runner(_sarif_with_findings(2))
        checker = SecretsChecker(subprocess_runner=runner)

        result = await checker.score(_make_candidate(), clone_dir="/tmp/repo")  # noqa: S108

        assert result.value == 0.7
        assert result.confidence == 1.0

    async def test_many_secrets(self) -> None:
        """SARIF with 10 results → value=0.1."""
        runner = _make_runner(_sarif_with_findings(10))
        checker = SecretsChecker(subprocess_runner=runner)

        result = await checker.score(_make_candidate(), clone_dir="/tmp/repo")  # noqa: S108

        assert result.value == 0.1

    async def test_gitleaks_not_installed(self) -> None:
        """gitleaks not found → value=0.5, confidence=0.0."""
        runner = _make_runner(
            stdout="",
            returncode=-1,
            stderr="Command not found: gitleaks",
        )
        checker = SecretsChecker(subprocess_runner=runner)

        result = await checker.score(_make_candidate(), clone_dir="/tmp/repo")  # noqa: S108

        assert result.value == 0.5
        assert result.confidence == 0.0

    async def test_no_clone_available(self) -> None:
        """No clone_dir → value=0.5, confidence=0.0."""
        checker = SecretsChecker(subprocess_runner=AsyncMock())

        result = await checker.score(_make_candidate(), clone_dir=None)

        assert result.value == 0.5
        assert result.confidence == 0.0

    async def test_sarif_parsing(self) -> None:
        """_parse_sarif correctly counts findings from SARIF JSON."""
        checker = SecretsChecker()

        sarif = json.dumps(
            {
                "version": "2.1.0",
                "runs": [
                    {"results": [{"ruleId": "r1"}, {"ruleId": "r2"}]},
                    {"results": [{"ruleId": "r3"}]},
                ],
            }
        )
        assert checker._parse_sarif(sarif) == 3

    async def test_sarif_parsing_invalid_json(self) -> None:
        """_parse_sarif returns 0 for invalid JSON."""
        checker = SecretsChecker()
        assert checker._parse_sarif("not json") == 0

    async def test_details_report_findings(self) -> None:
        """Details include findings_count, scan_tool, sarif_parsed."""
        runner = _make_runner(_sarif_with_findings(3))
        checker = SecretsChecker(subprocess_runner=runner)

        result = await checker.score(_make_candidate(), clone_dir="/tmp/repo")  # noqa: S108

        assert result.details["findings_count"] == 3
        assert result.details["scan_tool"] == "gitleaks"
        assert result.details["sarif_parsed"] is True
