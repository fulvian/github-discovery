# GitHub Discovery

> MCP-native agentic discovery engine that finds high-quality GitHub repositories independent of popularity.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-1326%20passing-brightgreen.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## The Problem

Current discovery tools — GitHub search, AI agents (Perplexity, Claude, ChatGPT, Gemini) — rely primarily on:

- **Star count** (popularity)
- **Online discussion frequency** (Reddit, Stack Overflow, blog mentions)

This creates a systematic bias that excludes technically excellent projects with low visibility.

**GitHub Discovery** flips this paradigm: it finds high-quality repositories using a tiered scoring pipeline that measures **technical merit** — not social buzz. Stars are treated as **corroboration metadata** (how many users validated quality), never as a scoring signal.

## How It Works

GitHub Discovery uses a **four-gate progressive pipeline** where each gate adds depth at increasing cost:

```
Gate 0 — Candidate Discovery    → Find repos via multiple channels (Search, Registry, Code Search, etc.)
Gate 1 — Metadata Screening      → Zero-cost quality signals (zero LLM, 7 sub-scores)
Gate 2 — Static/Security Screen  → Low-cost deep checks (zero or low LLM, 4 sub-scores)
Gate 3 — LLM Deep Assessment     → Expensive, only for top percentile (8 quality dimensions)
```

**Hard rule:** A candidate never reaches Gate 3 without passing Gates 1 + 2 first.

### Star-Neutral Quality Scoring

Stars are **corroboration metadata only** — they tell you HOW MANY people validated quality, not WHAT the quality is. Stars never change the quality score, never act as a ranking signal, and never penalize a repo.

**Quality Score** = domain-weighted composite across 8 dimensions:
- Code Quality (20%), Architecture (15%), Testing (15%), Documentation (10-15%)
- Maintenance (15%), Security (10-15%), Functionality (5-10%), Innovation (5%)

**Corroboration Levels** (informational metadata):

| Stars | Level | Meaning |
|-------|-------|---------|
| 0 | `new` | Quality assessment is the only signal |
| 1–49 | `unvalidated` | Few users have tested this |
| 50–499 | `emerging` | Some community validation |
| 500–4,999 | `validated` | Moderate community confirms quality |
| 5,000+ | `widely_adopted` | Broad community validation |

**Hidden Gems** = informational label for repos with `quality_score ≥ 0.5` AND `stars < 100`. This does NOT affect ranking — it's a flag for the user.

## Real E2E Validation

Tested with a real discovery query ("mcp office") against live GitHub APIs:

| Rank | Repository | Quality | Stars | Corroboration |
|------|-----------|---------|-------|---------------|
| 1 | [PsychQuant/che-word-mcp](https://github.com/PsychQuant/che-word-mcp) | 0.703 | 0 | new 💎 |
| 2 | [modelcontextprotocol/typescript-sdk](https://github.com/modelcontextprotocol/typescript-sdk) | 0.672 | 12,281 | widely_adopted |
| 3 | [walksoda/crawl-mcp](https://github.com/walksoda/crawl-mcp) | 0.653 | 0 | new 💎 |
| 4 | [OfficeDev/Office-UI-Fabric-Core](https://github.com/OfficeDev/Office-UI-Fabric-Core) | 0.431 | 3,747 | validated |
| 5 | [Softeria/ms-365-mcp-server](https://github.com/Softeria/ms-365-mcp-server) | 0.383 | 651 | validated |

→ See [Test Report #1](test_report_1.md) for the complete analysis with per-repo LLM assessment details.

## MCP-Native Architecture

GitHub Discovery is designed as an **MCP-native agentic system** — not a standalone CLI or API. It integrates deeply into agent workflows (Kilocode CLI, OpenCode/OpenClaude, Claude Code) via the Model Context Protocol.

### MCP Tools

| Tool | Purpose |
|------|---------|
| `discover_repos` | Find candidate repositories (Layer A) |
| `screen_candidates` | Gate 1+2 progressive screening (Layer B) |
| `quick_screen` | Single repo quick quality check |
| `deep_assess` | LLM deep assessment (Layer C) |
| `quick_assess` | Targeted dimension assessment |
| `rank_repos` | Star-neutral quality ranking (Layer D) |
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

**Alpha — fully implemented and E2E validated.** All 10 foundation phases complete:
- ✅ 137 source files, 1326 tests passing
- ✅ ruff + mypy --strict clean
- ✅ Full pipeline: discover → screen → deep-eval → rank → explain → compare
- ✅ MCP server with 16 tools, 4 resources, 5 prompts
- ✅ REST API with FastAPI
- ✅ CLI with typer + Rich output
- ✅ Real E2E validation against live GitHub APIs
- ✅ Docker deployment ready

## Documentation

- [Foundation Blueprint](docs/foundation/github-discovery_foundation_blueprint.md) — Complete project specification
- [Foundation Roadmap](docs/roadmaps/github-discovery_foundation_roadmap.md) — Project milestones
- [LLM Wiki](docs/llm-wiki/wiki/index.md) — Compiled knowledge base (31 articles)
- [Test Report #1](test_report_1.md) — Real E2E validation report

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12+ |
| MCP Server | FastMCP (Python MCP SDK) |
| REST API | FastAPI |
| CLI | Typer + Rich |
| Models | Pydantic v2 |
| Configuration | pydantic-settings (`GHDISC_` prefix) |
| HTTP Client | httpx (async) |
| LLM Provider | NanoGPT (OpenAI-compatible) + instructor |
| Code Packing | python-repomix |
| Database | SQLite (aiosqlite) |
| Logging | structlog |
| Testing | pytest, respx |
| Linting | Ruff, mypy --strict |

## Quick Start

```bash
# Install
make install
# or: pip install -e ".[dev]"

# Set GitHub token
export GHDISC_GITHUB_TOKEN=ghp_xxx

# Discover repos
python -m github_discovery discover --query "mcp office" --max-results 30

# Screen candidates (Gate 1+2)
python -m github_discovery screen --pool-id <pool-id>

# Deep LLM assessment (Gate 3)
python -m github_discovery deep-eval --repo-urls "https://github.com/owner/repo"

# Rank results
python -m github_discovery rank --pool-id <pool-id>

# Explain a repo's score
python -m github_discovery explain "https://github.com/owner/repo"

# Compare repos
python -m github_discovery compare "url1,url2,url3"

# Run MCP server
python -m github_discovery.mcp serve

# Run all tests
make ci
```

## Configuration

All settings use environment variables with the `GHDISC_` prefix:

```bash
# Required
GHDISC_GITHUB_TOKEN=ghp_xxx

# Assessment (Gate 3)
GHDISC_ASSESSMENT_NANOGPT_API_KEY=sk-nano-xxx
GHDISC_ASSESSMENT_LLM_MODEL=gpt-4o

# MCP server
GHDISC_MCP_TRANSPORT=stdio           # stdio | http
GHDISC_MCP_PORT=8080

# Sessions
GHDISC_SESSION_BACKEND=sqlite         # sqlite | redis
```

## Philosophy

- **Star-neutral**: stars are metadata, not a scoring signal
- **Quality-first**: technical merit determines ranking, not popularity
- **Plan before code**: every non-trivial task starts with an explicit plan
- **Verify before complete**: a task is not done without verifiable evidence
- **Reuse over rebuild**: integrate existing tools before extending
- **Least privilege**: read-only and allowlist by default
- **Context discipline**: short sessions, clear scope, reset between unrelated tasks
- **No silent failures**: errors must be logged with retry strategy

## License

MIT
