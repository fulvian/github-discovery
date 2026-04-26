---
Title: Discovery Channels and Strategies
Topic: domain
Sources: Foundation Blueprint §6 (Layer A); Roadmap Phase 2
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [roadmap.md](../../../roadmaps/github-discovery_foundation_roadmap.md)
Updated: 2026-04-27
Confidence: high
---

# Discovery Channels and Strategies

Layer A (Gate 0) of the pipeline discovers candidates through multiple channels to reduce popularity bias inherent in any single source.

## Key Points

- Multiple discovery channels reduce individual source bias
- Each channel produces candidates with a `discovery_score`
- The orchestrator deduplicates and merges across channels
- Channels run concurrently with `asyncio.Semaphore` rate limiting

## Channel Inventory

### 1. GitHub Search API / GraphQL
- **Module**: `discovery/search_channel.py`, `discovery/github_graphql.py`
- **What**: Structured search queries with filters (topic, language, date range, size, forks)
- **Bias**: Popularity-influenced search results, but filterable
- **Mitigation**: Sort by recency/updated rather than stars; use GraphQL for aggregate queries
- **Rate considerations**: REST rate limit (5000/hr authenticated), GraphQL point-cost system

### 2. GitHub Code Search API
- **Module**: `discovery/code_search_channel.py`
- **What**: Search for quality signal patterns in files (e.g., presence of `pytest`, `CI.yml`, `SECURITY.md`)
- **Bias**: Lower than repo search — finds repos by their practices, not popularity
- **Mitigation**: Use targeted patterns to find repos with quality infrastructure regardless of stars

### 3. Dependency Graph Traversal
- **Module**: `discovery/dependency_channel.py`
- **What**: From seed repos known to be high-quality, traverse `dependencies`/`dependents`
- **Bias**: Structural network bias (popular repos have more dependents)
- **Mitigation**: Start from curated seeds, weight by seed quality, not network size

### 4. Package Registry Mapping
- **Module**: `discovery/registry_channel.py`
- **What**: Query npm/PyPI/crates.io/Maven for packages → map to GitHub repos
- **Bias**: Download-count bias (but less skewed than GitHub stars)
- **Mitigation**: Focus on recently updated packages with quality signals

### 5. Awesome Lists & Curated Sources
- **Module**: `discovery/curated_channel.py`
- **What**: Parse awesome-X lists (GitHub README), community-curated collections
- **Bias**: Curation bias (maintainer preference) but human-quality-filtered
- **Mitigation**: Combine multiple curated lists, track source
- **Important fix (2026-04-27)**: Removed `sindresorhus/awesome` mega-list fallback. Previously, queries without a language match fell back to this mega-list (thousands of repos), flooding the pool with irrelevant results. Now:
  - Returns empty when no language/topic match found (instead of mega-list)
  - Added `_TOPIC_AWESOME_MAP` for keyword matching (ml, security, testing, devops, etc.)
  - Output capped at `_MAX_CURATED_CANDIDATES = 50` to prevent pool flooding
  - Matches against `query.topics` (explicit) and `query.query` keywords

### 6. Seed Expansion
- **Module**: `discovery/seed_expansion.py`
- **What**: Co-contributor analysis, org adjacency (same org as seed), co-dependency
- **Bias**: Network proximity bias (similar to seed repos)
- **Mitigation**: Limit expansion depth, diversify seed set

## Discovery Score

Each candidate receives a preliminary `discovery_score` (0.0-1.0) based on:
- Number of channels that found the repo (breadth signal)
- Channel-specific quality indicators
- Deduplication across channels

## Implementation Notes

- GitHub REST client uses `httpx.AsyncClient` with authentication, rate limit awareness, conditional requests (`etag`/`if-modified-since`), and retry with backoff
- GraphQL client uses cursor-based pagination (`first/after`), controlled batch for query cost
- Orchestrator coordinates channels, deduplicates by `full_name`, and manages concurrency

## See Also

- [Tiered Pipeline](../architecture/tiered-pipeline.md)
- [MCP-Native Design](../architecture/mcp-native-design.md)