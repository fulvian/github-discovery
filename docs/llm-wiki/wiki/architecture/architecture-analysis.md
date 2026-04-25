# GitHub Discovery — Analisi Completa dell'Architettura

**Title**: GitHub Discovery — Analisi Completa dell'Architettura
**Topic**: Architecture
**Sources**: [architecture_analysis.md](../../../../docs/analysis/architecture_analysis.md)
**Raw**: 
  - [Foundation Blueprint](../../../../docs/foundation/github-discovery_foundation_blueprint.md) — specifica completa del progetto
  - [Foundation Roadmap](../../../../docs/roadmaps/github-discovery_foundation_roadmap.md) — milestone e fasi
**Updated**: 2026-04-25
**Confidence**: high

## Sintesi

Questo articolo sintetizza l'analisi architetturale completa di GitHub Discovery (v0.1.0-alpha), coprendo la pipeline a 4 gate, il sistema di scoring star-neutral, l'architettura MCP-native, l'integrazione con agenti di coding, e la struttura del codice (107 file Python, 1326 test).

## Pipeline a 4 Gate

La pipeline è il nucleo strutturale. Quattro livelli progressivamente più costosi:

1. **Gate 0 — Discovery**: 6 canali paralleli (Search, Code Search, Dependency, Registry, Awesome Lists, Seed Expansion) raccolgono un pool ampio. Multi-canale per mitigare il bias di popolarità di ogni singola fonte.

2. **Gate 1 — Metadata Screening** (zero LLM): 7 sub-score calcolati da API GitHub (Hygiene, Maintenance, Release Discipline, Practices, Test Footprint, CI/CD, Dependency Quality). Output: `MetadataScreenResult` con `gate1_pass`.

3. **Gate 2 — Static/Security Screening** (zero/basso costo): 4 tool esterni su clone superficiale (OpenSSF Scorecard, OSV API, gitleaks, scc). Degradazione graceful: tool non disponibile → fallback score 0.3. Output: `StaticScreenResult` con `gate2_pass`.

4. **Gate 3 — LLM Deep Assessment** (costo alto): Valutazione LLM su 8 dimensioni tramite NanoGPT + instructor. Solo per candidati con `gate1_pass AND gate2_pass`. Budget-controlled con caching per commit SHA.

**Hard rule**: Nessun candidato raggiunge Gate 3 senza superare Gate 1 + Gate 2.

## Sistema Star-Neutral (Riprogettato 2026-04-25)

Evoluzione da anti-star bias (`quality_score / log10(stars + 10)`) a star-neutral (`value_score = quality_score`):
- Le stelle sono **metadati di corroborazione** (5 livelli: new → widely_adopted), mai un segnale di ranking
- Ranking: `(-quality_score, -confidence, -seeded_hash, full_name)` — stelle escluse
- Hidden gem: label informativo (quality ≥ 0.5, stars < 100, top 25% dominio)
- 11 profili di pesi per dominio (DomainProfile)
- Validato E2E: 2 repo con 0 stelle rankati sopra repo con 12,281 stelle

## Architettura MCP-Native

- **16 tool MCP** in 5 categorie (discovery, screening, assessment, ranking, session)
- **4 risorse** con URI template
- **5 prompt skills** (workflow predefiniti per agenti)
- **Session-aware**: `session_id` per workflow cross-sessione (progressive deepening)
- **Context-efficient**: output summary-first (< 2000 token default)
- **Composable**: delegazione a GitHub MCP Server ufficiale per operazioni standard

## Integrazione Agenti di Coding

Tre piattaforme supportate con configurazioni documentate:
- **Kilocode CLI / Kilo Code**: `kilo.json` con `{env:GITHUB_TOKEN}` syntax
- **Claude Code**: `.mcp.json` con `${GITHUB_PAT}` expansion
- **OpenCode**: `opencode.json` con merge configurazioni multiple

Tutti usano namespace `{server}_{tool}` e supportano read-only mode per GitHub MCP.

## Struttura Codice

107 file Python in 16 moduli (discovery, screening, assessment, scoring, mcp, api, cli, workers, models, feasibility). Stack: Python 3.12+, Pydantic v2, FastAPI, httpx, openai+instructor, MCP Python SDK, typer+rich, SQLite/aiosqlite.

## Stato

Phases 0-9 complete. 1326 test passanti, `make ci` green. Phase 10 (Alpha: Docker, Marketplace, Docs, PyPI) pending.

## See Also

- [Tiered Scoring Pipeline](tiered-pipeline.md) — dettaglio dei 4 gate
- [Star-Neutral Quality Scoring](anti-star-bias.md) — filosofia star-neutral
- [MCP-Native Agentic Integration Architecture](mcp-native-design.md) — design MCP-first
- [MCP Tool Specifications](../apis/mcp-tools.md) — specifiche complete dei 16 tool
- [Agent Workflow Patterns](../patterns/agent-workflows.md) — workflow per agenti
- [Kilo Marketplace Deployment Model](../patterns/marketplace-deployment.md) — deployment marketplace
