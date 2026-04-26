---
Title: Domain Strategy and Repository Taxonomy
Topic: domain
Sources: Foundation Blueprint §10; Roadmap Phase 5; Fase 2 Audit Remediation (2026-04-26)
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md); [fase2_plan.md](../../../plans/fase2_plan.md)
Updated: 2026-04-26
Confidence: high
---

# Domain Strategy and Repository Taxonomy

GitHub Discovery uses a domain taxonomy to enable fair intra-domain ranking. Comparing a CLI tool with 100 stars against a web framework with 100 stars is misleading — each domain has different baselines for quality and visibility.

## Domain Taxonomy

| Domain | Description | Key Quality Signals | Gate1/Gate2 Thresholds |
|--------|-------------|---------------------|----------------------|
| `cli` | Command-line tools | Testing, docs, release discipline | 0.40 / 0.50 |
| `web_framework` | Web frameworks and servers | Architecture, docs, migration guides | 0.50 / 0.60 |
| `data_tool` | Data processing and analysis | Functional completeness, docs | 0.40 / 0.50 |
| `ml_lib` | Machine learning libraries | Innovation, reproducibility, docs | 0.40 / 0.50 |
| `devops_tool` | DevOps and infrastructure | Security, reliability, testability | 0.50 / 0.60 |
| `library` | General-purpose libraries | API surface, docs, test coverage | 0.50 / 0.60 |
| `backend` | Backend services and APIs | Architecture, security, monitoring | 0.50 / 0.60 |
| `security_tool` | Security analysis and tooling | Security posture, crypto quality, audit trail | 0.60 / 0.70 |
| `lang_tool` | Language servers, linters, formatters | Code quality, testing, performance | 0.50 / 0.60 |
| `test_tool` | Testing frameworks and utilities | Testing (25% weight), docs, maintenance | 0.50 / 0.60 |
| `doc_tool` | Documentation generators and tools | Documentation (25% weight), functionality | 0.40 / 0.50 |
| `other` | Catch-all (default) | Default weights | 0.50 / 0.60 |

Note: `security_tool` has the strictest thresholds (0.60/0.70) because security tooling must meet a higher quality bar. `cli`, `data_tool`, `ml_lib`, `doc_tool` have more lenient thresholds (0.40/0.50) to avoid over-filtering in domains where metadata signals are weaker proxies.

## Domain-Dependent Quality Expectations

What "quality" means varies by domain:

- **CLI tools**: Comfort matters — error messages, help text, exit codes, config
- **Web frameworks**: Documentation and migration paths are critical; breaking changes are costly
- **ML libraries**: Reproducibility and clear API matter more than test coverage
- **DevOps tools**: Security and reliability are paramount; downtime is unacceptable
- **Data tools**: Functional completeness (can it handle real-world data?) outweighs micro-optimizations

## Ranking Intra-Domain

- Ranking is performed **within** each domain category separately
- Cross-domain comparison requires explicit normalization and a warning
- The `compare_repos` MCP tool emits a warning when repos span different domains
- Domain profiles configure weighting: `scoring/profiles.py`

## Domain Profile Model

```python
class DomainProfile(BaseModel):
    domain_type: DomainType
    display_name: str
    description: str
    dimension_weights: dict[ScoreDimension, float]  # sums to 1.0
    derivation_map: dict[str, list[list[float | str]]] | None  # per-profile override (T5.1)
    gate_thresholds: dict[str, float]  # gate1, gate2, gate3 minimum pass scores
    discovery_channels: list[DiscoveryChannel]  # preferred channels
    star_baseline: float  # expected star count for "established" project
```

### Per-Profile Derivation Map (Fase 2 T5.1)

Each profile can override the default `_DERIVATION_MAP` (dimension → sub-score mappings). The engine merges profile-specific entries with module-level defaults — dimensions specified in the profile override defaults, unspecified dimensions keep the default mapping.

Example use case: an ML_LIB profile could weight `complexity` higher in CODE_QUALITY because ML code quality is heavily influenced by model complexity.

### Per-Profile Gate Thresholds (Fase 2 T5.2)

All 12 built-in profiles have explicit `gate_thresholds` dicts (`gate1`, `gate2`, `gate3`). The screening orchestrator reads from `ProfileRegistry.get(domain).gate_thresholds` first, with fallback to legacy `_DOMAIN_THRESHOLDS`.

### Custom Profile Loading (Fase 2 T5.3)

`ProfileRegistry` supports loading custom profiles from YAML/TOML files:
- `load_from_yaml()` / `load_from_toml()` / `load_custom_profiles()` (auto-detects format)
- Case-insensitive domain_type matching (YAML `ML_LIB` → enum `ml_lib`)
- Supports custom derivation_map and gate_thresholds
- `ScoringSettings.custom_profiles_path` auto-loads on registry initialization
- Weight validation: all weights must sum to 1.0 (±0.01)
- CLI: `ghdisc profiles list`, `ghdisc profiles show <domain>`, `ghdisc profiles validate <path>`

### Configuration

Set `GHDISC_SCORING_CUSTOM_PROFILES_PATH=/path/to/profiles.yaml` in environment. All pipeline components that create a `ProfileRegistry` (ScoringEngine, ScreeningOrchestrator) will automatically load custom profiles.

## See Also

- [Scoring Dimensions](scoring-dimensions.md)
- [Anti-Star Bias](../architecture/anti-star-bias.md)