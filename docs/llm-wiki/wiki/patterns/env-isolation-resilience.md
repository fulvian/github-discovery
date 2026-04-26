# MCP Server Environment Isolation Resilience

**Last Updated**: 2026-04-26
**Confidence**: high
**Sources**: `src/github_discovery/config.py`, `src/github_discovery/logging.py`, `/home/fulvio/coding/aria/.env`
**Raw**: `src/github_discovery/config.py` (live source)

## Problem

When the github-discovery MCP server is spawned by Kilocode CLI from a project directory
that contains its own `.env` file (e.g., another project with `ARIA_HOME`, `KILOCODE_CONFIG_DIR`,
`SOPS_AGE_KEY_FILE` etc.), the server crashes with a pydantic validation error:

```
pydantic_core._pydantic_core.ValidationError: 11 validation errors for GitHubSettings
aria_home
  Extra inputs are not permitted [type=extra_forbidden, input_value='/home/fulvio/coding/aria', ...]
```

**Impact**: The MCP server fails to start. `kilo mcp list` shows `✗ github-discovery failed: MCP error -32000: Connection closed`.
All other MCP servers (npx-based, uvx-based) work fine because they don't read `.env`.

## Root Cause Chain

1. **Kilocode spawns MCP server processes with CWD = project directory** (not the MCP server's own directory)
2. **pydantic-settings `BaseSettings` with `env_file=".env"`** reads `.env` from CWD
3. **pydantic-settings loads ALL env vars from `.env`** into the validation pipeline (not just prefixed ones)
4. **Default `extra` behavior in pydantic-settings v2** rejects any field not defined in the model class
5. **Result**: If the host project's `.env` has any env var that doesn't map to a known field,
   validation fails and the server crashes

**Why only github-discovery is affected**: It's the only MCP server using `pydantic-settings` with `env_file=".env"`.
All other MCP servers (npx/uvx-based) are Node.js or Rust binaries that don't read Python `.env` files.

## Fix Applied

### 1. `config.py` — `extra="ignore"` on all SettingsConfigDict

Every `SettingsConfigDict` in `src/github_discovery/config.py` now includes `extra="ignore"`:

```python
class GitHubSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GHDISC_GITHUB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # tolerate foreign env vars from host project's .env
    )
```

This applies to all 8 settings classes: `GitHubSettings`, `DiscoverySettings`, `ScreeningSettings`,
`AssessmentSettings`, `ScoringSettings`, `MCPSettings`, `APISettings`, `Settings`.

### 2. `logging.py` — `_safe_add_logger_name` processor

Replaced `structlog.stdlib.add_logger_name` with a custom `_safe_add_logger_name` that handles
`logger=None` from third-party stdlib loggers (httpx, MCP SDK). This eliminated stderr noise
that appeared on every MCP request.

### 3. `server.py` — CWD-independent data directory

`_resolve_data_dir()` uses XDG data directory (`~/.local/share/github-discovery/`) instead
of relative paths, making the server work from any CWD.

## Design Principle

**An MCP server must be resilient to its host environment.** It will be spawned from arbitrary
project directories that may have their own `.env` files, environment variables, and configuration.
The server should:

1. **Ignore** any env vars it doesn't recognize (`extra="ignore"`)
2. **Use absolute paths** for data storage (XDG, not relative)
3. **Handle None loggers** gracefully (structlog processor chain)
4. **Never crash** due to the host project's environment

## Verification

```bash
# From aria project directory (has .env with ARIA_*, KILOCODE_*, SOPS_* vars)
cd /home/fulvio/coding/aria
kilo mcp list  # → ✗ github-discovery failed (BEFORE fix)
kilo mcp list  # → ✓ github-discovery connected (AFTER fix)

# From /tmp (no .env)
cd /tmp
kilo mcp list  # → ✓ github-discovery connected

# From github-discovery project root
cd /home/fulvio/coding/github-discovery
kilo mcp list  # → ✓ github-discovery connected
```

## Applicability

This pattern applies to **any Python MCP server using pydantic-settings** that may be spawned
from a directory other than its own project root. The `extra="ignore"` setting is the essential
defense against foreign environment contamination.
