---
Title: Domain Strategy and Repository Taxonomy
Topic: domain
Sources: Foundation Blueprint §10; Roadmap Phase 5
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md)
Updated: 2026-04-22
Confidence: medium
---

# Domain Strategy and Repository Taxonomy

GitHub Discovery uses a domain taxonomy to enable fair intra-domain ranking. Comparing a CLI tool with 100 stars against a web framework with 100 stars is misleading — each domain has different baselines for quality and visibility.

## Domain Taxonomy

| Domain | Description | Key Quality Signals |
|--------|-------------|---------------------|
| `CLI` | Command-line tools | Testing, docs, release discipline |
| `web_framework` | Web frameworks and servers | Architecture, docs, migration guides |
| `data_tool` | Data processing and analysis | Functional completeness, docs |
| `ml_lib` | Machine learning libraries | Innovation, reproducibility, docs |
| `devops_tool` | DevOps and infrastructure | Security, reliability, testability |
| `library` | General-purpose libraries | API surface, docs, test coverage |
| `backend` | Backend services and APIs | Architecture, security, monitoring |
| `other` | Catch-all category | Default weights |

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
    gate_thresholds: dict[GateLevel, float]  # minimum pass scores
    discovery_channels: list[DiscoveryChannel]  # preferred channels
    star_baseline: float  # expected star count for "established" project
```

## See Also

- [Scoring Dimensions](scoring-dimensions.md)
- [Anti-Star Bias](../architecture/anti-star-bias.md)