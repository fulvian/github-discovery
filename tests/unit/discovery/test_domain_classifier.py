"""Tests for DomainClassifier — rule-based domain classification (TA3).

Tests topic-based, language-based, and description-based rules
for mapping RepoCandidate metadata to DomainType.
"""

from __future__ import annotations

import pytest

from github_discovery.discovery.domain_classifier import DomainClassifier
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DiscoveryChannel, DomainType


def _make_candidate(
    full_name: str = "test/repo",
    description: str = "A test repository",
    language: str = "Python",
    topics: list[str] | None = None,
) -> RepoCandidate:
    """Create a test RepoCandidate with given metadata."""
    return RepoCandidate(
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        html_url=f"https://github.com/{full_name}",
        api_url=f"https://api.github.com/repos/{full_name}",
        description=description,
        language=language,
        stars=50,
        owner_login="test",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-06-01T00:00:00Z",
        pushed_at="2024-06-01T00:00:00Z",
        source_channel=DiscoveryChannel.SEARCH,
        topics=topics or [],
    )


class TestDomainClassifierML:
    """Tests for ML_LIB domain classification."""

    @pytest.fixture
    def classifier(self) -> DomainClassifier:
        return DomainClassifier()

    def test_ml_from_topics(self, classifier: DomainClassifier) -> None:
        """pytorch topic → ML_LIB."""
        candidate = _make_candidate(topics=["pytorch", "deep-learning"])
        assert classifier.classify(candidate) == DomainType.ML_LIB

    def test_ml_from_tensorflow_topics(self, classifier: DomainClassifier) -> None:
        """tensorflow topic → ML_LIB."""
        candidate = _make_candidate(topics=["tensorflow", "neural-network"])
        assert classifier.classify(candidate) == DomainType.ML_LIB

    def test_ml_from_machine_learning_topic(self, classifier: DomainClassifier) -> None:
        """machine-learning topic → ML_LIB."""
        candidate = _make_candidate(topics=["machine-learning", "nlp"])
        assert classifier.classify(candidate) == DomainType.ML_LIB

    def test_ml_from_llm_topics(self, classifier: DomainClassifier) -> None:
        """llm topic → ML_LIB."""
        candidate = _make_candidate(topics=["llm", "gpt"])
        assert classifier.classify(candidate) == DomainType.ML_LIB


class TestDomainClassifierWeb:
    """Tests for WEB_FRAMEWORK domain classification."""

    @pytest.fixture
    def classifier(self) -> DomainClassifier:
        return DomainClassifier()

    def test_web_from_topics(self, classifier: DomainClassifier) -> None:
        """web-framework topic → WEB_FRAMEWORK."""
        candidate = _make_candidate(topics=["web-framework", "http"])
        assert classifier.classify(candidate) == DomainType.WEB_FRAMEWORK

    def test_web_from_asgi(self, classifier: DomainClassifier) -> None:
        """asgi topic → WEB_FRAMEWORK."""
        candidate = _make_candidate(topics=["asgi", "server"])
        assert classifier.classify(candidate) == DomainType.WEB_FRAMEWORK

    def test_web_from_rest_api_description(self, classifier: DomainClassifier) -> None:
        """REST API in description + no topics → WEB_FRAMEWORK."""
        # Use a language that doesn't match language rules (to avoid ML_LIB)
        candidate = _make_candidate(
            description="REST API framework for building web services",
            topics=[],
            language="Unknown",
        )
        assert classifier.classify(candidate) == DomainType.WEB_FRAMEWORK


class TestDomainClassifierCLI:
    """Tests for CLI domain classification."""

    @pytest.fixture
    def classifier(self) -> DomainClassifier:
        return DomainClassifier()

    def test_cli_from_topics(self, classifier: DomainClassifier) -> None:
        """cli topic → CLI."""
        candidate = _make_candidate(topics=["cli", "command-line"])
        assert classifier.classify(candidate) == DomainType.CLI

    def test_cli_from_description(self, classifier: DomainClassifier) -> None:
        """command-line interface in description → CLI."""
        # Use a language that doesn't match language rules (to avoid ML_LIB)
        # Avoid description keywords that match other rules (like "data processing" → DATA_TOOL)
        candidate = _make_candidate(
            description="command-line interface for managing configurations",
            topics=[],
            language="Unknown",
        )
        assert classifier.classify(candidate) == DomainType.CLI


class TestDomainClassifierDataTool:
    """Tests for DATA_TOOL domain classification."""

    @pytest.fixture
    def classifier(self) -> DomainClassifier:
        return DomainClassifier()

    def test_data_from_topics(self, classifier: DomainClassifier) -> None:
        """data-science topic → DATA_TOOL."""
        candidate = _make_candidate(topics=["data-science", "analytics"])
        assert classifier.classify(candidate) == DomainType.DATA_TOOL

    def test_data_from_etl_pipeline(self, classifier: DomainClassifier) -> None:
        """etl topic → DATA_TOOL."""
        candidate = _make_candidate(topics=["etl", "pipeline"])
        assert classifier.classify(candidate) == DomainType.DATA_TOOL

    def test_data_from_description(self, classifier: DomainClassifier) -> None:
        """data processing in description → DATA_TOOL."""
        candidate = _make_candidate(
            description="data processing pipeline for large datasets",
            topics=[],
            language="Unknown",
        )
        assert classifier.classify(candidate) == DomainType.DATA_TOOL


class TestDomainClassifierOther:
    """Tests for OTHER (fallback) domain classification."""

    @pytest.fixture
    def classifier(self) -> DomainClassifier:
        return DomainClassifier()

    def test_fallback_to_other(self, classifier: DomainClassifier) -> None:
        """Generic repo with no matching signals → OTHER."""
        candidate = _make_candidate(
            description="A collection of miscellaneous utilities",
            topics=["utilities"],
            language="Unknown",
        )
        assert classifier.classify(candidate) == DomainType.OTHER

    def test_no_topics_short_description_other(self, classifier: DomainClassifier) -> None:
        """Repo with no topics and short description → OTHER."""
        candidate = _make_candidate(
            description="Stuff",
            topics=[],
            language="Unknown",
        )
        assert classifier.classify(candidate) == DomainType.OTHER
