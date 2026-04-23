---
Title: Phase 4 Deep Assessment Implementation
Topic: patterns
Sources: Roadmap Phase 4; Blueprint §6 (Layer C), §16.5; Context7 verification of repomix, instructor, openai; NanoGPT API docs
Raw: [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md); [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); https://docs.nano-gpt.com/introduction; https://docs.nano-gpt.com/api-reference/endpoint/chat-completion
Updated: 2026-04-23
Confidence: high
---

# Phase 4 Deep Assessment Implementation

Phase 4 implements Gate 3 (Deep Technical Assessment) — the expensive LLM-based evaluation layer.
Only top 10-15% candidates from Gate 1+2 are assessed.

**Status: COMPLETE + VERIFIED** — `make ci` green: ruff + ruff format + mypy --strict + pytest.
863 total project tests pass (230 assessment tests).

## Key Architecture Decisions

### LLM Provider: NanoGPT with instructor + openai SDK

- **Provider**: NanoGPT (https://nano-gpt.com) — OpenAI-compatible API aggregating OpenAI, Anthropic, Gemini, open-source models
- **Subscription endpoint**: `https://nano-gpt.com/api/subscription/v1` (user has subscription)
- **SDK stack**: `openai` AsyncOpenAI SDK (with custom `base_url`) + `instructor.from_openai()` for structured output with Pydantic validation + automatic retry
- **Why not litellm**: NanoGPT already handles multi-provider routing; litellm would be redundant overhead
- **Structured output**: `instructor` with `response_model=PydanticModel` — maps directly to Pydantic models

### Codebase Packing: repomix (PyPI package)

- **PyPI package**: `repomix` (NOT `python-repomix` — that package doesn't exist on PyPI)
- **Import**: `from repomix import RepoProcessor, RepomixConfig`
- **Constructor**: `RepoProcessor(repo_url=url, config=config)` — config passed at construction, not process()
- **Process**: `processor.process(write_output=False)` — returns `RepoProcessorResult` with `.output_content`, `.total_files`, `.total_tokens`, `.total_chars`
- **Compression**: `config.compression.enabled=True`, `.keep_interfaces=True` for signatures + docstrings only
- **Token counting**: `config.output.calculate_tokens=True`, encoding `o200k_base`
- **Large repo handling**: Interface compression → character-based truncation (~4 chars/token) → early-stop
- **Async**: `asyncio.to_thread()` wrapper since `process()` is synchronous

### Budget Control (Hard Rules)

- Per-repo limit: `max_tokens_per_repo` (default 50k tokens)
- Per-day limit: `max_tokens_per_day` (default 500k tokens)
- Caching: mandatory by `full_name + commit_sha` in orchestrator's `_cache` dict
- All limits enforced as hard constraints — `BudgetExceededError` raised, no override possible
- Daily auto-reset via date key comparison in `_today_key()`

## Assessment Flow

```
Hard Gate Check → Cache Check → Budget Check → Repomix Pack →
Heuristic Scoring → LLM Assessment → Result Composition → Budget Record → Cache Store
```

- LLM assessment can be batch (all dimensions in one call) or per-dimension
- Heuristic scoring provides baseline and fallback when LLM fails
- Result parser handles partial/failed dimensions gracefully (fills with heuristic scores)
- Hard gate enforcement: `HardGateViolationError` raised if Gate 1+2 not passed

## Dependencies Added

| Package | PyPI Name | Purpose |
|---------|-----------|---------|
| repomix | `repomix>=0.1.0` | Programmatic repo packing |
| openai | `openai>=1.30` | AsyncOpenAI SDK with NanoGPT custom base_url |
| instructor | `instructor>=1.4` | Structured output with Pydantic validation + retry |

## 8 Assessment Dimensions

Each dimension has a dedicated prompt template in `assessment/prompts/`:

1. Code Quality (`code_quality.py`) — style, complexity, error handling, naming
2. Architecture (`architecture.py`) — modularity, coupling, abstraction layers
3. Testing (`testing.py`) — presence, coverage, quality, CI integration
4. Documentation (`documentation.py`) — README, API docs, guides, onboarding
5. Maintenance (`maintenance.py`) — CI/CD, release discipline, contributor docs
6. Security (`security.py`) — dependency pinning, secret handling, input validation
7. Functionality (`functionality.py`) — feature completeness, use-case coverage
8. Innovation (`innovation.py`) — novelty, uniqueness, differentiation

Each prompt includes evaluation criteria, scoring guidelines (0.0-1.0 in 4 tiers), and output format requirements.

## Module Structure

```
assessment/
├── __init__.py               # Public API exports (11 classes)
├── types.py                  # RepoContent, HeuristicScores, AssessmentContext, LLMDimensionOutput, LLMBatchOutput
├── repomix_adapter.py        # Repo packing via repomix RepoProcessor
├── llm_provider.py           # NanoGPT provider (instructor + AsyncOpenAI)
├── result_parser.py          # LLM response → DeepAssessmentResult + heuristic fallback
├── heuristics.py             # Non-LLM code structure scoring (7 detection methods)
├── budget_controller.py      # Token budget enforcement (per-repo + per-day)
├── orchestrator.py           # Full pipeline coordination + hard gate check
└── prompts/                  # 8 dimension prompt templates + DIMENSION_PROMPTS registry
    ├── __init__.py           # get_prompt(), DIMENSION_PROMPTS dict
    ├── code_quality.py
    ├── architecture.py
    ├── testing.py
    ├── documentation.py
    ├── maintenance.py
    ├── security.py
    ├── functionality.py
    └── innovation.py
```

## Configuration (AssessmentSettings)

| Setting | Env Var | Default | Description |
|---------|---------|---------|-------------|
| `nanogpt_api_key` | `GHDISC_ASSESSMENT_NANOGPT_API_KEY` | `""` | NanoGPT API key |
| `nanogpt_base_url` | `GHDISC_ASSESSMENT_NANOGPT_BASE_URL` | `https://nano-gpt.com/api/subscription/v1` | NanoGPT API base URL |
| `llm_model` | `GHDISC_ASSESSMENT_LLM_MODEL` | `gpt-4o` | Model identifier |
| `llm_temperature` | `GHDISC_ASSESSMENT_LLM_TEMPERATURE` | `0.1` | Sampling temperature |
| `llm_max_retries` | `GHDISC_ASSESSMENT_LLM_MAX_RETRIES` | `3` | Max retries via instructor |
| `max_tokens_per_repo` | `GHDISC_ASSESSMENT_MAX_TOKENS_PER_REPO` | `50000` | Per-repo token budget |
| `max_tokens_per_day` | `GHDISC_ASSESSMENT_MAX_TOKENS_PER_DAY` | `500000` | Per-day token budget |
| `repomix_max_tokens` | `GHDISC_ASSESSMENT_REPOMIX_MAX_TOKENS` | `40000` | Max tokens for packed content |
| `repomix_compression` | `GHDISC_ASSESSMENT_REPOMIX_COMPRESSION` | `True` | Interface-mode compression |
| `gate3_threshold` | `GHDISC_ASSESSMENT_GATE3_THRESHOLD` | `0.6` | Gate 3 pass threshold |
| `cache_ttl_hours` | `GHDISC_ASSESSMENT_CACHE_TTL_HOURS` | `24` | Cache TTL in hours |

## Test Coverage

- 230 unit tests across 11 test files (including lang_analyzers/ and test_prompts/)
- `conftest.py` with 8 shared fixtures
- All modules tested with mocked external dependencies (repomix, instructor)
- Hard gate enforcement tested (5 scenarios)
- Budget controller tested (25 tests: per-repo, daily, cumulative, auto-reset)
- Heuristic analyzer tested (38 tests: all 7 detection methods + scoring + categorization)
- Result parser tested (34 tests: batch, per-dimension, fallback, name parsing, quality computation)
- Orchestrator tested (27 tests: full pipeline, cache, cache TTL, quick_assess, hard gate)
- Prompt templates tested (26 tests: registry, content structure, domain focus adjustments)
- Language analyzers tested (15 tests: base ABC, python ruff subprocess)

## Bugs Fixed During Verification

1. **repomix API mismatch**: `RepoProcessor(repo_url)` then `process(config)` is wrong — config must be passed to constructor: `RepoProcessor(repo_url, config=config)`. Fixed with `asyncio.to_thread()` positional arg for `write_output=False`.
2. **BudgetController.record_usage**: Originally used `token_usage.model_used` as repo identifier (wrong). Fixed to accept `full_name` as keyword argument.
3. **PyPI package name**: `python-repomix` doesn't exist on PyPI; the correct package is `repomix`. Fixed in pyproject.toml.

## Post-Implementation Verification (2026-04-23)

Deep analysis of all assessment modules against blueprint §6 (Layer C), §16.5 and phase4 plan. 25+ issues identified across Phase 4+5. Phase 4 fixes:

1. **repomix_adapter.py — timeout inflation (HIGH)**: Added `timeout_seconds=120` with `asyncio.wait_for()` to prevent indefinite hangs. Fixed `total_tokens` inflation after truncation — now uses char-based estimate (`total_chars // 4`) instead of counting tokens from removed content.
2. **orchestrator.py — pre-pack budget check (HIGH)**: Added budget check BEFORE repomix call to avoid wasting resources on repos that will exceed budget. Fixed `gate_passed` derivation in `_check_hard_gate` error — was always 0, now correctly derives from screening result.
3. **llm_provider.py — fallback model retry (HIGH)**: Added `fallback_model` support — if primary model fails, retry with fallback model. Safe `close()` with try/except to prevent double-close errors.
4. **config.py — missing settings**: Added `llm_fallback_model`, `llm_subscription_mode`, and `effective_base_url` property to `AssessmentSettings`.
5. **lang_analyzers/ module created (Task 4.6 — was 0%)**: New module with `base.py` (ABC for language-specific analyzers) and `python_analyzer.py` (ruff subprocess integration) + 15 tests.
6. **Cache TTL enforcement (Issue #1)**: `_cache` changed from `dict[str, DeepAssessmentResult]` to `dict[str, tuple[DeepAssessmentResult, float]]` with `time.monotonic()` timestamps. On read, expired entries are evicted. `_cache_ttl_seconds` initialized from `AssessmentSettings.cache_ttl_hours`.
7. **Domain-specific prompt adjustments (Issue #3)**: `get_prompt()` now accepts optional `domain: DomainType` parameter. Added `_DOMAIN_FOCUS` registry with 10 domain+dimension pairs (CLI, ML_LIB, SECURITY_TOOL, DEVOPS_TOOL, LANG_TOOL, DATA_TOOL) that append focus notes to prompts.
8. **Prompt test coverage (Issue #2)**: Created `tests/unit/assessment/test_prompts/` with 26 tests across 4 test classes — verifying all 8 prompts contain required structural elements and domain focus works correctly.

## Context7 Verification Summary

| Library | Library ID | Key API Verified |
|---------|-----------|-----------------|
| repomix | `/andersonby/python-repomix` | `RepoProcessor(repo_url, config)`, `process(write_output=False)`, `RepomixConfig` compression + token counting |
| instructor | `/websites/python_useinstructor` | `instructor.from_openai(AsyncOpenAI(...))`, `response_model=PydanticModel`, `max_retries` |
| openai | `/openai/openai-python` | `AsyncOpenAI(base_url=..., api_key=...)`, structured output via response_model |
| pydantic | `/websites/pydantic_dev_validation` | `BaseModel`, `computed_field`, `model_json_schema()`, `field_validator` |

## See Also

- [Tiered Pipeline](../architecture/tiered-pipeline.md)
- [Scoring Dimensions](../domain/scoring-dimensions.md)
- [Screening Gates](../domain/screening-gates.md)
- [Tech Stack](tech-stack.md)
- [Phase 3 Implementation](phase3-screening-implementation.md)
