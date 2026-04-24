---
Title: Kilo Marketplace MCP Server Deployment Model
Topic: patterns
Sources:
  - https://github.com/Kilo-Org/kilo-marketplace (README.md, CONTRIBUTING.md)
  - mcps/github/MCP.yaml (example entry)
  - mcps/context7/MCP.yaml (example with multiple install options)
  - Context7 /modelcontextprotocol/python-sdk (FastMCP transport patterns)
Raw:
  - docs/analysis/phase10_analysis.md
Updated: 2026-04-24
Confidence: high
---

# Kilo Marketplace MCP Server Deployment Model

## What is the Kilo Marketplace

The [Kilo Marketplace](https://github.com/Kilo-Org/kilo-marketplace) is a curated GitHub repository that indexes three types of resources for the Kilo ecosystem (Kilo Code, Kilo CLI, compatible agents):

| Type | Format | Purpose |
|------|--------|---------|
| **Skills** | `skills/<name>/SKILL.md` | Agent workflows and domain expertise |
| **MCP Servers** | `mcps/<name>/MCP.yaml` | Standardized tool/service integrations |
| **Modes** | `modes/<name>/MODE.yaml` | Custom agent personalities/behaviors |

**Important**: The marketplace does NOT host source code. It acts as an index pointing to external repositories.

## MCP.yaml Format

Every MCP server entry is a `mcps/<name>/MCP.yaml` file with this structure:

```yaml
id: server-name                    # Unique kebab-case identifier
name: Display Name                 # Human-readable name
description: >                     # Clear description of capabilities
  Description text here.
author: author-name                # Author or organization
url: https://github.com/org/repo   # Link to source repository
tags:                              # Tags for discovery
  - tag1
  - tag2
prerequisites:                     # Required software/accounts
  - Prerequisite 1
content:                           # Installation config(s)
  - name: NPX                      # Option name
    prerequisites:
      - Node.js
    content: |
      {
        "command": "npx",
        "args": ["-y", "@package/mcp-server"],
        "env": {
          "API_KEY": "{{API_KEY}}"
        }
      }
parameters:                        # User-configurable params
  - name: API Key
    key: API_KEY
    placeholder: your_api_key_here
```

## Install Options for Python MCP Servers

### UVX (recommended for Python)

```yaml
- name: UVX
  prerequisites:
    - Python 3.12+
    - uv package manager
  content: |
    {
      "command": "uvx",
      "args": ["package-name", "mcp", "serve", "--transport", "stdio"],
      "env": {
        "API_TOKEN": "{{API_TOKEN}}"
      }
    }
```

### Docker

```yaml
- name: Docker
  prerequisites:
    - Docker
  content: |
    {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-e", "API_TOKEN",
               "org/package-name:latest"],
      "env": {
        "API_TOKEN": "{{API_TOKEN}}"
      }
    }
```

### Remote Server (Streamable HTTP)

```yaml
- name: Remote Server
  content: |
    {
      "type": "streamable-http",
      "url": "https://your-server.com/mcp",
      "headers": {
        "Authorization": "Bearer {{API_TOKEN}}"
      }
    }
```

## GitHub Discovery MCP.yaml

```yaml
id: github-discovery
name: GitHub Discovery
description: >
  MCP-native agentic discovery engine that finds high-quality GitHub repositories
  independent of popularity. Tiered scoring: discovery → screening → deep assessment →
  anti-star bias ranking with explainability.
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
prerequisites:
  - GitHub Personal Access Token
content:
  - name: UVX (recommended)
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
                 "ghcr.io/fulviocoschi/github-discovery:latest"],
        "env": {
          "GHDISC_GITHUB_TOKEN": "{{GHDISC_GITHUB_TOKEN}}"
        }
      }
parameters:
  - name: GitHub Token
    key: GHDISC_GITHUB_TOKEN
    placeholder: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## Submission Process

1. Fork `Kilo-Org/kilo-marketplace`
2. Create `mcps/github-discovery/MCP.yaml`
3. Open PR with title "Add GitHub Discovery MCP server"
4. Kilo team reviews and merges

## Client Configuration Patterns

### Kilo Code / Kilocode CLI

```json
{
  "mcp": {
    "github-discovery": {
      "command": "uvx",
      "args": ["github-discovery", "mcp", "serve", "--transport", "stdio"],
      "env": {
        "GHDISC_GITHUB_TOKEN": "{env:GITHUB_TOKEN}"
      }
    }
  }
}
```

### OpenCode

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

### Claude Desktop

```json
{
  "mcpServers": {
    "github-discovery": {
      "command": "uvx",
      "args": ["github-discovery", "mcp", "serve", "--transport", "stdio"],
      "env": {
        "GHDISC_GITHUB_TOKEN": "ghp_xxx"
      }
    }
  }
}
```

## MCP Transport (Context7-verified)

From `/modelcontextprotocol/python-sdk` v1.x:

| Transport | Use Case | Config |
|-----------|----------|--------|
| `stdio` | Local agent integration (Kilo Code, Claude Desktop) | `mcp.run(transport="stdio")` |
| `streamable-http` | Remote/deployment, production | `mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)` |

Stateless HTTP mode (recommended for production):
```python
mcp = FastMCP("Server", stateless_http=True, json_response=True)
```

## See Also
- [Phase 10 Alpha Engine Analysis](phase10-alpha-analysis.md)
- [MCP Python SDK Verification](../apis/mcp-sdk-verification.md)
- [MCP-Native Agentic Integration Architecture](../architecture/mcp-native-design.md)
