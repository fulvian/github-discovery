---
Title: Phase 4 Deep Assessment Implementation
Topic: patterns
Sources: Roadmap Phase 4; Blueprint §6 (Layer C), §16.5; Context7 verification of python-repomix, instructor, litellm; NanoGPT API docs
Raw: [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md); [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); https://docs.nano-gpt.com/introduction; https://docs.nano-gpt.com/api-reference/endpoint/chat-completion
Updated: 2026-04-23
Confidence: high
---

# Phase 4 Deep Assessment Implementation

Phase 4 implements Gate 3 (Deep Technical Assessment) — the expensive LLM-based evaluation layer. Only top 10-15% candidates from Gate 1+2 are assessed.

## Key Architecture Decisions

### LLM Provider: NanoGPT with instructor + openai SDK

- **Provider**: NanoGPT (https://nano-gpt.com) — OpenAI-compatible API aggregating OpenAI, Anthropic, Gemini, open-source models
- **Subscription endpoint**: `https://nano-gpt.com/api/subscription/v1/chat/completions` (user has subscription)
- **SDK stack**: `openai` SDK (with custom `base_url`) + `instructor` for structured output with Pydantic validation + automatic retry
- **Why not litellm**: NanoGPT already handles multi-provider routing; litellm would be redundant overhead
- **Structured output**: `response_format` with `json_schema` — maps directly to Pydantic models

### Codebase Packing: python-repomix

- **Library**: `python-repomix` (not the Node.js CLI) for programmatic repo packing
- **Key features**: `RepoProcessor(repo_url=url).process()`, token counting, interface-mode compression (signatures + docstrings only)
- **Large repo handling**: Interface compression → truncation → early-stop

### Budget Control (Hard Rules)

- Per-repo limit: `max_tokens_per_repo` (default 50k tokens)
- Per-day limit: `max_tokens_per_day` (default 500k tokens)
- Caching: mandatory by `full_name + commit_sha` in Feature Store
- All limits enforced as hard constraints — no override possible

## Assessment Flow

```
Hard Gate Check → Cache Check → Budget Check → Repomix Pack →
Heuristic Scoring → LLM Assessment → Result Composition → Cache Store
```

- LLM assessment can be batch (all dimensions in one call) or per-dimension
- Heuristic scoring provides baseline and fallback when LLM fails
- Result parser handles partial/failed dimensions gracefully

## Dependencies Added

| Package | Purpose |
|---------|---------|
| `python-repomix>=0.1.0` | Programmatic repo packing |
| `openai>=1.30` | OpenAI SDK used with NanoGPT custom base_url |
| `instructor>=1.4` | Structured output with Pydantic validation + retry |

## 8 Assessment Dimensions

Each dimension has a dedicated prompt template in `assessment/prompts/`:

1. Code Quality — style, complexity, error handling, naming
2. Architecture — modularity, coupling, abstraction layers
3. Testing — presence, coverage, quality, CI integration
4. Documentation — README, API docs, guides, onboarding
5. Maintenance — commit cadence, releases, issue management
6. Security — dependency pinning, vulnerability management
7. Functionality — feature completeness, use-case fit
8. Innovation — novelty, uniqueness, differentiation

## Module Structure

```
assessment/
├── repomix_adapter.py       # Repo packing
├── llm_provider.py          # NanoGPT provider abstraction
├── result_parser.py         # LLM response → DeepAssessmentResult
├── heuristics.py            # Non-LLM code structure scoring
├── budget_controller.py     # Token budget enforcement
├── orchestrator.py          # Full pipeline coordination
├── prompts/                 # 8 dimension prompt templates
└── lang_analyzers/          # Language-specific (Python/ruff initially)
```

## See Also

- [Tiered Pipeline](../architecture/tiered-pipeline.md)
- [Scoring Dimensions](../domain/scoring-dimensions.md)
- [Screening Gates](../domain/screening-gates.md)
- [Tech Stack](tech-stack.md)
- [Phase 3 Implementation](phase3-screening-implementation.md)
