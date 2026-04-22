---
Title: Phase 1 Data Models Implementation Decisions
Topic: patterns
Sources: Context7 verification (Pydantic v2 computed_field, model_validator, JSON schema); Roadmap Phase 1; Blueprint §7, §16, §21
Raw: [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md); [phase1-plan.md](../../plans/phase1-implementation-plan.md)
Updated: 2026-04-22
Confidence: high
---

# Phase 1 Data Models Implementation Decisions

Detailed implementation decisions for Phase 1 (Data Models & Type System), verified against official documentation via Context7. Phase 1 is COMPLETE — all models implemented, all tests passing, `make ci` green.

## Key Points

- **ScoreDimension realignment**: `COMMUNITY` → `FUNCTIONALITY`, `NOVELTY` → `INNOVATION` to match Blueprint §7 exactly (8 dimensions)
- **CandidateStatus enum**: New enum tracking pipeline progression (discovered → screened → assessed → ranked)
- **SubScore base pattern**: All 11 gate sub-scores share a common `SubScore` base with `value`, `weight`, `details`, `confidence`, `notes`
- **RepoCandidate**: Central model with ~30 fields from GitHub API, stars explicitly marked as "CONTEXT ONLY"
- **ValueScore as `computed_field`**: Uses Pydantic v2 `@computed_field` for automatic computation from `quality_score / log10(stars + 10)`
- **Dict[ScoreDimension, DimensionScore]**: Assessment results use enum-keyed dicts for type-safe dimension access
- **Feature Store with SHA dedup**: `RepoFeatures` keyed by `full_name + commit_sha` with TTL expiry
- **MCPToolResult**: Context-efficient output model (< 2000 tokens default) with summary + references + confidence

## Implementation Results

### CI Verification (2026-04-22)

- `ruff check src/ tests/` — All checks passed
- `ruff format --check src/ tests/` — 54 files already formatted
- `mypy src/ --strict` — Success: no issues found in 33 source files
- `pytest tests/ -v` — **140 passed** in 0.13s (113 unit model tests + 27 pre-existing)

### Model Files Implemented

| File | Models | Lines | Tests |
|------|--------|-------|-------|
| `models/enums.py` | `ScoreDimension` (updated), `CandidateStatus` (new) | ~80 | 13 (test_enums.py) |
| `models/candidate.py` | `RepoCandidate`, `CandidatePool` | ~265 | 12 (test_candidate.py) |
| `models/screening.py` | `SubScore`, 7 Gate1, `MetadataScreenResult`, 4 Gate2, `StaticScreenResult`, `ScreeningResult` | ~340 | 13 (test_screening.py) |
| `models/assessment.py` | `DimensionScore`, `TokenUsage`, `DeepAssessmentResult` | ~130 | 9 (test_assessment.py) |
| `models/scoring.py` | `DomainProfile`, `ScoreResult`, `RankedRepo`, `ExplainabilityReport`, 4 profiles | ~315 | 13 (test_scoring.py) |
| `models/features.py` | `FeatureStoreKey`, `RepoFeatures` | ~140 | 8 (test_features.py) |
| `models/api.py` | `PaginationParams`, `PaginatedResponse`, 4 request/response pairs, `ExportFormat` | ~250 | 9 (test_api.py) |
| `models/agent.py` | `MCPToolResult`, `DiscoverySession` | ~190 | 9 (test_agent.py) |
| `models/__init__.py` | All Phase 1 exports + Phase 0 re-exports | ~170 | — |

### Issues Found and Resolved During Implementation

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| `@computed_field` + `@property` mypy `prop-decorator` error | mypy doesn't support decorators stacked on `@property` | Added `# type: ignore[prop-decorator]` on `@computed_field` lines |
| `TestFootprintScore` collected by pytest | Model name starts with `Test`, matches `python_classes = ["Test*"]` | Aliased import as `FootprintScore` in test file |
| `model_copy(update=...)` bypasses Pydantic validation | `model_copy` creates without full re-validation | Changed test helper to use `model_validate(merged_dict)` |
| `SubScore.weight` has `le=1.0`, test passed `2.0` | Test assumed no upper bound on weight | Fixed test to use `0.5` |
| Ruff TC001 for Pydantic model imports | Pydantic v2 needs types at runtime for validation | Added `# noqa: TC001` (can't move to TYPE_CHECKING) |
| Ruff PLR2004 magic values (365, 0.01) | Numeric literals in comparisons | Extracted `_ACTIVE_THRESHOLD_DAYS = 365` and `_WEIGHT_TOLERANCE = 0.01` |
| Ruff E501 long description strings | Several Field descriptions exceeded 99 chars | Wrapped multi-line with string concatenation |
| Ruff RUF022 unsorted `__all__` | Section comments prevented alphabetical sorting | Auto-fixed with `ruff --fix --unsafe-fixes` |
| Ruff B017 `pytest.raises(Exception)` | Catching base `Exception` is too broad | Added `# noqa: B017` (acceptable for validation error tests) |
| Makefile bare commands not in PATH | `mypy`, `ruff`, `pytest` not in system PATH | Updated Makefile to use `$(PYTHON) -m` with `PYTHON ?= .venv/bin/python` |

### Key Pydantic v2 Patterns Used

1. **`@computed_field` for derived values**: `value_score` in `ScoreResult`, `value_score`/`quality_score`/`stars` in `RankedRepo`
2. **`Field(ge=0.0, le=1.0)` constraints**: All score fields use Pydantic built-in validators
3. **`model_validate()` for dict→model**: `RepoCandidate.model_validate(gh_dict)` for GitHub API responses
4. **`model_dump_json()` / `model_validate_json()`**: JSON round-trip tested on all models
5. **`default_factory` for mutable defaults**: `list`, `dict` fields use `default_factory=list/dict`
6. **StrEnum for all enumerations**: Python 3.12+ `StrEnum` for JSON-serializable enum values

## Details

### ScoreDimension Alignment

Blueprint §7 defines exactly 8 evaluation dimensions. Phase 0 had a mismatch:

| Phase 0 Enum | Blueprint §7 | Fix |
|-------------|-------------|-----|
| `CODE_QUALITY` | Code Quality | ✓ No change |
| `ARCHITECTURE` | Architecture & Modularity | ✓ No change |
| `TESTING` | Testability & Verification | ✓ No change |
| `DOCUMENTATION` | Documentation & DX | ✓ No change |
| `SECURITY` | Security & Supply Chain | ✓ No change |
| `MAINTENANCE` | Maintenance & Operations | ✓ No change |
| `COMMUNITY` | Functional Completeness | ✗ → `FUNCTIONALITY` |
| `NOVELTY` | Innovation & Distinctiveness | ✗ → `INNOVATION` |

### SubScore Pattern

All gate sub-scores (7 Gate 1 + 4 Gate 2 = 11 total) share the same base structure:

```python
class SubScore(BaseModel):
    value: float = Field(ge=0.0, le=1.0)  # Score range
    weight: float = Field(gt=0.0, le=1.0)  # Composite weight
    details: dict[str, object]              # What was checked
    confidence: float = Field(ge=0.0, le=1.0)  # Data quality
    notes: list[str]                        # Human-readable
```

Each sub-score type adds typed `details` documentation for its specific checks.

### RepoCandidate Design

- ~30 fields from GitHub REST API `/repos/{owner}/{repo}` endpoint
- Stars field explicitly documented as "CONTEXT ONLY — never primary signal"
- `domain: DomainType` for intra-domain ranking (default `OTHER`)
- `commit_sha` for Feature Store dedup
- `status: CandidateStatus` for pipeline state tracking
- Properties (not serialized): `owner_name`, `repo_name`, `is_archived_or_disabled`, `is_active`

### ValueScore Implementation

Uses Pydantic v2 `@computed_field` decorator (verified via Context7):

```python
@computed_field  # type: ignore[prop-decorator]
@property
def value_score(self) -> float:
    return self.quality_score / log10(self.stars + 10)
```

Key behaviors:
- Zero quality → zero value score (avoid division by zero)
- Low stars + high quality → high value (hidden gems)
- High stars + high quality → moderate value (popular but not underrated)

### Domain Profiles

Predefined weight profiles for domain-specific scoring:
- `LIBRARY_PROFILE`: balanced, docs 15%
- `CLI_PROFILE`: testing 20%, maintenance 20%
- `DEVOPS_PROFILE`: testing 20%, security 15%
- `DEFAULT_PROFILE`: Blueprint §7 default weights

All profiles validated: dimension weights sum to 1.0.

### Feature Store Contract

- Key: `FeatureStoreKey(full_name, commit_sha)` — composite key for dedup
- TTL: default 24 hours, configurable
- `is_expired` property checks TTL
- `highest_gate_completed` tracks progress (0-3)
- `computation_version` for invalidation on logic changes

### MCPToolResult Context-Efficient Design

- `summary`: < 500 chars human-readable summary
- `data`: structured JSON-parseable result data
- `references`: dict of `{ref_name: tool_call_hint}` for on-demand detail
- `confidence`: agent decides whether to deepen
- `detail_available_via`: hint for getting full detail
- `tokens_used`: tracks context consumption

## See Also

- [Phase 0 Implementation Decisions](phase0-implementation.md)
- [Tiered Pipeline](../architecture/tiered-pipeline.md)
- [Scoring Dimensions](../domain/scoring-dimensions.md)
- [Screening Gates Detail](../domain/screening-gates.md)
- [Session Workflow](session-workflow.md)
- [Technology Stack Decisions](tech-stack.md)
