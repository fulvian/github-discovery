---
Title: Option C Hybrid Architecture Decision
Topic: architecture
Sources: Foundation Blueprint §9, §19
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md)
Updated: 2026-04-22
Confidence: high
---

# Option C Hybrid Architecture Decision

The foundational architecture decision for GitHub Discovery is **Option C — Hybrid**: API/Worker core + MCP facade + CLI, now evolved to **MCP-native agentic system** per §21.

## Key Points

- Three delivery options were evaluated: MCP-first (A), API+Worker+Web UI (B), Hybrid (C)
- Option C was chosen as the direction, then evolved to MCP-native per §21
- Core principles: reuse-first, thin orchestration layer, two-lane pipeline, security-first, composable deployment

## Options Evaluated

### Option A — MCP-First Service
- Core engine + MCP server
- Target: agent workflows
- Pro: native AI integration
- Con: limited standalone usability

### Option B — API + Worker + Web UI
- Backend scoring + dashboard discovery
- Pro: broad product usability
- Con: weak AI agent integration

### Option C — Hybrid (Chosen)
- API/Worker core + MCP facade + CLI
- Pro: maximum flexibility
- Then evolved to **MCP-native agentic system** (§21): MCP primary, API secondary, CLI agent-friendly

## Anti-Overengineering Principles

1. **Reuse-first**: Use `github/github-mcp-server` for standard GitHub operations, no custom adapters where unnecessary
2. **Thin orchestration layer**: GitHub Discovery adds only discovery/scoring/ranking logic, not duplicate MCP functionality
3. **Two-lane pipeline**: Lane 1 (cheap) — non-LLM pre-screening on large volumes; Lane 2 (deep) — LLM analysis only on high-priority shortlist
4. **Security-first execution**: Default `read-only` in analysis flows; write enabled only in authorized workflows
5. **Composable deployment**: Core service (API + queue + workers), MCP facade for agentic access, CLI for batch/CI

## Minimal Components

- **Discovery API**: Candidate ingestion, filters, ranking queries
- **Scoring Workers**: Separate workers for `metadata`, `static/security`, `LLM deep eval`
- **Feature Store**: Persistent feature storage per repo (avoids expensive recalculation)
- **Policy Engine**: Domain-specific thresholds, weights, gating
- **MCP Integration Layer**: Client to official GitHub MCP with minimal toolsets
- **CLI**: Commands `discover`, `screen`, `deep-eval`, `rank`, `export`

## See Also

- [MCP-Native Design](mcp-native-design.md)
- [Tech Stack Decisions](../patterns/tech-stack.md)