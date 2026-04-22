# GitHub Discovery — Phase 1 Implementation Plan

## Meta

- **Stato**: Draft v1
- **Data**: 2026-04-22
- **Riferimento roadmap**: `docs/roadmaps/github-discovery_foundation_roadmap.md` — Phase 1
- **Riferimento blueprint**: `docs/foundation/github-discovery_foundation_blueprint.md`
- **Riferimento wiki**: `docs/llm-wiki/wiki/` — articoli su tiered pipeline, scoring dimensions, screening gates, domain strategy
- **Durata stimata**: 1-2 settimane
- **Milestone**: M0 — Foundation Ready (completamento con Phase 0)
- **Dipendenza**: Phase 0 completata (tutti gli 11 task verificati)

---

## Indice

1. [Obiettivo](#1-obiettivo)
2. [Task Overview](#2-task-overview)
3. [Task 1.7 — Enums e tipi condivisi (aggiornamento)](#3-task-17--enums-e-tipi-condivisi)
4. [Task 1.1 — Modello `RepoCandidate`](#4-task-11--modello-repocandidate)
5. [Task 1.2 — Modelli screening Gate 1](#5-task-12--modelli-screening-gate-1)
6. [Task 1.3 — Modelli screening Gate 2](#6-task-13--modelli-screening-gate-2)
7. [Task 1.4 — Modelli deep assessment Gate 3](#7-task-14--modelli-deep-assessment-gate-3)
8. [Task 1.5 — Modelli scoring & ranking](#8-task-15--modelli-scoring--ranking)
9. [Task 1.8 — Modello Feature Store](#9-task-18--modello-feature-store)
10. [Task 1.6 — Modelli API request/response](#10-task-16--modelli-api-requestresponse)
11. [Task 1.9 — Modelli supporto agentico](#11-task-19--modelli-supporto-agentico)
12. [Sequenza di implementazione](#12-sequenza-di-implementazione)
13. [Test plan](#13-test-plan)
14. [Criteri di accettazione](#14-criteri-di-accettazione)
15. [Rischi e mitigazioni](#15-rischi-e-mitigazioni)
16. [Verifica Context7 completata](#16-verifica-context7-completata)

---

## 1) Obiettivo

Definire tutti i modelli Pydantic v2 che costituiscono il vocabolario del dominio GitHub Discovery. Ogni fase successiva (Discovery, Screening, Assessment, Scoring, API, MCP) dipende da questi tipi.

Al completamento della Phase 1:

- Tutti i modelli Pydantic passano `mypy --strict`
- Serializzazione JSON round-trip per ogni modello
- Validator Pydantic operativi (range scores, required fields, computed fields)
- Enum allineati con il blueprint §7 (8 dimensioni) e §16 (gate features)
- Il `models/__init__.py` esporta l'intero vocabolario del dominio
- I modelli API sono compatibili con FastAPI serialization

---

## 2) Task Overview

| Task ID | Task | Priorità | Dipendenze | Output verificabile |
|---------|------|----------|------------|---------------------|
| 1.7 | Enums e tipi condivisi (aggiornamento) | Critica | Phase 0 | ScoreDimension allineato con blueprint §7 |
| 1.1 | Modello `RepoCandidate` | Critica | 1.7 | Istanziabile da dict GitHub API JSON |
| 1.2 | Modelli screening Gate 1 | Critica | 1.1, 1.7 | 7 sottoscore + MetadataScreenResult |
| 1.3 | Modelli screening Gate 2 | Critica | 1.1, 1.7 | 4 sottoscore + StaticScreenResult |
| 1.4 | Modelli deep assessment Gate 3 | Critica | 1.1, 1.7 | 8 DimensionScore + DeepAssessmentResult |
| 1.5 | Modelli scoring & ranking | Critica | 1.2, 1.3, 1.4 | ScoreResult, ValueScore, RankedRepo, ExplainabilityReport, DomainProfile |
| 1.8 | Modello Feature Store | Alta | 1.1 | RepoFeatures con SHA dedup |
| 1.6 | Modelli API request/response | Alta | 1.1-1.5 | Compatibili FastAPI, pagination |
| 1.9 | Modelli supporto agentico | Alta | 1.1-1.5 | MCPToolResult, DiscoverySession |

**Nota sulla numerazione**: Il task 1.7 (Enums) è elencato per primo perché rappresenta un prerequisito trasversale — gli enum devono essere allineati con il blueprint prima di costruire i modelli che li referenziano. La numerazione segue la roadmap ma la sequenza di implementazione (§12) riflette le dipendenze reali.

---

## 3) Task 1.7 — Enums e tipi condivisi

### Obiettivo

Allineare gli enum esistenti con il blueprint §7 (8 dimensioni di valutazione) e aggiungere tipi condivisi necessari per i modelli successivi. Gli enum sono stati creati in Phase 0 ma `ScoreDimension` non corrisponde esattamente alle 8 dimensioni del blueprint.

### Modifiche a `src/github_discovery/models/enums.py`

**Problema riscontrato**: L'enum `ScoreDimension` esistente ha `COMMUNITY` e `NOVELTY`, mentre il blueprint §7 specifica esplicitamente 8 dimensioni:
1. Code Quality → `CODE_QUALITY` ✓
2. Architecture & Modularity → `ARCHITECTURE` ✓
3. Testability & Verification → `TESTING` ✓
4. Documentation & Developer Experience → `DOCUMENTATION` ✓
5. Maintenance & Project Operations → `MAINTENANCE` ✓
6. Security & Supply Chain Hygiene → `SECURITY` ✓
7. **Functional Completeness** → `COMMUNITY` ✗ (non corrisponde)
8. **Innovation / Distinctiveness** → `NOVELTY` (accettabile, ma `INNOVATION` è più chiaro)

**Soluzione**: Allineare `ScoreDimension` con il blueprint.

```python
"""Domain enumerations for GitHub Discovery.

Defines the core enums used across the scoring pipeline:
DomainType, GateLevel, ScoreDimension, DiscoveryChannel.
"""

from __future__ import annotations

from enum import StrEnum


class DomainType(StrEnum):
    """Repository domain types for domain-specific scoring."""

    CLI = "cli"
    WEB_FRAMEWORK = "web_framework"
    DATA_TOOL = "data_tool"
    LIBRARY = "library"
    ML_LIB = "ml_lib"
    DEVOPS_TOOL = "devops_tool"
    SECURITY_TOOL = "security_tool"
    LANG_TOOL = "lang_tool"
    TEST_TOOL = "test_tool"
    DOC_TOOL = "doc_tool"
    OTHER = "other"


class GateLevel(StrEnum):
    """Pipeline gate levels."""

    DISCOVERY = "0"
    METADATA = "1"
    STATIC_SECURITY = "2"
    DEEP_ASSESSMENT = "3"


class ScoreDimension(StrEnum):
    """Scoring dimensions for repository evaluation.

    Aligned with Blueprint §7 — 8 evaluation dimensions:
    1. Code Quality (20% default)
    2. Architecture & Modularity (15%)
    3. Testability & Verification (15%)
    4. Documentation & Developer Experience (10%)
    5. Maintenance & Project Operations (15%)
    6. Security & Supply Chain Hygiene (10%)
    7. Functional Completeness (10%)
    8. Innovation & Distinctiveness (5%)
    """

    CODE_QUALITY = "code_quality"
    ARCHITECTURE = "architecture"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    SECURITY = "security"
    MAINTENANCE = "maintenance"
    FUNCTIONALITY = "functionality"
    INNOVATION = "innovation"


class DiscoveryChannel(StrEnum):
    """Discovery channels for candidate repository search."""

    SEARCH = "search"
    CODE_SEARCH = "code_search"
    DEPENDENCY = "dependency"
    REGISTRY = "registry"
    AWESOME_LIST = "awesome_list"
    SEED_EXPANSION = "seed_expansion"


class CandidateStatus(StrEnum):
    """Status of a repo candidate through the pipeline."""

    DISCOVERED = "discovered"
    SCREENING_GATE1 = "screening_gate1"
    SCREENING_GATE2 = "screening_gate2"
    GATE1_PASSED = "gate1_passed"
    GATE1_FAILED = "gate1_failed"
    GATE2_PASSED = "gate2_passed"
    GATE2_FAILED = "gate2_failed"
    ASSESSING = "assessing"
    ASSESSED = "assessed"
    RANKED = "ranked"
    EXCLUDED = "excluded"
```

**Nuovo enum aggiunto**: `CandidateStatus` traccia lo stato di un candidato attraverso la pipeline. Necessario per il pool manager (Phase 2) e il Feature Store (Task 1.8).

### Impatto sulle modifiche Phase 0

Le seguenti modifiche sono necessarie per l'allineamento:

1. **`enums.py`**: Sostituire `COMMUNITY` → `FUNCTIONALITY`, `NOVELTY` → `INNOVATION`
2. **`models/mcp_spec.py`**: Aggiornare eventuali riferimenti a `ScoreDimension.NOVELTY` → `ScoreDimension.INNOVATION`
3. **`tests/unit/test_models/test_enums.py`**: Aggiornare test per le nuove values
4. **`models/__init__.py`**: Aggiungere `CandidateStatus` agli exports

### Test: aggiornamento `tests/unit/test_models/test_enums.py`

```python
"""Tests for domain enumerations."""

from __future__ import annotations

from github_discovery.models.enums import (
    CandidateStatus,
    DiscoveryChannel,
    DomainType,
    GateLevel,
    ScoreDimension,
)


class TestScoreDimension:
    """Test ScoreDimension alignment with Blueprint §7."""

    def test_exactly_8_dimensions(self) -> None:
        """Blueprint §7 defines exactly 8 evaluation dimensions."""
        assert len(ScoreDimension) == 8

    def test_code_quality_present(self) -> None:
        """Code Quality dimension exists."""
        assert ScoreDimension.CODE_QUALITY == "code_quality"

    def test_functionality_present(self) -> None:
        """Functional Completeness dimension exists (Blueprint §7 #7)."""
        assert ScoreDimension.FUNCTIONALITY == "functionality"

    def test_innovation_present(self) -> None:
        """Innovation dimension exists (Blueprint §7 #8)."""
        assert ScoreDimension.INNOVATION == "innovation"

    def test_all_dimensions_unique(self) -> None:
        """All dimension values are unique."""
        values = [d.value for d in ScoreDimension]
        assert len(values) == len(set(values))


class TestDomainType:
    """Test DomainType enum."""

    def test_core_domains_present(self) -> None:
        """Core domains from Blueprint §10 exist."""
        assert DomainType.CLI == "cli"
        assert DomainType.WEB_FRAMEWORK == "web_framework"
        assert DomainType.LIBRARY == "library"
        assert DomainType.OTHER == "other"

    def test_exactly_11_domains(self) -> None:
        """All defined domain types present."""
        assert len(DomainType) == 11


class TestGateLevel:
    """Test GateLevel enum."""

    def test_four_gates(self) -> None:
        """Four gate levels (0-3) per Blueprint §16."""
        assert len(GateLevel) == 4
        assert GateLevel.DISCOVERY == "0"
        assert GateLevel.DEEP_ASSESSMENT == "3"


class TestDiscoveryChannel:
    """Test DiscoveryChannel enum."""

    def test_six_channels(self) -> None:
        """Six discovery channels per Blueprint §6."""
        assert len(DiscoveryChannel) == 6

    def test_channels_match_blueprint(self) -> None:
        """Channels match Blueprint §6 Layer A."""
        channels = {c.value for c in DiscoveryChannel}
        expected = {"search", "code_search", "dependency", "registry", "awesome_list", "seed_expansion"}
        assert channels == expected


class TestCandidateStatus:
    """Test CandidateStatus enum."""

    def test_status_values(self) -> None:
        """Candidate statuses track pipeline progression."""
        assert CandidateStatus.DISCOVERED == "discovered"
        assert CandidateStatus.RANKED == "ranked"
        assert CandidateStatus.EXCLUDED == "excluded"

    def test_pipeline_ordering(self) -> None:
        """Statuses represent a logical pipeline flow."""
        statuses = list(CandidateStatus)
        assert statuses[0] == CandidateStatus.DISCOVERED
        assert statuses[-1] == CandidateStatus.EXCLUDED
```

### Verifica

```bash
mypy src/github_discovery/models/enums.py --strict
pytest tests/unit/test_models/test_enums.py -v
```

---

## 4) Task 1.1 — Modello `RepoCandidate`

### Obiettivo

Modello centrale della pipeline: rappresenta un repository GitHub candidato alla valutazione. Contiene metadata dal GitHub API, il canale di discovery, e lo score preliminare. È il tipo che fluisce attraverso tutti i gate.

### Implementazione: `src/github_discovery/models/candidate.py`

```python
"""Repository candidate models for the discovery pipeline.

RepoCandidate is the central model that flows through all gates:
Gate 0 (discovery) → Gate 1 (metadata screening) → Gate 2 (static/security)
→ Gate 3 (deep assessment) → Layer D (scoring/ranking).

Stars are context only, never a primary scoring signal (Blueprint §3).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl

from github_discovery.models.enums import CandidateStatus, DiscoveryChannel, DomainType


class RepoCandidate(BaseModel):
    """A GitHub repository candidate for quality evaluation.

    Fields are derived from GitHub REST API repository endpoint.
    Stars are included as context only — they must never be used
    as a primary ranking signal (Blueprint §3, §15).

    This model is immutable after creation: pipeline stages add
    results via separate models (MetadataScreenResult, etc.)
    linked by `full_name` and `commit_sha`.
    """

    # --- Identity ---
    full_name: str = Field(
        description="Repository full name (owner/repo)",
        examples=["python/cpython", "pallets/flask"],
    )
    url: str = Field(
        description="GitHub repository URL",
        examples=["https://github.com/python/cpython"],
    )
    html_url: str = Field(
        description="GitHub HTML URL",
        examples=["https://github.com/python/cpython"],
    )
    api_url: str = Field(
        description="GitHub API URL for this repository",
        examples=["https://api.github.com/repos/python/cpython"],
    )

    # --- Description & Classification ---
    description: str = Field(
        default="",
        description="Repository description",
    )
    language: str | None = Field(
        default=None,
        description="Primary programming language",
        examples=["Python", "TypeScript", "Rust"],
    )
    languages: dict[str, int] = Field(
        default_factory=dict,
        description="Language breakdown {name: bytes_of_code}",
    )
    topics: list[str] = Field(
        default_factory=list,
        description="Repository topics/tags",
    )
    domain: DomainType = Field(
        default=DomainType.OTHER,
        description="Inferred domain type for domain-specific scoring",
    )

    # --- Context Signals (NOT primary ranking criteria) ---
    stars: int = Field(
        default=0,
        ge=0,
        description="Star count (CONTEXT ONLY — never primary signal)",
    )
    forks_count: int = Field(
        default=0,
        ge=0,
        description="Fork count (context signal)",
    )
    watchers_count: int = Field(
        default=0,
        ge=0,
        description="Watcher count (context signal)",
    )
    subscribers_count: int = Field(
        default=0,
        ge=0,
        description="Subscriber count (context signal)",
    )

    # --- Activity Signals ---
    open_issues_count: int = Field(
        default=0,
        ge=0,
        description="Number of open issues",
    )
    created_at: datetime = Field(
        description="Repository creation timestamp",
    )
    updated_at: datetime = Field(
        description="Last update timestamp",
    )
    pushed_at: datetime | None = Field(
        default=None,
        description="Last push timestamp",
    )

    # --- Repository Metadata ---
    license_info: dict[str, object] | None = Field(
        default=None,
        description="License information from GitHub API (spdx_id, name, url)",
    )
    default_branch: str = Field(
        default="main",
        description="Default branch name",
    )
    size_kb: int = Field(
        default=0,
        ge=0,
        description="Repository size in kilobytes",
    )
    archived: bool = Field(
        default=False,
        description="Whether the repository is archived",
    )
    disabled: bool = Field(
        default=False,
        description="Whether the repository is disabled",
    )
    is_fork: bool = Field(
        default=False,
        description="Whether this is a fork",
    )
    is_template: bool = Field(
        default=False,
        description="Whether this is a template repository",
    )
    has_issues: bool = Field(
        default=True,
        description="Whether issues are enabled",
    )
    has_wiki: bool = Field(
        default=True,
        description="Whether wiki is enabled",
    )
    has_pages: bool = Field(
        default=False,
        description="Whether GitHub Pages is enabled",
    )
    has_discussions: bool = Field(
        default=False,
        description="Whether discussions are enabled",
    )

    # --- Organization / Owner ---
    owner_login: str = Field(
        description="Repository owner login",
    )
    owner_type: str = Field(
        default="User",
        description="Owner type (User or Organization)",
    )

    # --- Pipeline State ---
    source_channel: DiscoveryChannel = Field(
        description="Discovery channel that found this candidate",
    )
    discovery_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Preliminary score from discovery (Gate 0)",
    )
    discovered_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when this candidate was discovered",
    )
    commit_sha: str = Field(
        default="",
        description="Latest commit SHA (for dedup and caching)",
    )
    status: CandidateStatus = Field(
        default=CandidateStatus.DISCOVERED,
        description="Current pipeline status of this candidate",
    )

    @property
    def owner_name(self) -> str:
        """Extract owner from full_name."""
        return self.full_name.split("/")[0] if "/" in self.full_name else self.full_name

    @property
    def repo_name(self) -> str:
        """Extract repo name from full_name."""
        return self.full_name.split("/")[1] if "/" in self.full_name else self.full_name

    @property
    def is_archived_or_disabled(self) -> bool:
        """Check if repo should be excluded from evaluation."""
        return self.archived or self.disabled

    @property
    def is_active(self) -> bool:
        """Check if repo has recent activity (within last 365 days)."""
        if self.pushed_at is None:
            return False
        now = datetime.now(UTC)
        delta = (now - self.pushed_at).days
        return delta <= 365


class CandidatePool(BaseModel):
    """A pool of discovered repository candidates.

    Created by the discovery orchestrator (Phase 2), consumed
    by screening (Phase 3) and assessment (Phase 4).
    """

    pool_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique pool identifier",
    )
    query: str = Field(
        default="",
        description="Original discovery query",
    )
    channels_used: list[DiscoveryChannel] = Field(
        default_factory=list,
        description="Discovery channels that contributed to this pool",
    )
    candidates: list[RepoCandidate] = Field(
        default_factory=list,
        description="Pool of discovered candidates",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Pool creation timestamp",
    )
    session_id: str | None = Field(
        default=None,
        description="Associated session ID for cross-session workflows",
    )

    @property
    def total_count(self) -> int:
        """Total number of candidates in pool."""
        return len(self.candidates)

    @property
    def unique_full_names(self) -> set[str]:
        """Unique repository full names in pool."""
        return {c.full_name for c in self.candidates}

    @property
    def domain_distribution(self) -> dict[str, int]:
        """Count of candidates per domain type."""
        distribution: dict[str, int] = {}
        for c in self.candidates:
            key = c.domain.value
            distribution[key] = distribution.get(key, 0) + 1
        return distribution
```

**Giustificazioni**:

- **`stars` come campo documentato come "CONTEXT ONLY"**: Il modello cattura i dati GitHub API ma il campo è etichettato esplicitamente. Il anti-star bias è enforceato nello scoring engine (Phase 5), non nel modello dati.
- **`domain: DomainType`**: Ogni candidato ha un dominio inferito per intra-domain ranking. Il default è `OTHER` — la classificazione domain avviene durante la discovery.
- **`commit_sha`**: Chiave per il Feature Store dedup (Blueprint §16.5 caching obbligatorio per commit SHA).
- **`status: CandidateStatus`**: Traccia la posizione del candidato nella pipeline.
- **`CandidatePool`**: Aggrega i candidati con metadati della query di discovery. È l'output di Gate 0.
- **Properties**: Calcoli derivati (non persistiti nel JSON) per comodità senza costo di serializzazione.

### Test: `tests/unit/test_models/test_candidate.py`

```python
"""Tests for repository candidate models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from github_discovery.models.candidate import CandidatePool, RepoCandidate
from github_discovery.models.enums import CandidateStatus, DiscoveryChannel, DomainType


def _make_candidate(**overrides: object) -> RepoCandidate:
    """Create a test candidate with sensible defaults."""
    defaults = {
        "full_name": "test/repo",
        "url": "https://github.com/test/repo",
        "html_url": "https://github.com/test/repo",
        "api_url": "https://api.github.com/repos/test/repo",
        "description": "A test repository",
        "language": "Python",
        "topics": ["testing", "quality"],
        "domain": DomainType.LIBRARY,
        "stars": 42,
        "forks_count": 5,
        "open_issues_count": 10,
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 4, 1, tzinfo=UTC),
        "pushed_at": datetime(2026, 4, 15, tzinfo=UTC),
        "license_info": {"spdx_id": "MIT", "name": "MIT License"},
        "default_branch": "main",
        "size_kb": 1024,
        "owner_login": "test",
        "source_channel": DiscoveryChannel.SEARCH,
        "discovery_score": 0.75,
    }
    return RepoCandidate(**{**defaults, **overrides})


class TestRepoCandidate:
    """Test RepoCandidate model."""

    def test_create_from_defaults(self) -> None:
        """Candidate can be created with required fields."""
        candidate = _make_candidate()
        assert candidate.full_name == "test/repo"
        assert candidate.language == "Python"
        assert candidate.domain == DomainType.LIBRARY
        assert candidate.status == CandidateStatus.DISCOVERED

    def test_json_round_trip(self) -> None:
        """Candidate serializes to/from JSON."""
        candidate = _make_candidate()
        json_str = candidate.model_dump_json()
        restored = RepoCandidate.model_validate_json(json_str)
        assert restored.full_name == candidate.full_name
        assert restored.stars == candidate.stars
        assert restored.source_channel == DiscoveryChannel.SEARCH

    def test_stars_default_zero(self) -> None:
        """Stars default to 0 and are non-negative."""
        candidate = _make_candidate(stars=0)
        assert candidate.stars == 0

    def test_stars_negative_raises(self) -> None:
        """Stars cannot be negative."""
        with pytest.raises(Exception):
            _make_candidate(stars=-1)

    def test_discovery_score_range(self) -> None:
        """Discovery score must be between 0.0 and 1.0."""
        with pytest.raises(Exception):
            _make_candidate(discovery_score=1.5)
        with pytest.raises(Exception):
            _make_candidate(discovery_score=-0.1)

    def test_owner_name_property(self) -> None:
        """owner_name extracts owner from full_name."""
        candidate = _make_candidate(full_name="pallets/flask")
        assert candidate.owner_name == "pallets"

    def test_repo_name_property(self) -> None:
        """repo_name extracts repo from full_name."""
        candidate = _make_candidate(full_name="pallets/flask")
        assert candidate.repo_name == "flask"

    def test_is_archived_or_disabled(self) -> None:
        """Archived or disabled repos are flagged."""
        assert _make_candidate(archived=True).is_archived_or_disabled is True
        assert _make_candidate(disabled=True).is_archived_or_disabled is True
        assert _make_candidate(archived=False, disabled=False).is_archived_or_disabled is False

    def test_is_active(self) -> None:
        """Repo with push within 365 days is active."""
        recent = datetime.now(UTC) - timedelta(days=30)
        old = datetime.now(UTC) - timedelta(days=400)
        assert _make_candidate(pushed_at=recent).is_active is True
        assert _make_candidate(pushed_at=old).is_active is False
        assert _make_candidate(pushed_at=None).is_active is False

    def test_from_github_api_dict(self) -> None:
        """Candidate can be created from a GitHub API response dict."""
        gh_response = {
            "full_name": "python/cpython",
            "url": "https://api.github.com/repos/python/cpython",
            "html_url": "https://github.com/python/cpython",
            "api_url": "https://api.github.com/repos/python/cpython",
            "description": "The Python programming language",
            "language": "Python",
            "topics": ["python", "interpreter"],
            "stargazers_count": 65000,
            "forks_count": 25000,
            "open_issues_count": 1000,
            "created_at": "2010-01-01T00:00:00Z",
            "updated_at": "2026-04-22T00:00:00Z",
            "pushed_at": "2026-04-22T00:00:00Z",
            "license": {"spdx_id": "PSF-2.0", "name": "Python Software Foundation License"},
            "default_branch": "main",
            "size": 500000,
            "archived": False,
            "disabled": False,
            "fork": False,
            "is_template": False,
            "has_issues": True,
            "has_wiki": True,
            "has_pages": False,
            "has_discussions": True,
            "owner": {"login": "python", "type": "Organization"},
            "owner_login": "python",
            "owner_type": "Organization",
            "source_channel": "search",
            "discovery_score": 0.9,
        }
        candidate = RepoCandidate.model_validate(gh_response)
        assert candidate.full_name == "python/cpython"
        assert candidate.stars == 65000


class TestCandidatePool:
    """Test CandidatePool model."""

    def test_empty_pool(self) -> None:
        """Empty pool can be created."""
        pool = CandidatePool(query="test")
        assert pool.total_count == 0
        assert pool.unique_full_names == set()

    def test_pool_with_candidates(self) -> None:
        """Pool tracks candidates correctly."""
        candidates = [
            _make_candidate(full_name="user/repo1"),
            _make_candidate(full_name="user/repo2"),
        ]
        pool = CandidatePool(query="python testing", candidates=candidates)
        assert pool.total_count == 2
        assert len(pool.unique_full_names) == 2

    def test_domain_distribution(self) -> None:
        """Pool computes domain distribution."""
        candidates = [
            _make_candidate(full_name="a/lib1", domain=DomainType.LIBRARY),
            _make_candidate(full_name="a/lib2", domain=DomainType.LIBRARY),
            _make_candidate(full_name="a/cli1", domain=DomainType.CLI),
        ]
        pool = CandidatePool(candidates=candidates)
        dist = pool.domain_distribution
        assert dist["library"] == 2
        assert dist["cli"] == 1

    def test_pool_json_round_trip(self) -> None:
        """Pool serializes to/from JSON."""
        pool = CandidatePool(
            query="python static analysis",
            channels_used=[DiscoveryChannel.SEARCH, DiscoveryChannel.REGISTRY],
            candidates=[_make_candidate()],
        )
        json_str = pool.model_dump_json()
        restored = CandidatePool.model_validate_json(json_str)
        assert restored.query == pool.query
        assert restored.total_count == 1
        assert restored.channels_used == [DiscoveryChannel.SEARCH, DiscoveryChannel.REGISTRY]
```

### Verifica

```bash
mypy src/github_discovery/models/candidate.py --strict
pytest tests/unit/test_models/test_candidate.py -v
```

---

## 5) Task 1.2 — Modelli screening Gate 1

### Obiettivo

Definire i 7 sottoscore e il modello composito `MetadataScreenResult` per il Gate 1 (metadata screening, zero LLM cost). Ogni sottoscore ha range 0.0-1.0 con dettagli specifici.

### Pattern di base: `SubScore`

Tutti i sottoscore Gate 1 e Gate 2 condividono un pattern comune:

```python
class SubScore(BaseModel):
    """Base pattern for all gate sub-scores.

    Every sub-score has:
    - A value in [0.0, 1.0]
    - A weight for composite calculation
    - Details explaining the score
    - A confidence indicator for the quality of the data
    """
    value: float = Field(ge=0.0, le=1.0, description="Score value 0.0-1.0")
    weight: float = Field(gt=0.0, le=1.0, description="Weight in composite calculation")
    details: dict[str, object] = Field(default_factory=dict, description="Scoring breakdown details")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Data quality confidence")
    notes: list[str] = Field(default_factory=list, description="Human-readable scoring notes")
```

### Implementazione: `src/github_discovery/models/screening.py`

```python
"""Screening models for Gate 1 (metadata) and Gate 2 (static/security).

Gate 1 uses repository metadata from GitHub API — zero LLM cost.
Gate 2 uses automated tools on shallow clone — zero or low cost.

Both gates produce sub-scores (0.0-1.0) and composite pass/fail results.
Hard rule (Blueprint §16.5): no Gate 3 without Gate 1 + Gate 2 pass.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# --- Sub-Score Base Pattern ---


class SubScore(BaseModel):
    """Base pattern for all gate sub-scores.

    Every sub-score has a value in [0.0, 1.0], a weight for composite
    calculation, details explaining the score breakdown, and a confidence
    indicator for the quality of available data.
    """

    value: float = Field(ge=0.0, le=1.0, description="Score value 0.0-1.0")
    weight: float = Field(
        default=1.0,
        gt=0.0,
        le=1.0,
        description="Weight in composite calculation",
    )
    details: dict[str, object] = Field(
        default_factory=dict,
        description="Scoring breakdown details (e.g., which files found)",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Data quality confidence (1.0 = full API data, lower = heuristic)",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Human-readable scoring notes",
    )


# --- Gate 1: Metadata Screening Sub-Scores ---


class HygieneScore(SubScore):
    """Repository hygiene file presence and quality.

    Checks: LICENSE (SPDX valid), CONTRIBUTING.md, CODE_OF_CONDUCT.md,
    SECURITY.md, CHANGELOG.md, README.md (with content minimum).
    """

    details: dict[str, object] = Field(
        default_factory=dict,
        description="Files found: {license, contributing, code_of_conduct, security, changelog, readme}",
    )


class MaintenanceScore(SubScore):
    """Maintenance signals from commit history and activity.

    Checks: commit recency, commit cadence, bus factor proxy,
    issue resolution rate.
    """

    details: dict[str, object] = Field(
        default_factory=dict,
        description="Signals: {last_commit_days_ago, commit_cadence, bus_factor, issue_resolution_rate}",
    )


class ReleaseDisciplineScore(SubScore):
    """Release discipline and versioning practices.

    Checks: semver tagging, release cadence, changelog per release,
    release notes quality.
    """

    details: dict[str, object] = Field(
        default_factory=dict,
        description="Signals: {has_semver_tags, release_count, release_cadence_days, has_changelog_per_release}",
    )


class ReviewPracticeScore(SubScore):
    """Code review practices and PR management.

    Checks: PR template, review presence, label usage,
    response latency proxy.
    """

    details: dict[str, object] = Field(
        default_factory=dict,
        description="Signals: {has_pr_template, review_rate, label_usage, avg_response_hours}",
    )


class TestFootprintScore(SubScore):
    """Test infrastructure presence and coverage indicators.

    Checks: test directories/pattern presence, test config files
    (pytest.ini, conftest.py, setup.cfg test section), test/source
    file ratio.
    """

    details: dict[str, object] = Field(
        default_factory=dict,
        description="Signals: {has_test_dir, test_frameworks, test_file_ratio, has_conftest}",
    )


class CiCdScore(SubScore):
    """CI/CD pipeline presence and configuration quality.

    Checks: .github/workflows presence, CI badge, config validity,
    multi-OS testing, coverage reporting.
    """

    details: dict[str, object] = Field(
        default_factory=dict,
        description="Signals: {has_github_actions, workflow_count, has_ci_badge, has_coverage}",
    )


class DependencyQualityScore(SubScore):
    """Dependency management quality signals.

    Checks: lockfile presence, dependency pinning, update signals
    (dependabot/renovate config).
    """

    details: dict[str, object] = Field(
        default_factory=dict,
        description="Signals: {has_lockfile, pinning_ratio, has_dependabot, has_renovate}",
    )


# --- Gate 1: Composite Result ---


class MetadataScreenResult(BaseModel):
    """Gate 1 — Metadata screening result (zero LLM cost).

    Combines 7 sub-scores into a composite gate1_total.
    gate1_pass is determined by comparing gate1_total against
    the configured threshold (default 0.4, configurable per-session).
    """

    full_name: str = Field(description="Repository full name (owner/repo)")
    commit_sha: str = Field(default="", description="Commit SHA at screening time")

    hygiene: HygieneScore = Field(default_factory=lambda: HygieneScore(value=0.0))
    maintenance: MaintenanceScore = Field(default_factory=lambda: MaintenanceScore(value=0.0))
    release_discipline: ReleaseDisciplineScore = Field(
        default_factory=lambda: ReleaseDisciplineScore(value=0.0),
    )
    review_practice: ReviewPracticeScore = Field(
        default_factory=lambda: ReviewPracticeScore(value=0.0),
    )
    test_footprint: TestFootprintScore = Field(
        default_factory=lambda: TestFootprintScore(value=0.0),
    )
    ci_cd: CiCdScore = Field(default_factory=lambda: CiCdScore(value=0.0))
    dependency_quality: DependencyQualityScore = Field(
        default_factory=lambda: DependencyQualityScore(value=0.0),
    )

    gate1_total: float = Field(default=0.0, ge=0.0, le=1.0, description="Weighted composite score")
    gate1_pass: bool = Field(default=False, description="Whether candidate passed Gate 1")
    threshold_used: float = Field(default=0.4, description="Threshold applied for pass/fail")

    def compute_total(self) -> float:
        """Compute weighted composite score from sub-scores."""
        scores = [
            self.hygiene,
            self.maintenance,
            self.release_discipline,
            self.review_practice,
            self.test_footprint,
            self.ci_cd,
            self.dependency_quality,
        ]
        total_weight = sum(s.weight for s in scores)
        if total_weight == 0:
            return 0.0
        return sum(s.value * s.weight for s in scores) / total_weight
```

### Test: `tests/unit/test_models/test_screening.py`

```python
"""Tests for screening models (Gate 1 and Gate 2)."""

from __future__ import annotations

from github_discovery.models.screening import (
    CiCdScore,
    DependencyQualityScore,
    HygieneScore,
    MaintenanceScore,
    MetadataScreenResult,
    ReleaseDisciplineScore,
    ReviewPracticeScore,
    StaticScreenResult,
    SubScore,
    TestFootprintScore,
)


class TestSubScore:
    """Test SubScore base pattern."""

    def test_valid_score(self) -> None:
        """SubScore accepts valid 0.0-1.0 values."""
        score = SubScore(value=0.75)
        assert score.value == 0.75
        assert score.confidence == 1.0

    def test_score_out_of_range(self) -> None:
        """SubScore rejects values outside 0.0-1.0."""
        import pytest

        with pytest.raises(Exception):
            SubScore(value=1.5)
        with pytest.raises(Exception):
            SubScore(value=-0.1)

    def test_score_with_details(self) -> None:
        """SubScore carries details dict."""
        score = SubScore(
            value=0.8,
            details={"files_found": ["LICENSE", "README.md"]},
            notes=["LICENSE is MIT", "README has content"],
        )
        assert score.details["files_found"] == ["LICENSE", "README.md"]
        assert len(score.notes) == 2


class TestMetadataScreenResult:
    """Test Gate 1 composite result."""

    def test_default_result(self) -> None:
        """Default result has all scores at 0.0 and fails."""
        result = MetadataScreenResult(full_name="test/repo")
        assert result.gate1_pass is False
        assert result.gate1_total == 0.0

    def test_compute_total_uniform_weights(self) -> None:
        """Compute total averages scores with uniform weights."""
        result = MetadataScreenResult(
            full_name="test/repo",
            hygiene=HygieneScore(value=0.8),
            maintenance=MaintenanceScore(value=0.6),
            release_discipline=ReleaseDisciplineScore(value=0.7),
            review_practice=ReviewPracticeScore(value=0.5),
            test_footprint=TestFootprintScore(value=0.9),
            ci_cd=CiCdScore(value=0.4),
            dependency_quality=DependencyQualityScore(value=0.6),
        )
        total = result.compute_total()
        assert 0.0 <= total <= 1.0
        # With uniform weights (1.0 each), total should be average
        expected_avg = (0.8 + 0.6 + 0.7 + 0.5 + 0.9 + 0.4 + 0.6) / 7
        assert abs(total - expected_avg) < 0.01

    def test_pass_with_high_scores(self) -> None:
        """Result passes with high scores above threshold."""
        result = MetadataScreenResult(
            full_name="test/repo",
            hygiene=HygieneScore(value=0.9),
            maintenance=MaintenanceScore(value=0.8),
            release_discipline=ReleaseDisciplineScore(value=0.7),
            review_practice=ReviewPracticeScore(value=0.6),
            test_footprint=TestFootprintScore(value=0.8),
            ci_cd=CiCdScore(value=0.7),
            dependency_quality=DependencyQualityScore(value=0.7),
            gate1_total=0.75,
            gate1_pass=True,
        )
        assert result.gate1_pass is True
        assert result.gate1_total >= result.threshold_used

    def test_json_round_trip(self) -> None:
        """MetadataScreenResult serializes to/from JSON."""
        result = MetadataScreenResult(
            full_name="test/repo",
            hygiene=HygieneScore(value=0.8, details={"files_found": ["LICENSE"]}),
            gate1_total=0.6,
            gate1_pass=True,
        )
        json_str = result.model_dump_json()
        restored = MetadataScreenResult.model_validate_json(json_str)
        assert restored.full_name == "test/repo"
        assert restored.hygiene.value == 0.8
        assert restored.gate1_pass is True

    def test_sub_scores_with_custom_weights(self) -> None:
        """Sub-scores can have custom weights for domain-specific scoring."""
        score = HygieneScore(value=0.8, weight=2.0)
        assert score.weight == 2.0
```

### Verifica

```bash
mypy src/github_discovery/models/screening.py --strict
pytest tests/unit/test_models/test_screening.py -v
```

---

## 6) Task 1.3 — Modelli screening Gate 2

### Obiettivo

Definire i 4 sottoscore e il modello composito `StaticScreenResult` per il Gate 2 (static/security screening, zero o low cost). Include tool-specific details.

### Implementazione (stesso file `src/github_discovery/models/screening.py`)

Aggiungere al file `screening.py` dopo le classi Gate 1:

```python
# --- Gate 2: Static/Security Screening Sub-Scores ---


class SecurityHygieneScore(SubScore):
    """Security posture from OpenSSF Scorecard.

    Checks: branch protection, workflow security, token permissions,
    dependency update automation, signed releases.
    """

    details: dict[str, object] = Field(
        default_factory=dict,
        description="Scorecard details: {scorecard_score, branch_protection, token_permissions, ...}",
    )


class VulnerabilityScore(SubScore):
    """Known vulnerability assessment from OSV API.

    Checks: vulnerabilities in declared dependencies (severity,
    count, age of CVEs).
    """

    details: dict[str, object] = Field(
        default_factory=dict,
        description="Vulnerability details: {vuln_count, critical_count, high_count, osv_packages_checked}",
    )


class ComplexityScore(SubScore):
    """Code complexity and size metrics from scc/cloc.

    Checks: LOC, language breakdown, complexity metrics,
    file count, directory depth.
    """

    details: dict[str, object] = Field(
        default_factory=dict,
        description="Complexity details: {total_loc, languages, file_count, avg_complexity}",
    )


class SecretHygieneScore(SubScore):
    """Secret detection from gitleaks scan.

    Checks: leaked secrets in git history, SARIF findings count.
    """

    details: dict[str, object] = Field(
        default_factory=dict,
        description="Secret scan details: {findings_count, scan_tool, sarif_parsed}",
    )


# --- Gate 2: Composite Result ---


class StaticScreenResult(BaseModel):
    """Gate 2 — Static/security screening result (zero or low cost).

    Combines 4 sub-scores into a composite gate2_total.
    gate2_pass is determined by comparing gate2_total against
    the configured threshold (default 0.5, configurable per-session).

    Hard rule (Blueprint §16.5): gate2_pass must be True before
    any Gate 3 deep assessment.
    """

    full_name: str = Field(description="Repository full name (owner/repo)")
    commit_sha: str = Field(default="", description="Commit SHA at screening time")

    security_hygiene: SecurityHygieneScore = Field(
        default_factory=lambda: SecurityHygieneScore(value=0.0),
    )
    vulnerability: VulnerabilityScore = Field(
        default_factory=lambda: VulnerabilityScore(value=0.0),
    )
    complexity: ComplexityScore = Field(
        default_factory=lambda: ComplexityScore(value=0.0),
    )
    secret_hygiene: SecretHygieneScore = Field(
        default_factory=lambda: SecretHygieneScore(value=0.0),
    )

    gate2_total: float = Field(default=0.0, ge=0.0, le=1.0, description="Weighted composite score")
    gate2_pass: bool = Field(default=False, description="Whether candidate passed Gate 2")
    threshold_used: float = Field(default=0.5, description="Threshold applied for pass/fail")

    tools_used: list[str] = Field(
        default_factory=list,
        description="External tools invoked (e.g., ['scorecard', 'gitleaks', 'scc', 'osv'])",
    )
    tools_failed: list[str] = Field(
        default_factory=list,
        description="Tools that failed during screening (graceful degradation)",
    )

    def compute_total(self) -> float:
        """Compute weighted composite score from sub-scores."""
        scores = [
            self.security_hygiene,
            self.vulnerability,
            self.complexity,
            self.secret_hygiene,
        ]
        total_weight = sum(s.weight for s in scores)
        if total_weight == 0:
            return 0.0
        return sum(s.value * s.weight for s in scores) / total_weight


# --- Combined Screening Result ---


class ScreeningResult(BaseModel):
    """Combined Gate 1 + Gate 2 screening result for a repository.

    This is the complete screening state used by the screening
    orchestrator (Phase 3) and hard gate enforcement.
    """

    full_name: str = Field(description="Repository full name (owner/repo)")
    commit_sha: str = Field(default="", description="Commit SHA at screening time")

    gate1: MetadataScreenResult | None = Field(
        default=None,
        description="Gate 1 result (None if not yet screened)",
    )
    gate2: StaticScreenResult | None = Field(
        default=None,
        description="Gate 2 result (None if not yet screened)",
    )

    @property
    def can_proceed_to_gate3(self) -> bool:
        """Check hard gate: Gate 1 + Gate 2 must both pass.

        Implements Blueprint §16.5 hard rule:
        no deep-scan LLM below Gate 1+2 threshold.
        """
        if self.gate1 is None or self.gate2 is None:
            return False
        return self.gate1.gate1_pass and self.gate2.gate2_pass
```

### Test (aggiungere a `tests/unit/test_models/test_screening.py`)

```python
class TestStaticScreenResult:
    """Test Gate 2 composite result."""

    def test_default_result(self) -> None:
        """Default result has all scores at 0.0 and fails."""
        result = StaticScreenResult(full_name="test/repo")
        assert result.gate2_pass is False
        assert result.gate2_total == 0.0

    def test_compute_total(self) -> None:
        """Compute total averages Gate 2 scores."""
        result = StaticScreenResult(
            full_name="test/repo",
            security_hygiene=SecurityHygieneScore(value=0.8),
            vulnerability=VulnerabilityScore(value=0.9),
            complexity=ComplexityScore(value=0.6),
            secret_hygiene=SecretHygieneScore(value=1.0),
        )
        total = result.compute_total()
        expected = (0.8 + 0.9 + 0.6 + 1.0) / 4
        assert abs(total - expected) < 0.01

    def test_tools_tracking(self) -> None:
        """Result tracks which tools were used and which failed."""
        result = StaticScreenResult(
            full_name="test/repo",
            tools_used=["scorecard", "scc", "osv"],
            tools_failed=["gitleaks"],
        )
        assert "gitleaks" in result.tools_failed


class TestScreeningResult:
    """Test combined Gate 1 + Gate 2 result."""

    def test_can_proceed_to_gate3_both_pass(self) -> None:
        """Can proceed when both gates pass."""
        result = ScreeningResult(
            full_name="test/repo",
            gate1=MetadataScreenResult(
                full_name="test/repo", gate1_total=0.7, gate1_pass=True,
            ),
            gate2=StaticScreenResult(
                full_name="test/repo", gate2_total=0.6, gate2_pass=True,
            ),
        )
        assert result.can_proceed_to_gate3 is True

    def test_cannot_proceed_gate1_fail(self) -> None:
        """Cannot proceed when Gate 1 fails (hard gate)."""
        result = ScreeningResult(
            full_name="test/repo",
            gate1=MetadataScreenResult(
                full_name="test/repo", gate1_total=0.3, gate1_pass=False,
            ),
            gate2=StaticScreenResult(
                full_name="test/repo", gate2_total=0.7, gate2_pass=True,
            ),
        )
        assert result.can_proceed_to_gate3 is False

    def test_cannot_proceed_gate2_missing(self) -> None:
        """Cannot proceed when Gate 2 not yet done."""
        result = ScreeningResult(
            full_name="test/repo",
            gate1=MetadataScreenResult(
                full_name="test/repo", gate1_total=0.7, gate1_pass=True,
            ),
            gate2=None,
        )
        assert result.can_proceed_to_gate3 is False

    def test_cannot_proceed_both_missing(self) -> None:
        """Cannot proceed when neither gate done."""
        result = ScreeningResult(full_name="test/repo")
        assert result.can_proceed_to_gate3 is False
```

### Verifica

```bash
mypy src/github_discovery/models/screening.py --strict
pytest tests/unit/test_models/test_screening.py -v
```

---

## 7) Task 1.4 — Modelli deep assessment Gate 3

### Obiettivo

Definire il modello `DeepAssessmentResult` con 8 `DimensionScore` per ciascuna dimensione del blueprint §7, più explanation, evidence e confidence. Include budget tracking.

### Implementazione: `src/github_discovery/models/assessment.py`

```python
"""Deep assessment models for Gate 3 (LLM-based evaluation).

Gate 3 is the expensive deep assessment — only for top percentile
candidates that passed Gate 1 + Gate 2. Uses LLM structured output
across 8 evaluation dimensions (Blueprint §7).

Budget control (Blueprint §16.5):
- Maximum token budget per day and per repo
- Timeout and early-stop on repos too large
- Mandatory caching by commit SHA
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from github_discovery.models.enums import ScoreDimension


class DimensionScore(BaseModel):
    """Score for a single evaluation dimension.

    Each dimension has a value (0.0-1.0), an explanation of the
    score, supporting evidence (specific observations from the code),
    and a confidence indicator for the assessment quality.
    """

    dimension: ScoreDimension = Field(description="Which evaluation dimension")
    value: float = Field(ge=0.0, le=1.0, description="Score value 0.0-1.0")
    explanation: str = Field(
        default="",
        description="LLM-generated explanation of the score",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Specific observations supporting the score",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Assessment confidence (higher = more reliable)",
    )
    assessment_method: str = Field(
        default="llm",
        description="How this score was derived: llm, heuristic, static_analysis",
    )


class TokenUsage(BaseModel):
    """Token usage tracking for LLM budget control."""

    prompt_tokens: int = Field(default=0, ge=0, description="Prompt tokens consumed")
    completion_tokens: int = Field(default=0, ge=0, description="Completion tokens consumed")
    total_tokens: int = Field(default=0, ge=0, description="Total tokens consumed")
    model_used: str = Field(default="", description="LLM model identifier")
    provider: str = Field(default="", description="LLM provider name")


class DeepAssessmentResult(BaseModel):
    """Gate 3 — Deep technical assessment result.

    Contains dimension scores for all 8 evaluation dimensions (Blueprint §7),
    plus overall assessment metadata including explanation, confidence,
    and token usage for budget tracking.

    Hard gate enforcement: this result should only exist for candidates
    that passed Gate 1 + Gate 2 (enforced by the assessment orchestrator).
    """

    full_name: str = Field(description="Repository full name (owner/repo)")
    commit_sha: str = Field(default="", description="Commit SHA at assessment time")

    dimensions: dict[ScoreDimension, DimensionScore] = Field(
        default_factory=dict,
        description="Per-dimension scores (keyed by ScoreDimension enum)",
    )

    overall_quality: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Weighted composite quality score across all dimensions",
    )
    overall_explanation: str = Field(
        default="",
        description="Summary explanation of overall quality assessment",
    )
    overall_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall assessment confidence (lowest dimension confidence)",
    )

    gate3_pass: bool = Field(
        default=False,
        description="Whether candidate passed Gate 3 quality threshold",
    )
    gate3_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Threshold applied for Gate 3 pass/fail",
    )

    token_usage: TokenUsage = Field(
        default_factory=TokenUsage,
        description="Token budget tracking for this assessment",
    )
    assessed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Assessment completion timestamp",
    )
    assessment_duration_seconds: float = Field(
        default=0.0,
        ge=0.0,
        description="Duration of the assessment in seconds",
    )
    cached: bool = Field(
        default=False,
        description="Whether this result was loaded from cache (dedup by SHA)",
    )

    @property
    def dimensions_assessed(self) -> int:
        """Number of dimensions with actual scores."""
        return len(self.dimensions)

    @property
    def expected_dimensions(self) -> int:
        """Expected number of dimensions (Blueprint §7: 8)."""
        return len(ScoreDimension)

    @property
    def completeness_ratio(self) -> float:
        """Ratio of assessed dimensions to expected dimensions."""
        if self.expected_dimensions == 0:
            return 0.0
        return self.dimensions_assessed / self.expected_dimensions

    def get_dimension_score(self, dimension: ScoreDimension) -> DimensionScore | None:
        """Get score for a specific dimension."""
        return self.dimensions.get(dimension)

    def compute_overall_confidence(self) -> float:
        """Compute overall confidence as minimum of dimension confidences."""
        if not self.dimensions:
            return 0.0
        return min(ds.confidence for ds in self.dimensions.values())
```

### Test: `tests/unit/test_models/test_assessment.py`

```python
"""Tests for deep assessment models (Gate 3)."""

from __future__ import annotations

from github_discovery.models.assessment import (
    DeepAssessmentResult,
    DimensionScore,
    TokenUsage,
)
from github_discovery.models.enums import ScoreDimension


def _make_dimension_score(
    dimension: ScoreDimension,
    value: float = 0.8,
) -> DimensionScore:
    """Create a test dimension score."""
    return DimensionScore(
        dimension=dimension,
        value=value,
        explanation=f"{dimension.value} looks good",
        evidence=[f"evidence_{dimension.value}"],
        confidence=0.85,
    )


class TestDimensionScore:
    """Test individual dimension score."""

    def test_valid_score(self) -> None:
        """DimensionScore accepts valid values."""
        ds = DimensionScore(
            dimension=ScoreDimension.CODE_QUALITY,
            value=0.75,
            explanation="Well-structured code",
            evidence=["Consistent naming", "Good modularity"],
        )
        assert ds.dimension == ScoreDimension.CODE_QUALITY
        assert ds.value == 0.75
        assert len(ds.evidence) == 2

    def test_invalid_value_range(self) -> None:
        """DimensionScore rejects values outside 0.0-1.0."""
        import pytest

        with pytest.raises(Exception):
            DimensionScore(dimension=ScoreDimension.TESTING, value=1.5)


class TestDeepAssessmentResult:
    """Test Gate 3 deep assessment result."""

    def test_empty_result(self) -> None:
        """Empty result has no dimensions scored."""
        result = DeepAssessmentResult(full_name="test/repo")
        assert result.dimensions_assessed == 0
        assert result.completeness_ratio == 0.0
        assert result.gate3_pass is False

    def test_with_all_dimensions(self) -> None:
        """Result with all 8 dimensions."""
        dims = {d: _make_dimension_score(d) for d in ScoreDimension}
        result = DeepAssessmentResult(
            full_name="test/repo",
            dimensions=dims,
            overall_quality=0.82,
            gate3_pass=True,
        )
        assert result.dimensions_assessed == 8
        assert result.completeness_ratio == 1.0

    def test_get_dimension_score(self) -> None:
        """Can retrieve score by dimension."""
        ds = _make_dimension_score(ScoreDimension.SECURITY, value=0.9)
        result = DeepAssessmentResult(
            full_name="test/repo",
            dimensions={ScoreDimension.SECURITY: ds},
        )
        retrieved = result.get_dimension_score(ScoreDimension.SECURITY)
        assert retrieved is not None
        assert retrieved.value == 0.9

    def test_compute_overall_confidence(self) -> None:
        """Overall confidence is minimum of dimension confidences."""
        dims = {
            ScoreDimension.CODE_QUALITY: DimensionScore(
                dimension=ScoreDimension.CODE_QUALITY,
                value=0.9,
                confidence=0.9,
            ),
            ScoreDimension.TESTING: DimensionScore(
                dimension=ScoreDimension.TESTING,
                value=0.7,
                confidence=0.6,
            ),
        }
        result = DeepAssessmentResult(
            full_name="test/repo",
            dimensions=dims,
        )
        assert result.compute_overall_confidence() == 0.6

    def test_json_round_trip(self) -> None:
        """DeepAssessmentResult serializes to/from JSON."""
        dims = {
            ScoreDimension.ARCHITECTURE: _make_dimension_score(ScoreDimension.ARCHITECTURE),
        }
        result = DeepAssessmentResult(
            full_name="test/repo",
            dimensions=dims,
            overall_quality=0.8,
            token_usage=TokenUsage(total_tokens=5000, model_used="gpt-4o"),
        )
        json_str = result.model_dump_json()
        restored = DeepAssessmentResult.model_validate_json(json_str)
        assert restored.full_name == "test/repo"
        assert restored.token_usage.total_tokens == 5000

    def test_cached_flag(self) -> None:
        """Result tracks whether it came from cache."""
        result = DeepAssessmentResult(full_name="test/repo", cached=True)
        assert result.cached is True


class TestTokenUsage:
    """Test token usage tracking."""

    def test_default_usage(self) -> None:
        """Default usage is zero."""
        usage = TokenUsage()
        assert usage.total_tokens == 0

    def test_usage_tracking(self) -> None:
        """Usage tracks prompt and completion tokens."""
        usage = TokenUsage(
            prompt_tokens=3000,
            completion_tokens=2000,
            total_tokens=5000,
            model_used="gpt-4o",
            provider="openai",
        )
        assert usage.total_tokens == 5000
        assert usage.model_used == "gpt-4o"
```

### Verifica

```bash
mypy src/github_discovery/models/assessment.py --strict
pytest tests/unit/test_models/test_assessment.py -v
```

---

## 8) Task 1.5 — Modelli scoring & ranking

### Obiettivo

Definire i modelli per il Layer D (scoring, ranking, explainability): `ScoreResult` (composite multi-score), `ValueScore` (anti-star bias), `RankedRepo` (intra-domain), `ExplainabilityReport` (feature breakdown), `DomainProfile` (taxonomy + weights).

### Implementazione: `src/github_discovery/models/scoring.py`

```python
"""Scoring, ranking, and explainability models (Layer D).

Layer D produces the final ranked output with anti-star bias
(Stars are context only — never primary ranking signal).

Key formulas:
- ValueScore = quality_score / log10(stars + 10)  (Blueprint §5)
- Ranking is intra-domain: no unfair cross-domain comparison
- Explainability: every score is explainable per feature and dimension
"""

from __future__ import annotations

from datetime import UTC, datetime
from math import log10

from pydantic import BaseModel, Field, computed_field

from github_discovery.models.enums import DomainType, ScoreDimension


# --- Domain Profile ---


class DomainProfile(BaseModel):
    """Domain-specific weight profile for scoring.

    Each domain has different quality expectations and weight profiles
    (Blueprint §10). For example, CLI tools weight testing higher,
    while ML libraries weight innovation higher.

    dimension_weights must sum to 1.0 (validated at runtime).
    gate_thresholds define minimum scores per gate for this domain.
    """

    domain_type: DomainType = Field(description="Which domain this profile covers")
    display_name: str = Field(description="Human-readable domain name")
    description: str = Field(default="", description="What this domain covers")

    dimension_weights: dict[ScoreDimension, float] = Field(
        description="Per-dimension weights (must sum to 1.0)",
    )
    gate_thresholds: dict[str, float] = Field(
        default_factory=lambda: {"gate1": 0.4, "gate2": 0.5, "gate3": 0.6},
        description="Minimum pass scores per gate for this domain",
    )
    star_baseline: float = Field(
        default=1000.0,
        description="Expected star count for an 'established' project in this domain",
    )
    preferred_channels: list[str] = Field(
        default_factory=list,
        description="Discovery channels preferred for this domain",
    )

    def validate_weights(self) -> bool:
        """Check that dimension weights sum to approximately 1.0."""
        total = sum(self.dimension_weights.values())
        return abs(total - 1.0) < 0.01


# --- Scoring ---


class ScoreResult(BaseModel):
    """Composite scoring result for a repository.

    Combines Gate 1 + Gate 2 + Gate 3 results into a final
    multi-dimensional quality score with confidence tracking.
    """

    full_name: str = Field(description="Repository full name (owner/repo)")
    commit_sha: str = Field(default="", description="Commit SHA at scoring time")
    domain: DomainType = Field(
        default=DomainType.OTHER,
        description="Domain type used for weighting",
    )

    quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Domain-weighted composite quality score",
    )
    dimension_scores: dict[ScoreDimension, float] = Field(
        default_factory=dict,
        description="Per-dimension score values (0.0-1.0)",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence in the scoring result",
    )

    stars: int = Field(
        default=0,
        ge=0,
        description="Star count at scoring time (for ValueScore computation)",
    )

    gate1_total: float = Field(default=0.0, ge=0.0, le=1.0)
    gate2_total: float = Field(default=0.0, ge=0.0, le=1.0)
    gate3_available: bool = Field(
        default=False,
        description="Whether Gate 3 deep assessment was performed",
    )

    scored_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Scoring timestamp",
    )

    @computed_field
    @property
    def value_score(self) -> float:
        """Anti-star bias Value Score.

        Formula: quality_score / log10(stars + 10)

        Repos with high quality and low stars get high value scores.
        Repos with high quality and high stars get moderate value scores.
        This identifies hidden gems that star-based ranking misses.

        Reference: Blueprint §5, §15 — anti-popularity debiasing.
        """
        if self.quality_score <= 0.0:
            return 0.0
        return self.quality_score / log10(self.stars + 10)


class RankedRepo(BaseModel):
    """A repository with its ranking position and scores.

    Ranking is intra-domain: positions are relative to other repos
    in the same DomainType. Cross-domain comparison requires
    explicit normalization and a warning.
    """

    rank: int = Field(ge=1, description="Ranking position within domain")
    full_name: str = Field(description="Repository full name (owner/repo)")
    domain: DomainType = Field(description="Domain type for this ranking")
    score_result: ScoreResult = Field(description="Complete scoring result")

    @computed_field
    @property
    def value_score(self) -> float:
        """Convenience access to value score."""
        return self.score_result.value_score

    @computed_field
    @property
    def quality_score(self) -> float:
        """Convenience access to quality score."""
        return self.score_result.quality_score

    @computed_field
    @property
    def stars(self) -> int:
        """Convenience access to star count."""
        return self.score_result.stars


class ExplainabilityReport(BaseModel):
    """Explainability report for a repository's scoring.

    Every score must be explainable per feature and dimension (Blueprint §3).
    Reports provide both human-readable explanations and machine-readable
    feature breakdowns for transparency.
    """

    full_name: str = Field(description="Repository full name (owner/repo)")
    domain: DomainType = Field(description="Domain type")
    overall_quality: float = Field(ge=0.0, le=1.0, description="Overall quality score")
    value_score: float = Field(ge=0.0, description="Anti-star bias value score")

    dimension_breakdown: dict[str, dict[str, object]] = Field(
        default_factory=dict,
        description="Per-dimension breakdown: {dimension: {score, weight, explanation, evidence}}",
    )

    strengths: list[str] = Field(
        default_factory=list,
        description="Key strengths identified (top 3-5 features)",
    )
    weaknesses: list[str] = Field(
        default_factory=list,
        description="Key weaknesses identified (top 3-5)",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recommendations for improvement",
    )

    star_context: str = Field(
        default="",
        description="Star count context (e.g., '42 stars — low visibility for this quality level')",
    )
    hidden_gem_indicator: bool = Field(
        default=False,
        description="Whether this repo is identified as a hidden gem",
    )
    hidden_gem_reason: str = Field(
        default="",
        description="Why this repo is/isn't a hidden gem",
    )

    compared_to_star_baseline: str = Field(
        default="",
        description="How this repo compares to star-based ranking expectation",
    )

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence in the assessment",
    )

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Report generation timestamp",
    )


# --- Predefined Domain Profiles ---


LIBRARY_PROFILE = DomainProfile(
    domain_type=DomainType.LIBRARY,
    display_name="Library",
    description="General-purpose libraries",
    dimension_weights={
        ScoreDimension.CODE_QUALITY: 0.20,
        ScoreDimension.ARCHITECTURE: 0.15,
        ScoreDimension.TESTING: 0.15,
        ScoreDimension.DOCUMENTATION: 0.15,
        ScoreDimension.MAINTENANCE: 0.15,
        ScoreDimension.SECURITY: 0.10,
        ScoreDimension.FUNCTIONALITY: 0.05,
        ScoreDimension.INNOVATION: 0.05,
    },
    star_baseline=500.0,
    preferred_channels=["search", "registry", "awesome_list"],
)

CLI_PROFILE = DomainProfile(
    domain_type=DomainType.CLI,
    display_name="CLI Tool",
    description="Command-line tools",
    dimension_weights={
        ScoreDimension.CODE_QUALITY: 0.15,
        ScoreDimension.ARCHITECTURE: 0.10,
        ScoreDimension.TESTING: 0.20,
        ScoreDimension.DOCUMENTATION: 0.10,
        ScoreDimension.MAINTENANCE: 0.20,
        ScoreDimension.SECURITY: 0.10,
        ScoreDimension.FUNCTIONALITY: 0.10,
        ScoreDimension.INNOVATION: 0.05,
    },
    star_baseline=300.0,
    preferred_channels=["search", "registry", "awesome_list"],
)

DEVOPS_PROFILE = DomainProfile(
    domain_type=DomainType.DEVOPS_TOOL,
    display_name="DevOps Tool",
    description="DevOps and infrastructure tools",
    dimension_weights={
        ScoreDimension.CODE_QUALITY: 0.15,
        ScoreDimension.ARCHITECTURE: 0.15,
        ScoreDimension.TESTING: 0.20,
        ScoreDimension.DOCUMENTATION: 0.10,
        ScoreDimension.MAINTENANCE: 0.15,
        ScoreDimension.SECURITY: 0.15,
        ScoreDimension.FUNCTIONALITY: 0.05,
        ScoreDimension.INNOVATION: 0.05,
    },
    star_baseline=2000.0,
    preferred_channels=["search", "dependency", "registry"],
)

DEFAULT_PROFILE = DomainProfile(
    domain_type=DomainType.OTHER,
    display_name="Other",
    description="Default profile for uncategorized repositories",
    dimension_weights={
        ScoreDimension.CODE_QUALITY: 0.20,
        ScoreDimension.ARCHITECTURE: 0.15,
        ScoreDimension.TESTING: 0.15,
        ScoreDimension.DOCUMENTATION: 0.10,
        ScoreDimension.MAINTENANCE: 0.15,
        ScoreDimension.SECURITY: 0.10,
        ScoreDimension.FUNCTIONALITY: 0.10,
        ScoreDimension.INNOVATION: 0.05,
    },
    star_baseline=1000.0,
)

DOMAIN_PROFILES: dict[DomainType, DomainProfile] = {
    DomainType.LIBRARY: LIBRARY_PROFILE,
    DomainType.CLI: CLI_PROFILE,
    DomainType.DEVOPS_TOOL: DEVOPS_PROFILE,
    # All other domains use DEFAULT_PROFILE
}


def get_domain_profile(domain: DomainType) -> DomainProfile:
    """Get the scoring profile for a domain type.

    Returns the domain-specific profile if defined,
    otherwise returns the default profile.
    """
    return DOMAIN_PROFILES.get(domain, DEFAULT_PROFILE)
```

### Test: `tests/unit/test_models/test_scoring.py`

```python
"""Tests for scoring, ranking, and explainability models."""

from __future__ import annotations

from math import log10

from github_discovery.models.enums import DomainType, ScoreDimension
from github_discovery.models.scoring import (
    CLI_PROFILE,
    DEFAULT_PROFILE,
    DOMAIN_PROFILES,
    DEVOPS_PROFILE,
    ExplainabilityReport,
    LIBRARY_PROFILE,
    RankedRepo,
    ScoreResult,
    get_domain_profile,
)


class TestValueScore:
    """Test anti-star bias Value Score computation."""

    def test_hidden_gem_high_value(self) -> None:
        """Low stars + high quality = high value score (hidden gem)."""
        score = ScoreResult(
            full_name="hidden/gem",
            quality_score=0.9,
            stars=10,
        )
        expected = 0.9 / log10(10 + 10)
        assert abs(score.value_score - expected) < 0.001
        assert score.value_score > 0.5  # High value score

    def test_popular_repo_moderate_value(self) -> None:
        """High stars + high quality = moderate value score."""
        score = ScoreResult(
            full_name="popular/repo",
            quality_score=0.9,
            stars=50000,
        )
        expected = 0.9 / log10(50000 + 10)
        assert abs(score.value_score - expected) < 0.001
        # Should be lower than hidden gem with same quality
        assert score.value_score < 0.2

    def test_zero_quality_zero_value(self) -> None:
        """Zero quality = zero value score."""
        score = ScoreResult(full_name="bad/repo", quality_score=0.0, stars=100)
        assert score.value_score == 0.0

    def test_zero_stars_high_quality(self) -> None:
        """Zero stars + high quality = very high value score."""
        score = ScoreResult(
            full_name="new/repo",
            quality_score=0.8,
            stars=0,
        )
        expected = 0.8 / log10(0 + 10)
        assert abs(score.value_score - expected) < 0.001
        assert score.value_score > 0.5

    def test_anti_star_bias_ordering(self) -> None:
        """Hidden gems rank higher than popular repos with same quality."""
        hidden = ScoreResult(full_name="hidden/gem", quality_score=0.85, stars=15)
        popular = ScoreResult(full_name="popular/repo", quality_score=0.85, stars=30000)
        assert hidden.value_score > popular.value_score


class TestDomainProfile:
    """Test domain weight profiles."""

    def test_library_profile_weights_sum_to_one(self) -> None:
        """Library profile weights sum to 1.0."""
        assert LIBRARY_PROFILE.validate_weights() is True

    def test_cli_profile_weights_sum_to_one(self) -> None:
        """CLI profile weights sum to 1.0."""
        assert CLI_PROFILE.validate_weights() is True

    def test_default_profile_weights_sum_to_one(self) -> None:
        """Default profile weights sum to 1.0."""
        assert DEFAULT_PROFILE.validate_weights() is True

    def test_devops_security_weight_higher(self) -> None:
        """DevOps profile weights security higher than library."""
        devops_sec = DEVOPS_PROFILE.dimension_weights[ScoreDimension.SECURITY]
        lib_sec = LIBRARY_PROFILE.dimension_weights[ScoreDimension.SECURITY]
        assert devops_sec > lib_sec

    def test_cli_testing_weight_higher(self) -> None:
        """CLI profile weights testing higher than default."""
        cli_test = CLI_PROFILE.dimension_weights[ScoreDimension.TESTING]
        default_test = DEFAULT_PROFILE.dimension_weights[ScoreDimension.TESTING]
        assert cli_test > default_test

    def test_get_domain_profile(self) -> None:
        """get_domain_profile returns correct profile."""
        assert get_domain_profile(DomainType.LIBRARY) is LIBRARY_PROFILE
        assert get_domain_profile(DomainType.OTHER) is DEFAULT_PROFILE
        # Unknown domain returns default
        assert get_domain_profile(DomainType.ML_LIB) is DEFAULT_PROFILE


class TestRankedRepo:
    """Test ranked repository model."""

    def test_computed_fields(self) -> None:
        """RankedRepo exposes computed fields from ScoreResult."""
        score = ScoreResult(
            full_name="test/repo",
            quality_score=0.8,
            stars=100,
        )
        ranked = RankedRepo(
            rank=1,
            full_name="test/repo",
            domain=DomainType.LIBRARY,
            score_result=score,
        )
        assert ranked.quality_score == 0.8
        assert ranked.stars == 100
        assert ranked.value_score == score.value_score


class TestExplainabilityReport:
    """Test explainability report model."""

    def test_report_creation(self) -> None:
        """Report can be created with all fields."""
        report = ExplainabilityReport(
            full_name="test/repo",
            domain=DomainType.LIBRARY,
            overall_quality=0.8,
            value_score=0.6,
            strengths=["Excellent test coverage", "Clean architecture"],
            weaknesses=["Missing security policy"],
            hidden_gem_indicator=True,
            hidden_gem_reason="High quality (0.8) with low visibility (42 stars)",
        )
        assert report.hidden_gem_indicator is True
        assert len(report.strengths) == 2

    def test_json_round_trip(self) -> None:
        """Report serializes to/from JSON."""
        report = ExplainabilityReport(
            full_name="test/repo",
            domain=DomainType.CLI,
            overall_quality=0.7,
            value_score=0.5,
        )
        json_str = report.model_dump_json()
        restored = ExplainabilityReport.model_validate_json(json_str)
        assert restored.full_name == "test/repo"
        assert restored.domain == DomainType.CLI
```

### Verifica

```bash
mypy src/github_discovery/models/scoring.py --strict
pytest tests/unit/test_models/test_scoring.py -v
```

---

## 9) Task 1.8 — Modello Feature Store

### Obiettivo

Definire il modello `RepoFeatures` per persistenza feature per repo (evita ricalcolo costoso), con chiave su `repo_full_name + commit_sha`, TTL configurabile, e source gate tracking.

### Implementazione: `src/github_discovery/models/features.py`

```python
"""Feature store models for caching computed repository features.

The feature store avoids expensive recomputation by caching results
per repo + commit SHA. Results are invalidated when a new commit
is detected (Blueprint §16.5: mandatory caching by commit SHA).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

from github_discovery.models.assessment import DeepAssessmentResult
from github_discovery.models.enums import DomainType
from github_discovery.models.screening import MetadataScreenResult, StaticScreenResult


class FeatureStoreKey(BaseModel):
    """Composite key for feature store lookups.

    Features are keyed by repo full name + commit SHA to enable:
    - Dedup: same repo at same SHA = same features
    - Invalidation: new commit SHA = features need recomputation
    - Cross-session reuse: any session can reuse cached features
    """

    full_name: str = Field(description="Repository full name (owner/repo)")
    commit_sha: str = Field(description="Git commit SHA for dedup")


class RepoFeatures(BaseModel):
    """Cached feature set for a repository at a specific commit.

    Stores the complete set of computed features for a repo at a
    given commit SHA. This includes all gate results and metadata.

    TTL is configurable (default 24 hours). Features are automatically
    invalidated when the commit SHA changes.
    """

    # --- Identity ---
    full_name: str = Field(description="Repository full name (owner/repo)")
    commit_sha: str = Field(description="Git commit SHA for dedup")
    domain: DomainType = Field(
        default=DomainType.OTHER,
        description="Inferred domain type",
    )

    # --- Gate Results (populated progressively) ---
    gate1_result: MetadataScreenResult | None = Field(
        default=None,
        description="Gate 1 metadata screening result (None = not yet screened)",
    )
    gate2_result: StaticScreenResult | None = Field(
        default=None,
        description="Gate 2 static/security screening result (None = not yet screened)",
    )
    gate3_result: DeepAssessmentResult | None = Field(
        default=None,
        description="Gate 3 deep assessment result (None = not yet assessed)",
    )

    # --- Metadata ---
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When features were last computed",
    )
    ttl_hours: int = Field(
        default=24,
        gt=0,
        description="Cache TTL in hours",
    )
    source_session_id: str | None = Field(
        default=None,
        description="Session that computed these features",
    )
    computation_version: str = Field(
        default="1.0",
        description="Version of computation logic (for cache invalidation on logic changes)",
    )

    @property
    def is_expired(self) -> bool:
        """Check if cached features have exceeded TTL."""
        expiry = self.computed_at + timedelta(hours=self.ttl_hours)
        return datetime.now(UTC) > expiry

    @property
    def highest_gate_completed(self) -> int:
        """Return the highest gate level with results (0 = none)."""
        if self.gate3_result is not None:
            return 3
        if self.gate2_result is not None:
            return 2
        if self.gate1_result is not None:
            return 1
        return 0

    @property
    def is_fully_assessed(self) -> bool:
        """Check if all gates have been completed."""
        return (
            self.gate1_result is not None
            and self.gate2_result is not None
            and self.gate3_result is not None
        )

    @property
    def store_key(self) -> FeatureStoreKey:
        """Get the cache key for this feature set."""
        return FeatureStoreKey(full_name=self.full_name, commit_sha=self.commit_sha)
```

### Test: `tests/unit/test_models/test_features.py`

```python
"""Tests for feature store models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from github_discovery.models.features import FeatureStoreKey, RepoFeatures


class TestFeatureStoreKey:
    """Test feature store composite key."""

    def test_key_creation(self) -> None:
        """Key can be created with full_name and commit_sha."""
        key = FeatureStoreKey(full_name="test/repo", commit_sha="abc123")
        assert key.full_name == "test/repo"
        assert key.commit_sha == "abc123"

    def test_key_equality(self) -> None:
        """Keys with same values are equal."""
        key1 = FeatureStoreKey(full_name="test/repo", commit_sha="abc123")
        key2 = FeatureStoreKey(full_name="test/repo", commit_sha="abc123")
        assert key1 == key2

    def test_key_inequality_sha(self) -> None:
        """Keys with different SHA are not equal."""
        key1 = FeatureStoreKey(full_name="test/repo", commit_sha="abc123")
        key2 = FeatureStoreKey(full_name="test/repo", commit_sha="def456")
        assert key1 != key2


class TestRepoFeatures:
    """Test cached feature set."""

    def test_empty_features(self) -> None:
        """Empty features have no gate results."""
        features = RepoFeatures(full_name="test/repo", commit_sha="abc123")
        assert features.highest_gate_completed == 0
        assert features.is_fully_assessed is False

    def test_features_with_gate1(self) -> None:
        """Features with only Gate 1 result."""
        from github_discovery.models.screening import MetadataScreenResult

        features = RepoFeatures(
            full_name="test/repo",
            commit_sha="abc123",
            gate1_result=MetadataScreenResult(
                full_name="test/repo",
                gate1_total=0.7,
                gate1_pass=True,
            ),
        )
        assert features.highest_gate_completed == 1
        assert features.is_fully_assessed is False

    def test_is_expired(self) -> None:
        """Features check TTL expiry."""
        # Not expired: computed now
        fresh = RepoFeatures(full_name="test/repo", commit_sha="abc123")
        assert fresh.is_expired is False

        # Expired: computed 48 hours ago with 24h TTL
        expired = RepoFeatures(
            full_name="test/repo",
            commit_sha="abc123",
            computed_at=datetime.now(UTC) - timedelta(hours=48),
            ttl_hours=24,
        )
        assert expired.is_expired is True

    def test_store_key(self) -> None:
        """Features provide their cache key."""
        features = RepoFeatures(full_name="test/repo", commit_sha="abc123")
        key = features.store_key
        assert key.full_name == "test/repo"
        assert key.commit_sha == "abc123"

    def test_json_round_trip(self) -> None:
        """RepoFeatures serializes to/from JSON."""
        features = RepoFeatures(full_name="test/repo", commit_sha="abc123")
        json_str = features.model_dump_json()
        restored = RepoFeatures.model_validate_json(json_str)
        assert restored.full_name == features.full_name
        assert restored.commit_sha == features.commit_sha
```

### Verifica

```bash
mypy src/github_discovery/models/features.py --strict
pytest tests/unit/test_models/test_features.py -v
```

---

## 10) Task 1.6 — Modelli API request/response

### Obiettivo

Definire i modelli per la superficie API REST (FastAPI), inclusi request bodies, response wrappers con pagination, e export formats.

### Implementazione: `src/github_discovery/models/api.py`

```python
"""API request/response models for the REST interface (Phase 6).

These models define the FastAPI request bodies and response wrappers.
They are compatible with FastAPI's automatic OpenAPI schema generation.

Note: The MCP interface uses its own tool parameter schemas (see mcp_spec.py).
API is a secondary consumer of the same core services (Blueprint §21.1).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field

from github_discovery.models.candidate import CandidatePool, RepoCandidate
from github_discovery.models.enums import DiscoveryChannel, DomainType, GateLevel
from github_discovery.models.screening import ScreeningResult
from github_discovery.models.scoring import RankedRepo


# --- Pagination ---


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")


class PaginatedResponse(BaseModel):
    """Paginated response wrapper for list endpoints."""

    total_count: int = Field(ge=0, description="Total items across all pages")
    page: int = Field(ge=1, description="Current page number")
    page_size: int = Field(ge=1, description="Items per page")
    total_pages: int = Field(ge=0, description="Total number of pages")
    has_next: bool = Field(description="Whether a next page exists")
    has_prev: bool = Field(description="Whether a previous page exists")


# --- Discovery ---


class DiscoveryQuery(BaseModel):
    """Request to discover candidate repositories."""

    query: str = Field(min_length=1, description="Search query string")
    channels: list[DiscoveryChannel] = Field(
        default_factory=lambda: [DiscoveryChannel.SEARCH, DiscoveryChannel.REGISTRY],
        description="Discovery channels to use",
    )
    max_candidates: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum candidates to discover",
    )
    domain: DomainType | None = Field(
        default=None,
        description="Preferred domain filter",
    )
    session_id: str | None = Field(
        default=None,
        description="Attach to an existing session",
    )
    languages: list[str] = Field(
        default_factory=list,
        description="Filter by programming languages",
    )


class DiscoveryResponse(BaseModel):
    """Response from a discovery request."""

    job_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique job identifier for tracking",
    )
    status: str = Field(default="pending", description="Job status: pending, running, completed, failed")
    pool_id: str | None = Field(default=None, description="Pool ID once discovery completes")
    total_candidates: int = Field(default=0, ge=0)
    channels_used: list[DiscoveryChannel] = Field(default_factory=list)
    session_id: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# --- Screening ---


class ScreeningRequest(BaseModel):
    """Request to screen a pool of candidates."""

    pool_id: str = Field(description="Candidate pool to screen")
    gate_level: GateLevel = Field(
        default=GateLevel.METADATA,
        description="Gate level: '1' (metadata), '2' (static), or run both",
    )
    min_gate1_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Override minimum Gate 1 score",
    )
    min_gate2_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Override minimum Gate 2 score",
    )
    session_id: str | None = Field(default=None)


class ScreeningResponse(BaseModel):
    """Response from a screening request."""

    job_id: str = Field(default_factory=lambda: str(uuid4()))
    status: str = Field(default="pending")
    pool_id: str
    gate_level: GateLevel
    total_screened: int = Field(default=0, ge=0)
    passed: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    session_id: str | None = Field(default=None)


# --- Assessment ---


class AssessmentRequest(BaseModel):
    """Request to deep-assess specific repositories.

    Hard gate (Blueprint §16.5): Only repos that passed Gate 1+2
    can be assessed. The API will reject requests for unqualified repos.
    """

    repo_urls: list[str] = Field(
        min_length=1,
        max_length=50,
        description="Repository URLs to assess (max 50)",
    )
    dimensions: list[str] = Field(
        default_factory=list,
        description="Specific dimensions to assess (empty = all 8)",
    )
    budget_tokens: int | None = Field(
        default=None,
        ge=1000,
        description="Override token budget for this assessment",
    )
    session_id: str | None = Field(default=None)


class AssessmentResponse(BaseModel):
    """Response from a deep assessment request."""

    job_id: str = Field(default_factory=lambda: str(uuid4()))
    status: str = Field(default="pending")
    total_repos: int = Field(default=0, ge=0)
    assessed: int = Field(default=0, ge=0)
    rejected_hard_gate: int = Field(
        default=0,
        ge=0,
        description="Repos rejected by hard gate (Gate 1+2 not passed)",
    )
    tokens_used: int = Field(default=0, ge=0)
    session_id: str | None = Field(default=None)


# --- Ranking ---


class RankingQuery(BaseModel):
    """Request to get ranked results."""

    domain: DomainType | None = Field(
        default=None,
        description="Filter by domain (required for meaningful ranking)",
    )
    min_confidence: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold",
    )
    min_value_score: float = Field(
        default=0.0,
        ge=0.0,
        description="Minimum value score (anti-star bias)",
    )
    max_results: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum results to return",
    )
    session_id: str | None = Field(default=None)
    pagination: PaginationParams = Field(default_factory=PaginationParams)


class RankingResponse(BaseModel):
    """Response with ranked repositories."""

    ranked_repos: list[RankedRepo] = Field(default_factory=list)
    pagination: PaginatedResponse
    domain: DomainType | None = Field(default=None)
    session_id: str | None = Field(default=None)


# --- Export ---


class ExportFormat(StrEnum):
    """Supported export formats."""

    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


class ExportRequest(BaseModel):
    """Request to export session results."""

    session_id: str = Field(description="Session to export")
    format: ExportFormat = Field(default=ExportFormat.JSON, description="Output format")
    domain: DomainType | None = Field(default=None, description="Filter by domain")
    include_details: bool = Field(
        default=False,
        description="Include full dimension breakdown and evidence",
    )


class ExportResponse(BaseModel):
    """Response from an export request."""

    download_url: str | None = Field(default=None, description="URL to download exported file")
    format: ExportFormat
    total_repos: int = Field(default=0, ge=0)
    content: str | None = Field(
        default=None,
        description="Inline content (for small exports)",
    )
```

### Test: `tests/unit/test_models/test_api.py`

```python
"""Tests for API request/response models."""

from __future__ import annotations

from github_discovery.models.api import (
    AssessmentRequest,
    DiscoveryQuery,
    DiscoveryResponse,
    ExportFormat,
    ExportRequest,
    PaginatedResponse,
    PaginationParams,
    RankingQuery,
    RankingResponse,
    ScreeningRequest,
)


class TestDiscoveryQuery:
    """Test discovery query model."""

    def test_minimal_query(self) -> None:
        """Query requires only the query string."""
        q = DiscoveryQuery(query="python static analysis")
        assert q.query == "python static analysis"
        assert q.max_candidates == 100

    def test_query_with_filters(self) -> None:
        """Query can specify channels, domain, languages."""
        q = DiscoveryQuery(
            query="rust cli tools",
            max_candidates=500,
            domain="cli",
            languages=["Rust"],
        )
        assert q.max_candidates == 500

    def test_query_validation(self) -> None:
        """Query string must be non-empty."""
        import pytest

        with pytest.raises(Exception):
            DiscoveryQuery(query="")


class TestPaginationParams:
    """Test pagination model."""

    def test_defaults(self) -> None:
        """Default pagination is page 1, 20 items."""
        p = PaginationParams()
        assert p.page == 1
        assert p.page_size == 20

    def test_custom_pagination(self) -> None:
        """Custom pagination values."""
        p = PaginationParams(page=3, page_size=50)
        assert p.page == 3
        assert p.page_size == 50


class TestPaginatedResponse:
    """Test paginated response model."""

    def test_response_fields(self) -> None:
        """Response includes all pagination metadata."""
        r = PaginatedResponse(
            total_count=100,
            page=2,
            page_size=20,
            total_pages=5,
            has_next=True,
            has_prev=True,
        )
        assert r.has_next is True
        assert r.has_prev is True


class TestExportFormat:
    """Test export format enum."""

    def test_supported_formats(self) -> None:
        """Three formats supported: JSON, CSV, Markdown."""
        assert ExportFormat.JSON == "json"
        assert ExportFormat.CSV == "csv"
        assert ExportFormat.MARKDOWN == "markdown"
```

### Verifica

```bash
mypy src/github_discovery/models/api.py --strict
pytest tests/unit/test_models/test_api.py -v
```

---

## 11) Task 1.9 — Modelli supporto agentico

### Obiettivo

Definire i modelli per il supporto agentico MCP: `MCPToolResult` (output context-efficient), `DiscoverySession` (sessione aggregata). Questi modelli collegano i modelli di dominio con l'interfaccia MCP.

### Implementazione: `src/github_discovery/models/agent.py`

```python
"""Agentic support models for MCP integration.

These models bridge domain models with the MCP interface:
- MCPToolResult: Context-efficient output for MCP tool invocations
- DiscoverySession: Aggregated session state with pools and results

Design principles (Blueprint §21.2):
- Context-efficient: summary-first, detail on-demand
- Reference-based: return IDs instead of full data
- Session-aware: all operations can be session-scoped
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from github_discovery.models.enums import DomainType


class MCPToolResult(BaseModel):
    """Context-efficient output for MCP tool invocations.

    Every MCP tool returns this structure to ensure:
    1. Summary-first: top results + counts in < 2000 tokens default
    2. Reference-based: IDs for on-demand detail retrieval
    3. Confidence indicators: agent can decide whether to deepen

    Blueprint §21.8: output parsimonioso di default, dettaglio on-demand.
    """

    success: bool = Field(description="Whether the operation succeeded")
    summary: str = Field(
        default="",
        description="Human-readable summary of results (concise, < 500 chars default)",
    )
    data: dict[str, object] = Field(
        default_factory=dict,
        description="Structured result data (JSON-parseable, context-efficient)",
    )
    references: dict[str, str] = Field(
        default_factory=dict,
        description="References for on-demand detail: {ref_name: tool_call_hint}",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the result quality",
    )
    detail_available_via: str = Field(
        default="",
        description="Hint for getting full detail (e.g., 'get_shortlist(pool_id=..., limit=50)')",
    )
    session_id: str | None = Field(
        default=None,
        description="Associated session ID for cross-session workflows",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if success=False",
    )
    tokens_used: int = Field(
        default=0,
        ge=0,
        description="Approximate context tokens consumed by this result",
    )


class DiscoverySession(BaseModel):
    """Aggregated discovery session state.

    Combines SessionState with concrete pool references, screening
    progress, and assessment results. This is the session's complete
    view for agent workflow management.

    Blueprint §21.4: cross-session progressive deepening support.
    """

    session_id: str = Field(description="Unique session identifier")
    name: str = Field(default="", description="Human-readable session name")

    # --- Pool References ---
    pool_ids: list[str] = Field(
        default_factory=list,
        description="IDs of candidate pools in this session",
    )
    total_discovered: int = Field(
        default=0,
        ge=0,
        description="Total candidates discovered across all pools",
    )

    # --- Screening Progress ---
    total_screened: int = Field(
        default=0,
        ge=0,
        description="Total candidates screened (Gate 1 or Gate 2)",
    )
    gate1_passed: int = Field(default=0, ge=0, description="Candidates that passed Gate 1")
    gate2_passed: int = Field(default=0, ge=0, description="Candidates that passed Gate 2")

    # --- Assessment Progress ---
    total_assessed: int = Field(
        default=0,
        ge=0,
        description="Candidates with deep assessment (Gate 3)",
    )
    tokens_consumed: int = Field(
        default=0,
        ge=0,
        description="Total LLM tokens consumed in this session",
    )
    tokens_budget: int = Field(
        default=500000,
        gt=0,
        description="Total token budget for this session",
    )

    # --- Ranking Progress ---
    domains_ranked: list[DomainType] = Field(
        default_factory=list,
        description="Domains that have been ranked in this session",
    )
    top_findings_count: int = Field(
        default=0,
        ge=0,
        description="Number of repos identified as hidden gems",
    )

    # --- Status ---
    status: str = Field(
        default="created",
        description="Session status: created, discovering, screening, assessing, ranking, completed, failed",
    )
    current_phase: str = Field(
        default="discovery",
        description="Current phase in the workflow",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Session creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Session last update timestamp",
    )

    @property
    def tokens_remaining(self) -> int:
        """Remaining token budget."""
        return max(0, self.tokens_budget - self.tokens_consumed)

    @property
    def budget_utilization(self) -> float:
        """Budget utilization ratio (0.0-1.0)."""
        if self.tokens_budget == 0:
            return 0.0
        return self.tokens_consumed / self.tokens_budget

    @property
    def screening_yield(self) -> float:
        """Yield ratio: Gate 2 passed / total screened."""
        if self.total_screened == 0:
            return 0.0
        return self.gate2_passed / self.total_screened

    def to_mcp_result(self) -> MCPToolResult:
        """Convert to context-efficient MCP tool result."""
        return MCPToolResult(
            success=True,
            summary=(
                f"Session '{self.name}' ({self.status}): "
                f"{self.total_discovered} discovered, "
                f"{self.gate2_passed}/{self.total_screened} passed screening, "
                f"{self.total_assessed} assessed, "
                f"{self.top_findings_count} hidden gems found"
            ),
            data={
                "session_id": self.session_id,
                "status": self.status,
                "discovered": self.total_discovered,
                "gate2_passed": self.gate2_passed,
                "assessed": self.total_assessed,
                "hidden_gems": self.top_findings_count,
                "budget_used_pct": round(self.budget_utilization * 100, 1),
            },
            references={
                "session": f"get_session(session_id='{self.session_id}')",
                "pools": f"get_candidate_pool(pool_id='<pool_id>')",
                "rankings": f"rank_repos(session_id='{self.session_id}')",
            },
            session_id=self.session_id,
        )
```

### Test: `tests/unit/test_models/test_agent.py`

```python
"""Tests for agentic support models."""

from __future__ import annotations

from github_discovery.models.agent import DiscoverySession, MCPToolResult


class TestMCPToolResult:
    """Test MCP tool result model."""

    def test_success_result(self) -> None:
        """Success result with summary."""
        result = MCPToolResult(
            success=True,
            summary="Found 42 candidates from 3 channels",
            data={"total": 42, "channels": 3},
            references={"detail": "get_candidate_pool(pool_id='pool-123')"},
        )
        assert result.success is True
        assert result.confidence == 1.0

    def test_error_result(self) -> None:
        """Error result with message."""
        result = MCPToolResult(
            success=False,
            error_message="GitHub API rate limit exceeded",
        )
        assert result.success is False
        assert "rate limit" in result.error_message

    def test_context_efficiency(self) -> None:
        """Result tracks tokens used."""
        result = MCPToolResult(
            success=True,
            summary="Screened 100 candidates",
            tokens_used=850,
        )
        assert result.tokens_used == 850

    def test_json_round_trip(self) -> None:
        """Result serializes to/from JSON."""
        result = MCPToolResult(
            success=True,
            summary="Test",
            data={"key": "value"},
        )
        json_str = result.model_dump_json()
        restored = MCPToolResult.model_validate_json(json_str)
        assert restored.success is True


class TestDiscoverySession:
    """Test discovery session model."""

    def test_empty_session(self) -> None:
        """Empty session has zero counts."""
        session = DiscoverySession(session_id="sess-123")
        assert session.total_discovered == 0
        assert session.tokens_remaining == session.tokens_budget

    def test_tokens_remaining(self) -> None:
        """Remaining tokens computed correctly."""
        session = DiscoverySession(
            session_id="sess-123",
            tokens_consumed=200000,
            tokens_budget=500000,
        )
        assert session.tokens_remaining == 300000

    def test_budget_utilization(self) -> None:
        """Budget utilization ratio computed correctly."""
        session = DiscoverySession(
            session_id="sess-123",
            tokens_consumed=250000,
            tokens_budget=500000,
        )
        assert session.budget_utilization == 0.5

    def test_screening_yield(self) -> None:
        """Screening yield ratio computed correctly."""
        session = DiscoverySession(
            session_id="sess-123",
            total_screened=100,
            gate2_passed=15,
        )
        assert session.screening_yield == 0.15

    def test_to_mcp_result(self) -> None:
        """Session can convert to context-efficient MCP result."""
        session = DiscoverySession(
            session_id="sess-123",
            name="test-session",
            status="screening",
            total_discovered=500,
            total_screened=200,
            gate2_passed=30,
            total_assessed=5,
            top_findings_count=3,
            tokens_consumed=100000,
            tokens_budget=500000,
        )
        result = session.to_mcp_result()
        assert result.success is True
        assert "500 discovered" in result.summary
        assert result.data["hidden_gems"] == 3
        assert result.session_id == "sess-123"
```

### Verifica

```bash
mypy src/github_discovery/models/agent.py --strict
pytest tests/unit/test_models/test_agent.py -v
```

---

## 12) Sequenza di implementazione

La sequenza segue le dipendenze reali tra i modelli:

```
Step 1: Task 1.7 — Enums (fix ScoreDimension, aggiungi CandidateStatus)
         │
Step 2: Task 1.1 — RepoCandidate + CandidatePool
         │
         ├─► Step 3: Task 1.2 — Gate 1 screening (SubScore + 7 sub-scores + MetadataScreenResult)
         │
         └─► Step 4: Task 1.3 — Gate 2 screening (4 sub-scores + StaticScreenResult + ScreeningResult)
                     │
                     └─► Step 5: Task 1.4 — Gate 3 assessment (DimensionScore + DeepAssessmentResult)
                                 │
                                 ├─► Step 6: Task 1.5 — Scoring (ScoreResult, ValueScore, RankedRepo, ExplainabilityReport, DomainProfile)
                                 │
                                 ├─► Step 7: Task 1.8 — Feature Store (RepoFeatures)
                                 │
                                 ├─► Step 8: Task 1.6 — API models (request/response wrappers)
                                 │
                                 └─► Step 9: Task 1.9 — Agent models (MCPToolResult, DiscoverySession)
```

**Parallelizzazioni possibili**:
- Steps 3 e 4 (Gate 1 + Gate 2) possono procedere in parallelo dopo Step 2
- Steps 6, 7, 8 possono procedere in parallelo dopo Step 5
- Step 9 può procedere in parallelo con Steps 6-8

**Tempistiche stimate**:
- Step 1-2: 1 giorno (enums fix + modello centrale)
- Steps 3-4: 1-2 giorni (screening models, 11 sub-scores)
- Step 5: 1 giorno (assessment models)
- Steps 6-9: 2-3 giorni (scoring, features, API, agent)
- Test + integrazione: 1 giorno

**Totale stimato**: 6-8 giorni lavorativi

---

## 13) Test plan

### Strategia di test

Ogni nuovo file modello ha un corrispondente file di test in `tests/unit/test_models/`:

```
tests/unit/test_models/
├── __init__.py              # Esistente
├── test_enums.py            # Aggiornare (fix ScoreDimension)
├── test_session.py          # Esistente (Phase 0)
├── test_mcp_spec.py         # Esistente (Phase 0)
├── test_candidate.py        # Nuovo (Task 1.1)
├── test_screening.py        # Nuovo (Tasks 1.2, 1.3)
├── test_assessment.py       # Nuovo (Task 1.4)
├── test_scoring.py          # Nuovo (Task 1.5)
├── test_features.py         # Nuovo (Task 1.8)
├── test_api.py              # Nuovo (Task 1.6)
└── test_agent.py            # Nuovo (Task 1.9)
```

### Criteri di test per ogni modello

1. **Istanziazione**: il modello si crea con defaults sensati
2. **Validazione**: i validator Pydantic rifiutano dati invalidi (range, required fields)
3. **JSON round-trip**: `model_dump_json()` → `model_validate_json()` preserva i dati
4. **Type safety**: `mypy --strict` passa senza errori
5. **Proprietà/computed fields**: i valori derivati sono corretti
6. **Enum alignment**: ScoreDimension ha esattamente 8 valori come da blueprint §7

### Coverage target

- **>90%** su tutti i modelli (sono modelli dati puri, facilmente testabili)
- Ogni sub-score testato per range 0.0-1.0
- ValueScore testato per anti-star bias ordering
- DomainProfile weights testato per somma = 1.0

---

## 14) Criteri di accettazione

Phase 1 è completa quando **tutti** i seguenti criteri sono soddisfatti:

- [ ] `make ci` passa (ruff + mypy --strict + pytest)
- [ ] `ScoreDimension` ha esattamente 8 valori allineati con blueprint §7
- [ ] `RepoCandidate` è istanziabile da un dict GitHub API JSON
- [ ] `MetadataScreenResult` ha 7 sottoscore con range 0.0-1.0
- [ ] `StaticScreenResult` ha 4 sottoscore con range 0.0-1.0
- [ ] `DeepAssessmentResult` ha 8 dimensioni con explanation + evidence + confidence
- [ ] `ScoreResult.value_score` calcola correttamente l'anti-star bias
- [ ] `RankedRepo` ha computed fields per quality_score, value_score, stars
- [ ] `ExplainabilityReport` ha breakdown per dimensione + strengths/weaknesses
- [ ] `DomainProfile` weights sommano a 1.0 per almeno 4 profili
- [ ] `RepoFeatures` supporta SHA dedup e TTL expiry
- [ ] API models sono compatibili con FastAPI serialization
- [ ] `MCPToolResult` ha summary + references + confidence
- [ ] `DiscoverySession.to_mcp_result()` produce output context-efficient
- [ ] `models/__init__.py` esporta l'intero vocabolario del dominio
- [ ] Test coverage >90% su `models/`
- [ ] Nessun warning mypy in `models/`

---

## 15) Rischi e mitigazioni

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| Breaking change in ScoreDimension enum (COMMUNITY→FUNCTIONALITY, NOVELTY→INNOVATION) | Medio — test esistenti da aggiornare | Aggiornare test enums + mcp_spec.py references in stesso commit |
| Pydantic `dict[ScoreDimension, DimensionScore]` serializzazione con enum come chiave | Basso — Pydantic v2 gestisce enum keys nativamente | Verificare con test round-trip JSON |
| `computed_field` in Pydantic v2 compatibilità con FastAPI schema generation | Basso — `computed_field` è supportato in serialization mode | Testare che FastAPI genera schema corretto per ScoreResult |
| Modello troppo grande (RepoCandidate ha ~30 campi) | Basso — inevitabile per catturare GitHub API response | Usare `default_factory` per tutti i campi opzionali |
| API models non allineati con MCP tool specs | Medio — due superfici diverse | Task 1.6 models usano gli stessi tipi dominio; MCP ha i propri parametri |
| Feature Store modello non ancora collegato a backend reale | Basso — il modello definisce solo il contratto dati | Backend SQLite implementato in Phase 2-3 |

---

## 16) Verifica Context7 completata

Le seguenti verifiche Context7 sono state effettuate per informare le decisioni di implementazione:

| Libreria | Pattern verificato | Risultato |
|----------|-------------------|-----------|
| Pydantic v2 | `computed_field` decorator per ValueScore | ✓ Supportato, incluso in JSON schema serialization mode |
| Pydantic v2 | `model_validator(mode='after')` per validazione cross-field | ✓ Disponibile per validazioni composite |
| Pydantic v2 | `field_validator` per validazione per-campo | ✓ Usato per range checks |
| Pydantic v2 | `model_dump_json()` / `model_validate_json()` round-trip | ✓ Funziona con enum keys e nested models |
| Pydantic v2 | `dict[EnumType, ModelType]` serializzazione | ✓ Pydantic v2 gestisce enum come dict keys |

Verifiche precedentemente completate (Phase 0 wiki):
- Pydantic BaseSettings / SettingsConfigDict patterns ✓
- pydantic-settings nested delimiter support ✓
- structlog stdlib ProcessorFormatter integration ✓
- MCP FastMCP tool/resource/prompt decorators ✓
- pytest import-mode=importlib for src layout ✓

---

*Stato documento: Draft Phase 1 Implementation Plan v1*
*Data: 2026-04-22*
*Basato su: Phase 0 completata, wiki articles (tiered-pipeline, scoring-dimensions, screening-gates, domain-strategy), Context7 verification*
