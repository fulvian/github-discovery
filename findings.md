# GitHub Discovery — Findings

## Progetti Simili Esistenti

### Core benchmark trovato
- **github_repo_classifier**: https://github.com/chriscarrollsmith/github_repo_classifier
  - Discovery + LLM classification
  - Usa `repomix` + `llm` + `gh`
  - Introduce `Value Score = quality_score / log10(star_count + 10)`

### OSS health & sustainability
- **CHAOSS**: https://chaoss.community/software/
- **GrimoireLab**: https://chaoss.github.io/grimoirelab/
- **Augur**: https://github.com/chaoss/augur

### Security quality signals
- **OpenSSF Scorecard**: https://github.com/ossf/scorecard
- **Scorecard portal**: https://scorecard.dev/

### MCP / AI analysis tools
- **GitHub official MCP server**: https://github.com/github/github-mcp-server
- **github-intelligence-mcp**: https://github.com/meltemeroglu/github-intelligence-mcp
- **GitHub-Analyzer-MCP-Server**: https://github.com/iamthite/GitHub-Analyzer-MCP-Server
- **codeglance-mcp**: https://github.com/lucidopus/codeglance-mcp
- **mcp-code-review**: https://github.com/mauriziomocci/mcp-code-review

### Complementary tools
- **Repomix**: https://github.com/yamadashy/repomix

## GitHub API — Capabilities per Analisi Qualitativa
- REST e GraphQL forniscono metadata repo, commits, PR, issue, release, contributor activity.
- GraphQL consente query aggregate efficienti ma con cost model a punti.
- Code search e file presence checks consentono screening strutturale (test, CI, hygiene files).
- Bulk analysis richiede paginazione rigorosa + throttling + caching.

## Metodi di Valutazione Tecnica
- Pipeline in 3 livelli:
  1) Candidate discovery
  2) Lightweight screening (metadata/structure)
  3) Deep assessment (LLM + static/security signals)
- Multi-dimensional scoring (no single metric).
- Ranking intra-dominio per evitare confronti unfair.
- Explainability obbligatoria per ogni score.

## Strumenti e MCP
- MCP utile come layer di integrazione per agent orchestration.
- GitHub official MCP server e base solida per operations standard.
- MCP custom puo esporre endpoint di scoring e retrieval ranked repos.

## CLI Agentic Workflow (fonti ufficiali)
- OpenCode CLI ufficiale: `opencode run`, `opencode serve`, `opencode mcp add/list/auth`, permission model granulare `allow/ask/deny`.
- Kilo CLI ufficiale: `kilo run --auto`, orchestrazione multi-modalita, slash commands operative, policy permission e config in `~/.config/kilo/`.
- Claude Code best practices: gestione rigorosa context window, ciclo explore-plan-implement-verify, uso di subagent/sessioni parallele e automazione non-interattiva.

## Insights Chiave
1. Esistono componenti utili, ma non una soluzione end-to-end completa orientata a technical discovery anti-popularity bias.
2. `github_repo_classifier` e il riferimento piu vicino per bootstrap concettuale.
3. OpenSSF Scorecard e un modulo forte da integrare come segnale security/hygiene.
4. CHAOSS e prezioso per metriche community health, ma non sostituisce code quality assessment.
5. Il vantaggio strategico di GitHub Discovery e unire discovery multicanale + scoring tecnico explainable + MCP-native access.
