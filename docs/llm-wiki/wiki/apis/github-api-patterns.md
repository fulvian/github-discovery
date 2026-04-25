---
Title: GitHub API Patterns and Constraints
Topic: apis
Sources: Foundation Blueprint §8, §18; Findings; Rate limit fix (2026-04-25)
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [findings.md](../../../../findings.md)
Updated: 2026-04-25
Confidence: high
---

# GitHub API Patterns and Constraints

GitHub Discovery uses both REST and GraphQL APIs for repository metadata and discovery. Understanding their constraints is essential for building a scalable pipeline.

## Key Points

- Both REST and GraphQL APIs are used for different purposes
- Rate limits and cost models require careful management
- Pagination must be rigorous for bulk analysis
- Composition with GitHub MCP Server avoids reimplementing standard operations
- **Exponential backoff with retry is mandatory** — never fail-fast on rate limit

## REST API

### Capabilities Used
- Repository metadata (owner, language, stars, topics, dates)
- Commit history and contributor patterns
- Issue/PR/review metadata
- Release/tag activity
- Code search and file presence checks

### REST Best Practices
- Use authenticated requests (Bearer token) for higher rate limits
- Handle `retry-after` and `x-ratelimit-*` headers
- Use conditional requests (`etag` / `if-modified-since`) to avoid reprocessing unchanged data
- Limit concurrency to respect rate limits
- Respect `x-ratelimit-remaining` and back off proactively

### Rate Limits
- Authenticated: 5,000 requests/hour (core), 30/minute (search)
- Unauthenticated: 60 requests/hour (insufficient for production)
- Search API: 30 requests/minute authenticated

### Rate Limit Handling (Bug Fix 2026-04-25)

**Problem**: The original `GitHubRestClient` raised `RateLimitError` immediately when `x-ratelimit-remaining` was below a watermark (50 for core, 5 for search). The caller (`gate1_metadata.py`) caught the exception and returned empty data → zero scores for all affected repos.

**Solution**: The client now retries with exponential backoff instead of failing fast:

| Mechanism | Implementation |
|-----------|---------------|
| **Proactive waiting** | `_await_if_rate_limited()`: when `remaining < watermark`, waits until `X-RateLimit-Reset` timestamp |
| **Exponential backoff** | `_retry_on_rate_limit()`: 1s→2s→4s→8s→16s with random jitter (±50%) |
| **Wait for reset** | Uses exact `X-RateLimit-Reset` header (UNIX timestamp) for precise timing |
| **Retry budget** | 5 attempts max, 60s cap per wait |
| **Watermarks** | Core: 10 (was 50), Search: 3 (was 5) — too conservative before |

**Key insight**: `gate1_metadata.py` makes 7 parallel API calls per repo. With 30 repos, that's 210 calls. Authenticated rate limit is 5000/hour — enough, but only if we don't waste them by failing fast and retrying entire batches.

## GraphQL API

### Capabilities Used
- Aggregate queries (combine repo + issues + PRs metadata in single call)
- Cursor-based pagination (`first`/`last` + `after`/`before` + `pageInfo`)
- Complex filtering on server side

### GraphQL Best Practices
- Use cursor-based pagination (`first/last 1..100`, `pageInfo` with `hasNextPage`/`endCursor`)
- Control batch size to avoid query cost overruns
- Monitor `rateLimit` field in responses
- Handle `cost` calculations: higher complexity = more points consumed

### Cost Model
- GraphQL uses a point-based system
- Complex queries (deep nesting, many fields) cost more
- Budget controlled per session via `asyncio.Semaphore`

## GitHub MCP Server Composition

GitHub Discovery **does not reimplement** standard GitHub operations. Instead:
- Uses `github/github-mcp-server` for repos, issues, PRs, code search
- Minimal toolset: `repos, issues, pull_requests, context`
- Read-only mode by default: `X-MCP-Readonly: true`
- Composable configuration in `.kilo/mcp.json`

### Configuration Principles
- `exclude-tools` to remove unwanted operations
- `dynamic-toolsets` for progressive tool discovery
- `lockdown-mode` for restrictive content policies
- Same authentication token shared via environment variables

## Implementation Notes

- `httpx.AsyncClient` with authentication, rate limit awareness, retry with backoff
- GraphQL client with cursor-based pagination and controlled batch sizes
- Rate limiting via `asyncio.Semaphore` for parallel requests
- Feature Store caching to avoid redundant API calls (dedup by `repo_full_name + commit_SHA`)

## See Also

- [Discovery Channels](../domain/discovery-channels.md)
- [MCP-Native Design](../architecture/mcp-native-design.md)
- [Tech Stack](../patterns/tech-stack.md)