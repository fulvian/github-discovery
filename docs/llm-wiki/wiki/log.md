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

## [2026-04-22] lint | Initial wiki health check
- 14 articles created across 4 directories (architecture, apis, domain, patterns)
- 3 issues found: broken raw links to findings.md (wrong relative path `../../../findings.md` → fixed to `../../../../findings.md`)
- 3 auto-fixed
- All internal cross-references verified (15 cross-links between articles)
- All raw source references verified (pointing to project files in docs/foundation/, docs/roadmaps/, findings.md)