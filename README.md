# GitHub Discovery

> MCP-native agentic discovery engine that finds high-quality GitHub repositories independent of popularity.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## The Problem

Current discovery tools — GitHub search, AI agents (Perplexity, Claude, ChatGPT, Gemini) — rely primarily on:

- **Star count** (popularity)
- **Online discussion frequency** (Reddit, Stack Overflow, blog mentions)

This creates a systematic bias that excludes technically excellent projects with low visibility.

**GitHub Discovery** flips this paradigm: it finds underrated, high-quality repositories using a tiered scoring pipeline that measures **technical merit** — not social buzz.

## How It Works

GitHub Discovery uses a **four-gate progressive pipeline** where each gate adds depth at increasing cost:

```
Gate 0 — Candidate Discovery    → Find repos via multiple channels
Gate 1 — Metadata Screening      → Zero-cost quality signals (zero LLM)
Gate 2 — Static/Security Screen  → Low-cost deep checks (zero or low LLM)
Gate 3 — LLM Deep Assessment     → Expensive, only for top percentile
```

**Hard rule:** A candidate never reaches Gate 3 without passing Gates 1 + 2 first.

### Anti-Star Bias

Stars are **context only**, never a primary scoring signal. The core metric is the **Value Score**:

```
Value Score = quality_score / log10(star_count + 10)
```

This surfaces hidden gems — technically excellent repos that are underrated by star count alone.

## MCP-Native Architecture

GitHub Discovery is designed as an **MCP-native agentic system**, not a standalone CLI or API. It integrates deeply into agent workflows (Kilocode CLI, OpenCode/OpenClaude, Claude Code) via the Model Context Protocol.

### MCP Tools

| Tool | Purpose |
|------|---------|
| `discover_repos` | Find candidate repositories (Layer A) |
| `screen_candidates` | Gate 1+2 progressive screening (Layer B) |
| `quick_screen` | Single repo quick quality check |
| `deep_assess` | LLM deep assessment (Layer C) |
| `quick_assess` | Targeted dimension assessment |
| `rank_repos` | Anti-star bias ranking (Layer D) |
| `explain_repo` | Explainability report for a repo |
| `compare_repos` | Side-by-side comparison |
| `create_session` | Start a discovery session |
| `export_session` | Export results |

### MCP Prompt Skills (Agent Workflows)

| Skill | Description |
|-------|-------------|
| `discover_underrated` | Find technically excellent repos underrated by star count |
| `quick_quality_check` | Quick quality assessment of a specific repository |
| `compare_for_adoption` | Compare multiple repos for adoption decision |
| `domain_deep_dive` | Deep exploration of a specific domain |
| `security_audit` | Security-first assessment of repositories |

## Project Status

**Early planning phase.** The foundation blueprint is complete, including the full agentic integration architecture (§21). No source code yet — this repo contains the design documents, research findings, and LLM wiki knowledge base.

## Documentation

- [Foundation Blueprint](docs/foundation/github-discovery_foundation_blueprint.md) — Complete project specification
- [Foundation Roadmap](docs/roadmaps/github-discovery_foundation_roadmap.md) — Project milestones
- [LLM Wiki](docs/llm-wiki/wiki/index.md) — Compiled knowledge base

## Tech Stack (Planned)

- **Language:** Python 3.12+
- **MCP Server:** FastMCP (Python MCP SDK)
- **REST API:** FastAPI (secondary interface)
- **CLI:** Typer
- **Models:** Pydantic v2
- **Configuration:** pydantic-settings (`GHDISC_` prefix)
- **HTTP Client:** httpx (async)
- **Logging:** structlog
- **Testing:** pytest, respx
- **Linting/Formatting:** Ruff, mypy --strict

## Quick Start (Planned)

```bash
# Install
pip install -e ".[dev]"

# CLI usage
python -m github_discovery discover --query "static analysis python"

# MCP server
python -m github_discovery.mcp serve
```

## Configuration

All settings use environment variables with the `GHDISC_` prefix:

```bash
GHDISC_GITHUB_TOKEN=ghp_xxx          # Required: GitHub token
GHDISC_SESSION_BACKEND=sqlite         # Session storage (sqlite | redis)
GHDISC_MCP_TRANSPORT=stdio           # MCP transport (stdio | http)
```

## Philosophy

- **Plan before code** — every non-trivial task starts with an explicit plan
- **Verify before complete** — a task is not done without verifiable evidence
- **Reuse over rebuild** — integrate existing tools before extending
- **Least privilege** — read-only and allowlist by default
- **Context discipline** — short sessions, clear scope, reset between unrelated tasks
- **No silent failures** — errors must be logged with retry strategy

## License

MIT