# AGENTS.md — GitHub Discovery

Guidance for agentic coding agents operating in this repository.

## Project Overview

GitHub Discovery is a **MCP-native agentic discovery engine** that finds high-quality GitHub repositories
independent of popularity (stars, social buzz). It uses a tiered scoring pipeline:
discovery → lightweight screening → deep LLM assessment → explainable ranking.

**Architecture**: MCP-native agentic system (MCP primary, API secondary, CLI agent-friendly).
Designed for deep integration into Kilocode CLI, OpenCode/OpenClaude, and Claude Code agent workflows.
See `docs/foundation/github-discovery_foundation_blueprint.md` §21 for full agentic integration architecture.

**Current phase:** Early planning. No source code yet. Foundation blueprint is complete (including §21 Agentic Integration Architecture).

---

## Build / Lint / Test Commands

> These commands will be activated once the Python project structure is scaffolded.

```bash
# Install dependencies (dev + runtime)
make install
# or: pip install -e ".[dev]"

# Run all tests
make test
# or: pytest

# Run a single test file
pytest tests/test_discovery.py

# Run a single test by name (function or class::method)
pytest tests/test_scoring.py::test_metadata_score -v
pytest tests/test_screening.py::TestGate1::test_hygiene_files -v

# Run tests matching a keyword expression
pytest -k "test_ranking" -v

# Run only unit tests (exclude integration/slow)
pytest -m "not integration and not slow"

# Lint everything
make lint
# or individually:
ruff check src/ tests/
mypy src/

# Format check
ruff format --check src/ tests/

# Auto-fix lint issues
ruff check --fix src/ tests/
ruff format src/ tests/

# Type check
mypy src/ --strict

# Run the CLI locally
python -m github_discovery --help
python -m github_discovery discover --query "static analysis python"

# Run MCP server locally
python -m github_discovery.mcp serve

# Run MCP server with specific transport
python -m github_discovery.mcp serve --transport stdio
python -m github_discovery.mcp serve --transport http --port 8080

# Test MCP integration (requires MCP client)
pytest tests/agentic/ -v

# Generate MCP config for agent integration
python -m github_discovery mcp init-config --target kilo
```

---

## Project Structure (Planned)

```
github-discovery/
├── src/github_discovery/       # Main package
│   ├── __init__.py
│   ├── cli.py                  # CLI entry point (typer)
│   ├── api/                    # FastAPI REST API (secondary interface)
│   ├── discovery/              # Candidate discovery engine (Layer A)
│   ├── screening/              # Lightweight quality screening (Layer B)
│   ├── assessment/             # Deep technical assessment (Layer C)
│   ├── scoring/                # Scoring, ranking, explainability (Layer D)
│   ├── mcp/                    # MCP primary interface (tools, resources, prompts)
│   │   ├── server.py           # FastMCP server setup
│   │   ├── tools/              # Granular per-gate MCP tools
│   │   ├── resources/          # MCP resources (scores, pools, rankings)
│   │   ├── prompts.py          # Agent skill definitions (workflow prompts)
│   │   ├── session.py          # Session management for cross-agent workflows
│   │   ├── progress.py         # Streamable progress notifications
│   │   ├── output_format.py    # Context-efficient output formatting
│   │   ├── github_client.py    # Composition with GitHub MCP Server
│   │   ├── transport.py        # STDIO + streamable-http transports
│   │   └── config.py           # MCP configuration (GHDISC_MCP_*)
│   ├── models/                 # Pydantic data models
│   │   ├── session.py          # Session state, progress, workflow config
│   │   ├── mcp_spec.py         # MCP tool specs, agent workflow configs
│   │   └── agent.py            # Agentic support models
│   ├── workers/                # Background scoring workers
│   └── config.py               # Settings (pydantic-settings)
├── tests/                      # Mirrors src structure
│   ├── unit/
│   ├── integration/
│   ├── agentic/                # MCP client integration tests
│   └── conftest.py
├── .kilo/                      # Kilocode CLI config
│   └── mcp.json.template       # Template for MCP composition config
├── pyproject.toml              # Build config, dependencies, tool settings
├── Makefile                    # Common dev commands
└── docs/                       # Documentation
```

---

## Code Style Guidelines

### Python Version & Tooling

- **Python 3.12+** (use modern syntax: type aliases, match statements, f-strings)
- **Ruff** for linting and formatting (replaces black, isort, flake8)
- **mypy --strict** for type checking
- **pytest** for testing
- **Pydantic v2** for data models and settings

### Imports

```python
# Standard library first
from pathlib import Path

# Third-party second
from pydantic import BaseModel
import httpx

# Local imports last — use absolute imports from package root
from github_discovery.models import RepoCandidate, ScoreResult
from github_discovery.screening.gate1 import metadata_screen

# Use explicit imports — avoid wildcard imports
# BAD: from github_discovery.scoring import *
# GOOD: from github_discovery.scoring import compute_rank, ScoreDimension
```

### Formatting

- Line length: **99 characters** (ruff default is 88; override in pyproject.toml)
- Use **trailing commas** in multi-line collections
- Use **f-strings** over `.format()` or `%` formatting
- Use **snake_case** for variables, functions, modules
- Use **PascalCase** for classes, Pydantic models, type aliases
- Use **UPPER_SNAKE_CASE** for constants

### Type Annotations

- **All** public functions must have full type annotations (enforced by mypy --strict)
- Use `from __future__ import annotations` at the top of files for forward references
- Prefer Pydantic models over raw dicts for structured data
- Use `Optional[X]` or `X | None` for nullable values
- Use `list[X]`, `dict[str, X]` (lowercase generics — Python 3.12+ style)

```python
from __future__ import annotations

def compute_score(
    repo: RepoCandidate,
    dimensions: list[ScoreDimension],
    *,
    min_confidence: float = 0.5,
) -> ScoreResult:
    ...
```

### Naming Conventions

- **Modules**: `screening.py`, `gate1_metadata.py` (snake_case, descriptive)
- **Classes**: `RepoCandidate`, `ScoreResult`, `DiscoveryEngine` (PascalCase)
- **Functions**: `compute_rank()`, `screen_candidates()` (snake_case, verb-noun)
- **Constants**: `MAX_TOKENS_PER_REPO`, `DEFAULT_GATING_THRESHOLD` (UPPER_SNAKE)
- **Config/settings**: `Settings` class with `pydantic-settings`, env-prefixed `GHDISC_`
- **CLI commands**: `discover`, `screen`, `deep-eval`, `rank`, `export` (kebab-case)

### Error Handling

- Use **custom exception hierarchy** — never raise bare `Exception`
- Define domain exceptions in `github_discovery/exceptions.py`
- Use **structured error results** over exceptions for expected failures (e.g., repo not scorable)
- Log with `structlog` (structured JSON logging) — never use `print()` for diagnostics
- Always include **context** in error messages (repo URL, dimension, gate level)

```python
# BAD
raise Exception("Scoring failed")

# GOOD
class ScoringError(GitHubDiscoveryError):
    """Raised when scoring pipeline fails for a candidate."""

raise ScoringError(
    f"Gate 2 static screening failed for {repo.full_name}: {detail}"
)
```

### Async Patterns

- Use `async/await` for I/O-bound operations (API calls, file I/O, subprocess)
- Use `httpx` for async HTTP (GitHub API calls)
- Use `asyncio.Semaphore` for rate limiting — respect GitHub API limits
- Workers should use task queues (not raw asyncio.gather for unbounded parallelism)

### Testing Conventions

- **Mirror source structure** in `tests/`: `tests/screening/test_gate1.py`
- Use **fixtures** in `conftest.py` for shared setup (GitHub API mocks, sample repos)
- Mark integration tests with `@pytest.mark.integration`
- Mark slow tests with `@pytest.mark.slow`
- Use `pytest.raises` for expected errors — never use `try/except` in tests
- Mock external APIs with `respx` (httpx) or `pytest-httpx`
- Aim for **>80% coverage** on screening/scoring logic

---

## Architectural Rules

### Tiered Pipeline (Critical)

The scoring pipeline has hard gates. Respect them:

1. **Gate 0** — Candidate discovery (multichannel)
2. **Gate 1** — Metadata screening (zero LLM cost)
3. **Gate 2** — Static/security screening (zero or low cost)
4. **Gate 3** — LLM deep assessment (expensive — only top percentile)

**Hard rule:** Never send a candidate to Gate 3 without passing Gate 1 + Gate 2.

### Anti-Star Bias

Stars are **context only**, never a primary scoring signal. The `Value Score`
formula (`quality_score / log10(star_count + 10)`) is the reference pattern
for identifying hidden gems.

### MCP Integration

- Reuse `github/github-mcp-server` for standard GitHub operations
- GitHub Discovery adds only scoring/ranking logic — do not duplicate MCP functionality
- Default to **read-only** mode in analysis pipelines
- MCP toolsets should be minimal (`repos, issues, pull_requests, context`)

### Configuration

- All settings via environment variables with `GHDISC_` prefix
- Use `pydantic-settings` for typed configuration
- Never hardcode API tokens — always from env/secrets
- Sensible defaults for local development
- MCP-related settings via `GHDISC_MCP_*` prefix (transport, toolsets, session backend)
- Session backend: `sqlite` (default, local), `redis` (deployment)
- MCP tool context limit: default 2000 tokens per tool invocation (configurable via `GHDISC_MCP_MAX_CONTEXT_TOKENS`)

---

## Agentic Integration Architecture (Blueprint §21)

GitHub Discovery is designed as a **MCP-native agentic system**, not a standalone app or script.
It integrates deeply into agent workflows (Kilocode CLI, OpenCode/OpenClaude, Claude Code) via MCP.

### MCP-First Design Principles

1. **MCP is the primary interface** — Agents interact via MCP tools, resources, and prompts. REST API is a secondary consumer of the same core services.
2. **Progressive Deepening** — Every gate is an independent MCP tool. Agents decide when to deepen, not the pipeline.
3. **Agent-Driven Policy** — Gating thresholds are tool parameters, not hardcoded constants.
4. **Session-Aware** — Operations support `session_id` for cross-session workflow continuity.
5. **Context-Efficient** — Tools return summary-first output (< 2000 tokens default) with on-demand detail.
6. **Composable with GitHub MCP** — No duplication of GitHub functionality; discovery adds only scoring/ranking.

### MCP Tool Overview

| Tool | Purpose | Agent Workflow |
|------|---------|---------------|
| `discover_repos` | Find candidate repos (Layer A) | Start discovery, get pool |
| `screen_candidates` | Gate 1+2 screening (Layer B) | Progressive deepening by gate |
| `quick_screen` | Single repo quick check | Fast quality check on a specific repo |
| `deep_assess` | LLM deep assessment (Layer C) | Deep evaluation of top candidates |
| `quick_assess` | Subset dimension assessment | Targeted assessment on specific dimensions |
| `rank_repos` | Anti-star bias ranking (Layer D) | Get ranked results per domain |
| `explain_repo` | Explainability report | Understand why a repo scored high/low |
| `compare_repos` | Side-by-side comparison | Decision-making between alternatives |
| `create_session` | Start a discovery session | Cross-session workflow |
| `export_session` | Export results | Persist and share findings |

### MCP Prompt Skills (Agent Workflows)

| Skill | Description |
|-------|-------------|
| `discover_underrated` | Find technically excellent repos underrated by star count |
| `quick_quality_check` | Quick quality assessment of a specific repository |
| `compare_for_adoption` | Compare multiple repos for adoption decision |
| `domain_deep_dive` | Deep exploration of a specific domain |
| `security_audit` | Security-first assessment of repositories |

### Configuration for Kilocode CLI

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

### Agent Workflow Patterns

```
Pattern 1: Quick Assessment
  → discover_repos(query="static analysis python", max_candidates=50)
  → quick_screen(repo_url) or screen_candidates(gate_level="1")
  → Result: fast quality signal

Pattern 2: Deep Discovery (Progressive Deepening)
  → create_session(name="ml-search")
  → discover_repos(query="machine learning framework", session_id=...)
  → screen_candidates(gate_level="both", session_id=...)
  → deep_assess(repo_urls=[...], session_id=...)
  → rank_repos(domain="ml_lib", session_id=...)
  → explain_repo(repo_url=..., detail_level="full")

Pattern 3: Comparison for Adoption
  → screen_candidates → quick_assess → compare_repos
  → Result: side-by-side comparison for decision
```

---

## Operational Rules (from Foundation Blueprint §17)

1. **Plan before code** — every non-trivial task starts with an explicit plan
2. **Verify before complete** — a task is not done without verifiable evidence
3. **Reuse over rebuild** — integrate existing official tools before extending
4. **Least privilege by default** — read-only and allowlist for commands/tools
5. **Context discipline** — short sessions, clear scope, reset between unrelated tasks
6. **No silent failures** — errors must be logged with retry strategy

### Agent Workflow Standard

```
Explore → Plan → Implement → Verify → Review → Ship
```

- **Explore**: read-only analysis of context
- **Plan**: implementation plan with verification criteria
- **Implement**: minimal, iterative changes
- **Verify**: test/lint/typecheck/metrics
- **Review**: final check (human or sub-agent)
- **Ship**: commit/PR with rationale

---

## Key References

- Foundation blueprint: `docs/foundation/github-discovery_foundation_blueprint.md` (including §21 Agentic Integration Architecture)
- Roadmap: `docs/roadmaps/github-discovery_foundation_roadmap.md`
- Findings and research: `findings.md`
- Task plan: `task_plan.md`
- Progress log: `progress.md`
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- MCP Apps SDK: https://github.com/modelcontextprotocol/ext-apps
- GitHub MCP Server: https://github.com/github/github-mcp-server
- Kilocode CLI MCP docs: https://kilo.ai/docs/automate/mcp/using-in-cli
- Kilocode Code MCP docs: https://kilo.ai/docs/features/mcp/using-mcp-in-kilo-code
- Kilo Marketplace: https://github.com/Kilo-Org/kilo-marketplace

---

## LLM Wiki — Persistent Knowledge Base

> **Inspired by [Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)** — the wiki is a persistent, compounding artifact. Knowledge is compiled once and kept current, not re-derived on every session. The LLM owns the wiki layer; you own the sources and the questions.

### Core Principle

**IMPORTANT: When reconstructing project context at the start of any session, the agent MUST consult the LLM Wiki FIRST.** The wiki contains pre-compiled, cross-referenced, citation-backed knowledge about this project. Raw documentation (`docs/foundation/`, `docs/roadmaps/`, etc.) is the secondary source — consult it only when the wiki does not cover the topic, or when verifying a claim that appears stale.

The priority order for context reconstruction is:
1. **`docs/llm-wiki/wiki/`** — Compiled knowledge (primary context source)
2. **Project raw documentation** — All `.md` files in `docs/` (except `docs/llm-wiki/`), root `.md` files, and other project documentation (verification and deepening)
3. **`docs/llm-wiki/raw/`** — External sources collected during research (supplementary)

### Architecture

The LLM Wiki has three layers:

| Layer | Path | Owner | Mutability | Purpose |
|-------|------|-------|------------|---------|
| **Raw sources (project)** | `docs/foundation/`, `docs/roadmaps/`, root `.md` files | Human | Immutable | Project source documents |
| **Raw sources (external)** | `docs/llm-wiki/raw/` | Human | Immutable | External sources collected during research |
| **Wiki** | `docs/llm-wiki/wiki/` | LLM | LLM-maintained | Compiled, cross-referenced knowledge |
| **Schema** | `AGENTS.md` (this section) | Both | Co-evolved | Rules for wiki structure and operations |

**Raw sources inventory — the following project documentation constitutes the raw layer and MUST NOT be modified after ingestion:**

| Raw Source | Path | Description |
|------------|------|-------------|
| Foundation Blueprint | `docs/foundation/github-discovery_foundation_blueprint.md` | Complete project specification including §21 Agentic Integration Architecture |
| Foundation Roadmap | `docs/roadmaps/github-discovery_foundation_roadmap.md` | Project roadmap and milestones |
| Findings | `findings.md` | Research findings and discoveries |
| Task Plan | `task_plan.md` | Active task planning and tracking |
| Progress Log | `progress.md` | Session progress tracking |
| Workflow State | `.workflow/state.md` | Current workflow phase and agent history |

Additional `.md` files may be added as the project evolves. Any `.md` file outside `docs/llm-wiki/` is a raw source. The wiki layer synthesizes knowledge FROM these raw sources — it never replaces them.

**Directory structure:**

```
docs/llm-wiki/
├── raw/                        # External sources (research, articles, library docs)
│   ├── architecture/            # Architecture decision records from external sources
│   ├── apis/                    # API references, MCP specs from external sources
│   ├── research/                # Research papers, articles found online
│   └── libraries/               # Library documentation, framework docs downloaded
├── wiki/                        # LLM-maintained compiled knowledge
│   ├── architecture/            # Architecture decisions and rationale
│   ├── apis/                    # API design knowledge
│   ├── domain/                  # GitHub discovery domain knowledge
│   ├── patterns/                # Implementation patterns and conventions
│   ├── index.md                 # Global table of contents
│   └── log.md                   # Append-only operation log
└── templates/                   # Page templates for consistency
    ├── raw-source.md
    ├── article.md
    └── archive.md

Project raw sources (NOT inside llm-wiki/ — treated as immutable inputs):
├── docs/foundation/             # Foundation blueprint and specifications
├── docs/roadmaps/               # Roadmap and milestone documents
├── findings.md                  # Research findings (root)
├── task_plan.md                 # Task planning (root)
├── progress.md                  # Progress tracking (root)
└── .workflow/state.md            # Workflow state
```

### Three Operations

The wiki supports three operations. Every interaction with the knowledge base is one of these:

#### 1. Ingest — Compile a source into the wiki

**When:** A new document, decision, or piece of knowledge needs to be internalized.

**Source types:**
- **Project raw sources** — Files already in the project (`docs/foundation/`, `docs/roadmaps/`, root `.md` files). These are already in place — do NOT copy them into `raw/`. Reference them directly from wiki articles via relative paths.
- **External sources** — Articles, papers, library docs found online. Store these in `docs/llm-wiki/raw/<topic>/` with metadata header (see `templates/raw-source.md`).

**Steps:**
1. For external sources: store in `docs/llm-wiki/raw/<topic>/` with metadata header. For project sources: skip this step — they already exist in place.
2. Determine where the knowledge belongs in the wiki:
   - **Same thesis as existing article** → Merge into that article, add source to `Sources/Raw` fields
   - **New concept** → Create new article in `wiki/<topic>/`
   - **Spans multiple topics** → Place in most relevant topic, add `See Also` cross-references
3. **Cascade updates:** Check all other wiki articles for content affected by the new source. Update every materially affected article and refresh its `Updated` date
4. Update `wiki/index.md` with new/modified entries
5. Append to `wiki/log.md`: `## [YYYY-MM-DD] ingest | <article title>`

**IMPORTANT: Never modify project raw sources (`docs/foundation/`, `docs/roadmaps/`, root `.md` files) or files in `docs/llm-wiki/raw/` after initial ingestion. All raw sources are immutable.**

#### 2. Query — Search the wiki and answer with citations

**When:** Reconstructing project context or answering a question about the project.

**Steps:**
1. Read `wiki/index.md` to locate relevant articles
2. Read relevant articles and synthesize an answer
3. **Cite wiki pages** with markdown links: `[Article Title](docs/llm-wiki/wiki/topic/article.md)`
4. If the wiki does not cover the topic, fall back to raw documentation in this order:
   - `docs/llm-wiki/raw/` (curated external sources collected during research)
   - `docs/foundation/`, `docs/roadmaps/` (project specification and roadmap documents)
   - Root `.md` files: `findings.md`, `task_plan.md`, `progress.md` (research, planning, progress)
5. **If the answer is particularly valuable** (non-obvious synthesis, comparison, decision rationale), offer to archive it as a new wiki page

**IMPORTANT: Always prefer wiki content over raw documentation. The wiki already contains synthesized, cross-referenced knowledge. Re-deriving from raw sources wastes context and loses accumulated insight.**

#### 3. Lint — Health-check the wiki

**When:** Periodically, or when you suspect wiki staleness. Run as a maintenance task.

**Deterministic checks (auto-fix):**
- **Index consistency:** Compare `wiki/index.md` against actual files. Add missing entries. Mark phantom entries as `[MISSING]`
- **Internal links:** Verify every markdown link in wiki/ points to an existing file. Fix broken paths
- **Raw references:** Verify every link in `Raw` fields points to an existing file — either in `docs/llm-wiki/raw/` (external sources) or in the project raw source locations (`docs/foundation/`, `docs/roadmaps/`, root `.md` files)
- **See Also:** Add missing cross-references between related articles; remove links to deleted files

**Heuristic checks (report only):**
- Factual contradictions across articles
- Outdated claims superseded by newer sources
- Missing conflict annotations where sources disagree
- Orphan pages with no inbound links from other wiki articles
- Concepts frequently mentioned but lacking a dedicated page

**After lint:** Append to `wiki/log.md`: `## [YYYY-MM-DD] lint | N issues found, M auto-fixed`

### Wiki Page Conventions

- **Article format:** Follow `templates/article.md` — metadata header (Title, Topic, Sources, Raw, Updated, Confidence), then content
- **File naming:** `kebab-case.md` based on the concept, not the source file
- **Cross-references:** Use relative markdown links within wiki files. Use project-root-relative paths in conversation
- **Topic directories:** One level only — `wiki/<topic>/<article>.md`. No deeper nesting
- **Confidence field:** `high` (3+ sources, recently confirmed), `medium` (1-2 sources), `low` (single source, untested)
- **Updated field:** Reflects when knowledge content last changed, not file system timestamp
- **Archived query answers:** Follow `templates/archive.md`. Always create as new pages — never merge into existing articles

### Session Context Rules (MANDATORY)

These rules govern how agents reconstruct project context across sessions:

1. **WIKI-FIRST CONTEXT RECONSTRUCTION:** At the start of every coding session, the agent MUST read `docs/llm-wiki/wiki/index.md` to understand what knowledge has already been compiled. This is the primary context source — not raw docs.

2. **PROGRESSIVE DISCLOSURE FOR CONTEXT:** When the agent needs deeper knowledge on a topic found in the index, read the specific wiki article. Only then, if still needed, consult raw sources. This minimizes context window consumption.

3. **COMPILE BACK INTO THE WIKI:** When the agent discovers non-trivial knowledge during a session (architecture decisions, debugging insights, design rationale, domain knowledge), it SHOULD offer to ingest it into the wiki. Good answers and explorations compound — they should not disappear into chat history.

4. **SESSION START PROTOCOL:**
   ```
   Read docs/llm-wiki/wiki/index.md → identify relevant articles → read articles → start work
   ```
   NOT:
   ```
   Read docs/foundation/*.md → read docs/roadmaps/*.md → re-derive everything from scratch
   ```

5. **SESSION END PROTOCOL:** Before ending a session where significant knowledge was produced or discovered:
   - Offer to ingest new knowledge into the wiki
   - Offer to lint if the wiki hasn't been checked recently
   - Update `wiki/log.md` with session summary

6. **STALENESS DETECTION:** If a wiki article's `Updated` date is more than 30 days old and the topic relates to active development, flag it for re-verification against current raw sources.

7. **NO DUPLICATION:** Never duplicate information that already exists in a wiki article. If the same fact appears in `AGENTS.md` and the wiki, the wiki is the canonical source. `AGENTS.md` contains rules, not knowledge.

### When to Ingest

Ingest into the wiki whenever:
- A new design decision is made and documented
- A significant debugging session reveals non-obvious project knowledge
- Raw documentation is read and synthesized for the first time
- A new library, framework, or external dependency's key concepts are learned
- Domain knowledge about GitHub scoring, quality signals, or anti-star bias is formalized
- An architectural pattern or convention is established

### When NOT to Ingest

Do NOT ingest:
- Trivial facts the agent can infer from code (e.g., "the project uses Python" — that's in `AGENTS.md`)
- Transient debugging state (e.g., "this specific test is currently failing")
- Information already captured in an existing wiki article (update instead)
- Raw content that hasn't been synthesized — that goes in `raw/`, not `wiki/`

### LLM Wiki Reference

- Original concept: [Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- V2 extension (lifecycle, knowledge graph): [LLM Wiki v2](https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2)
- Agent skill implementation: [karpathy-llm-wiki](https://github.com/Astro-Han/karpathy-llm-wiki)
