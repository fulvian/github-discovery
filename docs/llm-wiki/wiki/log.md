# Wiki Log

<!-- Append-only operation log. Each entry follows the format: -->
<!-- ## [YYYY-MM-DD] operation | title -->
<!-- - detail line -->

<!-- Operations: ingest, query, lint, archive -->

## [2026-04-22] ingest | Tiered Scoring Pipeline
- Ingested from Foundation Blueprint §6, §16 and Roadmap Phase 2-5
- Created wiki/architecture/tiered-pipeline.md

## [2026-04-22] ingest | MCP-Native Agentic Integration Architecture
- Ingested from Foundation Blueprint §21 and Roadmap Phase 7
- Created wiki/architecture/mcp-native-design.md

## [2026-04-22] ingest | Anti-Star Bias Philosophy
- Ingested from Foundation Blueprint §3, §5, §7 and Findings §1
- Created wiki/architecture/anti-star-bias.md

## [2026-04-22] ingest | Option C Hybrid Architecture Decision
- Ingested from Foundation Blueprint §9, §19
- Created wiki/architecture/option-c-hybrid.md

## [2026-04-22] ingest | MCP Tool Specifications
- Ingested from Foundation Blueprint §21.3-21.8 and Roadmap Phase 7
- Created wiki/apis/mcp-tools.md

## [2026-04-22] ingest | GitHub API Patterns and Constraints
- Ingested from Foundation Blueprint §8, §18 and Findings
- Created wiki/apis/github-api-patterns.md

## [2026-04-22] ingest | Scoring Dimensions and Weight Profiles
- Ingested from Foundation Blueprint §7, §10 and Roadmap Phase 3-5
- Created wiki/domain/scoring-dimensions.md

## [2026-04-22] ingest | Discovery Channels and Strategies
- Ingested from Foundation Blueprint §6 (Layer A) and Roadmap Phase 2
- Created wiki/domain/discovery-channels.md

## [2026-04-22] ingest | Screening Gates Detail
- Ingested from Foundation Blueprint §16.2-16.5 and Roadmap Phase 3
- Created wiki/domain/screening-gates.md

## [2026-04-22] ingest | Competitive Landscape and Gap Analysis
- Ingested from Foundation Blueprint §4, §5 and Findings
- Created wiki/domain/competitive-landscape.md

## [2026-04-22] ingest | Domain Strategy and Repository Taxonomy
- Ingested from Foundation Blueprint §10 and Roadmap Phase 5
- Created wiki/domain/domain-strategy.md

## [2026-04-22] ingest | Session Workflow and Progressive Deepening
- Ingested from Foundation Blueprint §21.4-21.6 and Roadmap Phase 7
- Created wiki/patterns/session-workflow.md

## [2026-04-22] ingest | Agent Workflow Patterns
- Ingested from Foundation Blueprint §21.7, §17 and Roadmap Phase 7-9
- Created wiki/patterns/agent-workflows.md

## [2026-04-22] ingest | Technology Stack Decisions
- Ingested from Foundation Blueprint §9, §16 and Roadmap §7
- Created wiki/patterns/tech-stack.md

## [2026-04-22] ingest | Operational Rules and Workflow Standards
- Ingested from Foundation Blueprint §17 and Roadmap §8
- Created wiki/patterns/operational-rules.md

## [2026-04-22] ingest | Wiki Index populated
- Updated wiki/index.md with all 14 articles across 4 topic directories

## [2026-04-22] ingest | Phase 0 Implementation Decisions
- Ingested from Context7-verified research and Phase 0 implementation plan
- Created wiki/patterns/phase0-implementation.md
- Covers: pyproject.toml, config architecture, exception hierarchy, session models, MCP spec models, logging, ruff/mypy/pytest

## [2026-04-22] ingest | Python Development Tooling Configuration
- Ingested from Context7 verification of pydantic-settings, structlog, ruff, pytest, pre-commit
- Created wiki/patterns/dev-tooling-and-ci.md
- Covers: SettingsConfigDict patterns, structlog stdlib integration, ruff rule selection rationale, pytest src layout, pre-commit config

## [2026-04-22] ingest | MCP Python SDK Verification
- Ingested from Context7 verification of /modelcontextprotocol/python-sdk v1.x
- Created wiki/apis/mcp-sdk-verification.md
- Covers: FastMCP setup, tool definition with Context, progress notifications (report_progress not deprecated progress()), transport configuration, elicitation

## [2026-04-22] lint | Initial wiki health check
- 14 articles created across 4 directories (architecture, apis, domain, patterns)
- 3 issues found: broken raw links to findings.md (wrong relative path `../../../findings.md` → fixed to `../../../../findings.md`)
- 3 auto-fixed
- All internal cross-references verified (15 cross-links between articles)
- All raw source references verified (pointing to project files in docs/foundation/, docs/roadmaps/, findings.md)

## [2026-04-22] ingest | Phase 0 Implementation Completed
- All 11 tasks from phase0-implementation-plan.md implemented and verified
- Key implementation decisions during coding:
  - StrEnum (Python 3.12+) used instead of (str, Enum) per ruff UP042 rule
  - `datetime.UTC` used instead of `timezone.utc` per ruff UP017 rule
  - Domain exception `__init__` methods got explicit docstrings to satisfy D107
  - `from __future__ import annotations` required in all files per ruff isort config
  - `structlog.get_logger()` return type needs explicit cast for mypy strict
  - pyproject.toml `ignore_missing_imports` overridemodule list includes `mcp.*`, `respx.*`, `typer.*`
- All acceptance criteria verified:
  - `pip install -e ".[dev]"` works ✓
  - `python -c "import github_discovery"` works ✓
  - `make lint && make format-check && make typecheck && make test` all pass ✓
  - `make ci` passes (ruff + mypy --strict + 46 tests) ✓
  - Settings(), logging, exceptions, session models, MCP specs all verified ✓
  - `.kilo/mcp.json` and `.kilo/mcp.json.template` are valid JSON ✓
- Context7 verification confirmed before implementation:
  - Pydantic BaseSettings/SettingsConfigDict patterns ✓
  - pydantic-settings nested delimiter support ✓
  - structlog stdlib ProcessorFormatter integration ✓
  - MCP FastMCP tool/resource/prompt decorators ✓
  - pytest import-mode=importlib for src layout ✓

## [2026-04-22] ingest | Phase 1 Data Models Implementation Decisions
- Ingested from Context7-verified Pydantic v2 patterns and Phase 1 implementation plan
- Created wiki/patterns/phase1-models-implementation.md
- Covers: ScoreDimension realignment (COMMUNITY→FUNCTIONALITY, NOVELTY→INNOVATION), SubScore base pattern, RepoCandidate design, ValueScore computed_field, DomainProfile predefined weights, Feature Store SHA dedup, MCPToolResult context-efficient output, 7 new model files planned
- Updated wiki/index.md with new article entry
- Cross-referenced from phase0-implementation.md

## [2026-04-22] ingest | Phase 1 Data Models Implementation Complete
- Updated wiki/patterns/phase1-models-implementation.md with actual implementation results
- All 9 model files written: enums, candidate, screening, assessment, scoring, features, api, agent, __init__
- 113 new unit tests (140 total including Phase 0) — all passing
- `make ci` green: ruff + mypy --strict + pytest
- Key issues resolved: computed_field mypy prop-decorator, TestFootprintScore pytest collection, model_validate for constraints, Makefile venv python
- Updated wiki/index.md with completion status

## [2026-04-22] ingest | Phase 0+1 Gap Analysis and Fixes
- Compared actual implementation against Roadmap Phase 0 (tasks 0.1-0.11) and Phase 1 (tasks 1.1-1.9)
- Context7 verification of Pydantic, pydantic-settings, structlog, MCP Python SDK before analysis
- Issues found and fixed:
  - CRITICAL: Missing __main__.py — `python -m github_discovery` was broken. Created entry point.
  - MEDIUM: Stale ruff ignores (ANN101, ANN102 removed in ruff 0.8+). Removed from pyproject.toml.
  - MEDIUM: Missing 'backend' DomainType from Blueprint §10. Added to enums.py + BACKEND_PROFILE in scoring.py.
  - MEDIUM: mypy unused overrides warning. Removed `[[tool.mypy.overrides]]` for mcp/respx (now have py.typed).
  - LOW: mcp/config.py was an empty stub duplicating config.py:MCPSettings. Added clarifying docstring.
- After fixes: `make ci` green — 0 lint errors, 0 typecheck errors, 142 tests passed (2 new)
- Verified: `python -m github_discovery` and `python -m github_discovery --help` work correctly

## [2026-04-22] ingest | Phase 2 Discovery Engine Implementation Plan
- Created docs/plans/phase2-implementation-plan.md
- Context7 verification of httpx, pytest-httpx, GitHub REST API, GitHub GraphQL API before planning
- Covers 10 tasks: REST client, GraphQL client, 6 discovery channels, orchestrator, pool manager
- Key patterns verified: AsyncClient auth/retry/event hooks, cursor-based GraphQL pagination, REST Link header pagination, search/code search rate limits, pytest-httpx mocking
- New dependency needed: aiosqlite>=0.20 for SQLite pool persistence
- ~79 unit tests planned across 10 test files
- Updated wiki/index.md with new plan reference

## [2026-04-22] ingest | Phase 2 Discovery Engine Implementation Complete
- All 10 tasks (2.1–2.10) implemented and verified
- 320 tests passing (149 new discovery tests + 171 pre-existing), `make ci` green
- 45 source files pass mypy --strict, 77 files pass ruff check/format
- Key modules created:
  - Infrastructure: github_client.py (16 tests), graphql_client.py (13 tests), pool.py (13 tests)
  - Channels: search_channel.py (11), curated_channel.py (17), code_search_channel.py (13), registry_channel.py (30), dependency_channel.py (25), seed_expansion.py (25)
  - Integration: orchestrator.py (15 tests), types.py, __init__.py exports
- Key decisions documented:
  - _BearerAuth uses Generator not Iterator for httpx.Auth compatibility
  - HTTP status codes as named constants (PLR2004 compliance)
  - contextlib.suppress replaces try/except/pass (SIM105)
  - Pydantic models need runtime imports (# noqa: TC001, not TYPE_CHECKING)
  - CandidatePool.total_count is @property, not constructor param
  - DiscoveryChannel.AWESOME_LIST (not CURATED) is the enum for curated channel
  - SeedExpansion.expand() takes seed_urls, not DiscoveryQuery — orchestrator special-cases
  - Discovery scoring: base + breadth bonus + channel quality bonuses, capped at 1.0
- Updated wiki/patterns/phase2-discovery-plan.md with complete implementation record
- Updated wiki/index.md with completion status

## [2026-04-22] ingest | Phase 3 Screening Implementation Plan
- Created docs/plans/phase3-implementation-plan.md
- Context7 verification of PyDriller, Pydantic v2, aiosqlite, asyncio subprocess, structlog before planning
- Covers 14 tasks: Gate 1 engine + 7 sub-score checkers, Gate 2 engine + 4 external tool integrations, orchestrator + policy engine
- Key patterns verified:
  - PyDriller: Repository.traverse_commits(), CodeChurn, ContributorsCount, ContributorsExperience, complexity via Lizard
  - asyncio.create_subprocess_exec with PIPE and communicate() for gitleaks/scc subprocess integration
  - aiosqlite async context manager patterns for screening result persistence
  - OSV API POST query pattern for dependency vulnerability scanning
  - OpenSSF Scorecard API GET pattern for security posture assessment
- New dependency needed: pydriller>=2.6 for Git repository mining
- External tools required (CLI): gitleaks, scc — with graceful degradation if not installed
- ~116 unit tests planned across 15 test files
- Updated wiki/index.md with plan reference

## [2026-04-23] ingest | Phase 3 Screening Implementation Complete
- All 14 tasks (3.1–3.14) from phase3-implementation-plan.md implemented and verified
- 459 tests passing (139 new screening tests + 320 pre-existing), `make ci` green
- 61 source files pass mypy --strict, 111 files pass ruff check/format
- 16 screening modules implemented:
  - Infrastructure: types.py, subprocess_runner.py
  - Gate 1 (7 checkers): hygiene.py, ci_cd.py, test_footprint.py, release_discipline.py, dependency_quality.py, practices.py, maintenance.py
  - Gate 1 engine: gate1_metadata.py
  - Gate 2 (4 adapters): scorecard_adapter.py, osv_adapter.py, secrets_check.py, complexity.py
  - Gate 2 engine: gate2_static.py
  - Policy Engine: orchestrator.py
- Key decisions:
  - SubprocessRunner for async subprocess with graceful degradation
  - PyDriller deferred — API-based heuristics (confidence=0.7) by default
  - OSV adapter returns neutral scores (confidence=0.0) — lockfile parsing deferred
  - TypeVar("_SubScoreT", bound=SubScore) for type-safe sub-score collection
  - Domain-specific thresholds in orchestrator (SECURITY → stricter Gate 2)
- Created wiki/patterns/phase3-screening-implementation.md
- Updated wiki/index.md with completion entry

## [2026-04-23] ingest | Phase 4 Deep Assessment Implementation Plan
- Created docs/plans/phase4-implementation-plan.md
- Context7 verification of python-repomix, instructor, litellm before planning
- External documentation verified: NanoGPT API docs (https://docs.nano-gpt.com/introduction, https://docs.nano-gpt.com/api-reference/endpoint/chat-completion)
- Key architecture decisions:
  - LLM Provider: NanoGPT (OpenAI-compatible) with subscription endpoint
  - SDK: openai + instructor for structured output with Pydantic validation + retry
  - litellm scartato: NanoGPT already handles multi-provider routing
  - Codebase packing: python-repomix (programmatic, not CLI)
  - Structured output: response_format json_schema mapping to Pydantic models
- Covers 8 tasks: Repomix adapter, LLM provider, prompts (8 dimensions), result parser, heuristics, lang analyzers, budget controller, orchestrator
- New dependencies: python-repomix>=0.1.0, openai>=1.30, instructor>=1.4
- ~65 unit tests + 3 integration tests planned
- Created wiki/patterns/phase4-assessment-implementation.md
- Updated wiki/index.md with new article

## [2026-04-23] ingest | Phase 3 Verification and Bug Fixes
- Systematic verification of Phase 3 screening against blueprint §16.2-16.5 and roadmap tasks 3.1-3.14
- 7 bugs/gaps found and fixed:
  - CRITICAL: Shallow clone management added to gate2_static.py (git clone --depth=1 + cleanup)
  - CRITICAL: SubprocessRunner wired into SecretsChecker and ComplexityAnalyzer
  - HIGH: OSV adapter rewritten from stub to actual API integration (httpx, severity scoring)
  - HIGH: hard_gate_enforcement setting now honored in Gate2StaticScreener.screen()
  - HIGH: GateLevel comparison uses int() conversion instead of string comparison
  - MEDIUM: All 12 DomainType values now have domain-specific thresholds (was 6 of 12)
  - MEDIUM: Resource cleanup added (close() methods for Gate2 and ScorecardAdapter)
- Test updates:
  - test_gate2_static.py: 9 new tests (clone management, hard_gate toggle, cleanup, close)
  - test_osv_adapter.py: Rewritten with 16 properly mocked tests (no real API calls)
  - test_orchestrator.py: Added parametrized TestAllDomainThresholds (22 test cases)
- 500 total tests pass, `make ci` green: ruff + mypy --strict + pytest
- Updated wiki/patterns/phase3-screening-implementation.md with verification findings
- Updated wiki/index.md with revised Phase 3 entry

## [2026-04-23] ingest | Phase 4 Deep Assessment Implementation Complete
- All 13 implementation tasks completed and verified
- 700 tests passing (200 new assessment tests + 500 pre-existing), `make ci` green
- ruff check ✅ | ruff format ✅ | mypy --strict ✅ | pytest 700/700 ✅
- 77 source files pass mypy --strict, all pass ruff check/format
- Source modules created (17 files):
  - types.py: RepoContent, HeuristicScores, AssessmentContext, LLMDimensionOutput, LLMBatchOutput
  - repomix_adapter.py: Repo packing via repomix RepoProcessor (async via asyncio.to_thread)
  - llm_provider.py: NanoGPT provider with instructor.from_openai(AsyncOpenAI(...))
  - budget_controller.py: Per-repo + per-day token budget enforcement
  - heuristics.py: 7 detection methods + additive structure scoring
  - result_parser.py: Batch/per-dimension parsing + heuristic fallback
  - orchestrator.py: Full Gate 3 pipeline + hard gate enforcement + caching
  - prompts/: 8 dimension prompt templates + DIMENSION_PROMPTS registry
  - __init__.py: 11 public API exports
- Test files created (9 files):
  - conftest.py (8 fixtures), test_types.py (35), test_heuristics.py (38), test_budget_controller.py (25)
  - test_result_parser.py (34), test_repomix_adapter.py (15), test_llm_provider.py (18), test_orchestrator.py (24)
- Bugs fixed during verification:
  - repomix PyPI package name: `repomix` (not `python-repomix`)
  - RepoProcessor API: config in constructor, not process()
  - BudgetController.record_usage: added full_name parameter (was using model_used as repo key)
- Context7 verification before implementation:
  - repomix: RepoProcessor(repo_url, config=config), process(write_output=False), RepomixConfig compression
  - instructor: instructor.from_openai(AsyncOpenAI(...)), response_model=PydanticModel, max_retries
  - openai: AsyncOpenAI(base_url=..., api_key=...), structured output
  - pydantic: BaseModel, computed_field, model_json_schema(), field_validator
- Updated wiki/patterns/phase4-assessment-implementation.md with complete implementation record
- Updated wiki/index.md with completion status