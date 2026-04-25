# GitHub Discovery — Analisi Completa dell'Architettura

> **Data**: 2026-04-25
> **Versione analizzata**: v0.1.0-alpha (Phases 0-9 complete, 1326 test, `make ci` green)
> **Tipo**: Report architetturale descrittivo, in italiano
> **Fonti**: Foundation Blueprint, LLM Wiki (45 articoli), codebase (107 file Python), doc ufficiali Kilocode/Claude Code/OpenCode MCP

---

## 1. Panoramica del Progetto

GitHub Discovery è un **motore di discovery agentico MCP-native** che trova repository GitHub di alta qualità tecnica indipendentemente dalla popolarità (stelle, buzz sociale). A differenza dei canali tradizionali (GitHub Search, trend dashboard, blog), il sistema separa deliberatamente la qualità ingegneristica dal successo sociale, utilizzando una pipeline di scoring a 4 livelli: **Discovery → Screening leggero → Valutazione LLM profonda → Ranking spiegabile**.

### 1.1 Problema Risolto

I canali di discovery attuali (search engine, AI agent, trend dashboard) tendono a sovra-pesare:
- **Star count** — repos popolari dominano i risultati indipendentemente dalla qualità
- **Segnali social** — Reddit, blog, discussioni amplificano progetti già visibili
- **Momentum mediatico** — trend temporanei oscurano progetti solidi ma silenziosi

L'effetto: repository tecnicamente eccellenti ma poco visibili (0-50 stelle) restano completamente fuori dal radar. GitHub Discovery inverte questa dinamica.

### 1.2 Criteri Guida

| Criterio | Descrizione |
|----------|-------------|
| **Star-neutrality** | Le stelle sono metadati di corroborazione, mai un segnale primario di ranking |
| **Technical-first** | Enfasi su codice, architettura, test, manutenzione, sicurezza |
| **Explainability** | Ogni score deve essere spiegabile per dimensione, con punti di forza/debolezza |
| **Domain-aware** | Pesi e soglie diverse per libreria, framework, CLI, backend, ML, devops |
| **Cost-aware** | Pipeline a livelli (cheap→deep) per ridurre i costi di analisi profonda |
| **MCP-native** | Integrabile nativamente in workflow agentici (Claude Code, Kilocode, OpenCode) |

---

## 2. La Pipeline a 4 Gate — Cuore dell'Architettura

La pipeline è il nucleo strutturale del sistema. Quattro livelli progressivamente più costosi riducono un pool iniziale ampio a una shortlist di candidati valutati in profondità. La **regola ferrea** (`hard gate enforcement`) è inviolabile: **nessun candidato raggiunge il Gate 3 senza aver superato Gate 1 + Gate 2**.

```
┌──────────────────────────────────────────────────────────────────┐
│                     PIPELINE COMPLETA                             │
│                                                                   │
│  Gate 0              Gate 1            Gate 2          Gate 3     │
│  DISCOVERY  ──────►  METADATA  ──────► STATIC/ ──────► DEEP LLM  │
│  (6 canali)          SCREENING         SECURITY        ASSESSMENT │
│  ★ costo: basso      (7 sub-score)     (4 sub-score)   ★ costo:   │
│  ★ LLM: no           ★ LLM: no         ★ LLM: no        ALTO      │
│  ★ output:           ★ output:         ★ output:       ★ output:  │
│    RepoCandidate       MetadataScrRes    StaticScrRes    DeepAssess│
│                           │                  │               │    │
│                           └──────────────────┘               │    │
│                                    │                         │    │
│                              HARD GATE ──────────────────────┘    │
│                        (gate1_pass AND gate2_pass)                │
│                                                                   │
│                                      ▼                            │
│                              LAYER D: SCORING & RANKING           │
│                              ★ ScoringEngine (pesato dominio)     │
│                              ★ ValueScoreCalculator (★-neutral)   │
│                              ★ Ranker (quality DESC, deterministico)│
│                              ★ ExplainabilityGenerator            │
└──────────────────────────────────────────────────────────────────┘
```

### 2.1 Gate 0 — Candidate Discovery (Layer A)

**Obiettivo**: Raccogliere un pool ampio e diversificato di repository candidati, riducendo il bias di popolarità intrinseco di ogni singola fonte.

**Modulo**: `src/github_discovery/discovery/` (6 canali, 2 client, 1 orchestratore, 1 pool manager)

#### I 6 Canali di Discovery

| # | Canale | Classe | Funzionamento | Bias Mitigato |
|---|--------|--------|---------------|---------------|
| 1 | **GitHub Search API** | `SearchChannel` | Query strutturate con filtri avanzati (topic, linguaggio, data, dimensione). Ordina per `updated` invece di `stars`. | Popularità delle search |
| 2 | **GitHub Code Search** | `CodeSearchChannel` | Cerca pattern di qualità nei file (`pytest`, `CI.yml`, type hints). | Bias di popolarità più basso della search normale |
| 3 | **Dependency Graph** | `DependencyChannel` | Naviga il grafo delle dipendenze a partire da seed repositories. | Mitigato da seed curati e pesatura qualità |
| 4 | **Package Registry** | `RegistryChannel` | Mappa pacchetti npm/PyPI/crates.io/Maven → repository GitHub. | Download-count meno distorto delle stelle |
| 5 | **Awesome Lists** | `CuratedChannel` | Parsing di README di awesome-X, liste curate dalla comunità. | Curation bias mitigato combinando multiple liste |
| 6 | **Seed Expansion** | `SeedExpansion` | Co-contributor analysis, org adjacency, co-dependency. | Network proximity bias mitigato da profondità limitata |

#### Flusso dell'Orchestratore (`DiscoveryOrchestrator`)

```
1. Risoluzione canali: query dell'agente → canali da attivare
2. Esecuzione parallela: tutti i canali attivi eseguiti concorrentemente
   (con asyncio.Semaphore per rate limiting)
3. Deduplicazione: per full_name, mantiene il discovery_score più alto
4. Scoring bonuses:
   - breadth_bonus: +0.1 per ogni canale extra oltre il primo
   - channel_quality: awesome_list +0.1, dependency +0.1, code_search +0.05
5. Ordinamento: discovery_score DESC
6. Troncamento: a max_candidates dalla configurazione (default: 1000)
7. Persistenza: PoolManager (SQLite via aiosqlite, `.ghdisc/pools.db`)
```

**Output**: `RepoCandidate` — il modello centrale che fluisce attraverso tutti i gate (~40 campi: identità, metadati, segnali di contesto, stato pipeline, canale di origine, discovery_score).

### 2.2 Gate 1 — Metadata Screening (Layer B, prima metà)

**Obiettivo**: Valutare 7 dimensioni di qualità usando esclusivamente metadati dell'API GitHub. **Costo LLM: zero**. Nessun clone, nessun tool esterno.

**Modulo**: `src/github_discovery/screening/gate1_metadata.py` (+ 7 checker)

#### I 7 Sub-Score del Gate 1

| # | Checker | File | Cosa Valuta | Segnali |
|---|---------|------|-------------|---------|
| 1 | **HygieneChecker** | `hygiene.py` | File di igiene del progetto | `LICENSE`, `README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md` |
| 2 | **MaintenanceAnalyzer** | `maintenance.py` | Salute della manutenzione | Recency commit, cadenza, bus factor (contributor count), issue resolution rate |
| 3 | **ReleaseDisciplineScorer** | `release_discipline.py` | Disciplina di release | Tag semver, cadenza release, changelog versionati |
| 4 | **PracticesScorer** | `practices.py` | Buone pratiche | PR templates, code review, usage label, branch protection |
| 5 | **TestFootprintAnalyzer** | `test_footprint.py` | Presenza e qualità dei test | Directory `tests/`, framework rilevati (pytest, jest, etc.), rapporto test/sorgente |
| 6 | **CiCdDetector** | `ci_cd.py` | Integrazione continua | `.github/workflows/`, badge CI nel README, coverage reporting |
| 7 | **DependencyQualityScorer** | `dependency_quality.py` | Gestione dipendenze | Lockfiles, version pinning, Dependabot/Renovate config |

#### Flusso `Gate1MetadataScreener.screen()`

```
1. gather_context(): 7 chiamate API parallele (repo meta, contents, releases,
   commits, issues, PRs, linguaggi) con asyncio.Semaphore(5)
2. Auto-fail: repo archiviati o disabilitati → gate1_pass=False immediato
3. Esecuzione 7 checker con error isolation (_safe_score):
   ogni checker wrappato in try/except → fallback zero-value in caso di errore
4. Costruzione MetadataScreenResult con tutti i sub-score
5. Calcolo totale pesato e confronto con soglia (default: 0.4)
6. Domain-specific thresholds: SECURITY_TOOL gate1=0.6, altri domini hanno valori propri
```

**Output**: `MetadataScreenResult` con `gate1_total`, `gate1_pass`, 7 sub-score tipizzati.

### 2.3 Gate 2 — Static & Security Screening (Layer B, seconda metà)

**Obiettivo**: Valutare sicurezza e complessità con tool esterni su un clone superficiale del repository. **Costo: zero/basso** (nessun LLM). Tool non disponibili → degradazione graceful, mai blocco della pipeline.

**Modulo**: `src/github_discovery/screening/gate2_static.py` (+ 4 adapter)

#### I 4 Sub-Score del Gate 2

| # | Adapter | File | Tool | Cosa Valuta |
|---|---------|------|------|-------------|
| 1 | **ScorecardAdapter** | `scorecard_adapter.py` | OpenSSF Scorecard API | Branch protection, workflow security, token permissions, signed releases, SAST, fuzzing |
| 2 | **OsvAdapter** | `osv_adapter.py` | OSV API (HTTP POST) | Vulnerabilità note nelle dipendenze, severity scoring |
| 3 | **SecretsChecker** | `secrets_check.py` | gitleaks (subprocess) | Secreti leaked nel codice (API key, token, password) |
| 4 | **ComplexityAnalyzer** | `complexity.py` | scc/cloc (subprocess) | LOC per linguaggio, breakdown linguaggi, complessità strutturale |

#### Flusso `Gate2StaticScreener.screen()`

```
0. Controllo hard gate: se gate1_pass è False → HardGateViolationError
1. Shallow clone: git clone --depth=1 in directory temporanea (120s timeout)
2. Esecuzione 4 tool in parallelo con error handling individuale:
   ogni fallimento → fallback score 0.3 con confidence ridotta
3. Costruzione StaticScreenResult con tutti i sub-score
4. Calcolo totale e confronto con soglia (default: 0.5)
5. Pulizia: shutil.rmtree del clone in blocco finally
```

**Output**: `StaticScreenResult` con `gate2_total`, `gate2_pass`, 4 sub-score, `tools_used`, `tools_failed`.

**Nota sulla degradazione graceful**: Se gitleaks non è installato, il SecretsChecker restituisce un punteggio neutro (0.3) con confidence=0.0, e la pipeline continua. Lo stesso vale per scc e per le API OSV/Scorecard in caso di timeout.

### 2.4 Gate 3 — LLM Deep Assessment (Layer C)

**Obiettivo**: Valutazione tecnica profonda tramite LLM sulle 8 dimensioni di qualità. **Costo: alto** — solo per i candidati top percentile che hanno superato entrambi i gate precedenti.

**Modulo**: `src/github_discovery/assessment/` (orchestratore, LLM provider, repomix adapter, heuristic analyzer, result parser, budget controller, 8 prompt templates, language analyzers)

#### Pipeline a 8 Step di `AssessmentOrchestrator`

```
1. HARD GATE CHECK
   Verifica gate1_pass AND gate2_pass → HardGateViolationError se fallito

2. CACHE CHECK
   FeatureStore lookup per commit SHA → skip se già valutato (TTL configurabile)

3. BUDGET CHECK (BudgetController)
   Per-repo: max 50,000 token | Per-giorno: max 500,000 token
   Sforamento → BudgetExceededError

4. REPOMIX PACK (RepomixAdapter)
   Download + packing codebase via python-repomix RepoProcessor
   Config: compressione, esclusioni (node_modules, .git, venv, etc.)

5. HEURISTIC SCORING (HeuristicAnalyzer)
   Baseline zero-LLM: 7 metodi di detection strutturale dal contenuto packed
   (struttura directory, pattern di codice, presenza di test inline, etc.)

6. LLM ASSESSMENT (LLMProvider)
   Provider: NanoGPT (OpenAI-compatible) via openai + instructor
   Modalità batch: una singola chiamata LLM per tutte le 8 dimensioni
   Modalità per-dimensione: chiamate individuali (fallback se batch fallisce)
   Structured output: Pydantic models via response_format json_schema

7. RESULT PARSING (ResultParser)
   LLM output → DeepAssessmentResult con 8 DimensionScore tipizzati
   Fallback euristico se il parsing LLM fallisce

8. BUDGET RECORDING
   Tracciamento token usati, salvataggio in cache (FeatureStore)
```

#### Le 8 Dimensioni di Valutazione

| Dimensione | Peso Default | Prompt | Dominio Focus |
|------------|-------------|--------|---------------|
| **code_quality** | 20% | `prompts/code_quality.py` | Leggibilità, complessità, pattern, best practices |
| **architecture** | 15% | `prompts/architecture.py` | Modularità, separazione concerns, design pattern |
| **testing** | 15% | `prompts/testing.py` | Copertura, tipi di test, qualità suite test |
| **documentation** | 10% | `prompts/documentation.py` | README, API docs, esempi, commenti inline |
| **maintenance** | 15% | `prompts/maintenance.py` | Attività, risoluzione issue, aggiornamento dipendenze |
| **security** | 10% | `prompts/security.py` | Vulnerabilità, sanitizzazione input, dipendenze sicure |
| **functionality** | 10% | `prompts/functionality.py` | Completezza funzionale, API design, gestione errori |
| **innovation** | 5% | `prompts/innovation.py` | Novità approccio, originalità soluzione |

Ogni dimensione ha un prompt specializzato e, per 10 combinazioni dominio+dimensione, aggiustamenti `_DOMAIN_FOCUS` che orientano la valutazione LLM (es. security_tool+security → enfasi su audit supply chain).

**Output**: `DeepAssessmentResult` con 8 `DimensionScore`, `overall_quality`, `gate3_pass`, `token_usage`.

---

## 3. Il Sistema di Scoring e Ranking Star-Neutral (Layer D)

### 3.1 Filosofia Star-Neutral

Il sistema ha subito un'evoluzione fondamentale il 25 aprile 2026. La formula originale anti-star bias (`quality_score / log10(stars + 10)`) è stata sostituita da un approccio **star-neutral**:

**Prima (anti-star bias)**:
```
value_score = quality_score / log₁₀(stars + 10)
→ penalizza attivamente i repo popolari
```

**Dopo (star-neutral)**:
```
value_score = quality_score
→ le stelle sono puramente metadati di corroborazione
```

Il principio guida: **dividere per la popolarità è ancora bias, solo nella direzione opposta**. Nessun sistema di ranking mainstream (IMDB, Stack Overflow, Google Scholar) penalizza la popolarità — la tratta come segnale separato. GitHub Discovery fa lo stesso.

### 3.2 Componenti del Layer D

**Modulo**: `src/github_discovery/scoring/` (10 file)

| Componente | File | Ruolo |
|------------|------|-------|
| **ScoringEngine** | `engine.py` | Combina Gate 1+2+3 in score compositi multi-dimensionali |
| **ProfileRegistry** | `profiles.py` | 11 profili di pesi per dominio (LIBRARY, CLI, DEVOPS, BACKEND, WEB_FRAMEWORK, DATA_TOOL, ML_LIB, SECURITY_TOOL, LANG_TOOL, TEST_TOOL, DOC_TOOL) |
| **ValueScoreCalculator** | `value_score.py` | Calcolo star-neutral, hidden gem detection, star_context() |
| **ConfidenceCalculator** | `confidence.py` | Confidenza per-dimensione basata sulla fonte del segnale |
| **Ranker** | `ranker.py` | Ranking intra-dominio deterministico, identificazione hidden gem |
| **CrossDomainGuard** | `cross_domain.py` | Normalizzazione cross-dominio con avvisi |
| **ExplainabilityGenerator** | `explainability.py` | Report spiegabili: punti di forza, debolezze, raccomandazioni |
| **FeatureStore** | `feature_store.py` | Cache SQLite con TTL per score e feature |

### 3.3 Algoritmo di Scoring (`ScoringEngine.score()`)

```
Per ogni dimensione (8 totali):
  1. Se Gate 3 disponibile → usa punteggio LLM (confidence=0.8)
  2. Altrimenti deriva da Gate 1+2 (_DERIVATION_MAP):
     - code_quality: media pesata di hygiene + practices + complexity
     - architecture: proxy da maintenance + complexity
     - testing: test_footprint + ci_cd
     - documentation: hygiene
     - security: scorecard + osv + secrets
     - maintenance: maintenance + release_discipline
     - functionality: NON derivabile da screening → default 0.5
     - innovation: NON derivabile da screening → default 0.5
  3. Filtro phantom score: dimensioni con confidence ≤ 0.0 escluse dalla media

Calcolo quality_score:
  Σ (dimensione_score × peso_dominio[dimensione]) / Σ pesi_dimensioni_valide

Calcolo confidence:
  Media confidence per-dimensione + bonus gate_coverage
  (gate3_llm=0.8, gate12_derived=0.4, default=0.0)
```

### 3.4 Algoritmo di Ranking (`Ranker.rank()`)

```
1. Filtra per dominio, min_confidence, min_value_score
2. Ordina per: (-quality_score, -confidence, -seeded_hash, full_name)
   ★ STELLE MAI nella chiave di ordinamento ★
3. Assegna rank 1-based
4. Identifica hidden gem (label informativo, non modifica ranking):
   - stelle < _HIDDEN_GEM_MAX_STARS (100)
   - quality_score ≥ _HIDDEN_GEM_MIN_QUALITY (0.5)
   - nel top 25% del dominio

Tie-breaking deterministico:
  seeded_hash = hash(f"{full_name}:{ranking_seed}") — seed=42
```

### 3.5 Livelli di Corroborazione (Star Context)

5 livelli puramente informativi — mai usati per scoring o ranking:

| Livello | Range Stelle | Significato |
|---------|-------------|-------------|
| `new` | 0 | Repository sconosciuto, nessuna corroborazione sociale |
| `unvalidated` | 1-49 | Prime adozioni, validazione iniziale |
| `emerging` | 50-499 | Comunità in crescita |
| `validated` | 500-4,999 | Ampia adozione, qualità percepita confermata |
| `widely_adopted` | 5,000+ | Adozione di massa |

### 3.6 Validazione E2E del Sistema Star-Neutral

Il 25 aprile 2026 è stata eseguita una validazione completa con 20 repository reali (query "mcp office"):

```
Risultati dopo pipeline completa (discover → screen Gate 1+2 → deep-eval Gate 3 → rank):

1. PsychQuant/che-word-mcp:  quality=0.703, stars=0,    hidden gem 💎
2. modelcontextprotocol/typescript-sdk: quality=0.672, stars=12281, widely_adopted
3. walksoda/crawl-mcp:      quality=0.653, stars=0,    hidden gem 💎
```

Due repository con **zero stelle** si sono classificati al primo e terzo posto, sopra un repo con 12,281 stelle, perché la loro qualità tecnica profonda (valutata dal Gate 3 LLM) era superiore. Questo conferma che il sistema funziona come progettato: **la qualità tecnica, non la popolarità, determina il ranking**.

---

## 4. Architettura MCP-Native — L'Interfaccia Primaria

### 4.1 Principi Fondamentali

GitHub Discovery è progettato come **sistema agentico MCP-native**, non come app standalone:

| Principio | Implementazione |
|-----------|-----------------|
| **MCP è l'interfaccia primaria** | 16 tool, 4 risorse, 5 prompt — la REST API è un'interfaccia secondaria |
| **Progressive Deepening** | Ogni gate è un tool MCP indipendente. L'agente decide quando approfondire, non la pipeline |
| **Agent-Driven Policy** | Soglie di gating sono parametri dei tool (`min_gate1_score=0.6`), non costanti hardcoded |
| **Session-Aware** | `session_id` abilita workflow cross-sessione (discovery in sessione 1, screening in sessione 2) |
| **Context-Efficient** | Output summary-first (< 2000 token default), con riferimento `detail_available_via` |
| **Composable con GitHub MCP** | Discovery aggiunge solo scoring/ranking — non duplica operazioni GitHub standard |

### 4.2 Inventario Completo dei Tool MCP (16 tool)

**Modulo**: `src/github_discovery/mcp/tools/` (5 file)

#### Discovery Tools (3)

| Tool | Parametri Chiave | Funzione |
|------|-----------------|----------|
| `discover_repos` | `query`, `channels`, `max_candidates`, `session_id` | Avvia discovery multicanale, restituisce `pool_id` |
| `get_candidate_pool` | `pool_id`, `sort_by`, `limit`, `offset` | Recupera candidati da un pool con paginazione |
| `expand_seeds` | `seed_urls`, `session_id` | Espande da seed repositories |

#### Screening Tools (3)

| Tool | Parametri Chiave | Funzione |
|------|-----------------|----------|
| `screen_candidates` | `pool_id`, `gate_level`, `min_gate1_score`, `min_gate2_score`, `session_id` | Screening Gate 1 e/o Gate 2 su un pool |
| `get_shortlist` | `pool_id`, `min_discovery_score`, `domain` | Filtra pool per shortlist |
| `quick_screen` | `repo_url`, `gate_level` | Screening veloce su singolo repo |

#### Assessment Tools (3)

| Tool | Parametri Chiave | Funzione |
|------|-----------------|----------|
| `deep_assess` | `repo_urls`, `session_id` | Valutazione LLM profonda (Gate 3) — applica hard gate automaticamente |
| `quick_assess` | `repo_url`, `dimensions` | Valutazione LLM su dimensioni selezionate |
| `get_assessment` | `repo_url` | Verifica stato cache della valutazione |

#### Ranking Tools (3)

| Tool | Parametri Chiave | Funzione |
|------|-----------------|----------|
| `rank_repos` | `domain`, `session_id`, `min_confidence` | Ranking star-neutral intra-dominio |
| `explain_repo` | `repo_url`, `detail_level` | Report di spiegabilità (summary/full) |
| `compare_repos` | `repo_urls` | Confronto side-by-side (2-5 repo), determina vincitore |

#### Session Tools (4)

| Tool | Parametri Chiave | Funzione |
|------|-----------------|----------|
| `create_session` | `name`, `config` | Crea sessione persistente |
| `get_session` | `session_id` | Recupera stato sessione + progresso |
| `list_sessions` | `status` | Elenca sessioni |
| `export_session` | `session_id`, `format` | Esporta risultati sessione (JSON/summary) |

### 4.3 Risorse MCP (4)

| URI Template | Descrizione |
|-------------|-------------|
| `repo://{owner}/{name}/score` | Score completo di un repository |
| `pool://{id}/candidates` | Lista candidati in un pool |
| `rank://{domain}/top` | Top-ranked per dominio |
| `session://{id}/status` | Stato di una sessione |

### 4.4 Prompt Skills MCP (5)

| Skill | Workflow | Use Case |
|-------|----------|----------|
| `discover_underrated` | discover → screen → assess → rank → explain | Trova gemme nascoste in un dominio |
| `quick_quality_check` | screen → report | Valutazione rapida di un repo specifico |
| `compare_for_adoption` | screen → assess → compare | Confronto per decisione di adozione |
| `domain_deep_dive` | discover → screen → assess → domain rank | Esplorazione profonda di un dominio |
| `security_audit` | screen (Gate 2 heavy) → security assess → report | Audit di sicurezza |

### 4.5 Session Manager

Il `SessionManager` (SQLite, `.ghdisc/sessions.db`) abilita il **progressive deepening cross-sessione**:

```
Sessione 1: discover_repos("static analysis python") → pool_id=abc123
Sessione 2: screen_candidates(pool_id="abc123", gate_level="both") → 15 passano
Sessione 3: deep_assess(repo_urls=[...top 5...]) → valutazione LLM
Sessione 4: rank_repos(domain="cli") → ranking finale
```

Lo stato (`SessionState`) persiste: `pool_ids`, `screening_results`, `assessment_results`, `ranking_results`, configurazione sovrascrivibile (`SessionConfig` con soglie, budget, domini).

### 4.6 Context-Efficient Output

Tutti i tool MCP rispettano un budget di token configurabile (default: 2000 token). Pattern:

```python
# Output summary-first
result = format_tool_result(
    summary="6 repos passed Gate 1+2 screening (domain: cli)",
    data=top_5_shortlist,
    detail_available_via="get_shortlist(pool_id='...', limit=20)"
)

# Truncamento per budget
truncated = truncate_for_context(full_result, max_tokens=2000)
```

---

## 5. Integrazione con Agenti di Coding (Claude Code, Kilocode, OpenCode)

### 5.1 Architettura di Composizione

GitHub Discovery è progettato per funzionare in **composizione** con il GitHub MCP Server ufficiale. Discovery aggiunge solo scoring/ranking — le operazioni GitHub standard (browse repo, issues, PR, search) sono delegate al server ufficiale.

```
┌─────────────────────────────────────────────────────────┐
│                   AI CODING AGENT                        │
│  (Claude Code / Kilocode / OpenCode)                     │
│                                                          │
│  ┌──────────────────────┐  ┌───────────────────────────┐│
│  │ GitHub MCP Server    │  │ GitHub Discovery MCP      ││
│  │ (ufficiale GitHub)   │  │ (scoring/ranking engine)  ││
│  │                      │  │                           ││
│  │ • repos, issues, PRs │  │ • discover_repos          ││
│  │ • search, context    │  │ • screen_candidates       ││
│  │ • actions, security  │  │ • deep_assess             ││
│  │ • read-only mode     │  │ • rank_repos              ││
│  │                      │  │ • explain_repo            ││
│  └──────────────────────┘  │ • compare_repos           ││
│                             └───────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### 5.2 Kilocode CLI / Kilo Code

**Docs ufficiali**: https://kilo.ai/docs/automate/mcp/using-in-cli, https://kilo.ai/docs/features/mcp/using-mcp-in-kilo-code

**Configurazione** (`~/.config/kilo/kilo.json` o `.kilo/kilo.json`):

```json
{
  "mcp": {
    "github": {
      "type": "remote",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": {
        "X-MCP-Toolsets": "repos,issues,pull_requests,context",
        "X-MCP-Readonly": "true"
      }
    },
    "github-discovery": {
      "type": "local",
      "command": ["python", "-m", "github_discovery.mcp", "serve", "--transport", "stdio"],
      "environment": {
        "GHDISC_GITHUB_TOKEN": "{env:GITHUB_TOKEN}",
        "GHDISC_SESSION_BACKEND": "sqlite"
      }
    }
  }
}
```

**Caratteristiche Kilocode**:
- Namespace tool: `{server}_{tool}` (es. `github-discovery_discover_repos`)
- Permessi: `allow`/`ask`/`deny` con glob patterns (`github-discovery_*`)
- Supporto OAuth 2.0 per server remoti
- Marketplace: Kilo-Org/kilo-marketplace (formato `MCP.yaml`)
- `/mcps` slash command per toggle server on/off

### 5.3 Claude Code (Anthropic)

**Docs ufficiali**: https://docs.anthropic.com/en/docs/claude-code/mcp

**Configurazione** (`.mcp.json` nel progetto):

```json
{
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": {
        "Authorization": "Bearer ${GITHUB_PAT}",
        "X-MCP-Toolsets": "repos,issues,pull_requests,context",
        "X-MCP-Readonly": "true"
      }
    },
    "github-discovery": {
      "command": "python",
      "args": ["-m", "github_discovery.mcp", "serve", "--transport", "stdio"],
      "env": {
        "GHDISC_GITHUB_TOKEN": "${GITHUB_PAT}",
        "GHDISC_SESSION_BACKEND": "sqlite"
      }
    }
  }
}
```

**Comandi Claude Code**:
```bash
# Aggiungere GitHub MCP (remoto)
claude mcp add-json github '{"type":"http","url":"https://api.githubcopilot.com/mcp/","headers":{"Authorization":"Bearer YOUR_GITHUB_PAT"}}'

# Aggiungere GitHub Discovery (locale)
claude mcp add --transport stdio github-discovery \
  -e GHDISC_GITHUB_TOKEN=YOUR_GITHUB_PAT \
  -e GHDISC_SESSION_BACKEND=sqlite \
  -- python -m github_discovery.mcp serve --transport stdio
```

**Caratteristiche Claude Code**:
- Environment variable expansion: `${VAR}`, `${VAR:-default}`
- `managed-mcp.json` per controllo enterprise (allowlist/denylist)
- Reconnection automatico con exponential backoff (HTTP/SSE)
- MCP prompts disponibili come `/mcp__github-discovery__discover_underrated`
- Tool search: caricamento on-demand degli schema dei tool
- Dynamic tool updates: supporta `list_changed` notifications

### 5.4 OpenCode / OpenClaude

**Docs ufficiali**: https://opencode.ai/docs/mcp-servers/

**Configurazione** (`opencode.json`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "github": {
      "type": "remote",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": {
        "X-MCP-Toolsets": "repos,issues,pull_requests,context",
        "X-MCP-Readonly": "true"
      }
    },
    "github-discovery": {
      "type": "local",
      "command": ["python", "-m", "github_discovery.mcp", "serve", "--transport", "stdio"],
      "environment": {
        "GHDISC_GITHUB_TOKEN": "{env:GITHUB_TOKEN}",
        "GHDISC_SESSION_BACKEND": "sqlite"
      }
    }
  }
}
```

**Caratteristiche OpenCode**:
- Config merge: file multipli mergiati (non sostituiti) con precedenza ordinata
- OAuth automatic detection con Dynamic Client Registration (RFC 7591)
- Tool namespacing: `{servername}_{tool}`
- `opencode mcp auth <name>` per flusso autenticazione

### 5.5 Kilo Marketplace — Deployment

GitHub Discovery è progettato per essere pubblicato sul [Kilo Marketplace](https://github.com/Kilo-Org/kilo-marketplace) tramite un file `MCP.yaml`:

```yaml
id: github-discovery
name: GitHub Discovery
description: MCP-native agentic discovery engine che trova repository GitHub
  di alta qualità indipendentemente dalla popolarità (stelle, buzz sociale).
author: fulviocoschi
url: https://github.com/fulviocoschi/github-discovery
tags:
  - github
  - discovery
  - scoring
  - code-quality
  - hidden-gems
content:
  - name: UVX (Recommended)
    content: |
      {
        "command": "uvx",
        "args": ["github-discovery", "mcp", "serve", "--transport", "stdio"],
        "env": {
          "GHDISC_GITHUB_TOKEN": "{{GITHUB_TOKEN}}",
          "GHDISC_SESSION_BACKEND": "sqlite"
        }
      }
    prerequisites:
      - Python 3.12+
      - uv
    parameters:
      - name: GitHub Personal Access Token
        key: GITHUB_TOKEN
        placeholder: ghp_xxxxxxxxxxxxxxxxxxxx
  - name: Docker
    content: |
      {
        "command": "docker",
        "args": ["run", "-i", "--rm", "-e", "GHDISC_GITHUB_TOKEN", "ghcr.io/fulviocoschi/github-discovery:latest"],
        "env": {
          "GHDISC_GITHUB_TOKEN": "{{GITHUB_TOKEN}}"
        }
      }
    prerequisites:
      - Docker
    parameters:
      - name: GitHub Personal Access Token
        key: GITHUB_TOKEN
        placeholder: ghp_xxxxxxxxxxxxxxxxxxxx
```

Il marketplace offre 3 opzioni di installazione: UVX (raccomandato, zero install), Docker, e streamable-http (per deploy remote).

---

## 6. Struttura Completa del Codice

### 6.1 Panoramica

Il progetto consiste di **107 file Python** organizzati in **16 moduli** sotto `src/github_discovery/`. Ogni fase della pipeline ha il proprio package:

```
src/github_discovery/
├── config.py              # Pydantic-settings: 8 classi di configurazione
├── exceptions.py          # Gerarchia eccezioni: 14 classi
├── logging.py             # Structured logging (structlog)
├── __main__.py            # Entry point: python -m github_discovery
│
├── models/                # 9 file — ~60 modelli Pydantic v2
│   ├── enums.py           # 6 enum (DomainType, GateLevel, ScoreDimension, ...)
│   ├── candidate.py       # RepoCandidate, CandidatePool
│   ├── screening.py       # SubScore + 11 sub-score + 3 result models
│   ├── assessment.py      # DeepAssessmentResult, DimensionScore, TokenUsage
│   ├── scoring.py         # ScoreResult, RankedRepo, DomainProfile, ExplainabilityReport
│   ├── features.py        # FeatureStoreKey, RepoFeatures
│   ├── api.py             # Request/Response models REST API
│   ├── agent.py           # DiscoverySession, MCPToolResult
│   ├── mcp_spec.py        # MCPToolSpec, AgentWorkflowConfig
│   └── session.py         # SessionState, SessionConfig, SessionStatus
│
├── discovery/             # 11 file — Layer A (Gate 0)
│   ├── orchestrator.py    # DiscoveryOrchestrator
│   ├── github_client.py   # GitHubRestClient (httpx, exponential backoff)
│   ├── graphql_client.py  # GitHubGraphQLClient
│   ├── pool.py            # PoolManager (SQLite/aiosqlite)
│   ├── search_channel.py, code_search_channel.py, curated_channel.py,
│   │   registry_channel.py, dependency_channel.py, seed_expansion.py
│   └── types.py           # DiscoveryQuery, ChannelResult, DiscoveryResult
│
├── screening/             # 16 file — Layer B (Gate 1+2)
│   ├── orchestrator.py    # ScreeningOrchestrator
│   ├── gate1_metadata.py  # Gate1MetadataScreener (7 checker)
│   ├── gate2_static.py    # Gate2StaticScreener (4 adapter, shallow clone)
│   ├── hygiene.py, maintenance.py, practices.py, test_footprint.py,
│   │   ci_cd.py, release_discipline.py, dependency_quality.py
│   ├── scorecard_adapter.py, osv_adapter.py, secrets_check.py, complexity.py
│   ├── subprocess_runner.py
│   └── types.py           # RepoContext, ScreeningContext, SubprocessResult
│
├── assessment/            # 17 file — Layer C (Gate 3)
│   ├── orchestrator.py    # AssessmentOrchestrator (8-step pipeline)
│   ├── llm_provider.py    # LLMProvider (NanoGPT + instructor)
│   ├── repomix_adapter.py # RepomixAdapter (python-repomix)
│   ├── budget_controller.py # BudgetController (token/day tracking)
│   ├── heuristics.py      # HeuristicAnalyzer (7 detection methods)
│   ├── result_parser.py   # ResultParser (LLM output → DeepAssessmentResult)
│   ├── types.py           # RepoContent, HeuristicScores, AssessmentContext
│   ├── lang_analyzers/    # LanguageAnalyzer, PythonAnalyzer
│   └── prompts/           # 8 dimension prompt templates
│
├── scoring/               # 10 file — Layer D
│   ├── engine.py          # ScoringEngine (combinazione Gate 1+2+3)
│   ├── ranker.py          # Ranker (star-neutral, tie-breaking deterministico)
│   ├── value_score.py     # ValueScoreCalculator (star-neutral)
│   ├── confidence.py      # ConfidenceCalculator (per-source + gate coverage)
│   ├── profiles.py        # ProfileRegistry (11 profili dominio)
│   ├── cross_domain.py    # CrossDomainGuard (normalizzazione, warnings)
│   ├── explainability.py  # ExplainabilityGenerator (strengths, weaknesses, recs)
│   ├── feature_store.py   # FeatureStore (SQLite, TTL, CRUD, batch)
│   └── types.py           # ScoringInput, DimensionScoreInfo, RankingResult
│
├── mcp/                   # 20 file — Interfaccia Primaria
│   ├── server.py          # FastMCP + lifespan + AppContext
│   ├── session.py         # SessionManager (SQLite)
│   ├── prompts.py         # 5 prompt skill definitions
│   ├── output_format.py   # format_tool_result(), truncate_for_context()
│   ├── progress.py        # report_*_progress() per ogni fase
│   ├── config.py          # Tool/toolset filtering
│   ├── transport.py       # stdio vs streamable-http
│   ├── github_client.py   # Composizione con GitHub MCP Server
│   ├── __main__.py        # python -m github_discovery.mcp
│   ├── tools/             # 5 file, 16 tool MCP
│   │   ├── discovery.py   # discover_repos, get_candidate_pool, expand_seeds
│   │   ├── screening.py   # screen_candidates, get_shortlist, quick_screen
│   │   ├── assessment.py  # deep_assess, quick_assess, get_assessment
│   │   ├── ranking.py     # rank_repos, explain_repo, compare_repos
│   │   └── session.py     # create_session, get_session, list_sessions, export_session
│   └── resources/         # 4 risorse MCP (URI template)
│
├── api/                   # 11 file — Interfaccia Secondaria (REST)
│   ├── app.py             # FastAPI app factory + lifespan
│   ├── auth.py            # API key auth
│   ├── deps.py            # Dependency injection
│   ├── middleware.py       # CORS, rate limiting
│   ├── errors.py          # Error handlers
│   └── routes/            # 5 route groups (discovery, screening, assessment, ranking, export)
│
├── cli/                   # 14 file — CLI (Typer + Rich)
│   ├── app.py             # Typer app factory, global options, command registration
│   ├── discover.py, screen.py, deep_eval.py, rank.py
│   ├── explain.py, compare.py, export.py, session.py
│   ├── mcp_serve.py, mcp_config.py
│   ├── formatters.py      # 4 formati output (table, json, markdown, yaml)
│   ├── progress_display.py # Rich Progress bar
│   └── utils.py           # Utility CLI
│
├── workers/               # 8 file — Background job processing
│   ├── worker_manager.py  # WorkerManager (lifecycle)
│   ├── queue.py           # AsyncTaskQueue (asyncio.Queue + JobStore)
│   ├── job_store.py       # JobStore (SQLite)
│   ├── base_worker.py     # BaseWorker (abstract)
│   ├── discovery_worker.py, screening_worker.py, assessment_worker.py
│   └── types.py           # Job, JobStatus, JobType, WorkerResult
│
└── feasibility/           # 5 file — Sprint 0 validation
    ├── sprint0.py         # Pipeline runner per test queries
    ├── baseline.py        # Baseline star-based comparison
    ├── metrics.py         # Precision@K, NDCG, MRR
    └── calibration.py     # Weight calibration via grid search
```

### 6.2 Stack Tecnologico Verificato

| Componente | Tecnologia | Versione | Verifica |
|------------|-----------|----------|----------|
| Linguaggio | Python | 3.12+ | ✅ |
| Modelli dati | Pydantic | v2 | Context7-verified |
| Configurazione | pydantic-settings | latest | Context7-verified |
| HTTP client | httpx | latest | async, retry con exponential backoff |
| LLM client | openai + instructor | ≥1.30, ≥1.4 | Context7-verified |
| Codebase packing | python-repomix | ≥0.1.0 | Context7-verified |
| MCP server | mcp (Python SDK) | ≥1.6 | Context7-verified |
| REST API | FastAPI | ≥0.115 | Context7-verified |
| ASGI server | uvicorn | ≥0.30 | Standard |
| CLI | typer + rich | ≥0.12, ≥13.0 | Context7-verified |
| Database | SQLite (aiosqlite) | latest | 4 database files (pools, features, sessions, jobs) |
| Git mining | PyDriller | ≥2.6 | Differito (API heuristics di default) |
| Logging | structlog | latest | Context7-verified |
| Linting | ruff | latest | 99 char line length |
| Type checking | mypy | latest | --strict mode |
| Testing | pytest | latest | import-mode=importlib |

---

## 7. Basi di Dati e Persistenza

Il sistema usa **4 database SQLite** indipendenti, tutti nella directory `.ghdisc/`:

| Database | Path | Gestore | Contenuto | TTL |
|----------|------|---------|-----------|-----|
| **Pools** | `.ghdisc/pools.db` | `PoolManager` | Pool di candidati, risultati discovery | Sessione |
| **Features** | `.ghdisc/features.db` | `FeatureStore` | ScoreResult, DeepAssessmentResult | 48 ore (configurabile) |
| **Sessions** | `.ghdisc/sessions.db` | `SessionManager` | SessionState, progresso workflow | Persistente |
| **Jobs** | `.ghdisc/jobs.db` | `JobStore` | Job asincroni (API workers) | 24 ore |

Il FeatureStore è il più critico: usa la coppia `(full_name, commit_sha)` come chiave per deduplicare le valutazioni. Se un repository viene rivalutato con lo stesso commit SHA, il risultato in cache viene riutilizzato (entro TTL).

---

## 8. Flusso Dati End-to-End

```
Gate 0: DiscoveryOrchestrator.discover("static analysis python")
  └► [RepoCandidate × 50] → PoolManager.save(pool_id, candidates)

Gate 1: ScreeningOrchestrator.screen(pool_id, gate_level="METADATA")
  └► Gate1MetadataScreener.screen(repo) per ogni candidato
    └► 7 chiamate API parallele → 7 sub-score → MetadataScreenResult
      └► gate1_pass = True (se totale ≥ 0.4)

Gate 2: ScreeningOrchestrator.screen(pool_id, gate_level="STATIC_SECURITY")
  └► Gate2StaticScreener.screen(repo) per ogni candidato (con gate1_pass)
    └► git clone --depth=1 → 4 tool paralleli → 4 sub-score → StaticScreenResult
      └► gate2_pass = True (se totale ≥ 0.5)
      └► pulizia clone

Gate 3: AssessmentOrchestrator.assess([top_5_repos])
  └► Per ogni repo:
    ├► Hard gate check: gate1_pass AND gate2_pass
    ├► Cache check: FeatureStore.get(full_name, commit_sha)
    ├► Budget check: BudgetController.verify(daily=500K, per_repo=50K)
    ├► RepomixAdapter.pack(repo) → contenuto packed
    ├► HeuristicAnalyzer.analyze(content) → baseline euristico
    ├► LLMProvider.assess(content, domain) → structured output su 8 dimensioni
    ├► ResultParser.parse(llm_output) → DeepAssessmentResult
    └► BudgetController.record_usage(tokens) + FeatureStore.save(result)

Layer D: ScoringEngine.score(repo, gate1, gate2, gate3)
  └► Per ogni dimensione: best signal (Gate 3 > Gate 2 > Gate 1 > default)
  └► Applica pesi dominio → quality_score
  └► ConfidenceCalculator → confidence
  └► FeatureStore.save_async(ScoreResult)

Layer D: Ranker.rank(domain="cli", results=[...])
  └► Ordina: (-quality_score, -confidence, -seeded_hash, full_name)
  └► Assegna rank 1-based
  └► Identifica hidden gem (label informativo)

Layer D: ExplainabilityGenerator.explain(repo)
  └► Punti di forza, debolezze, raccomandazioni
  └► Contesto stellare (corroboration_level)
  └► Indicatore hidden gem (se applicabile)
```

---

## 9. Pattern Architetturali e Decisioni Chiave

### 9.1 Dependency Injection via AppContext

Il server MCP usa un dataclass `AppContext` come container di dependency injection:

```python
@dataclass
class AppContext:
    settings: Settings
    session_manager: SessionManager
    pool_manager: PoolManager
    discovery_orchestrator: DiscoveryOrchestrator
    screening_orchestrator: ScreeningOrchestrator
    assessment_orchestrator: AssessmentOrchestrator
    scoring_engine: ScoringEngine
    ranker: Ranker
    feature_store: FeatureStore
```

Tutti i tool MCP accedono ai servizi attraverso `get_app_context(ctx)`, un pattern typesafe che evita global state.

### 9.2 Rate Limiting e Resilienza

Il `GitHubRestClient` implementa un sistema di retry sofisticato:

```
Exponential backoff con jitter:
  Attempt 1: wait 1s
  Attempt 2: wait 2s (+ random jitter)
  Attempt 3: wait 4s (+ random jitter)
  Attempt 4: wait 8s (+ random jitter)
  Attempt 5: wait 16s (+ random jitter)
  Max wait: 60s total

Proactive waiting:
  Se X-RateLimit-Remaining < watermark (core=10, search=3):
    Attendi fino a X-RateLimit-Reset (timestamp esatto da GitHub)
```

Questo sistema ha sostituito un fail-fast precedente che causava score=0.0 per repo colpiti da rate limit.

### 9.3 Pattern di Errore e Degradazione

La filosofia di errore del sistema è **mai bloccare la pipeline su un singolo fallimento**:

| Livello | Strategia |
|---------|-----------|
| **Discovery** | Canali eseguiti concorrentemente con error isolation — un canale che fallisce non blocca gli altri |
| **Gate 1** | `_safe_score()` wrappa ogni checker in try/except → fallback zero-value |
| **Gate 2** | Tool esterni con graceful degradation → fallback score 0.3, confidence 0.0 |
| **Gate 3** | Fallback euristico se LLM non disponibile → HeuristicAnalyzer |
| **API** | Circuit breaker, timeout, retry con backoff |

### 9.4 Ottimizzazione dei Costi

Il design a livelli (cheap→deep) è la strategia primaria di controllo costi:

```
Scenario tipico: 1000 candidati iniziali
  Gate 0: 1000 → costo API GitHub (gratuito, rate-limited)
  Gate 1: 1000 → solo metadati API GitHub (gratuito)
  Gate 2: ~200 passano Gate 1 → shallow clone + tool esterni (basso)
  Gate 3: ~20 passano Gate 2 → LLM assessment ($$)
  Ranking: sui 20 valutati → gratis

Costo LLM stimato: ~20 × 50K token × $0.00015/token ≈ $0.15 per query
(con NanoGPT, variabile in base al provider)
```

---

## 10. Stato Attuale e Roadmap

### 10.1 Stato Corrente (25 Aprile 2026)

| Fase | Stato | Test | Note |
|------|-------|------|------|
| Phase 0 — Scaffolding | ✅ COMPLETO | 46 | Config, logging, eccezioni, modelli sessione |
| Phase 1 — Data Models | ✅ COMPLETO | 113 | 60+ modelli Pydantic v2, 6 enum |
| Phase 2 — Discovery Engine | ✅ COMPLETO | 320 | 6 canali, 2 client API, orchestratore, pool |
| Phase 3 — Screening | ✅ COMPLETO | 500 | Gate 1 (7 checker) + Gate 2 (4 adapter) |
| Phase 4 — Deep Assessment | ✅ COMPLETO | 863 | Gate 3 LLM, 8 dimensioni, repomix, budget |
| Phase 5 — Scoring & Ranking | ✅ COMPLETO | 1326 | Star-neutral redesign, 11 profili dominio |
| Phase 6 — API & Workers | ✅ COMPLETO | 990 | FastAPI, job queue, 3 worker types |
| Phase 7 — MCP Integration | ✅ COMPLETO | 1114 | 16 tool, 4 risorse, 5 prompt |
| Phase 8 — CLI | ✅ COMPLETO | 1199 | Typer + Rich, 11 comandi |
| Phase 9 — Feasibility | ✅ COMPLETO | 1314 | E2E validation, metrics, calibration |
| Wave 0 — Smoke Tests | ✅ COMPLETO | 10 real API | 3 bug fissati, validato contro API reali |
| **Phase 10 — Alpha** | 🔜 PENDING | — | Docker, Marketplace, Docs, PyPI |

**Metriche attuali**: 1326 test passanti, `make ci` green (ruff + mypy --strict + pytest), 0 errori di lint/type.

### 10.2 Gap Identificati (Phase 10)

| Gap | Severità | Azione Richiesta |
|-----|----------|-----------------|
| Nessun test con API GitHub reali | CRITICAL | Wave 0 smoke tests (✅ completato) |
| Nessun packaging Docker | HIGH | Dockerfile + docker-compose |
| Nessuna pubblicazione PyPI | HIGH | Publish v0.1.0-alpha |
| Nessuna documentazione utente | HIGH | README.md, docs/usage/ |
| Nessun entry nel Kilo Marketplace | HIGH | MCP.yaml + PR |
| Nessun test con client MCP reali | MEDIUM | Verifica con Claude Code / Kilocode / OpenCode |
| Dependency channel sempre vuoto | MEDIUM | Nessuna API pubblica GitHub per dependents |
| Task 9.5 (Human Evaluation) non implementato | LOW | Richiede valutatori umani |
| Directory `tests/unit/test_mcp/` stub residua | LOW | Pulizia |

### 10.3 Dipendenze da Installare per l'Uso

```bash
# Runtime
pip install github-discovery

# Oppure via UVX (zero install):
uvx github-discovery mcp serve --transport stdio

# Tool esterni opzionali per Gate 2
brew install gitleaks    # Secret scanning
brew install scc         # Code complexity

# Per sviluppo
pip install -e ".[dev]"  # Include ruff, mypy, pytest
```

---

## 11. Riferimenti

### Documentazione di Progetto
- **Foundation Blueprint**: `docs/foundation/github-discovery_foundation_blueprint.md` (657 righe, 21 sezioni)
- **Roadmap**: `docs/roadmaps/github-discovery_foundation_roadmap.md`
- **LLM Wiki**: `docs/llm-wiki/wiki/index.md` (45 articoli in 4 topic)
- **Progress Log**: `progress.md`
- **Workflow State**: `.workflow/state.md`

### Documentazione Esterna
- **MCP Python SDK**: https://github.com/modelcontextprotocol/python-sdk
- **GitHub MCP Server**: https://github.com/github/github-mcp-server
- **Kilocode MCP Docs**: https://kilo.ai/docs/automate/mcp/using-in-cli
- **Claude Code MCP**: https://docs.anthropic.com/en/docs/claude-code/mcp
- **OpenCode MCP**: https://opencode.ai/docs/mcp-servers/
- **Kilo Marketplace**: https://github.com/Kilo-Org/kilo-marketplace
- **MCP Protocol Spec**: https://modelcontextprotocol.io

### Progetti di Riferimento
- **github_repo_classifier**: https://github.com/chriscarrollsmith/github_repo_classifier
- **OpenSSF Scorecard**: https://github.com/ossf/scorecard
- **CHAOSS**: https://chaoss.community
- **Repomix**: https://github.com/yamadashy/repomix

---

> **Disclaimer**: Questo report è basato sull'analisi della codebase al commit corrente (2026-04-25). Il progetto è in fase alpha (v0.1.0). Alcuni dettagli implementativi potrebbero evolvere nelle fasi successive.
