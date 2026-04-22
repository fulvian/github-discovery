# GitHub Discovery — Task Plan

## Goal
Creare il Foundation Blueprint per "GitHub Discovery": uno strumento per scoprire repository GitHub di alta qualita tecnica indipendentemente dalla popolarita (stars, discussioni online).

## Problem Statement
I motori di ricerca e gli AI agent (Perplexity, Claude, ChatGPT, Gemini) si basano principalmente su:
- Stelle GitHub (popolarita)
- Frequenza di discussione online (Reddit, Stack Overflow, blog)

Questo crea un bias sistematico che esclude progetti tecnicamente eccellenti ma con scarsa visibilita.

## Phases

### Phase 1: Ricerca Esplorativa [complete]
- [x] Ricerca progetti simili gia esistenti
- [x] Analisi GitHub API per valutazione qualitativa
- [x] Metodi alternativi di valutazione tecnica
- [x] GitHub MCP e strumenti di scanning

### Phase 2: Analisi e Sintesi [complete]
- [x] Confronto approcci trovati
- [x] Identificazione gap e opportunita
- [x] Definizione metriche di qualita tecnica

### Phase 3: Foundation Blueprint [complete]
- [x] Stesura del documento fondativo
- [x] Definizione aree di approfondimento
- [x] Domande aperte per iterazioni successive

## Deliverables
- `docs/foundation/github-discovery_foundation_blueprint.md`
- `findings.md`
- `progress.md`

## Constraints
- Fase esplorativa, non implementativa
- Output: documento blueprint + domande aperte
- Approccio iterativo, non one-shot

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| Tavily research API usage limit | 1 | fallback su Brave/GitHub API/perplexity |
| Firecrawl insufficient credits | 1 | fallback su Brave/GitHub API |
| Brave rate-limited su burst requests | 1 | richieste sequenziali e fonti alternative |
| Perplexity transient network error | 1 | retry con query ridotta |
