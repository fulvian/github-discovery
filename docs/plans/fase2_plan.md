# GitHub Discovery — Fase 2 Implementation Plan (Audit Remediation)

## Meta

- **Stato**: Draft v1
- **Data**: 2026-04-26
- **Tipo**: Remediation plan post-audit indipendente (4 LLM auditor)
- **Versione di partenza**: v0.1.0-alpha (118+ source files, 1326 tests passing, 0 lint/type errors)
- **Versione target**: v0.2.0-beta (scoring difendibile, ranking deterministico, single-source-of-truth, calibrazione empirica)
- **Riferimenti audit**:
  - `docs/audit/audit_1_claude.md` (1068 righe, deep analysis — *fonte primaria*)
  - `docs/audit/audit_1_gemini.md` ≡ `docs/audit/audit_1_chatgpt.md` (145 righe, sintesi convergente)
  - `docs/audit/audit_1_perplexity.md` (21 righe, scarso valore — solo riformulazione del prompt)
  - `docs/audit/audit_prompt_1.md` (494 righe, prompt originale)
- **Riferimenti wiki obbligatori** (per CLAUDE.md):
  - `docs/llm-wiki/wiki/architecture/anti-star-bias.md` — star-neutral design, hidden gem definition
  - `docs/llm-wiki/wiki/architecture/tiered-pipeline.md` — pipeline a 4 gate, derivazione dimensioni
  - `docs/llm-wiki/wiki/domain/scoring-dimensions.md` — 8 dimensioni, weight profiles
  - `docs/llm-wiki/wiki/domain/screening-gates.md` — Gate 1/2 sub-scores
  - `docs/llm-wiki/wiki/patterns/operational-rules.md` — error handling standard, structlog
  - `docs/llm-wiki/wiki/patterns/phase5-scoring-implementation.md` — stato attuale Layer D
- **Context7 verification obbligatoria** (CLAUDE.md): pydantic v2 `Field`/`computed_field`/`model_validator`, pydantic-settings v2 multi-source loading, `hashlib.blake2b` (stdlib), `tenacity` retry/backoff, `httpx.AsyncClient` lifecycle, `hypothesis` strategies, `structlog` bound logger, `pytest` parametrize/property-based.
- **Durata stimata**: 4–6 settimane (1 dev FT) o 2–3 settimane (2 dev paralleli)
- **Milestone**: M9 — Scoring Defensible Beta (release v0.2.0-beta)
- **Dipendenza**: tutte le 10 fasi precedenti (Phase 0–9) verificate, `make ci` verde

---

## Indice

1. [Obiettivo e contesto](#1-obiettivo-e-contesto)
2. [Sintesi convergente dei 4 audit](#2-sintesi-convergente-dei-4-audit)
3. [Verifica sul codice reale](#3-verifica-sul-codice-reale)
4. [Task overview](#4-task-overview)
5. [Wave 1 — Critical Bugs (P0)](#5-wave-1--critical-bugs-p0)
6. [Wave 2 — Scoring Logic Hardening (P0/P1)](#6-wave-2--scoring-logic-hardening-p0p1)
7. [Wave 3 — Robustness & Resource Safety (P1)](#7-wave-3--robustness--resource-safety-p1)
8. [Wave 4 — Empirical Calibration (P0 metodologico)](#8-wave-4--empirical-calibration-p0-metodologico)
9. [Wave 5 — Architectural Refactor (P2)](#9-wave-5--architectural-refactor-p2)
10. [Sequenza di implementazione](#10-sequenza-di-implementazione)
11. [Test plan](#11-test-plan)
12. [Criteri di accettazione](#12-criteri-di-accettazione)
13. [Rischi e mitigazioni](#13-rischi-e-mitigazioni)
14. [Verifica Context7 e wiki cross-references](#14-verifica-context7-e-wiki-cross-references)
15. [Out of scope](#15-out-of-scope)

---

## 1) Obiettivo e contesto

I 4 audit indipendenti convergono su un giudizio comune: **architettura solida, scoring promettente ma con difetti concettuali e bug verificabili**. Voti medi:

| Auditor | Scoring logic | Code quality |
|---------|---------------|--------------|
| Claude | 5.5 / 10 | 7 / 10 |
| Gemini | 6.5 / 10 | 8 / 10 |
| ChatGPT | 6.5 / 10 (≡ Gemini) | 8 / 10 |
| Perplexity | n/a (solo prompt restate) | n/a |

Phase 2 chiude i problemi **identificabili e indipendenti dal benchmark empirico** (Wave 1–3, 5) e avvia il **lavoro metodologico** che sblocca il resto (Wave 4: ground-truth dataset, calibrazione weight per dominio).

**Principi**:
1. **No regressioni**: la suite di 1326 test deve rimanere verde dopo ogni task. Aggiunte di test, non rewrite.
2. **Single source of truth** per ogni costante, threshold, mapping.
3. **Star-neutrality preservata**: `value_score = quality_score`. Non si tocca il principio architetturale.
4. **Determinismo cross-process**: ranking riproducibile bit-perfect tra deploy distinti.
5. **Explainability first**: ogni cambiamento al composite score deve essere visibile via `coverage`/`degraded` flag.
6. **Mypy --strict mantenuto**: ogni nuova funzione full-typed; trailing commas; line length 99; structlog only.

---

## 2) Sintesi convergente dei 4 audit

I problemi su cui **almeno 2 auditor concordano** o che ho **verificato direttamente nel codice**:

### 2.1 CRITICAL — Bug confermati nel codice

| # | Problema | File | Concordanza |
|---|----------|------|-------------|
| C1 | **Doppia source-of-truth `hidden_gem` thresholds**: `models/scoring.py:29-30` (`_HIDDEN_GEM_MAX_STARS=100`, `_HIDDEN_GEM_MIN_QUALITY=0.5`) usato da `ScoreResult.is_hidden_gem` (line 152). `config.py:171/175` (`hidden_gem_star_threshold=500`, `hidden_gem_min_quality=0.7`) usato da `ValueScoreCalculator.is_hidden_gem`. Due API pubbliche restituiscono risultati contraddittori per lo stesso repo. | `models/scoring.py`, `scoring/value_score.py` | Claude, Gemini, ChatGPT |
| C2 | **`hash()` non deterministico cross-process**: `scoring/ranker.py:150` usa `hash((seed, full_name))`. PEP 456 → `PYTHONHASHSEED` randomizzato per process; output cambia anche tra versioni minor di CPython. Tie-breaking non riproducibile. | `scoring/ranker.py` | Claude, Gemini, ChatGPT |
| C3 | **Weight redistribution implicita**: `scoring/engine.py:373-383` esclude dimensioni con `confidence ≤ 0.0` e divide per `total_weight` ridotto. Per profilo `ML_LIB` un repo Gate1+2-only viene valutato sul 60% del peso (FUNC 0.25 + INNOV 0.15 esclusi), e il quality_score non è confrontabile con un repo Gate1+2+3 completo. Nessuna `coverage` esposta. | `scoring/engine.py` | Claude, Gemini, ChatGPT |

### 2.2 HIGH — Errori concettuali nel `_DERIVATION_MAP`

`scoring/engine.py:35-67`. Verdetti convergenti:

| Dimensione | Mapping attuale | Verdetto convergente |
|------------|----------------|----------------------|
| `CODE_QUALITY` | `0.5·review_practice + 0.3·ci_cd + 0.2·dependency_quality` | **Errato** — omette `complexity` e `test_footprint`, sovrappesa il *processo* (review) sul *prodotto* (codice) |
| `ARCHITECTURE` | `0.7·complexity + 0.3·ci_cd` | **Gravemente errato** — complessità ciclomatica (scc) ≠ qualità architetturale; misura LOC e branches, non coupling/cohesion/layering |
| `TESTING` | `0.7·test_footprint + 0.3·ci_cd` | **Ragionevole** — proxy di quantità accettabile; misura presenza non qualità |
| `DOCUMENTATION` | `0.6·hygiene + 0.4·review_practice` | **Errato** — `review_practice` (PR template, label usage) non ha relazione causale con qualità doc |
| `MAINTENANCE` | `0.4·maint + 0.3·release + 0.2·ci_cd + 0.1·hygiene` | **Corretto** — tuning minore: ridurre double-counting di `ci_cd` |
| `SECURITY` | `0.35·sec_hyg + 0.25·vuln + 0.25·secret + 0.15·dep` | **Corretto** — nota: `vulnerability` è di fatto neutralizzato (OSV adapter stub) |
| `FUNCTIONALITY` | `[]` (non derivabile) | **Onesto come scelta**, ma il default neutro causa C3 |
| `INNOVATION` | `[]` (non derivabile) | Idem |

### 2.3 HIGH — Confidence model

- Confidence overall = `mean(per_dim_confidence) + gate_coverage_bonus`. Non pesata dai weight del profilo. Una dimensione critica per il dominio (es. SECURITY in DEVOPS_TOOL) pesa quanto una marginale.
- `_SOURCE_CONFIDENCE["gate3_llm"] = 0.8` non documentato (literature: 0.6–0.75 per LLM su code review).
- Confidence per-dimensione costante per `gate12_derived` (sempre 0.4): non riflette la qualità del mapping (TESTING ha mapping forte → 0.55, ARCHITECTURE debole → 0.25).

### 2.4 MEDIUM — Robustness e error handling

- `_safe_score()` Gate 1: `try/except → (0.0, 0.0)` (fail-closed silenzioso). Trasforma rate-limit/auth in "repo scadente".
- `gather_context()._fetch()`: `except Exception: return {}` maschera 401/403/429/5xx come "no data".
- Heuristic fallback (`assessment/heuristics.py`): scoring additivo basato su substring → gameable (`mkdir tests && touch ci.yml` ottiene ~0.85).
- Clone temp dir: `shutil.rmtree` in `finally` non resiste a SIGKILL/OOM → orphan dir leak.
- Cache assessment in-memory: non persistente, non condivisa cross-process.

### 2.5 MEDIUM — Cross-domain normalization

- `cross_domain.py` z-score con `N=1` ricade su `std=0.1` fallback → ogni repo isolato ottiene `normalized=0.5`. Soglia minima dovrebbe essere `N≥3`.
- `value_score` normalizzato separatamente da `quality_score`: ridondante (sono uguali per design star-neutral).

### 2.6 LOW — Architettura

- `_DERIVATION_MAP` e `_DOMAIN_THRESHOLDS` module-level: meglio per-`DomainProfile` (calibrazione e A/B test).
- Aggiunta di una 9ª dimensione richiede 6 file da modificare (no registry pattern).
- `custom_profiles_path` in `ScoringSettings` esiste ma non implementato (gap di trasparenza).

### 2.7 P0 metodologico — Validazione empirica assente

Tutti gli auditor concordano: **senza ground-truth dataset, ogni claim di "qualità" è non falsificabile**. Phase 9 calibration usa fixture mock (60 repo). Soglia minima per significatività: 200 repo, 3 rater, Cohen's κ ≥ 0.6.

---

## 3) Verifica sul codice reale

Prima di accettare le accuse degli auditor, ogni claim è stato verificato direttamente nei sorgenti corrispondenti:

| Claim audit | File:line | Verificato |
|-------------|-----------|------------|
| Hidden gem dual constants | `models/scoring.py:29-30, 152` + `config.py:171, 175` + `value_score.py:48-49, 92, 97` | ✅ Bug reale |
| `hash()` non deterministico | `scoring/ranker.py:150` | ✅ Bug reale |
| Weight redistribution senza coverage | `scoring/engine.py:358-383` | ✅ Bug reale |
| `_DERIVATION_MAP` mapping | `scoring/engine.py:35-67` | ✅ Mapping confermato testualmente |
| Confidence non pesata | `scoring/confidence.py:84-92` | ✅ `avg_confidence = sum(dim_confidences)/len(...)` |
| Source confidence 0.8 hardcoded | `scoring/confidence.py:26-30` | ✅ Confermato |
| Heuristic substring patterns | `assessment/heuristics.py:23-58` | ✅ Confermato |

Non ci sono claim auditor smentiti dal codice; tutti i bug elencati sono presenti.

---

## 4) Task overview

| Wave | Task ID | Task | Priorità | Dipendenze | Effort | Output verificabile |
|------|---------|------|----------|------------|--------|---------------------|
| 1 | T1.1 | Single-source-of-truth `hidden_gem` thresholds | P0 | — | 0.5g | Test parametrico: 100 input random → `ScoreResult.is_hidden_gem == ValueScoreCalculator.is_hidden_gem` |
| 1 | T1.2 | Sostituire `hash()` con `hashlib.blake2b` per tie-breaking | P0 | — | 0.5g | Test cross-process: stesso seed → stesso ordering bit-perfect |
| 1 | T1.3 | Aggiungere `coverage` field esplicito a `ScoreResult` + adjusted score | P0 | T1.1 | 1.5g | `ScoreResult.coverage ∈ [0, 1]` esposto via API/CLI; test su scenario partial-coverage |
| 1 | T1.4 | Field validators stringenti (`SubScore.weight ge=0 le=10`, `details: dict[str, str\|int\|float\|bool\|None]`) | P0 | — | 0.5g | mypy + pydantic raise su input invalido |
| 2 | T2.1 | Riprogettare `_DERIVATION_MAP` con motivazioni documentate | P0 | T1.3 | 2g | `docs/foundation/SCORING_METHODOLOGY.md`; ablation test su fixture; mapping rivisto per CODE_QUALITY/ARCHITECTURE/DOCUMENTATION |
| 2 | T2.2 | Confidence pesata dai profile weights | P1 | T2.1 | 1g | `compute_overall_confidence(infos, profile)` con weighted avg |
| 2 | T2.3 | Confidence per-dimensione variabile (`_DIMENSION_CONFIDENCE_FROM_GATE12`) | P1 | T2.1 | 0.5g | Test: TESTING > ARCHITECTURE in confidence-from-gate12 |
| 2 | T2.4 | Heuristic fallback come "ignorance signal" (range + low confidence) | P1 | — | 1.5g | `HeuristicFallback.confidence ≤ 0.2`; LLM-disabled run → tutti i repo confidence < 0.25 |
| 2 | T2.5 | Path-based detection in heuristics (regex boundary, no substring) | P1 | T2.4 | 0.5g | Falsi positivi `"latest_release"` → no match; test fixture |
| 3 | T3.1 | Distinguere errori in `_fetch()` (auth/rate-limit/network/server) | P1 | — | 1.5g | `GitHubAuthError`, `GitHubRateLimitError`, `GitHubFetchError` con `from e`; test su 401/429/5xx |
| 3 | T3.2 | Tenacity retry+backoff su Gate 1 / Gate 2 API calls | P1 | T3.1 | 1g | Retry su 429/5xx con jitter; test simulato |
| 3 | T3.3 | Orphan temp dir cleanup all'avvio worker | P2 | — | 0.5g | `_cleanup_orphan_temps(threshold_hours=6)`; test su tmp con file vecchi |
| 3 | T3.4 | LLM provider lifecycle (`async with` o lifespan) | P1 | — | 0.5g | `AsyncOpenAI` chiusura corretta; no connection leak in test |
| 3 | T3.5 | FeatureStore TTL + `ghdisc db prune` CLI | P2 | — | 1g | Colonna `expires_at` + comando typer; test su entry scaduta |
| 3 | T3.6 | Cross-domain z-score: skip normalize se `N<3` | P2 | — | 0.5g | Test: pool con 1 repo per dominio → `cross_domain_confidence=0` |
| 3 | T3.7 | Eliminare normalizzazione `value_score` (è già `quality_score`) | P2 | — | 0.25g | `value_score` rimosso da batch normalize, alias mantenuto in computed_field |
| 4 | T4.1 | Dataset di calibrazione: 200 repo cross-domain | P0 | — | 2 settimane (esterno) | `tests/feasibility/golden_dataset.json` con 200 entry |
| 4 | T4.2 | Inter-rater agreement: 3 rater, Cohen's κ ≥ 0.6 | P0 | T4.1 | 1 settimana | Report κ in `docs/foundation/calibration_report.md` |
| 4 | T4.3 | Riprogettare/ricalibrare i 12 domain profile weights su dataset | P1 | T4.2 | 1 settimana | NDCG@10 sul 20% hold-out ≥ 0.75 |
| 4 | T4.4 | Baseline comparison: random / star-only / OpenSSF / GitHub trending | P1 | T4.2 | 3g | Wilcoxon signed-rank p<0.05 vs star-ranking |
| 5 | T5.1 | `_DERIVATION_MAP` per-DomainProfile | P2 | T2.1, T4.3 | 2g | `DomainProfile.derivation_map` opzionale con fallback al default |
| 5 | T5.2 | `gate_thresholds` per-DomainProfile (rimuovere `_DOMAIN_THRESHOLDS` da orchestrator) | P2 | T5.1 | 1g | Profilo ML_LIB con `gate1_threshold=0.3`, CLI_TOOL con `0.5` |
| 5 | T5.3 | Implementare `custom_profiles_path` (YAML/TOML loading) | P2 | T5.1 | 1.5g | Test E2E: profilo custom carica e influenza ranking |
| 5 | T5.4 | Rimuovere `is_hidden_gem` da `ScoreResult` (logica di servizio, non model) — *opzionale* | P3 | T1.1 | 0.5g | Solo `ValueScoreCalculator` espone hidden gem; deprecation note |
| 5 | T5.5 | Property-based test (Hypothesis) per invarianti scoring | P1 | T1.3 | 1g | 1000 generated cases: `0≤quality≤1`, `0≤confidence≤1`, monotonicity, profile sum=1 |

**Totale effort tecnico (Wave 1+2+3+5)**: ≈ 18 giorni-uomo.
**Totale effort metodologico (Wave 4)**: 4 settimane (parallelizzabile).

---

## 5) Wave 1 — Critical Bugs (P0)

Obiettivo: chiudere i 3 bug verificabili che compromettono determinismo e consistenza, prima di tutto il resto.

### T1.1 — Single-source-of-truth `hidden_gem` thresholds

**Stato attuale** (verificato):
- `src/github_discovery/models/scoring.py:29-30` definisce costanti private `_HIDDEN_GEM_MAX_STARS=100`, `_HIDDEN_GEM_MIN_QUALITY=0.5` usate dal computed_field `is_hidden_gem` (line 152).
- `src/github_discovery/config.py:171,175` (`ScoringSettings`) definisce `hidden_gem_star_threshold=500`, `hidden_gem_min_quality=0.7` usati da `ValueScoreCalculator.is_hidden_gem` (`scoring/value_score.py:92,97`).
- Stesso input → due output diversi a seconda dell'API chiamata.

**Azioni**:
1. Cancellare `_HIDDEN_GEM_MAX_STARS` e `_HIDDEN_GEM_MIN_QUALITY` da `models/scoring.py`.
2. Rendere `ScoreResult.is_hidden_gem` dipendente da `ScoringSettings`. Due opzioni:
   - **Opzione A (preferita)**: `is_hidden_gem` non è più computed_field. Diventa metodo `evaluate_hidden_gem(settings: ScoringSettings) -> bool`. Più esplicito, niente import nel model.
   - **Opzione B**: mantenere computed_field, leggere settings via singleton lazy. Più comodo ma accoppia il model alla config.
3. `ValueScoreCalculator.is_hidden_gem` resta single source of truth della logica (criteria + reason string).
4. Aggiornare wiki `docs/llm-wiki/wiki/architecture/anti-star-bias.md` (sezione "Hidden Gem Detection") con i valori reali da config.

**Test**:
```python
# tests/unit/scoring/test_hidden_gem_consistency.py
@pytest.mark.parametrize("quality, stars", [
    (0.55, 80), (0.6, 300), (0.7, 499), (0.7, 500), (0.69, 80),
    *[(random.random(), random.randint(0, 5000)) for _ in range(100)],
])
def test_hidden_gem_consistency(quality, stars, default_settings):
    sr = ScoreResult(full_name="x/y", quality_score=quality, stars=stars)
    calc = ValueScoreCalculator(default_settings)
    assert sr.evaluate_hidden_gem(default_settings) == calc.is_hidden_gem(quality, stars, quality)[0]
```

**Acceptance**: 0 occorrenze di `_HIDDEN_GEM_*` fuori da test. Test `test_hidden_gem_consistency` verde su 100+ input.

---

### T1.2 — Tie-breaking deterministico cross-process

**Stato attuale**: `scoring/ranker.py:150` — `hash((self._settings.ranking_seed, result.full_name))`. Output dipende da `PYTHONHASHSEED` e versione CPython.

**Azione**:
```python
# scoring/ranker.py
import hashlib

def _seeded_hash(self, full_name: str) -> int:
    payload = f"{self._settings.ranking_seed}:{full_name}".encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=False)

def _sort_key(self, result: ScoreResult) -> tuple[float, float, int, str]:
    return (
        -result.quality_score,
        -result.confidence,
        -self._seeded_hash(result.full_name),
        result.full_name,
    )
```

**Context7 verify**: `hashlib.blake2b(data, digest_size=N)` è stdlib (Python 3.6+), deterministico, no platform variance.

**Test**:
- Hardcoded golden value test: `assert ranker._seeded_hash("foo/bar") == <golden_int>`.
- Subprocess test: lancia `python -c "..."` due volte (PYTHONHASHSEED random), verifica ordering identico.

**Acceptance**: ranking ripetuto in 5 run consecutivi su pool di 50 repo → identico bit-perfect.

---

### T1.3 — `coverage` field esplicito su `ScoreResult`

**Stato attuale**: `scoring/engine.py:358-383` `_apply_weights` fa `weighted_sum / total_weight` senza esporre il rapporto `total_weight / total_weight_possible`.

**Azione**:
```python
# scoring/engine.py
def _apply_weights(
    self,
    dimension_scores: dict[ScoreDimension, DimensionScoreInfo],
    profile: DomainProfile,
) -> tuple[float, float]:
    """Returns (raw_score, coverage) — coverage ∈ [0, 1]."""
    weighted_sum = 0.0
    total_weight_used = 0.0
    total_weight_possible = sum(profile.dimension_weights.values())  # ~ 1.0

    for dim, info in dimension_scores.items():
        weight = profile.dimension_weights.get(dim, 0.0)
        if info.confidence <= 0.0:
            continue
        weighted_sum += info.value * weight
        total_weight_used += weight

    if total_weight_used <= 0.0:
        return 0.0, 0.0

    raw_score = weighted_sum / total_weight_used
    coverage = total_weight_used / total_weight_possible if total_weight_possible > 0 else 0.0
    return raw_score, coverage
```

E in `score()`:
```python
quality_score, coverage = self._apply_weights(dimension_infos, profile)
# Penalize low-coverage scores conservatively (max 50% damping):
adjusted_quality = quality_score * (0.5 + 0.5 * coverage)
return ScoreResult(
    ...,
    quality_score=round(adjusted_quality, 4),
    coverage=round(coverage, 4),
    raw_quality_score=round(quality_score, 4),  # for explainability
    ...
)
```

Aggiungere a `ScoreResult` (`models/scoring.py`):
```python
coverage: float = Field(
    default=1.0, ge=0.0, le=1.0,
    description="Fraction of profile weight backed by real data (vs neutral defaults)",
)
raw_quality_score: float = Field(
    default=0.0, ge=0.0, le=1.0,
    description="Quality score before low-coverage damping",
)
```

**Esposizione**: `coverage` visibile in `mcp/tools/explainability.py`, CLI output, REST API response, `ExplainabilityReport`.

**Acceptance**: due repo con stesso `raw_quality_score=0.6`, coverage 0.6 vs 0.9 → `quality_score` finale 0.48 vs 0.57. Differenza visibile in CLI.

---

### T1.4 — Field validators stringenti

**Azioni**:
- `models/screening.py` `SubScore`: `weight: float = Field(default=1.0, ge=0.0, le=10.0)`.
- `models/screening.py`: cambiare `details: dict[str, object]` → `details: dict[str, str | int | float | bool | None]` (JSON-compatible).
- Verificare che `ScoreDimension` (StrEnum) round-trip via `model_dump_json` / `model_validate_json` (test esplicito).

**Acceptance**: pydantic raise `ValidationError` su `SubScore(weight=-1)` o `SubScore(weight=100)`.

---

## 6) Wave 2 — Scoring Logic Hardening (P0/P1)

### T2.1 — Riprogettare `_DERIVATION_MAP` con motivazioni documentate

**Mapping rivisto** (versione iniziale, da affinare con T4.3 calibration):

```python
_DERIVATION_MAP: dict[ScoreDimension, list[tuple[str, float]]] = {
    # CODE_QUALITY: prodotto tecnico (codice) > processo (review)
    # Aggiunge complexity (-> qualità strutturale) e test_footprint (-> testabilità)
    ScoreDimension.CODE_QUALITY: [
        ("complexity", 0.35),
        ("test_footprint", 0.25),
        ("review_practice", 0.25),
        ("ci_cd", 0.15),
    ],
    # ARCHITECTURE: non derivabile in modo affidabile da metadati Gate 1+2.
    # Mantenuto vuoto per onestà — vedi nota in SCORING_METHODOLOGY.md.
    ScoreDimension.ARCHITECTURE: [],
    # TESTING: invariato (mapping ragionevole)
    ScoreDimension.TESTING: [
        ("test_footprint", 0.7),
        ("ci_cd", 0.3),
    ],
    # DOCUMENTATION: review_practice rimosso (no relazione causale)
    # release_discipline = changelog per release = doc del cambiamento
    ScoreDimension.DOCUMENTATION: [
        ("hygiene", 0.7),
        ("release_discipline", 0.3),
    ],
    # MAINTENANCE: invariato con tuning per ridurre double-counting ci_cd
    ScoreDimension.MAINTENANCE: [
        ("maintenance", 0.45),
        ("release_discipline", 0.35),
        ("ci_cd", 0.10),
        ("hygiene", 0.10),
    ],
    # SECURITY: invariato (mapping ben strutturato)
    ScoreDimension.SECURITY: [
        ("security_hygiene", 0.35),
        ("vulnerability", 0.25),
        ("secret_hygiene", 0.25),
        ("dependency_quality", 0.15),
    ],
    ScoreDimension.FUNCTIONALITY: [],
    ScoreDimension.INNOVATION: [],
}
```

**Nota architetturale**: in T5.1 il mapping diventa per-`DomainProfile`, ma il *default* va corretto subito.

**Documentazione obbligatoria** (`docs/foundation/SCORING_METHODOLOGY.md`):
- Per ogni mapping: 1) razionale, 2) citazione (CHAOSS metric, OpenSSF, ISO/IEC 25010, paper), 3) confidence dichiarata.
- Sezione "Limitations": ARCHITECTURE non derivabile da Gate 1+2 → confidence 0 senza Gate 3.
- Sezione "Validation": link a `docs/foundation/calibration_report.md` (output di T4.3).

**Wiki update**: `docs/llm-wiki/wiki/domain/scoring-dimensions.md` — sezione "Derivation Map".

**Acceptance**:
1. Test ablation: per 20 fixture repo, confronto quality_score pre/post change. Differenze documentate per repo.
2. Test esiste `SCORING_METHODOLOGY.md` con citazioni minime per ogni dimensione.

---

### T2.2 — Confidence pesata dai profile weights

**Stato**: `scoring/confidence.py:84-92` — `avg_confidence = sum(dim_confidences) / len(dim_confidences)`.

**Azione**: passare `profile` al calcolo confidence:

```python
def compute(
    self,
    dimension_infos: dict[ScoreDimension, DimensionScoreInfo],
    profile: DomainProfile,
    screening: ScreeningResult | None = None,
    assessment: DeepAssessmentResult | None = None,
) -> float:
    if not dimension_infos:
        return 0.0

    weighted_conf_sum = 0.0
    weight_sum = 0.0
    for dim, info in dimension_infos.items():
        w = profile.dimension_weights.get(dim, 0.0)
        per_dim = self.compute_dimension_confidence(dim, info.source, screening, assessment)
        weighted_conf_sum += w * per_dim
        weight_sum += w

    avg_confidence = weighted_conf_sum / weight_sum if weight_sum > 0 else 0.0
    bonus = self.gate_coverage_bonus(screening, assessment)
    return max(0.0, min(1.0, avg_confidence + bonus))
```

**Guard rail aggiuntivo**: se `min(per_dim) ≤ 0.0` per dimensione con `weight ≥ 0.15`, abbassare confidence overall di 0.10 (segnale "dimensione critica mancante").

**Test**: scenario partial-coverage Gate 1+2-only su `ML_LIB` → confidence < 0.4 (vs 0.55 con avg semplice).

---

### T2.3 — Confidence per-dimensione variabile

**Stato**: `_SOURCE_CONFIDENCE["gate12_derived"] = 0.4` costante.

**Azione**:
```python
# scoring/confidence.py
_DIMENSION_CONFIDENCE_FROM_GATE12: dict[ScoreDimension, float] = {
    ScoreDimension.TESTING: 0.55,        # mapping forte (test_footprint diretto)
    ScoreDimension.MAINTENANCE: 0.50,
    ScoreDimension.SECURITY: 0.50,
    ScoreDimension.DOCUMENTATION: 0.40,
    ScoreDimension.CODE_QUALITY: 0.40,   # post T2.1: include complexity + test
    ScoreDimension.ARCHITECTURE: 0.0,    # mapping vuoto (T2.1)
    ScoreDimension.FUNCTIONALITY: 0.0,
    ScoreDimension.INNOVATION: 0.0,
}
```

`compute_dimension_confidence` usa la mappa quando `source == "gate12_derived"`, altrimenti il default `_SOURCE_CONFIDENCE`.

---

### T2.4 — Heuristic fallback come "ignorance signal"

**Stato**: `assessment/heuristics.py` ritorna point estimate fino a 1.0 con confidence implicita alta.

**Azione**: nuova classe in `assessment/types.py`:
```python
class HeuristicFallback(BaseModel):
    point_estimate: float = Field(default=0.5, ge=0.0, le=1.0)
    uncertainty_range: tuple[float, float] = Field(default=(0.3, 0.7))
    confidence: float = Field(default=0.15, ge=0.0, le=0.25)  # explicitly capped low
    presence_signals: dict[str, bool] = Field(default_factory=dict)
    note: str = "LLM unavailable; heuristic fallback only — interpret with caution"
```

`HeuristicAnalyzer.score()` ritorna `HeuristicFallback`. L'orchestrator marca `DeepAssessmentResult.degraded = True` quando il fallback kicks in.

**Acceptance**: 20 repo con LLM disabled → tutti `confidence < 0.25`, `degraded=True`, score range visibile in CLI.

---

### T2.5 — Path-based detection in heuristics

**Stato**: `assessment/heuristics.py:23-30` — `_TEST_PATTERNS` come substring case-insensitive sul packed content. Falsi positivi: README "we use pytest", `latest_release` matcha "test" come substring? (no: `pytest` matcha solo se literal `pytest` presente, ma `pytestplugin` matcha)

**Azione**: parsing del file tree dal packed content (repomix include header `==== file: src/foo/bar.py ====`):
```python
def _extract_file_paths(packed: str) -> list[str]:
    return re.findall(r"^=+\s*file:\s*(\S+)", packed, re.MULTILINE)

def has_test_dir(file_paths: list[str]) -> bool:
    test_dirs = {"tests", "test", "__tests__", "spec", "specs"}
    return any(
        Path(p).parts[0] in test_dirs or
        any(part in test_dirs for part in Path(p).parts)
        for p in file_paths
    )
```

**Test fixture**: pacchetto con `README.md` che cita "pytest" e nessun file di test → `has_test_dir() == False`.

---

## 7) Wave 3 — Robustness & Resource Safety (P1)

### T3.1 — Distinzione errori in `_fetch()`

**Azione**: nuove eccezioni in `exceptions.py` (rispettare regola CLAUDE.md "no bare Exception"):
```python
class GitHubFetchError(GitHubDiscoveryError): ...
class GitHubAuthError(GitHubFetchError): ...
class GitHubRateLimitError(GitHubFetchError):
    def __init__(self, retry_after: int | None = None) -> None:
        super().__init__("rate limited")
        self.retry_after = retry_after
class GitHubServerError(GitHubFetchError): ...
```

Refactor `_fetch()` per mappare status code → eccezione tipata (vedi audit Claude §B1.2 per snippet completo).

**Caller behavior**:
- Gate 1 sub-score: cattura `GitHubAuthError`/`GitHubRateLimitError` → marca dimension `degraded` (NON 0.0), propaga warning.
- Gate 1 orchestrator: aggrega n. degraded sub-scores, espone in `MetadataScreenResult.degraded_count`.

---

### T3.2 — Tenacity retry+backoff

**Context7 verify**: `tenacity` v8.x: `@retry(stop=stop_after_attempt(N), wait=wait_exponential_jitter(initial=1, max=30), retry=retry_if_exception_type((GitHubRateLimitError, GitHubServerError)))`.

**Azione**: applicare a `_fetch()` con max 3 attempt, jittered exponential backoff. Honor `Retry-After` header se presente.

**Acceptance**: test mock `httpx` ritorna 429 due volte poi 200 → `_fetch` ritorna successo dopo 2 retry.

---

### T3.3 — Orphan temp dir cleanup

**Azione**: in `screening/clone_manager.py` (o equivalente), aggiungere helper:
```python
def cleanup_orphan_clones(prefix: str = "ghdisc_clone_", max_age_hours: float = 6.0) -> int:
    pattern = f"{prefix}*"
    cutoff = time.time() - max_age_hours * 3600
    removed = 0
    for path in Path(tempfile.gettempdir()).glob(pattern):
        try:
            if path.stat().st_mtime < cutoff:
                shutil.rmtree(path, ignore_errors=True)
                removed += 1
        except OSError:
            continue
    return removed
```

Chiamare in `workers/__init__.py` (o lifecycle hook FastAPI/MCP server) all'avvio.

---

### T3.4 — LLM provider lifecycle

**Stato**: `_ensure_provider()` lazy-init senza chiusura esplicita.

**Azione**: pattern context manager:
```python
class NanoGPTProvider:
    async def __aenter__(self) -> NanoGPTProvider:
        self._client = AsyncOpenAI(api_key=..., base_url=...)
        return self
    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.close()
```

Orchestrator usa `async with provider:` o registra cleanup in `lifespan` FastAPI / `mcp.server` shutdown hook.

**Context7 verify**: `httpx.AsyncClient` requires explicit `aclose()`; `openai.AsyncOpenAI` wraps it.

---

### T3.5 — FeatureStore TTL + `ghdisc db prune`

**Azione**:
1. Migration SQLite: aggiungere colonna `expires_at TIMESTAMP` a `score_results`.
2. `FeatureStore.put()` setta `expires_at = now() + ttl_seconds` (default 30 giorni configurable).
3. `FeatureStore.get()` filtra `WHERE expires_at > datetime('now')`.
4. Nuovo comando `cli/db.py`: `ghdisc db prune [--dry-run]` → `DELETE FROM score_results WHERE expires_at < datetime('now')`.

---

### T3.6 — Cross-domain z-score skip se N<3

**Stato**: `scoring/cross_domain.py` ha fallback `std=0.1` per N=1.

**Azione**:
```python
def _normalize_scores(self, scores_per_domain: dict[DomainType, list[float]]) -> ...:
    for domain, scores in scores_per_domain.items():
        if len(scores) < 3:
            # Insufficient sample — pass through, mark cross_domain_confidence=0
            continue
        mean = statistics.mean(scores)
        std = statistics.stdev(scores)
        if std < 0.05:  # near-uniform domain
            continue
        ...
```

Espone `cross_domain_confidence: float` per repo (0 se non normalizzato).

---

### T3.7 — Eliminare normalizzazione duplicata `value_score`

**Stato**: `value_score.normalize_batch()` esiste ma `value_score == quality_score`. Doppia normalizzazione.

**Azione**: rimuovere `normalize_batch` da `ValueScoreCalculator`. Documentare in changelog. Mantenere `value_score` come computed_field alias di `quality_score` (backward compat).

---

## 8) Wave 4 — Empirical Calibration (P0 metodologico)

Wave parallelizzabile rispetto a Wave 1–3 (effort esterno: labeling). Sblocca tutti i claim "qualitativi" del progetto.

### T4.1 — Golden dataset (200 repo cross-domain)

**Sample design**:
- 200 repo, stratificato per:
  - 12 domini (~15 repo/dominio, min 10 max 25)
  - Star bucket: 25% `<50`, 25% `50-499`, 25% `500-4999`, 25% `5000+`
  - Linguaggio: Python, JS/TS, Rust, Go, Java (≥20 ciascuno)
- Repo selezionati da: GitHub Trending (last year), awesome lists curate, hidden gem suggestion da maintainer noti, random sample da BigQuery `githubarchive`.

**Output**: `tests/feasibility/golden_dataset.json`:
```json
[
  {
    "full_name": "owner/repo",
    "commit_sha": "...",
    "domain": "ML_LIB",
    "language": "Python",
    "stars_at_label": 1234,
    "ratings": [
      {"rater_id": "r1", "code_quality": 4, "architecture": 3, ..., "innovation": 5, "notes": "..."},
      {"rater_id": "r2", ...},
      {"rater_id": "r3", ...}
    ]
  }, ...
]
```

### T4.2 — Inter-rater agreement (Cohen's κ ≥ 0.6)

3 rater senior con guidelines scritte (`docs/foundation/labeling_guidelines.md`). Scala 1–5 per ognuna delle 8 dimensioni. Cohen's κ pairwise + Fleiss' κ multi-rater.

**Acceptance**: κ ≥ 0.6. Se < 0.6, refinement guidelines + relabel subset.

**Output**: `docs/foundation/calibration_report.md` con κ table, distribuzione rating, esempi disagreement risolti.

### T4.3 — Calibrazione weight per dominio

**Approccio**: per ogni dominio (≥15 repo), grid search / Bayesian optimization su `dimension_weights` per massimizzare correlazione (Spearman) tra `quality_score` predetto e `mean_expert_rating`. Vincolo: somma weight = 1.0.

**Hold-out**: 20% del dataset (40 repo) come test set. NDCG@10 ≥ 0.75 sul hold-out.

**Output**: nuovo `scoring/profiles.py` con weights data-driven. Legacy weights mantenuti come `_LEGACY_PROFILES` per A/B test.

### T4.4 — Baseline comparison

Eseguire pipeline GitHub Discovery + 4 baseline su golden dataset:
1. Random shuffle (sanity check)
2. Star-only ranking (`sort by -stars`)
3. OpenSSF Scorecard composite
4. GitHub trending order (per categoria)

Metriche: NDCG@10, NDCG@25, Spearman vs expert ranking, Pairwise Accuracy.

**Significatività**: Wilcoxon signed-rank, p < 0.05 vs star-only baseline.

**Acceptance**: GitHub Discovery batte star-only su NDCG@10 con p<0.05. Output: `docs/foundation/benchmark_report.md`.

---

## 9) Wave 5 — Architectural Refactor (P2)

### T5.1 — `_DERIVATION_MAP` per-DomainProfile

**Azione**: aggiungere campo opzionale a `DomainProfile`:
```python
class DomainProfile(BaseModel):
    ...
    derivation_map: dict[ScoreDimension, list[tuple[str, float]]] | None = Field(
        default=None,
        description="Per-domain derivation override; None = use default",
    )
```

`ScoringEngine._derive_from_screening()` usa `profile.derivation_map or _DEFAULT_DERIVATION_MAP`.

**Beneficio**: ML_LIB può sovrascrivere `CODE_QUALITY` con peso maggiore su `complexity`; CLI_TOOL può enfatizzare `test_footprint`.

### T5.2 — `gate_thresholds` per-DomainProfile

`DomainProfile.gate_thresholds` esiste già (`models/scoring.py:53`) ma `_DOMAIN_THRESHOLDS` orchestrator-level li sovrascrive. Rimuovere il duplicato, propagare solo da profilo.

### T5.3 — `custom_profiles_path`

**Azione**:
1. Implementare `ProfileRegistry.load_from_yaml(path: Path)` che parsa file YAML con schema validato.
2. Validare somma weights = 1.0; warn se profilo custom usa dimensioni non note.
3. CLI: `ghdisc profiles list`, `ghdisc profiles show <domain>`, `ghdisc profiles validate <path>`.

### T5.4 — *Opzionale*: rimuovere `is_hidden_gem` da `ScoreResult`

Discussione necessaria (deprecation breaking change). Se accettato, esposizione solo via `ValueScoreCalculator.is_hidden_gem`. Update consumer (MCP tools, API routes, CLI rendering).

### T5.5 — Property-based test (Hypothesis)

**Context7 verify**: `hypothesis` strategies (`floats`, `integers`, `dictionaries`, `lists`).

**Test invarianti**:
```python
@given(
    sub_scores=st.dictionaries(
        keys=st.sampled_from(SUB_SCORE_NAMES),
        values=st.floats(min_value=0.0, max_value=1.0),
        min_size=4, max_size=11,
    ),
    domain=st.sampled_from(list(DomainType)),
)
def test_score_in_range(sub_scores, domain):
    result = engine.score(make_candidate(domain), make_screening(sub_scores))
    assert 0.0 <= result.quality_score <= 1.0
    assert 0.0 <= result.confidence <= 1.0
    assert 0.0 <= result.coverage <= 1.0

@given(...)
def test_monotonicity(sub_scores, dim_to_increase):
    """Aumentare un sub-score (a parità altri) non diminuisce quality_score."""
    base_result = engine.score(make_candidate(), make_screening(sub_scores))
    boosted = {**sub_scores, dim_to_increase: min(1.0, sub_scores[dim_to_increase] + 0.1)}
    new_result = engine.score(make_candidate(), make_screening(boosted))
    assert new_result.quality_score >= base_result.quality_score - 1e-9

@given(profile=st.sampled_from(list(ALL_PROFILES)))
def test_profile_weights_sum_to_one(profile):
    assert abs(sum(profile.dimension_weights.values()) - 1.0) < 1e-9
```

---

## 10) Sequenza di implementazione

### Settimana 1 — Critical bugs e setup
- T1.1, T1.2, T1.4 (in parallelo, indipendenti)
- T1.3 dopo T1.1 (richiede aggiornamento `ScoreResult`)
- Avvio T4.1: definizione sample design, recruiting rater

### Settimana 2 — Scoring logic hardening
- T2.1 (riprogetta `_DERIVATION_MAP` + `SCORING_METHODOLOGY.md`)
- T2.2, T2.3, T2.4, T2.5 (in parallelo dopo T2.1)
- T5.5 (property-based test, sblocca regression check)
- T4.1 in corso (labeling esterno)

### Settimana 3 — Robustness
- T3.1, T3.2 (sequenziali)
- T3.3, T3.4, T3.5, T3.6, T3.7 (in parallelo)
- T4.2 conclude (κ report)

### Settimana 4 — Calibrazione + refactor
- T4.3, T4.4 (calibrazione + benchmark)
- T5.1, T5.2 (derivation/threshold per-profile)
- Decisione su T5.4 (deprecation `is_hidden_gem` model field)

### Settimana 5 (buffer) — T5.3, polish, docs

### Settimana 6 (buffer) — Release v0.2.0-beta, blog post, tag

---

## 11) Test plan

| Categoria | Aggiunte | Esistenti | Note |
|-----------|----------|-----------|------|
| Unit (scoring) | +50 (consistency, coverage, derivation, confidence weighted) | preserved | mantenere 1326 verdi |
| Property-based (Hypothesis) | +15 (T5.5) | 0 | nuovo |
| Integration (E2E, real fixture) | +5 (LLM-disabled, multi-domain coverage) | preserved | |
| Regression (cross-process determinism) | +3 (subprocess test su `_seeded_hash`, ranking) | 0 | nuovo |
| Feasibility (golden dataset) | +N (calibration validation) | Phase 9 mock | parzialmente sostituisce |

**Coverage target**: scoring/screening modules ≥ 90% line coverage. Mantain `make ci` verde.

---

## 12) Criteri di accettazione

Phase 2 completa quando **tutti** i seguenti sono soddisfatti:

1. ✅ Single source of truth per `hidden_gem`: 0 occorrenze di `_HIDDEN_GEM_*` fuori da test.
2. ✅ Ranking deterministico: 5 run su pool di 50 repo → ordering identico bit-perfect (cross-process).
3. ✅ `coverage` field esposto in API/CLI/MCP/`ExplainabilityReport`.
4. ✅ `_DERIVATION_MAP` v2 documentato in `SCORING_METHODOLOGY.md` con citazioni.
5. ✅ Confidence pesata dai profile weights; per-dimensione variabile.
6. ✅ Heuristic fallback: confidence ≤ 0.25, `degraded=True` flag visibile.
7. ✅ Errori GitHub API tipizzati (auth/rate-limit/network/server) + retry tenacity.
8. ✅ Orphan clone cleanup attivo all'avvio worker.
9. ✅ FeatureStore TTL + `ghdisc db prune` CLI.
10. ✅ Property-based test su scoring (≥1000 generated cases passano).
11. ✅ Golden dataset 200 repo, Cohen's κ ≥ 0.6, calibration report pubblicato.
12. ✅ NDCG@10 sul hold-out ≥ 0.75; baseline benchmark con p<0.05 vs star-only.
13. ✅ `make ci` verde; mypy --strict 0 errori; ruff 0 errori.
14. ✅ Wiki aggiornata: `anti-star-bias.md`, `scoring-dimensions.md`, `screening-gates.md` riflettono i cambiamenti.
15. ✅ Release notes `CHANGELOG.md` per v0.2.0-beta complete.

---

## 13) Rischi e mitigazioni

| Rischio | Probabilità | Impatto | Mitigazione |
|---------|-------------|---------|-------------|
| T2.1 introduce regressioni significative su quality_score | Media | Alto | Ablation test su 20 fixture pre-merge; release behind feature flag `scoring_v2` con fallback al vecchio mapping |
| T4.1 labeling rater richiede più di 2 settimane | Alta | Medio | Avviare in parallelo a Wave 1; budget esterni se necessario; ridurre a 150 repo se time-boxed |
| Cohen's κ < 0.6 al primo round | Media | Medio | Refinement guidelines + relabel subset disagreement; coinvolgere 4° rater come tiebreaker |
| Calibrazione T4.3 produce weights con NDCG < 0.75 | Media | Alto | Iterazione: revisione `_DERIVATION_MAP`; estendere dataset; accettare 0.70 come MVP con commitment a iterazione |
| Hidden gem dual-source rimozione rompe consumer downstream | Bassa | Medio | Deprecation warning per 1 release prima di rimuovere `ScoreResult.is_hidden_gem`; tests su MCP tools, CLI, API |
| Tenacity retry su 429 amplifica rate limit storm | Bassa | Alto | Honor `Retry-After`; circuit breaker globale (`pybreaker`) opzionale |
| Coverage damping abbassa troppo i quality score storici | Media | Medio | Esporre `raw_quality_score` per backward compat; gradient damping (`0.5 + 0.5*coverage` invece di `coverage` lineare) |

---

## 14) Verifica Context7 e wiki cross-references

**Context7** (richiesto da CLAUDE.md): prima di implementare ogni task, eseguire query su `mcp__plugin_context7_context7__resolve-library-id` + `query-docs` per:

| Libreria | Tema verificato | Task |
|----------|-----------------|------|
| `pydantic` v2 | `Field(ge, le)`, `computed_field`, `model_validator`, JSON-compat dict types | T1.4, T1.3 |
| `pydantic-settings` v2 | `BaseSettings`, `SettingsConfigDict(extra='ignore')`, env var loading | T1.1, T5.3 |
| `hashlib` (stdlib) | `blake2b(digest_size=8)`, deterministic across CPython versions | T1.2 |
| `tenacity` v8 | `@retry`, `wait_exponential_jitter`, `retry_if_exception_type`, `stop_after_attempt` | T3.2 |
| `httpx` AsyncClient | `aclose()` lifecycle, response status_code mapping | T3.1, T3.4 |
| `openai` AsyncOpenAI | `close()`, retry config, async context | T3.4 |
| `hypothesis` | `@given`, strategies (`floats`, `integers`, `dictionaries`, `sampled_from`), shrinking | T5.5 |
| `structlog` | bound logger, context vars, JSON renderer (per error logging T3.1) | T3.1 |
| `typer` | sub-command groups (`ghdisc db prune`, `ghdisc profiles list`) | T3.5, T5.3 |
| `pytest` | parametrize, fixtures, markers (`integration`, `slow`), tmp_path | tutti |

**Wiki cross-references** (richiesto da CLAUDE.md): aggiornare/creare al termine di ogni Wave:

| File wiki | Wave | Sezione da aggiornare/creare |
|-----------|------|------------------------------|
| `architecture/anti-star-bias.md` | W1, W5 | "Hidden Gem Detection" → riflette single source threshold |
| `architecture/tiered-pipeline.md` | W2 | "Coverage and confidence" sezione nuova |
| `domain/scoring-dimensions.md` | W2 | "Derivation Map v2" + tabella |
| `domain/screening-gates.md` | W3 | "Error handling and degraded mode" sezione nuova |
| `patterns/operational-rules.md` | W3 | "Retry/backoff policy" |
| `patterns/phase5-scoring-implementation.md` | W1–W5 | snapshot di stato a fine Phase 2 |
| `architecture/phase2-remediation.md` *(nuovo)* | tutti | log delle decisioni di remediation |

**Foundation docs** (nuovi):
- `docs/foundation/SCORING_METHODOLOGY.md` (T2.1)
- `docs/foundation/labeling_guidelines.md` (T4.1)
- `docs/foundation/calibration_report.md` (T4.2)
- `docs/foundation/benchmark_report.md` (T4.4)

---

## 15) Out of scope

Esplicitamente **non** affrontati in Phase 2 (rimandati a Phase 3+):

- Redis cache layer (Phase 3 — scaling multi-worker)
- PyDriller integration per Gate 1 maintenance (mantenere API heuristics, confidence 0.7)
- OSV adapter lockfile parsing reale (mantenere stub neutral)
- Public MCP server hosting (Phase 4 — go-to-market)
- Multi-rater feedback loop in produzione (continuous calibration) — Phase 4
- Per-language quality benchmarks separati (Python/JS/Rust/Go/Java) — Phase 4
- Performance tuning P95 < 60s end-to-end — Phase 4
- Custom dimension registry (oltre alle 8 standard) — Phase 4
- ARCHITECTURE proxy via dependency-graph clustering — research, Phase 4
- A/B testing infrastructure per profile weights — Phase 4

---

**Fine Phase 2 Implementation Plan.**
