# GitHub Discovery — Foundation Blueprint

## 1) Missione
Costruire un sistema di discovery che trovi repository GitHub di alta qualita tecnica anche quando hanno poche o zero stelle.

Obiettivo centrale: separare la qualita ingegneristica dal successo sociale.

## 2) Problema reale da risolvere
I canali attuali (search engine, AI agent, trend dashboard) tendono a sovra-pesare:
- star count
- segnali social (Reddit/blog/discussioni)
- momentum mediatico

Effetto: i repository tecnicamente ottimi ma poco visibili restano fuori dal radar.

## 3) Criteri guida del progetto
- Star-independence: le stelle non devono dominare il ranking.
- Technical-first: enfasi su codice, architettura, test, manutenzione.
- Explainability: ogni score deve essere spiegabile per feature.
- Domain-aware: metriche diverse per libreria, framework, CLI, backend, ML.
- Cost-aware: pipeline a livelli per ridurre costi di analisi profonda.
- MCP-native: integrabile in workflow agentici (Claude, GPT, ecc.).

## 4) Ricerca di stato dell'arte (cosa esiste gia)

### 4.1 Progetto piu vicino trovato
1. **chriscarrollsmith/github_repo_classifier**
   - URL: https://github.com/chriscarrollsmith/github_repo_classifier
   - Approccio: discovery via query GitHub + classificazione LLM (repomix + llm + gh CLI)
   - Insight chiave: usa un Value Score (`quality_score / log10(star_count + 10)`) per identificare hidden gems.
   - Limite: pipeline shell script oriented, discovery ancora fortemente keyword-based.

### 4.2 Ecosistema metriche salute OSS
2. **CHAOSS / GrimoireLab / Augur**
   - URLs:
     - https://chaoss.community/software/
     - https://chaoss.github.io/grimoirelab/
     - https://github.com/chaoss/augur
   - Focus: health/sustainability community (non code quality profonda file-level).

3. **OpenSSF Scorecard**
   - URLs:
     - https://github.com/ossf/scorecard
     - https://scorecard.dev/
   - Focus: security health checks automatizzati (branch protection, workflow security, token permissions, ecc.).
   - Valore: fortissimo segnale di igiene/protezione supply chain.

### 4.3 Strumenti MCP / AI analysis emersi
4. **github/github-mcp-server** (ufficiale GitHub)
   - URL: https://github.com/github/github-mcp-server
   - Valore: base ufficiale per integrazione agent->GitHub.

5. Altri MCP orientati ad analisi repo (sperimentali/non standardizzati):
   - https://github.com/meltemeroglu/github-intelligence-mcp
   - https://github.com/iamthite/GitHub-Analyzer-MCP-Server
   - https://github.com/lucidopus/codeglance-mcp
   - https://github.com/mauriziomocci/mcp-code-review

### 4.4 Tool complementari rilevanti
6. **Repomix**
   - URL: https://github.com/yamadashy/repomix
   - Ruolo: impacchettamento codebase per valutazione LLM.

7. **Trend dashboards** (es. trendshift)
   - Utili per trend detection, ma non risolvono il bias popularity-first.

## 5) Gap analysis (cosa manca sul mercato)
Nessun prodotto trovato combina in modo robusto:
1. Discovery sistematica anti-popularity bias
2. Valutazione tecnica multi-dimensionale spiegabile
3. Pipeline scalabile a livelli (cheap->deep)
4. Ranking domain-aware
5. Interfaccia MCP-native + dataset persistente dei risultati

Questo e lo spazio strategico di GitHub Discovery.

## 6) Architettura concettuale proposta (v1)

### Layer A — Candidate Discovery Engine
Obiettivo: trovare candidati promettenti prima della valutazione profonda.

Canali candidati:
- GitHub Search API/GraphQL (filtri avanzati: topic, language, date, size)
- Code Search API (pattern di quality signal nei file)
- Dependency graph traversal (repo usati da progetti affidabili)
- Package registries (npm/PyPI/crates/Maven -> mapping al repo)
- Awesome lists e curated sources
- Seed expansion per associazione (co-contributor, co-dependency, org adjacency)

Output: pool candidati con score preliminare.

### Layer B — Lightweight Quality Screening
Obiettivo: ridurre il pool con segnali a basso costo computazionale.

Feature proposte (esempi):
- Presenza CI/CD (`.github/workflows`, badge build)
- Presenza test (`tests/`, `*_test.*`, coverage config)
- Hygiene files (`LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md`)
- Release discipline (tagging, semver, cadence)
- Maintenance signals (recency, commit consistency, bus factor proxy)
- Issue/PR practices (template, response latency proxy, review evidence)
- Dependency quality (lockfiles, pinning, update signals)

Output: shortlist candidati meritevoli di deep scan.

### Layer C — Deep Technical Assessment
Obiettivo: valutazione tecnica ad alta precisione.

Metodi:
- Repomix + LLM structured evaluation
- Static analysis adapters (Sonar-like checks dove possibile)
- Code structure and architecture heuristic scoring
- Security posture enrichment (OpenSSF Scorecard)
- Optional language-specific analyzers

Output: punteggi per dimensione + spiegazione per evidenze.

### Layer D — Scoring, Ranking, Explainability
Obiettivo: ranking finale e interpretabile.

Principi:
- Multi-score, non solo singolo punteggio
- Ranking intra-dominio (no confronto diretto unfair tra categorie diverse)
- Anti-star bias esplicito (stars come feature debole o solo di contesto)
- Confidence score (qualita dei dati disponibili)

Output: lista "best technically underrated repos" con motivazioni.

## 7) Framework di metriche iniziale (draft)

### 7.1 Dimensioni di valutazione
1. Code Quality
2. Architecture & Modularity
3. Testability & Verification
4. Documentation & Developer Experience
5. Maintenance & Project Operations
6. Security & Supply Chain Hygiene
7. Functional Completeness (fit rispetto allo use-case target)
8. Innovation / Distinctiveness

### 7.2 Esempio pesi iniziali (da validare)
- Code Quality: 20%
- Architecture: 15%
- Testing: 15%
- Documentation: 10%
- Maintenance: 15%
- Security: 10%
- Functional Completeness: 10%
- Innovation: 5%

Nota: i pesi devono essere domain-dependent.

## 8) API e capability utili (concrete)

### 8.1 GitHub REST/GraphQL
Utilizzabili per:
- repository metadata
- commit history e contributor patterns
- issue/PR/review metadata
- release/tag activity
- code search e file presence checks

Vincoli:
- rate limit e cost model (GraphQL a punti)
- paginazione rigorosa necessaria per bulk analysis

### 8.2 GitHub Code Quality (public preview)
Segnale emergente su quality/coverage in ecosistema GitHub, da monitorare per integrazione quando API mature saranno stabili.

### 8.3 OpenSSF Scorecard
Integrazione consigliata come modulo security-quality standard.

## 9) Blueprint prodotto: opzioni di delivery

### Option A — MCP-first service
- Core engine + MCP server
- target primario: agent workflows
- pro: integrazione AI nativa

### Option B — API + Worker + Web UI
- backend scoring + dashboard discovery
- pro: product usability ampia

### Option C — Hybrid
- API/worker core + MCP facade + CLI
- pro: massima flessibilita

Direzione suggerita: Option C.

#### Option C (approfondita) — Principi architetturali anti-overengineering
1. **Reuse-first**: usare il `github/github-mcp-server` ufficiale come servizio/tool interno per operazioni GitHub standard (repo, issue, PR, search, read/write controllato), evitando di reimplementare adapter custom dove non necessario.
2. **Thin orchestration layer**: GitHub Discovery aggiunge solo logica di discovery/scoring/ranking e non duplica funzionalita gia presenti nell'MCP ufficiale.
3. **Two-lane pipeline**:
   - Lane 1 (cheap): pre-screening non-LLM su grandi volumi
   - Lane 2 (deep): analisi LLM solo su shortlist ad alta priorita
4. **Security-first execution**: default `read-only` nei flussi di analisi; write abilitato solo nei workflow autorizzati.
5. **Composable deployment**:
   - servizio core (API + queue + workers)
   - MCP facade per accesso agentico
   - CLI per batch e automazione CI

#### Option C (approfondita) — Componenti minimi consigliati
- **Discovery API**: ingest candidati, filtri, ranking query.
- **Scoring Workers**: worker separati per `metadata`, `static/security`, `LLM deep eval`.
- **Feature Store**: persistenza feature per repo (evita ricalcolo costoso).
- **Policy Engine**: soglie, pesi, gating per dominio.
- **MCP Integration Layer**: client verso GitHub MCP ufficiale con toolset minimali.
- **CLI**: comandi `discover`, `screen`, `deep-eval`, `rank`, `export`.

#### Option C (approfondita) — Integrazione consigliata con GitHub MCP ufficiale
Baseline operativa:
- Toolsets ridotti al minimo necessario (`repos,issues,pull_requests,context` oppure subset ancora piu stretto).
- Abilitare `read-only` in analisi (`X-MCP-Readonly: true` o `--read-only`).
- Usare `exclude-tools` per rimuovere operazioni non desiderate anche se incluse nel toolset.
- Valutare `dynamic-toolsets` in locale quando serve discovery progressiva dei tool.
- Usare `lockdown-mode` in scenari con policy restrittive su contenuti pubblici.

## 10) Domain strategy
Definire taxonomia repo (es. CLI, web framework, data tool, ML lib, DevOps tool) e usare:
- feature set specifiche
- soglie specifiche
- ranking separato per cluster

Evita confronti fuorvianti tra repository eterogenei.

## 11) Rischi principali
1. **Scalabilita costo LLM** su deep scans
2. **Bias residuo nella candidate discovery**
3. **False positives** (progetti ben formattati ma deboli funzionalmente)
4. **Data incompleti** (repo piccoli/nuovi con poco storico)
5. **Comparabilita cross-language**

Mitigazioni:
- pipeline a livelli con early pruning
- confidence score per output
- sampling + audit manuale su subset
- fallback rule-based quando il contesto non basta

## 12) Esperimenti fondativi da eseguire (priorita)

### Sprint 0 — Feasibility (2-3 settimane)
1. Implementare mini-pipeline su 500-1000 repo candidati
2. Calcolare baseline metadata score (senza LLM)
3. Deep-scan solo top 10-15%
4. Confrontare ranking con star-based baseline
5. Valutazione manuale su campione (blind) per validare utilita

Deliverable sprint 0:
- dataset scored
- report precision@k su hidden gems
- prima tuning dei pesi

### Sprint 1 — Alpha engine
- discovery multicanale
- scoring explainable
- output queryable (API/CLI)
- MCP endpoint minimo per agent

## 13) KPI di successo progetto
- Hidden Gem Precision@K (valutazione umana)
- % di top risultati con stars basse ma quality alta
- Coverage multi-language
- Costo medio per repo valutato
- Tempo medio end-to-end di analisi
- Stabilita ranking tra run successive

## 14) Aree di approfondimento successive (backlog di ricerca)
1. Modello migliore per anti-popularity debiasing
2. Metriche language-agnostic robuste
3. Mapping package ecosystem -> repo quality signals
4. Benchmark pubblico per repository technical excellence
5. Valutazione human-in-the-loop per calibrazione pesi
6. Strategia anti-gaming dei metric signals

## 15) Decisioni fondative proposte
- Il progetto nasce come **technical discovery engine**, non come trend tracker.
- Stars e buzz vengono trattati come contesto, non come criterio primario.
- L'architettura deve essere **tiered + explainable + MCP-native**.
- La prima milestone e dimostrare che troviamo repo migliori del baseline star-based su un campione reale.

## 16) Estensione blueprint (Aprile 2026): pre-screening low/zero LLM cost

### 16.1 Obiettivo
Ridurre drasticamente costo/token/tempo LLM applicando una scrematura tecnica non-LLM su un bouquet ampio di repository, e inviare al deep assessment solo i candidati migliori.

### 16.2 Strategia a costo minimo (gating progressivo)
1. **Gate 0 - Discovery grezzo**
   - raccolta candidati multicanale (GitHub search, package registries, curated lists)
2. **Gate 1 - Metadata screening (zero LLM)**
   - segnali repository-level da API (attivita, hygiene files, release discipline, review evidence)
3. **Gate 2 - Static/security screening (zero o low cost)**
   - tool automatici su clone shallow o snapshot
4. **Gate 3 - LLM deep assessment (costoso)**
   - solo top percentile (es. 10-15%)

### 16.3 Tooling consigliato per pre-screening (ufficiale/documentato)
- **PyDriller** (`/websites/pydriller_readthedocs_io_en`): process metrics su commit/churn/contributor concentration.
- **scc** (`/boyter/scc`) o **cloc** (`/aldanial/cloc`): LOC/language/complexity preliminare via output JSON.
- **Semgrep CE** (`/semgrep/semgrep-docs`): static checks multi-language a costo contenuto.
- **Gitleaks** (`/gitleaks/gitleaks`): secret hygiene.
- **OSV scanner / OSV API** (`/google/osv.dev`): vulnerability screening su dipendenze/commit.
- **OpenSSF Scorecard** (`/ossf/scorecard`): security posture standardizzata.

### 16.4 Feature set non-LLM suggerite per ranking preliminare
- Repository hygiene score (LICENSE, SECURITY.md, CONTRIBUTING.md, CHANGELOG.md)
- Maintenance score (commit recency/cadence, release cadence)
- Review practice score (PR activity, review presence)
- Test footprint score (test dirs/pattern ratio)
- Complexity/size sanity score (scc/radon/cloc dove applicabile)
- Security hygiene score (Scorecard + secrets + dependency vulnerabilities)

### 16.5 Policy di budget LLM (hard rules)
- Nessun deep-scan LLM sotto soglia minima Gate 1+2.
- Massimo budget token/giorno e budget token per repo.
- Timeout e early-stop su repo troppo grandi o non parsabili.
- Caching obbligatorio risultati intermedi e dedup per commit SHA.

## 17) Regole operative (stella polare del progetto)

### 17.1 Principi
1. **Plan before code**: ogni iniziativa non banale parte da piano esplicito.
2. **Verify before complete**: una task non e finita senza evidenza verificabile.
3. **Reuse over rebuild**: prima integrare tool ufficiali esistenti, poi estendere.
4. **Least privilege by default**: read-only e allowlist comandi/tool.
5. **Context discipline**: sessioni corte, scope chiaro, reset tra task non correlate.

### 17.2 Workflow agentico standard (OpenCode, KiloCode, Claude Code)
1. **Explore**: analisi read-only del contesto
2. **Plan**: piano implementativo con criteri di verifica
3. **Implement**: cambi minimi, iterativi
4. **Verify**: test/lint/check/metriche richieste
5. **Review**: controllo finale (umano o subagent reviewer)
6. **Ship**: commit/PR con rationale

### 17.3 Guardrail cross-tool
- **Permission gating**: usare policy granulari `allow/ask/deny` (OpenCode/KiloCode/Claude).
- **Subagent isolation**: decomporre task complessi in contesti isolati con summary di ritorno.
- **Deterministic checks**: codificare controlli ricorrenti via hook/workflow/command.
- **No silent failures**: errori loggati con retry strategy esplicita.

### 17.4 Best practice pratiche CLI (non estensioni)
- **Claude Code CLI**: usare ciclo *explore -> plan -> implement -> verify*; usare `/clear` per separare task non correlate; automatizzare con `claude -p` quando serve non-interattivo; mantenere `CLAUDE.md` corto e ad alta priorita informativa.
- **OpenCode CLI**: usare `opencode run` per automazioni, `opencode serve` per backend headless, `opencode mcp add/list/auth` per gestione MCP; separare agent `plan/build/review` con permission policy granulari (`allow/ask/deny`).
- **Kilo CLI**: usare `kilo run --auto` in pipeline non-interattive, Orchestrator Mode per decomporre task complessi, `/connect` per bootstrap provider, e regole permission nel file config per comandare auto-approval sicura.

### 17.5 Pattern operativo standard CLI
1. Sessione interattiva per discovery/pianificazione (`opencode` / `kilo` / `claude`)
2. Validazione piano e criteri di test
3. Esecuzione automatizzabile in non-interattivo (`opencode run`, `kilo run --auto`, `claude -p`)
4. Verifica con comandi deterministici (test/lint/typecheck)
5. Export risultati/sessioni quando utile per audit (`opencode export`, `kilo export`)

## 18) Best practice API/MCP per scala (aprile 2026)
- REST best practices GitHub: evitare polling, usare richieste autenticate, limitare concorrenza, gestire `retry-after` e `x-ratelimit-*`, usare conditional requests (`etag`/`if-modified-since`).
- GraphQL: paginazione cursor-based obbligatoria (`first/last` 1..100, `pageInfo`), batch controllato per evitare query cost eccessivi.
- GitHub MCP server: configurazione composabile con `toolsets/tools/exclude-tools`; `read-only` come filtro di sicurezza prioritario; `dynamic-toolsets` utile per discovery locale.

## 19) Decisioni incrementalmente approvate in questa revisione
1. Option C resta direzione primaria, con estensione dettagliata.
2. GitHub MCP ufficiale viene adottato come servizio interno standard.
3. La riduzione costi LLM e requisito architetturale primario (non ottimizzazione secondaria).
4. Workflow agentico standardizzato (OpenCode/KiloCode/Claude Code) diventa policy operativa del progetto.

## 20) Fonti chiave usate in questa fase
- https://github.com/chriscarrollsmith/github_repo_classifier
- https://github.com/yamadashy/repomix
- https://github.com/ossf/scorecard
- https://scorecard.dev/
- https://chaoss.community/software/
- https://chaoss.github.io/grimoirelab/
- https://github.com/chaoss/augur
- https://github.com/github/github-mcp-server
- https://github.com/github/github-mcp-server/blob/main/docs/server-configuration.md
- https://docs.github.com/en/graphql
- https://docs.github.com/en/graphql/guides/using-pagination-in-the-graphql-api
- https://docs.github.com/en/rest
- https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api
- https://opencode.ai/docs/cli
- https://kilocode.ai/docs/code-with-ai/platforms/cli
- https://code.claude.com/docs/en/best-practices

## 21) Agentic Integration Architecture (Giugno 2026)

Questa sezione raccoglie le estensioni architetturali necessarie per trasformare GitHub Discovery da un servizio standalone con MCP facade a un **sistema agentico MCP-native**, progettato per integrarsi profondamente in workflow agentici di Kilocode CLI, OpenCode/OpenClaude e Claude Code.

### 21.1 Problema: dal servizio standalone al sistema agentico

L'architettura originale (Option C) descrive un servizio API+Worker con MCP facade e CLI come interfacce secondarie. Questo modello è sufficiente per uso batch/CI, ma è **inadeguato per integrazione agentica profonda** per tre motivi fondamentali:

1. **MCP è trattato come facade (Phase 7, dopo API Phase 6)**, mentre dovrebbe essere l'interfaccia primaria per agent AI. Un agente in Kilocode/OpenClaude interagisce primariamente via MCP tools — non via REST API.

2. **La pipeline è monolitica** (Gate 0→1→2→3→D come flusso sequenziale fisso), mentre un agente ha bisogno di accesso granulare: eseguire Gate 1 su un pool, poi decidere se deepen, poi eseguire Gate 2 su specifici candidati, tutto in un workflow interattivo multi-step.

3. **Non c'è sessione né contesto persistente**: un agente che scopre candidati in una sessione e vuole deepen nella sessione successiva non ha meccanismo per farlo.

**Direzione architetturale**: GitHub Discovery diventa un **MCP-native agentic discovery engine** dove MCP è l'interfaccia primaria, l'API è un consumer secondario degli stessi servizi core, e il CLI supporta sia batch che sessioni agentiche interattive.

### 21.2 Principi di design MCP-First

I seguenti principi guidano l'integrazione agentica e sostituiscono la nozione di "MCP facade":

1. **MCP è l'interfaccia primaria** — Gli agent interagiscono via MCP tools, resources e prompts. L'API REST è un consumer secondario degli stessi servizi core (non il contrario).

2. **Progressive Deepening** — Ogni gate è un tool MCP indipendente invocabile singolarmente. L'agente decide quando deepen, non la pipeline. Il flusso lineare è solo uno dei possibili workflow.

3. **Agent-Driven Policy** — Le soglie di gating sono parametri dei tool MCP, non costanti hardcoded. L'agente può configurare `min_gate1_score=0.6` in una query rapida e `min_gate1_score=0.3` per deep exploration.

4. **Session-Aware** — Le operazioni MCP sono session-aware: un agente può creare una sessione, scoprire candidati, esplorare risultati, e riprendere in una sessione successiva senza perdere stato.

5. **Streaming & Progress** — Le operazioni lunghe (discovery, deep assessment) emettono progress notifications MCP e restituiscono risultati parziali incrementali, permettendo all'agente di ragionare su risultati intermedi.

6. **Compositional Tool Design** — I tool MCP sono progettati per composizione: l'agente può combinare `discover_repos` + `screen_candidates` + `deep_assess` in un workflow multi-step, oppure usare il prompt `discover_underrated` per un workflow guidato.

7. **Context-Efficient** — I tool MCP sono parsimoniosi con contesto: restituiscono riassunti strutturati di default, con opzioni per dettaglio on-demand (evitando context overflow).

### 21.3 MCP Tool Design per Progressive Deepening

Il design dei tool MCP segue il principio di progressive deepening: ogni gate è un tool indipendente, e l'agente può scegliere il livello di profondità.

#### Tool MCP — Discovery (Layer A)

| Tool | Parametri | Output | Note |
|------|-----------|-------|------|
| `discover_repos` | `query`, `channels`, `max_candidates`, `session_id` | Pool candidati con `discovery_score`, reference al `session_id` | Crea o aggiorna una sessione. Agente può riprendere. |
| `get_candidate_pool` | `pool_id`, `filters`, `sort_by`, `limit` | Lista candidati con score preliminare | Filtro e ordinamento on-demand |
| `expand_seeds` | `seed_urls`, `expansion_strategy`, `max_depth`, `session_id` | Nuovi candidati da espansione seed | Per agent che hanno seed specifici |

#### Tool MCP — Screening (Layer B)

| Tool | Parametri | Output | Note |
|------|-----------|-------|------|
| `screen_candidates` | `pool_id`, `gate_level` (1 o 2 o "both"), `min_gate1_score`, `min_gate2_score`, `session_id` | `ScreenResult` con pass/fail per gate, sottoscore | L'agente sceglie il livello di screening e le soglie |
| `get_shortlist` | `pool_id`, `min_score`, `domain`, `limit` | Candidati che hanno passato i gate specificati | Filtro on-demand |
| `quick_screen` | `repo_url`, `gate_levels` ("1" o "1,2") | Singolo repo screening rapido | Per verifica rapida di un repo specifico |

#### Tool MCP — Assessment (Layer C)

| Tool | Parametri | Output | Note |
|------|-----------|-------|------|
| `deep_assess` | `repo_urls`, `dimensions`, `budget_tokens`, `session_id` | `DeepAssessmentResult` per repo, con dimensioni, explanation, confidence | Hard gate enforcement: rifiuta se candidate non passato Gate 1+2 |
| `quick_assess` | `repo_url`, `dimensions` (subset) | Assessment rapido su subset di dimensioni | Per agent che vogliono valutazione mirata |
| `get_assessment` | `repo_url`, `session_id` | Assessment esistente (se cached) | Evita ricalcolo costoso |

#### Tool MCP — Scoring & Ranking (Layer D)

| Tool | Parametri | Output | Note |
|------|-----------|-------|------|
| `rank_repos` | `domain`, `min_confidence`, `min_value_score`, `max_results`, `session_id` | `RankedRepo` list con value_score e explainability | Ranking intra-dominio con filtri |
| `explain_repo` | `repo_url`, `detail_level` ("summary" o "full"), `session_id` | `ExplainabilityReport` con breakdown per dimensione | Dettaglio on-demand, parsimonioso di default |
| `compare_repos` | `repo_urls`, `dimensions`, `session_id` | Confronto side-by-side su dimensioni specificate | Per agent decision-making comparativo |

#### Tool MCP — Session Management

| Tool | Parametri | Output | Note |
|------|-----------|-------|------|
| `create_session` | `name`, `config_overrides` | `session_id` con stato iniziale | Configurazione per-session: soglie, budget, domini |
| `get_session` | `session_id` | Stato sessione, pool, progress, risultati | Per riprendere workflow interrotti |
| `list_sessions` | `status`, `limit` | Lista sessioni attive/completate | Per agent multi-sessione |
| `export_session` | `session_id`, `format` ("json", "csv", "markdown") | Export completo dei risultati | Per persistenza e condivisione |

### 21.4 Session & Context Management per Agent Workflow

Un agente in Kilocode/OpenClaude/Claude Code opera in sessioni che possono essere interrotte, riprese, o concatenate. GitHub Discovery supporta questo pattern con:

1. **Sessione persistente**: ogni operazione MCP può specificare `session_id`. I risultati intermedi (pool, screening, assessment) sono associati alla sessione e persistenti in Feature Store.

2. **Progressive Deepening cross-sessione**: un agente può:
   - Sessione 1: `discover_repos` per pool iniziale
   - Sessione 2: `screen_candidates` su quel pool (stesso `session_id`)
   - Sessione 3: `deep_assess` solo sui top candidati (stesso `session_id`)
   - Sessione 4: `rank_repos` e `explain_repo` per decisioni finali

3. **Configurazione per-sessione**: ogni sessione può avere soglie di gating, budget LLM, e preferenze di dominio che sovrascrivono i default globali.

4. **Context compaction**: per sessioni lunghe, il sistema supporta summary/compaction dei risultati intermedi, permettendo all'agente di mantenere contesto rilevante senza context overflow.

5. **Cross-reference**: i tool MCP restituiscono reference (pool_id, session_id, repo_url) che l'agente può usare in chiamate successive,而不是 risultati completi ad ogni invocazione.

### 21.5 Composizione MCP con GitHub MCP Server

GitHub Discovery è progettato per operare **in composizione** con il GitHub MCP Server ufficiale, non in sostituzione. Un agente può:

1. **Usare GitHub MCP per operazioni standard**: repo browse, issue management, PR review, code search diretto.
2. **Usare GitHub Discovery MCP per discovery, screening, assessment e ranking**: operazioni di analisi qualitativa che il GitHub MCP non fornisce.
3. **Combinare i due in un workflow**: l'agente usa GitHub Discovery per trovare repo underrated, poi GitHub MCP per approfondire issue/PR specifiche.

#### Configurazione composita per Kilocode CLI

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

#### Configurazione composita per OpenCode

```json
{
  "mcp": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      }
    },
    "github-discovery": {
      "command": "python",
      "args": ["-m", "github_discovery.mcp", "serve", "--transport", "stdio"],
      "env": {
        "GHDISC_GITHUB_TOKEN": "${GITHUB_TOKEN}",
        "GHDISC_SESSION_BACKEND": "sqlite"
      }
    }
  }
}
```

#### Regole di composizione

1. **Non duplicare funzionalità GitHub MCP**: GitHub Discovery non espone tool per operazioni standard (list repos, read files, create issues) già coperte dal GitHub MCP. Espone solo tool di discovery, screening, assessment e ranking.
2. **Toolset minimale e focalizzato**: GitHub Discovery MCP espone solo i tool necessari per il pipeline di scoring, seguendo il principio di contesto parsimonioso.
3. **Read-only di default**: entrambi i server MCP operano in read-only per le pipeline di analisi. Write abilitato solo in workflow autorizzati.
4. **Condivisione autenticazione**: GitHub Discovery può usare lo stesso token GitHub del GitHub MCP, passato via variabili d'ambiente.

### 21.6 Streaming Results & Progress Notifications

MCP supporta progress notifications (`send_progress_notification`). GitHub Discovery le usa per operazioni lunghe:

1. **Discovery streaming**: man mano che i canali restituiscono candidati, il tool `discover_repos` emette progress con conteggio candidati trovati per canale.
2. **Screening progress**: il tool `screen_candidates` emette progress con conteggio repo processati vs totali per gate.
3. **Deep assessment progress**: il tool `deep_assess` emette progress con repo completati, token usati, e budget rimanente.

Formato progress notification:
```json
{
  "progress_token": "session-abc123",
  "progress": 42.0,
  "total": 100.0,
  "message": "Screened 42/100 candidates (Gate 1)"
}
```

### 21.7 MCP Prompts come Agent Skill Definitions

I prompt MCP non sono solo template testuali, ma **skill definitions** che guidano l'agente attraverso workflow multi-step strutturati. Seguendo il pattern hooks→skills→plugins→MCP di Claude Code (costo di contesto crescente):

| Prompt Name | Descrizione | Workflow guidato |
|-------------|-------------|------------------|
| `discover_underrated` | "Find technically excellent repos that are underrated by star count" | 1. Discover pool → 2. Screen (Gate 1+2) → 3. Deep assess top candidates → 4. Rank with value_score → 5. Explain top finds |
| `quick_quality_check` | "Quick quality assessment of a specific repository" | 1. Quick screen (Gate 1) → 2. Report quality signals |
| `compare_for_adoption` | "Compare multiple repos for adoption decision" | 1. Screen candidates → 2. Quick assess on key dimensions → 3. Side-by-side comparison |
| `domain_deep_dive` | "Deep exploration of a specific domain (e.g., Python static analysis tools)" | 1. Discover in domain → 2. Screen → 3. Deep assess → 4. Domain-specific ranking |
| `security_audit` | "Security-first assessment of repositories" | 1. Screen (Gate 2 heavy) → 2. Security-focused deep assess → 3. Security report |

Questi prompts forniscono all'agente un workflow pre-strutturato, riducendo il bisogno di orchestrare manualmente i singoli tool.

### 21.8 Struttura di contesto efficiente per agenti

L'output di ogni tool MCP è progettato per essere **context-efficient** — parsimonioso di default, dettagliato on-demand:

1. **Summary-first**: ogni tool restituisce un riassunto strutturato per default. Dettaglio completo accessibile via tool dedicati (`explain_repo`, `get_assessment`).
2. **Reference-based**: i tool restituiscono reference (ID, URL) invece di dati completi. L'agente recupera dettaglio solo quando necessario.
3. **Structured content**: uso di MCP structured content (JSON) per output parsable, con fallback a testo per agenti che non supportano structured content.
4. **Confidence indicators**: ogni risultato indica confidence e completezza dei dati, permettendo all'agente di decidere se deepen.

Esempio di output context-efficient per `screen_candidates`:

```json
{
  "pool_id": "pool-abc123",
  "total_candidates": 500,
  "gate1_passed": 87,
  "gate2_passed": 23,
  "shortlist_top_5": [
    {"repo": "user/repo1", "gate1_score": 0.89, "gate2_score": 0.82, "discovery_score": 0.75},
    {"repo": "user/repo2", "gate1_score": 0.85, "gate2_score": 0.78, "discovery_score": 0.71}
  ],
  "session_id": "session-xyz789",
  "detail_available_via": "get_shortlist(pool_id='pool-abc123', limit=50)"
}
```

### 21.9 Integrazione con Kilocode CLI, OpenClaude e Claude Code

#### Kilocode CLI

- **Configurazione**: `kilo.json` o `.kilo/kilo.json` con entry per `github-discovery` server locale (STDIO) o remoto (HTTP).
- **Permission**: tool GitHub Discovery configurati con pattern `github-discovery_*` in `permission` section (allow/ask/deny).
- **Kilo Marketplace**: packaging come skill MCP per distribuzione nella marketplace Kilo.
- **Agent Manager**: supporto per workflow multi-step via session_id, permettendo all'Agent Manager di orchestrare discovery su worktree separati.

#### OpenCode/OpenClaude

- **Configurazione**: `.config/opencode/` o `opencode.jsonc` con `mcpServers` entry.
- **Agent mode**: workflow discovery strutturati come prompt MCP per uso con agent in modalità `plan/build/review`.
- **Session isolation**: ogni agente usa session_id separato per isolation dei risultati.

#### Claude Code

- **Configurazione**: MCP config in `~/.config/claude/` con server config STDIO.
- **CLAUDE.md**: project-level instructions per workflow discovery (es. "use discover_underrated prompt for finding hidden gems in Python ML libraries").
- **Permission gating**: usare `allow/ask/deny` per tool discovery. Screening e deep assessment in `ask` di default, `rank` e `explain` in `allow`.

### 21.10 Packaging per Kilo Marketplace e OpenCode Registry

GitHub Discovery deve essere distribuibile come:

1. **PyPI package** (`github-discovery`): installabile via `pip install github-discovery`, include CLI, MCP server, e API server.
2. **Docker image** (`ghcr.io/github-discovery/server`): per deployment come servizio remoto.
3. **Kilo Marketplace skill**: entry nella marketplace Kilo con configurazione MCP predefinita e prompt/skill templates.
4. **OpenCode agent config**: template `.config/opencode/agent/discovery.md` con istruzioni per l'agente OpenCode.

### 21.11 Decisioni incrementalmente approvate in questa estensione

1. **MCP diventa interfaccia primaria** — non più facade secondaria. API REST è consumer secondario degli stessi servizi core.
2. **Progressive deepening come pattern architetturale** — ogni gate è un tool MCP indipendente, l'agente ordestra il flusso.
3. **Session-awareness come requisito di prima classe** — strumenti MCP supportano session_id per workflow cross-sessione.
4. **Context-efficient design** — output parsimoniosi di default, dettaglio on-demand.
5. **Composizione con GitHub MCP Server** — non duplicazione, specializzazione. GitHub Discovery espone solo scoring/ranking.
6. **MCP Prompts come skill definitions** — workflow pre-strutturati per agent, non solo template testuali.
7. **Progress notifications MCP** — streaming per operazioni lunghe.
8. **Agent-driven policy** — soglie di gating configurabili per-query, non solo per-config.

### 21.12 Impatto sulle fasi del roadmap

Questa estensione architetturale ha i seguenti impatti sul roadmap esistente:

1. **Phase 0 (Foundation)**: aggiungere modelli di sessione e reference (SessionConfig, ProgressNotification).
2. **Phase 1 (Models)**: aggiungere `SessionState`, `ProgressInfo`, `MCPToolSpec`, `AgentWorkflowConfig`.
3. **Phase 7 (MCP)**: riformulare da "facade" a "interfaccia primaria", con tool granulari, prompts come skill, e session management.
4. **Phase 8 (CLI)**: aggiungere supporto per session management, streaming output, e agent-friendly commands.
5. **Cross-cutting**: il Feature Store diventa session-aware; il Policy Engine supporta configurazione per-query.

Queste modifiche sono dettagliate nel Roadmap aggiornato (vedere sezione corrispondente nel documento roadmap).

---

Stato documento: Draft Foundation v1 (esplorativo) — aggiornato con §21 Agentic Integration Architecture (Giugno 2026)
Data: 2026-04-22 (originale), 2026-06-XX (estensione §21)
