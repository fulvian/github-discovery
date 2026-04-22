# GitHub Discovery — Phase 2 Implementation Plan

## Meta

- **Stato**: Draft v1
- **Data**: 2026-04-22
- **Riferimento roadmap**: `docs/roadmaps/github-discovery_foundation_roadmap.md` — Phase 2
- **Riferimento blueprint**: `docs/foundation/github-discovery_foundation_blueprint.md` — §6 (Layer A), §8, §16.2, §18
- **Riferimento wiki**: `docs/llm-wiki/wiki/` — articoli su discovery channels, GitHub API patterns, tiered pipeline
- **Durata stimata**: 2-3 settimane
- **Milestone**: M1 — Discovery MVP (pool di candidati da 3+ canali, deduplica funzionante)
- **Dipendenza**: Phase 0+1 completate (142 tests passing, `make ci` verde)

---

## Indice

1. [Obiettivo](#1-obiettivo)
2. [Task Overview](#2-task-overview)
3. [Architettura del modulo discovery](#3-architettura-del-modulo-discovery)
4. [Task 2.1 — GitHub REST API Client](#4-task-21--github-rest-api-client)
5. [Task 2.2 — GitHub GraphQL Client](#5-task-22--github-graphql-client)
6. [Task 2.3 — Search API Channel](#6-task-23--search-api-channel)
7. [Task 2.4 — Code Search Channel](#7-task-24--code-search-channel)
8. [Task 2.5 — Dependency Graph Channel](#8-task-25--dependency-graph-channel)
9. [Task 2.6 — Package Registry Channel](#9-task-26--package-registry-channel)
10. [Task 2.7 — Awesome Lists & Curated Sources Channel](#10-task-27--awesome-lists--curated-sources-channel)
11. [Task 2.8 — Seed Expansion](#11-task-28--seed-expansion)
12. [Task 2.9 — Discovery Orchestrator](#12-task-29--discovery-orchestrator)
13. [Task 2.10 — Candidate Pool Manager](#13-task-210--candidate-pool-manager)
14. [Sequenza di implementazione](#14-sequenza-di-implementazione)
15. [Test plan](#15-test-plan)
16. [Criteri di accettazione](#16-criteri-di-accettazione)
17. [Rischi e mitigazioni](#17-rischi-e-mitigazioni)
18. [Verifica Context7 completata](#18-verifica-context7-completata)

---

## 1) Obiettivo

Implementare la pipeline di discovery multicanale (Layer A / Gate 0) che produce un pool di candidati `RepoCandidate` con `discovery_score` preliminare. La pipeline coordina 6 canali di discovery, deduplica per `full_name`, e persiste il pool per le fasi successive (Screening Gate 1+2).

Al completamento della Phase 2:

- Discovery pipeline produce pool di candidati da almeno 3 canali attivi
- Deduplica funzionante per `full_name` attraverso canali diversi
- Score preliminare `discovery_score` assegnato a ogni candidato
- Rate limiting rigoroso: rispetto dei limiti GitHub REST (5000/hr core, 30/min search, 10/min code search) e GraphQL (point-cost)
- Paginazione rigorosa: REST (Link header, per_page/page), GraphQL (cursor-based first/after con pageInfo)
- Conditional requests (`ETag`/`If-None-Match`) per evitare chiamate non necessarie
- Tutti i moduli passano `mypy --strict` e `ruff check`
- Test coverage >80% sulla logica di discovery con mock `pytest-httpx`

---

## 2) Task Overview

| Task ID | Task | Priorità | Dipendenze | Output verificabile |
|---------|------|----------|------------|---------------------|
| 2.1 | GitHub REST API Client | Critica | Phase 1 | Client httpx con auth, rate limit, retry, conditional requests, paginazione |
| 2.2 | GitHub GraphQL Client | Critica | 2.1 | Client GraphQL con cursor-based pagination, batch cost control |
| 2.3 | Search API Channel | Critica | 2.1 | Canale operativo: query builder, filtri avanzati, sort recency |
| 2.4 | Code Search Channel | Alta | 2.1 | Canale operativo: quality signal pattern search |
| 2.5 | Dependency Graph Channel | Media | 2.1 | Canale operativo: dependency/dependent traversal da seed |
| 2.6 | Package Registry Channel | Media | — | Canale operativo: almeno PyPI + npm |
| 2.7 | Awesome Lists Channel | Alta | 2.1 | Canale operativo: parser awesome-X README |
| 2.8 | Seed Expansion | Media | 2.1, 2.2 | Co-contributor, org adjacency, co-dependency |
| 2.9 | Discovery Orchestrator | Critica | 2.3-2.8 | Pipeline end-to-end con concorrenza, dedup, scoring |
| 2.10 | Candidate Pool Manager | Critica | Phase 1 (CandidatePool) | Persistenza SQLite, CRUD, stato per candidato |

---

## 3) Architettura del modulo discovery

### Struttura directory

```
src/github_discovery/discovery/
├── __init__.py              # Export pubblici del package discovery
├── github_client.py         # REST API client (httpx.AsyncClient wrapper)
├── graphql_client.py        # GraphQL API client (cursor-based pagination)
├── search_channel.py        # Search API channel (query builder + filtri)
├── code_search_channel.py   # Code Search channel (quality signal patterns)
├── dependency_channel.py    # Dependency graph traversal channel
├── registry_channel.py      # Package registry mapping channel
├── curated_channel.py       # Awesome lists & curated sources parser
├── seed_expansion.py        # Seed expansion (co-contributor, org adjacency)
├── orchestrator.py          # Discovery orchestrator (coordination + dedup)
├── pool.py                  # Candidate pool persistence (SQLite-backed)
└── types.py                 # Tipi condivisi discovery (query, result, channel config)

tests/
├── unit/
│   └── discovery/
│       ├── test_github_client.py
│       ├── test_graphql_client.py
│       ├── test_search_channel.py
│       ├── test_code_search_channel.py
│       ├── test_dependency_channel.py
│       ├── test_registry_channel.py
│       ├── test_curated_channel.py
│       ├── test_seed_expansion.py
│       ├── test_orchestrator.py
│       ├── test_pool.py
│       └── conftest.py      # Shared fixtures (mock responses, sample repos)
└── integration/
    └── discovery/
        └── test_discovery_e2e.py  # End-to-end with real API (marked @pytest.mark.integration)
```

### Modelli esistenti riutilizzati

Da Phase 1, i seguenti modelli sono già disponibili e non necessitano modifica:

| Modello | File | Utilizzo in Phase 2 |
|---------|------|---------------------|
| `RepoCandidate` | `models/candidate.py` | Output di ogni canale → pool |
| `CandidatePool` | `models/candidate.py` | Container per pool + metadata |
| `DiscoveryChannel` | `models/enums.py` | Enum canali (SEARCH, CODE_SEARCH, etc.) |
| `CandidateStatus` | `models/enums.py` | Stato pipeline (DISCOVERED iniziale) |
| `DomainType` | `models/enums.py` | Classificazione dominio |
| `SessionState` | `models/session.py` | Sessione agentica (session_id) |
| `GitHubSettings` | `config.py` | token, api_base_url, graphql_url, timeout, max_concurrent |
| `DiscoverySettings` | `config.py` | max_candidates, default_channels |
| `DiscoveryError` | `exceptions.py` | Errore dominio discovery |
| `RateLimitError` | `exceptions.py` | Rate limit exceeded con reset_at, remaining |

### Tipi nuovi necessari (types.py)

```python
# Tipi condivisi per il discovery engine — definiti qui per evitare
# import circolari tra i moduli del package.

class DiscoveryQuery(BaseModel):
    """Input per una query di discovery."""
    query: str                                    # Termine di ricerca
    channels: list[DiscoveryChannel] | None       # Override canali (None = default)
    max_candidates: int = 500                     # Limite candidati
    language: str | None = None                   # Filtro linguaggio
    topics: list[str] | None = None               # Filtro topic
    domain_hint: DomainType | None = None         # Hint per classificazione
    session_id: str | None = None                 # Sessione agentica

class ChannelResult(BaseModel):
    """Risultato di un singolo canale di discovery."""
    channel: DiscoveryChannel
    candidates: list[RepoCandidate]
    total_found: int                              # Totale disponibile (potenzialmente > restituiti)
    has_more: bool                                # Ci sono più risultati paginati
    rate_limit_remaining: int | None              # Rate limit rimanente dopo la query
    elapsed_seconds: float

class DiscoveryResult(BaseModel):
    """Risultato aggregato della discovery orchestrator."""
    pool_id: str                                  # UUID del pool
    total_candidates: int                         # Dopo dedup
    candidates_by_channel: dict[str, int]         # Conteggio per canale (pre-dedup)
    channels_used: list[DiscoveryChannel]
    duplicate_count: int                          # Repo trovati da più canali
    elapsed_seconds: float
    session_id: str | None = None
```

### Flusso dati

```
DiscoveryQuery
    │
    ├─► SearchChannel.search(query) ──────────────► ChannelResult (candidates)
    ├─► CodeSearchChannel.search(query) ──────────► ChannelResult (candidates)
    ├─► DependencyChannel.discover(seed_urls) ────► ChannelResult (candidates)
    ├─► RegistryChannel.search(query) ────────────► ChannelResult (candidates)
    ├─► CuratedChannel.parse(awesome_lists) ──────► ChannelResult (candidates)
    ├─► SeedExpansion.expand(seed_urls) ──────────► ChannelResult (candidates)
    │
    └─► Orchestrator.discover(query)
            │
            ├── Coordina canali (asyncio.gather con Semaphore)
            ├── Deduplica per full_name
            ├── Calcola discovery_score (breadth signal)
            ├── Aggiorna pool (SQLite)
            └── Ritorna DiscoveryResult
```

---

## 4) Task 2.1 — GitHub REST API Client

### Obiettivo

Client HTTP robusto basato su `httpx.AsyncClient` che gestisce autenticazione, rate limiting, retry, conditional requests e paginazione per le GitHub REST API.

### Context7: Pattern verificati

Da `/encode/httpx`:
- `httpx.AsyncClient` come async context manager per connection pooling
- `httpx.AsyncHTTPTransport(retries=3)` per retry automatico a livello trasporto
- `httpx.Auth` subclass per Bearer token authentication (`auth_flow` method)
- Event hooks async (`event_hooks={"response": [hook]}`) per logging e rate limit tracking
- `response.headers` per accedere a `x-ratelimit-remaining`, `x-ratelimit-reset`, `etag`

Da `/websites/github_en_rest`:
- Rate limits: core 5000/hr, search 30/min, code_search 10/min
- `GET /rate_limit` per monitoring (non conta contro rate limit)
- Conditional requests: `If-None-Match: "{etag}"` → 304 Not Modified (non conta contro rate limit se autenticato)
- Paginazione REST: `Link` header con `rel="next"`, `rel="last"`, parametri `per_page` (max 100) e `page`
- Header richiesto: `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`

### Design

```python
# discovery/github_client.py

class GitHubRestClient:
    """Async client for GitHub REST API with rate limit awareness,
    retry, conditional requests, and pagination."""

    def __init__(self, settings: GitHubSettings) -> None: ...

    async def get(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        etag: str | None = None,         # Conditional request
    ) -> httpx.Response: ...

    async def get_all_pages(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        max_pages: int = 10,             # Safety limit
        per_page: int = 100,
    ) -> list[dict[str, object]]: ...

    async def search(
        self,
        endpoint: str,                   # /search/repositories or /search/code
        query: str,
        *,
        sort: str | None = None,
        order: str = "desc",
        max_pages: int = 5,
        per_page: int = 100,
    ) -> tuple[list[dict[str, object]], int]:
        """Returns (items, total_count). Respects search rate limits."""
        ...

    @property
    def rate_limit_remaining(self) -> int | None: ...

    @property
    def rate_limit_reset_at(self) -> datetime | None: ...

    async def check_rate_limit(self) -> dict[str, int]:
        """GET /rate_limit — does not count against limits."""
        ...

    async def close(self) -> None: ...

    async def __aenter__(self) -> GitHubRestClient: ...
    async def __aexit__(self, *args: object) -> None: ...
```

### Implementazione dettagliata

1. **Autenticazione**: Subclass `httpx.Auth` con `Bearer {token}` header
2. **Transport retry**: `httpx.AsyncHTTPTransport(retries=3)` per retry su connection errors
3. **Rate limit tracking**: Event hook async su response per estrarre `x-ratelimit-*` headers e aggiornare stato interno
4. **Rate limit enforcement**: Prima di ogni richiesta, check `remaining < threshold` (configurable, default 50) → `RateLimitError` con `reset_at`
5. **Conditional requests**: Se `etag` fornito, aggiunge `If-None-Match` header → gestisce 304 returnando cache o None
6. **Paginazione REST**: Parse `Link` header per `rel="next"` URL, itera con `max_pages` safety limit
7. **Search rate limiting**: Prima di chiamata search, verifica rate limit specifico (30/min per search, 10/min per code search) → sleep/warning se vicino al limite
8. **Logging**: structlog con contesto (url, status_code, rate_limit_remaining, elapsed_ms)

### Test plan

- `test_github_client.py`: Mock con `pytest-httpx` (già dipendenza integration)
  - `test_bearer_auth_header`: Verifica header `Authorization: Bearer {token}`
  - `test_rate_limit_tracking`: Mock response con `x-ratelimit-remaining` header → proprietà aggiornata
  - `test_rate_limit_enforcement`: Mock remaining=5 → `RateLimitError` sollevata
  - `test_conditional_request_etag`: Mock etag → verifica `If-None-Match` header inviato
  - `test_conditional_request_304`: Mock 304 response → gestisce correttamente
  - `test_pagination_single_page`: Mock response senza Link header → singola pagina
  - `test_pagination_multiple_pages`: Mock 3 pagine con Link header → tutti gli items raccolti
  - `test_pagination_max_pages_limit`: Mock >max_pages pagine → si ferma al limite
  - `test_search_rate_limiting`: Mock search rate near limit → backoff o errore
  - `test_retry_on_connection_error`: Mock ConnectError poi successo → retry funzionante
  - `test_context_manager`: Verifica `async with` pattern
  - `test_search_returns_items_and_total`: Mock search response → (items, total_count) tuple

### Dipendenze pyproject.toml

Nessuna nuova dipendenza richiesta — `httpx>=0.28` e `pytest-httpx>=0.30` già presenti.

### Criterio di verifica

```bash
pytest tests/unit/discovery/test_github_client.py -v   # 12 tests passing
mypy src/github_discovery/discovery/github_client.py --strict  # 0 errors
```

---

## 5) Task 2.2 — GitHub GraphQL Client

### Obiettivo

Client GraphQL per query aggregate con cursor-based pagination (`first/after` + `pageInfo`), controllo cost query, e rate limit awareness.

### Context7: Pattern verificati

Da `/websites/github_en_graphql`:
- Cursor-based pagination: `first: 100, after: null` per prima pagina, `after: "{endCursor}"` per successive
- `pageInfo { hasNextPage endCursor startCursor hasPreviousPage }` per navigazione
- `rateLimit { cost remaining resetAt }` per monitoring cost per query
- Batch controllato: `first` max 100 per connection
- Cost model: query più complesse costano più punti

### Design

```python
# discovery/graphql_client.py

class GitHubGraphQLClient:
    """GraphQL client for GitHub API with cursor-based pagination
    and query cost management."""

    def __init__(self, settings: GitHubSettings) -> None: ...

    async def execute(
        self,
        query: str,
        variables: dict[str, object] | None = None,
    ) -> dict[str, object]: ...

    async def paginate(
        self,
        query: str,
        *,
        variables: dict[str, object] | None = None,
        page_size: int = 100,
        max_pages: int = 10,
        connection_path: str = "data.repository",  # Path to connection in response
    ) -> list[dict[str, object]]:
        """Cursor-based pagination over a GraphQL connection.
        Automatically follows pageInfo.hasNextPage / endCursor."""
        ...

    async def close(self) -> None: ...
    async def __aenter__(self) -> GitHubGraphQLClient: ...
    async def __aexit__(self, *args: object) -> None: ...
```

### Implementazione dettagliata

1. **Query execution**: POST a `{graphql_url}` con `{"query": ..., "variables": ...}`
2. **Error handling**: Parse `errors` array in response → `DiscoveryError` con dettagli
3. **Cost monitoring**: Se `rateLimit` field presente nella response → log cost + check remaining
4. **Cursor-based pagination**: Itera `pageInfo.hasNextPage` con `endCursor` come `after` nella query successiva
5. **Rate limit**: Stessi controlli del REST client (i rate limits sono separati per GraphQL)
6. **Timeout**: `{request_timeout}` seconds per query (da config)

### Test plan

- `test_graphql_client.py`: Mock con `pytest-httpx`
  - `test_execute_simple_query`: Mock response → dict result
  - `test_execute_with_variables`: Mock → variabili passate correttamente
  - `test_execute_handles_errors`: Mock errors array → DiscoveryError
  - `test_paginate_single_page`: Mock hasNextPage=false → singola pagina di items
  - `test_paginate_multiple_pages`: Mock 3 pagine con cursor → tutti items raccolti
  - `test_paginate_max_pages_limit`: Mock >max_pages → si ferma al limite
  - `test_cost_monitoring`: Mock rateLimit field → logging + remaining check
  - `test_context_manager`: async with pattern

### Criterio di verifica

```bash
pytest tests/unit/discovery/test_graphql_client.py -v   # 8 tests passing
mypy src/github_discovery/discovery/graphql_client.py --strict
```

---

## 6) Task 2.3 — Search API Channel

### Obiettivo

Canale di discovery primario basato su GitHub Search API (`GET /search/repositories`). Supporta query builder con filtri avanzati (topic, language, date range, size, forks), ordinamento per recency/updated per ridurre bias popolarità.

### Context7: Pattern verificati

Da `/websites/github_en_rest`:
- Endpoint: `GET /search/repositories`
- Parametri: `q` (query con qualifiers), `sort` (stars/forks/help-wanted-issues/updated), `order` (asc/desc), `per_page` (max 100), `page`
- Response: `total_count`, `incomplete_results`, `items[]` (repo objects)
- Rate limit: 30 requests/min (authenticated)
- Qualifiers supportati: `language:`, `topic:`, `pushed:`, `created:`, `size:`, `forks:`, `license:`, `archived:`, `is:public`
- Sort by `updated` riduce popolarità bias vs sort by `stars`

### Design

```python
# discovery/search_channel.py

class SearchChannel:
    """GitHub Search API discovery channel.

    Uses /search/repositories with structured queries.
    Sorts by recency/updated by default to reduce popularity bias.
    """

    def __init__(self, client: GitHubRestClient) -> None: ...

    async def search(
        self,
        query: DiscoveryQuery,
    ) -> ChannelResult: ...

    def build_query(
        self,
        query: DiscoveryQuery,
    ) -> str:
        """Build GitHub search query string with qualifiers.
        Examples:
            'static analysis language:python pushed:>2024-01-01 topic:testing'
            'web framework language:typescript topic:backend -stars:>10000'
        """
        ...
```

### Implementazione dettagliata

1. **Query builder**: Costruisce stringa `q` con keyword + qualifiers
   - `language:{lang}` se `query.language` specificato
   - `topic:{t}` per ogni topic in `query.topics`
   - `pushed:>{6_months_ago}` per escludere repo inattivi (default)
   - `archived:false` per escludere repo archiviati
   - `is:public` per escludere repo privati
   - `-stars:>100000` opzionale per escludere mega-popular (configurable)
2. **Sort strategy**: Default `sort=updated&order=desc` per ridurre bias popolarità. Alternativa: `sort=stars&order=asc` per hidden gems
3. **Pagination**: Usa `client.search()` con `max_pages` basato su `max_candidates / per_page`
4. **Rate limit**: Prima di ogni batch, verifica search rate limit (30/min) → sleep se necessario
5. **Mapping**: Ogni item → `RepoCandidate.model_validate(item)` con `source_channel=DiscoveryChannel.SEARCH`
6. **discovery_score preliminare**: Basato su GitHub search `score` field + sort position

### Test plan

- `test_search_channel.py`:
  - `test_build_query_basic`: Solo keyword → query string
  - `test_build_query_with_filters`: Keyword + language + topic + pushed → query con qualifiers
  - `test_build_query_excludes_archived`: Verifica `archived:false` nella query
  - `test_search_returns_channel_result`: Mock search response → ChannelResult con RepoCandidate
  - `test_search_maps_to_repo_candidate`: Verifica mapping corretto (full_name, url, stars, etc.)
  - `test_search_respects_max_candidates`: Mock 500 risultati → si ferma a max_candidates
  - `test_search_rate_limit_handling`: Mock rate limit near 0 → backoff
  - `test_search_sort_by_updated`: Default sort è updated, non stars
  - `test_search_incomplete_results_handling`: Mock `incomplete_results=true` → log warning

### Criterio di verifica

```bash
pytest tests/unit/discovery/test_search_channel.py -v   # 9 tests passing
```

---

## 7) Task 2.4 — Code Search Channel

### Obiettivo

Canale di discovery basato su GitHub Code Search API (`GET /search/code`) per trovare repo tramite quality signal pattern nei file (presenza pytest, CI.yml, SECURITY.md, ecc.). Bias più basso rispetto a Search API — trova repo per le loro practices, non popolarità.

### Context7: Pattern verificati

Da `/websites/github_en_rest`:
- Endpoint: `GET /search/code`
- Parametri: `q` (query con qualifiers), `per_page` (max 100), `page`
- Rate limit: **10 requests/min** (molto più restrittivo!)
- Response: `items[]` con `repository.full_name`, `repository.url`, `path`, `name`
- Solo default branch considerato, solo file < 384 KB
- Qualifiers: `language:`, `path:`, `filename:`, `extension:`, `repo:`
- Header opzionale: `Accept: application/vnd.github.text-match+json` per text_matches

### Design

```python
# discovery/code_search_channel.py

# Quality signal patterns per identificare repo con buone practices
QUALITY_SIGNAL_PATTERNS: dict[str, list[str]] = {
    "testing": [
        "filename:conftest.py",
        "filename:pytest.ini",
        "filename:setup.cfg path:test",
        "filename:.mocharc",
    ],
    "ci_cd": [
        "filename:.github/workflows path:.github",
        "filename:Jenkinsfile",
        "filename:.gitlab-ci.yml",
    ],
    "security": [
        "filename:SECURITY.md",
        "filename:security.txt",
    ],
    "documentation": [
        "filename:CONTRIBUTING.md",
        "filename:CHANGELOG.md",
    ],
}

class CodeSearchChannel:
    """GitHub Code Search discovery channel.

    Finds repos by quality signal patterns in their files.
    Lower popularity bias than Search API — finds by practices, not stars.
    """

    def __init__(self, client: GitHubRestClient) -> None: ...

    async def search(
        self,
        query: DiscoveryQuery,
    ) -> ChannelResult: ...

    async def search_quality_signals(
        self,
        language: str | None = None,
        signals: list[str] | None = None,   # Subset of QUALITY_SIGNAL_PATTERNS keys
    ) -> ChannelResult:
        """Search for repos with specific quality signal patterns."""
        ...
```

### Implementazione dettagliata

1. **Quality signal patterns**: Dizionario predefinito di pattern per categorie (testing, ci_cd, security, documentation)
2. **Query costruzione**: Combina keyword + quality signal pattern + filtri
3. **Rate limit critico**: Code search ha solo 10 req/min → throttling rigoroso, sleep tra richieste
4. **Dedup intra-channel**: Code search può trovare stesso repo tramite pattern diversi → dedup per `full_name`
5. **Mapping**: Ogni item → `RepoCandidate` con `source_channel=DiscoveryChannel.CODE_SEARCH`, score basato su numero di pattern matchati

### Test plan

- `test_code_search_channel.py`:
  - `test_quality_signal_patterns_defined`: Verifica pattern predefiniti coprono 4+ categorie
  - `test_search_returns_channel_result`: Mock code search → ChannelResult
  - `test_search_rate_limit_strict`: Verifica throttle tra richieste (10/min)
  - `test_search_dedup_same_repo`: Mock stesso repo da 2 pattern → 1 RepoCandidate
  - `test_search_maps_repository_from_code_result`: Verifica mapping repository.full_name → RepoCandidate
  - `test_search_quality_signals_by_language`: Filtra pattern per linguaggio

### Criterio di verifica

```bash
pytest tests/unit/discovery/test_code_search_channel.py -v   # 6 tests passing
```

---

## 8) Task 2.5 — Dependency Graph Channel

### Obiettivo

Canale che traversa il grafo delle dipendenze/dependents da repo seed affidabili per trovare repo usati da progetti di qualità.

### Context7: Pattern verificati

Da `/websites/github_en_rest`:
- `GET /repos/{owner}/{repo}/dependency-graph/sbom` — SBOM in formato SPDX JSON
- `GET /repos/{owner}/{repo}/dependency-graph/compare/{basehead}` — diff dipendenze tra commit
- Nota: Non esiste un endpoint pubblico diretto per "dependents" via REST API — usare il web scraping o la pagina GitHub `/network/dependents`

### Design

```python
# discovery/dependency_channel.py

class DependencyChannel:
    """Dependency graph traversal discovery channel.

    From seed repos known to be high-quality, discover their
    dependencies (what they use) and dependents (what uses them).
    """

    def __init__(
        self,
        rest_client: GitHubRestClient,
        graphql_client: GitHubGraphQLClient,
    ) -> None: ...

    async def discover_dependencies(
        self,
        seed_urls: list[str],
        max_depth: int = 1,
    ) -> ChannelResult:
        """Traverse dependencies of seed repos.
        Depth 1: direct deps. Depth 2: transitive deps (use sparingly)."""
        ...

    async def discover_dependents(
        self,
        seed_urls: list[str],
        max_results: int = 50,
    ) -> ChannelResult:
        """Find repos that depend on the seed repos.
        Uses GraphQL dependency query or dependents listing."""
        ...
```

### Implementazione dettagliata

1. **Dependencies traversal**: Usa SBOM endpoint per ottenere dipendenze di un repo seed → mappa package names → GitHub repo URLs
2. **Dependents discovery**: Usa GraphQL query per `repository.dependents` o scraping della pagina `/network/dependents`
3. **Seed quality weighting**: Repo trovati tramite seed affidabili ricevono `discovery_score` boost
4. **Depth limiting**: Max depth 1 di default (solo dipendenze dirette), depth 2 solo con flag esplicito
5. **Package→Repo mapping**: Se dipendenza ha `source_repository_url` nel SBOM → mappa direttamente. Altrimenti fallback a registry lookup (Task 2.6)

### Test plan

- `test_dependency_channel.py`:
  - `test_discover_dependencies_from_seed`: Mock SBOM → candidati trovati
  - `test_discover_dependencies_depth_1`: Solo dipendenze dirette
  - `test_discover_dependencies_depth_limit`: Depth > max → si ferma
  - `test_discover_dependents_from_seed`: Mock dependents → candidati
  - `test_seed_quality_scoring`: Repo da seed affidabili hanno score boost
  - `test_package_to_repo_mapping`: SBOM source_repository_url → RepoCandidate

### Criterio di verifica

```bash
pytest tests/unit/discovery/test_dependency_channel.py -v   # 6 tests passing
```

---

## 9) Task 2.6 — Package Registry Channel

### Obiettivo

Canale che query package registry (PyPI, npm) per package → mapping al repository GitHub. Questo canale non dipende da GitHub API e ha rate limits meno restrittivi.

### Design

```python
# discovery/registry_channel.py

class RegistryChannel:
    """Package registry mapping discovery channel.

    Queries PyPI/npm/crates.io for packages matching the query,
    maps to their GitHub repository URLs.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None: ...

    async def search_pypi(
        self,
        query: str,
        *,
        max_results: int = 50,
    ) -> ChannelResult:
        """Search PyPI packages and map to GitHub repos.
        Uses PyPI JSON API (no auth required)."""
        ...

    async def search_npm(
        self,
        query: str,
        *,
        max_results: int = 50,
    ) -> ChannelResult:
        """Search npm packages and map to GitHub repos.
        Uses npm registry API."""
        ...

    async def search(
        self,
        query: DiscoveryQuery,
    ) -> ChannelResult:
        """Search configured registries and aggregate results."""
        ...
```

### Implementazione dettagliata

1. **PyPI JSON API**: `GET https://pypi.org/pypi/{package}/json` → `info.home_page` o `info.project_urls.Source` per GitHub URL
2. **PyPI Simple Search**: `GET https://pypi.org/search/?q={query}` (HTML parsing) o usare `GET https://pypi.org/simple/` per listing
3. **npm Registry API**: `GET https://registry.npmjs.org/-/v1/search?text={query}` → `package.links.repository` per GitHub URL
4. **No auth required**: PyPI e npm API non richiedono autenticazione per search
5. **Rate limits**: Più generosi di GitHub — usare comunque con rispetto
6. **Filtering**: Escludere package senza GitHub URL, package deprecati, package con 0 download
7. **Mapping**: Package metadata → `RepoCandidate` con `source_channel=DiscoveryChannel.REGISTRY`

### Test plan

- `test_registry_channel.py`:
  - `test_search_pypi_maps_to_github`: Mock PyPI response con GitHub URL → RepoCandidate
  - `test_search_pypi_skips_no_github`: Mock PyPI response senza GitHub URL → escluso
  - `test_search_npm_maps_to_github`: Mock npm response → RepoCandidate
  - `test_search_aggregates_registries`: Mock PyPI + npm → risultati combinati
  - `test_rate_limiting_respected`: Verifica throttle tra richieste

### Criterio di verifica

```bash
pytest tests/unit/discovery/test_registry_channel.py -v   # 5 tests passing
```

---

## 10) Task 2.7 — Awesome Lists & Curated Sources Channel

### Obiettivo

Parser per awesome-X lists (GitHub README) e altre fonti curate per estrarre repository URL. Bias basso — human-quality-filtered.

### Design

```python
# discovery/curated_channel.py

class CuratedChannel:
    """Awesome lists and curated sources discovery channel.

    Parses awesome-X README lists and community collections
    to extract GitHub repository URLs.
    """

    def __init__(self, rest_client: GitHubRestClient) -> None: ...

    async def parse_awesome_list(
        self,
        awesome_repo_url: str,
    ) -> ChannelResult:
        """Parse an awesome-X list README and extract repo URLs.
        Fetches the README.md via GitHub API, parses markdown links."""
        ...

    async def parse_multiple(
        self,
        awesome_repo_urls: list[str],
    ) -> ChannelResult:
        """Parse multiple awesome lists and aggregate."""
        ...

    async def search(
        self,
        query: DiscoveryQuery,
    ) -> ChannelResult:
        """Search curated sources relevant to the query."""
        ...

    @staticmethod
    def extract_github_urls(markdown_content: str) -> list[str]:
        """Extract GitHub repository URLs from markdown content.
        Handles: [text](https://github.com/owner/repo),
        bare URLs, and subsection-style lists."""
        ...
```

### Implementazione dettagliata

1. **README fetch**: Usa REST client per `GET /repos/{owner}/{repo}/readme` → base64 decode
2. **Markdown parsing**: Regex per estrarre `https://github.com/{owner}/{repo}` URLs dal markdown
3. **Dedup**: Stesso repo può apparire in multiple awesome lists
4. **Metadata extraction**: Sezione della lista (categoria) → potenziale mapping a `DomainType`
5. **Query matching**: Filtra repo URLs per keyword matching nel testo circostante
6. **Predefined lists**: Hardcoded lista di awesome list popolari per domini comuni (awesome-python, awesome-nodejs, awesome-rust, etc.)

### Test plan

- `test_curated_channel.py`:
  - `test_extract_github_urls_basic`: Markdown con link GitHub → lista URL
  - `test_extract_github_urls_ignores_non_repo`: Link a GitHub ma non repo (es. /issues, /pull) → esclusi
  - `test_extract_github_urls_handles_subsection`: Markdown con sottosezioni → URL estratti
  - `test_parse_awesome_list_fetches_readme`: Mock README API call → ChannelResult
  - `test_parse_awesome_list_maps_to_candidates`: Verifica mapping URL → RepoCandidate
  - `test_parse_multiple_deduplicates`: Stesso repo in 2 liste → 1 RepoCandidate
  - `test_search_filters_by_query`: Mock lista → filtra per keyword

### Criterio di verifica

```bash
pytest tests/unit/discovery/test_curated_channel.py -v   # 7 tests passing
```

---

## 11) Task 2.8 — Seed Expansion

### Obiettivo

Espansione del pool da un set di repo seed tramite co-contributor analysis, org adjacency (stessa org del seed), e co-dependency.

### Design

```python
# discovery/seed_expansion.py

class SeedExpansion:
    """Expand candidate pool from seed repositories.

    Strategies: co-contributor analysis, org adjacency, co-dependency.
    """

    def __init__(
        self,
        rest_client: GitHubRestClient,
        graphql_client: GitHubGraphQLClient,
    ) -> None: ...

    async def expand_by_org(
        self,
        seed_urls: list[str],
        max_per_org: int = 20,
    ) -> ChannelResult:
        """Find repos from the same org as seed repos."""
        ...

    async def expand_by_contributors(
        self,
        seed_urls: list[str],
        max_contributors: int = 10,
        max_repos_per_contributor: int = 5,
    ) -> ChannelResult:
        """Find repos from contributors to seed repos."""
        ...

    async def expand(
        self,
        seed_urls: list[str],
        strategies: list[str] | None = None,
        max_depth: int = 1,
    ) -> ChannelResult:
        """Run expansion strategies on seed repos."""
        ...
```

### Implementazione dettagliata

1. **Org adjacency**: Da `seed.full_name` → extract `owner` → `GET /orgs/{owner}/repos` (se org) o `GET /users/{owner}/repos` (se user)
2. **Co-contributor**: Da seed repo → `GET /repos/{owner}/{repo}/contributors` → per ogni contributor → `GET /users/{username}/repos` → filtra per linguaggio/topic simili
3. **GraphQL aggregation**: Query singola per contributor + loro repo (riduce N+1)
4. **Depth limiting**: Depth 1 = solo espansione diretta. Depth > 1 usato con cautela (rischio explosion)
5. **Dedup**: Escludere seed originali dai risultati
6. **Score**: Repo trovati tramite contributor attivi di seed affidabili ricevono score boost

### Test plan

- `test_seed_expansion.py`:
  - `test_expand_by_org_finds_same_org_repos`: Mock org repos → ChannelResult
  - `test_expand_by_org_ignores_seed_repos`: Seed URLs escluse dai risultati
  - `test_expand_by_contributors_finds_repos`: Mock contributors + user repos → ChannelResult
  - `test_expand_by_contributors_limits_per_user`: Rispetta max_repos_per_contributor
  - `test_expand_multiple_strategies`: Combina org + contributors → dedup
  - `test_expand_depth_limiting`: Depth > max → si ferma

### Criterio di verifica

```bash
pytest tests/unit/discovery/test_seed_expansion.py -v   # 6 tests passing
```

---

## 12) Task 2.9 — Discovery Orchestrator

### Obiettivo

Orchestratore centrale che coordina i canali di discovery, gestisce concorrenza, deduplica per `full_name`, calcola `discovery_score`, e produce il pool finale.

### Design

```python
# discovery/orchestrator.py

class DiscoveryOrchestrator:
    """Central orchestrator for the discovery pipeline.

    Coordinates channels, deduplicates, scores, and produces
    the final candidate pool.
    """

    def __init__(
        self,
        settings: Settings,
        pool_manager: PoolManager,
    ) -> None: ...

    async def discover(
        self,
        query: DiscoveryQuery,
    ) -> DiscoveryResult:
        """Run discovery across configured channels.

        1. Initialize channels based on query config
        2. Run channels concurrently (asyncio.gather with Semaphore)
        3. Merge and deduplicate candidates by full_name
        4. Calculate discovery_score for each candidate
        5. Persist pool via PoolManager
        6. Return DiscoveryResult with pool_id
        """
        ...

    def _calculate_discovery_score(
        self,
        candidate: RepoCandidate,
        channels_found_by: list[DiscoveryChannel],
    ) -> float:
        """Calculate preliminary discovery score based on:
        - Breadth: number of channels that found the repo (0.0-1.0)
        - Channel quality: some channels have higher confidence
        - Source-specific signals (search rank, quality signals, etc.)
        """
        ...
```

### Implementazione dettagliata

1. **Channel registry**: Dizionario `{DiscoveryChannel: Channel}` inizializzato con tutti i canali attivi
2. **Channel selection**: Da `query.channels` (se None → `settings.discovery.default_channels`)
3. **Concurrency**: `asyncio.gather` con `asyncio.Semaphore(max_concurrent)` per limitare chiamate parallele
4. **Error isolation**: Ogni canale in try/except — fallimento di un canale non blocca gli altri. Log + ChannelResult vuoto
5. **Deduplication**: Dict `{full_name: (RepoCandidate, set[DiscoveryChannel])}` → merge channel info
6. **Discovery score**: Formula:
   - Base: `len(channels_found_by) / total_channels` (breadth signal, 0.0-1.0)
   - Boost: `+0.1` per canale curato (awesome_list, dependency), `+0.05` per code_search quality signal
   - Normalize a 0.0-1.0
7. **Pool persistence**: PoolManager salva il pool con tutti i candidati
8. **Logging**: Per canale: candidates found, rate limit status, elapsed. Totale: dedup stats

### Test plan

- `test_orchestrator.py`:
  - `test_discover_runs_multiple_channels`: Mock 3 canali → risultati aggregati
  - `test_discover_deduplicates_by_full_name`: Stesso repo da 2 canali → 1 candidato con metadata merge
  - `test_discover_calculates_discovery_score`: Repo trovato da 3 canali → score > repo trovato da 1
  - `test_discover_respects_max_candidates`: Mock 1000 candidati → si ferma a max_candidates
  - `test_discover_channel_failure_graceful`: Mock 1 canale fallisce → altri canali continuano
  - `test_discover_empty_results`: Mock tutti canali vuoti → DiscoveryResult con pool vuoto
  - `test_discover_logs_channel_stats`: Verifica logging per canale
  - `test_calculate_discovery_score_breadth`: Score cresce con numero di canali
  - `test_calculate_discovery_score_channel_quality`: Canale curato dà boost vs search

### Criterio di verifica

```bash
pytest tests/unit/discovery/test_orchestrator.py -v   # 9 tests passing
```

---

## 13) Task 2.10 — Candidate Pool Manager

### Obiettivo

Persistenza del pool candidati con supporto CRUD, tracking stato per candidato, e query per status. Backend SQLite per sviluppo locale, con interfaccia astratta per futuro backend Redis.

### Design

```python
# discovery/pool.py

class PoolManager:
    """Manages candidate pool persistence.

    SQLite-backed for local development, abstract interface
    for future Redis backend.
    """

    def __init__(self, db_path: str | Path = "github_discovery.db") -> None: ...

    async def create_pool(
        self,
        query: DiscoveryQuery,
        candidates: list[RepoCandidate],
    ) -> CandidatePool: ...

    async def get_pool(self, pool_id: str) -> CandidatePool | None: ...

    async def add_candidates(
        self,
        pool_id: str,
        candidates: list[RepoCandidate],
    ) -> int:
        """Add candidates to existing pool. Returns count of new (non-duplicate) adds."""
        ...

    async def update_candidate_status(
        self,
        pool_id: str,
        full_name: str,
        status: CandidateStatus,
    ) -> bool: ...

    async def get_candidates(
        self,
        pool_id: str,
        *,
        status: CandidateStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RepoCandidate]: ...

    async def get_pool_stats(self, pool_id: str) -> dict[str, int]:
        """Returns {total, discovered, screened, assessed, ranked, excluded}."""
        ...

    async def delete_pool(self, pool_id: str) -> bool: ...

    async def close(self) -> None: ...
```

### Implementazione dettagliata

1. **SQLite schema**:
   - `pools` table: pool_id, query_json, created_at, updated_at, total_candidates
   - `candidates` table: pool_id, full_name, data_json, status, discovery_score, source_channels, created_at
   - `UNIQUE(pool_id, full_name)` per dedup
2. **JSON serialization**: `RepoCandidate.model_dump_json()` per storage, `model_validate_json()` per deserialization
3. **Async SQLite**: `aiosqlite` per operazioni non-bloccanti — aggiungere dipendenza
4. **Dedup on insert**: `INSERT OR IGNORE` per gestire duplicati cross-canale
5. **Status tracking**: `CandidateStatus` enum per pipeline state (DISCOVERED iniziale)
6. **Pool stats**: Query aggregata per conteggi per status

### Dipendenze pyproject.toml (nuova)

```toml
dependencies = [
    # ... existing ...
    "aiosqlite>=0.20",    # Async SQLite for pool persistence
]
```

### Test plan

- `test_pool.py`:
  - `test_create_pool_with_candidates`: Crea pool con 5 candidati → retrieve per pool_id
  - `test_get_pool_returns_correct_data`: Pool recuperato ha query e candidati corretti
  - `test_get_pool_nonexistent_returns_none`: pool_id inesistente → None
  - `test_add_candidates_deduplicates`: Aggiungi candidato duplicato → count = 0
  - `test_add_candidates_new`: Aggiungi candidato nuovo → count = 1
  - `test_update_candidate_status`: Update status → get_candidates filtrato per status
  - `test_get_candidates_with_status_filter`: Solo candidati con status DISCOVERED
  - `test_get_candidates_pagination`: limit + offset funzionanti
  - `test_get_pool_stats`: Stats corrette per pool con status misti
  - `test_delete_pool`: Pool eliminato → get_pool restituisce None
  - `test_close_cleans_up`: Close non solleva errori

### Criterio di verifica

```bash
pytest tests/unit/discovery/test_pool.py -v   # 11 tests passing
```

---

## 14) Sequenza di implementazione

La sequenza tiene conto delle dipendenze reali tra task e della complessità decrescente:

```
Fase A — Fondamentali (Settimana 1)
  Task 2.1  GitHub REST API Client      [critico, blocca tutto]
  Task 2.10 Candidate Pool Manager       [critico, usato da orchestrator]
  Task 2.2  GitHub GraphQL Client        [dipende da 2.1 per auth/rate limit pattern]

Fase B — Canali primari (Settimana 1-2)
  Task 2.3  Search API Channel           [dipende da 2.1]
  Task 2.7  Awesome Lists Channel        [dipende da 2.1]
  Task 2.4  Code Search Channel          [dipende da 2.1]

Fase C — Canali secondari + Orchestrator (Settimana 2-3)
  Task 2.6  Package Registry Channel     [indipendente, usa httpx diretto]
  Task 2.5  Dependency Graph Channel     [dipende da 2.1 + 2.2]
  Task 2.8  Seed Expansion               [dipende da 2.1 + 2.2]

Fase D — Integrazione (Settimana 2-3)
  Task 2.9  Discovery Orchestrator       [dipende da 2.3-2.8, 2.10]
```

### Ordine consigliato per l'implementazione

1. **2.1** — GitHub REST Client (fondazione)
2. **2.10** — Pool Manager (persistenza)
3. **2.2** — GraphQL Client (pattern simile a 2.1)
4. **2.3** — Search Channel (canale primario, più importante)
5. **2.7** — Curated Channel (semplice, high value)
6. **2.4** — Code Search Channel (rate limit critico)
7. **2.6** — Registry Channel (indipendente)
8. **2.5** — Dependency Channel (complesso)
9. **2.8** — Seed Expansion (complesso, usa GraphQL)
10. **2.9** — Orchestrator (integra tutto)

Ogni task deve essere completato con test passing e mypy strict prima di procedere al successivo.

---

## 15) Test plan

### Test unitari (per modulo)

| Modulo | File test | Tests stimati | Dipendenza mock |
|--------|-----------|---------------|-----------------|
| `github_client.py` | `test_github_client.py` | 12 | pytest-httpx |
| `graphql_client.py` | `test_graphql_client.py` | 8 | pytest-httpx |
| `search_channel.py` | `test_search_channel.py` | 9 | pytest-httpx |
| `code_search_channel.py` | `test_code_search_channel.py` | 6 | pytest-httpx |
| `dependency_channel.py` | `test_dependency_channel.py` | 6 | pytest-httpx |
| `registry_channel.py` | `test_registry_channel.py` | 5 | pytest-httpx |
| `curated_channel.py` | `test_curated_channel.py` | 7 | pytest-httpx |
| `seed_expansion.py` | `test_seed_expansion.py` | 6 | pytest-httpx |
| `orchestrator.py` | `test_orchestrator.py` | 9 | pytest-httpx + mock channels |
| `pool.py` | `test_pool.py` | 11 | aiosqlite (in-memory) |
| **Totale** | | **~79** | |

### Fixtures condivise (conftest.py)

```python
# tests/unit/discovery/conftest.py

@pytest.fixture
def mock_github_settings() -> GitHubSettings:
    """Settings with test token and API URL."""

@pytest.fixture
def sample_repo_json() -> dict[str, object]:
    """Sample GitHub API /repos/{owner}/{repo} JSON response."""

@pytest.fixture
def sample_search_response() -> dict[str, object]:
    """Sample GitHub /search/repositories response with 3 items."""

@pytest.fixture
def sample_code_search_response() -> dict[str, object]:
    """Sample GitHub /search/code response."""

@pytest.fixture
def sample_graphql_repo_response() -> dict[str, object]:
    """Sample GraphQL repository query response."""

@pytest.fixture
def sample_pypi_response() -> dict[str, object]:
    """Sample PyPI package JSON API response."""

@pytest.fixture
def sample_npm_response() -> dict[str, object]:
    """Sample npm registry search response."""

@pytest.fixture
def awesome_readme_content() -> str:
    """Sample awesome list README markdown."""

@pytest.fixture
def pool_manager(tmp_path: Path) -> PoolManager:
    """PoolManager with temporary SQLite database."""
```

### Test di integrazione

```python
# tests/integration/discovery/test_discovery_e2e.py

@pytest.mark.integration
@pytest.mark.slow
class TestDiscoveryE2E:
    """End-to-end discovery tests against real GitHub API.

    These tests require GHDISC_GITHUB_TOKEN set and count against rate limits.
    Run with: pytest -m integration tests/integration/discovery/
    """

    async def test_search_finds_real_repos(self): ...
    async def test_code_search_finds_quality_signals(self): ...
    async def test_awesome_list_parses_real(self): ...
    async def test_discovery_pipeline_produces_pool(self): ...
```

### Target coverage

- **github_client.py**: >90% (core infrastructure)
- **search_channel.py**: >85% (primary channel)
- **orchestrator.py**: >80% (integration logic)
- **pool.py**: >85% (data persistence)
- **Altri moduli**: >75%

---

## 16) Criteri di accettazione

### Checkpoint Phase 2 (Roadmap)

> Discovery pipeline produce pool di candidati da almeno 3 canali, deduplica funzionante, score preliminare assegnato.

### Criteri verificabili

1. **`make ci` verde**: ruff check + mypy --strict + pytest tutti passing
2. **Test count**: Almeno 79 nuovi test unitari passing
3. **3+ canali operativi**: Search API + Awesome Lists + almeno un altro canale producono candidati
4. **Deduplica**: Stesso repo trovato da canali diversi → singolo RepoCandidate con metadata merge
5. **discovery_score**: Ogni candidato ha score preliminare 0.0-1.0
6. **Rate limiting**: Client rispetta rate limits (test verificano backoff/warning)
7. **Pool persistence**: PoolManager crea/recupera/aggiorna pool con SQLite
8. **Pipeline end-to-end**: `DiscoveryOrchestrator.discover(query)` → `DiscoveryResult` con pool_id
9. **mypy --strict**: 0 errors in `src/github_discovery/discovery/`
10. **Integration test**: Almeno 1 test E2E con API reale (marked `@pytest.mark.integration`)

### Comandi di verifica

```bash
make ci                                           # Full CI: lint + typecheck + test
pytest tests/unit/discovery/ -v                   # All discovery unit tests
pytest tests/unit/discovery/ --cov=github_discovery.discovery --cov-report=term-missing
pytest -m integration tests/integration/discovery/ -v  # E2E tests (needs token)
mypy src/github_discovery/discovery/ --strict     # Type check discovery module
```

---

## 17) Rischi e mitigazioni

| Rischio | Impatto | Probabilità | Mitigazione |
|---------|---------|-------------|-------------|
| **Rate limit GitHub API su discovery bulk** | Alto — discovery bloccata | Media | Throttling rigoroso (Semaphore), caching (Feature Store), GraphQL per ridurre chiamate, conditional requests, sleep when near limit |
| **Code Search rate limit molto basso (10/min)** | Medio — canale lento | Alta | Code search usato con parsimonia, sleep tra richieste, batch ridotto, combinato con altri canali |
| **Bias residuo nei canali (Search API popolarità-influenced)** | Medio — pool iniziale distorto | Media | Combinare 3+ canali con diverso bias, awesome lists come controbilancio, sort by updated non stars |
| **Parsing awesome lists fragile (formato non standard)** | Basso — canale fallisce | Media | Regex robuste, fallback, graceful error handling, lista hardcoded di awesome lists testate |
| **Dependents API non pubblica diretta** | Medio — dependency channel incompleto | Alta | Fallback a GraphQL query o web scraping, documentare limitazione, implementare solo ciò che è disponibile via API |
| **aiosqlite non in dependencies** | Basso — pool non funzionante | Bassa | Aggiungere `aiosqlite>=0.20` a pyproject.toml dependencies |
| **Schema SQLite complessità crescente** | Basso — refactoring necessario | Bassa | Schema minimale iniziale (2 tabelle), interfaccia astratta per futuro backend Redis |

---

## 18) Verifica Context7 completata

Le seguenti librerie e pattern sono stati verificati tramite Context7 prima della stesura di questo piano:

| Libreria | ID Context7 | Pattern verificati |
|----------|-------------|-------------------|
| **httpx** | `/encode/httpx` | AsyncClient, AsyncHTTPTransport(retries), httpx.Auth subclass, event hooks async, context manager |
| **pytest-httpx** | `/colin-b/pytest_httpx` | HTTPXMock fixture, add_response, custom headers (rate limit), is_reusable, get_requests |
| **GitHub REST API** | `/websites/github_en_rest` | /search/repositories (q, sort, order, per_page, page, Link header), /search/code (10 req/min!), /rate_limit, conditional requests (ETag/If-None-Match → 304), dependency-graph/sbom |
| **GitHub GraphQL** | `/websites/github_en_graphql` | Cursor-based pagination (first/after, pageInfo.hasNextPage/endCursor), rateLimit { cost remaining resetAt } |

### Pattern chiave verificati

1. **httpx Auth subclass**: `class BearerAuth(httpx.Auth)` con `auth_flow` method che setta `Authorization: Bearer {token}`
2. **httpx retry transport**: `httpx.AsyncHTTPTransport(retries=3)` per retry automatico su connection errors
3. **httpx event hooks**: Async hooks per response → tracking `x-ratelimit-*` headers
4. **GitHub REST pagination**: Parse `Link` header per `rel="next"` URL, iterare fino a `max_pages`
5. **GitHub Search rate limits**: Core 5000/hr, Search 30/min, Code Search 10/min (critical!)
6. **GitHub conditional requests**: `If-None-Match: "{etag}"` → 304 non conta contro rate limit
7. **GitHub GraphQL pagination**: `first: 100, after: "{endCursor}"` + `pageInfo { hasNextPage endCursor }`
8. **pytest-httpx mocking**: `httpx_mock.add_response(json=..., headers={"X-RateLimit-Remaining": "99"})` per mock responses con rate limit headers
