"""Domain classification for repository candidates.

Uses rules-based classification + heuristic fallback to map RepoCandidate
metadata (topics, languages, description) to a DomainType.

Classifies candidates discovered through any channel so that the correct
DomainProfile can be applied during scoring (Layer D).

TA3 from Production Readiness Plan v1.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DomainType

if TYPE_CHECKING:
    from github_discovery.models.candidate import RepoCandidate

logger = structlog.get_logger(__name__)


class DomainClassifier:
    """Maps RepoCandidate metadata to DomainType using rules + heuristics.

    Rules are applied in priority order; first match wins.
    Falls back to OTHER when no rules match.

    Classification uses:
    - GitHub topics (highest signal, curated by repo maintainers)
    - Primary language (from GitHub API)
    - Description keywords (supplementary signal)
    """

    # Topic → DomainType mapping. Topics are GitHub-curated and provide
    # strong signal about the repo's purpose.
    _TOPIC_RULES: tuple[tuple[DomainType, tuple[str, ...]], ...] = (
        # ML / AI
        (
            DomainType.ML_LIB,
            (
                "machine-learning",
                "deep-learning",
                "neural-networks",
                "pytorch",
                "tensorflow",
                "keras",
                "huggingface",
                "transformers",
                "llm",
                "large-language-models",
                "computer-vision",
                "natural-language-processing",
                "reinforcement-learning",
                "ai",
                "artificial-intelligence",
                "generative-ai",
                "diffusion-models",
            ),
        ),
        # Web frameworks
        (
            DomainType.WEB_FRAMEWORK,
            (
                "web-framework",
                "http",
                "asgi",
                "wsgi",
                "rest-api",
                "graphql",
                "websocket",
                "server",
                "fastapi",
                "flask",
                "django",
                "rails",
                "laravel",
                "spring",
                "express",
                "nextjs",
                "remix",
                "nuxt",
                "gatsby",
            ),
        ),
        # CLI tools
        (
            DomainType.CLI,
            (
                "cli",
                "command-line",
                "terminal",
                "console",
                "bash",
                "shell",
                "tool",
                "utility",
                "script",
            ),
        ),
        # DevOps / Infrastructure
        (
            DomainType.DEVOPS_TOOL,
            (
                "devops",
                "infrastructure",
                "kubernetes",
                "docker",
                "terraform",
                "ansible",
                "ci-cd",
                "automation",
                "monitoring",
                "logging",
                "observability",
                "deployment",
                "cloud",
                "aws",
                "gcp",
                "azure",
            ),
        ),
        # Security tools
        (
            DomainType.SECURITY_TOOL,
            (
                "security",
                "cryptography",
                "authentication",
                "authorization",
                "oauth",
                "encryption",
                "vulnerability",
                "audit",
                "penetration-testing",
                "infosec",
            ),
        ),
        # Data tools
        (
            DomainType.DATA_TOOL,
            (
                "data-science",
                "data-analysis",
                "etl",
                "pipeline",
                "data-engineering",
                "pandas",
                "numpy",
                "spark",
                "kafka",
                "data-processing",
                "analytics",
            ),
        ),
        # Libraries (general Python/Rust libraries)
        (
            DomainType.LIBRARY,
            (
                "library",
                "package",
                "module",
                "sdk",
                "api",
                "parsing",
                "serialization",
                "template",
                "configuration",
            ),
        ),
        # Testing tools
        (
            DomainType.TEST_TOOL,
            (
                "testing",
                "test-framework",
                "unit-testing",
                "integration-testing",
                "mocking",
                "fixture",
                "tdd",
                "bdd",
            ),
        ),
        # Documentation tools
        (
            DomainType.DOC_TOOL,
            (
                "documentation",
                "docs",
                "markdown",
                "static-site-generator",
                "docs-generator",
                "api-docs",
            ),
        ),
        # Programming language tools
        (
            DomainType.LANG_TOOL,
            (
                "compiler",
                "interpreter",
                "parser",
                "linter",
                "formatter",
                "language-server",
                "ide",
                "editor",
                "syntax-highlighting",
            ),
        ),
    )

    # Language → DomainType mapping (secondary signal).
    _LANGUAGE_RULES: tuple[tuple[DomainType, tuple[str, ...]], ...] = (
        (DomainType.CLI, ("Shell", "Bash")),
        (DomainType.ML_LIB, ("Jupyter Notebook", "Python")),
        (DomainType.LIBRARY, ("Rust", "Go", "C", "C++")),
        (DomainType.WEB_FRAMEWORK, ("JavaScript", "TypeScript", "Ruby", "PHP")),
        (DomainType.DATA_TOOL, ("Python", "R", "SQL")),
        (DomainType.DEVOPS_TOOL, ("HCL", "Dockerfile")),
        (DomainType.SECURITY_TOOL, ("C", "Rust", "Go")),
        (DomainType.TEST_TOOL, ("Python", "JavaScript")),
    )

    # Description keyword → DomainType (tertiary signal, lower priority).
    _DESCRIPTION_RULES: tuple[tuple[DomainType, tuple[str, ...]], ...] = (
        (
            DomainType.ML_LIB,
            (
                "machine learning",
                "deep learning",
                "neural network",
                "llm",
                "large language model",
                "ai model",
                "diffusion",
            ),
        ),
        (
            DomainType.WEB_FRAMEWORK,
            (
                "web framework",
                "rest api",
                "graphql server",
                "http server",
                "microservice",
                "api framework",
            ),
        ),
        (
            DomainType.CLI,
            (
                "command line",
                "cli tool",
                "terminal utility",
                "shell script",
                "command-line interface",
            ),
        ),
        (
            DomainType.DEVOPS_TOOL,
            (
                "kubernetes",
                "docker container",
                "ci/cd",
                "deployment",
                "infrastructure as code",
                "cloud native",
            ),
        ),
        (
            DomainType.SECURITY_TOOL,
            (
                "security",
                "cryptography",
                "encryption",
                "authentication",
                "vulnerability",
                "penetration test",
            ),
        ),
        (
            DomainType.DATA_TOOL,
            (
                "data processing",
                "etl pipeline",
                "data analysis",
                "data engineering",
                "analytics",
            ),
        ),
        (
            DomainType.LIBRARY,
            (
                "utility library",
                "python library",
                "rust crate",
                "go module",
                "software library",
                "package",
            ),
        ),
        (
            DomainType.TEST_TOOL,
            (
                "testing framework",
                "unit test",
                "integration test",
            ),
        ),
    )

    def classify(self, candidate: RepoCandidate) -> DomainType:
        """Classify a repository candidate into a domain type.

        Applies rules in priority order. Returns OTHER if no rules match.

        Args:
            candidate: The repository candidate to classify.

        Returns:
            DomainType matching the candidate's domain.
        """
        # 1. Topics (highest priority — maintainer-curated)
        if candidate.topics:
            for domain, topics in self._TOPIC_RULES:
                for topic in candidate.topics:
                    if topic.lower() in [t.lower() for t in topics]:
                        logger.debug(
                            "domain_classified",
                            full_name=candidate.full_name,
                            domain=domain.value,
                            signal="topic",
                            matched_topic=topic,
                        )
                        return domain

        # 2. Primary language (from GitHub API)
        if candidate.language:
            lang = candidate.language
            for domain, langs in self._LANGUAGE_RULES:
                if lang in langs:
                    logger.debug(
                        "domain_classified",
                        full_name=candidate.full_name,
                        domain=domain.value,
                        signal="language",
                        matched_language=lang,
                    )
                    return domain

        # 3. Description keywords (lower priority, last resort)
        if candidate.description:
            desc_lower = candidate.description.lower()
            for domain, keywords in self._DESCRIPTION_RULES:
                for keyword in keywords:
                    if keyword.lower() in desc_lower:
                        logger.debug(
                            "domain_classified",
                            full_name=candidate.full_name,
                            domain=domain.value,
                            signal="description",
                            matched_keyword=keyword,
                        )
                        return domain

        # No match → OTHER (default profile applied)
        logger.debug(
            "domain_classified",
            full_name=candidate.full_name,
            domain=DomainType.OTHER.value,
            signal="none",
        )
        return DomainType.OTHER


# Module-level singleton for use across discovery channels.
_classifier: DomainClassifier | None = None


def get_classifier() -> DomainClassifier:
    """Get the module-level DomainClassifier singleton."""
    global _classifier  # noqa: PLW0603
    if _classifier is None:
        _classifier = DomainClassifier()
    return _classifier


def classify_candidate(candidate: RepoCandidate) -> DomainType:
    """Convenience function to classify a candidate using the singleton."""
    return get_classifier().classify(candidate)
