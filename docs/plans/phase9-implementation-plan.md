# GitHub Discovery — Phase 9 Implementation Plan

## Meta

- **Stato**: Draft v1
- **Data**: 2026-04-24
- **Riferimento roadmap**: `docs/roadmaps/github-discovery_foundation_roadmap.md` — Phase 9
- **Riferimento blueprint**: `docs/foundation/github-discovery_foundation_blueprint.md` — §21 (Agentic Integration Architecture), §16.5 (Hard Gate Enforcement), §17 (Operational Rules)
- **Riferimento wiki**: `docs/llm-wiki/wiki/` — articoli su tiered pipeline, MCP-native design, screening gates, scoring dimensions, agent workflows, session workflow
- **Durata stimata**: 2-3 settimane
- **Milestone**: M8 — Feasibility Gate (CRITICO) — Precision@K > baseline star-based, valutazione umana positiva, agentic integration testata con 2+ client
- **Dipendenza**: Phase 0+1+2+3+4+5+6+7+8 completate (1199 tests passing, `make ci` verde)
- **Context7 verification**: MCP Python SDK v1.x (ClientSession, stdio_client, tool call testing), FastAPI AsyncClient + ASGITransport (async endpoint testing), pytest (markers, fixtures, conftest, parametrize, tmp_path)

---

## Indice

1. [Obiettivo](#1-obiettivo)
2. [Task Overview](#2-task-overview)
3. [Architettura generale](#3-architettura-generale)
4. [Nuove dipendenze](#4-nuove-dipendenze)
5. [Codice esistente — stato attuale](#5-codice-esistente--stato-attuale)
6. [Task 9.1 — Sprint 0: Mini-pipeline su 500-1000 repo](#6-task-91--sprint-0-mini-pipeline-su-500-1000-repo)
7. [Task 9.2 — Baseline Metadata Score](#7-task-92--baseline-metadata-score)
8. [Task 9.3 — Deep-scan Top 10-15%](#8-task-93--deep-scan-top-10-15)
9. [Task 9.4 — Star-based Baseline Comparison](#9-task-94--star-based-baseline-comparison)
10. [Task 9.5 — Blind Human Evaluation](#10-task-95--blind-human-evaluation)
11. [Task 9.6 — Precision@K Measurement](#11-task-96--precisionk-measurement)
12. [Task 9.7 — Weight Tuning & Calibration](#12-task-97--weight-tuning--calibration)
13. [Task 9.8 — End-to-End Integration Tests](#13-task-98--end-to-end-integration-tests)
14. [Task 9.9 — Agentic Integration Tests](#14-task-99--agentic-integration-tests)
15. [Task 9.10 — Kilocode CLI Integration Test](#15-task-910--kilocode-cli-integration-test)
16. [Task 9.11 — OpenCode Integration Test](#16-task-911--opencode-integration-test)
17. [Sequenza di implementazione — Waves](#17-sequenza-di-implementazione--waves)
18. [Test plan](#18-test-plan)
19. [Criteri di accettazione](#19-criteri-di-accettazione)
20. [Rischi e mitigazioni](#20-rischi-e-mitigazioni)
21. [Verifica Context7](#21-verifica-context7)

---

## 1) Obiettivo

Validare l'intero sistema GitHub Discovery con l'esperimento di fattibilità (Sprint 0 del blueprint): dimostrare che il sistema trova repo tecnicamente migliori del baseline star-based su un campione reale. Questa è la fase **go/no-go** del progetto.

Phase 9 ha due obiettivi paralleli:

1. **Feasibility Validation**: Eseguire la pipeline completa Gate 0→1→2→3 su pool reale di candidati, misurare Precision@K contro baseline star-based, calibrare pesi, validare con valutazione umana
2. **Integration Testing**: Test end-to-end completi della pipeline CLI → API → Workers → Discovery → Screening → Assessment → Scoring → Export, test agentic MCP con client reali, test integrazione con Kilocode CLI e OpenCode

Al completamento della Phase 9:

- **Pipeline completa validata** su volume reale (500-1000 candidati)
- **Anti-star bias dimostrato**: GitHub Discovery trova hidden gems che star-ranking non vede
- **Precision@10 > baseline** misurata e documentata
- **Pesì calibrati** per dominio basato su dati reali
- **Integration test coverage** >80% su screening/scoring
- **Agentic integration** verificata con MCP client (Context7-verified `mcp.Client` + `ClientSession`)
- **Almeno 2 agent client** testati (Kilocode CLI + OpenCode o MCP client diretto)

### Principi architetturali

1. **Sprint 0 è la validazione**: La mini-pipeline non è un test, è la dimostrazione del valore del sistema
2. **Mock solo per esterni**: GitHub API e LLM provider sono mockati; la pipeline interna è reale
3. **Human-in-the-loop**: La valutazione umana (Task 9.5) richiede input manuale — preparare dataset in anticipo
4. **Determinismo**: Risultati Sprint 0 devono essere riproducibili (seed, cached data, frozen snapshots)
5. **No LLM cost overflow**: Budget controller è hard constraint — nessun deep-scan senza controllo token

---

## 2) Task Overview

| Task ID | Task | Output | Tipo | Dipende da |
|---------|------|--------|------|------------|
| 9.1 | Sprint 0 — Mini-pipeline su 500-1000 repo | Dataset scored completo | Feasibility | — |
| 9.2 | Baseline metadata score | Report baseline vs star-ranking | Feasibility | 9.1 |
| 9.3 | Deep-scan top 10-15% | Risultati deep assessment | Feasibility | 9.2 |
| 9.4 | Star-based baseline comparison | Report comparativo | Feasibility | 9.3 |
| 9.5 | Blind human evaluation | Dataset valutazione umana | Feasibility | 9.4 |
| 9.6 | Precision@K measurement | Report precision@k | Feasibility | 9.4 |
| 9.7 | Weight tuning & calibration | Pesi calibrati per dominio | Feasibility | 9.6 |
| 9.8 | End-to-end integration tests | Test suite integration | Testing | — |
| 9.9 | Agentic integration tests | Test suite agentic | Testing | 9.8 |
| 9.10 | Kilocode CLI integration test | Test report Kilocode | Testing | 9.9 |
| 9.11 | OpenCode integration test | Test report OpenCode | Testing | 9.9 |

### Classificazione task

- **Feasibility (9.1-9.7)**: Validazione del valore del sistema — dimostrazione che anti-star bias funziona
- **Testing (9.8-9.11)**: Infrastructure di test — integration test, agentic test, client-specific test

---

## 3) Architettura generale

### Struttura moduli

```
tests/
├── integration/
│   ├── __init__.py
│   ├── conftest.py                        # Shared integration fixtures
│   ├── test_pipeline_e2e.py               # End-to-end pipeline tests (Task 9.8)
│   ├── test_api_e2e.py                    # API integration tests (Task 9.8)
│   ├── test_mcp_server.py                 # MCP server tests (già esistente, esteso)
│   └── test_star_baseline.py              # Star baseline comparison (Task 9.4)
├── agentic/
│   ├── __init__.py
│   ├── conftest.py                        # Agentic test fixtures
│   ├── test_mcp_client.py                 # Riscritto: MCP client integration (Task 9.9)
│   ├── test_progressive_deepening.py      # Progressive deepening workflow (Task 9.9)
│   ├── test_session_workflow.py           # Session cross-invocation (Task 9.9)
│   ├── test_kilocode_integration.py       # Kilocode CLI tests (Task 9.10)
│   └── test_opencode_integration.py       # OpenCode tests (Task 9.11)
├── feasibility/                           # NUOVO — Sprint 0 validation
│   ├── __init__.py
│   ├── conftest.py                        # Feasibility test fixtures
│   ├── test_sprint0_pipeline.py           # Mini-pipeline validation (Task 9.1)
│   ├── test_baseline_scoring.py           # Baseline metadata score (Task 9.2)
│   ├── test_deep_scan.py                  # Deep-scan top percentile (Task 9.3)
│   ├── test_precision_at_k.py             # Precision@K measurement (Task 9.6)
│   └── test_weight_calibration.py         # Weight tuning (Task 9.7)
└── fixtures/                              # NUOVO — Test data fixtures
    ├── __init__.py
    ├── sample_repos.json                  # Frozen repo data for Sprint 0
    ├── baseline_rankings.json             # Star-based rankings for comparison
    ├── human_eval_template.json           # Template for blind human evaluation
    └── calibrated_weights.json            # Output: calibrated domain weights
```

### Moduli source (nessun nuovo modulo — solo test infrastructure)

Phase 9 è primariamente testing e validazione. I moduli source esistenti sono:

| Componente | Modulo | Stato |
|-----------|--------|-------|
| DiscoveryOrchestrator | `discovery/orchestrator.py` | ✅ Phase 2 |
| PoolManager | `discovery/pool.py` | ✅ Phase 2 |
| ScreeningOrchestrator | `screening/orchestrator.py` | ✅ Phase 3 |
| AssessmentOrchestrator | `assessment/orchestrator.py` | ✅ Phase 4 |
| ScoringEngine | `scoring/engine.py` | ✅ Phase 5 |
| Ranker | `scoring/ranker.py` | ✅ Phase 5 |
| FeatureStore | `scoring/feature_store.py` | ✅ Phase 5 |
| ValueScoreCalculator | `scoring/value_score.py` | ✅ Phase 5 |
| ProfileRegistry | `scoring/profiles.py` | ✅ Phase 5 |
| FastAPI app | `api/app.py` | ✅ Phase 6 |
| MCP server | `mcp/server.py` | ✅ Phase 7 |
| SessionManager | `mcp/session.py` | ✅ Phase 7 |
| CLI app | `cli/app.py` | ✅ Phase 8 |

### Moduli di supporto per feasibility

Un piccolo modulo helper per Sprint 0 scripting:

```
src/github_discovery/
├── feasibility/                    # NUOVO
│   ├── __init__.py
│   ├── sprint0.py                  # Sprint 0 pipeline runner (orchestrates full pipeline)
│   ├── baseline.py                 # Star-based baseline scorer (for comparison)
│   ├── metrics.py                  # Precision@K, NDCG, overlap analysis
│   └── calibration.py              # Weight calibration via grid search
```

---

## 4) Nuove dipendenze

**Nessuna nuova dipendenza richiesta** per Phase 9. Tutte le librerie necessarie sono già presenti:

| Libreria | Versione | Utilizzo |
|----------|----------|----------|
| `pytest` | 8.x | Test framework, markers, fixtures |
| `pytest-asyncio` | latest | Async test support |
| `pytest-httpx` | latest | HTTP mocking per GitHub API |
| `httpx` | 0.28+ | AsyncClient + ASGITransport per API testing |
| `mcp` | 1.x | MCP `Client` + `ClientSession` per agentic testing |
| `pydantic` | 2.x | Model validation nei test |
| `aiosqlite` | 0.20+ | SQLite test fixtures (session, pool, feature store) |

**Possibili dipendenze future** (non in Phase 9):
- `inline-snapshot` — per MCP tool output assertion (già usato negli esempi Context7, ma non obbligatorio)

---

## 5) Codice esistente — stato attuale

### Test infrastructure esistente

| Directory | Contenuto | Stato |
|-----------|-----------|-------|
| `tests/unit/` | 80+ test files, ~1120 unit tests | ✅ Completo |
| `tests/integration/` | 2 files: `test_imports.py` (12), `test_mcp_server.py` (12) | ✅ Parziale |
| `tests/agentic/` | 1 file: `test_mcp_client.py` (3 skipped stubs) | ⚠️ Stub |
| `tests/conftest.py` | `settings`, `settings_with_token` fixtures | ✅ Base |

### Modelli dati disponibili per i test

| Modello | File | Utilizzo Phase 9 |
|---------|------|------------------|
| `RepoCandidate` | `models/candidate.py` | Sprint 0 dataset |
| `MetadataScreenResult` | `models/screening.py` | Baseline scoring |
| `StaticScreenResult` | `models/screening.py` | Gate 2 validation |
| `DeepAssessmentResult` | `models/assessment.py` | Deep-scan validation |
| `ScoreResult` | `models/scoring.py` | Pipeline output |
| `RankedRepo` | `models/scoring.py` | Ranking comparison |
| `ValueScore` | `models/scoring.py` | Anti-star bias measurement |
| `SessionState` | `models/session.py` | Session workflow tests |
| `DomainType` | `models/enums.py` | Domain filtering |
| `GateLevel` | `models/enums.py` | Gate filtering |

### Servizi core da testare (già esistenti)

| Servizio | Modulo | Metodi chiave per Phase 9 |
|----------|--------|---------------------------|
| `DiscoveryOrchestrator` | `discovery/orchestrator.py` | `discover()` |
| `ScreeningOrchestrator` | `screening/orchestrator.py` | `screen_pool()`, `screen_single()` |
| `AssessmentOrchestrator` | `assessment/orchestrator.py` | `assess_pool()`, `quick_assess()` |
| `ScoringEngine` | `scoring/engine.py` | `score()`, `score_cached()` |
| `Ranker` | `scoring/ranker.py` | `rank()` |
| `FeatureStore` | `scoring/feature_store.py` | `get()`, `get_batch()`, `put()` |
| `ExplainabilityGenerator` | `scoring/explainability.py` | `generate_report()` |
| `SessionManager` | `mcp/session.py` | `create()`, `get()`, `update()` |
| `PoolManager` | `discovery/pool.py` | `create_pool()`, `add_candidates()` |
| FastAPI `app` | `api/app.py` | `GET /health`, `POST /api/v1/discover`, etc. |
| MCP `server` | `mcp/server.py` | `create_server()`, `serve()` |
| CLI `app` | `cli/app.py` | `ghdisc discover`, `ghdisc rank`, etc. |

---

## 6) Task 9.1 — Sprint 0: Mini-pipeline su 500-1000 repo

### Obiettivo

Eseguire la pipeline completa Gate 0→1→2→3 su un pool reale di 500-1000 candidati, usando dati GitHub API reali (o frozen snapshot) con mock solo per LLM calls e tool esterni costosi.

### Design

#### feasibility/sprint0.py

```python
"""Sprint 0 pipeline runner — validates the full scoring pipeline on a real candidate pool."""

from __future__ import annotations

from dataclasses import dataclass, field

from github_discovery.config import Settings
from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.enums import DomainType
from github_discovery.models.screening import ScreeningResult
from github_discovery.models.assessment import DeepAssessmentResult
from github_discovery.models.scoring import ScoreResult, RankedRepo


@dataclass
class Sprint0Config:
    """Configuration for Sprint 0 execution."""

    max_candidates: int = 500
    queries: list[str] = field(default_factory=lambda: [
        "static analysis python",
        "machine learning framework",
        "web framework rust",
        "cli tool go",
        "data pipeline python",
    ])
    domains: list[DomainType] = field(default_factory=lambda: [
        DomainType.LIBRARY,
        DomainType.CLI,
        DomainType.ML_LIB,
        DomainType.DATA_TOOL,
        DomainType.WEB_FRAMEWORK,
    ])
    gate1_threshold: float = 0.4
    gate2_threshold: float = 0.3
    deep_assess_percentile: float = 0.15  # top 15%
    llm_budget_tokens: int = 500_000
    seed: int = 42


@dataclass
class Sprint0Result:
    """Results from Sprint 0 pipeline execution."""

    total_discovered: int
    gate1_passed: int
    gate2_passed: int
    gate3_assessed: int
    ranked_repos: list[RankedRepo]
    hidden_gems: list[RankedRepo]
    domain_distribution: dict[str, int]
    pipeline_duration_seconds: float
    llm_tokens_used: int


async def run_sprint0(
    settings: Settings,
    config: Sprint0Config | None = None,
    *,
    candidates: list[RepoCandidate] | None = None,
) -> Sprint0Result:
    """Execute the full Sprint 0 pipeline.

    If `candidates` is provided, skip discovery and use provided data.
    Otherwise, run discovery with configured queries.
    """
    config = config or Sprint0Config()
    # ... pipeline implementation:
    # 1. Discovery (or use provided candidates)
    # 2. Gate 1 screening
    # 3. Gate 2 screening
    # 4. Deep assessment (top 10-15%)
    # 5. Scoring & ranking
    # 6. Hidden gem identification
    ...
```

#### Test: tests/feasibility/test_sprint0_pipeline.py

```python
"""Sprint 0 pipeline validation tests.

Tests that the full pipeline Gate 0→1→2→3 executes correctly
on a representative dataset of candidates.
"""

from __future__ import annotations

import pytest

from github_discovery.feasibility.sprint0 import Sprint0Config, Sprint0Result, run_sprint0
from github_discovery.models.candidate import RepoCandidate


pytestmark = pytest.mark.integration


class TestSprint0Pipeline:
    """Validate Sprint 0 pipeline execution."""

    async def test_sprint0_completes_with_mock_candidates(
        self,
        settings: Settings,
        sample_candidates: list[RepoCandidate],  # fixture with ~100 repos
    ) -> None:
        """Sprint 0 completes without errors on mock candidate pool."""
        config = Sprint0Config(max_candidates=100, deep_assess_percentile=0.15)
        result = await run_sprint0(settings, config, candidates=sample_candidates)

        assert result.total_discovered == 100
        assert result.gate1_passed > 0
        assert result.gate2_passed <= result.gate1_passed
        assert result.gate3_assessed <= result.gate2_passed
        assert result.ranked_repos is not None
        assert len(result.hidden_gems) > 0

    async def test_sprint0_respects_hard_gates(self, settings: Settings) -> None:
        """No repo reaches Gate 3 without passing Gate 1+2."""
        # ... verify hard gate enforcement in pipeline
        ...

    async def test_sprint0_respects_llm_budget(self, settings: Settings) -> None:
        """Total LLM tokens used stays within configured budget."""
        config = Sprint0Config(llm_budget_tokens=100_000)
        result = await run_sprint0(settings, config, candidates=...)

        assert result.llm_tokens_used <= config.llm_budget_tokens

    async def test_sprint0_deterministic_with_seed(self, settings: Settings) -> None:
        """Two runs with same seed produce identical ranking."""
        config = Sprint0Config(seed=42)
        result1 = await run_sprint0(settings, config, candidates=...)
        result2 = await run_sprint0(settings, config, candidates=...)

        rankings1 = [r.full_name for r in result1.ranked_repos]
        rankings2 = [r.full_name for r in result2.ranked_repos]
        assert rankings1 == rankings2
```

### Verifica

- Sprint 0 pipeline completa senza errori su pool di 100+ candidati (mock)
- Hard gate enforcement verificato
- Budget LLM rispettato
- Ranking deterministico con seed

---

## 7) Task 9.2 — Baseline Metadata Score

### Obiettivo

Calcolare baseline score senza LLM (solo Gate 1+2 metadata) e confrontare con ranking per stelle. Questo stabilisce il baseline contro cui misurare il valore aggiunto del deep assessment.

### Design

#### feasibility/baseline.py

```python
"""Star-based baseline scorer for comparison with GitHub Discovery ranking."""

from __future__ import annotations

from dataclasses import dataclass

from github_discovery.models.candidate import RepoCandidate
from github_discovery.models.scoring import RankedRepo


@dataclass
class BaselineComparison:
    """Result of comparing metadata scoring vs star-based ranking."""

    metadata_top_10: list[str]  # full_names of top 10 by metadata score
    star_top_10: list[str]  # full_names of top 10 by star count
    overlap_count: int  # repos in both top-10 lists
    hidden_gems_metadata: list[str]  # repos ranked high by metadata but low by stars
    overhyped_by_stars: list[str]  # repos ranked high by stars but low by metadata
    correlation_coefficient: float  # Spearman correlation between rankings


def compute_star_ranking(
    candidates: list[RepoCandidate],
    *,
    domain: str | None = None,
    max_results: int = 100,
) -> list[RankedRepo]:
    """Compute a simple star-based ranking.

    Stars are the ONLY ranking criterion — no quality signals.
    This is the baseline we must beat.
    """
    ...


def compute_metadata_ranking(
    candidates: list[RepoCandidate],
    screening_results: dict[str, ScreeningResult],
    *,
    domain: str | None = None,
    max_results: int = 100,
) -> list[RankedRepo]:
    """Compute ranking using only Gate 1+2 metadata scores (no LLM)."""
    ...


def compare_rankings(
    metadata_ranked: list[RankedRepo],
    star_ranked: list[RankedRepo],
    *,
    top_k: int = 10,
) -> BaselineComparison:
    """Compare metadata-based vs star-based rankings."""
    ...
```

### Verifica

- Hidden gems identificati dal metadata score (repo con alta qualità ma basse stelle)
- Overlap analysis mostra divergenza tra metadata ranking e star ranking
- Correlazione Spearman calcolata

---

## 8) Task 9.3 — Deep-scan Top 10-15%

### Obiettivo

Eseguire deep assessment (Gate 3) solo su top percentile dal Gate 2, con rispetto rigoroso del budget LLM. Mock del LLM provider per test deterministici.

### Design

Deep-scan usa `AssessmentOrchestrator.assess_pool()` già esistente. Il test verifica:

1. Solo repo che hanno passato Gate 1+2 vengono valutati
2. Budget token è rispettato
3. Risultati sono caching-per-SHA funzionanti
4. Output `DeepAssessmentResult` è valido per tutte le 8 dimensioni

```python
class TestDeepScan:
    """Validate Gate 3 deep assessment on top percentile."""

    async def test_deep_scan_only_gate12_passed(self, ...) -> None:
        """Only repos passing Gate 1+2 are deep-assessed."""
        ...

    async def test_deep_scan_respects_budget(self, ...) -> None:
        """Token budget is enforced — no overflow."""
        ...

    async def test_deep_scan_caches_by_sha(self, ...) -> None:
        """Same commit SHA returns cached result without re-assessment."""
        ...

    async def test_deep_scan_all_8_dimensions(self, ...) -> None:
        """Every assessed repo has scores for all 8 dimensions."""
        ...
```

### Verifica

- Nessun repo senza Gate 1+2 pass viene mandato a Gate 3
- Budget LLM rispettato
- Cache per SHA funzionante (no double-assessment)
- 8 dimensioni popolate per ogni repo assessato

---

## 9) Task 9.4 — Star-based Baseline Comparison

### Obiettivo

Confronto formale tra ranking GitHub Discovery e ranking star-based. Produce un report comparativo che dimostra dove e perché GD trova repo migliori.

### Design

Estende `feasibility/baseline.py` con analisi dettagliata:

```python
@dataclass
class DetailedComparison:
    """Detailed comparison report between GD ranking and star ranking."""

    # Overlap analysis
    overlap_at_5: int  # repos in both top-5
    overlap_at_10: int  # repos in both top-10
    overlap_at_20: int  # repos in both top-20

    # Hidden gems (GD finds, stars miss)
    hidden_gems: list[HiddenGem]
    #   - repo with quality_score > 0.7 and stars < 100
    #   - ranked top-20 by GD but not in star top-100

    # Overhyped (stars suggest, GD rejects)
    overhyped_repos: list[OverhypedRepo]
    #   - repo with stars > 1000 but quality_score < 0.4
    #   - ranked top-20 by stars but not in GD top-100

    # Per-domain breakdown
    domain_comparisons: dict[str, BaselineComparison]

    # Statistical significance
    wilcoxon_p_value: float  # Wilcoxon signed-rank test p-value


@dataclass
class HiddenGem:
    """A repository identified as a hidden gem by GD."""
    full_name: str
    quality_score: float
    value_score: float
    gd_rank: int
    star_rank: int
    stars: int
    quality_evidence: list[str]


@dataclass
class OverhypedRepo:
    """A repository over-ranked by stars vs quality."""
    full_name: str
    quality_score: float
    star_rank: int
    gd_rank: int
    stars: int
    quality_concerns: list[str]
```

### Verifica

- GitHub Discovery trova repo che star-ranking non vede (hidden gems)
- Report include almeno 5 hidden gems identificati
- Per-domain breakdown mostra differenze tra domini
- Analisi statistica (Spearman, Wilcoxon) completa

---

## 10) Task 9.5 — Blind Human Evaluation

### Obiettivo

Valutazione umana su campione di 20-30 repo senza indicazione della fonte di ranking (GD vs stars). Il valutatore assegna un rating di qualità tecnica (1-5) a ciascun repo.

### Design

Questo task è principalmente procedurale (richiede intervento umano). Il codice produce il dataset per la valutazione:

```python
@dataclass
class HumanEvalSample:
    """A repo sample for blind human evaluation."""
    full_name: str
    description: str
    url: str
    language: str
    # Quality signals visible to evaluator (NOT the ranking source)
    readme_length: int
    has_tests: bool
    has_ci: bool
    has_license: bool
    last_commit_days_ago: int
    # Ground truth (hidden from evaluator)
    source_ranking: str  # "gd" or "stars"
    gd_rank: int
    star_rank: int
    quality_score: float


def generate_human_eval_dataset(
    gd_ranked: list[RankedRepo],
    star_ranked: list[RankedRepo],
    candidates: list[RepoCandidate],
    *,
    sample_size: int = 25,
    seed: int = 42,
) -> list[HumanEvalSample]:
    """Generate balanced dataset for blind human evaluation.

    Selects repos from both GD and star rankings, shuffled so the
    evaluator cannot tell which source ranked them.
    """
    ...
```

### Verifica

- Dataset bilanciato: ~50% da GD top-20, ~50% da star top-20
- Nessun indicatore della fonte nel dataset presentato al valutatore
- Template di valutazione pronto per uso manuale

**Nota**: La valutazione umana vera e propria avviene fuori dal codice. Il risultato atteso è una correlazione positiva tra ranking GD e qualità percepita dal valutatore.

---

## 11) Task 9.6 — Precision@K Measurement

### Obiettivo

Misurare Precision@5, Precision@10, Precision@20 su "hidden gems" (basse stelle, alta qualità tecnica). Confrontare con baseline star-based.

### Design

#### feasibility/metrics.py

```python
"""Evaluation metrics for GitHub Discovery pipeline validation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PrecisionAtKResult:
    """Precision@K measurement result."""

    k: int
    gd_precision: float  # % of GD top-K that are "truly good"
    star_precision: float  # % of star top-K that are "truly good"
    improvement: float  # gd_precision - star_precision
    gd_relevant: list[str]  # repos in GD top-K that are relevant
    star_relevant: list[str]  # repos in star top-K that are relevant


@dataclass
class FullMetricsReport:
    """Complete evaluation metrics."""

    precision_at_5: PrecisionAtKResult
    precision_at_10: PrecisionAtKResult
    precision_at_20: PrecisionAtKResult
    ndcg_gd: float  # NDCG for GD ranking
    ndcg_stars: float  # NDCG for star ranking
    hidden_gem_recall: float  # % of known hidden gems found by GD
    mrr_gd: float  # Mean Reciprocal Rank for GD
    mrr_stars: float  # Mean Reciprocal Rank for stars


def compute_precision_at_k(
    ranked_repos: list[RankedRepo],
    ground_truth_good: set[str],  # repos known to be high-quality
    *,
    k: int = 10,
) -> float:
    """Compute Precision@K: fraction of top-K repos that are truly good."""
    ...


def compute_ndcg(
    ranked_repos: list[RankedRepo],
    relevance_scores: dict[str, float],  # repo → relevance (0.0-1.0)
    *,
    k: int = 20,
) -> float:
    """Compute Normalized Discounted Cumulative Gain."""
    ...


def compute_full_metrics(
    gd_ranked: list[RankedRepo],
    star_ranked: list[RankedRepo],
    ground_truth: dict[str, float],  # repo → quality score (ground truth)
) -> FullMetricsReport:
    """Compute complete evaluation metrics comparing GD vs star ranking."""
    ...
```

### Verifica

- Precision@10 GD > Precision@10 star-based (target: almeno +10%)
- NDCG GD > NDCG star-based
- Hidden gem recall misurato
- Report completo con tutti i KPI

---

## 12) Task 9.7 — Weight Tuning & Calibration

### Obiettivo

Aggiustare pesi dimensioni per dominio basato su risultati Sprint 0. Usare grid search o ottimizzazione semplice per trovare pesi che massimizzano Precision@K.

### Design

#### feasibility/calibration.py

```python
"""Weight calibration for domain-specific scoring profiles."""

from __future__ import annotations

from dataclasses import dataclass

from github_discovery.models.scoring import DomainProfile
from github_discovery.models.enums import DomainType


@dataclass
class CalibrationResult:
    """Result of weight calibration for a domain."""

    domain: DomainType
    original_weights: dict[str, float]  # dimension → weight
    calibrated_weights: dict[str, float]
    precision_before: float  # Precision@10 before calibration
    precision_after: float  # Precision@10 after calibration
    improvement: float  # precision_after - precision_before
    best_params: dict[str, float]  # full parameter set that achieved best result


def grid_search_weights(
    domain: DomainType,
    base_profile: DomainProfile,
    candidates: list[RepoCandidate],
    ground_truth: dict[str, float],
    *,
    precision_k: int = 10,
    step: float = 0.05,
) -> CalibrationResult:
    """Simple grid search over dimension weights to maximize Precision@K.

    For each domain, tries variations of the weight profile and selects
    the one with highest Precision@K against ground truth.
    """
    ...


def calibrate_all_domains(
    base_profiles: dict[DomainType, DomainProfile],
    candidates: list[RepoCandidate],
    ground_truth: dict[str, float],
) -> dict[DomainType, CalibrationResult]:
    """Calibrate weights for all domains with sufficient data."""
    ...
```

### Verifica

- Almeno 3 domini con pesi calibrati
- Precision@K migliorata rispetto a pesi default
- I pesi calibrati sono salvati in `tests/fixtures/calibrated_weights.json`
- Profili aggiornabili in `scoring/profiles.py`

---

## 13) Task 9.8 — End-to-End Integration Tests

### Obiettivo

Test integrazione completi che coprono l'intero stack: CLI → API → Workers → Discovery → Screening → Assessment → Scoring → Export. Mock esterni (GitHub API, LLM), pipeline interna reale.

### Design

#### tests/integration/conftest.py

```python
"""Shared fixtures for integration tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from github_discovery.config import Settings
from github_discovery.models.candidate import RepoCandidate


@pytest.fixture
def integration_settings(tmp_path: Path) -> Settings:
    """Settings configured for integration testing."""
    return Settings(
        github=GitHubSettings(token="ghp_test_integration"),
        session_store_path=str(tmp_path / "sessions.db"),
        pool_db_path=str(tmp_path / "pools.db"),
        feature_store_path=str(tmp_path / "features.db"),
    )


@pytest.fixture
async def api_client(integration_settings: Settings) -> AsyncClient:
    """Async HTTP client for FastAPI integration tests.

    Uses httpx.AsyncClient with ASGITransport per Context7-verified pattern:
    AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    """
    from github_discovery.api.app import create_app

    app = create_app(integration_settings)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def sample_repos_frozen() -> list[RepoCandidate]:
    """Load frozen sample repos from JSON fixture."""
    import json
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_repos.json"
    data = json.loads(fixture_path.read_text())
    return [RepoCandidate.model_validate(r) for r in data]


@pytest.fixture
def mock_github_api(httpx_mock: HTTPXMock) -> None:
    """Mock GitHub REST/GraphQL API responses for integration tests."""
    # Mock search results, repo details, etc.
    ...
```

#### tests/integration/test_pipeline_e2e.py

```python
"""End-to-end pipeline integration tests.

Validates the complete pipeline: discovery → screening → assessment → scoring → ranking.
Uses frozen test data and mocked external APIs.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


class TestPipelineE2E:
    """Full pipeline end-to-end tests."""

    async def test_discovery_to_screening(
        self,
        integration_settings: Settings,
        mock_github_api: None,
    ) -> None:
        """Discovery produces candidates that can be screened."""
        # 1. Run discovery
        # 2. Verify candidates in pool
        # 3. Run screening (Gate 1+2)
        # 4. Verify screening results
        ...

    async def test_screening_to_assessment(
        self,
        integration_settings: Settings,
        sample_repos_frozen: list[RepoCandidate],
        mock_github_api: None,
    ) -> None:
        """Screened candidates can be deep-assessed."""
        # 1. Load frozen candidates into pool
        # 2. Run screening
        # 3. Get shortlist (Gate 1+2 passed)
        # 4. Run deep assessment (Gate 3) with mock LLM
        # 5. Verify assessment results
        ...

    async def test_assessment_to_ranking(
        self,
        integration_settings: Settings,
        mock_llm_provider: AsyncMock,
    ) -> None:
        """Assessed repos can be scored and ranked."""
        # 1. Pre-populate feature store with assessment results
        # 2. Run scoring engine
        # 3. Run ranker
        # 4. Verify anti-star bias (hidden gems rank high)
        ...

    async def test_full_pipeline_gate_enforcement(
        self,
        integration_settings: Settings,
    ) -> None:
        """Hard gate: no repo reaches Gate 3 without Gate 1+2 pass."""
        ...

    async def test_pipeline_with_session(
        self,
        integration_settings: Settings,
    ) -> None:
        """Pipeline works with session-based progressive deepening."""
        # 1. Create session
        # 2. Discover in session
        # 3. Screen in session
        # 4. Assess in session
        # 5. Rank in session
        # 6. Export session
        ...
```

#### tests/integration/test_api_e2e.py

```python
"""API endpoint integration tests.

Tests FastAPI endpoints end-to-end using httpx.AsyncClient with ASGITransport.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


class TestAPIE2E:
    """Full API integration tests."""

    async def test_discover_endpoint(self, api_client: AsyncClient) -> None:
        """POST /api/v1/discover starts discovery job."""
        response = await api_client.post("/api/v1/discover", json={
            "query": "static analysis python",
            "max_candidates": 50,
        })
        assert response.status_code == 202
        assert "job_id" in response.json()

    async def test_screen_endpoint_hard_gate(
        self, api_client: AsyncClient
    ) -> None:
        """POST /api/v1/assess rejects candidates not passing Gate 1+2."""
        response = await api_client.post("/api/v1/assess", json={
            "pool_id": "test-pool",
            "repo_urls": ["https://github.com/test/low-quality"],
        })
        assert response.status_code in (403, 422)  # hard gate rejection

    async def test_rank_endpoint_returns_ranked(
        self, api_client: AsyncClient
    ) -> None:
        """GET /api/v1/rank returns ranked repos."""
        response = await api_client.get("/api/v1/rank", params={"domain": "library"})
        assert response.status_code == 200

    async def test_export_endpoint_json(
        self, api_client: AsyncClient
    ) -> None:
        """POST /api/v1/export produces valid JSON export."""
        ...

    async def test_health_endpoint(self, api_client: AsyncClient) -> None:
        """GET /health returns 200."""
        response = await api_client.get("/health")
        assert response.status_code == 200
```

### Verifica

- Pipeline E2E completa senza errori (con mock esterni)
- API endpoints rispondono correttamente
- Hard gate enforcement verificato nell'API
- Coverage integration >80% su screening/scoring

---

## 14) Task 9.9 — Agentic Integration Tests

### Obiettivo

Test MCP tools con client MCP reale usando il pattern Context7-verified (`mcp.Client` + `ClientSession`). Verifica progressive deepening, session cross-invocazione, progress notifications, context-efficient output, composizione con GitHub MCP.

### Design

#### Contesto Context7: MCP Python SDK Testing Pattern

```python
# Context7-verified pattern from /modelcontextprotocol/python-sdk docs/testing.md
from mcp import Client
from mcp.types import CallToolResult, TextContent

@pytest.fixture
async def client(settings: Settings):
    """MCP client connected to GitHub Discovery server."""
    from github_discovery.mcp.server import create_server
    server = create_server(settings)
    async with Client(server, raise_exceptions=True) as c:
        yield c
```

#### tests/agentic/conftest.py

```python
"""Shared fixtures for agentic MCP integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp import Client

from github_discovery.config import Settings
from github_discovery.mcp.server import create_server


@pytest.fixture
def agentic_settings(tmp_path: Path) -> Settings:
    """Settings for agentic tests with temp databases."""
    ...


@pytest.fixture
async def mcp_client(agentic_settings: Settings) -> Client:
    """MCP client connected to GitHub Discovery server.

    Uses the Context7-verified pattern:
    async with Client(fastmcp_server, raise_exceptions=True) as c
    """
    server = create_server(agentic_settings)
    async with Client(server, raise_exceptions=True) as c:
        yield c
```

#### tests/agentic/test_mcp_client.py (RISCRITTO)

```python
"""MCP client integration tests.

Tests that an MCP client can connect to the GitHub Discovery MCP server,
list tools, call tools, and receive structured results.
"""

from __future__ import annotations

import pytest
from mcp import Client
from mcp.types import CallToolResult, TextContent

pytestmark = [pytest.mark.integration, pytest.mark.slow]


class TestMCPClientIntegration:
    """MCP client integration with real MCP protocol."""

    async def test_client_can_list_tools(self, mcp_client: Client) -> None:
        """MCP client can list all 16 registered tools."""
        tools = await mcp_client.list_tools()
        tool_names = {t.name for t in tools}
        assert len(tools) == 16
        assert "discover_repos" in tool_names
        assert "rank_repos" in tool_names
        assert "create_session" in tool_names

    async def test_client_can_call_create_session(self, mcp_client: Client) -> None:
        """MCP client can invoke create_session tool."""
        result = await mcp_client.call_tool(
            "create_session",
            arguments={"name": "test-session"},
        )
        assert result is not None
        # Verify structured content
        ...

    async def test_client_can_call_discover_repos(self, mcp_client: Client) -> None:
        """MCP client can invoke discover_repos tool."""
        result = await mcp_client.call_tool(
            "discover_repos",
            arguments={"query": "test query", "max_candidates": 10},
        )
        assert result is not None

    async def test_client_receives_structured_content(self, mcp_client: Client) -> None:
        """Tool results include structured content (not just text)."""
        result = await mcp_client.call_tool("list_sessions", arguments={})
        assert result is not None

    async def test_client_can_list_resources(self, mcp_client: Client) -> None:
        """MCP client can list resource templates."""
        resources = await mcp_client.list_resource_templates()
        uris = {r.uriTemplate for r in resources}
        assert "repo://{owner}/{name}/score" in uris

    async def test_client_can_list_prompts(self, mcp_client: Client) -> None:
        """MCP client can list prompt skills."""
        prompts = await mcp_client.list_prompts()
        prompt_names = {p.name for p in prompts}
        assert "discover_underrated" in prompt_names
        assert "quick_quality_check" in prompt_names
```

#### tests/agentic/test_progressive_deepening.py

```python
"""Test progressive deepening workflow via MCP client.

Validates Pattern 2 from Blueprint §21.7:
discover → screen → deep assess → rank → explain
"""

from __future__ import annotations

import pytest
from mcp import Client

pytestmark = [pytest.mark.integration, pytest.mark.slow]


class TestProgressiveDeepening:
    """Test agent-driven progressive deepening workflow."""

    async def test_gate_by_gate_deepening(self, mcp_client: Client) -> None:
        """Agent can screen at Gate 1, decide, then screen at Gate 2."""
        # 1. Create session
        session = await mcp_client.call_tool("create_session", arguments={"name": "pd-test"})

        # 2. Discover candidates
        discovery = await mcp_client.call_tool("discover_repos", arguments={
            "query": "static analysis python",
            "max_candidates": 20,
            "session_id": session["session_id"],
        })

        # 3. Screen at Gate 1 only
        screening_g1 = await mcp_client.call_tool("screen_candidates", arguments={
            "pool_id": discovery["pool_id"],
            "gate_level": "1",
            "session_id": session["session_id"],
        })

        # 4. Agent decides to deepen: screen at Gate 2
        screening_g2 = await mcp_client.call_tool("screen_candidates", arguments={
            "pool_id": discovery["pool_id"],
            "gate_level": "2",
            "session_id": session["session_id"],
        })

        # 5. Verify progressive results
        assert screening_g1["gate1_passed"] > 0
        assert screening_g2["gate2_passed"] <= screening_g1["gate1_passed"]

    async def test_full_deepening_to_ranking(self, mcp_client: Client) -> None:
        """Full progressive deepening: discover → screen → assess → rank."""
        ...

    async def test_agent_can_set_custom_thresholds(self, mcp_client: Client) -> None:
        """Agent-driven policy: custom gate thresholds via tool parameters."""
        result = await mcp_client.call_tool("screen_candidates", arguments={
            "pool_id": "test-pool",
            "gate_level": "1",
            "min_gate1_score": 0.6,  # Custom threshold
        })
        ...

    async def test_context_efficient_output(self, mcp_client: Client) -> None:
        """Tool output respects context limits (< 2000 tokens default)."""
        result = await mcp_client.call_tool("discover_repos", arguments={
            "query": "python",
            "max_candidates": 100,
        })
        # Output should be summary-first with references
        assert "detail_available_via" in result or "total_candidates" in result
```

#### tests/agentic/test_session_workflow.py

```python
"""Test session cross-invocation workflow.

Validates that sessions persist state across multiple MCP tool calls.
"""

from __future__ import annotations

import pytest
from mcp import Client

pytestmark = [pytest.mark.integration, pytest.mark.slow]


class TestSessionWorkflow:
    """Test session-aware MCP workflow."""

    async def test_session_persists_across_calls(self, mcp_client: Client) -> None:
        """Session state persists across separate tool invocations."""
        # 1. Create session
        session = await mcp_client.call_tool("create_session", arguments={"name": "persist-test"})
        session_id = session["session_id"]

        # 2. Discover in session
        await mcp_client.call_tool("discover_repos", arguments={
            "query": "test",
            "max_candidates": 10,
            "session_id": session_id,
        })

        # 3. Get session — should show discovered repos
        session_state = await mcp_client.call_tool("get_session", arguments={
            "session_id": session_id,
        })
        assert session_state["discovered_repo_count"] > 0

    async def test_session_export(self, mcp_client: Client) -> None:
        """Session can be exported after workflow completion."""
        ...

    async def test_multiple_sessions_isolated(self, mcp_client: Client) -> None:
        """Multiple sessions maintain independent state."""
        ...
```

### Verifica

- Ogni workflow agentico del Blueprint §21.7 testato end-to-end
- Progressive deepening: Gate 1 → decide → Gate 2 → decide → Gate 3
- Session cross-invocazione funzionante
- Context-efficient output verificato (< 2000 token)
- MCP `Client` + `ClientSession` usati (Context7-verified pattern)

---

## 15) Task 9.10 — Kilocode CLI Integration Test

### Obiettivo

Test effettivo con Kilocode CLI: configurazione `kilo.json`, agent chiama tool discovery, workflow multi-step con session_id, permission system.

### Design

Kilocode CLI integra MCP server locali via configurazione JSON. Il test verifica:

1. Generazione config MCP via CLI: `ghdisc mcp init-config --target kilo`
2. Configurazione valida per Kilocode CLI
3. MCP server avviabile in stdio mode
4. Tool invocabili dalla config generata

```python
class TestKilocodeIntegration:
    """Test MCP integration with Kilocode CLI configuration."""

    def test_mcp_config_generation(self, tmp_path: Path) -> None:
        """ghdisc mcp init-config --target kilo produces valid config."""
        from github_discovery.mcp.github_client import get_composition_config

        config = get_composition_config("kilo")
        assert "github" in config
        assert "github-discovery" in config
        assert config["github-discovery"]["type"] == "local"
        assert "command" in config["github-discovery"]

    async def test_stdio_server_starts(self, settings: Settings) -> None:
        """MCP server starts successfully in stdio mode."""
        from github_discovery.mcp.server import create_server

        server = create_server(settings)
        assert server.name == "github-discovery"

        # Verify it can be connected to via Client
        async with Client(server, raise_exceptions=True) as client:
            tools = await client.list_tools()
            assert len(tools) == 16

    async def test_kilocode_workflow_simulation(self, mcp_client: Client) -> None:
        """Simulate a Kilocode CLI agent workflow.

        Pattern: Agent creates session → discovers → screens → ranks → explains
        This is the primary Kilocode CLI usage pattern from Blueprint §21.
        """
        # 1. Agent starts with discover_underrated prompt skill
        prompts = await mcp_client.list_prompts()
        discover_prompt = next(p for p in prompts if p.name == "discover_underrated")

        # 2. Agent executes the workflow steps
        session = await mcp_client.call_tool("create_session", arguments={"name": "kilo-test"})
        discovery = await mcp_client.call_tool("discover_repos", arguments={
            "query": "python cli tool",
            "max_candidates": 20,
        })
        screening = await mcp_client.call_tool("screen_candidates", arguments={
            "pool_id": discovery["pool_id"],
            "gate_level": "both",
        })

        # 3. Agent requests ranking
        ranking = await mcp_client.call_tool("rank_repos", arguments={
            "domain": "cli",
            "max_results": 5,
        })

        # 4. Agent explains top result
        if ranking.get("ranked_repos"):
            top_repo = ranking["ranked_repos"][0]["full_name"]
            explanation = await mcp_client.call_tool("explain_repo", arguments={
                "repo_url": f"https://github.com/{top_repo}",
                "detail_level": "summary",
            })
            assert explanation is not None
```

### Verifica

- Config MCP generata valida per Kilocode CLI
- Server avviabile in stdio mode
- Almeno 1 workflow completo eseguito via Client (simulando Kilocode CLI)

---

## 16) Task 9.11 — OpenCode Integration Test

### Obiettivo

Test effettivo con OpenCode: configurazione `opencode.jsonc`, agent chiama tool discovery, workflow con plan/build/review modes.

### Design

Simile a Task 9.10 ma con focus su OpenCode-specific patterns:

```python
class TestOpenCodeIntegration:
    """Test MCP integration with OpenCode configuration."""

    def test_mcp_config_generation(self) -> None:
        """ghdisc mcp init-config --target opencode produces valid config."""
        from github_discovery.mcp.github_client import get_composition_config

        config = get_composition_config("opencode")
        assert "github-discovery" in config

    async def test_opencode_plan_mode_workflow(self, mcp_client: Client) -> None:
        """Simulate OpenCode plan mode: explore without deep assessment.

        In plan mode, agent uses lightweight tools (discover, quick_screen)
        without invoking expensive Gate 3 assessment.
        """
        # 1. Quick discovery
        discovery = await mcp_client.call_tool("discover_repos", arguments={
            "query": "rust web framework",
            "max_candidates": 30,
        })

        # 2. Quick screen (Gate 1 only)
        screening = await mcp_client.call_tool("quick_screen", arguments={
            "repo_url": "https://github.com/tokio-rs/axum",
            "gate_levels": ["1"],
        })

        # 3. No deep assessment in plan mode
        assert screening is not None

    async def test_opencode_review_mode_workflow(self, mcp_client: Client) -> None:
        """Simulate OpenCode review mode: compare repos for decision."""
        comparison = await mcp_client.call_tool("compare_repos", arguments={
            "repo_urls": [
                "https://github.com/user/repo1",
                "https://github.com/user/repo2",
            ],
            "dimensions": ["code_quality", "testing", "security"],
        })
        assert comparison is not None
```

### Verifica

- Config MCP generata valida per OpenCode
- Workflow plan mode (lightweight) e review mode (comparison) testati
- Almeno 1 workflow completo eseguito via Client (simulando OpenCode)

---

## 17) Sequenza di implementazione — Waves

### Wave A — Feasibility Infrastructure (2-3 giorni)

| Task | Focus | Output | Test previsti |
|------|-------|--------|---------------|
| 9.1 (parziale) | `feasibility/` module: sprint0.py, baseline.py, metrics.py, calibration.py | 4 moduli source | 15 |
| 9.1 (test) | Sprint 0 pipeline validation tests | `tests/feasibility/` | 10 |
| Fixtures | `tests/fixtures/` con sample_repos.json, baseline_rankings.json | Frozen test data | — |

### Wave B — Integration Tests (3-4 giorni)

| Task | Focus | Output | Test previsti |
|------|-------|--------|---------------|
| 9.8 | End-to-end pipeline tests + API integration | `tests/integration/` | 30 |
| 9.2 | Baseline metadata score tests | `tests/feasibility/test_baseline_scoring.py` | 8 |
| 9.3 | Deep-scan validation tests | `tests/feasibility/test_deep_scan.py` | 8 |

### Wave C — Feasibility Validation (2-3 giorni)

| Task | Focus | Output | Test previsti |
|------|-------|--------|---------------|
| 9.4 | Star-based comparison tests | `tests/integration/test_star_baseline.py` | 10 |
| 9.6 | Precision@K measurement tests | `tests/feasibility/test_precision_at_k.py` | 10 |
| 9.7 | Weight calibration tests | `tests/feasibility/test_weight_calibration.py` | 8 |
| 9.5 | Human eval dataset generation | `tests/fixtures/human_eval_template.json` | 3 |

### Wave D — Agentic Integration (3-4 giorni)

| Task | Focus | Output | Test previsti |
|------|-------|--------|---------------|
| 9.9 | MCP client integration tests (rewrite stubs) | `tests/agentic/test_mcp_client.py` | 10 |
| 9.9 | Progressive deepening + session workflow | `tests/agentic/test_*.py` | 15 |
| 9.10 | Kilocode CLI integration | `tests/agentic/test_kilocode_integration.py` | 5 |
| 9.11 | OpenCode integration | `tests/agentic/test_opencode_integration.py` | 5 |

### Totale stimato

| Wave | Test previsti | Cumulativo |
|------|---------------|-----------|
| Wave A | ~25 | 1224 |
| Wave B | ~46 | 1270 |
| Wave C | ~31 | 1301 |
| Wave D | ~35 | 1336 |
| **Totale Phase 9** | **~137** | **~1336** |

**Nota**: Il totale cumulativo parte da 1199 (Phase 8) + 137 nuovi = ~1336 tests.

---

## 18) Test plan

### Marker convenzioni

```python
# pytest markers (già registrati in pyproject.toml)
pytest.mark.integration  # Tests that use multiple modules together
pytest.mark.slow  # Tests that take >1s (deep assessment, large pools)
pytest.mark.feasibility  # Sprint 0 validation tests
```

### Registrazione markers (pyproject.toml update)

```toml
[tool.pytest.ini_options]
markers = [
    "integration: marks tests as integration tests (deselect with '-m \"not integration\"')",
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "feasibility: marks Sprint 0 feasibility validation tests",
]
```

### Fixture gerarchia

```
tests/conftest.py
├── settings
├── settings_with_token
│
├── tests/integration/conftest.py
│   ├── integration_settings (tmp_path based)
│   ├── api_client (AsyncClient + ASGITransport)
│   ├── sample_repos_frozen (from fixtures/sample_repos.json)
│   └── mock_github_api (httpx_mock)
│
├── tests/agentic/conftest.py
│   ├── agentic_settings (tmp_path based)
│   └── mcp_client (mcp.Client + create_server)
│
└── tests/feasibility/conftest.py
    ├── sprint0_config (Sprint0Config defaults)
    ├── ground_truth_repos (dict[str, float] for quality)
    └── sample_pool (PoolManager with pre-loaded candidates)
```

### Coverage target

| Modulo | Coverage target | Strategia |
|--------|----------------|-----------|
| `screening/` | >80% | Integration tests che esercitano Gate 1+2 end-to-end |
| `scoring/` | >80% | Feasibility tests con scoring reale su pool |
| `assessment/` | >70% | Deep-scan tests con mock LLM |
| `discovery/` | >60% | Pipeline E2E con mock GitHub API |
| `api/` | >70% | API E2E tests via AsyncClient |
| `mcp/` | >70% | Agentic tests via MCP Client |
| `cli/` | >60% | CLI E2E via CliRunner o invocazione diretta |

---

## 19) Criteri di accettazione

### Criteri obbligatori (go/no-go)

| # | Criterio | Misura | Verifica |
|---|----------|--------|----------|
| 1 | Pipeline completa senza errori | Sprint 0 su 100+ candidati mock | `pytest tests/feasibility/` verde |
| 2 | Hard gate enforcement | Nessun repo senza Gate 1+2 passa a Gate 3 | `test_pipeline_gate_enforcement` passa |
| 3 | Budget LLM rispettato | Token usati ≤ budget configurato | `test_deep_scan_respects_budget` passa |
| 4 | Precision@10 GD > baseline | Precision@10(gd) > Precision@10(stars) | `test_precision_at_k` verifica improvement |
| 5 | Hidden gems identificati | ≥5 repo con quality > 0.7 e stars < 100 | `test_hidden_gem_detection` passa |
| 6 | Integration test verdi | >80% coverage su screening/scoring | `make ci` verde con coverage report |
| 7 | MCP client integration | Client può list/call tools e ricevere risultati | `pytest tests/agentic/ -m integration` verde |
| 8 | Progressive deepening | Gate-by-gate invocation funziona | `test_gate_by_gate_deepening` passa |
| 9 | Session cross-invocazione | Stato persiste tra tool call | `test_session_persists_across_calls` passa |
| 10 | Almeno 1 agent client testato | Kilocode CLI o OpenCode workflow completo | Wave D test passa |

### Criteri desiderabili (non blocking)

| # | Criterio | Misura |
|---|----------|--------|
| 11 | Valutazione umana positiva | Correlazione GD ranking ↔ qualità percepita |
| 12 | Pesì calibrati per ≥3 domini | Miglioramento Precision@K vs default |
| 13 | Entrambi i client testati | Kilocode CLI + OpenCode |
| 14 | Ranking deterministico | Stesso seed → stesso ranking |
| 15 | NDCG GD > NDCG stars | Su almeno 1 dominio |

---

## 20) Rischi e mitigazioni

| Rischio | Impatto | Probabilità | Mitigazione |
|---------|---------|-------------|-------------|
| Precision@K non supera baseline star-based | Critico — progetto non dimostra valore | Media | Tuning pesi (Task 9.7); aggiungere dimensioni; cambiare soglie; worst case: rivalutare l'approccio |
| MCP Client non supporta testing inline | Alto — test agentic non eseguibili | Bassa | Context7 verificato: `mcp.Client(fastmcp_server)` pattern supportato in SDK v1.x |
| Budget LLM overflow in Sprint 0 | Alto — costi non controllati | Bassa | Budget controller hard limits (già implementato Phase 4); mock LLM per test |
| Client MCP (Kilocode/OpenCode) non supportano progress notifications | Basso — agent non riceve aggiornamenti | Media | Fallback a polling (tool `get_session`); documentation per client senza streaming |
| Frozen test data non rappresentativo | Medio — risultati Sprint 0 non significativi | Media | Usare dati reali (GitHub API live) per dataset iniziale; congelare solo per riproducibilità |
| Valutazione umana non disponibile | Medio — manca validazione esterna | Media | Preparare template e dataset (Task 9.5); la valutazione può avvenire post-Phase 9 |
| Test integration troppo lenti | Basso — CI timeout | Media | `pytest.mark.slow` per escludere; `pytest.mark.integration` per separare; mock esterni |

---

## 21) Verifica Context7

### MCP Python SDK v1.x (da `/modelcontextprotocol/python-sdk`)

Pattern verificati per Phase 9:

1. **`mcp.Client(fastmcp_server, raise_exceptions=True)`** — crea client connesso a un FastMCP server senza avviare un processo separato
2. **`await client.list_tools()`** — elenca tutti i tool registrati
3. **`await client.call_tool("tool_name", arguments={...})`** — invoca un tool MCP
4. **`await client.list_resource_templates()`** — elenca template di risorse
5. **`await client.list_prompts()`** — elenca prompt skill
6. **`await client.send_progress_notification(...)`** — invia notifiche di progresso
7. **Testing pattern**: fixture `async def client()` con `async with Client(app) as c: yield c`
8. **`pytest.mark.anyio`** per test async con MCP client

### FastAPI (da `/websites/fastapi_tiangolo`)

Pattern verificati per Phase 9:

1. **`httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`** — test client async per FastAPI
2. **`TestClient(app)`** — test client sincrono (per test non-async)
3. **`@pytest.mark.anyio` + `async def test_...`** — pattern per test async
4. **Non usare `TestClient` in test async** — usare `AsyncClient` direttamente

### pytest (da `/websites/pytest_en_stable`)

Pattern verificati per Phase 9:

1. **`conftest.py` gerarchia** — fixture condivise per directory
2. **`@pytest.mark.parametrize`** — test parametrizzati per multi-domain
3. **`@pytest.mark.integration` / `@pytest.mark.slow`** — marker custom
4. **`tmp_path` fixture** — directory temporanee per database SQLite
5. **`request.node.get_closest_marker("fixt_data")`** — dati marker passati a fixture
6. **`pytest.param(..., marks=pytest.mark.slow)`** — marker su singoli parametri

---

## Appendice A — Frozen Test Data Schema

### tests/fixtures/sample_repos.json

```json
{
  "version": 1,
  "generated_at": "2026-04-24T00:00:00Z",
  "queries": ["static analysis python", "machine learning framework", "web framework rust"],
  "total_repos": 100,
  "repos": [
    {
      "full_name": "example/high-quality-lib",
      "url": "https://github.com/example/high-quality-lib",
      "description": "A well-maintained library",
      "language": "Python",
      "topics": ["testing", "quality"],
      "stars": 42,
      "created_at": "2023-01-15T00:00:00Z",
      "updated_at": "2026-04-20T00:00:00Z",
      "pushed_at": "2026-04-18T00:00:00Z",
      "license": "MIT",
      "default_branch": "main",
      "size_kb": 1200,
      "open_issues_count": 3,
      "forks_count": 5,
      "archived": false,
      "disabled": false,
      "source_channel": "search",
      "discovery_score": 0.85
    }
  ]
}
```

---

*Stato documento: Draft v1 — Phase 9 Implementation Plan*
*Data: 2026-04-24*
*Basato su: roadmap Phase 9 + blueprint §21 + AGENTS.md + Context7 verification (MCP SDK, FastAPI, pytest)*
