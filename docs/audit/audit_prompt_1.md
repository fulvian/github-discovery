# Audit Prompt — GitHub Discovery v0.1.0-alpha

> **Tipo di audit**: Completo e severo — qualità del codice, correttezza logica, e soprattutto qualità della logica di valutazione e ranking.  
> **Target**: LLM avanzati (Claude, GPT-4o, Gemini, DeepSeek, etc.) per raccolta analisi indipendenti.  
> **Data**: 2026-04-26  
> **Versione progetto**: v0.1.0-alpha — 118+ source files, 1326 tests passing, 0 lint/type errors.
> **Repository**: https://github.com/fulvian/github-discovery

---

## Istruzioni per l'LLM Auditore

Sei un **Senior Software Architect e Domain Expert** in sistemi di valutazione della qualità del software. Devi condurre un audit severo, indipendente e approfondito del progetto **GitHub Discovery**, un engine MCP-native che scopre repository GitHub di alta qualità indipendentemente dalla popolarità (stars).

Il tuo audit deve essere **critico, costruttivo e concreto**. Non limitarti a descrivere il codice — identifica problemi reali, proponi soluzioni specifiche, e valuta la solidità teorica e pratica della logica di scoring.

**ATTENZIONE**: Questo audit è particolarmente focalizzato sulla **qualità e correttezza della logica di valutazione e ranking**. La qualità del codice Python è importante, ma la priorità assoluta è la validità del modello di scoring come sistema di valutazione della qualità del software.

---

## 1. Contesto del Progetto

### 1.1 Obiettivo

GitHub Discovery è un sistema che valuta la qualità tecnica dei repository GitHub attraverso una pipeline a 4 gate progressivi:

```
Gate 0 (Discovery) → Gate 1 (Metadata Screening) → Gate 2 (Static/Security) → Gate 3 (LLM Deep Assessment) → Ranking
```

Il principio fondamentale è **star-neutral**: le stelle GitHub sono solo metadati di corroborazione, MAI un segnale di scoring primario. Il `quality_score` è un puro assessment tecnico da Gate 1+2+3.

### 1.2 Architettura della Pipeline

| Gate | Livello | Costo | Input | Output |
|------|---------|-------|-------|--------|
| **Gate 0** | Discovery | API calls | Query utente | Pool di candidati |
| **Gate 1** | Metadata Screening | Zero LLM | Metadati GitHub API | 7 sub-scores (hygiene, maintenance, CI/CD, test footprint, release discipline, review practices, dependency quality) |
| **Gate 2** | Static/Security | Zero/low | Shallow clone + API esterne | 4 sub-scores (OpenSSF Scorecard, OSV vulnerabilities, gitleaks secrets, scc complexity) |
| **Gate 3** | Deep Assessment | Alto (LLM) | Repo pack via repomix | 8 dimension scores (code_quality, architecture, testing, documentation, maintenance, security, functionality, innovation) |
| **Ranking** | Layer D | Zero | ScoreResult per repo | RankedRepo list, hidden gems, explainability reports |

**Hard rule**: Nessun candidato può raggiungere Gate 3 senza aver passato Gate 1 + Gate 2.

### 1.3 Struttura del Codice Sorgente

```
src/github_discovery/
├── config.py                    # Settings (GHDISC_* env prefix, pydantic-settings)
├── exceptions.py                # Custom exception hierarchy
├── models/
│   ├── enums.py                 # DomainType (12), ScoreDimension (8), GateLevel, etc.
│   ├── candidate.py             # RepoCandidate, CandidatePool
│   ├── screening.py             # SubScore, MetadataScreenResult, StaticScreenResult, ScreeningResult
│   ├── assessment.py            # DimensionScore, DeepAssessmentResult
│   └── scoring.py               # ScoreResult, DomainProfile, RankedRepo, ExplainabilityReport
├── discovery/                   # Gate 0: 6 channels, orchestrator, pool manager
├── screening/                   # Gate 1+2: 7 Gate1 checkers, 4 Gate2 adapters, orchestrator
├── assessment/                  # Gate 3: LLM provider, 8 dimension prompts, repomix, heuristics
├── scoring/                     # Layer D: engine, profiles, ranker, confidence, value_score, explainability
├── mcp/                         # MCP server: 16 tools, 4 resources, 5 prompts
├── cli/                         # CLI: typer + rich, 6 pipeline commands
├── api/                         # FastAPI REST (secondary interface)
└── workers/                     # Background workers
```

---

## 2. Codice da Analizzare

Di seguito il codice critico da auditare. Analizza ogni modulo in dettaglio, non limitarti a una lettura superficiale.

### 2.1 Scoring Engine (`scoring/engine.py`)

```python
# Mappa derivazione dimensioni da Gate 1+2 sub-scores
_DERIVATION_MAP: dict[ScoreDimension, list[tuple[str, float]]] = {
    ScoreDimension.CODE_QUALITY: [
        ("review_practice", 0.5),
        ("ci_cd", 0.3),
        ("dependency_quality", 0.2),
    ],
    ScoreDimension.ARCHITECTURE: [
        ("complexity", 0.7),
        ("ci_cd", 0.3),
    ],
    ScoreDimension.TESTING: [
        ("test_footprint", 0.7),
        ("ci_cd", 0.3),
    ],
    ScoreDimension.DOCUMENTATION: [
        ("hygiene", 0.6),
        ("review_practice", 0.4),
    ],
    ScoreDimension.MAINTENANCE: [
        ("maintenance", 0.4),
        ("release_discipline", 0.3),
        ("ci_cd", 0.2),
        ("hygiene", 0.1),
    ],
    ScoreDimension.SECURITY: [
        ("security_hygiene", 0.35),
        ("vulnerability", 0.25),
        ("secret_hygiene", 0.25),
        ("dependency_quality", 0.15),
    ],
    ScoreDimension.FUNCTIONALITY: [],   # Cannot be derived from Gate 1+2
    ScoreDimension.INNOVATION: [],       # Cannot be derived from Gate 1+2
}

# Calcolo score composito — le dimensioni con confidence 0.0 sono escluse
def _apply_weights(self, dimension_scores, profile):
    weighted_sum = 0.0
    total_weight = 0.0
    for dim, info in dimension_scores.items():
        weight = profile.dimension_weights.get(dim, 0.0)
        if info.confidence <= 0.0:  # Skip neutral defaults
            continue
        weighted_sum += info.value * weight
        total_weight += weight
    if total_weight <= 0.0:
        return 0.0
    return weighted_sum / total_weight
```

### 2.2 Confidence Calculator (`scoring/confidence.py`)

```python
_SOURCE_CONFIDENCE: dict[str, float] = {
    "gate3_llm": 0.8,
    "gate12_derived": 0.4,
    "default_neutral": 0.0,
}

_GATE_COVERAGE_BONUS = {
    "gate1_only": 0.0,
    "gate1_gate2": 0.05,
    "gate1_gate2_gate3": 0.10,
}

def compute(self, dimension_infos, screening, assessment):
    dim_confidences = [self.compute_dimension_confidence(...) for info in dimension_infos.values()]
    avg_confidence = sum(dim_confidences) / len(dim_confidences)
    bonus = self.gate_coverage_bonus(screening, assessment)
    total = avg_confidence + bonus
    return max(0.0, min(1.0, total))
```

### 2.3 Ranker (`scoring/ranker.py`)

```python
def _sort_key(self, result: ScoreResult) -> tuple[float, float, int, str]:
    """Star-neutral sort key."""
    seeded_hash = hash((self._settings.ranking_seed, result.full_name))
    return (-result.quality_score, -result.confidence, -seeded_hash, result.full_name)

def _identify_hidden_gems(self, ranked, domain):
    """Hidden gem = informational label, NOT a score modifier."""
    # Criteria: stars < threshold, quality >= min_quality, quality in top 25%
    # With <4 repos: top_25_q = 0.0 (no percentile filter)
```

### 2.4 Value Score (`scoring/value_score.py`)

```python
def compute(self, quality_score: float, stars: int) -> float:
    """Star-neutral: value_score = quality_score."""
    _ = stars  # explicitly unused
    return max(quality_score, 0.0)

def is_hidden_gem(self, quality_score, stars, value_score) -> tuple[bool, str]:
    """Informational label only."""
    if quality_score < self._hidden_gem_min_quality:
        return (False, "Quality below threshold")
    if stars >= self._hidden_gem_star_threshold:
        return (False, "Stars at or above threshold")
    return (True, f"High quality ({quality_score:.2f}) with low visibility ({stars} stars)")
```

### 2.5 ScoreResult Model (`models/scoring.py`)

```python
class ScoreResult(BaseModel):
    quality_score: float = Field(ge=0.0, le=1.0)
    dimension_scores: dict[ScoreDimension, float]
    confidence: float = Field(ge=0.0, le=1.0)
    stars: int = Field(ge=0, description="Star count — metadata, not used in quality scoring")
    
    @computed_field
    @property
    def corroboration_level(self) -> str:
        if self.stars == 0: return "new"
        if self.stars < 50: return "unvalidated"
        if self.stars < 500: return "emerging"
        if self.stars < 5000: return "validated"
        return "widely_adopted"
    
    @computed_field
    @property
    def is_hidden_gem(self) -> bool:
        return self.quality_score >= 0.5 and self.stars < 100
    
    @computed_field
    @property
    def value_score(self) -> float:
        return self.quality_score  # Star-neutral
```

### 2.6 Domain Profiles (`scoring/profiles.py` + `models/scoring.py`)

12 domain profiles, ognuno con 8 dimension weights che sommano a 1.0. Esempio:

```python
LIBRARY_PROFILE = DomainProfile(
    dimension_weights={
        CODE_QUALITY: 0.20, ARCHITECTURE: 0.15, TESTING: 0.15,
        DOCUMENTATION: 0.15, MAINTENANCE: 0.15, SECURITY: 0.10,
        FUNCTIONALITY: 0.05, INNOVATION: 0.05,
    },
    star_baseline=500.0,
)

ML_LIB_PROFILE = DomainProfile(
    dimension_weights={
        CODE_QUALITY: 0.10, ARCHITECTURE: 0.10, TESTING: 0.10,
        DOCUMENTATION: 0.10, MAINTENANCE: 0.15, SECURITY: 0.05,
        FUNCTIONALITY: 0.25, INNOVATION: 0.15,
    },
    star_baseline=2000.0,
)
```

### 2.7 Gate 1 Screening (`screening/gate1_metadata.py`)

7 sub-score checkers, ognuno con weight default 1.0:
- **HygieneScore**: LICENSE (SPDX validation), README, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY.md, CHANGELOG
- **MaintenanceScore**: commit recency (30/90/180/365 days), cadence (7/30/90 days), bus factor (2/3/5 authors), issue resolution rate
- **CiCdScore**: GitHub Actions presence, workflow count, CI badge, coverage reporting
- **TestFootprintScore**: test directories, frameworks, test/source ratio, conftest.py
- **ReleaseDisciplineScore**: semver tags, release count, cadence, changelog per release
- **ReviewPracticeScore**: PR template, review rate, label usage, response latency
- **DependencyQualityScore**: lockfile presence, pinning ratio, dependabot/renovate config

Composite: `gate1_total = sum(value * weight) / sum(weight)` per tutti i 7 sub-scores.

### 2.8 Gate 2 Screening (`screening/gate2_static.py`)

4 sub-score checkers:
- **OpenSSF Scorecard API** (HTTP)
- **OSV Vulnerability API** (HTTP)
- **gitleaks** (subprocess su shallow clone)
- **scc** (subprocess per LOC/complexity)

Graceful degradation: tool failures → fallback score 0.3, confidence 0.0.

### 2.9 Gate 3 Deep Assessment (`assessment/orchestrator.py`)

Pipeline: Hard Gate Check → Cache Check → Budget Check → Repomix Pack → Heuristic Scoring → LLM Assessment → Result Composition.

LLM assessment usa NanoGPT (OpenAI-compatible) + instructor per structured output. 8 dimension prompts con domain-specific focus adjustments. Batch mode (1 LLM call) o per-dimension mode (8 LLM calls).

### 2.10 Heuristic Analyzer (`assessment/heuristics.py`)

Scoring additivo per fallback:
- Has tests: +0.2
- Has CI: +0.2
- Has docs: +0.15
- Has security policy: +0.15
- File count in reasonable range (10-500): +0.15
- Has src/ or lib/: +0.15

### 2.11 Cross-Domain Guard (`scoring/cross_domain.py`)

Normalizzazione z-score per confronti cross-domain:
`normalized = (quality_score - domain_mean) / domain_std + 0.5`

### 2.12 Hidden Gem Thresholds (config)

```python
hidden_gem_star_threshold: int = 500     # Max stars
hidden_gem_min_quality: float = 0.7       # Min quality_score
```

Ma in `models/scoring.py`:
```python
_HIDDEN_GEM_MAX_STARS = 100
_HIDDEN_GEM_MIN_QUALITY = 0.5
```

**Domanda per l'audit**: Questa divergenza è un bug o è intenzionale? Qual è il comportamento effettivo?

---

## 3. Aree di Audit

### SEZIONE A: Logica di Valutazione e Ranking (PRIORITÀ MASSIMA)

Questa è la sezione più importante dell'audit. Valuta criticamente ogni aspetto della logica di scoring.

#### A1. Validità del Modello di Scoring

- **Correttezza della derivazione Gate 1+2 → Dimension Scores**: Il `_DERIVATION_MAP` nell'engine mappa sub-scores di Gate 1/2 alle 8 dimensioni di scoring. È questo mapping logicamente corretto? `CODE_QUALITY` è derivato da `(review_practice=0.5, ci_cd=0.3, dependency_quality=0.2)` — ha senso? `ARCHITECTURE` da `(complexity=0.7, ci_cd=0.3)` — l'architettura è davvero il 70% complessità?
- **FUNCTIONALITY e INNOVATION** non possono essere derivati da Gate 1+2 (mapping vuoto). Questo significa che ricevono sempre il default neutro (0.5, confidence=0.0) a meno che Gate 3 non sia eseguito. È questo corretto? Qual è l'impatto sul quality_score composito dato che queste dimensioni hanno pesi dal 5% al 25% a seconda del dominio?
- **Esclusione delle dimensioni default**: Il calcolo del quality_score esclude le dimensioni con confidence ≤ 0.0 (i default neutral) e redistribuisce il peso. Questo è un buon approccio? Cosa succede se un repo ha solo Gate 1 (7 sub-scores) ma nessun Gate 3 — quante dimensioni rimangono effettivamente nel calcolo?

#### A2. Coerenza del Calcolo Composite

- **Weight redistribution**: Quando le dimensioni con confidence 0.0 sono escluse, il peso viene redistribuito implicitamente (dividendo per `total_weight` ridotto). È questo un approccio corretto? Quali sono le conseguenze quando molte dimensioni sono escluse?
- **Interazione Gate 1+2 vs Gate 3**: Un repo con solo Gate 1+2 avrà confidence 0.4 per le dimensioni derivabili e 0.0 per FUNCTIONALITY/INNOVATION. Un repo con Gate 3 completo avrà confidence 0.8 per tutte. Questo crea un gap significativo nel quality_score — è desiderabile?
- **Sub-score weights in Gate 1**: Tutti i sub-scores di Gate 1 hanno `weight: float = 1.0` (default). Significa che hygiene ha lo stesso peso di CI/CD e test_footprint. È questo appropriato?

#### A3. Confidence Model

- **Valori hardcoded**: `_SOURCE_CONFIDENCE = {"gate3_llm": 0.8, "gate12_derived": 0.4, "default_neutral": 0.0}`. Sono questi valori giustificati? Da dove derivano?
- **Gate coverage bonus**: `{gate1_only: 0.0, gate1_gate2: 0.05, gate1_gate2_gate3: 0.10}`. Il bonus è additivo alla media delle confidence per-dimensione. Può questo portare a confidence > 1.0 per repo con Gate 3 completo? (È clamped a [0.0, 1.0], ma è il range ragionevole?)
- **Average vs min confidence**: La confidence calcolata come media delle dimension confidences. Sarebbe più prudente usare il minimo? O una media pesata?

#### A4. Ranking e Tie-Breaking

- **Sort key**: `(-quality_score, -confidence, -seeded_hash, full_name)`. L'uso di `seeded_hash` per tie-breaking è deterministico? `hash()` in Python è randomizzato per processo (PYTHONHASHSEED) — il seed settings garantisce riproducibilità cross-session?
- **Hidden gem identification**: Il threshold top-25% è calcolato con `sorted_qs[max(1, len(sorted_qs) // 4) - 1]`. È corretto per pool piccole (<4 repos il threshold diventa 0.0)?
- **Star-neutral design**: La decisione di rendere `value_score = quality_score` elimina completamente l'influenza delle stelle. È questo troppo estremo? Ci sono scenari dove le stelle dovrebbero avere un ruolo informativo nel ranking?

#### A5. Threshold e Configurazione

- **Gate 1 threshold (0.4)**: È troppo permissivo? Un repo con 4/7 hygiene files, CI assente, e nessun test potrebbe passare?
- **Gate 2 threshold (0.5)**: Con graceful degradation (fallback 0.3 per tool failures), un repo dove tutti i tool falliscono riceve 0.3 × 4 / 4 = 0.3 < 0.5 → fails. Ma se solo 1-2 tool falliscono?
- **Gate 3 threshold (0.6)**: È appropriato? Troppo alto? Troppo basso?
- **Hidden gem thresholds divergenza**: `ScoringSettings.hidden_gem_star_threshold=500` vs `_HIDDEN_GEM_MAX_STARS=100` in `models/scoring.py`. E `ScoringSettings.hidden_gem_min_quality=0.7` vs `_HIDDEN_GEM_MIN_QUALITY=0.5`. Quale viene usato effettivamente e in quale contesto?

#### A6. Domain Profile Weights

- **Giustificazione dei pesi**: I 12 domain profiles con 8 weights ciascuno — sono questi weights giustificati da ricerca, best practices, o sono arbitrari? C'è un meccanismo di calibrazione (il Phase 9 feasibility calibration è implementato ma usa mock data)?
- **Profile per OTHER**: Il default è `CODE_QUALITY: 0.20, ARCHITECTURE: 0.15, TESTING: 0.15, DOC: 0.10, MAINT: 0.15, SEC: 0.10, FUNC: 0.10, INNOV: 0.05`. È un profilo bilanciato ragionevole?
- **ML_LIB innovation weight (0.15)**: Per ML libraries, innovation è pesata al 15% — è sufficiente dato che l'innovazione è spesso il principale differenziale?

#### A7. Cross-Domain Normalization

- **Z-score normalization**: `(quality_score - domain_mean) / domain_std + 0.5`. Quando un dominio ha un solo repo, `domain_std = 0.0` → si usa il fallback `0.1`. È robusto?
- **Value score normalization**: Normalizza `value_score` separatamente da `quality_score`, ma `value_score = quality_score`. Questo significa normalizzare lo stesso valore due volte — è un residuo del vecchio design anti-star-bias?

#### A8. Heuristic Fallback Quality

- **Scoring additivo**: Tests (+0.2), CI (+0.2), Docs (+0.15), Security (+0.15), File count (10-500, +0.15), src/lib (+0.15) = max 1.0. È questo un buon fallback quando il LLM fallisce?
- **Pattern-based detection**: I pattern come `_TEST_PATTERNS = ("test/", "tests/", "__test__", "spec/", "pytest", "jest", ...)` sono applicati come substring match case-insensitive sul contenuto packed del repo. Questo è soggetto a falsi positivi?

### SEZIONE B: Qualità e Correttezza del Codice

#### B1. Error Handling e Robustness

- **`_safe_score()` in Gate 1**: Ogni sub-score checker è wrappato in try/except che ritorna `value=0.0, confidence=0.0` su errore. Questo è un approccio "fail-closed" (zero score su errore). È preferibile a "fail-open" (score neutro 0.5)?
- **`_fetch()` in `gather_context()`**: Cattura tutte le eccezioni e ritorna `{}`. Questo maschera errori API reali (rate limiting, auth failures, etc.) come "no data" — è corretto?
- **Assessment orchestrator**: Il catch `except AssessmentError: raise` seguito da `except Exception: raise AssessmentError` è un pattern corretto per preservare la catena di errori?

#### B2. Type Safety e Consistency

- **`SubScore.weight` default 1.0**: Tutti i sub-scores hanno weight 1.0, ma il campo è `float`. C'è rischio di inconsistenze se weights vengono customizzati senza validazione?
- **`object` type nei details**: `details: dict[str, object]` nei sub-scores — è troppo permissivo? Sarebbe meglio tipare più specificamente?
- **`ScoreDimension` come dict key**: Usare `StrEnum` come chiave di dict in `dimension_scores` e `dimensions` — è serializzabile correttamente in JSON/SQLite?

#### B3. Concurrency e Resource Management

- **`asyncio.Semaphore` nei batch**: `_MAX_CONCURRENT = 5` per Gate 1, `_MAX_CONCURRENT = 3` per Gate 2 e Gate 3. Sono questi valori appropriati?
- **Clone management**: `tempfile.mkdtemp` + `shutil.rmtree` in finally block — c'è rischio di leak se il processo viene killato?
- **LLM provider**: Il provider è lazy-initialized (`_ensure_provider()`). Il client OpenAI viene mai chiuso correttamente in caso di errore?

#### B4. Caching e State

- **In-memory cache**: L'assessment orchestrator usa `dict[str, tuple[DeepAssessmentResult, float]]` con TTL. Non è persistente across restart — è un problema?
- **FeatureStore**: Usa SQLite per caching di ScoreResult. La TTL è gestita? Ci sono meccanismi di cleanup per entry scadute?
- **Session state**: Lo `hash()` per seeded tie-breaking è calcolato con `hash((settings.ranking_seed, result.full_name))`. È riproducibile cross-process?

### SEZIONE C: Architettura e Design

#### C1. Separation of Concerns

- **`_DERIVATION_MAP` come modulo-level constant**: È hardcoded nell'engine. Sarebbe meglio nel DomainProfile per permettere mapping per-domain?
- **`_DOMAIN_THRESHOLDS` nell'orchestrator**: Thresholds per-domain hardcoded nel screening orchestrator. Dovrebbero essere nel DomainProfile?
- **Dual threshold source**: Hidden gem thresholds sono definiti sia in `ScoringSettings` che in `models/scoring.py` come costanti — c'è un single source of truth?

#### C2. Extensibility

- **Aggiunta di nuove dimensioni**: Se si volesse aggiungere una 9° dimensione (es. ACCESSIBILITY), quante parti del codice vanno toccate? È un problema?
- **Aggiunta di nuovi domini**: La aggiunta di DomainType.QA_TOOL richiede modifiche in enums.py, profiles.py, e orchestrator.py. È accettabile?
- **Custom profiles**: `custom_profiles_path` esiste in ScoringSettings ma non è implementato. È un gap?

#### C3. Test Coverage Quality

- **1326 tests passing**: Ma quanta parte della logica di scoring è testata con edge cases realistici vs. test su mock?
- **Mock-heavy testing**: La maggior parte dei test usa mock per API calls e LLM. Il sistema è mai stato testato end-to-end con repository reali (al di fuori del smoke test con 20 repo)?
- **Feasibility validation**: Phase 9 include metriche (Precision@K, NDCG, MRR) ma calcolate su fixture data (60 sample repos). C'è una baseline reale?

---

## 4. Domande Specifiche per l'Auditore

Rispondi a queste domande in modo diretto e concreto:

1. **Il modello di scoring è valido come sistema di valutazione della qualità del software?** Giustifica la risposta con riferimenti a letteratura, best practice, o framework esistenti (es. OpenSSF Scorecard, CHAOSS, SQALE, etc.).

2. **Il mapping Gate 1+2 → Dimension Scores è logicamente corretto?** Per ogni dimensione nel `_DERIVATION_MAP`, valuta se i sub-scores scelti e i loro weights sono ragionevoli. Proponi alternative se appropriato.

3. **L'esclusione delle dimensioni default (confidence 0.0) dal calcolo composito introduce bias?** Analizza matematicamente cosa succede per repo con solo Gate 1 vs Gate 1+2+3.

4. **Il confidence model è robusto?** Un repo con Gate 1+2+3 parziale (3/8 dimensioni dal LLM) avrà confidence bassa o alta? È corretto?

5. **Il ranking è davvero star-neutral?** Analizza se ci sono vie indirette attraverso cui le stelle influenzano il ranking (es. discovery score, domain assignment, threshold per-domain).

6. **I 12 domain profiles sono bilanciati e giustificati?** Confronta i weights proposti con le best practice per ogni dominio.

7. **Quali sono i 5 problemi più critici che dovrei risolvere?** Prioritizza per impatto sulla validità del sistema di valutazione.

8. **Quali sono i 5 miglioramenti più importanti per la logica di scoring?** Non per il codice, ma per la qualità della valutazione.

9. **Il sistema è pronto per un uso production-facing?** Quali sono i gap principali?

10. **Quali metriche di validazione raccomandi?** Come potrei validare empiricamente che il sistema produce ranking significativamente migliori di un ranking basato sulle stelle?

---

## 5. Output Richiesto

Struttura la tua risposta nei seguenti capitoli:

### Capitolo 1: Executive Summary
- Valutazione complessiva (1-10) della qualità della logica di scoring/ranking
- Valutazione complessiva (1-10) della qualità del codice
- Top 5 problemi critici (con severity: CRITICAL / HIGH / MEDIUM / LOW)
- Top 5 raccomandazioni per miglioramento

### Capitolo 2: Analisi della Logica di Scoring (Dettaglio)
- Per ogni area A1-A8: analisi dettagliata, problemi identificati, raccomandazioni
- Include esempi concreti di scenari problematici

### Capitolo 3: Analisi del Codice (Dettaglio)
- Per ogni area B1-B4: problemi, rischi, raccomandazioni
- Esempi di codice problematico con fix proposti

### Capitolo 4: Analisi Architetturale
- Per ogni area C1-C3: valutazione, gap, raccomandazioni

### Capitolo 5: Risposte alle Domande Specifiche
- Risposta diretta a ciascuna delle 10 domande

### Capitolo 6: Piano di Azione Suggerito
- Azioni prioritarie (immediate, breve termine, lungo termine)
- Metriche di successo per ogni azione
- Stima effort

---

## 6. Vincoli per l'Auditore

1. **Sii specifico**: Non scrivere "i weights potrebbero essere migliorati" — scrivi "il weight di ARCHITECTURE nel DEVOPS_TOOL profile (0.15) è troppo basso rispetto alla sua importanza per tool infrastrutturali; raccomando 0.20 riducendo FUNCTIONALITY da 0.05 a 0.0".

2. **Sia critico ma costruttivo**: Identifica problemi ma proponi sempre soluzioni concrete.

3. **Prioritizza per impatto**: Un bug nel ranking ha priorità più alta di un refactoring di stile.

4. **Considera il contesto**: Questo è un progetto alpha (v0.1.0). Non aspettarti production-hardening completo, ma identifica cosa manca per arrivarci.

5. **Non limitarti al codice mostrato**: Se hai accesso al repository completo, esamina i file che non sono inclusi in questo prompt. Se non ce l'hai, basati su quanto fornito ma segnala le limitazioni.

6. **Confronta con lo stato dell'arte**: Quando appropriato, confronta le scelte di design con sistemi esistenti (OpenSSF Scorecard, CHAOSS metrics, library.io, etc.).

---

## 7. Contesto Aggiuntivo

### 7.1 Risultati E2E Realizzati (Smoke Test)

Con 20 repository MCP office:
- 6 hanno passato Gate 1+2
- 3 hanno ricevuto Gate 3 deep assessment
- Hidden gems identificati: repo con 0 stars e quality > 0.65
- Star-neutral ranking validato: repo con 0 stars classificati sopra repo con 12,281 stars per qualità

### 7.2 Problemi Già Noti (dal Wiki)

- Dependency discovery channel ritorna sempre vuoto
- Sistema mai testato contro API GitHub reali al di fuori dei 20 repo del smoke test
- OSV adapter ritorna scores neutrali (lockfile parsing deferred)
- PyDriller deferred — Gate 1 maintenance usa solo API heuristics (confidence 0.7)
- FullMetricsReport usa flat float fields invece di nested objects
- Wilcoxon signed-rank tie-handling bug (fixed)
- Star count preservation bug durante Gate 3 re-scoring (fixed)

### 7.3 Scelte di Design Intenzionali

- NanoGPT come LLM provider (OpenAI-compatible, non OpenAI diretto)
- in-memory cache per assessment (non persistente)
- SQLite per feature store e sessions (non Redis/Postgres)
- MCP come interfaccia primaria (API REST secondaria)
- Star-neutral design (value_score = quality_score, no star penalty/bonus)
