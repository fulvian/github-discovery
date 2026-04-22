---
Title: MCP Python SDK Verification (Context7)
Topic: apis
Sources: Context7 verification of /modelcontextprotocol/python-sdk v1.x
Raw: [phase0-plan.md](../../plans/phase0-implementation-plan.md)
Updated: 2026-04-22
Confidence: high
---

# MCP Python SDK Verification (Context7)

Key API patterns and verified code examples from the MCP Python SDK documentation, verified via Context7 on 2026-04-22.

## Key Points

- **FastMCP** is the primary high-level API for creating MCP servers
- **Tools** use `@mcp.tool()` decorator with async support and `Context` parameter
- **Resources** use `@mcp.resource()` decorator with URI templates
- **Prompts** use `@mcp.prompt()` decorator for agent skill definitions
- **Progress notifications** use `ctx.report_progress(progress, total, message)`
- **Transports**: stdio (default for local), streamable-http (recommended for production)
- **Session management** via `Context` parameter in tool handlers

## FastMCP Server Setup

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("github-discovery", json_response=True)

# Stateful (session persistence) vs Stateless
# Development: mcp = FastMCP("github-discovery")  # stateful
# Production:  mcp = FastMCP("github-discovery", stateless_http=True, json_response=True)
```

**For GitHub Discovery**: Use stateful for sessions (cross-session progressive deepening), json_response=True for context efficiency.

## Tool Definition Pattern

```python
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

mcp = FastMCP("github-discovery")

@mcp.tool()
async def discover_repos(
    query: str,
    max_candidates: int = 50,
    session_id: str | None = None,
    ctx: Context[ServerSession, None] | None = None,
) -> str:
    """Find candidate repositories matching a query."""
    # Progress notifications for long operations
    if ctx:
        await ctx.report_progress(0.1, 1.0, "Starting discovery...")
        await ctx.info("Discovery started", extra={"query": query})
    
    # ... discovery logic ...
    
    # Return context-efficient summary
    return f"Discovered {len(candidates)} candidates"
```

**Key patterns verified**:
1. `ctx: Context` parameter for logging, progress, and resource access
2. `await ctx.report_progress(progress, total, message)` — NOT the deprecated `progress()` context manager
3. `await ctx.info()`, `await ctx.debug()`, `await ctx.warning()`, `await ctx.error()` for structured logging
4. `session_id` as optional parameter for cross-session workflows

## Transport Configuration

```python
# Option 1: STDIO (for Kilocode CLI, OpenCode, Claude Code local)
mcp.run(transport="stdio")

# Option 2: Streamable HTTP (recommended for production)
mcp.run(
    transport="streamable-http",
    host="127.0.0.1",
    port=8080,
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
)
```

**For GitHub Discovery**: Default to `stdio` for local agent integration (Kilocode CLI, Claude Code). Support `streamable-http` for deployment.

## Context Capabilities (Verified)

```python
from pydantic import BaseModel

class BookingPreferences(BaseModel):
    check_alternative: bool
    alternative_date: str = "2024-12-26"

@mcp.tool()
async def process_with_context(data: str, ctx: Context) -> str:
    # Logging at different levels
    await ctx.debug(f"Debug: Processing '{data}'")
    await ctx.info("Info: Starting processing")
    await ctx.warning("Warning: Experimental")
    
    # Structured logging with extra data
    await ctx.info("Processing", extra={"data_length": len(data)})
    
    # Progress reporting (Blueprint §21.6)
    await ctx.report_progress(25, 100, "Step 1 of 4")
    
    # Read another resource
    resource_data = await ctx.read_resource("config://settings")
    
    # Request metadata
    request_id = ctx.request_id
    client_id = ctx.client_id  # May be None
    
    # Elicit additional information from user (form mode)
    result = await ctx.elicit(
        message="Would you like to check another date?",
        schema=BookingPreferences,
    )
    
    return f"Processed: {data}"
```

**Important**: `ctx.elicit()` uses Pydantic models for structured user input — potential future pattern for agent-driven policy configuration.

## Migration Note (Verified)

The `mcp.shared.progress` module has been **removed**. Use `Context.report_progress()` instead:

```python
# REMOVED (old pattern):
# from mcp.shared.progress import progress
# with progress(ctx, total=100) as p:
#     await p.progress(25)

# CURRENT (new pattern):
@mcp.tool()
async def my_tool(x: int, ctx: Context) -> str:
    await ctx.report_progress(25, 100, "Step 1")
    # Process...
    await ctx.report_progress(100, 100, "Complete")
    return "done"
```

## Implications for GitHub Discovery Phase 7

1. **FastMCP is the right abstraction** — no need for low-level MCP server setup
2. **Context parameter is essential** — all discovery/screening/assessment tools should accept `ctx: Context` for progress and logging
3. **Progress notifications** use `ctx.report_progress()` (NOT the deprecated `progress()` context manager)
4. **json_response=True** matches our context-efficient output design (Blueprint §21.8)
5. **stateless_http=True** for production deployment, stateful for development with sessions
6. **Elicit** could enable agent-driven policy in future (e.g., "should I deepen this candidate?")

## See Also

- [MCP-Native Design](../architecture/mcp-native-design.md)
- [MCP Tool Specifications](mcp-tools.md)
- [Session Workflow](../patterns/session-workflow.md)
- [Phase 0 Implementation](../patterns/phase0-implementation.md)