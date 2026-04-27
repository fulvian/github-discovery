---
Title: GitHub API Patterns and Constraints
Topic: apis
Sources: Foundation Blueprint §8, §18; Findings; Rate limit fix (2026-04-25); Smart throttle (2026-04-27)
Raw: [blueprint.md](../../../foundation/github-discovery_foundation_blueprint.md); [findings.md](../../../../findings.md)
Updated: 2026-04-27
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

### Rate Limit Handling — Smart Throttling (2026-04-27 fix)

**Problem**: Original `_await_if_rate_limited()` waited for full reset (3597s observed)
instead of capping wait. Watermarks too aggressive (10/3).

**Solution implemented** (Context7 + Brave verified GitHub best practices):

| Mechanism | Before | After |
|-----------|--------|-------|
| Core watermark | 10 | 5 |
| Search watermark | 3 | 2 |
| Max wait on low limit | Full reset (~60min) | 30s cap |
| Concurrent limit when throttled | 5 (via httpx transport) | 3 via asyncio.Semaphore |
| Configurable cap | No | Yes (`GHDISC_GITHUB_RATE_LIMIT_CAP_SECONDS`) |

**Key GitHub best practice**: "Don't wait full reset — use exponential backoff.
Wait at most 30s before retrying" (GitHub REST API docs).

**Adaptive throttling behavior**:
1. First request: `remaining=None` → assume fine, no wait
2. Response received: `_core_remaining` tracked via event hook
3. Second request: if `remaining < watermark (5)` → wait capped 30s, activate Semaphore(3)
4. Subsequent requests: throttle reduces concurrent requests from 5 → 3
5. Recovery: when `remaining >= watermark`, throttle resets on next request

**Configurable settings** (env vars):
- `GHDISC_GITHUB_RATE_LIMIT_CAP_SECONDS` (default: 30.0) — max wait seconds
- `GHDISC_GITHUB_MAX_CONCURRENT_REQUESTS` (default: 10) — pre-existing

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