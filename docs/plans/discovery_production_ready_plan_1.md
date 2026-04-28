# GitHub Discovery — Production Readiness Plan v1

## Meta

- **Stato**: Draft v1
- **Data**: 2026-04-27
- **Tipo**: Plan di debugging + hardening post-Fase 2 verso `v0.3.0-beta` "production-ready"
- **Versione di partenza**: `v0.2.0-beta` (Fase 2 Waves 0–3, 5 completate; 1587 test verdi; Wave 4 esterno pending)
- **Versione target**: `v0.3.0-beta` — pipeline E2E robusta su pool reali, falsi negativi/positivi tracciabili, costo/qualità Gate 3 difendibile, deployabile out-of-box (no system tools mancanti, no truncation cieca)
- **Riferimenti obbligatori CLAUDE.md**:
  - Wiki: `docs/llm-wiki/wiki/architecture/{anti-star-bias.md, tiered-pipeline.md, phase2-remediation.md}`, `docs/llm-wiki/wiki/domain/{scoring-dimensions.md, screening-gates.md}`, `docs/llm-wiki/wiki/patterns/{operational-rules.md, phase5-scoring-implementation.md}`
  - Context7: `pydantic` v2, `httpx` AsyncClient, `tenacity` (retry/jitter), `instructor` (Mode.MD_JSON, async, max_retries), `openai` AsyncOpenAI lifecycle, `python-repomix` (compression modes, RepoProcessor), `hypothesis`
- **Input audit**:
  - `docs/plans/fase2_plan.md` (Audit Remediation, completato)
  - `test_report_2.md` (E2E session pydantic, 2026-04-27 — bottleneck reali emersi)
  - Verifica diretta sul codice (`src/github_discovery/**`)
- **Durata stimata**: 3 settimane (1 dev FT) o 1.5 settimane (2 dev paralleli, Wave A+B)
- **Milestone**: M10 — Production-Ready Beta
- **No regressioni**: 1587 test devono restare verdi. Solo aggiunte.

---

## Indice

1. [Obiettivo](#1-obiettivo)
2. [Sintesi criticità](#2-sintesi-criticità)
3. [Verifica sul codice reale](#3-verifica-sul-codice-reale)
4. [Task overview](#4-task-overview)
5. [Wave A — Discovery Star-Neutrality + Domain Detection (P0)](#5-wave-a)
6. [Wave B — Gate 2 Tooling & Confidence-Aware Composite (P0)](#6-wave-b)
7. [Wave C — Gate 3 Content Strategy + Confidence Propagation (P0)](#7-wave-c)
8. [Wave D — Heuristic CI/test Detection + Truncation-Resilience (P1)](#8-wave-d)
9. [Wave E — Operational Hardening (P1)](#9-wave-e)
10. [Wave F — Observability & Reproducibility (P2)](#10-wave-f)
11. [Sequenza](#11-sequenza)
12. [Test plan](#12-test-plan)
13. [Acceptance](#13-acceptance)
14. [Rischi](#14-rischi)
15. [Context7 + wiki cross-refs](#15-context7--wiki-cross-refs)
16. [Out of scope](#16-out-of-scope)

---

## 1) Obiettivo

Fase 2 ha chiuso i bug logici dello scoring (single source `hidden_gem`, blake2b, coverage damping, weighted confidence, derivation map v2, retry tipizzati, orphan cleanup, TTL cache, property-based test). Restano **5 classi di criticità che bloccano la production-readiness**:

1. **Discovery non perfettamente star-neutral**: filtro `-stars:>100000` esclude mega-popular ma non documentato/configurabile; default `-stars:>0` o language obbligatorio mancante per channel registry; un repo a 0 star può essere filtrato implicitamente da inactivity. Il test_report_2 cita un filtro `stars:>10` non presente nel codice → discrepanza che indica documentazione vs realtà fuori sync.
2. **Gate 2 non resiliente all'assenza dei system tools**: `gitleaks`/`scc` mancanti sul sistema → tutti i sub-score fallback con `value=0.5, confidence=0.0` (secrets) o `value=0.5, confidence=0.3` (complexity) ma `compute_total()` è una **media flat** che ignora `confidence` → composite Gate 2 collassa, pass-rate 1/12 in test reale. Bug architetturale: la coverage-aware logic di Layer D non è replicata in Gate 2.
3. **Gate 3 content truncation cieca**: hard-cap `_MAX_LLM_CONTENT_CHARS = 4_000` indipendente dalla repo size. Per `pydantic` (243K token sorgente) → 1.5% del codice arriva al LLM. Per `huggingface/diffusers` (1.75M token) → repomix timeout a 120s prima ancora di arrivare al LLM. **Confidence reale dell'assessment è ~0.05–0.15, non i 0.7 dichiarati nei prompt**.
4. **Heuristic detection rotta su large OSS**: `_detect_ci()` cerca substring `.github/workflows/` su contenuto packed. Dopo interface-mode compression + truncation, gli header dei file sotto `.github/` sono spesso droppati → `has_ci=False` per pydantic e fastapi-code-generator (entrambi hanno CI Actions). Falso negativo sistematico.
5. **Confidence floor 0.30 hardcoded**: `result_parser._fill_missing_with_heuristics` e `create_heuristic_fallback` mettono `confidence=0.3` literal. `_compute_overall_confidence = min(...)` → con 1 dimensione fallback heuristic, l'intera assessment è confidence 0.30 indipendentemente dalle altre 7. Confidence gauge non riflette la realtà.

Output v0.3.0: pipeline che, lanciata su un pool reale di 20 repo, produce un ranking con `coverage`, `confidence` e `degraded` flag esplicativi, anche quando system tools mancano e quando le repo sono troppo grandi per essere packate intere.

---

## 2) Sintesi criticità

### 2.1 P0 — Discovery & star-neutrality

| # | Problema | File:line | Evidenza |
|---|----------|-----------|----------|
| A1 | `-stars:>100000` mega-popular exclusion non documentato come opt-out, non esposto come config | `discovery/search_channel.py:27,85` | `_MEGA_POPULAR_STAR_THRESHOLD = 100_000` hardcoded; nessuna env var |
| A2 | Test report cita `stars:>10` ma codice non lo contiene → sospetto filtro implicito non tracciato (default GitHub Search senza star qualifier può escludere repo 0-star) | `test_report_2.md:18,27` vs `discovery/search_channel.py:51-87` | Discrepanza — verificare se `_INACTIVITY_DAYS=180` implicitamente esclude repo "new" star=0 |
| A3 | `code_search_channel.py` rate limit 10 req/min, `_MAX_PAGES_CODE_SEARCH=1`, `_PER_PAGE_CODE_SEARCH=30` — tetto effettivo 30 candidate per signal. Per pool grandi, la copertura Code Search è marginale | `discovery/code_search_channel.py:28-29` | Limita la diversità del pool: dipendenza eccessiva da Search API (popolarità-orientata) |
| A4 | `domain` rimane `OTHER` per la maggior parte dei repo discovered (mancano signals di classificazione domain) → DEFAULT_PROFILE applicato sempre, profili specifici WEB_FRAMEWORK/ML_LIB/etc. sono dead code in pratica | `discovery/*.py`, `models/candidate.py:domain` | Test report `Domain` column vuota su entrambi i ranked repo |

### 2.2 P0 — Gate 2 confidence-blind composite

| # | Problema | File:line | Evidenza |
|---|----------|-----------|----------|
| B1 | `StaticScreenResult.compute_total()` è media weighted ma **ignora `confidence`** dei sub-score | `models/screening.py:306-317` | gitleaks fallback `value=0.5, conf=0.0` viene contato come 0.5 nella media, deflazionando il composite |
| B2 | Doppio fallback gitleaks: `secrets_check.py:48-54` ritorna `value=0.5, conf=0.0` (no clone), `secrets_check.py:71-81` ritorna `value=0.5, conf=0.0` (binary not found). Ma in `gate2_static.py:238-242` (try/except wrapper) il fallback è `value=0.3, conf=0.0` (incoerente) | `secrets_check.py`, `gate2_static.py:230-256` | Tre code path con valori divergenti |
| B3 | Stessa incoerenza per scc: `complexity.py:60-74` `value=0.5, conf=0.3` (binary missing), wrapper `gate2_static.py:252-256` `value=0.3, conf=0.0` | come sopra | |
| B4 | Nessun pre-flight check sui binary required al boot del worker / MCP server. Errore visibile solo a runtime, dopo il primo Gate 2 | `mcp/server.py`, `cli/screen.py` | UX scadente per deploy |
| B5 | `MetadataScreenResult.compute_total()` ha lo stesso difetto (media flat, no confidence weighting) — bug speculativo, va verificato che Gate 1 non subisca lo stesso collasso quando un sub-score fallisce | `models/screening.py:188-202` | Architectural consistency |

### 2.3 P0 — Gate 3 content + confidence

| # | Problema | File:line | Evidenza |
|---|----------|-----------|----------|
| C1 | `_MAX_LLM_CONTENT_CHARS = 4_000` hardcoded → repo grandi assessate su <2% del codice | `assessment/orchestrator.py:48,231-237` | pydantic 243K tokens → 4K chars; LLM "vede" 1 file di interfaccia |
| C2 | `RepomixAdapter` timeout fisso `120s` per QUALSIASI repo. Pre-check sulla size mancante → repo grandi (1M+ token sorgente) timeout sicuro | `assessment/repomix_adapter.py:39,84-88` | huggingface/diffusers fail già documentato |
| C3 | `result_parser._compute_overall_confidence` è `min(confidence)` su tutte le dimensioni → 1 fallback heuristic (conf=0.3) deflaziona tutte le altre | `assessment/result_parser.py:348-355` | Pydantic risultato: confidence 0.30 su tutte 8 dim |
| C4 | `_fill_missing_with_heuristics` e `create_heuristic_fallback` hardcoded `confidence=0.3`. Phase 2 T2.4 voleva ≤0.25 + degraded flag — implementato in `scoring/types.py::HeuristicFallback` ma non collegato al parser | `assessment/result_parser.py:247,319` + `scoring/types.py::HeuristicFallback` | Modello esiste, mai usato |
| C5 | `assess_dimension`/`assess_batch` usano `instructor.Mode.MD_JSON` (corretto per GLM-5.1) ma nessun retry tipizzato sui transient API error: instructor ritenta solo su `ValidationError`, NON su 429/5xx/timeout. `LLMProvider._call_llm` ha solo singolo `asyncio.wait_for` + 1 fallback model | `assessment/llm_provider.py:95-160` | Costo/latenza imprevedibile su rate limit transient |

### 2.4 P1 — Heuristic detection truncation-fragile

| # | Problema | File:line | Evidenza |
|---|----------|-----------|----------|
| D1 | `_detect_ci()` substring `.github/workflows/` su packed content. Repomix interface-mode con keep_signatures=True droppa file YAML completi (non sono code) → CI workflows non finiscono nel pack | `assessment/heuristics.py:225-228` + `repomix_adapter.py:158-173` | pydantic ha `.github/workflows/`, heuristic dice no |
| D2 | `_detect_tests` ha già fallback path-based (T2.5 Fase 2) ma `_detect_ci`/`_detect_docs`/`_detect_security` no — ancora substring puro | `assessment/heuristics.py:225-246` | Asymmetric quality |
| D3 | `_detect_languages` dipende da regex su pathlike. Su contenuto truncato a 4K char i linguaggi rilevati non riflettono la repo | `assessment/heuristics.py:293-313` | Underreporting language distribution |

### 2.5 P1 — Operational hardening

| # | Problema | File:line | Evidenza |
|---|----------|-----------|----------|
| E1 | `gate2_static._clone_repo` usa bare `except Exception` (CLAUDE.md violation: "Never raise bare Exception") | `gate2_static.py:157` | Lint clean ma viola spirit della rule |
| E2 | LLM in-memory cache `_cache: dict[str, tuple[...]]` non persistente; perde stato a restart MCP server. Phase 2 T3.5 ha aggiunto `FeatureStore` per ScoreResult ma non per `DeepAssessmentResult` | `assessment/orchestrator.py:85-87,197-207` | Coverage parziale del caching layer |
| E3 | Nessun budget enforcement sul totale tokens/giorno — `BudgetController.check_daily_soft_limit` solo monitor (non blocca). Costo runaway possibile | `assessment/budget_controller.py`, `orchestrator.py:210` | "soft" non sufficiente per produzione |
| E4 | `assessment/orchestrator.py::_assess_candidate` cattura `Exception` generico al `except` finale → maschera errori non-AssessmentError (memoryError, KeyboardInterrupt-related, ecc.) | `assessment/orchestrator.py:301-306` | Debug più difficile su errori transient |

### 2.6 P2 — Observability & reproducibility

| # | Problema | File:line | Evidenza |
|---|----------|-----------|----------|
| F1 | Manca un comando `ghdisc doctor` che faccia pre-flight: ping GitHub API, ping NanoGPT, check `gitleaks`/`scc`/`git`/`repomix`, validate config, validate profiles | — | Vedi A→E che richiedono diagnostica |
| F2 | Test report markdown manuale. Phase 2 ha generator per Wave 4 calibration; nessun generator per E2E session report | `scripts/generate_wave4_reports.py` (presente), nessuno per session E2E | Riproducibilità report |
| F3 | `DeepAssessmentResult.degraded` field non esposto in CLI rank table (Phase 2 T2.4 lo definì ma non lo collegò all'output finale) | `cli/rank.py`, `models/assessment.py` | UX explainability |
| F4 | Missing `corroboration_level` column nel `ghdisc rank` output (defined su ScoreResult, mai visualizzato) | `cli/rank.py:362+` | Già notato in test_report_2 |

---

## 3) Verifica sul codice reale

Ogni claim sopra verificato con grep / Read sul tree corrente:

| Claim | File:line | Verifica |
|-------|-----------|----------|
| `_MEGA_POPULAR_STAR_THRESHOLD = 100_000` | `discovery/search_channel.py:27` | ✅ confermato |
| `compute_total` flat avg no confidence | `models/screening.py:306-317` | ✅ confermato |
| Tre fallback gitleaks divergenti | `secrets_check.py:48,75` + `gate2_static.py:238` | ✅ confermato |
| `_MAX_LLM_CONTENT_CHARS = 4_000` | `assessment/orchestrator.py:48` | ✅ confermato |
| `repomix` timeout fisso 120s | `assessment/repomix_adapter.py:39` | ✅ confermato |
| `min(confidence)` overall | `result_parser.py:355` | ✅ confermato |
| `confidence=0.3` literal heuristic | `result_parser.py:247,319` | ✅ confermato |
| `HeuristicFallback` definito ma scollegato | `scoring/types.py::HeuristicFallback` non importato in `result_parser.py` | ✅ confermato |
| `_detect_ci` substring puro | `assessment/heuristics.py:225-228` | ✅ confermato |
| Bare `except Exception` clone | `gate2_static.py:157` | ✅ confermato |
| 12/12 DomainProfile registrati | `scoring/profiles.py:260-368` + `models/scoring.py:328-419` | ✅ tutti definiti, ma domain detection upstream non li attiva |

`_DOMAIN_THRESHOLDS` legacy: già rimosso (Phase 2 D11).

---

## 4) Task overview

| Wave | ID | Task | Pri | Dep | Effort | Output verificabile |
|------|----|------|-----|-----|--------|---------------------|
| A | TA1 | `_MEGA_POPULAR_STAR_THRESHOLD` configurable + documentato + opt-out | P0 | — | 0.5g | env var `GHDISC_DISCOVERY_MEGA_POPULAR_THRESHOLD`, default 100K, doc in wiki |
| A | TA2 | Audit search query: rimuovere ogni filtro implicito che escluda 0-star repos; logging completo della query string finale | P0 | — | 0.5g | log strutturato `discovery_query_built` con `q_string` completa; test snapshot |
| A | TA3 | Domain detection module: classificazione `RepoCandidate.domain` da topics/language/description (regole + fallback heuristic) | P0 | — | 2g | `discovery/domain_classifier.py` nuovo; ≥70% accuracy su fixture 50 repo manually-labeled |
| A | TA4 | Espandere `code_search_channel` budget (configurable, allow >1 page con polite throttle) per ridurre dominanza Search API | P1 | — | 1g | env `GHDISC_DISCOVERY_CODE_SEARCH_MAX_PAGES`, default 1; test su 3 |
| B | TB1 | `compute_total` confidence-aware in `MetadataScreenResult` e `StaticScreenResult` (esclude sub-score con `confidence ≤ 0.0` dalla media, espone `coverage`) | P0 | — | 1.5g | nuovi field `gate1_coverage`/`gate2_coverage`; ablation test |
| B | TB2 | Unificare fallback gitleaks/scc/scorecard a un unico `_FALLBACK_*` set (`value=0.5, confidence=0.0`) — rimuovere magic 0.3 | P0 | TB1 | 0.5g | grep `_FALLBACK` ritorna 1 source per (value, confidence); test |
| B | TB3 | `ghdisc doctor` (sub-comando o flag) che pre-checka `gitleaks`, `scc`, `git`, repomix, ping GitHub, ping NanoGPT — emette warning strutturati | P0 | — | 1g | `ghdisc doctor` esce 0 se OK, 1 se any check fail; CI uses it |
| B | TB4 | MCP server / CLI startup: log warning una sola volta (`logger.warning("system_tool_missing", tool="gitleaks")`) se tool assenti, **non** ad ogni Gate 2 | P1 | TB3 | 0.5g | log emesso 1x per process, dedupe via flag |
| C | TC1 | Adaptive `_MAX_LLM_CONTENT_CHARS` basato su tier: tiny <1K → full, small 1K-10K → 16K chars, medium 10K-100K → 12K chars, large 100K+ → 8K chars + hint nei prompt che il contenuto è truncato | P0 | — | 2g | `assessment/content_strategy.py` nuovo; test parametrico su 4 tier |
| C | TC2 | `RepomixAdapter`: pre-check size via lightweight `git ls-tree` o GitHub API; se >500K token estimated, skip repomix e fai sampling (top-k file più rilevanti via path heuristic) | P0 | TC1 | 2.5g | repo huge non timeout; `RepoContent.sampling_used: bool` |
| C | TC3 | `result_parser` use `HeuristicFallback` (cap 0.25) e `degraded=True` quando dimensioni fallback heuristic | P0 | — | 1g | rimuovere literal `0.3`; field `degraded: bool` su `DeepAssessmentResult` |
| C | TC4 | `_compute_overall_confidence`: weighted avg pesata sui weights del DEFAULT_PROFILE, **non** `min(...)` | P0 | — | 0.5g | confidence riflette mix LLM/heuristic; test ablation |
| C | TC5 | `LLMProvider._call_llm`: tenacity retry su 429/5xx/timeout (3 attempt, exponential jitter `multiplier=1, max=30, jitter=5`), distinto dal max_retries di instructor (che ritenta solo su validation) | P0 | — | 1g | mock httpx 429→200 → 1 retry; test |
| C | TC6 | `LLMProvider`: estrazione token usage robusta (parsing `raw_response.usage` per provider che lo espone, fallback estimato chiaro) | P1 | TC5 | 0.5g | log `token_usage_source: "api" | "estimated"` |
| D | TD1 | `_detect_ci` path-based fallback simmetrico a `_detect_tests` (cerca `.github/workflows/*` nei file_paths, non in content lower) | P0 | — | 0.5g | fixture pydantic-like → `has_ci=True` |
| D | TD2 | Stesso pattern per `_detect_security` (`SECURITY.md` nei paths) e `_detect_docs` (`README.md`/`docs/` nei paths) | P1 | TD1 | 0.5g | fixture |
| D | TD3 | RepomixAdapter: opzione `include_paths=[".github/workflows/*", "SECURITY.md", ...]` per garantire che i signal file finiscano nel pack indipendentemente dalla compressione | P1 | TD1 | 1g | RepoContent contiene workflow yaml file headers; test |
| E | TE1 | Sostituire `except Exception` in `gate2_static._clone_repo` con `OSError`/`asyncio.TimeoutError`/domain exception | P1 | — | 0.25g | grep ritorna 0 |
| E | TE2 | `AssessmentOrchestrator`: persistere `DeepAssessmentResult` in `FeatureStore` (analogo a `ScoringEngine.score_cached`) → cache cross-restart | P1 | — | 1g | restart MCP, re-assess: cache hit |
| E | TE3 | `BudgetController`: opzione `hard_daily_limit` configurable; quando superato → raise `BudgetExceededError` invece di solo log | P1 | — | 0.5g | env `GHDISC_ASSESSMENT_HARD_DAILY_LIMIT`; test |
| E | TE4 | Audit `except Exception` su tutta la codebase: lista violations e fix mirati | P2 | — | 1g | grep + fix; lint rule `BLE001` opzionale |
| F | TF1 | `cli/rank.py`: aggiungere colonne `Coverage`, `Confidence`, `Degraded`, `Corroboration` al table renderer | P1 | — | 0.5g | snapshot test del rendering |
| F | TF2 | `scripts/generate_session_report.py` analogo a `generate_wave4_reports.py` per E2E session JSON → markdown report deterministico | P2 | TF1 | 1g | comando documentato |
| F | TF3 | Wiki update: `architecture/phase3-production-readiness.md` (nuovo log decisioni); aggiornare `tiered-pipeline.md` con coverage Gate1/Gate2; `screening-gates.md` con doctor pre-check; `operational-rules.md` con tenacity LLM | P1 | tutti | 1g | file presenti, link validi |

**Totale tecnico**: ~22 giorni-uomo. Parallelizzabile A+B+D, poi C+E, infine F.

---

## 5) Wave A

### TA1 — Mega-popular threshold configurable

**Stato**: hardcoded `100_000`, sempre attivo, no documentazione.

**Azione**:
```python
# config.py — DiscoverySettings
mega_popular_star_threshold: int | None = Field(
    default=100_000,
    description=(
        "Stars threshold above which repos are excluded from Search API results "
        "to reduce noise from over-represented mega-popular projects. "
        "Set to None to disable (full star-neutrality). "
        "This is NOT a quality penalty — quality is evaluated independently."
    ),
)

# search_channel.py
def build_query(self, query: DiscoveryQuery) -> str:
    parts = [...]
    if self._settings.mega_popular_star_threshold is not None:
        parts.append(f"-stars:>{self._settings.mega_popular_star_threshold}")
    return " ".join(parts)
```

**Wiki**: `anti-star-bias.md` — sezione "Discovery noise reduction (not a bias)" che spiega esplicitamente che `-stars:>N` è **opt-out**, non un anti-star penalty.

**Acceptance**: `GHDISC_DISCOVERY_MEGA_POPULAR_STAR_THRESHOLD=` (vuoto) → query non contiene `-stars:>`. Default mantenuto.

### TA2 — Query logging trasparente

**Stato**: query construction non loggata; test report cita filtro non presente.

**Azione**:
```python
# search_channel.py::search()
logger.info(
    "discovery_query_built",
    channel="search",
    query_string=query_string,
    qualifiers={
        "language": query.language,
        "topics": query.topics,
        "pushed_after": cutoff_iso,
        "exclude_archived": True,
        "mega_popular_threshold": self._settings.mega_popular_star_threshold,
    },
)
```

Stesso log per `code_search_channel`, `seed_expansion`, `registry_channel`.

**Acceptance**: ogni discovery run espone query string completa nel log strutturato.

### TA3 — Domain classifier

**Stato**: `RepoCandidate.domain` quasi sempre `OTHER` → DEFAULT_PROFILE applicato → 11 profili specifici dead code.

**Azione** — `discovery/domain_classifier.py`:
```python
class DomainClassifier:
    """Maps RepoCandidate metadata to DomainType using rules + heuristics.

    Rules applied in order; first match wins. Falls back to OTHER.
    Rules are derived from: topic taxonomy, language conventions, description keywords.
    """

    _RULES: list[tuple[DomainType, _RuleFn]] = [
        (DomainType.ML_LIB, lambda c: any(t in c.topics for t in {"machine-learning", "deep-learning", "pytorch", "tensorflow"})),
        (DomainType.WEB_FRAMEWORK, lambda c: any(t in c.topics for t in {"web-framework", "http", "asgi", "wsgi"})),
        (DomainType.CLI, lambda c: "cli" in c.topics or _has_cli_signals(c)),
        ...
    ]

    def classify(self, candidate: RepoCandidate) -> DomainType: ...
```

Hook in discovery channels (post `_map_item`) → set `candidate.domain` prima di tornare il pool.

**Wiki**: `domain/domain-strategy.md` — sezione nuova "Classification rules table".

**Acceptance**: fixture 50 repo manually labeled (10 per main domain) → ≥70% accuracy. Test + golden file.

### TA4 — Code search pages configurable

**Stato**: `_MAX_PAGES_CODE_SEARCH = 1` blocca espansione; signal-driven discovery rimane sotto-rappresentata vs Search API.

**Azione**: `DiscoverySettings.code_search_max_pages: int = 1` (default conservativo, può essere alzato a 3 se rate budget consente). Logging quota residua dopo ogni call.

---

## 6) Wave B

### TB1 — Confidence-aware Gate 1/2 composite

**Stato**: `compute_total` media flat ignorando `confidence`. Sub-score fallback (conf=0.0) deflazionano composite.

**Azione**:
```python
# models/screening.py
def compute_total(self) -> tuple[float, float]:
    """Returns (raw_total, coverage).

    Sub-scores with confidence ≤ 0 are excluded from average; coverage
    reports the fraction of weight that had real data.
    """
    scores = [self.hygiene, self.maintenance, ...]
    total_weight_possible = sum(s.weight for s in scores)
    weighted_sum = 0.0
    weight_used = 0.0
    for s in scores:
        if s.confidence <= 0.0:
            continue
        weighted_sum += s.value * s.weight
        weight_used += s.weight
    if weight_used <= 0:
        return 0.0, 0.0
    coverage = weight_used / total_weight_possible
    raw = weighted_sum / weight_used
    # Damping mirroring scoring/engine.py::_apply_weights (D3)
    damped = raw * (0.5 + 0.5 * coverage)
    return damped, coverage
```

Aggiungere `gate1_coverage: float`, `gate2_coverage: float` ai rispettivi result model.

**Wiki**: `screening-gates.md` — sezione "Coverage-aware composite (consistency with Layer D)".

**Acceptance**:
- Test: 4 sub-score con 1 fallback (conf=0) e 3 reali (conf=1, value=0.7) → composite NON deflazionato vs scenario tutti reali.
- Test: tutti fallback → composite=0.0, coverage=0.0.
- Backward compat: tests esistenti che assumono `gate2_total: float` direttamente continuano a passare (rifattorizzare se serve).

### TB2 — Unificare fallback magic numbers

**Stato**: tre code path divergenti (0.5/0.0, 0.5/0.3, 0.3/0.0).

**Azione**: costanti centralizzate in `screening/__init__.py`:
```python
FALLBACK_VALUE: float = 0.5      # neutro, non penalizza né premia
FALLBACK_CONFIDENCE: float = 0.0  # marker "no data" → escluso dalla media (TB1)
```

Sostituire ogni `value=0.3 / 0.5, confidence=0.0/0.3` con queste costanti. Effetti:
- gitleaks-missing → `value=0.5, confidence=0.0` ovunque.
- scc-missing → `value=0.5, confidence=0.0` (era 0.5/0.3 — chiarisce semantica).
- scorecard-missing → idem (Phase2 wiki menziona 0.3 ma è già stato spostato a constant).

**Acceptance**: grep `value=0\.[0-9]+, confidence=` ritorna 1 sola sorgente per valore.

### TB3 — `ghdisc doctor`

**Stato**: nessun pre-flight; problema ai system tools emerge solo a runtime.

**Azione** — nuovo `cli/doctor.py`:
```python
@app.command()
def doctor() -> None:
    """Pre-flight check for system dependencies + connectivity."""
    checks: list[CheckResult] = [
        check_binary("git", required=True),
        check_binary("gitleaks", required=False, impact="Gate 2 secret scoring degraded"),
        check_binary("scc", required=False, impact="Gate 2 complexity scoring degraded"),
        check_python_package("repomix"),
        check_github_api(token=settings.github.token),
        check_nanogpt_api(api_key=settings.assessment.nanogpt_api_key),
        check_profiles_loadable(settings.scoring.custom_profiles_path),
        check_writable(settings.feature_store.db_path),
    ]
    render_table(checks)
    raise typer.Exit(code=0 if all(c.ok for c in checks) else 1)
```

Hook in `make ci` opzionale (`make ci-doctor`).

**Acceptance**: `ghdisc doctor` su sistema senza gitleaks/scc esce 0 con warning chiari (`required=False`), su sistema senza git esce 1.

### TB4 — Boot warning dedupe

**Stato**: `gate2_static._run_secrets/_run_complexity` warning per ogni repo.

**Azione**: `SubprocessRunner` mantiene `_unavailable_tools: set[str]`; primo discovery → `logger.warning("tool_unavailable")` + add to set; chiamate successive → `logger.debug` invece di warning.

---

## 7) Wave C

### TC1 — Adaptive content strategy

**Stato**: `_MAX_LLM_CONTENT_CHARS = 4_000` indipendente dalla repo size.

**Azione** — `assessment/content_strategy.py`:
```python
@dataclass(frozen=True)
class ContentStrategy:
    repo_size_tier: Literal["tiny", "small", "medium", "large", "huge"]
    repomix_max_tokens: int
    llm_max_chars: int
    use_sampling: bool

def select_strategy(estimated_total_tokens: int) -> ContentStrategy:
    if estimated_total_tokens < 2_000:
        return ContentStrategy("tiny", 4_000, 16_000, False)
    if estimated_total_tokens < 20_000:
        return ContentStrategy("small", 16_000, 16_000, False)
    if estimated_total_tokens < 200_000:
        return ContentStrategy("medium", 30_000, 12_000, False)
    if estimated_total_tokens < 1_000_000:
        return ContentStrategy("large", 40_000, 10_000, True)
    return ContentStrategy("huge", 40_000, 8_000, True)  # sampling required
```

`AssessmentOrchestrator._assess_candidate` usa `select_strategy(estimated_tokens_pre_pack)` per dimensionare repomix + llm content.

**Acceptance**: pydantic (243K tokens) → strategy "large", llm_max_chars=10_000, sampling abilitato. Test parametrico per ogni tier.

### TC2 — Pre-pack size estimate + sampling

**Stato**: nessuna pre-stima; repomix lanciato sempre con timeout 120s.

**Azione**:
1. `RepomixAdapter.estimate_size(repo_url) -> int`: usa `git ls-tree -l HEAD` lightweight via `git clone --depth=1 --no-checkout` + `du`, oppure GitHub `/repos/{owner}/{repo}` `size` field (KB) come proxy iniziale (`tokens ≈ size_kb * 250`, calibrare).
2. Se `estimated > 1_000_000` tokens (huge): skip full repomix, attiva `_pack_sampled()`:
   - Esegue repomix con `include_patterns` mirati: `["README*", "CHANGELOG*", "docs/**/*.md", ".github/workflows/*", "src/**/__init__.py", "src/**/*.py"][:N_files]`.
   - Fallback ulteriore: top-k file per LOC (via `git ls-files | xargs wc -l | sort -rn`) limitati a N=50.
3. Marker su `RepoContent.sampling_used: bool` propagato a `DeepAssessmentResult.degraded` se True.

**Acceptance**: huggingface/diffusers (1.75M token) → `sampling_used=True`, no timeout, assessment completata con `degraded=True`.

### TC3 — Wire HeuristicFallback nel parser

**Stato**: `scoring/types.py::HeuristicFallback` definito, mai importato.

**Azione**: `result_parser._fill_missing_with_heuristics` e `create_heuristic_fallback` ritornano `HeuristicFallback` con `confidence ≤ 0.25`. `DeepAssessmentResult.degraded: bool = False` settato a True quando ≥1 dimension fallback heuristic.

```python
# result_parser.py
from github_discovery.scoring.types import HeuristicFallback

_HEURISTIC_CONFIDENCE_CAP = 0.20
```

**Acceptance**: pydantic con tutte LLM dim ok → degraded=False; con 1 LLM dim failed → degraded=True, confidence overall ridotta proporzionalmente.

### TC4 — Weighted overall confidence

**Stato**: `_compute_overall_confidence = min(...)` → 1 dim a 0.3 → tutto a 0.3.

**Azione**:
```python
def _compute_overall_confidence(self, dimensions, profile=None) -> float:
    if not dimensions:
        return 0.0
    profile = profile or get_domain_profile(DomainType.OTHER)
    weighted_sum = 0.0
    weight_sum = 0.0
    for dim, ds in dimensions.items():
        w = profile.dimension_weights.get(dim, 0.0)
        weighted_sum += ds.confidence * w
        weight_sum += w
    return weighted_sum / weight_sum if weight_sum > 0 else 0.0
```

Coerente con `ConfidenceCalculator.compute` (Phase 2 T2.2).

**Acceptance**: 7 dim conf=0.7 + 1 dim heuristic conf=0.2 con weight=0.05 → overall ≈ 0.675, non 0.20.

### TC5 — Tenacity retry su transient API errors

**Stato**: `_call_llm` solo `asyncio.wait_for` + 1 fallback model.

**Azione**:
```python
# llm_provider.py
from tenacity import (
    retry, stop_after_attempt, wait_random_exponential,
    retry_if_exception_type, before_sleep_log,
)
import openai

_TRANSIENT_OPENAI = (
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.RateLimitError,
    openai.InternalServerError,
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, max=30),
    retry=retry_if_exception_type(_TRANSIENT_OPENAI),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def _call_llm_with_retry(self, ...) -> ...:
    return await self._client.chat.completions.create(...)
```

**Context7-verified pattern** (tenacity): `wait_random_exponential(multiplier=1, max=30)` = "Full Jitter", AWS-style, riduce thundering herd.

`max_retries` di instructor (validation retry) resta separato — non sostituibile.

**Acceptance**: pytest-httpx mock 429×2 then 200 → retry 2 volte, ritorna successo.

### TC6 — Token usage robusto

**Stato**: estrazione assume `raw.usage` o stima greedy.

**Azione**: log esplicito su quale path è stato usato (`token_usage_source: "api" | "estimated"`), e quando estimated logga la formula usata.

---

## 8) Wave D

### TD1 — `_detect_ci` path-based

**Azione** — analogo a `_detect_tests`:
```python
_CI_PATH_PATTERNS = (".github/workflows/", "Jenkinsfile", ".gitlab-ci.yml", ".circleci/config")

def _detect_ci(self, content: str) -> bool:
    file_paths = _extract_file_paths(content)
    if file_paths:
        for path in file_paths:
            if any(p in path for p in _CI_PATH_PATTERNS):
                return True
        # Path data is authoritative when available; if no CI files seen,
        # don't fall back to substring (which has false positives in READMEs)
        return False
    # Legacy fallback when no Repomix file headers
    content_lower = content.lower()
    return any(p in content_lower for p in _CI_PATTERNS)
```

**Acceptance**: fixture pydantic-style packed con `==== File: .github/workflows/ci.yml ====` → `has_ci=True`. Fixture solo README citing "GitHub Actions" → `has_ci=False`.

### TD2 — Stesso pattern per security/docs

`_detect_security`: `SECURITY.md`, `dependabot.yml`, `renovate.json` nei path.
`_detect_docs`: `README.*`, `docs/`, `CONTRIBUTING.md`, `CHANGELOG.md` nei path.

### TD3 — Repomix include_patterns mirati per signal file

**Azione** — `RepomixAdapter.pack`:
```python
config.include = [...repo_default..., ".github/workflows/*", "SECURITY.md", "README*", "CHANGELOG*"]
```

Garantisce che file diagnostici per heuristics finiscano nel pack anche dopo compression.

**Verifica context7 (python-repomix)**: `config.include = [pattern]` documentato come prima funzionalità nel README.

---

## 9) Wave E

### TE1 — Bare except in clone_repo

```python
# gate2_static.py:157
except (asyncio.TimeoutError, OSError, GitHubFetchError) as e:
    logger.warning(...)
    shutil.rmtree(clone_dir, ignore_errors=True)
    return None
```

### TE2 — Persistent assessment cache

**Azione**: aggiungere `assessment_results` table al `FeatureStore` schema; `AssessmentOrchestrator._assess_candidate` consulta lo store prima del lookup in-memory; scrive dopo assessment.

Schema:
```sql
CREATE TABLE IF NOT EXISTS assessment_results (
    full_name TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    result_json TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    PRIMARY KEY (full_name, commit_sha)
);
```

TTL configurable (`AssessmentSettings.cache_ttl_hours`, già presente — riusarlo).

### TE3 — Hard daily limit

```python
# config.py
hard_daily_limit: int | None = Field(default=None, description="...")

# budget_controller.py
def check_daily_soft_limit(self, full_name: str) -> None:
    if self._daily_used >= self._daily_soft_limit:
        logger.warning(...)
    if self._hard_daily_limit and self._daily_used >= self._hard_daily_limit:
        raise BudgetExceededError(f"Daily token limit {self._hard_daily_limit} exceeded")
```

### TE4 — `except Exception` audit

```bash
grep -rn "except Exception" src/github_discovery/ | grep -v "test\|__pycache__"
```

Per ogni hit: o restringere a tipi domain, o loggare + re-raise se non è recovery legittimo.

---

## 10) Wave F

### TF1 — Rank table colonne mancanti

**Azione**: `cli/rank.py` formatter — colonne `Coverage`, `Confidence`, `Degraded` (✓/✗), `Corroboration` (`new`/`unvalidated`/`emerging`/`validated`/`widely_adopted`).

### TF2 — Session report generator

`scripts/generate_session_report.py` consuma `~/.local/share/ghdisc/sessions/<id>.json` (output esistente o nuovo) → produce markdown deterministico stile `test_report_2.md`.

### TF3 — Wiki update

| File | Sezione |
|------|---------|
| `architecture/phase3-production-readiness.md` *(nuovo)* | Decision log Wave A–F |
| `architecture/anti-star-bias.md` | TA1: configurable mega-popular threshold |
| `architecture/tiered-pipeline.md` | TB1: coverage-aware Gate 1/2 |
| `domain/screening-gates.md` | TB1, TB2: unified fallback constants; TB3: doctor |
| `patterns/operational-rules.md` | TC5: tenacity LLM retry policy; TE3: hard daily limit |
| `patterns/phase5-scoring-implementation.md` | TC3, TC4: weighted confidence + degraded flag |

---

## 11) Sequenza

### Settimana 1 — P0 critical
- **Track 1 (Discovery)**: TA1, TA2, TA3 in ordine; TA4 in parallelo
- **Track 2 (Gate 2)**: TB1, TB2, TB3, TB4 in ordine
- Fine settimana 1: pipeline producibile su pool reale con coverage trasparente

### Settimana 2 — Gate 3 + heuristics
- **Track 1**: TC1, TC2 (sequenziali); TC3, TC4 in parallelo; TC5, TC6
- **Track 2**: TD1, TD2, TD3 in parallelo

### Settimana 3 — Hardening + observability
- TE1, TE2, TE3 in parallelo; TE4 audit
- TF1, TF2, TF3 in parallelo
- E2E session run + `test_report_3.md` generato
- Tag `v0.3.0-beta`

---

## 12) Test plan

| Categoria | Aggiunte | Esistenti | Note |
|-----------|----------|-----------|------|
| Unit (discovery) | +20 (mega-popular toggle, query logging snapshot, domain classifier rules) | preserved | |
| Unit (screening composite) | +15 (TB1 ablation, TB2 fallback constants) | preserved | |
| Unit (assessment) | +25 (content strategy tier, sampling, parser HeuristicFallback wire, weighted conf, tenacity retry mock) | preserved | |
| Unit (heuristics) | +12 (TD1/TD2/TD3 path-based) | preserved | |
| Integration (E2E) | +3 (huge repo sampling, missing-tool degraded mode, doctor exit codes) | preserved | |
| Property-based | +5 (coverage Gate1/Gate2 invariants) | preserved | |
| Lint | `BLE001` (no bare except) opt-in optional | — | |

**Coverage target**: scoring/screening/assessment ≥ 92%.

---

## 13) Acceptance

`v0.3.0-beta` marker quando **tutti** soddisfatti:

1. ✅ `ghdisc doctor` esiste, esce 0/1 deterministicamente
2. ✅ `_MEGA_POPULAR_STAR_THRESHOLD` configurable + documentato in `anti-star-bias.md`
3. ✅ Domain classifier ≥70% accuracy su fixture 50 repo
4. ✅ Gate 1 e Gate 2 espongono `coverage` field; composite confidence-aware
5. ✅ Fallback constants unificati (1 source per coppia value/confidence)
6. ✅ `_MAX_LLM_CONTENT_CHARS` adaptive da `ContentStrategy`
7. ✅ Repo huge (>1M token) gestiti via sampling; nessun timeout repomix
8. ✅ `DeepAssessmentResult.degraded` esposto in CLI rank table
9. ✅ Confidence overall pesata (no min); riflette mix LLM/heuristic
10. ✅ Tenacity retry su 429/5xx/timeout LLM (3 attempt, jittered exponential)
11. ✅ `_detect_ci`/`_detect_security`/`_detect_docs` path-based primary
12. ✅ Persistent assessment cache (FeatureStore extended)
13. ✅ `BudgetExceededError` raise su hard limit
14. ✅ E2E session report generabile via script
15. ✅ Wiki aggiornata (4 file existing + 1 nuovo)
16. ✅ `make ci` verde; mypy --strict 0 errori; ruff 0 errori
17. ✅ 1587 → ≥1670 test, 0 regression

---

## 14) Rischi

| Rischio | Prob | Imp | Mitigazione |
|---------|------|-----|-------------|
| TB1 cambia composite Gate 2 → repo prima passing falliscono ora | Media | Alto | Ablation test su fixture 20 repo; flag `GHDISC_SCREENING_LEGACY_COMPOSITE=1` per rollback temporaneo |
| TC2 sampling produce LLM input degraded → quality_score divergono molto da pre-change | Media | Medio | `degraded=True` flag esposto; doc impact in CHANGELOG; expert review N=10 repo huge pre/post |
| TC5 tenacity retry maschera errori reali (es. API key sbagliata) | Bassa | Medio | Solo `_TRANSIENT_OPENAI` whitelist; auth/permission errors NON ritentati; `before_sleep_log` |
| TA3 domain classifier accuracy <70% sul fixture | Media | Medio | Iterazione regole; estendere fixture a 100; fallback OTHER + log per bootstrapping training set futuro |
| TE2 cache persistente popola DB con risultati stale dopo cambio modello LLM | Media | Medio | TTL già presente; in `cache_key` includere `model_used` per invalidare on switch |
| TF1 colonne nuove rompono rendering width terminale | Bassa | Basso | Rich auto-truncate; opzione `--compact` per layout ridotto |

---

## 15) Context7 + wiki cross-refs

**Context7 verified** (eseguire `mcp__plugin_context7_context7__query-docs` prima di implementare):

| Lib | ID | Pattern | Task |
|-----|----|---------|------|
| `python-repomix` | `/andersonby/python-repomix` | `RepomixConfig.include`, `compression.keep_interfaces`, RepoProcessor pre-process estimate | TC1, TC2, TD3 |
| `tenacity` | `/jd/tenacity` | `@retry(stop=stop_after_attempt(N), wait=wait_random_exponential(multiplier=1, max=30), retry=retry_if_exception_type(...))` | TC5 |
| `instructor` | `/567-labs/instructor` | `instructor.from_openai(client, mode=instructor.Mode.MD_JSON)`, `max_retries` (separate from network retry), async client patching | TC5, TC6 |
| `httpx` | `/encode/httpx` | `AsyncClient` lifecycle, `aclose()`, `AsyncHTTPTransport(retries=N)` for connection-level retries | TC5, TE1 |
| `pydantic` v2 | `/pydantic/pydantic` | `Field(ge,le)`, `computed_field`, model_validator, JSON-compatible dict types | TB1, TC3 |
| `hypothesis` | `/hypothesisworks/hypothesis` | strategies for property-based composite invariants | property test TB1 |
| `typer` | — | sub-command groups (`ghdisc doctor`) | TB3 |
| `structlog` | — | bound logger; one-time warning dedupe | TB4 |

**Wiki update obbligatorio (CLAUDE.md)**:

| File | Sezione |
|------|---------|
| `architecture/phase3-production-readiness.md` *(nuovo)* | Decision log Wave A–F (analogo a `phase2-remediation.md`) |
| `architecture/anti-star-bias.md` | "Discovery noise reduction is opt-out" + TA1 |
| `architecture/tiered-pipeline.md` | "Coverage propagates from Gate 1+2 to Layer D" + TB1 |
| `domain/screening-gates.md` | TB2 unified constants table; TB3 doctor pre-flight; TB1 confidence-aware composite |
| `domain/scoring-dimensions.md` | TC3/TC4 confidence semantics with `degraded` flag |
| `patterns/operational-rules.md` | TC5 tenacity policy; TE3 hard budget; TE4 except hygiene |
| `patterns/phase5-scoring-implementation.md` | TC1/TC2 content strategy snapshot |

---

## 16) Out of scope

Esplicitamente **non** in v0.3.0:

- Wave 4 Fase 2 (golden dataset, Cohen κ, NDCG benchmark) — esecuzione esterna pending
- Redis distributed cache → v0.4 (multi-worker scaling)
- OSV adapter lockfile parsing reale → v0.4
- Fine-tune custom domain classifier su training data → v0.4
- ARCHITECTURE proxy via dependency-graph clustering → v0.4 (research)
- Public hosted MCP server → v0.4 (go-to-market)
- Multi-rater feedback loop in produzione → v0.4
- Per-language quality benchmarks Python/JS/Rust/Go/Java separati → v0.4
- A/B testing infrastructure per profile weights → v0.4
- Sostituzione GLM-5.1 con modello calibrato → v0.4 (richiede Wave 4 data)
- Removal `is_hidden_gem` da `ScoreResult` (deprecated 0.2.0) → v0.3.x cleanup separato

---

**Fine Production Readiness Plan v1.**
