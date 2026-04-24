# Phase 10 — Alpha Engine & Marketplace: Analisi Approfondita

**Data**: 2026-04-24
**Autore**: General Manager (analisi strategica)
**Stato**: Analisi completa — in attesa di decisione
**Riferimento roadmap**: `docs/roadmaps/github-discovery_foundation_roadmap.md` — Phase 10

---

## Indice

1. [Stato attuale del progetto](#1-stato-attuale-del-progetto)
2. [Analisi dettagliata dei task Phase 10](#2-analisi-dettagliata-dei-task-phase-10)
3. [Cosa significa "deployment nel marketplace"](#3-cosa-significa-deployment-nel-marketplace)
4. [Modalità di installazione e configurazione](#4-modalità-di-installazione-e-configurazione)
5. [Testare ora o implementare Phase 10?](#5-testare-ora-o-implementare-phase-10)
6. [Raccomandazione strategica](#6-raccomandazione-strategica)
7. [Piano di implementazione proposto](#7-piano-di-implementazione-proposto)
8. [Rischi e mitigazioni](#8-rischi-e-mitigazioni)

---

## 1. Stato attuale del progetto

### Metriche complessive

| Metrica | Valore |
|---------|--------|
| **Fasi completate** | Phase 0-9 (10 fasi) |
| **Source files** | ~135 |
| **Tests passing** | 1314 (ruff + mypy --strict green) |
| **Lint errors** | 0 |
| **Type check errors** | 0 |
| **Console script** | `ghdisc` → `github_discovery.cli.app:app` |
| **PyPI version** | `0.1.0-alpha` (configurato in pyproject.toml, non pubblicato) |

### Moduli implementati per layer

| Layer | Moduli | Stato |
|-------|--------|-------|
| **Layer A — Discovery** | 6 canali (Search, Code Search, Dependency, Registry, Awesome Lists, Seed Expansion) + orchestrator + pool | ✅ Completo |
| **Layer B — Screening** | Gate 1 (7 sub-scorer) + Gate 2 (4 adapter: Scorecard, OSV, gitleaks, scc) + Policy Engine | ✅ Completo |
| **Layer C — Assessment** | Repomix adapter + NanoGPT LLM provider (instructor+openai) + 8 dimension prompts + Budget controller + Heuristics + Lang analyzers | ✅ Completo |
| **Layer D — Scoring** | ScoringEngine + ProfileRegistry (11 domains) + ValueScoreCalculator + ConfidenceCalculator + Ranker + FeatureStore | ✅ Completo |
| **MCP Server** | FastMCP con 16 tools, 4 resources, 5 prompts, SessionManager, progress notifications, context-efficient output, composizione GitHub MCP | ✅ Completo |
| **CLI** | typer: discover, screen, deep-eval, rank, export, session, mcp serve, mcp init-config | ✅ Completo |
| **API** | FastAPI: 5 route groups, 3 worker types, JobStore, rate limiting, API key auth, export (JSON/CSV/MD) | ✅ Completo |
| **Feasibility** | Sprint0 runner, star-based baseline comparison, Precision@K/NDCG/MRR metrics, weight calibration | ✅ Completo |

### Cosa MANCA (gap rispetto a un sistema production-ready)

1. **Nessun test con API GitHub reali** — Tutti i 1314 test usano mock. Il sistema non è mai stato eseguito contro API GitHub reali.
2. **Nessuna documentazione user-facing** — AGENTS.md esiste per agent, ma non c'è README quickstart, ARCHITECTURE.md, o guide setup.
3. **Nessun packaging Docker** — Nessun Dockerfile o docker-compose.yml.
4. **Nessuna verifica con client MCP reali** — I test MCP usano ClientSession + MemoryObjectStream, non client produttivi (Kilo Code, Claude Desktop, Cursor).
5. **PyPI non pubblicato** — pyproject.toml configurato ma il pacchetto non è su PyPI.
6. **Nessuna entry nel Kilo Marketplace** — Non esiste MCP.yaml in formato marketplace.

---

## 2. Analisi dettagliata dei task Phase 10

### Task 10.1 — Multi-channel discovery validation

| Aspetto | Dettaglio |
|---------|-----------|
| **Obiettivo** | Validare che tutti i 6 canali discovery producono risultati reali, misurare coverage per canale |
| **Stato attuale** | 6 canali implementati e testati con mock. Il canale Dependency restituisce sempre lista vuota (non c'è API pubblica GitHub per dependents). |
| **Sforzo stimato** | Medio (2-3 giorni) — richiede chiamate API reali, raccolta metriche |
| **Rischio** | MEDIO — Alcuni canali potrebbero avere coverage molto bassa in produzione |
| **Priorità** | **MEDIA** — Importante per confidenza nella qualità, ma non bloccante per alpha |
| **Dipendenze** | Richiede GitHub token valido e tempo di esecuzione API reale |
| **Verifica** | Report coverage: ≥3 canali con coverage significativa (>100 repo/canale) |

**Analisi critica**: Questo task è essenzialmente un "test reale" del Layer A. È importante farlo, ma dovrebbe essere parte di un più ampio "real-world testing" pre-alpha, non un task isolato.

### Task 10.2 — Scoring explainability review

| Aspetto | Dettaglio |
|---------|-----------|
| **Obiettivo** | Review qualità explainability report su campione ampio, migliorare template |
| **Stato attuale** | ExplainabilityGenerator produce summary e full report con improvement suggestions |
| **Sforzo stimato** | Basso (1-2 giorni) |
| **Rischio** | BASSO |
| **Priorità** | **MEDIA** — Polish task, migliora usabilità |
| **Dipendenze** | Richiede output reali dalla pipeline (quindi dipende da test reali) |

### Task 10.3 — Output queryability

| Aspetto | Dettaglio |
|---------|-----------|
| **Obiettivo** | Verificare che API/CLI/MCP consentano query flessibili |
| **Stato attuale** | Filtri già implementati in tutti e tre gli interfacce |
| **Sforzo stimato** | Basso (0.5-1 giorno) |
| **Rischio** | BASSO |
| **Priorità** | **BASSA** — Validation task, la funzionalità esiste già |

### Task 10.4 — MCP endpoint stabilization

| Aspetto | Dettaglio |
|---------|-----------|
| **Obiettivo** | Test MCP con client reali (Kilo Code, Cursor, Claude Desktop) |
| **Stato attuale** | MCP server testato solo via ClientSession in-memory |
| **Sforzo stimato** | Medio-Alto (3-5 giorni) — richiede setup ambienti multipli |
| **Rischio** | **ALTO** — La compatibilità con client reali può rivelare problemi significativi (protocolli, serialization, transport) |
| **Priorità** | **ALTA** — Critico per marketplace e adozione |
| **Dipendenze** | Richiede accesso a client AI reali |

**Analisi critica**: Questo è il task più rischioso e importante. Il protocollo MCP è in evoluzione e ogni client può avere comportamenti diversi. È fondamentale testare con almeno 2 client reali prima di release pubblica.

### Task 10.5 — Kilo Marketplace packaging

| Aspetto | Dettaglio |
|---------|-----------|
| **Obiettivo** | Creare entry Kilo Marketplace con configurazione MCP predefinita |
| **Stato attuale** | `.kilo/mcp.json.template` esiste ma non è in formato marketplace |
| **Sforzo stimato** | Basso (0.5-1 giorno) — formato MCP.yaml è semplice e ben documentato |
| **Rischio** | BASSO |
| **Priorità** | **ALTA** — Essenziale per distribuzione |
| **Formato richiesto** | `mcps/github-discovery/MCP.yaml` nel repo [Kilo-Org/kilo-marketplace](https://github.com/Kilo-Org/kilo-marketplace) |

**Formato MCP.yaml richiesto** (basato su analisi del marketplace esistente):

```yaml
id: github-discovery
name: GitHub Discovery
description: >
  MCP-native agentic discovery engine that finds high-quality GitHub repositories
  independent of popularity (stars). Uses tiered scoring: discovery → screening →
  deep LLM assessment → explainable ranking with anti-star bias.
author: github-discovery-team
url: https://github.com/fulviocoschi/github-discovery
tags:
  - github
  - repository-discovery
  - code-quality
  - mcp
  - scoring
  - ranking
  - hidden-gems
prerequisites:
  - Python 3.12+
  - GitHub Personal Access Token
content:
  - name: UVX
    prerequisites:
      - Python 3.12+
      - uv
    content: |
      {
        "command": "uvx",
        "args": ["github-discovery", "mcp", "serve", "--transport", "stdio"],
        "env": {
          "GHDISC_GITHUB_TOKEN": "{{GHDISC_GITHUB_TOKEN}}"
        }
      }
  - name: Docker
    prerequisites:
      - Docker
    content: |
      {
        "command": "docker",
        "args": ["run", "-i", "--rm", "-e", "GHDISC_GITHUB_TOKEN",
                 "github-discovery/mcp-server"],
        "env": {
          "GHDISC_GITHUB_TOKEN": "{{GHDISC_GITHUB_TOKEN}}"
        }
      }
  - name: Remote Server
    content: |
      {
        "type": "streamable-http",
        "url": "https://your-server-url.com/mcp",
        "headers": {
          "Authorization": "Bearer {{GHDISC_GITHUB_TOKEN}}"
        }
      }
parameters:
  - name: GitHub Token
    key: GHDISC_GITHUB_TOKEN
    placeholder: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Task 10.6 — OpenCode agent template

| Aspetto | Dettaglio |
|---------|-----------|
| **Obiettivo** | Creare template `.config/opencode/agent/discovery.md` |
| **Stato attuale** | `ghdisc mcp init-config --target opencode` genera configurazione |
| **Sforzo stimato** | Basso (0.5 giorno) |
| **Rischio** | BASSO |
| **Priorità** | **MEDIA** — Nice-to-have per distribuzione |

### Task 10.7 — Performance optimization

| Aspetto | Dettaglio |
|---------|-----------|
| **Obiettivo** | Profiling bottleneck, caching, lazy loading, parallelizzazione |
| **Stato attuale** | FeatureStore SQLite caching esistente. Nessun profiling. |
| **Sforzo stimato** | Medio (2-3 giorni) |
| **Rischio** | MEDIO — Potrebbero emergere bottleneck inaspettati |
| **Priorità** | **MEDIA** — Importante per usabilità ma non bloccante alpha |

**Nota**: Il profiling reale richiede esecuzione con dati reali. Senza test reali, qualsiasi ottimizzazione è prematura.

### Task 10.8 — Documentation & user guides

| Aspetto | Dettaglio |
|---------|-----------|
| **Obiettivo** | README quickstart, ARCHITECTURE.md, API reference, MCP integration guide, CLI guide |
| **Stato attuale** | AGENTS.md (per agent) esiste. Nessuna doc user-facing. |
| **Sforzo stimato** | Medio-Alto (3-4 giorni) — doc completa richiede tempo significativo |
| **Rischio** | BASSO |
| **Priorità** | **ALTA** — Essenziale per adozione. Obiettivo: setup in <30 min |

**Documenti necessari**:
1. `README.md` — Quickstart: install → configure → run first discovery
2. `docs/ARCHITECTURE.md` — System architecture, tiered pipeline, MCP-native design
3. `docs/MCP_INTEGRATION.md` — Setup guide per Kilo Code, Claude Desktop, Cursor, OpenCode
4. `docs/CLI_GUIDE.md` — Comandi CLI con esempi
5. `docs/API_REFERENCE.md` — FastAPI endpoints, request/response formats
6. `docs/SCORING_METHODOLOGY.md` — Come funziona lo scoring, anti-star bias, dimensioni

### Task 10.9 — Docker packaging

| Aspetto | Dettaglio |
|---------|-----------|
| **Obiettivo** | Dockerfile multi-stage, docker-compose.yml (API + workers + MCP) |
| **Stato attuale** | Nessun Dockerfile |
| **Sforzo stimato** | Medio (1-2 giorni) |
| **Rischio** | BASSO — Standard Python Docker packaging |
| **Priorità** | **ALTA** — Essenziale per deployment flessibile |

**Struttura Docker proposta**:

```
Dockerfile          — Multi-stage: builder → runtime
docker-compose.yml  — 3 servizi: api, mcp-server, worker
```

Il Dockerfile deve supportare due modalità:
1. **MCP stdio mode**: `docker run -i github-discovery mcp serve --transport stdio`
2. **API + Worker mode**: `docker compose up` (FastAPI + workers + MCP HTTP)

### Task 10.10 — Alpha release

| Aspetto | Dettaglio |
|---------|-----------|
| **Obiettivo** | Tag v0.1.0-alpha, release notes, PyPI publish |
| **Stato attuale** | pyproject.toml ha già version = "0.1.0-alpha" |
| **Sforzo stimato** | Basso (0.5-1 giorno) |
| **Rischio** | BASSO |
| **Priorità** | **ALTA** — Deliverable finale |
| **Checklist** | vedi sezione 7 |

---

## 3. Cosa significa "deployment nel marketplace"

### Il Kilo Marketplace

Il [Kilo Marketplace](https://github.com/Kilo-Org/kilo-marketplace) è un repository GitHub curato che funge da **indice** di tre tipi di risorse:

| Tipo | Descrizione | Formato |
|------|-------------|---------|
| **Skills** | Workflow modulari che insegnano agli agent compiti specifici | `skills/<name>/SKILL.md` |
| **MCP Servers** | Integrazioni standardizzate via Model Context Protocol | `mcps/<name>/MCP.yaml` |
| **Modes** | Configurazioni personalizzate di comportamento agent | `modes/<name>/MODE.yaml` |

### GitHub Discovery nel Marketplace

GitHub Discovery si posiziona come **MCP Server** nel marketplace. Il deployment significa:

1. **Creare `mcps/github-discovery/MCP.yaml`** nel repo `Kilo-Org/kilo-marketplace` via PR
2. Il file YAML contiene:
   - `id`: `github-discovery`
   - `name`: `GitHub Discovery`
   - `description`: descrizione delle capacità
   - `author`: autore del progetto
   - `url`: link al repository GitHub del progetto
   - `content`: configurazione MCP in formato JSON (una o più opzioni di installazione)
   - `parameters`: parametri configurabili (es. GitHub Token)
   - `tags`: tag per discovery
   - `prerequisites`: prerequisiti software

3. Il marketplace NON ospita il codice sorgente — funge solo da indice. Il codice vive nel nostro repository.

### Opzioni di installazione supportate

Per un MCP server Python, le opzioni standard sono:

| Opzione | Comando | Prerequisiti |
|---------|---------|--------------|
| **UVX** | `uvx github-discovery mcp serve --transport stdio` | Python 3.12+, uv |
| **pip + command** | `pip install github-discovery && ghdisc mcp serve --transport stdio` | Python 3.12+ |
| **Docker** | `docker run -i github-discovery/mcp-server` | Docker |
| **Remote HTTP** | `{ "type": "streamable-http", "url": "..." }` | URL server remoto |

Il formato del `content` nel MCP.yaml è esattamente la configurazione JSON che il client AI (Kilo Code, Claude Desktop) usa per avviare il server MCP. Per esempio:

```json
{
  "command": "uvx",
  "args": ["github-discovery", "mcp", "serve", "--transport", "stdio"],
  "env": {
    "GHDISC_GITHUB_TOKEN": "{{GHDISC_GITHUB_TOKEN}}"
  }
}
```

Quando un utente installa il MCP server dal marketplace, il client AI genera questa configurazione nel proprio file di configurazione (es. `kilo.json` per Kilo Code).

### Processo di pubblicazione

1. Creare `mcps/github-discovery/MCP.yaml` nel fork di `Kilo-Org/kilo-marketplace`
2. Aprire PR verso `Kilo-Org/kilo-marketplace` main branch
3. Review da parte del team Kilo
4. Merge → il server è disponibile nel marketplace

---

## 4. Modalità di installazione e configurazione

### 4.1 Installazione via Kilo Marketplace (target primario)

**Flusso utente ideale**:
1. Utente apre Kilo Code → Settings → MCP → Add from Marketplace
2. Seleziona "GitHub Discovery"
3. Inserisce il proprio GitHub Token
4. Il server è configurato e funzionante

**Requisito tecnico**: Il pacchetto deve essere pubblicato su PyPI per supportare `uvx github-discovery`.

### 4.2 Installazione manuale via Kilo Code / Kilocode CLI

**Configurazione manuale** in `kilo.json` o `.kilo/mcp.json`:

```json
{
  "mcp": {
    "github-discovery": {
      "type": "local",
      "command": ["uvx", "github-discovery", "mcp", "serve", "--transport", "stdio"],
      "environment": {
        "GHDISC_GITHUB_TOKEN": "{env:GITHUB_TOKEN}",
        "GHDISC_SESSION_BACKEND": "sqlite"
      }
    }
  }
}
```

**In alternativa**, usare il comando built-in:
```bash
ghdisc mcp init-config --target kilo
```
Che genera automaticamente la configurazione.

### 4.3 Installazione via OpenCode

**Configurazione** in `opencode.jsonc`:

```jsonc
{
  "mcp": {
    "github-discovery": {
      "command": "uvx",
      "args": ["github-discovery", "mcp", "serve", "--transport", "stdio"],
      "env": {
        "GHDISC_GITHUB_TOKEN": "$GITHUB_TOKEN"
      }
    }
  }
}
```

### 4.4 Installazione via Docker

```bash
# MCP stdio mode (per client AI locali)
docker run -i --rm \
  -e GHDISC_GITHUB_TOKEN=ghp_xxx \
  github-discovery/mcp-server

# API + Worker mode (per deployment)
docker compose up
```

### 4.5 Configurazione ambiente

**Variabili d'ambiente richieste**:

| Variabile | Obbligatoria | Descrizione |
|-----------|-------------|-------------|
| `GHDISC_GITHUB_TOKEN` | **Sì** | GitHub Personal Access Token |
| `GHDISC_LLM_API_KEY` | Solo per Gate 3 | API key per LLM provider (NanoGPT) |
| `GHDISC_SESSION_BACKEND` | No (default: sqlite) | Backend sessioni (sqlite/redis) |

**Variabili opzionali principali**:

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `GHDISC_MCP_TRANSPORT` | stdio | Transport MCP (stdio/streamable-http) |
| `GHDISC_MCP_HOST` | 127.0.0.1 | Host per HTTP transport |
| `GHDISC_MCP_PORT` | 8080 | Porta per HTTP transport |
| `GHDISC_MCP_MAX_CONTEXT_TOKENS` | 2000 | Limite token per tool invocation |
| `GHDISC_API_HOST` | 127.0.0.1 | Host API REST |
| `GHDISC_API_PORT` | 8000 | Porta API REST |
| `GHDISC_LOG_LEVEL` | INFO | Livello di logging |

---

## 5. Testare ora o implementare Phase 10?

### La domanda chiave

Il sistema ha **1314 test, tutti con mock**. Nessun test ha mai toccato API GitHub reali, LLM reali, o client MCP reali. Questo è un gap significativo.

### Argomenti per testare PRIMA di Phase 10

1. **Rischio di alpha inutilizzabile**: Se pubblichi un pacchetto PyPI che non funziona con API reali, la prima impressione degli utenti è rovinata.
2. **I mock nascondono bug**: I test mockano `httpx`, ma il comportamento reale di GitHub API (rate limiting, paginazione, risposte inaspettate) può rompere il sistema.
3. **Il canale Dependency è vuoto**: `DependencyChannel.discover_dependents()` restituisce sempre una lista vuota. Questo è un gap funzionale che i test mock non evidenziano.
4. **LLM provider non testato con API reale**: Il provider NanoGPT usa instructor+openai ma è testato solo con mock. Risposte reali possono rompere il parser.
5. **I task 10.1, 10.4, 10.7 richiedono dati reali**: Performance optimization, discovery validation e MCP stabilization richiedono esecuzione reale.

### Argomenti per implementare Phase 10 e testare dopo

1. **Alpha = "non production-ready"**: Il suffisso -alpha implica che il sistema può avere difetti. È meglio distribuire e raccogliere feedback.
2. **Il testing reale richiede tempo e risorse**: Sprint0 reale su 500 repo con LLM costa token e tempo.
3. **La documentazione è più urgente**: Senza docs, anche un sistema perfetto è inutilizzabile.
4. **Il packaging è prerequisite per testing reale**: Per testare con client reali serve un pacchetto installabile.

### Analisi dei gap critici dal Phase 9 verification

La verifica post-implementazione di Phase 8+9 ha identificato questi **gap documentati ma non corretti**:

| Gap | Impatto | Rischio per alpha |
|-----|---------|-------------------|
| Task 9.5 (Blind Human Evaluation) non implementato | MEDIO — nessuna validazione umana del ranking | BASSO — non bloccante per alpha |
| Sprint0 tests mockano tutta la pipeline interna | MEDIO — viola principio "mock only externals" | MEDIO — test non garantiscono funzionamento reale |
| 27 CLI tests sono superficiali (solo mock.called) | BASSO — test non verificano logica business | BASSO |
| MCP tests usano ClientSession in-memory, non client reali | ALTO — compatibilità con client reali non verificata | ALTO |
| OSV adapter ritorna confidence=0.0 (senza lockfile parsing) | MEDIO — scoring incompleto | MEDIO |
| Dependency channel sempre vuoto | BASSO — coverage ridotta | BASSO |

---

## 6. Raccomandazione strategica

### Verdetto: APPROCCIO IBRIDO — Test reale limitato PRIMA, poi Phase 10

**Raccomando un approccio in 3 fasi**:

### Fase A: Smoke Test Reale (2-3 giorni)

Prima di iniziare Phase 10, eseguire un **smoke test reale** mirato:

1. **Pipeline E2E con API GitHub reali** (30-50 repo, 1-2 query)
   - Verificare che discovery, screening, scoring funzionino con dati reali
   - Misurare tempi reali per Gate 0→1→2
   - Identificare errori di paginazione, rate limiting, parsing

2. **MCP server con un client reale** (Kilo Code o Claude Desktop)
   - Avviare `ghdisc mcp serve --transport stdio`
   - Chiamare 3-4 tool MCP da client reale
   - Verificare serialization, transport, error handling

3. **CLI smoke test**
   - Eseguire `ghdisc discover --query "static analysis python" --max 20`
   - Verificare output e gestione errori

**Se lo smoke test passa senza bug critici** → procedere con Phase 10.
**Se lo smoke test rileva bug critici** → fixare i bug prima di Phase 10.

### Fase B: Phase 10 — Implementazione (5-7 giorni)

Implementare Phase 10 con la priorità seguente:

| Priorità | Task | Giorni | Rationale |
|----------|------|--------|-----------|
| P0 | 10.5 Marketplace packaging | 0.5 | Essenziale per distribuzione, sforzo minimo |
| P0 | 10.9 Docker packaging | 1.5 | Essenziale per deployment flessibile |
| P0 | 10.8 Documentazione | 3 | Essenziale per adozione |
| P0 | 10.10 Alpha release | 0.5 | Deliverable finale |
| P1 | 10.4 MCP stabilization | 2 | Importante ma richiede client reali |
| P2 | 10.1 Discovery validation | 1.5 | Importante ma non bloccante |
| P2 | 10.6 OpenCode template | 0.5 | Nice-to-have |
| P2 | 10.7 Performance optimization | 2 | Prematuro senza profiling reale |
| P3 | 10.2 Explainability review | 1 | Polish |
| P3 | 10.3 Output queryability | 0.5 | Già funzionante |

### Fase C: Post-Alpha Validation (dopo release)

Dopo la alpha release, pianificare:
1. Sprint0 reale completo (500+ repo, con LLM se budget disponibile)
2. Human evaluation (Task 9.5)
3. Performance profiling su volume reale
4. Feedback da utenti alpha

### Perché non "solo testing" o "solo implementazione"

- **Solo testing** ritarda il packaging e la docs che servono per distribuire
- **Solo implementazione** rischia di impacchettare un sistema rotto
- **L'approccio ibrido** minimizza il rischio: smoke test rapido → fix critici → packaging

---

## 7. Piano di implementazione proposto

### Wave 0: Pre-Phase 10 — Smoke Test Reale (2-3 giorni)

| Step | Azione | Verifica |
|------|--------|----------|
| 0.1 | Eseguire discovery reale: 30-50 repo da 3+ query diverse | Pool generato senza errori |
| 0.2 | Eseguire screening reale: Gate 1+2 su pool | Risultati scoring coerenti |
| 0.3 | Eseguire MCP server via stdio + test con client reale | Tools richiamabili |
| 0.4 | Eseguire CLI end-to-end: discover → screen → rank | Output formattato correttamente |
| 0.5 | Fixare bug critici trovati | Pipeline E2E funzionante |

### Wave 1: Packaging & Distribuzione (2-3 giorni)

| Step | Task Roadmap | Azione | Verifica |
|------|-------------|--------|----------|
| 1.1 | 10.9 | Creare Dockerfile multi-stage | `docker build .` passa |
| 1.2 | 10.9 | Creare docker-compose.yml | `docker compose up` funziona |
| 1.3 | 10.5 | Creare MCP.yaml per marketplace | Formato valido |
| 1.4 | 10.5 | Creare Skill SKILL.md per marketplace (opzionale) | Formato valido |
| 1.5 | 10.6 | Creare OpenCode agent template | Config funzionante |

### Wave 2: Documentazione (2-3 giorni)

| Step | Task Roadmap | Azione | Verifica |
|------|-------------|--------|----------|
| 2.1 | 10.8 | README.md con quickstart (install → configure → run) | Utente nuovo setup in <30 min |
| 2.2 | 10.8 | docs/ARCHITECTURE.md | Descrive pipeline, MCP design |
| 2.3 | 10.8 | docs/MCP_INTEGRATION.md (Kilo, Claude, Cursor, OpenCode) | Guide per ogni client |
| 2.4 | 10.8 | docs/CLI_GUIDE.md | Ogni comando documentato |
| 2.5 | 10.8 | docs/SCORING_METHODOLOGY.md | Anti-star bias, dimensioni, Value Score |

### Wave 3: Stabilizzazione & Alpha Release (2-3 giorni)

| Step | Task Roadmap | Azione | Verifica |
|------|-------------|--------|----------|
| 3.1 | 10.4 | Test MCP con Kilo Code (o altro client disponibile) | Workflow completo |
| 3.2 | 10.1 | Discovery validation: coverage per canale | Report |
| 3.3 | 10.10 | PyPI publish (test pypi prima, poi pypi) | `pip install github-discovery` funziona |
| 3.4 | 10.10 | Git tag v0.1.0-alpha + release notes | Tag + GitHub Release |
| 3.5 | 10.10 | PR al Kilo Marketplace | PR aperta |

### Wave 4: Post-Alpha (ongoing)

- Task 10.7 Performance optimization (basato su profiling reale)
- Task 10.2 Explainability review (basato su output reali)
- Sprint0 completo con LLM reale
- Human evaluation
- Feedback utenti alpha

---

## 8. Rischi e mitigazioni

| Rischio | Probabilità | Impatto | Mitigazione |
|---------|-------------|---------|-------------|
| **Smoke test rileva bug critici nella pipeline reale** | ALTA | ALTO | Tempo preventivato per fix nel Wave 0 |
| **MCP non compatibile con client reali** | MEDIA | ALTO | Test prioritario nel Wave 3; fallback a documentazione manuale |
| **PyPI publish fallito per configurazione** | BASSA | MEDIO | Test prima su TestPyPI |
| **Dockerfile non builda correttamente** | BASSA | MEDIO | Multi-stage standard, test locale |
| **LLM provider (NanoGPT) down o lento** | MEDIA | MEDIO | Alpha può funzionare senza Gate 3 (solo Gate 1+2 per demo) |
| **Rate limiting GitHub API durante testing** | ALTA | BASSO | Throttling, conditional requests, caching |
| **Kilo Marketplace PR non accettata** | MEDIA | BASSO | Distribuzione alternativa via PyPI + docs manuali |

### Criteri go/no-go per alpha release

| Criterio | Obbligatorio | Misura |
|----------|-------------|--------|
| Pipeline Gate 0→1→2 funziona con API GitHub reali | **Sì** | 50+ repo processate senza crash |
| MCP server avviabile via stdio | **Sì** | Client MCP può listare tools |
| CLI produce output leggibile | **Sì** | `ghdisc discover --query X` funziona |
| Docker build passa | **Sì** | `docker build .` exit 0 |
| README quickstep verificato | **Sì** | Nuovo utente setup in <30 min |
| Gate 3 (LLM) funzionante con API reale | No | Alpha può funzionare senza |
| Test con 2+ client MCP reali | No | Documentato come known limitation |

---

## Appendice A: Fonti research

| Fonte | Tipo | Contenuto |
|-------|------|-----------|
| `docs/llm-wiki/wiki/index.md` | Wiki | Stato compilato progetto |
| `docs/llm-wiki/wiki/log.md` | Wiki | Cronologia operazioni |
| `docs/llm-wiki/wiki/patterns/phase9-feasibility-plan.md` | Wiki | Phase 9 dettagli |
| `docs/llm-wiki/wiki/apis/mcp-sdk-verification.md` | Wiki | MCP SDK Context7-verified |
| `docs/roadmaps/github-discovery_foundation_roadmap.md` | Raw | Roadmap Phase 10 |
| `progress.md` | Raw | Log progresso |
| `.workflow/state.md` | Raw | Stato workflow |
| [Kilo-Org/kilo-marketplace](https://github.com/Kilo-Org/kilo-marketplace) — README.md | External | Marketplace structure |
| [Kilo-Org/kilo-marketplace](https://github.com/Kilo-Org/kilo-marketplace) — CONTRIBUTING.md | External | MCP.yaml format, skill format |
| [Kilo-Org/kilo-marketplace](https://github.com/Kilo-Org/kilo-marketplace) — `mcps/github/MCP.yaml` | External | Esempio MCP marketplace entry |
| [Kilo-Org/kilo-marketplace](https://github.com/Kilo-Org/kilo-marketplace) — `mcps/context7/MCP.yaml` | External | Esempio MCP con multiple install options |
| Context7 `/modelcontextprotocol/python-sdk` | Context7 | FastMCP transport patterns (stdio, streamable-http) |

## Appendice B: Esempio MCP.yaml per GitHub Discovery

```yaml
id: github-discovery
name: GitHub Discovery
description: >
  MCP-native agentic discovery engine that finds high-quality GitHub repositories
  independent of popularity. Uses tiered scoring pipeline: multi-channel discovery →
  metadata screening → static/security screening → deep LLM assessment → anti-star
  bias ranking with explainability.
author: github-discovery-team
url: https://github.com/fulviocoschi/github-discovery
tags:
  - github
  - repository-discovery
  - code-quality
  - scoring
  - ranking
  - hidden-gems
  - mcp
  - assessment
prerequisites:
  - GitHub Personal Access Token (generate at https://github.com/settings/tokens/new)
content:
  - name: UVX (recommended)
    prerequisites:
      - Python 3.12+
      - uv package manager
    content: |
      {
        "command": "uvx",
        "args": ["github-discovery", "mcp", "serve", "--transport", "stdio"],
        "env": {
          "GHDISC_GITHUB_TOKEN": "{{GHDISC_GITHUB_TOKEN}}"
        }
      }
  - name: Docker
    prerequisites:
      - Docker
    content: |
      {
        "command": "docker",
        "args": ["run", "-i", "--rm", "-e", "GHDISC_GITHUB_TOKEN",
                 "ghcr.io/fulviocoschi/github-discovery:latest"],
        "env": {
          "GHDISC_GITHUB_TOKEN": "{{GHDISC_GITHUB_TOKEN}}"
        }
      }
parameters:
  - name: GitHub Token
    key: GHDISC_GITHUB_TOKEN
    placeholder: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (classic PAT from https://github.com/settings/tokens/new)
```
