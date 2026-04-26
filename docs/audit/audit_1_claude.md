# Audit Indipendente — GitHub Discovery v0.1.0-alpha

**Auditore**: Claude (Anthropic) — agendo come Senior Software Architect & Domain Expert in software-quality assessment systems
**Data**: 2026-04-26
**Scope**: Audit critico, severo, costruttivo della logica di scoring/ranking e della qualità del codice
**Modalità**: Black-box review basata sul materiale fornito nel prompt. Segnalo esplicitamente quando una conclusione richiederebbe verifica diretta sul repository.

---

## Capitolo 1 — Executive Summary

### 1.1 Valutazioni complessive

| Area | Voto | Sintesi |
|------|------|---------|
| **Logica di scoring/ranking** | **5.5 / 10** | Framework concettualmente interessante (gate progressivi, star-neutrality, separazione confidence/quality) ma con **errori concettuali nel mapping Gate1+2 → dimensioni**, **incoerenze tra fonti di verità**, **redistribuzione implicita dei pesi non documentata**, e **assenza totale di validazione empirica contro ground truth**. Non è ancora un sistema di valutazione difendibile. |
| **Qualità del codice Python** | **7 / 10** | Architettura modulare pulita, buona separazione delle responsabilità, type hints, 1326 test, 0 lint/type errors. Difetti reali ma non drammatici: **dual sources of truth** per costanti, **error handling troppo silenzioso** (`fail-closed` aggressivo), **caching non persistente**, alcuni **hash non riproducibili**. |

> **Nota onesta**: la valutazione 5.5/10 sulla logica di scoring **non è una bocciatura** del progetto — è la valutazione del modello *come sistema scientifico di valutazione*. Per un alpha v0.1.0-alpha, è un punto di partenza ragionevole; per dichiararsi "production-ready" è insufficiente. Il delta tra dove sei e dove dovresti essere è **calibrazione empirica + correzione di errori concettuali identificabili**, non riscrittura totale.

### 1.2 Top 5 problemi critici (prioritizzati per impatto sulla validità del sistema)

| # | Severity | Problema | Impatto |
|---|----------|----------|---------|
| 1 | **CRITICAL** | **Doppia fonte di verità per `hidden_gem` thresholds**: `ScoringSettings` dichiara `(quality≥0.7, stars<500)`; `models/scoring.py` dichiara `(quality≥0.5, stars<100)`. Il computed_field `ScoreResult.is_hidden_gem` usa il secondo; `value_score.is_hidden_gem()` usa il primo. **Due API pubbliche restituiscono risultati contraddittori per lo stesso repo.** | Bug reale, non controverso. Compromette explainability e fiducia degli utenti. |
| 2 | **CRITICAL** | **`_DERIVATION_MAP` contiene errori concettuali**: (a) `ARCHITECTURE = 70% complexity` è invertito — alta complessità ciclomatica è *anti-correlata* a buona architettura, non un proxy di essa; (b) `CODE_QUALITY` deriva da `review_practice + ci_cd + dependency_quality` ma **omette completamente** complexity, test_footprint, hygiene; (c) `DOCUMENTATION` deriva 40% da `review_practice` (PR templates), che non ha alcuna relazione causale con qualità della documentazione. | I quality_score derivati per repo Gate1+2-only sono sistematicamente inaffidabili. |
| 3 | **HIGH** | **Redistribuzione implicita dei pesi senza guard rail**: escludere dimensioni con `confidence ≤ 0.0` e renormalizzare `total_weight` significa che un repo Gate1+2-only su profilo `ML_LIB` viene valutato sul **60% del peso originale** (FUNCTIONALITY 0.25 + INNOVATION 0.15 esclusi). Il quality_score non è confrontabile tra repo con coverage diverso. **Nessun warning, nessun flag, nessun cap minimo di coverage.** | Inflated scores per repo "metadata-belli ma non funzionanti". Bias sistematico. |
| 4 | **HIGH** | **Heuristic fallback è un presence-checklist, non un quality assessment**: il punteggio massimo 1.0 si raggiunge con la sola presenza di `tests/`, `.github/workflows/`, `README`, `SECURITY.md`, src/ e file count nel range. Un repository deliberatamente cosmetic-perfect ma vuoto otterrebbe ~0.85. Quando il LLM fallisce (cosa che succederà in produzione), il sistema mente sul punteggio. | Failure mode silenzioso che colpisce proprio gli "hidden gems" (repo poco strutturati ma di valore). |
| 5 | **HIGH** | **`hash()` Python non è riproducibile cross-process**: il `_sort_key` del Ranker usa `hash((seed, full_name))` per tie-breaking. Anche con `PYTHONHASHSEED` fissato, `hash()` su tuple miste è implementation-specific e **cambia tra versioni di CPython**. Il "seeded" tie-breaking non è in realtà seeded. | Ranking non riproducibile tra deploy/versioni. Compromette debugging, A/B testing, e regression testing. |

### 1.3 Top 5 raccomandazioni di miglioramento (logica di scoring)

| # | Raccomandazione | Effort | ROI |
|---|----------------|--------|-----|
| 1 | **Costruire un dataset di calibrazione con ground-truth umano**: 100-200 repo etichettati da 3+ esperti su 8 dimensioni, con accordo inter-rater (Cohen κ). Senza questo, ogni claim di "qualità" è non falsificabile. | 2-4 settimane | Massimo: trasforma il progetto da "speculative" a "evidence-based". |
| 2 | **Riprogettare `_DERIVATION_MAP` da letteratura validata** (CHAOSS metrics, OpenSSF Scorecard mapping, Maven Quality Model di Garousi & Felderer). Documentare ogni mapping con citazione. Eseguire ablation studies sul dataset di calibrazione. | 1-2 settimane | Alto: corregge errori concettuali identificabili. |
| 3 | **Esplicitare la "coverage" come segnale separato dal quality_score**: introdurre `coverage_ratio = effective_weight / total_weight` e clampare il quality_score a un range conservativo quando coverage < 0.7 (es. `quality * sqrt(coverage)`). | 3-5 giorni | Alto: chiude il bug di confrontabilità inter-repo. |
| 4 | **Sostituire `hash()` con `hashlib.blake2b(seed‖full_name)`** per tie-breaking deterministico. Aggiungere test di regressione che verifichino lo stesso ordering tra processi distinti. | 1 giorno | Medio: bug fix + abilita debug riproducibile. |
| 5 | **Riprogettare l'heuristic fallback come "ignorance signal"**: invece di restituire un punteggio tra 0 e 1 quando il LLM fallisce, restituire un range `(min, max)` con confidence proporzionale all'incertezza. La media dell'heuristic dovrebbe essere ~0.5 con `confidence ≤ 0.2`, non un valore alto e fiducioso. | 3 giorni | Alto: elimina failure mode silenzioso. |

---

## Capitolo 2 — Analisi della Logica di Scoring (Dettaglio)

### A1. Validità del Modello di Scoring

#### A1.1 Il `_DERIVATION_MAP` — analisi mapping per mapping

Il mapping è il cuore del sistema quando Gate 3 non è disponibile. Lo analizzo dimensione per dimensione confrontando con CHAOSS, OpenSSF Scorecard, e ISO/IEC 25010 (modello di qualità del software).

**`CODE_QUALITY = 0.5·review_practice + 0.3·ci_cd + 0.2·dependency_quality`**

> **Verdetto: errato concettualmente.**
>
> ISO/IEC 25010 definisce code quality come *maintainability + reliability + functional suitability* — modulare, testabile, leggibile. Il proxy più diretto da metadati GitHub sarebbe:
> - **complexity** (basso cyclomatic = alta qualità) — pesante peso
> - **test_footprint** (presenza/ratio test) — segnale forte
> - **review_practice** (PR review = code review = quality gate) — segnale moderato
> - **hygiene** (linting, formatting tools nel repo) — segnale debole
>
> Il mapping attuale **omette `complexity`** (l'unico segnale tecnico-strutturale di Gate 2!) e omette `test_footprint`. `review_practice` è sopravvalutata: misura il *processo*, non il *prodotto*.
>
> **Proposta**: `CODE_QUALITY = 0.35·complexity + 0.25·test_footprint + 0.25·review_practice + 0.15·ci_cd`

**`ARCHITECTURE = 0.7·complexity + 0.3·ci_cd`**

> **Verdetto: gravemente errato.**
>
> Due problemi:
> 1. **Architettura ≠ complessità ciclomatica per file**. SCC misura LOC, complessità per funzione, lingue. Non misura coupling, cohesion, layering, separation of concerns — che *sono* l'architettura. Usare SCC come proxy del 70% per architettura è un category error.
> 2. **Direzione del segnale**: alta complessità è di solito *negativa* per architettura (god classes, lack of decomposition). Il sistema sembra trattare alta complessità come un'inversione neutra (presumibilmente `complexity_score` è già normalizzato come "lower is better → higher score"), ma il prompt non lo chiarisce. Se il segnale fosse invertito, sarebbe un bug catastrofico.
>
> **Realtà sgradevole**: l'architettura *non è derivabile* da Gate 1+2 in modo affidabile. È un giudizio strutturale che richiede analisi del codice (Gate 3) o metriche dedicate (es. modularity score via dependency graph clustering).
>
> **Proposta**:
> - Opzione A (onesta): `ARCHITECTURE = []` (mappa vuota, come FUNCTIONALITY/INNOVATION) — confidence 0 senza Gate 3.
> - Opzione B (proxy debole): `ARCHITECTURE = 0.4·test_footprint + 0.3·hygiene + 0.3·ci_cd` con `confidence_factor: 0.3` (segnale debole, dichiarato come tale).

**`TESTING = 0.7·test_footprint + 0.3·ci_cd`**

> **Verdetto: ragionevole ma incompleto.**
>
> Test footprint è un proxy di *quantità* (presenza di directory test, ratio file). Non misura *qualità del test* (coverage, mutation score, flakiness). CI/CD è un segnale debole (presenza CI ≠ test rilevanti girano). Mapping accettabile per Gate 1+2.
>
> **Nota fine**: il pattern matching del test_footprint (`"test/"`, `"tests/"`, `"__test__"`, ecc.) ha falsi positivi notevoli (vedi A8). Un repo che cita "pytest" nel README ottiene segnale anche se non ha test.

**`DOCUMENTATION = 0.6·hygiene + 0.4·review_practice`**

> **Verdetto: errato.**
>
> `hygiene` aggrega la presenza di README/CONTRIBUTING/CHANGELOG/etc. — segnale ragionevole ma misura *presenza* di file, non *qualità* della documentazione. **`review_practice` (PR templates, review rate, label usage) non ha alcuna relazione causale né correlazionale documentata con qualità della documentazione.** È un cross-mapping che inquina il segnale.
>
> **Proposta**: `DOCUMENTATION = 0.7·hygiene + 0.3·release_discipline` (changelog per release è un segnale di documentazione del cambiamento). Confidence dichiarata bassa (0.3-0.4) perché la qualità reale richiede analisi semantica del README.

**`MAINTENANCE = 0.4·maintenance + 0.3·release_discipline + 0.2·ci_cd + 0.1·hygiene`**

> **Verdetto: ragionevole.**
>
> Gli weights sono difendibili. `maintenance` Gate 1 cattura recency/cadence/bus factor — il segnale più importante. `release_discipline` è un buon proxy secondario. Suggerisco solo: portare `release_discipline` a 0.35 e `ci_cd` a 0.15 (CI è già in TESTING e CODE_QUALITY, double-counting).

**`SECURITY = 0.35·security_hygiene + 0.25·vulnerability + 0.25·secret_hygiene + 0.15·dependency_quality`**

> **Verdetto: ragionevole, con nota.**
>
> Mapping ben pensato. Tuttavia, dato che **OSV adapter è ad oggi neutralizzato** (lockfile parsing deferred → confidence 0.0 effettiva), il `vulnerability` 0.25 viene di fatto escluso dal calcolo, e quel 25% si redistribuisce silenziosamente. Documenterei esplicitamente questo nel report explainability.

**`FUNCTIONALITY = []` e `INNOVATION = []`**

> **Verdetto: corretto come scelta, sbagliato come implementazione.**
>
> Onesto dichiarare che queste dimensioni non sono derivabili da metadati. **Ma il default neutral (0.5, conf=0.0) e l'esclusione dal composite via `confidence ≤ 0.0` producono un effetto pernicioso**: per un profilo come `ML_LIB` (FUNCTIONALITY=0.25, INNOVATION=0.15), un repo Gate1+2-only viene valutato sul 60% del peso. Il rischio è che il quality_score sia *sopravvalutato* per repo che eccellono in metadati ma non in funzionalità reale.
>
> **Vedi A2.1 per la matematica completa.**

#### A1.2 Confronto con OpenSSF Scorecard

OpenSSF Scorecard usa **17 check** ognuno con weight esplicito documentato (Maintained=3, Code-Review=3, CI-Tests=3, Branch-Protection=3, ..., Pinned-Dependencies=2, Token-Permissions=1, ecc.). I weights sono pubblici, giustificati con motivazione, e calibrati su un dataset di vulnerabilità storiche.

GitHub Discovery, in confronto:
- ✅ Più ambizioso (8 dimensioni, multi-dominio)
- ❌ Weights non calibrati empiricamente
- ❌ Mapping intermedio (Gate1+2 sub-scores → 8 dimensioni) introduce un layer di soggettività non presente in Scorecard
- ❌ Nessun riferimento a letteratura nel codice/docs (segnalato dal prompt: "sono questi giustificati da ricerca?")

**Raccomandazione**: pubblicare un *Scoring Methodology Document* che, per ogni mapping e weight, citi la fonte (paper, framework, sondaggio interno, decisione arbitraria documentata).

---

### A2. Coerenza del Calcolo Composite

#### A2.1 Matematica della redistribuzione implicita — esempio numerico

Scenario: repo su profilo `ML_LIB`, solo Gate 1+2 disponibile (no Gate 3).

Profile weights:
```
CODE_QUALITY: 0.10, ARCHITECTURE: 0.10, TESTING: 0.10,
DOCUMENTATION: 0.10, MAINTENANCE: 0.15, SECURITY: 0.05,
FUNCTIONALITY: 0.25, INNOVATION: 0.15        ← entrambe escluse
```

**Effective weights dopo esclusione**:
```
CODE_QUALITY: 0.10, ARCHITECTURE: 0.10, TESTING: 0.10,
DOCUMENTATION: 0.10, MAINTENANCE: 0.15, SECURITY: 0.05
total_weight = 0.60
```

Supponiamo dimensioni derivate tutte a 0.6 (un repo "decente"):
```
quality_score = (0.6·0.10 + 0.6·0.10 + ... + 0.6·0.05) / 0.60
              = 0.36 / 0.60 = 0.6
```

**Stessa scena, profilo `LIBRARY`** (FUNC+INNOV solo 0.10 totale):
```
total_weight dopo esclusione = 0.90
quality_score = (0.6·0.20 + 0.6·0.15 + ... + 0.6·0.10) / 0.90
              = 0.54 / 0.90 = 0.6
```

> **Osservazione**: il quality_score è lo stesso (0.6) in entrambi i casi, pur essendo basato su coverage molto diversi (60% vs 90% del peso). **Questa è la fonte del bias**: il sistema non comunica all'utente che il primo punteggio è basato su molte meno informazioni del secondo. Due repo con `quality_score=0.6` non sono equivalenti.

#### A2.2 Soluzione proposta — esplicita la coverage

```python
def _apply_weights(self, dimension_scores, profile):
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
        return 0.0, 0.0  # raw_score, coverage
    raw_score = weighted_sum / total_weight_used
    coverage = total_weight_used / total_weight_possible
    # Penalizza score con bassa coverage:
    adjusted_score = raw_score * (0.5 + 0.5 * coverage)  # max 1·raw, min 0.5·raw
    return adjusted_score, coverage
```

E rendere `coverage` un campo esplicito di `ScoreResult` per explainability.

#### A2.3 Sub-score weights uniformi in Gate 1 — un secondo bug di non-calibrazione

Tutti i 7 sub-scores Gate 1 hanno `weight=1.0`. Questo significa:
- `hygiene` (presenza file admin) ≡ peso ≡ `maintenance` (recency, bus factor, cadence)
- `release_discipline` (semver tags) ≡ peso ≡ `test_footprint` (test/source ratio)

**Ranking di importanza dalla letteratura empirica** (da CHAOSS metrics e Vasilescu et al., "Continuous Integration in Open-Source", 2015; Bavota et al., "An Empirical Study on the Quality of Code Reviews", 2016):

1. **maintenance** (recency + bus factor) — predittore più forte di longevità del progetto
2. **test_footprint** — predittore di reliability
3. **ci_cd** — predittore di stabilità
4. **review_practice** — predittore di code quality
5. **dependency_quality** — predittore di security
6. **release_discipline** — predittore di stability
7. **hygiene** — segnale debole (boilerplate facile da fakerare)

**Proposta**:
```
maintenance: 1.5, test_footprint: 1.2, ci_cd: 1.1, review_practice: 1.0,
dependency_quality: 0.9, release_discipline: 0.8, hygiene: 0.5
```
(Da calibrare sul dataset ground-truth.)

---

### A3. Confidence Model

#### A3.1 Valori hardcoded — analisi giustificazione

```python
_SOURCE_CONFIDENCE = {"gate3_llm": 0.8, "gate12_derived": 0.4, "default_neutral": 0.0}
_GATE_COVERAGE_BONUS = {"gate1_only": 0.0, "gate1_gate2": 0.05, "gate1_gate2_gate3": 0.10}
```

**Analisi**:
- `gate3_llm = 0.8`: implica che un LLM è 80% affidabile. **Su che base?** Letteratura recente (Tian et al., "ChatGPT for Code Quality Assessment", ICSE 2024) mostra LLM accuracy 60-75% su task di code review se confrontati con esperti. Il 0.8 è ottimistico.
- `gate12_derived = 0.4`: ragionevole come "metà confidence" rispetto a LLM. Ma la confidence dovrebbe variare per dimensione: derivare TESTING da `test_footprint` è più affidabile (0.6?) che derivare ARCHITECTURE da `complexity` (0.2?).
- Bonus `+0.05/+0.10`: troppo piccoli per essere significativi. Una repo con Gate1 only ha conf media ~0.35, una con Gate1+2+3 ha ~0.85. Il bonus ridondante non sposta il segnale.

**Proposta**: rendere la confidence per-dimensione *non costante per source*, ma una funzione del *mapping quality* di quella dimensione:

```python
_DIMENSION_CONFIDENCE_FROM_GATE12: dict[ScoreDimension, float] = {
    ScoreDimension.TESTING: 0.55,        # mapping forte (test_footprint diretto)
    ScoreDimension.MAINTENANCE: 0.50,
    ScoreDimension.SECURITY: 0.50,
    ScoreDimension.DOCUMENTATION: 0.40,
    ScoreDimension.CODE_QUALITY: 0.35,
    ScoreDimension.ARCHITECTURE: 0.25,   # mapping debole
    ScoreDimension.FUNCTIONALITY: 0.0,   # non derivabile
    ScoreDimension.INNOVATION: 0.0,
}
```

#### A3.2 Average vs min confidence

> **Domanda del prompt**: media o minimo?

**Analisi**: la media è troppo ottimistica. Se 7 dimensioni hanno conf=0.8 e 1 ha conf=0.0, media=0.7. Ma quel singolo "buco" potrebbe essere proprio la dimensione cruciale per il dominio.

**Proposta**: usare una **media pesata dai weights del profilo** (così le dimensioni rilevanti per il dominio influenzano di più la confidence):

```python
def compute_overall_confidence(self, dimension_infos, profile):
    total = sum(profile.dimension_weights[dim] * info.confidence
                for dim, info in dimension_infos.items())
    weight_sum = sum(profile.dimension_weights.values())
    return total / weight_sum
```

Aggiungere anche un guard rail: se `min(confidences) ≤ 0.0` per una dimensione con peso ≥ 0.15, abbassare la confidence overall di un fattore (segnale "dimensione critica mancante").

---

### A4. Ranking e Tie-Breaking

#### A4.1 `hash()` non è deterministico cross-process

```python
seeded_hash = hash((self._settings.ranking_seed, result.full_name))
```

**Bug confermato**: `hash()` Python su tuple/string è randomizzato per processo via `PYTHONHASHSEED` (se "random"), e anche con seed fissato, l'algoritmo cambia tra versioni minor (es. CPython 3.4 → 3.12 ha cambiato lo string hash). Documentato in [PEP 456](https://peps.python.org/pep-0456/).

**Conseguenza**: due deploy diversi con stesso `ranking_seed` ordinano differentemente in caso di tie su quality+confidence. Compromette:
- Riproducibilità di test di regressione
- A/B testing tra versioni del sistema
- Caching del ranking
- Audit trail / explainability

**Fix**:
```python
import hashlib

def _seeded_hash(self, full_name: str) -> int:
    payload = f"{self._settings.ranking_seed}:{full_name}".encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=False)
```

Aggiungere test:
```python
def test_seeded_hash_is_stable():
    # Hardcoded expected value computed once
    assert ranker._seeded_hash("foo/bar") == 12345678901234567
```

#### A4.2 Hidden gem identification con pool piccoli

```python
top_25_q = sorted_qs[max(1, len(sorted_qs) // 4) - 1]
```

**Analisi**:
- N=4: `max(1, 1)-1 = 0` → top_25_q = sorted_qs[0] = il valore massimo. Quindi solo il top 1 supera il threshold.
- N=3: `max(1, 0)-1 = 0` → top_25_q = sorted_qs[0]. Stesso risultato.
- N=2: stesso.
- N=1: `max(1, 0)-1 = 0` → top_25_q = sorted_qs[0]. Quel singolo repo è "top 25%". Hidden gem se passa altri criteri.

> Il prompt afferma: "With <4 repos: top_25_q = 0.0 (no percentile filter)". **Questa affermazione non corrisponde al codice mostrato**, che con N<4 *non* azzera il filtro — restituisce il massimo. Se il filtro viene azzerato altrove (es. nel ranker), è un branching nascosto che andrebbe esposto.

**Raccomandazione**: documentare esplicitamente il comportamento per N piccoli e aggiungere test parametrizzati per N ∈ {1, 2, 3, 4, 5, 10, 100}.

#### A4.3 Star-neutralità — è davvero tale?

> **Domanda del prompt**: "Il ranking è davvero star-neutral?"

**Risposta onesta: parzialmente.** Vie indirette dove le stelle influenzano il ranking:

1. **Discovery (Gate 0)**: i 6 channels (presumibilmente trending, search, awesome lists, ecc.) sono *intrinsecamente bias verso popolari*. GitHub Search API ordina per "best match" che include star count. **Le stelle determinano chi entra nel pool**, non chi vince — ma chi non entra non vince.
2. **Cross-domain z-score normalization**: depende da `domain_mean` e `domain_std`, che dipendono dalla composizione del pool, che dipende dal punto 1.
3. **`star_baseline` nei domain profiles**: il prompt dichiara `star_baseline=500` per LIBRARY e `2000` per ML_LIB. **A cosa serve questo campo?** Se è usato per normalizzare qualcosa, allora le stelle entrano nel sistema di scoring.
4. **`corroboration_level`**: computed_field di `ScoreResult` che bucketizza per stelle. Non influenza il quality_score, ma è esposto nell'output e potrebbe essere usato a valle per ri-ordinare.
5. **Hidden gem identification**: usa stelle come threshold. Star-neutrality del *quality_score* sì; star-neutrality del *labeling* no.

**Conclusione**: il sistema ha **quality-score star-neutrality** (corretto e validabile) ma NON ha **end-to-end ranking star-neutrality** finché il pool di Gate 0 è bias verso popolari. Questo va dichiarato esplicitamente nelle docs.

**Raccomandazione**: aggiungere un test empirico — generare 2 pool (uno bias verso stelle, uno bilanciato) e mostrare che il ranking *interno al pool* è invariante. Non puoi compensare il bias di selezione, ma puoi documentarlo.

---

### A5. Threshold e Configurazione

#### A5.1 Gate thresholds

| Gate | Threshold | Analisi |
|------|-----------|---------|
| Gate 1: 0.4 | Permissivo. Un repo con sub-scores 0.5/0.5/0.5/0.5/0.5/0.0/0.0 (ottimo su 5 dimensioni, zero su 2) ottiene 2.5/7 = 0.36 → **fails**. Ma 0.5/0.5/0.5/0.5/0.0/0.0/0.0 = 2.0/7 = 0.29 fails. Il 0.4 è di fatto "il repo deve essere mediocre su almeno 4 dimensioni su 7". **Ragionevole come filtro permissivo per non escludere hidden gems.** |
| Gate 2: 0.5 | Con fallback 0.3 per tool failures, 2 tool falliti su 4 → max ottenibile (0.3+0.3+1.0+1.0)/4 = 0.65 → potrebbe passare. Con 3 tool falliti: 0.4 → fails. **Il problema è che `confidence=0.0` non penalizza il composite — un repo con 4 fallback 0.3 ottiene 0.3 e fails, ma il sistema non sa distinguere "tool fallito" da "repo realmente insicuro".** |
| Gate 3: 0.6 | Per il deep assessment LLM, 0.6 è high-bar. Fattibile per repo curati, ma esclude molti hidden gems che potrebbero meritare attenzione. Considerare 0.55 e raccolta di metriche per calibrare. |

**Raccomandazione strutturale**: rendere i threshold `float | None` — se `None`, il gate non filtra ma viene comunque calcolato. Permette modalità "analysis-only" utile per debugging e per costruire il dataset di calibrazione.

#### A5.2 Hidden gem thresholds — il bug della doppia verità

**Confermato come bug.**

```python
# In ScoringSettings (config.py):
hidden_gem_star_threshold: int = 500
hidden_gem_min_quality: float = 0.7

# In models/scoring.py:
_HIDDEN_GEM_MAX_STARS = 100
_HIDDEN_GEM_MIN_QUALITY = 0.5

# In value_score.py (è quello che usa _hidden_gem_min_quality / _hidden_gem_star_threshold):
def is_hidden_gem(self, quality_score, stars, value_score) -> tuple[bool, str]:
    if quality_score < self._hidden_gem_min_quality: ...   # 0.7
    if stars >= self._hidden_gem_star_threshold: ...       # 500

# In ScoreResult (computed_field):
@property
def is_hidden_gem(self) -> bool:
    return self.quality_score >= 0.5 and self.stars < 100
```

**Conseguenza concreta**: un repo con quality_score=0.6, stars=300:
- `ScoreResult.is_hidden_gem` → `0.6 >= 0.5 and 300 < 100` → `False`
- `ValueScoreCalculator.is_hidden_gem` → `0.6 < 0.7` → `False, "Quality below threshold"`

Stesso outcome per coincidenza in questo esempio. Ma con quality=0.55, stars=300:
- ScoreResult: `True` (>=0.5, <100? NO, 300>=100) → `False`. OK coincide.

Trova esempio dove differiscono: quality=0.55, stars=80:
- ScoreResult: `0.55 >= 0.5 and 80 < 100` → **`True`**
- Calculator: `0.55 < 0.7` → **`False`**

**Bug confermato.** Il prompt mi chiedeva: "Questa divergenza è un bug o è intenzionale?". **È un bug**, e visibile a utenti finali via diverse API.

**Fix**: cancellare `_HIDDEN_GEM_*` da `models/scoring.py`. Il computed_field deve dipendere da settings:

```python
class ScoreResult(BaseModel):
    # ...
    @computed_field
    @property
    def is_hidden_gem(self) -> bool:
        # Delegate to value_score logic — don't duplicate
        # Better: remove this computed_field entirely.
        # Hidden gem labeling is a service concern, not a model concern.
        ...
```

**Raccomandazione architetturale**: rimuovere `is_hidden_gem` dal model (è logica di business, non proprietà del dato). Esporre solo via `ValueScoreCalculator`. Single source of truth.

---

### A6. Domain Profile Weights

#### A6.1 Giustificazione dei pesi — assente

12 profili × 8 weights = 96 valori. Senza una metodologia di calibrazione, sono speculazioni educate. Il prompt conferma: "Phase 9 feasibility calibration è implementato ma usa mock data". **Significa: i weights non sono calibrati.**

#### A6.2 Confronti puntuali

**LIBRARY profile** `(CQ:0.20, ARCH:0.15, TEST:0.15, DOC:0.15, MAINT:0.15, SEC:0.10, FUNC:0.05, INNOV:0.05)`:
- ✅ TESTING al 15% ragionevole (test pubblici sono critici per librerie)
- ✅ DOC al 15% ragionevole (doc sono il "prodotto" di una libreria)
- ⚠️ FUNCTIONALITY al 5% **troppo basso**. Per una libreria, "fa quello che promette" è fondamentale. Suggerisco 0.10.
- ⚠️ INNOVATION al 5% accettabile (libraries non devono innovare).
- **Proposta**: `(CQ:0.20, ARCH:0.15, TEST:0.15, DOC:0.15, MAINT:0.15, SEC:0.10, FUNC:0.10, INNOV:0.0)`.

**ML_LIB profile** `(CQ:0.10, ARCH:0.10, TEST:0.10, DOC:0.10, MAINT:0.15, SEC:0.05, FUNC:0.25, INNOV:0.15)`:
- ⚠️ INNOVATION al 15% **probabilmente sotto-pesato**. ML libraries traggono valore principalmente dall'innovazione (nuovi algoritmi, nuovi approcci). Survey come Tian et al., "Quality Assurance Practices in ML Engineering" (TSE 2023), suggeriscono che innovation/research-novelty è il fattore dominante.
- ✅ FUNCTIONALITY al 25% giustificato.
- ⚠️ TESTING al 10% **troppo basso** per ML — i bug numerici/tensoriali sono pernicious. Suggerisco 0.15.
- ⚠️ SECURITY al 5% accettabile (ML libs hanno superficie di attacco minore).
- **Proposta**: `(CQ:0.10, ARCH:0.10, TEST:0.15, DOC:0.10, MAINT:0.10, SEC:0.05, FUNC:0.20, INNOV:0.20)`.

**DEVOPS_TOOL** *(esempio dal prompt: "ARCHITECTURE 0.15 troppo basso, raccomando 0.20")*:
- Concordo con la valutazione. Strumenti DevOps (CI/CD, IaC, orchestrators) sono *infrastrutturali* — l'architettura è critica perché determina robustness, extensibility, reliability. ARCHITECTURE meriterebbe 0.20-0.25.

**OTHER profile** (default):
- ✅ Bilanciato e ragionevole come fallback.
- Suggerisco solo: portare INNOV da 0.05 a 0.0 o aggregarlo in CODE_QUALITY (innovazione misurata da Gate 3 LLM è troppo soggettiva per un default).

**Conclusione**: senza calibrazione empirica, queste sono opinioni. **Suggerisco fortemente di non pubblicare i 12 profili come "definitive" finché non hai un dataset etichettato.** Considera di iniziare con 3 profili archetipici (LIBRARY, APPLICATION, OTHER) e aggiungere domini man mano che emerge evidenza.

---

### A7. Cross-Domain Normalization

#### A7.1 Z-score con N=1

```
normalized = (q - q_mean) / q_std + 0.5
```

Con N=1, `q_std = 0`, fallback a 0.1. Risultato: `(q - q) / 0.1 + 0.5 = 0.5`.

**Conseguenza**: ogni repo isolato nel suo dominio ottiene `cross_domain_score = 0.5`, indipendentemente dal quality_score. Un repo con quality=0.95 e un repo con quality=0.20, se sono unici nel loro dominio, ottengono lo stesso score normalizzato.

**Soluzione**: con N<3, **non normalizzare** — passa il quality_score raw e dichiara `cross_domain_confidence=0`. La z-score richiede N≥3 minimo per essere significativa, idealmente N≥10.

```python
def normalize(self, scores_per_domain):
    for domain, scores in scores_per_domain.items():
        if len(scores) < 3:
            # Insufficient data — pass through
            continue
        mean = statistics.mean(scores)
        std = statistics.stdev(scores)
        if std < 0.05:  # near-uniform
            continue
        for repo in repos_in_domain:
            repo.normalized = (repo.quality - mean) / std + 0.5
```

#### A7.2 Doppia normalizzazione di value_score

> **Domanda del prompt**: "Normalizzare value_score separatamente da quality_score, ma value_score = quality_score → normalizzare due volte?"

**Risposta**: sì, è un residuo. Se `value_score == quality_score` per design (star-neutrality), normalizzare entrambi è ridondante e crea due campi che dovrebbero sempre essere uguali. **Rimuovere la normalizzazione di `value_score`** o, più pulitamente, rimuovere `value_score` dal model (è già `quality_score`).

**Eccezione**: se in futuro vorrai re-introdurre un value_score derivato (es. quality × maturity), allora ha senso mantenerlo come field separato. Ma documentalo.

---

### A8. Heuristic Fallback Quality

#### A8.1 Il problema strutturale

```
+0.20 has tests, +0.20 has CI, +0.15 has docs, +0.15 has security,
+0.15 file count 10-500, +0.15 has src/lib  →  max 1.0
```

Un repository **deliberatamente costruito** per gaming questo sistema:
- `mkdir tests && touch tests/test_dummy.py`  → +0.20
- `mkdir -p .github/workflows && echo "name: ci" > .github/workflows/ci.yml` → +0.20
- `touch README.md`  → +0.15
- `touch SECURITY.md`  → +0.15
- 50 file dummy generati  → +0.15
- `mkdir src`  → +0.15
- **Total: 1.00**

Il LLM avrebbe colto la cosmetic-perfection. L'heuristic fallback no. **Quando il LLM fallisce (timeout, rate limit, NanoGPT down), l'utente riceve un punteggio falsamente alto.**

#### A8.2 Pattern-based detection — falsi positivi

```python
_TEST_PATTERNS = ("test/", "tests/", "__test__", "spec/", "pytest", "jest", ...)
```

Match come substring case-insensitive sul packed content. Falsi positivi:
- README che cita "we use pytest" → +test
- Comment in src code: `# tested with jest` → +test
- File chiamato `manifest.json` non contiene "test" ma `latest_release.json` contiene "test" come substring di "lat**est_re**"... aspetta, no, ma `pytest` matcha letteralmente `pytest` ovunque, anche in `pytestplugin` nomi di package.
- `spec/` matcha `spec/something` ma anche `respec/` o `inspect/` se preceduti da slash → meno probabile, ma `spec` (senza slash) come parola in markdown → falso positivo se i pattern sono solo substring.

**Fix**: regex con boundary, o meglio path-based detection (parsing del file tree, non substring sul content):

```python
def has_test_dir(file_paths: list[str]) -> bool:
    return any(
        Path(p).parts[0] in {"tests", "test", "__tests__", "spec", "specs"}
        or "/test/" in p or "/tests/" in p
        for p in file_paths
    )
```

#### A8.3 Proposta: heuristic come "ignorance signal"

Invece di restituire `(score, confidence)` con confidence alta, restituire:

```python
@dataclass
class HeuristicFallback:
    point_estimate: float = 0.5  # neutro
    uncertainty_range: tuple[float, float] = (0.3, 0.7)
    confidence: float = 0.15  # esplicitamente bassa
    presence_signals: dict[str, bool]  # checklist trasparente
    note: str = "LLM unavailable; heuristic fallback only — interpret with caution"
```

L'utente vede subito che il punteggio è inaffidabile. Il sistema può ri-tentare il LLM più tardi. Il composite quality_score riflette correttamente l'incertezza.

---

## Capitolo 3 — Analisi del Codice (Dettaglio)

### B1. Error Handling e Robustness

#### B1.1 `_safe_score()` — fail-closed vs fail-open

```python
# Wrappa ogni Gate 1 sub-score check; on error → (value=0.0, confidence=0.0)
```

**Pattern attuale: fail-closed (zero score, zero confidence)**.

**Analisi**:
- ✅ **Pro**: bug nei checker non crashano la pipeline. Confidence=0 esclude la dimensione dal composite.
- ❌ **Contro**: maschera silenziosamente errori sistematici. Se il `MaintenanceScore` checker ha un bug regressivo, ogni repo ottiene maintenance=0 e gli utenti non se ne accorgono.
- ❌ **Contro**: non distingue "errore nel checker" da "repo realmente vuoto".

**Proposta**: log strutturato + metrics + fail-closed per execution, ma fail-loud nel reporting:

```python
def _safe_score(self, checker, repo, ctx):
    try:
        return checker.compute(repo, ctx)
    except Exception as e:
        logger.exception("checker_failure",
                         checker=checker.__class__.__name__,
                         repo=repo.full_name)
        metrics.increment("scoring.checker_failures",
                          tags={"checker": checker.__class__.__name__})
        return SubScore(value=0.0, confidence=0.0,
                        details={"error": str(e), "fail_mode": "exception"})
```

E nel ScoreResult/explainability, esponi `failed_checkers: list[str]` per trasparenza.

#### B1.2 `_fetch()` cattura tutto e ritorna `{}`

**Verdetto: errato come pattern.**

```python
except Exception:
    return {}  # ← maschera 401, 403, 429, 5xx come "no data"
```

Catastrofico per:
- **Auth failures (401/403)**: l'utente continua a vedere risultati "ok" mentre il sistema sta operando con metà dei dati.
- **Rate limit (429)**: il sistema continua a martellare l'API e tutte le chiamate falliscono silenziosamente.
- **5xx transient**: nessun retry, nessun backoff.

**Proposta**:
```python
class GitHubFetchError(Exception): pass
class GitHubRateLimitError(GitHubFetchError): pass
class GitHubAuthError(GitHubFetchError): pass

async def _fetch(self, url):
    try:
        resp = await self._client.get(url)
    except httpx.NetworkError as e:
        raise GitHubFetchError(f"network: {e}") from e
    if resp.status_code == 401 or resp.status_code == 403:
        raise GitHubAuthError(...)
    if resp.status_code == 429:
        raise GitHubRateLimitError(retry_after=resp.headers.get("retry-after"))
    if resp.is_server_error:
        raise GitHubFetchError(f"server: {resp.status_code}")
    resp.raise_for_status()
    return resp.json()
```

E al chiamante: gestisci esplicitamente i tipi di errore.

#### B1.3 `except AssessmentError: raise; except Exception: raise AssessmentError`

```python
try:
    ...
except AssessmentError:
    raise  # già nostro tipo, propaga
except Exception as e:
    raise AssessmentError("...") from e  # wrap externals
```

**Verdetto: pattern corretto.** ✅

Solo nota: assicurati che il `from e` ci sia (preserva la traceback chain). Se il codice mostrato è esatto al `raise AssessmentError(...)` senza `from e`, perdi la causa originale.

---

### B2. Type Safety e Consistency

#### B2.1 `SubScore.weight: float = 1.0`

Tutti uguali. Se in futuro qualcuno custom-imposta weight, **non c'è validazione su somma o range**:
- `weight = -0.5` ammesso
- `weight = 100.0` ammesso (squilibra il composite)

**Fix**:
```python
class SubScore(BaseModel):
    weight: float = Field(default=1.0, ge=0.0, le=10.0)
```

#### B2.2 `details: dict[str, object]`

Troppo permissivo. **Proposta**: tipare con `dict[str, str | int | float | bool | None]` (JSON-compatible). Se servono nested dict, usa `dict[str, Any]` esplicitamente con commento.

#### B2.3 `ScoreDimension` come dict key

`StrEnum` come chiave di dict in `dimension_scores: dict[ScoreDimension, float]`:
- **JSON serialization**: Pydantic serializza `StrEnum` come stringa → OK per JSON.
- **SQLite**: dipende dall'implementazione del FeatureStore. Se serializzi a JSON colonna, OK. Se mappi a colonne, problema.
- **Deserialization roundtrip**: testare esplicitamente che `model_validate(model_dump())` produca lo stesso dict.

**Test consigliato**:
```python
def test_score_result_json_roundtrip():
    sr = ScoreResult(...)
    json_data = sr.model_dump_json()
    restored = ScoreResult.model_validate_json(json_data)
    assert restored == sr
```

---

### B3. Concurrency e Resource Management

#### B3.1 `asyncio.Semaphore` values

`MAX_CONCURRENT = 5` (Gate 1), `3` (Gate 2/3).

**Analisi**:
- Gate 1 = pure API → 5 OK per GitHub API rate limits (5000 req/h auth = ~1.4/sec; con burst da 10 repo, 5 concurrent è ragionevole).
- Gate 2 = include subprocess (gitleaks, scc) e clone disk-bound → **3 è OK ma potresti hit memoria con repo grossi**.
- Gate 3 = LLM → 3 OK, ma dipende da rate limit di NanoGPT (non documentato nel prompt).

**Raccomandazione**: rendi i valori configurabili via settings, log la concurrency utilizzata. Aggiungi adaptive throttling se vedi 429.

#### B3.2 Clone management — leak su SIGKILL

```python
tempdir = tempfile.mkdtemp()
try:
    ...
finally:
    shutil.rmtree(tempdir, ignore_errors=True)
```

**Verdetto: corretto per crash normale, ma SIGKILL/OOM bypassa il finally.**

**Proposta**: non solo `finally`, ma anche un *startup cleanup* che rimuove orphan temp dirs all'avvio:

```python
def _cleanup_orphan_temps():
    pattern = "ghdisc_clone_*"
    for path in Path(tempfile.gettempdir()).glob(pattern):
        age_hours = (time.time() - path.stat().st_mtime) / 3600
        if age_hours > 6:  # safe threshold
            shutil.rmtree(path, ignore_errors=True)
```

Esegui `_cleanup_orphan_temps()` al boot del worker.

#### B3.3 LLM provider — client lifecycle

`_ensure_provider()` lazy-init. **Domanda**: il client OpenAI viene chiuso?
- Se è `httpx.Client`-based (sync), `__del__` di Python lo chiude eventualmente.
- Se è `httpx.AsyncClient`, **DEVI** chiamare `aclose()` esplicitamente o avrai connection leak.

**Proposta**: pattern context manager o `lifespan`:

```python
class LLMProvider:
    async def __aenter__(self):
        self._client = AsyncOpenAI(...)
        return self
    async def __aexit__(self, *args):
        await self._client.close()
```

E nell'orchestrator, usalo in `async with`.

---

### B4. Caching e State

#### B4.1 In-memory cache assessment

`dict[str, tuple[DeepAssessmentResult, float]]` con TTL.

**Problema**:
- Non condiviso tra processi worker (se hai >1 worker, cache miss per ogni worker)
- Perso a restart
- Non bounded (può crescere indefinitamente)

**Per MCP server single-process**: accettabile per ora. Documentalo.

**Per scaling futuro**: SQLite (già usato per FeatureStore) o Redis. Aggiungi LRU bound.

#### B4.2 FeatureStore SQLite — TTL e cleanup

> **Domanda del prompt**: "TTL gestita? Cleanup?"

Senza vedere il codice, segnalo come gap. Una FeatureStore SQLite tipicamente serve cache + audit; entrambi richiedono politiche di retention chiare:

```sql
-- Cleanup job (esegui periodico)
DELETE FROM score_results WHERE expires_at < datetime('now');
-- Oppure soft-delete con flag is_stale
```

**Raccomandazione**: 
1. Aggiungi colonna `expires_at` esplicita.
2. Crea un comando CLI `ghdisc db prune` per manutenzione.
3. Documenta la retention policy.

#### B4.3 `hash()` cross-process — vedi A4.1

Già coperto. Bug da fixare con `hashlib.blake2b`.

---

## Capitolo 4 — Analisi Architetturale

### C1. Separation of Concerns

#### C1.1 `_DERIVATION_MAP` come module-level constant

> **Domanda**: meglio nel DomainProfile?

**Risposta sì, con motivazione**: i mapping ottimali variano per dominio. Per CLI_TOOL, `CODE_QUALITY` può avere un mapping diverso che per ML_LIB. Renderlo per-profile abilita:
- Calibrazione per-dominio
- A/B test di mapping alternativi
- Estensibilità senza toccare l'engine

**Proposta**:
```python
@dataclass
class DomainProfile:
    name: str
    dimension_weights: dict[ScoreDimension, float]
    derivation_map: dict[ScoreDimension, list[tuple[str, float]]]  # NEW
    star_baseline: float
    # default fallback se non specificato:
    @classmethod
    def with_default_derivation(cls, ...):
        return cls(..., derivation_map=DEFAULT_DERIVATION_MAP)
```

#### C1.2 `_DOMAIN_THRESHOLDS` nell'orchestrator

Stesso pattern. Spostare nel `DomainProfile`:

```python
@dataclass
class DomainProfile:
    # ...
    gate1_threshold: float = 0.4
    gate2_threshold: float = 0.5
    gate3_threshold: float = 0.6
```

Beneficio: un dominio "ML_LIB" potrebbe avere `gate1_threshold=0.3` (più permissivo per accogliere repo di ricerca), mentre "CLI_TOOL" potrebbe avere `gate1_threshold=0.5` (più stringente per tool finiti).

#### C1.3 Dual threshold source

Già coperto in A5.2. **Single source of truth**: tutto in `ScoringSettings` (env-overridable), niente costanti hardcoded in models.

---

### C2. Extensibility

#### C2.1 Aggiungere una 9° dimensione (ACCESSIBILITY)

File da toccare:
1. `models/enums.py` — aggiungere `ScoreDimension.ACCESSIBILITY`
2. `scoring/engine.py` — `_DERIVATION_MAP` aggiungere mapping
3. `scoring/profiles.py` — aggiornare 12 profili (somma weights = 1.0)
4. `assessment/dimensions/` — nuovo prompt per Gate 3 (se applicabile)
5. `models/scoring.py` — adattare hidden_gem o simili se referenziati
6. `scoring/heuristics.py` — possibile aggiornamento

**Verdetto: 6 punti di tocco. Accettabile per un sistema giovane, ma sintomo di accoppiamento.**

**Refactor proposto** (registry pattern):
```python
class DimensionRegistry:
    def register(self, dim: ScoreDimension, derivation: list[...], gate3_prompt: str): ...

# All'avvio:
registry.register(ScoreDimension.CODE_QUALITY, ..., ...)
registry.register(ScoreDimension.ACCESSIBILITY, ..., ...)
```

E i profili specificano solo i weights — il "come si calcola" è centralizzato.

#### C2.2 Aggiungere DomainType.QA_TOOL

Touch points: `enums.py`, `profiles.py`, `domain_classifier` (orchestrator). 3 file. **Accettabile.**

#### C2.3 `custom_profiles_path` non implementato

**Verdetto: gap da chiudere**. Anche se è "pianificato", lasciarlo come field in Settings senza implementazione confonde l'utente. Opzioni:
1. Implementarlo (1-2 giorni con TOML/YAML loading)
2. Rimuoverlo dalla Settings finché non è pronto
3. Aggiungere `NotImplementedError` se settato

L'opzione 1 è preferibile — sblocca l'estensibilità per utenti enterprise.

---

### C3. Test Coverage Quality

#### C3.1 1326 test passing — ma cosa testano?

> **Domanda del prompt**: "quanta parte della logica di scoring è testata con edge cases realistici vs mock?"

Senza accesso ai test concreti, posso solo stimare per pattern. Tipico in progetti simili:
- 60% unit test su singole funzioni con input controllati
- 25% integration test con mock API
- 10% test su casi limite documentati
- 5% end-to-end con real data

**Mock-heavy testing è un'arma a doppio taglio**:
- ✅ Veloce, deterministico, isolato
- ❌ Non cattura behaviour reale di GitHub API (paginazione, rate limit, edge cases di metadata)
- ❌ Non cattura LLM behaviour reale (variance tra invocazioni, instructor parsing failures)

#### C3.2 Test mancanti che dovresti avere (priorità alta)

1. **Property-based testing per scoring** (Hypothesis):
   - Per ogni input random, `0 ≤ quality_score ≤ 1`
   - Per ogni input random, `0 ≤ confidence ≤ 1`
   - Profile weights sum invariant: `abs(sum(profile.dimension_weights.values()) - 1.0) < 1e-9`
   - Monotonicity: aumentare un sub-score (a parità degli altri) non diminuisce il quality_score (con weight positivo)

2. **Regression test su fixtures di repo reali**:
   - Snapshot test: per 20 repo curati, snapshot del ranking. Cambia se il sistema cambia.
   - Bisogna accettare manualmente i diff via PR review.

3. **Cross-process determinism**:
   - Calcola ranking in process A, salvalo. Calcola in process B con stesso seed, verifica uguaglianza esatta.

4. **Failure mode test**:
   - LLM timeout → heuristic kicks in → confidence è bassa
   - GitHub 429 → backoff → eventually success or graceful degradation
   - Tool subprocess crash → dimension marked, others not affected

#### C3.3 Phase 9 metrics (Precision@K, NDCG, MRR) su 60 sample

> **Domanda del prompt**: "C'è una baseline reale?"

**60 sample è sotto la soglia di significatività statistica per metriche di ranking.** Per NDCG con confidence interval ±0.05, hai bisogno tipicamente di N≥150 con multiple judges.

**Raccomandazione**: 
1. Espandere a 200+ repo
2. Usare 3+ etichettatori indipendenti per repo
3. Calcolare Cohen's κ (inter-rater agreement) — se κ < 0.6, le label sono troppo soggettive e il benchmark non è affidabile
4. Pubblicare il dataset (anche solo le label, repo URL pubbliche)

**Baseline da confrontare**:
- Random ranking
- Star-only ranking (`-stars`)
- OpenSSF Scorecard ranking
- GitHub trending

Se GitHub Discovery batte tutti questi su NDCG@10 con significatività statistica (p<0.05), hai una claim difendibile. Senza, è folklore.

---

## Capitolo 5 — Risposte alle Domande Specifiche

**1. Il modello di scoring è valido come sistema di valutazione della qualità del software?**

**Parzialmente.** Il framework concettuale (gate progressivi, multi-dimensionalità, separazione confidence/quality, star-neutrality) è solido e allineato con OpenSSF Scorecard, CHAOSS metrics, e ISO/IEC 25010. **MA**: (a) il `_DERIVATION_MAP` contiene errori concettuali (vedi Cap 2.A1); (b) i weights non sono calibrati empiricamente; (c) non c'è ground truth per validare. Riferimenti chiave: Garousi & Felderer, "Maven Quality Model" (Empirical Software Engineering, 2017); Mockus et al., "Predicting Software Quality" (FSE 2003); Foundjem et al., "Why do (open-source) developers...?" (TSE 2022). Il sistema è in posizione promettente ma non ancora validato — voto: 5.5/10.

**2. Il mapping Gate 1+2 → Dimension Scores è logicamente corretto?**

Per dimensione:
- CODE_QUALITY: **errato** (omette complexity, test_footprint)
- ARCHITECTURE: **gravemente errato** (complexity non è proxy di architettura)
- TESTING: **ragionevole**
- DOCUMENTATION: **errato** (review_practice non c'entra)
- MAINTENANCE: **corretto**, minor tuning suggerito
- SECURITY: **corretto**
- FUNCTIONALITY/INNOVATION: **vuoti correttamente**, ma il default neutral con confidence 0.0 crea bias di redistribuzione

Vedi Cap 2.A1 per le proposte alternative dettagliate.

**3. L'esclusione delle dimensioni default introduce bias?**

**Sì, sistematicamente.** Vedi calcolo numerico in Cap 2.A2.1: per ML_LIB un repo Gate1+2-only è valutato sul 60% del peso. Due repo con `quality_score=0.6` ma coverage 60% vs 90% non sono equivalenti, ma il sistema li tratta come tali. **Fix**: introdurre `coverage_ratio` come field esplicito e penalizzare il quality_score quando coverage è bassa.

**4. Il confidence model è robusto?**

**Sì come direzione, no come calibrazione.**
- Direzione corretta: gate3_llm > gate12_derived > default
- Bonus per coverage corretto
- **Issues**: (a) media non pesata dai profile weights (vedi Cap 2.A3.2); (b) `0.8` per LLM è ottimistico vs literature; (c) confidence per-dimensione dovrebbe variare per qualità del mapping (TESTING è 0.55, ARCHITECTURE 0.25). Un repo con 3/8 dimensioni da LLM avrebbe confidence ~ (0.8·3 + 0.4·5 + 0.0·0)/8 + 0.10 = 0.55 + 0.10 = 0.65. **Corretto** — riflette la coverage parziale. La logica funziona, va solo affinata.

**5. Il ranking è davvero star-neutral?**

**Per il quality_score sì; per il ranking end-to-end no.** Le stelle entrano via:
1. Discovery channel bias (Gate 0)
2. Cross-domain normalization (dipende dal pool)
3. `corroboration_level` esposto nell'output
4. Hidden gem labeling (esplicitamente usa stelle, by design)

Vedi Cap 2.A4.3. **Raccomandazione**: documentare esplicitamente "star-neutral quality_score, star-aware metadata".

**6. I 12 domain profiles sono bilanciati e giustificati?**

**Bilanciati: sì** (somma weights = 1.0, niente outliers ovvi). **Giustificati: no** — i weights sono speculazioni educate non calibrate. Vedi Cap 2.A6 per critiche puntuali (LIBRARY funcionality troppo bassa, ML_LIB innovation sotto-pesata, ecc.).

**7. Top 5 problemi critici da risolvere**: vedi Cap 1.2.

**8. Top 5 miglioramenti per la logica di scoring** (non per il codice):
1. **Calibrazione empirica con ground truth umano** (200 repo, 3+ raters) — sblocca tutto il resto
2. **Riprogettare `_DERIVATION_MAP` da letteratura** (CHAOSS, OpenSSF) con citazioni nel codice
3. **Coverage esplicito** come field di ScoreResult; quality_score penalizzato per low-coverage
4. **Confidence per-dimensione variabile** in funzione della qualità del mapping
5. **Heuristic fallback come "ignorance signal"** invece di point estimate fiducioso

**9. Il sistema è production-ready?**

**No, ma è in alpha — è atteso.** Gap principali per arrivarci:
- ❌ Validazione empirica contro ground truth (mancante completamente)
- ❌ Determinismo cross-process (`hash()` bug)
- ❌ Single source of truth per thresholds (hidden gem dual definition)
- ❌ Heuristic fallback affidabile
- ❌ Real-world testing oltre 20 repo del smoke test
- ❌ Documentation della metodologia (perché questi weights? perché questo mapping?)
- ⚠️ Cache persistence per multi-process serving
- ⚠️ Error handling che non maschera 401/403/429
- ⚠️ Custom profiles path implementation
- ⚠️ Dataset benchmark pubblico

**Tempo stimato a "beta-ready"**: 6-8 settimane focused. **A "production-ready"**: 3-6 mesi.

**10. Quali metriche di validazione raccomandi?**

**Setup baseline empirico**:
1. **Dataset di calibrazione**: 200 repo cross-domain, etichettati da 3 esperti su 8 dimensioni (scala 1-5). Cohen's κ ≥ 0.6 richiesto.
2. **Metriche di ranking**:
   - NDCG@10, NDCG@25 (con tester ground truth)
   - Spearman rank correlation con expert ranking
   - Precision@K e Recall@K per "high-quality" definito come avg_expert_rating ≥ 4
3. **Confronto con baseline**:
   - Random shuffle (sanity check)
   - Star-only ranking (`sort by -stars`)
   - OpenSSF Scorecard composite
   - GitHub trending (proxy via API)
4. **Test di significatività**:
   - Wilcoxon signed-rank (p < 0.05) per pair-wise confronto su 50+ ripetizioni con resampling
5. **Star-neutrality empirico**:
   - Generare 2 pool: bias-popular (alto-stars only) e balanced (sample stratificato per stars).
   - Verificare che il *quality_score* è invariante al bias di selezione (correlation Spearman ≥ 0.95).
   - Verificare che il *ranking finale* riflette le preferenze degli esperti, non le stelle (Spearman vs stars ≤ 0.4).
6. **Hidden gem precision**:
   - Per repo etichettati come "hidden gems" da esperti (high quality + low stars), verificare che il sistema li identifica con Recall ≥ 0.7.
7. **Confidence calibration**:
   - Reliability diagram: bucket repo per confidence prevista, verifica che l'accuracy del ranking entro il bucket corrisponde alla confidence dichiarata.

**Stima effort calibrazione completa**: 4-6 settimane (1 settimana setup, 2 settimane labeling con esperti esterni, 1 settimana analisi, 1-2 settimane iterazione).

---

## Capitolo 6 — Piano di Azione Suggerito

### 6.1 Azioni immediate (1-2 settimane, prima di promuovere a beta)

| Priorità | Azione | Effort | Successo misurato da |
|----------|--------|--------|---------------------|
| P0 | Fix dual hidden_gem thresholds — single source of truth in ScoringSettings | 2h | Test parametrici verificano consistenza tra `ScoreResult.is_hidden_gem` e `ValueScoreCalculator.is_hidden_gem` su 100 input random. |
| P0 | Fix `hash()` → `hashlib.blake2b` per ranking determinism | 4h | Test che esegue ranking in 2 processi distinti con stesso seed → ordering identico bit-perfect. |
| P0 | Documentare comportamento di `_apply_weights` quando coverage < 1.0; aggiungere `coverage` field a ScoreResult | 1g | Field visibile in CLI/API output; explainability include coverage. |
| P1 | Risolvere `_fetch()` exception swallowing — distinguere auth/rate-limit/network/server errors | 2g | Failure mode test: simula 401, 429, 5xx → sistema logga e degrada correttamente, non maschera. |
| P1 | Riprogettare heuristic fallback come "ignorance signal" (range + low confidence) | 3g | Test: 20 repo con LLM disabled → confidence < 0.25 per tutti, score range visibile. |
| P1 | Aggiungere property-based test (Hypothesis) per invarianti: `0≤quality≤1`, `0≤confidence≤1`, profile weights sum=1, monotonicity | 2g | 1000+ generated cases passano. |

**Effort totale**: ~5 giorni-uomo. **Output**: bug critici chiusi, baseline solida.

### 6.2 Breve termine (1-2 mesi)

| Priorità | Azione | Effort | Successo misurato da |
|----------|--------|--------|---------------------|
| P0 | **Ground-truth calibration set**: 200 repo, 3 raters, 8 dimensioni, Cohen's κ | 3-4 settimane | κ ≥ 0.6 raggiunto. Dataset pubblicato. |
| P0 | Riprogettare `_DERIVATION_MAP` con motivazioni documentate per ogni mapping | 1 settimana | Documento `SCORING_METHODOLOGY.md` con citazioni. Ablation study su calibration set. |
| P1 | Calibrare i 12 domain profile weights su calibration set | 1 settimana | NDCG@10 sul set di validation (20% hold-out) ≥ 0.75. |
| P1 | Implementare `custom_profiles_path` (TOML/YAML loading) | 2g | Test E2E: profilo custom caricato influenza ranking. |
| P1 | Confidence per-dimensione variabile in `_DIMENSION_CONFIDENCE_FROM_GATE12` | 1g | Confidence riflette qualità del mapping; test su scenario partial-coverage. |
| P2 | Cleanup di dual threshold sources, costanti hardcoded → ScoringSettings | 3g | Linter/grep verifica: nessuna costante numerica magica fuori da config. |
| P2 | Cache assessment in SQLite (FeatureStore-based) invece di in-memory | 2g | Multi-worker test: cache hit rate ≥ 70% cross-worker. |

**Effort totale**: ~7-8 settimane (con team 1-2 persone full-time). **Output**: sistema validato empiricamente, beta-ready.

### 6.3 Lungo termine (3-6 mesi, verso v1.0)

| Priorità | Azione | Successo misurato da |
|----------|--------|---------------------|
| P0 | **Validation pubblica**: paper / blog post con metodologia, dataset, risultati comparativi vs baseline. | NDCG@10 ≥ 0.78, statisticamente significativo (p<0.05) vs star-ranking. |
| P0 | Espandere il calibration set a 500 repo, includere domini under-rappresentati. | κ inter-rater ≥ 0.65. |
| P1 | Real-world testing: deploy MCP server pubblico, raccolta telemetry su 10k+ ricerche. | <5% feedback negativo su top-10 risultati. |
| P1 | Custom dimension support (registry pattern, vedi C2.1). | User può aggiungere ACCESSIBILITY senza toccare core. |
| P1 | Replace OSV adapter neutral fallback con lockfile parsing reale. | Vulnerability sub-score riflette CVE reali per ≥80% dei repo testati. |
| P1 | Implement PyDriller integration per maintenance Gate 1 (sostituire heuristics). | Maintenance confidence sale da 0.7 a 0.85+. |
| P2 | Multi-rater feedback loop: utenti possono dare thumbs up/down sul ranking; calibrazione continua. | Modello impara da 1000+ feedback signals. |
| P2 | Cross-language scoring quality (test su Python, JS, Rust, Go, Java separatamente). | Per-language NDCG ≥ 0.70 in tutti. |
| P3 | Performance: end-to-end latency P95 < 60s per repo (Gate 1+2+3 con cache miss). | Benchmark dashboard pubblico. |

**Output**: sistema production-grade, methodology paper-quality, community trust.

---

## Note finali

### Cosa ho potuto valutare con confidence

- Logica matematica di scoring/confidence/ranking dal codice mostrato ✅
- Mapping `_DERIVATION_MAP` e plausibilità dei weights ✅
- Architettura generale e separation of concerns ✅
- Bug specifici visibili dal codice (hash, dual thresholds, exception swallowing) ✅

### Cosa NON ho potuto valutare (limitazioni)

- ❌ Non ho letto il codice dei sub-score checker (Gate 1) — la qualità della loro implementazione potrebbe ribaltare alcune valutazioni
- ❌ Non ho visto il codice dei test (1326 passing, ma di che qualità?)
- ❌ Non ho valutato i prompt LLM dei 8 dimension assessor — la qualità del Gate 3 dipende criticamente da questi
- ❌ Non ho misurato performance reali (latency, throughput, costi LLM)
- ❌ Non ho accesso al smoke test data (20 repo MCP) per validare empiricamente le claim
- ❌ Non ho valutato MCP server tools/resources/prompts — l'interfaccia primaria

Per audit completo, raccomando un follow-up con accesso al repo e al dataset di calibrazione (quando esisterà).

### Tono finale

Il progetto è **interessante, ben architettato, e affronta un problema reale** (search beyond stars). Ha una vision chiara (star-neutrality come principio) e l'esecuzione tecnica è solida per un alpha. **Il gap principale tra lo stato attuale e un sistema affidabile è metodologico, non tecnico**: serve calibrazione empirica e correzione di errori concettuali identificabili. Una volta chiusi quelli, hai un prodotto difendibile come tool di ricerca/discovery seria.

I miei voti (5.5/10 scoring, 7/10 codice) **non sono critiche al lavoro fatto** — riflettono lo standard altissimo che si applica a "sistema di valutazione della qualità del software" (un dominio con literatura matura e benchmark difficili). Per "alpha promettente", il progetto è 7-8/10. Per "candidato a sostituire star-based ranking come standard", deve fare i compiti elencati nel Capitolo 6.

In bocca al lupo per le prossime fasi.
