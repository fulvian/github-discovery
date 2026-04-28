# GitHub Discovery

> MCP-native agentic discovery engine that finds high-quality GitHub repositories independent of popularity (stars).

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-1773%20passing-brightgreen.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Quick Start (60 seconds)

```bash
# Install via uvx (no permanent install needed)
uvx github-discovery mcp serve --transport stdio

# Or install permanently
pip install github-discovery

# Run a quick discovery
ghdisc discover --query "static analysis python"

# Check system readiness
ghdisc doctor
```

Requires **Python 3.12+** and a **GitHub token** (`GHDISC_GITHUB_TOKEN`).

## What is GitHub Discovery?

GitHub Discovery is an **MCP-native agentic discovery engine** that finds high-quality
GitHub repositories independent of popularity (stars, social buzz).

**Key philosophy**: Stars tell you *how many* people validated quality, not *what* the
quality is. A 0-star repo can be technically excellent, and a 10K-star repo can be
poorly maintained. GitHub Discovery evaluates code quality, architecture, testing,
documentation, maintenance, security, functionality, and innovation — not popularity.

**Star-neutral scoring**: `quality_score` is a pure technical assessment. `value_score`
equals `quality_score` (stars are not used as a signal). Hidden gems (high quality +
low stars) are surfaced as informational labels.

## Architecture

4-gate tiered pipeline:
- **Gate 0**: Multi-channel discovery (Search, Registry, Curated/Awesome Lists, Seed Expansion, Code Search)
- **Gate 1**: Metadata screening (zero LLM cost) — hygiene, CI/CD, test footprint, etc.
- **Gate 2**: Static/security screening — OpenSSF Scorecard, OSV vulnerabilities, secrets, complexity
- **Gate 3**: LLM deep assessment (only top percentile) — 8 dimensions via NanoGPT
- **Ranking**: Star-neutral intra-domain ranking with deterministic tie-breaking

## Installation

### Via uvx (recommended, no install)
```bash
uvx github-discovery mcp serve --transport stdio
```

### Via pip
```bash
pip install github-discovery
ghdisc doctor
```

### Via Docker
```bash
docker run --rm -e GHDISC_GITHUB_TOKEN=$GITHUB_TOKEN ghcr.io/fulvio/github-discovery:latest doctor
```

### Agent Platform Configuration

**Claude Code** (`.mcp.json`):
```json
{
  "mcpServers": {
    "github-discovery": {
      "command": "uvx",
      "args": ["github-discovery", "mcp", "serve", "--transport", "stdio"],
      "env": {
        "GHDISC_GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```

**Kilocode CLI** (`.kilo/mcp.json`):
```json
{
  "mcp": {
    "github-discovery": {
      "type": "local",
      "command": ["uvx", "github-discovery", "mcp", "serve", "--transport", "stdio"],
      "environment": {
        "GHDISC_GITHUB_TOKEN": "{env:GITHUB_TOKEN}"
      }
    }
  }
}
```

See `.mcp.json.example` and `.kilo/mcp.json.example` for complete configurations.

## Usage

```bash
# Discover repositories
ghdisc discover --query "web framework rust" --max-candidates 50

# Screen candidates (Gate 1+2)
ghdisc screen --pool-id <pool-id>

# Deep assessment (Gate 3)
ghdisc deep-eval --pool-id <pool-id>

# Rank results
ghdisc rank --pool-id <pool-id>

# Start MCP server
ghdisc mcp serve --transport stdio

# Run diagnostics
ghdisc doctor
```

## MCP Tools

| Tool | Purpose |
|------|---------|
| `discover_repos` | Find candidate repos |
| `screen_candidates` | Gate 1+2 screening |
| `deep_assess` | LLM assessment (Gate 3) |
| `rank_repos` | Star-neutral ranking |
| `explain_repo` | Score explanation |
| `compare_repos` | Side-by-side comparison |

## Links

- **Repository**: https://github.com/fulvio/github-discovery
- **Docs**: https://github.com/fulvio/github-discovery/tree/main/docs
- **Wiki**: https://github.com/fulvio/github-discovery/tree/main/docs/llm-wiki/wiki
- **License**: MIT
