# GitHub Discovery — Phase 4 Implementation Plan

## Meta

- **Stato**: Draft v1
- **Data**: 2026-04-23
- **Riferimento roadmap**: `docs/roadmaps/github-discovery_foundation_roadmap.md` — Phase 4
- **Riferimento blueprint**: `docs/foundation/github-discovery_foundation_blueprint.md` — §6 (Layer C), §16.5
- **Riferimento wiki**: `docs/llm-wiki/wiki/` — articoli su tiered pipeline, scoring dimensions, screening gates, tech stack
- **Durata stimata**: 2-3 settimane
- **Milestone**: M3 — Deep Assessment MVP (Deep scan LLM con budget control, caching SHA)
- **Dipendenza**: Phase 0+1+2+3 completate (459 tests passing, `make ci` verde)
- **LLM Provider**: NanoGPT (https://nano-gpt.com) con subscription — OpenAI-compatible API

---

## Indice

1. [Obiettivo](#1-obiettivo)
2. [Task Overview](#2-task-overview)
3. [Architettura del modulo assessment](#3-architettura-del-modulo-assessment)
4. [Decisione LLM Provider: NanoGPT](#4-decisione-llm-provider-nanogpt)
5. [Task 4.1 — Repomix Integration](#5-task-41--repomix-integration)
6. [Task 4.2 — LLM Provider Abstraction](#6-task-42--llm-provider-abstraction)
7. [Task 4.3 — Multi-Dimension Assessment Prompts](#7-task-43--multi-dimension-assessment-prompts)
8. [Task 4.4 — Assessment Result Parser](#8-task-44--assessment-result-parser)
9. [Task 4.5 — Code Structure Heuristic Scoring](#9-task-45--code-structure-heuristic-scoring)
10. [Task 4.6 — Language-Specific Quality Analyzers](#10-task-46--language-specific-quality-analyzers)
11. [Task 4.7 — LLM Budget Controller](#11-task-47--llm-budget-controller)
12. [Task 4.8 — Deep Assessment Orchestrator](#12-task-48--deep-assessment-orchestrator)
13. [Sequenza di implementazione](#13-sequenza-di-implementazione)
14. [Test plan](#14-test-plan)
15. [Criteri di accettazione](#15-criteri-di-accettazione)
16. [Rischi e mitigazioni](#16-rischi-e-mitigazioni)
17. [Verifica Context7 completata](#17-verifica-context7-completata)

---

## 1) Obiettivo

Implementare Gate 3 (Deep Technical Assessment) — la valutazione tecnica ad alta precisione tramite LLM + euristiche, con budget control rigoroso. Solo il top percentile (10-15%) dai candidati che hanno passato Gate 1 + Gate 2 viene valutato.

Al completamento della Phase 4:

- Repomix integra il packing della codebase in formato LLM-friendly
- LLM provider abstraction con supporto structured output (JSON schema) via NanoGPT
- 8 dimensioni di valutazione con prompt template specifici per dimensione
- Budget controller con hard limits per-repo e per-day, timeout e early-stop
- Caching obbligatorio per commit SHA (dedup, nessun ricalcolo)
- Heuristic scoring non-LLM per code structure e language-specific quality
- Result parser robusto con gestione formati LLM variabili
- Deep assessment orchestrator che coordina l'intero flusso
- Tutti i moduli passano `mypy --strict` e `ruff check`
- Test coverage >80% sulla logica di assessment

### Regola critica (Blueprint §16.5)

> Massimo budget token/giorno e per repo. Timeout e early-stop obbligatori. Caching per commit SHA.

---

## 2) Task Overview

| Task ID | Task | Priorità | Dipendenze | Output verificabile |
|---------|------|----------|------------|---------------------|
| 4.1 | Repomix Integration | Critica | Phase 3 | Packing codebase in file singolo LLM-friendly, token counting |
| 4.2 | LLM Provider Abstraction | Critica | Nessuna | Chiamata NanoGPT con structured output (JSON schema) |
| 4.3 | Multi-Dimension Assessment Prompts | Critica | 4.2 | Prompt template per 8 dimensioni, output LLM parseable |
| 4.4 | Assessment Result Parser | Critica | 4.2, models/assessment.py | Parsing robusto risposta LLM → DeepAssessmentResult |
| 4.5 | Code Structure Heuristic Scoring | Alta | Nessuna | Score euristico su repo multi-module |
| 4.6 | Language-Specific Quality Analyzers | Media | 4.5 | Almeno Python adapter (ruff) operativo |
| 4.7 | LLM Budget Controller | Critica | 4.2 | Hard limits rispettati, nessun overflow di budget |
| 4.8 | Deep Assessment Orchestrator | Critica | 4.1-4.7 | Pipeline end-to-end su 5-10 repo reali |

---

## 3) Architettura del modulo assessment

### Struttura directory

```
src/github_discovery/assessment/
├── __init__.py                # Export pubblici del package assessment
├── repomix_adapter.py         # Repomix integration per codebase packing
├── llm_provider.py            # LLM provider abstraction (NanoGPT via instructor+openai)
├── result_parser.py           # Parsing robusto risposta LLM → DeepAssessmentResult
├── heuristics.py              # Code structure heuristic scoring (non-LLM)
├── budget_controller.py       # LLM token budget controller
├── orchestrator.py            # Deep assessment orchestrator
├── prompts/                   # Prompt templates per dimensione
│   ├── __init__.py
│   ├── base.py                # Base prompt template class + shared instructions
│   ├── code_quality.py        # Code Quality dimension prompt
│   ├── architecture.py        # Architecture & Modularity dimension prompt
│   ├── testing.py             # Testability & Verification dimension prompt
│   ├── documentation.py       # Documentation & Developer Experience prompt
│   ├── maintenance.py         # Maintenance & Project Operations prompt
│   ├── security.py            # Security & Supply Chain Hygiene prompt
│   ├── functionality.py       # Functional Completeness prompt
│   └── innovation.py          # Innovation & Distinctiveness prompt
└── lang_analyzers/            # Language-specific quality analyzers
    ├── __init__.py
    ├── base.py                # Base analyzer interface
    └── python_analyzer.py     # Python-specific (ruff subprocess)

tests/
├── unit/
│   └── assessment/
│       ├── test_repomix_adapter.py
│       ├── test_llm_provider.py
│       ├── test_result_parser.py
│       ├── test_heuristics.py
│       ├── test_budget_controller.py
│       ├── test_orchestrator.py
│       ├── test_prompts/
│       │   ├── test_base_prompt.py
│       │   └── test_dimension_prompts.py
│       ├── test_python_analyzer.py
│       └── conftest.py         # Shared fixtures (mock LLM responses, sample packed repos)
└── integration/
    └── assessment/
        └── test_assessment_e2e.py  # End-to-end with real NanoGPT (marked @pytest.mark.integration)
```

### Modelli esistenti riutilizzati (Phase 1)

Da `models/assessment.py` — tutti già implementati e testati:

| Modello | Utilizzo in Phase 4 |
|---------|---------------------|
| `DimensionScore` | Output per ogni dimensione valutata (value, explanation, evidence, confidence) |
| `TokenUsage` | Tracking token per budget control |
| `DeepAssessmentResult` | Output composito Gate 3 con 8 dimensioni, overall_quality, gate3_pass |

Da `models/enums.py`:

| Modello | Utilizzo |
|---------|----------|
| `ScoreDimension` | Enum con le 8 dimensioni di valutazione |
| `GateLevel.DEEP_ASSESSMENT` | Livello Gate 3 |

Da `config.py`:

| Modello | Utilizzo |
|---------|----------|
| `AssessmentSettings` | `max_tokens_per_repo`, `max_tokens_per_day`, `llm_provider`, `llm_model`, `cache_ttl_hours` |

Da `exceptions.py`:

| Modello | Utilizzo |
|---------|----------|
| `AssessmentError` | Errore dominio assessment |
| `BudgetExceededError` | Budget token superato |
| `HardGateViolationError` | Tentativo di assessment senza Gate 1+2 pass |

Da `models/features.py`:

| Modello | Utilizzo |
|---------|----------|
| `RepoFeatures` | Feature store per caching (key: full_name + commit_sha) |
| `FeatureStoreKey` | Chiave composita per lookup cache |

### Flusso dati

```
RepoCandidate (from PoolManager, con gate1_pass=True, gate2_pass=True)
    │
    ├── [Hard Gate Check] ── gate1_pass AND gate2_pass must be True
    │       └── Fail → HardGateViolationError
    │
    ├── [Cache Check] ── FeatureStore.get(full_name, commit_sha)
    │       └── Hit → Return cached DeepAssessmentResult (cached=True)
    │
    ├── [Budget Check] ── BudgetController.can_assess(repo)
    │       └── Fail → BudgetExceededError
    │
    ├── [Repomix Packing] ── RepomixAdapter.pack(candidate)
    │       ├── Remote pack via python-repomix
    │       ├── Token count check (< max_tokens_per_repo)
    │       ├── Compression if needed (interface mode: signatures + docstrings)
    │       └── Output: packed_code (string), token_count, file_count
    │
    ├── [Heuristic Scoring] ── HeuristicScorer.score(packed_code, metadata)
    │       ├── Directory structure analysis → modularity signal
    │       ├── Import analysis → coupling signal
    │       ├── Language-specific analyzer (if available)
    │       └── Output: dict[ScoreDimension, DimensionScore] (method="heuristic")
    │
    ├── [LLM Assessment — per dimension or batch] ── LLMProvider.assess()
    │       ├── Build prompt from dimension template + packed_code
    │       ├── Call NanoGPT via instructor with structured output
    │       ├── Parse response → DimensionScore (method="llm")
    │       ├── Retry on validation failure (max 2 retries)
    │       └── Track token usage via BudgetController
    │
    ├── [Result Composition] ── orchestrator
    │       ├── Merge LLM + heuristic dimension scores
    │       ├── Compute overall_quality (weighted composite)
    │       ├── Compute overall_confidence (min dimension confidence)
    │       ├── Apply gate3_threshold → gate3_pass
    │       └── Build DeepAssessmentResult
    │
    ├── [Cache Store] ── FeatureStore.put(full_name, commit_sha, result)
    │
    └── [Return] ── DeepAssessmentResult
```

---

## 4) Decisione LLM Provider: NanoGPT

### Perché NanoGPT

NanoGPT (https://nano-gpt.com) è un provider LLM con API **OpenAI-compatible** che aggrega multipli modelli (OpenAI GPT, Anthropic Claude, Google Gemini, modelli open-source). L'utente ha una subscription attiva.

### Caratteristiche chiave per Phase 4

| Feature | Dettaglio | Impatto su implementazione |
|---------|-----------|---------------------------|
| **OpenAI-compatible** | `POST /api/v1/chat/completions` formato identico a OpenAI | Possiamo usare `openai` SDK con `base_url` custom |
| **Subscription endpoint** | `https://nano-gpt.com/api/subscription/v1/chat/completions` | Usare questo endpoint per inclusione subscription |
| **Structured Output** | `response_format` con `json_schema` (OpenAI-compatible) | Direttamente mappabile ai nostri Pydantic models |
| **Multi-modello** | `openai/gpt-5.1`, `anthropic/claude-sonnet-4.5`, `google/gemini-3-flash-preview` | Fallback tra modelli se uno fallisce |
| **Prompt Caching** | Implicit caching + esplicito con `cache_control` | Riduzione costo su prompt ripetitivi (assessment templates) |
| **Usage tracking** | `usage.prompt_tokens`, `usage.completion_tokens` (standard OpenAI format) | Budget tracking nativo |

### Stack LLM scelto

**`instructor` + `openai` SDK** — Non usiamo `litellm` (overkill, NanoGPT già gestisce multi-provider).

Motivazione:
1. `openai` Python SDK con `base_url="https://nano-gpt.com/api/v1"` → compatibilità diretta
2. `instructor` wrappa l'SDK per structured output con validazione Pydantic automatica + retry
3. Retry su validation failure (LLM produce JSON non conforme → retry con feedback)
4. Supporto async nativo (`instructor.from_provider("openai/...", async_client=True)`)
5. Zero overhead aggiuntivo — non serve un layer multi-provider

### Configurazione

```python
# config.py — AssessmentSettings update

class AssessmentSettings(BaseSettings):
    """Deep assessment (Gate 3) settings."""

    model_config = SettingsConfigDict(
        env_prefix="GHDISC_ASSESSMENT_",
        env_file=".env",
    )

    # --- LLM Connection ---
    llm_api_key: str = Field(
        default="",
        description="NanoGPT API key (or OpenAI-compatible key)",
    )
    llm_base_url: str = Field(
        default="https://nano-gpt.com/api/v1",
        description="LLM API base URL (NanoGPT default)",
    )
    llm_subscription_mode: bool = Field(
        default=True,
        description="Use subscription endpoint instead of pay-as-you-go",
    )
    llm_model: str = Field(
        default="openai/gpt-4o",
        description="LLM model identifier (provider/model format for NanoGPT)",
    )
    llm_fallback_model: str = Field(
        default="anthropic/claude-sonnet-4-20250514",
        description="Fallback model if primary fails",
    )
    llm_temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
        description="LLM temperature for assessment (low = more deterministic)",
    )

    # --- Budget ---
    max_tokens_per_repo: int = Field(
        default=50000,
        description="Max LLM tokens per repo assessment",
    )
    max_tokens_per_day: int = Field(
        default=500000,
        description="Max LLM tokens per day budget",
    )
    max_retries_per_dimension: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Max retries for LLM validation failures",
    )

    # --- Caching ---
    cache_ttl_hours: int = Field(
        default=24,
        description="Cache TTL for assessment results (hours)",
    )

    @property
    def effective_base_url(self) -> str:
        """Get the effective base URL based on subscription mode."""
        if self.llm_subscription_mode:
            return self.llm_base_url.replace("/api/v1", "/api/subscription/v1")
        return self.llm_base_url
```

---

## 5) Task 4.1 — Repomix Integration

### Obiettivo

Wrappare `python-repomix` per impacchettare una codebase GitHub in un file singolo LLM-friendly, con token counting e gestione repo grandi (timeout, early-stop, compressione).

### Context7: Pattern verificati

Da `/andersonby/python-repomix`:

- `RepoProcessor(repo_url=url, config=config).process()` — packing programmatico da URL remoto
- `RepomixConfig` con opzioni: `output.file_path`, `output.style`, `output.calculate_tokens`, `compression`
- Interface mode: `compression.keep_signatures=True`, `compression.keep_docstrings=True` → rimuove implementation bodies
- Token counting: `config.output.calculate_tokens = True`
- Output styles: `"plain"`, `"markdown"`, `"xml"`

### Design

```python
# assessment/repomix_adapter.py

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from github_discovery.models.candidate import RepoCandidate


class PackedRepo(BaseModel):
    """Result of repomix packing operation."""

    content: str = Field(description="Packed codebase content (single file)")
    total_files: int = Field(default=0, ge=0, description="Number of files packed")
    total_tokens: int = Field(default=0, ge=0, description="Token count of packed content")
    truncated: bool = Field(
        default=False,
        description="Whether content was truncated to fit token budget",
    )
    compression_used: bool = Field(
        default=False,
        description="Whether interface-mode compression was applied",
    )


class RepomixAdapter:
    """Packs GitHub repositories into LLM-friendly single-file format.

    Uses python-repomix library for programmatic repo packing.
    Supports:
    - Remote repo packing (no local clone needed)
    - Token counting for budget awareness
    - Interface-mode compression for large repos
    - Timeout and early-stop for very large repos
    """

    def __init__(
        self,
        max_tokens: int = 50000,
        timeout_seconds: int = 120,
    ) -> None: ...

    async def pack(self, candidate: RepoCandidate) -> PackedRepo:
        """Pack a repository into a single LLM-friendly file.

        1. Try full pack with token counting
        2. If token count > max_tokens, retry with interface-mode compression
        3. If still too large, truncate with warning

        Args:
            candidate: Repository to pack (uses candidate.url for remote packing)

        Returns:
            PackedRepo with content, token count, and metadata
        """
        ...

    async def pack_with_compression(self, candidate: RepoCandidate) -> PackedRepo:
        """Pack using interface mode (signatures + docstrings only).

        Useful for very large repos where full content exceeds token budget.
        Keeps function signatures and docstrings, removes implementation bodies.
        """
        ...
```

### Implementazione dettagliata

1. **Full pack**: Crea `RepomixConfig` con `output.style = "markdown"`, `output.calculate_tokens = True`, chiama `RepoProcessor(repo_url=candidate.url).process()`
2. **Token check**: Se `result.total_tokens > max_tokens` → ritenta con interface-mode compression
3. **Compression**: `config.compression.enabled = True`, `config.compression.keep_signatures = True`, `config.compression.keep_docstrings = True`
4. **Truncation**: Se compresso ancora troppo grande → tronca il contenuto e marca `truncated=True`
5. **Security**: `config.security.enable_security_check = True` per escludere file sensibili
6. **Timeout**: `asyncio.wait_for` con timeout configurabile (default 120s)
7. **Error handling**: Se repomix fallisce → `AssessmentError` con contesto repo

### Dipendenza pyproject.toml

```toml
dependencies = [
    # ... existing ...
    "python-repomix>=0.1.0",    # Programmatic repo packing for LLM assessment
]
```

### Test plan

- `test_repomix_adapter.py`:
  - `test_pack_returns_packed_repo`: Mock repomix → PackedRepo con content e tokens
  - `test_pack_counts_tokens`: Token counting configurato e funzionante
  - `test_pack_truncation_on_large_repo`: Mock repo > max_tokens → truncated=True
  - `test_pack_compression_for_large_repo`: Mock repo > max_tokens → ritenta con compression
  - `test_pack_timeout`: Mock timeout → AssessmentError
  - `test_pack_invalid_repo`: Mock repo inesistente → AssessmentError
  - `test_pack_security_check_enabled`: Security check configurazione verificata

### Criterio di verifica

```bash
pytest tests/unit/assessment/test_repomix_adapter.py -v   # 7 tests passing
mypy src/github_discovery/assessment/repomix_adapter.py --strict
```

---

## 6) Task 4.2 — LLM Provider Abstraction

### Obiettivo

Interfaccia astratta per provider LLM che supporti structured output (JSON schema) via NanoGPT, con fallback tra modelli, retry su validation failure, e tracking token usage.

### Context7: Pattern verificati

Da `/websites/python_useinstructor` (instructor):
- `instructor.from_provider("openai/...", async_client=True)` — client async con structured output
- `client.create(response_model=PydanticModel, messages=[...])` — extraction con validazione automatica
- `max_retries=Retrying(stop=stop_after_attempt(2), wait=wait_fixed(1))` — retry configurabile
- Supporto multi-provider: `instructor.from_provider("openai/...")`, `instructor.from_provider("anthropic/...")`

Da NanoGPT docs:
- Endpoint: `https://nano-gpt.com/api/v1/chat/completions` (paygo) o `/api/subscription/v1/chat/completions` (subscription)
- Structured output: `response_format` con `json_schema` — supportato da OpenAI, Anthropic, Gemini
- Usage tracking: `usage.prompt_tokens`, `usage.completion_tokens` nel response

### Design

```python
# assessment/llm_provider.py

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel

from github_discovery.models.assessment import TokenUsage


class LLMResponse[T: BaseModel](BaseModel):
    """Typed LLM response with structured output and usage tracking."""

    data: T
    token_usage: TokenUsage
    model_used: str
    provider: str
    retries_used: int = 0


class LLMProvider(ABC):
    """Abstract interface for LLM providers.

    Supports structured output (JSON schema via Pydantic models),
    automatic retry on validation failure, and token usage tracking.
    """

    @abstractmethod
    async def assess_structured(
        self,
        response_model: type[T],
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_retries: int = 2,
    ) -> LLMResponse[T]:
        """Send messages and get structured, validated Pydantic output.

        Args:
            response_model: Pydantic model class for structured output
            messages: Chat messages in OpenAI format
            temperature: Sampling temperature
            max_retries: Max retries on validation failure

        Returns:
            LLMResponse with validated data and token usage
        """
        ...


class NanoGPTProvider(LLMProvider):
    """NanoGPT LLM provider using instructor + openai SDK.

    Configuration via AssessmentSettings:
    - llm_api_key: API key
    - effective_base_url: subscription or paygo endpoint
    - llm_model: primary model (e.g. "openai/gpt-4o")
    - llm_fallback_model: fallback model
    """

    def __init__(self, settings: AssessmentSettings) -> None: ...

    async def assess_structured(
        self,
        response_model: type[T],
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_retries: int = 2,
    ) -> LLMResponse[T]:
        """Structured assessment via NanoGPT with validation and retry.

        1. Try primary model with structured output
        2. On failure (validation, API error): retry with same model
        3. On persistent failure: try fallback model
        4. Track token usage for budget controller
        """
        ...
```

### Implementazione dettagliata

1. **Client setup**: Crea `openai.AsyncOpenAI(base_url=settings.effective_base_url, api_key=settings.llm_api_key)` → wrappa con `instructor.from_openai(client)`
2. **Structured output**: Usa `client.chat.completions.create(response_model=response_model, messages=messages)` — instructor gestisce JSON schema extraction e validazione
3. **Retry**: Instructor内置 retry via `max_retries` parameter — se Pydantic validation fallisce, ritenta automaticamente
4. **Fallback**: Se primary model fallisce dopo tutti i retry → prova fallback model
5. **Token tracking**: Estrai `response.response_metadata` per `prompt_tokens`, `completion_tokens`
6. **Error isolation**: Wrappa tutte le eccezioni LLM in `AssessmentError` con contesto

### Dipendenze pyproject.toml

```toml
dependencies = [
    # ... existing ...
    "openai>=1.30",      # OpenAI SDK (used with NanoGPT custom base_url)
    "instructor>=1.4",   # Structured output with Pydantic validation + retry
]
```

### Test plan

- `test_llm_provider.py`:
  - `test_assess_structured_returns_validated_data`: Mock instructor → LLMResponse con dati validati
  - `test_assess_structured_validates_pydantic`: Mock risposta non conforme → retry
  - `test_assess_structured_tracks_tokens`: Token usage estratto correttamente
  - `test_fallback_on_primary_failure`: Mock primary failure → fallback model usato
  - `test_error_wrapping`: Mock API error → AssessmentError
  - `test_subscription_url_used`: Verifica base_url con subscription mode
  - `test_retry_on_validation_failure`: Mock validation fail → retry count incrementato

### Criterio di verifica

```bash
pytest tests/unit/assessment/test_llm_provider.py -v   # 7 tests passing
mypy src/github_discovery/assessment/llm_provider.py --strict
```

---

## 7) Task 4.3 — Multi-Dimension Assessment Prompts

### Obiettivo

Creare prompt template per ciascuna delle 8 dimensioni di valutazione (Blueprint §7), con istruzioni per scoring + explanation + evidence. Ogni prompt è domain-aware e produce output parseable.

### Design

```python
# assessment/prompts/base.py

from __future__ import annotations

from github_discovery.models.enums import DomainType, ScoreDimension


class DimensionPrompt:
    """Base class for dimension assessment prompts.

    Each dimension has:
    - A system prompt with scoring criteria
    - A user prompt template that includes packed code + metadata
    - Domain-specific adjustments
    - Output schema for structured extraction
    """

    dimension: ScoreDimension
    description: str
    scoring_criteria: list[str]

    def build_messages(
        self,
        packed_code: str,
        repo_full_name: str,
        repo_metadata: str,
        domain: DomainType = DomainType.OTHER,
    ) -> list[dict[str, str]]:
        """Build chat messages for this dimension assessment.

        Returns:
            List of messages: system prompt + user prompt with code
        """
        ...

    def get_system_prompt(self, domain: DomainType) -> str:
        """Get system prompt with scoring criteria.

        Includes domain-specific weighting adjustments.
        """
        ...

    def get_user_prompt(
        self,
        packed_code: str,
        repo_full_name: str,
        repo_metadata: str,
    ) -> str:
        """Get user prompt with packed code and metadata.

        Instructs the LLM to:
        1. Analyze the codebase for this specific dimension
        2. Provide a score (0.0-1.0) with explanation
        3. List specific evidence (observations from the code)
        4. Indicate confidence level
        """
        ...
```

```python
# assessment/prompts/code_quality.py — Example dimension prompt

class CodeQualityPrompt(DimensionPrompt):
    """Code Quality dimension assessment prompt.

    Scoring criteria:
    - Code style consistency and adherence to language conventions
    - Complexity management (functions/methods not overly complex)
    - Error handling patterns
    - Naming conventions
    - Static analysis signals
    """

    dimension = ScoreDimension.CODE_QUALITY
    description = "Code Quality"
    scoring_criteria = [
        "Consistent code style and formatting",
        "Appropriate complexity levels (no god functions)",
        "Comprehensive error handling",
        "Clear naming conventions",
        "Absence of code smells (duplication, dead code)",
        "Use of language-specific idioms and best practices",
    ]
```

### Struttura prompt per ogni dimensione

Ogni prompt produce un output JSON con questo schema (mappato a `DimensionScore`):

```json
{
    "value": 0.75,
    "explanation": "The codebase demonstrates good code quality with consistent formatting...",
    "evidence": [
        "Uses ruff for linting (pyproject.toml has ruff config)",
        "Error handling via custom exception hierarchy (exceptions.py)",
        "Type annotations present on all public functions"
    ],
    "confidence": 0.8
}
```

### Dimensioni e criteri di scoring

| Dimensione | Prompt File | Criteri principali |
|------------|------------|-------------------|
| Code Quality | `code_quality.py` | Stile, complessità, error handling, naming, code smells |
| Architecture | `architecture.py` | Modularity, coupling, abstraction layers, API surface, directory structure |
| Testing | `testing.py` | Test presence, coverage, test quality, CI integration, test patterns |
| Documentation | `documentation.py` | README quality, API docs, guides, docstrings, onboarding friction |
| Maintenance | `maintenance.py` | Commit cadence, release discipline, issue management, bus factor |
| Security | `security.py` | Dependency pinning, secret hygiene, vulnerability management, Scorecard signals |
| Functionality | `functionality.py` | Feature completeness, API coverage, use-case fit, scope appropriateness |
| Innovation | `innovation.py` | Novel approaches, unique positioning, technical creativity, differentiation |

### Domain-specific adjustments

I prompt si adattano al dominio:

```python
_DOMAIN_FOCUS: dict[DomainType, dict[ScoreDimension, str]] = {
    DomainType.CLI: {
        ScoreDimension.TESTING: "CLI tools need comprehensive integration testing for command parsing",
        ScoreDimension.DOCUMENTATION: "CLI tools require clear usage docs, help text, and examples",
    },
    DomainType.ML_LIB: {
        ScoreDimension.INNOVATION: "ML libraries are valued for novel architectures and training approaches",
        ScoreDimension.DOCUMENTATION: "ML libraries need API docs, tutorials, and model cards",
    },
    # ... altri domini
}
```

### Test plan

- `test_prompts/test_base_prompt.py`:
  - `test_build_messages_returns_list`: Output è lista di dict con "role" e "content"
  - `test_system_prompt_includes_criteria`: System prompt contiene criteri di scoring
  - `test_user_prompt_includes_code`: User prompt contiene packed code
  - `test_domain_adjustments_applied`: Domain-specific adjustments inclusi
- `test_prompts/test_dimension_prompts.py`:
  - `test_all_dimensions_have_prompts`: 8 prompt files, uno per dimensione
  - `test_prompts_produce_valid_schema`: Output schema mappa a DimensionScore
  - `test_code_quality_prompt_criteria`: Criteri specifici per code quality
  - `test_architecture_prompt_criteria`: Criteri specifici per architecture

### Criterio di verifica

```bash
pytest tests/unit/assessment/test_prompts/ -v   # 9 tests passing
```

---

## 8) Task 4.4 — Assessment Result Parser

### Obiettivo

Parsing robusto della risposta LLM (JSON) in `DeepAssessmentResult` Pydantic model, con gestione di formati LLM variabili e fallback su parsing parziale.

### Design

```python
# assessment/result_parser.py

from __future__ import annotations

from github_discovery.models.assessment import (
    DeepAssessmentResult,
    DimensionScore,
    TokenUsage,
)
from github_discovery.models.enums import ScoreDimension


class AssessmentResultParser:
    """Parses LLM responses into DeepAssessmentResult models.

    Handles:
    - Structured JSON from instructor (happy path)
    - Partial JSON when LLM produces incomplete output
    - Malformed responses with graceful degradation
    - Missing dimensions with confidence adjustment
    """

    def parse_single_dimension(
        self,
        dimension: ScoreDimension,
        raw_response: dict[str, object],
    ) -> DimensionScore:
        """Parse a single dimension assessment response.

        Validates and normalizes:
        - value clamped to 0.0-1.0
        - explanation defaults to empty string
        - evidence defaults to empty list
        - confidence clamped to 0.0-1.0
        """
        ...

    def parse_full_assessment(
        self,
        full_name: str,
        commit_sha: str,
        dimension_responses: dict[ScoreDimension, dict[str, object]],
        token_usage: TokenUsage,
        duration_seconds: float,
        *,
        gate3_threshold: float = 0.6,
    ) -> DeepAssessmentResult:
        """Compose a full DeepAssessmentResult from dimension responses.

        1. Parse each dimension response
        2. Compute weighted overall_quality
        3. Compute overall_confidence (min of dimension confidences)
        4. Apply gate3_threshold
        5. Build DeepAssessmentResult with all metadata
        """
        ...

    def parse_partial_assessment(
        self,
        full_name: str,
        commit_sha: str,
        dimension_responses: dict[ScoreDimension, dict[str, object]],
        failed_dimensions: list[ScoreDimension],
        token_usage: TokenUsage,
        duration_seconds: float,
        error_context: str,
    ) -> DeepAssessmentResult:
        """Build a partial result when some dimensions failed.

        Failed dimensions get DimensionScore with:
        - value=0.0, confidence=0.0
        - explanation with error context
        - assessment_method="failed"
        """
        ...
```

### Implementazione dettagliata

1. **Happy path**: Instructor restituisce già un Pydantic model validato → `DimensionScore(**validated_data)`
2. **Partial parsing**: Se alcune dimensioni mancano → `parse_partial_assessment` con dimensioni fallite marcate
3. **Value normalization**: `max(0.0, min(1.0, raw_value))` — clamp forzato
4. **Evidence sanitization**: Lista di stringhe, massimo 10 elementi, ognuno max 200 chars
5. **Overall quality**: Media pesata delle dimensioni usando i pesi default (Blueprint §7)
6. **Gate3 pass**: `overall_quality >= gate3_threshold`

### Test plan

- `test_result_parser.py`:
  - `test_parse_single_dimension_valid`: Input valido → DimensionScore corretto
  - `test_parse_single_dimension_value_clamped`: Value > 1.0 → clamped a 1.0
  - `test_parse_single_dimension_missing_fields`: Campi mancanti → defaults
  - `test_parse_full_assessment_all_dimensions`: 8 dimensioni → DeepAssessmentResult completo
  - `test_parse_full_assessment_computes_overall_quality`: Overall quality = media pesata
  - `test_parse_full_assessment_gate3_pass`: Quality > threshold → gate3_pass=True
  - `test_parse_full_assessment_gate3_fail`: Quality < threshold → gate3_pass=False
  - `test_parse_partial_assessment`: Alcune dimensioni fallite → partial result con confidence bassa
  - `test_parse_evidence_sanitized`: Evidence troppo lunghe → troncate

### Criterio di verifica

```bash
pytest tests/unit/assessment/test_result_parser.py -v   # 9 tests passing
mypy src/github_discovery/assessment/result_parser.py --strict
```

---

## 9) Task 4.5 — Code Structure Heuristic Scoring

### Obiettivo

Euristiche non-LLM per code structure analysis: modularity, coupling, abstraction layers, API surface. Forniscono un baseline score senza costo LLM e arricchiscono l'assessment LLM.

### Design

```python
# assessment/heuristics.py

from __future__ import annotations

from github_discovery.models.assessment import DimensionScore
from github_discovery.models.enums import ScoreDimension


class HeuristicScorer:
    """Non-LLM heuristic scoring for code structure analysis.

    Provides baseline scores for architecture dimensions
    without LLM cost. Used as:
    1. Pre-enrichment for LLM assessment (additional signals)
    2. Fallback when LLM assessment fails
    3. Confidence cross-check against LLM scores
    """

    def score_modularity(self, packed_content: str) -> DimensionScore:
        """Score modularity from directory structure in packed content.

        Signals:
        - Number of top-level directories (more = more modular, up to a point)
        - Depth of directory tree (too deep = over-engineering)
        - Presence of common module patterns (src/, lib/, pkg/)
        """
        ...

    def score_coupling(self, packed_content: str) -> DimensionScore:
        """Score coupling from import patterns.

        Signals:
        - Cross-module imports vs self-contained modules
        - Circular dependency indicators
        - External dependency count
        """
        ...

    def score_api_surface(self, packed_content: str) -> DimensionScore:
        """Score API surface quality.

        Signals:
        - Public vs private function ratio (convention: _ prefix)
        - Presence of type hints / annotations
        - __init__.py exports pattern
        """
        ...

    def score_all(
        self,
        packed_content: str,
    ) -> dict[ScoreDimension, DimensionScore]:
        """Run all heuristic scorers.

        Returns dimension scores for:
        - architecture (from modularity + coupling + api_surface)
        - code_quality (from naming patterns, import patterns)
        - testing (from test file detection in packed content)
        """
        ...
```

### Implementazione dettagliata

1. **Modularity analysis**: Parse directory structure dal packed content (Repomix include directory tree). Conta moduli, profondità, distribuzione file.
2. **Coupling analysis**: Regex per import statements nel packed content. Conta cross-module imports.
3. **API surface**: Conta `def ` vs `def _` (pubblica vs privata), presenza type annotations (`: str`, `-> int`).
4. **Test detection**: Conta file con pattern `test_`/`_test.` nel packed content → proxy per test footprint.
5. **Confidence**: Sempre `0.5` per heuristic scores (media, meno affidabile di LLM).
6. **assessment_method**: `"heuristic"` per tutti i punteggi generati.

### Test plan

- `test_heuristics.py`:
  - `test_score_modularity_mono_module`: Single module → score basso modularity
  - `test_score_modularity_multi_module`: Multi-module → score alto modularity
  - `test_score_coupling_loose`: Poochi cross-imports → score alto
  - `test_score_coupling_tight`: Molti cross-imports → score basso
  - `test_score_api_surface_public_private`: Buon ratio pubblico/privato → score alto
  - `test_score_all_returns_dimensions`: Output contiene dimensioni expected
  - `test_heuristic_confidence_is_medium`: Confidence sempre 0.5
  - `test_empty_content`: Content vuoto → score 0.0, confidence 0.0

### Criterio di verifica

```bash
pytest tests/unit/assessment/test_heuristics.py -v   # 8 tests passing
```

---

## 10) Task 4.6 — Language-Specific Quality Analyzers

### Obiettivo

Adapter per analizzatori specifici per linguaggio: `ruff` (Python), `eslint` config presence (JS), `cargo clippy` (Rust). Solo dove disponibile, con fallback graceful.

### Design

```python
# assessment/lang_analyzers/base.py

from __future__ import annotations

from abc import ABC, abstractmethod

from github_discovery.models.assessment import DimensionScore


class LanguageAnalyzer(ABC):
    """Base class for language-specific quality analyzers."""

    @abstractmethod
    def language(self) -> str:
        """Language this analyzer handles (e.g. 'python', 'javascript')."""
        ...

    @abstractmethod
    async def analyze(self, clone_dir: str) -> DimensionScore | None:
        """Run language-specific analysis on a cloned repo.

        Returns None if the analyzer is not available or not applicable.
        """
        ...


# assessment/lang_analyzers/python_analyzer.py

class PythonAnalyzer(LanguageAnalyzer):
    """Python code quality analysis via ruff subprocess.

    Runs: ruff check --output-format json <dir>
    Parses JSON output for issue count, severity, rule codes.

    Falls back gracefully if ruff is not installed.
    """

    def language(self) -> str:
        return "python"

    async def analyze(self, clone_dir: str) -> DimensionScore | None:
        """
        1. Check if ruff is available
        2. Run ruff check --output-format json
        3. Parse issues by severity
        4. Compute score based on issue density
        """
        ...
```

### Implementazione dettagliata

1. **Python (ruff)**: `ruff check --output-format json <dir>` → parse issues → score basato su issue density (issues / LOC)
2. **Scoring**: 0 issues = 1.0, < 0.01 issues/LOC = 0.8, < 0.05 = 0.5, > 0.1 = 0.2
3. **Fallback**: Se ruff non installato → `None` (il pipeline continua senza)
4. **Future**: Altri analyzer (JS, Rust) saranno aggiunti in fasi successive

### Dipendenza esterna

`ruff` deve essere installato (`pip install ruff`). Già nel nostro tooling stack.

### Test plan

- `test_python_analyzer.py`:
  - `test_analyze_clean_repo`: Mock ruff con 0 issues → score 1.0
  - `test_analyze_issues_found`: Mock ruff con issues → score < 1.0
  - `test_analyze_ruff_not_installed`: Mock FileNotFoundError → None
  - `test_analyze_ruff_timeout`: Mock timeout → None
  - `test_score_based_on_density`: Molti issues per LOC → score basso

### Criterio di verifica

```bash
pytest tests/unit/assessment/test_python_analyzer.py -v   # 5 tests passing
```

---

## 11) Task 4.7 — LLM Budget Controller

### Obiettivo

Controller per il budget token LLM con hard limits per-repo e per-day, timeout, e caching obbligatorio per commit SHA.

### Design

```python
# assessment/budget_controller.py

from __future__ import annotations

from datetime import UTC, datetime

from github_discovery.config import AssessmentSettings
from github_discovery.exceptions import BudgetExceededError
from github_discovery.models.assessment import TokenUsage


class BudgetController:
    """LLM token budget controller with hard limits.

    Enforces:
    - Per-repo token limit (max_tokens_per_repo)
    - Per-day token limit (max_tokens_per_day)
    - Timeout and early-stop for repos too large
    - Mandatory caching by commit SHA

    This is a hard constraint — no assessment proceeds
    without budget check (Blueprint §16.5).
    """

    def __init__(self, settings: AssessmentSettings) -> None:
        self._settings = settings
        self._daily_usage: int = 0
        self._repo_usage: dict[str, int] = {}  # full_name → tokens used
        self._day_start: datetime = datetime.now(UTC)

    def can_assess(self, full_name: str, estimated_tokens: int = 0) -> bool:
        """Check if assessment is within budget.

        Checks:
        1. Per-repo limit: tokens_used_for_repo + estimated <= max_tokens_per_repo
        2. Per-day limit: daily_total + estimated <= max_tokens_per_day

        Returns True if within budget, False otherwise.
        """
        ...

    def check_and_raise(self, full_name: str, estimated_tokens: int = 0) -> None:
        """Check budget and raise BudgetExceededError if exceeded.

        Use this for hard enforcement — caller should not proceed
        if this raises.
        """
        ...

    def record_usage(
        self,
        full_name: str,
        token_usage: TokenUsage,
    ) -> None:
        """Record token usage after an assessment.

        Updates per-repo and per-day counters.
        """
        ...

    @property
    def daily_remaining(self) -> int:
        """Remaining daily budget in tokens."""

    @property
    def daily_usage_summary(self) -> dict[str, int]:
        """Summary: {used, limit, remaining, repos_assessed}."""

    def _reset_if_new_day(self) -> None:
        """Reset daily counters if a new day has started."""
        ...
```

### Implementazione dettagliata

1. **Per-repo check**: `_repo_usage.get(full_name, 0) + estimated <= max_tokens_per_repo`
2. **Per-day check**: `_daily_usage + estimated <= max_tokens_per_day`
3. **Daily reset**: Se `datetime.now(UTC).date() > _day_start.date()` → reset counters
4. **Record usage**: Aggiorna `_repo_usage[full_name]` e `_daily_usage`
5. **Hard enforcement**: `check_and_raise` — usato dall'orchestrator prima di ogni chiamata LLM
6. **Metrics**: `daily_remaining`, `daily_usage_summary` per monitoring e progress notifications

### Test plan

- `test_budget_controller.py`:
  - `test_can_assess_within_budget`: Budget disponibile → True
  - `test_can_assess_per_repo_exceeded`: Per-repo limit → False
  - `test_can_assess_per_day_exceeded**: Per-day limit → False
  - `test_check_and_raise_throws**: Budget exceeded → BudgetExceededError
  - `test_record_usage_updates_counters**: Record → counters aggiornati
  - `test_daily_reset**: Nuovo giorno → counters resettati
  - `test_daily_remaining**: Calcolo corretto rimanente
  - `test_multiple_repos**: Tracking separato per repo diversi
  - `test_budget_context_in_error**: BudgetExceededError ha contesto budget

### Criterio di verifica

```bash
pytest tests/unit/assessment/test_budget_controller.py -v   # 9 tests passing
mypy src/github_discovery/assessment/budget_controller.py --strict
```

---

## 12) Task 4.8 — Deep Assessment Orchestrator

### Obiettivo

Orchestratore centrale che coordina l'intero flusso di deep assessment: hard gate check → cache check → budget check → Repomix pack → heuristic scoring → LLM assessment → result composition → cache store. Gestisce concorrenza, error recovery e progress tracking.

### Design

```python
# assessment/orchestrator.py

from __future__ import annotations

from github_discovery.config import AssessmentSettings, Settings
from github_discovery.exceptions import (
    AssessmentError,
    HardGateViolationError,
)
from github_discovery.models.assessment import DeepAssessmentResult, TokenUsage
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import ScoreDimension


class AssessmentOrchestrator:
    """Orchestrates the Gate 3 deep assessment pipeline.

    Coordinates:
    1. Hard gate enforcement (no assessment without Gate 1+2 pass)
    2. Cache check (dedup by commit SHA)
    3. Budget check (per-repo and per-day limits)
    4. Repomix packing
    5. Heuristic scoring (non-LLM baseline)
    6. LLM assessment per dimension
    7. Result composition
    8. Cache store

    Concurrency: max N repos in parallel via asyncio.Semaphore.
    Error recovery: individual repo failures don't block others.
    """

    def __init__(
        self,
        settings: Settings,
        repomix: RepomixAdapter,
        llm_provider: LLMProvider,
        budget: BudgetController,
        parser: AssessmentResultParser,
        heuristics: HeuristicScorer,
    ) -> None: ...

    async def assess(
        self,
        candidate: RepoCandidate,
        *,
        dimensions: list[ScoreDimension] | None = None,
        gate1_passed: bool = True,
        gate2_passed: bool = True,
    ) -> DeepAssessmentResult:
        """Deep assess a single candidate repository.

        Precondition: candidate must have passed Gate 1 + Gate 2.

        Args:
            candidate: Repository to assess
            dimensions: Specific dimensions to assess (None = all 8)
            gate1_passed: Whether candidate passed Gate 1
            gate2_passed: Whether candidate passed Gate 2

        Returns:
            DeepAssessmentResult with dimension scores and metadata

        Raises:
            HardGateViolationError: If gate1_passed or gate2_passed is False
            BudgetExceededError: If token budget is exceeded
            AssessmentError: If assessment fails irrecoverably
        """
        ...

    async def assess_batch(
        self,
        candidates: list[tuple[RepoCandidate, bool, bool]],
        *,
        dimensions: list[ScoreDimension] | None = None,
        max_concurrent: int = 3,
    ) -> list[DeepAssessmentResult]:
        """Deep assess a batch of candidates with concurrency control.

        Only candidates that passed Gate 1+2 are assessed.
        Individual failures are logged but don't block others.
        """
        ...

    async def _assess_dimension(
        self,
        dimension: ScoreDimension,
        packed_content: str,
        repo_full_name: str,
        repo_metadata: str,
        domain: DomainType,
    ) -> DimensionScore:
        """Assess a single dimension via LLM with fallback to heuristic.

        1. Try LLM assessment via structured output
        2. On failure: fall back to heuristic score with lower confidence
        """
        ...
```

### Implementazione dettagliata

1. **Hard gate enforcement**:
   ```python
   if not gate1_passed or not gate2_passed:
       raise HardGateViolationError(
           f"Cannot assess {candidate.full_name}: requires Gate 1+2 pass",
           repo_url=candidate.url,
           gate_passed=2 if (gate1_passed and gate2_passed) else (1 if gate1_passed else 0),
           gate_required=2,
       )
   ```

2. **Cache check**: Lookup in Feature Store per `full_name + commit_sha`. Se hit e non expired → return cached result.

3. **Budget check**: `budget.check_and_raise(candidate.full_name, estimated_tokens=repomix_token_count)`

4. **Assessment strategies**:
   - **Full assessment (default)**: LLM su tutte 8 le dimensioni
   - **Quick assessment**: LLM solo su subset di dimensioni (per `quick_assess` MCP tool)
   - **Heuristic-only**: Se budget esaurito, ritorna solo heuristic scores con confidence bassa

5. **LLM assessment per dimension**:
   - Batch mode: invia packed code una volta, chiedi scoring su tutte le dimensioni in una chiamata
   - Per-dimension mode: una chiamata per dimensione (più costoso ma più preciso)
   - Default: batch mode per ridurre token usage

6. **Concurrency**: `asyncio.Semaphore(max_concurrent)` per max N repo in parallelo

7. **Error recovery**:
   - Single dimension failure → DimensionScore con value=0.0, confidence=0.0, method="failed"
   - All dimensions failure → `DeepAssessmentResult` parziale con overall_confidence=0.0
   - Repomix failure → `AssessmentError` con contesto

8. **Progress tracking**: Log structurato + optional callback per progress notifications MCP

9. **Cache store**: Salva in Feature Store dopo completamento

### Test plan

- `test_orchestrator.py`:
  - `test_assess_returns_deep_result`: Mock tutti i componenti → DeepAssessmentResult completo
  - `test_assess_hard_gate_enforcement`: gate1_passed=False → HardGateViolationError
  - `test_assess_hard_gate_gate2**: gate2_passed=False → HardGateViolationError
  - `test_assess_cache_hit`: Mock cache hit → ritorna cached result
  - `test_assess_budget_exceeded**: Mock budget exceeded → BudgetExceededError
  - `test_assess_llm_failure_fallback**: Mock LLM failure → heuristic fallback
  - `test_assess_partial_dimension_failure**: Mock 1 dimension failure → partial result
  - `test_assess_batch_concurrent**: Mock 5 candidati → tutti assessati
  - `test_assess_batch_skips_failed_gates**: Batch con mix → solo pass vengono assessati
  - `test_assess_records_usage**: Token usage registrato in budget controller
  - `test_assess_caches_result**: Result salvato in feature store

### Criterio di verifica

```bash
pytest tests/unit/assessment/test_orchestrator.py -v   # 11 tests passing
mypy src/github_discovery/assessment/orchestrator.py --strict
```

---

## 13) Sequenza di implementazione

L'implementazione segue un ordine che minimizza le dipendenze e permette testing incrementale:

```
Week 1 — Foundation
├── 4.7 Budget Controller        (nessuna dipendenza, puro Python + config)
├── 4.1 Repomix Adapter          (dipendenza: python-repomix)
└── 4.2 LLM Provider             (dipendenza: openai + instructor)

Week 2 — Core Logic
├── 4.3 Assessment Prompts        (dipendenza: 4.2 per verificare con LLM reale)
├── 4.4 Result Parser             (dipendenza: models/assessment.py)
├── 4.5 Heuristic Scorer          (nessuna dipendenza esterna)
└── 4.6 Python Analyzer           (dipendenza: ruff)

Week 3 — Integration
├── 4.8 Orchestrator              (dipendenza: 4.1-4.7 tutti)
└── Integration Tests             (dipendenza: 4.8)
```

### Parallelizzazione possibile

- Tasks 4.5 (Heuristics) e 4.6 (Lang Analyzers) sono indipendenti e possono procedere in parallelo
- Tasks 4.1 (Repomix) e 4.2 (LLM Provider) sono indipendenti e possono procedere in parallelo
- Tasks 4.7 (Budget Controller) è indipendente e può procedere in parallelo con tutto

### Gate di avanzamento

1. **Gate A** (dopo Week 1): Repomix + LLM Provider funzionanti → può fare assessment manuale di test
2. **Gate B** (dopo Week 2): Prompts + Parser + Heuristics → pipeline parziale operativa
3. **Gate C** (dopo Week 3): Orchestrator → pipeline completa end-to-end

---

## 14) Test plan

### Unit tests (per modulo)

| Modulo | File test | # Test stimati |
|--------|-----------|---------------|
| Repomix Adapter | `test_repomix_adapter.py` | 7 |
| LLM Provider | `test_llm_provider.py` | 7 |
| Result Parser | `test_result_parser.py` | 9 |
| Heuristic Scorer | `test_heuristics.py` | 8 |
| Python Analyzer | `test_python_analyzer.py` | 5 |
| Budget Controller | `test_budget_controller.py` | 9 |
| Orchestrator | `test_orchestrator.py` | 11 |
| Prompts | `test_prompts/` | 9 |
| **Totale unit** | | **~65** |

### Integration tests

| Test | File | Marker |
|------|------|--------|
| End-to-end: repo reale → Repomix → LLM → result | `test_assessment_e2e.py` | `@pytest.mark.integration` |
| Budget enforcement su sequenza di assessment | `test_assessment_e2e.py` | `@pytest.mark.integration` |
| Cache hit/miss su stesso commit SHA | `test_assessment_e2e.py` | `@pytest.mark.integration` |

### Coverage target

- **>80%** su assessment logic (orchestrator, parser, budget, heuristics)
- **>60%** su LLM provider (mock per unit, reale per integration)
- **>90%** su budget controller (critico per hard limits)

---

## 15) Criteri di accettazione

Il Phase 4 è completato quando **tutti** i seguenti criteri sono soddisfatti:

### Funzionali

- [ ] `DeepAssessmentResult` prodotto con 8 dimensioni + explanation + evidence + confidence
- [ ] Budget controller rispetta i limiti per-repo e per-day
- [ ] Caching per commit SHA funzionante (dedup, TTL, invalidazione)
- [ ] Hard gate enforcement: nessun assessment senza Gate 1+2 pass
- [ ] NanoGPT structured output con validazione Pydantic operativa
- [ ] Repomix packing con token counting e compressione
- [ ] Heuristic scoring come baseline e fallback

### Qualità

- [ ] Tutti i moduli passano `mypy --strict` con 0 errori
- [ ] Tutti i moduli passano `ruff check` con 0 errori
- [ ] Test coverage >80% su assessment logic
- [ ] ~65 unit tests + 3 integration tests passing
- [ ] `make ci` verde

### Verifiche manuali

- [ ] Pipeline end-to-end su 5-10 repo reali con NanoGPT subscription
- [ ] Budget tracking visibile in log structurati
- [ ] Cache hit su secondo assessment dello stesso repo + SHA
- [ ] Fallback a heuristic quando LLM fallisce

### Comandi di verifica

```bash
# Unit tests
pytest tests/unit/assessment/ -v

# Integration tests (richiede GHDISC_ASSESSMENT_LLM_API_KEY)
pytest tests/integration/assessment/ -v -m integration

# Type check
mypy src/github_discovery/assessment/ --strict

# Lint
ruff check src/github_discovery/assessment/

# Full CI
make ci
```

---

## 16) Rischi e mitigazioni

| Rischio | Impatto | Probabilità | Mitigazione |
|---------|---------|-------------|-------------|
| Costo LLM fuori controllo su deep scan | Alto | Medio | Budget controller hard limits, early-stop, caching SHA, top percentile solo |
| Qualità risposta LLM variabile | Medio | Alto | Prompt template testati, structured output con validation, retry con instructor, confidence score |
| python-repomix immaturo o con bug | Medio | Basso | Fallback a subprocess con repomix CLI (Node.js), oppure packing custom via GitHub API |
| NanoGPT subscription limits o rate limiting | Medio | Basso | Fallback model, retry con backoff, rate limit awareness nel provider |
| Repo troppo grandi per Repomix packing | Alto | Medio | Interface-mode compression, token truncation, early-stop, max file size limit |
| Structured output non disponibile per tutti i modelli | Medio | Basso | JSON object mode come fallback, response parser con regex fallback |
| Prompt non producono output parseable | Medio | Medio | Instructor retry su validation failure, result parser con partial parsing, heuristic fallback |
| Token counting non accurato | Basso | Medio | Stima conservativa, budget con margine 20%, tracking reale post-assessment |

---

## 17) Verifica Context7 completata

Le seguenti librerie sono state verificate tramite Context7 per la documentazione ufficiale aggiornata:

| Libreria | Context7 ID | Versione | Cosa verificato |
|----------|-------------|----------|-----------------|
| **python-repomix** | `/andersonby/python-repomix` | Latest | `RepoProcessor`, `RepomixConfig`, interface mode, token counting, remote packing |
| **instructor** | `/websites/python_useinstructor` | Latest | `instructor.from_provider()`, structured output con Pydantic, async, retry, multi-provider |
| **litellm** | `/berriai/litellm` | v1.81+ | `completion()`, structured output, multi-provider, cost tracking — **scartato** a favore di instructor (NanoGPT già gestisce multi-provider) |

### Documentazione esterna verificata

| Fonte | URL | Cosa verificato |
|-------|-----|-----------------|
| **NanoGPT API** | https://docs.nano-gpt.com/introduction | OpenAI-compatible endpoint, structured output (`json_schema`), subscription endpoint, prompt caching, usage tracking, model naming (`provider/model`) |
| **NanoGPT Chat Completion** | https://docs.nano-gpt.com/api-reference/endpoint/chat-completion | `response_format` con `json_schema`, `usage` tracking, streaming, temperature/seed per determinismo |

### Modelli esistenti verificati (da codice implementato)

| File | Modelli | Stato |
|------|---------|-------|
| `models/assessment.py` | `DimensionScore`, `TokenUsage`, `DeepAssessmentResult` | ✅ Implementato, 152 linee |
| `models/enums.py` | `ScoreDimension` (8 dimensioni), `GateLevel` | ✅ Implementato |
| `models/features.py` | `RepoFeatures`, `FeatureStoreKey` | ✅ Implementato, SHA dedup |
| `config.py` | `AssessmentSettings` | ✅ Implementato, da estendere con NanoGPT settings |
| `exceptions.py` | `AssessmentError`, `BudgetExceededError`, `HardGateViolationError` | ✅ Implementato |

---

*Stato documento: Draft v1 — Phase 4 Implementation Plan*
*Data: 2026-04-23*
*Basato su: github-discovery_foundation_blueprint.md v1 + §21 Agentic Integration Architecture*
*LLM Provider: NanoGPT (https://nano-gpt.com) con subscription*
