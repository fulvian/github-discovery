# Agenti di Coding — Integrazione MCP (Claude Code, Kilocode, OpenCode)

**Title**: Agenti di Coding — Integrazione MCP
**Topic**: APIs
**Sources**: [architecture_analysis.md §5](../../../../docs/analysis/architecture_analysis.md)
**Raw**:
  - Kilocode MCP Docs: https://kilo.ai/docs/automate/mcp/using-in-cli
  - Kilocode Code MCP Docs: https://kilo.ai/docs/features/mcp/using-mcp-in-kilo-code
  - Claude Code MCP Docs: https://docs.anthropic.com/en/docs/claude-code/mcp
  - OpenCode MCP Docs: https://opencode.ai/docs/mcp-servers/
  - Kilo Marketplace: https://github.com/Kilo-Org/kilo-marketplace
  - GitHub MCP Server: https://github.com/github/github-mcp-server
  - MCP Protocol Spec: https://modelcontextprotocol.io
  - [Foundation Blueprint §21](../../../../docs/foundation/github-discovery_foundation_blueprint.md#21-agentic-integration-architecture)
**Updated**: 2026-04-26
**Confidence**: high

## Panoramica

GitHub Discovery è progettato per integrarsi nativamente con tre piattaforme di AI coding agent:
Kilocode CLI / Kilo Code, Claude Code (Anthropic), e OpenCode. L'integrazione avviene tramite
composizione MCP: GitHub Discovery aggiunge scoring/ranking al GitHub MCP Server ufficiale.

### Stato Configurazione nel Repository (v0.1.0-alpha)

| File | Piattaforma | Stato | Contenuto |
|------|-------------|-------|-----------|
| `.mcp.json` | Claude Code | ✅ Presente | Composizione completa: github (http) + github-discovery (stdio) |
| `.kilo/mcp.json` | Kilocode CLI / Kilo Code | ✅ Presente | Composizione completa: github (remote) + github-discovery (local) |
| `.kilo/mcp.json.template` | Kilocode (template) | ✅ Presente | Template con composizione completa |
| `CLAUDE.md` | Claude Code (guide) | ✅ Presente | Build/test/lint comandi e regole codice |

## Architettura di Composizione

```
AI Coding Agent (Claude Code / Kilocode / OpenCode)
├── GitHub MCP Server (ufficiale) → repos, issues, PRs, search, context
└── GitHub Discovery MCP → discover_repos, screen_candidates, deep_assess, rank_repos
```

Discovery delega al server ufficiale tutte le operazioni GitHub standard — non duplica funzionalità.

## Kilocode CLI / Kilo Code

**Docs**: https://kilo.ai/docs/automate/mcp/using-in-cli (Brave-verified)

**Config**: `~/.config/kilo/kilo.json` o `~/.config/kilo/kilo.jsonc` (globale), `.kilo/kilo.json` (progetto)

### Formato `.kilo/mcp.json` (Brave-verified)

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

**Nota importante**: `"command"` è un array (non stringa) e le variabili d'ambiente usano `"environment"` (non `"env"`).
La sintassi di espansione è `"{env:VAR}"` (non `${VAR}` come in Claude Code).

**Caratteristiche** (Brave-verified):
- Namespace tool: `{server}_{tool}` (es. `github-discovery_discover_repos`)
- Permessi: `allow`/`ask`/`deny` con glob patterns
- Env var syntax: `{env:VARIABLE_NAME}`
- Marketplace: Kilo-Org/kilo-marketplace, formato `MCP.yaml`
- `/mcps` slash command per toggle server
- Config globale: `~/.config/kilo/kilo.jsonc` (JSONC — ammette commenti)
- SSE transport deprecato, usare solo stdio o remote

**File configurazione nel repository**:
- `.kilo/mcp.json` — config attiva con composizione completa (github + github-discovery)
- `.kilo/mcp.json.template` — template per nuovi progetti

## Claude Code (Anthropic)

**Docs**: https://docs.anthropic.com/en/docs/claude-code/mcp (Context7-verified: `/websites/code_claude`, `/ericbuess/claude-code-docs`)

**Config**: `.mcp.json` (progetto, version-controlled) o `~/.claude.json` (user)

### Formato `.mcp.json` (Context7-verificato)

Schema TypeScript di riferimento (`McpStdioServerConfig`):
```typescript
type McpStdioServerConfig = {
  type?: "stdio";
  command: string;
  args?: string[];
  env?: Record<string, string>;
};
```

Il file `.mcp.json` alla radice del progetto contiene:
```json
{
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": {
        "Authorization": "Bearer ${GITHUB_TOKEN}",
        "X-MCP-Toolsets": "repos,issues,pull_requests,context",
        "X-MCP-Readonly": "true"
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

**Nota importante**: `"command"` è una stringa (non array) e le variabili d'ambiente usano `"env"` (non `"environment"`).
La sintassi di espansione è `"${VAR}"` (dollar-brace, non `{env:VAR}` come in Kilocode).

**Comandi alternativi (CLI)**:
```bash
# Aggiungere server HTTP (remoto)
claude mcp add --transport http github https://api.githubcopilot.com/mcp/ \
  --header "Authorization: Bearer $GITHUB_TOKEN"

# Aggiungere server stdio (locale)
claude mcp add --transport stdio github-discovery \
  -e GHDISC_GITHUB_TOKEN=... -- python -m github_discovery.mcp serve

# Aggiungere da JSON
claude mcp add-json github-discovery '{"command":"python","args":["-m","github_discovery.mcp","serve"],"env":{"GHDISC_GITHUB_TOKEN":"..."}}'
```

**Caratteristiche** (Context7-verified):
- Env var expansion: `${VAR}`, `${VAR:-default}` (nella config file)
- `managed-mcp.json` per controllo enterprise (amministratore, `/Library/` o system-wide)
- Reconnection automatico con exponential backoff
- MCP prompts disponibili come `/mcp__github-discovery__discover_underrated`
- Tool search: caricamento on-demand schemi
- Dynamic tool updates: `list_changed` notifications
- TypeScript `McpStdioServerConfig`: `{type?, command, args?, env?}` — `type` opzionale (default: stdio)
- `.mcp.json` è auto-caricato se presente nella root del progetto
- `claude mcp add-json <name> '<json>'` per aggiunta da CLI con JSON inline

## OpenCode

**Docs**: https://opencode.ai/docs/mcp-servers/

**Config**: `opencode.json` (progetto) — merge di configurazioni multiple per precedenza

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

**Caratteristiche**:
- Config merge: file multipli mergiati (non sostituiti)
- OAuth automatic detection con Dynamic Client Registration (RFC 7591)
- `opencode mcp auth <name>` per flusso autenticazione
- Tool namespacing: `{servername}_{tool}`

## Kilo Marketplace — Deployment

GitHub Discovery sarà pubblicato su [Kilo Marketplace](https://github.com/Kilo-Org/kilo-marketplace) con 3 opzioni di installazione:

| Metodo | Comando | Prerequisiti |
|--------|---------|-------------|
| **UVX** (raccomandato) | `uvx github-discovery mcp serve --transport stdio` | Python 3.12+, uv |
| **Docker** | `docker run -i --rm ghcr.io/fulviocoschi/github-discovery:latest` | Docker |
| **Remote** | `https://github-discovery.example.com/mcp` | Server deployment |

## Tabella Comparativa Piattaforme (Context7 + Brave verified)

| Feature | Kilo CLI | Claude Code | OpenCode |
|---------|----------|-------------|----------|
| Config file | `.kilo/mcp.json` | `.mcp.json` | `opencode.json` |
| Top-level key | `"mcp"` | `"mcpServers"` | `"mcp"` |
| Global path | `~/.config/kilo/kilo.jsonc` | `~/.claude.json` | `~/.config/opencode/` |
| Command format | Array `["cmd","arg"]` | String `"cmd"` + `"args": ["arg"]` | Array `["cmd","arg"]` |
| Env key name | `"environment"` | `"env"` | `"environment"` |
| Env var syntax | `{env:VAR}` | `${VAR}` | `{env:VAR}` |
| Remote type | `"remote"` | `"http"` | `"remote"` |
| OAuth | `kilo mcp auth` | `/mcp` browser flow | Auto-detected |
| Tool namespace | `{server}_{tool}` | `mcp__{server}__{tool}` | `{server}_{tool}` |
| Enterprise/managed | Not documented | `managed-mcp.json` | MDM + `/Library/` |
| SSE support | Deprecated | Deprecated | N/A |
| JSONC support | ✅ `.jsonc` | ❌ | N/A |

### Differenze chiave tra formati

Queste differenze sono la principale fonte di errori nella configurazione MCP multi-piattaforma:

1. **Top-level key**: Kilocode/OpenCode usano `"mcp"`, Claude Code usa `"mcpServers"`
2. **Command**: Kilocode/OpenCode usano array `["cmd","arg"]`, Claude Code usa string `"cmd"` + `"args": [...]`
3. **Env key**: Kilocode/OpenCode usano `"environment"`, Claude Code usa `"env"`
4. **Env expansion**: Kilocode usa `{env:VAR}`, Claude Code usa `${VAR}`
5. **Remote type**: Kilocode usa `"type": "remote"`, Claude Code usa `"type": "http"`

## Best Practice per Configurazione MCP (Context7-verified)

### 1. Usa `json_response=True` per output strutturato
Il MCP SDK raccomanda `FastMCP("name", json_response=True)` per risposte JSON strutturate invece di testo SSE.

### 2. Usa stdio per sviluppo locale, streamable-http per produzione
- **stdio**: subprocess communication (Kilocode CLI, Claude Code, OpenCode)
- **streamable-http**: production deployment con `stateless_http=True` per scalabilità

### 3. Composizione con GitHub MCP Server
GitHub Discovery NON duplica le funzionalità GitHub standard. Compone con il server ufficiale:
- GitHub MCP → repos, issues, PRs, search, context (operazioni standard)
- GitHub Discovery → discover_repos, screen_candidates, deep_assess, rank_repos (scoring/ranking)

### 4. Sicurezza
- Usa `X-MCP-Readonly: true` per il server GitHub (nessuna scrittura)
- Non committare mai token GitHub nei file di configurazione
- Usa sempre variabili d'ambiente per le credenziali (`{env:GITHUB_TOKEN}` o `${GITHUB_TOKEN}`)

## See Also

- [MCP-Native Agentic Integration Architecture](../architecture/mcp-native-design.md) — design MCP-first
- [MCP Tool Specifications](mcp-tools.md) — specifiche complete dei 16 tool
- [Agent Workflow Patterns](../patterns/agent-workflows.md) — workflow per agenti
- [Kilo Marketplace Deployment Model](../patterns/marketplace-deployment.md) — formato MCP.yaml
- [Architecture Analysis](../architecture/architecture-analysis.md) — analisi architetturale completa
