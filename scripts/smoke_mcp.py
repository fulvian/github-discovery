#!/usr/bin/env python3
"""Wave 3: MCP Server smoke test using direct subprocess communication.

Tests MCP tool calls through stdio transport with real GitHub API.

Usage:
    GHDISC_GITHUB_TOKEN=ghp_xxx python scripts/smoke_mcp.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


async def main():
    """Test MCP server via stdio subprocess."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "github_discovery.mcp",
        "serve",
        "--transport",
        "stdio",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={
            **os.environ,
            "GHDISC_GITHUB_TOKEN": os.environ.get("GHDISC_GITHUB_TOKEN", ""),
        },
    )

    msg_id = 0

    async def send(method: str, params: dict | None = None) -> dict:
        nonlocal msg_id
        msg_id += 1
        msg = {"jsonrpc": "2.0", "id": msg_id, "method": method}
        if params:
            msg["params"] = params
        data = json.dumps(msg) + "\n"
        proc.stdin.write(data.encode())
        await proc.stdin.drain()

        # Read response line
        response_line = await asyncio.wait_for(proc.stdout.readline(), timeout=60)
        return json.loads(response_line)

    async def notify(method: str, params: dict | None = None) -> None:
        msg = {"jsonrpc": "2.0", "method": method}
        if params:
            msg["params"] = params
        data = json.dumps(msg) + "\n"
        proc.stdin.write(data.encode())
        await proc.stdin.drain()

    try:
        # 1. Initialize
        print("1. Initializing MCP server...")
        resp = await send(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "smoke-test", "version": "1.0"},
            },
        )
        print(
            f"   Server: {resp['result']['serverInfo']['name']} v{resp['result']['serverInfo']['version']}"
        )
        print(f"   Tools capability: {resp['result']['capabilities'].get('tools', {})}")

        # 2. Initialized notification
        await notify("notifications/initialized")
        # Small delay for server to process
        await asyncio.sleep(0.1)

        # 3. List tools
        print("\n2. Listing tools...")
        resp = await send("tools/list")
        tools = resp["result"]["tools"]
        print(f"   {len(tools)} tools registered:")
        for t in tools:
            print(f"     - {t['name']}")

        # 4. Create a session
        print("\n3. Creating session...")
        resp = await send(
            "tools/call",
            {
                "name": "create_session",
                "arguments": {"name": "smoke-test-session"},
            },
        )
        session_result = resp.get("result", {})
        # Parse content
        if "content" in session_result:
            for c in session_result["content"]:
                if c.get("type") == "text":
                    data = json.loads(c["text"])
                    session_id = data.get("session_id", "unknown")
                    print(f"   Session created: {session_id}")
                    break
        else:
            print(f"   Session result: {json.dumps(session_result, indent=2)[:200]}")

        # 5. Discover repos (search channel only, small batch)
        print("\n4. Discovering repos (search, max 5)...")
        resp = await send(
            "tools/call",
            {
                "name": "discover_repos",
                "arguments": {
                    "query": "python static analysis",
                    "channels": ["search"],
                    "max_candidates": 5,
                },
            },
        )
        discovery_result = resp.get("result", {})
        pool_id = None
        if "content" in discovery_result:
            for c in discovery_result["content"]:
                if c.get("type") == "text":
                    data = json.loads(c["text"])
                    pool_id = data.get("data", {}).get("pool_id")
                    total = data.get("data", {}).get("total_candidates", "?")
                    print(f"   Summary: {data.get('summary', '?')}")
                    print(f"   Pool ID: {pool_id}")
                    print(f"   Total candidates: {total}")
                    print(f"   Elapsed: {data.get('data', {}).get('elapsed_seconds', '?')}s")
                    break

        if not pool_id:
            print("   ERROR: No pool_id in discovery result")
            return

        # 6. Get candidate pool
        print("\n5. Getting candidate pool...")
        resp = await send(
            "tools/call",
            {
                "name": "get_candidate_pool",
                "arguments": {"pool_id": pool_id, "limit": 5},
            },
        )
        pool_result = resp.get("result", {})
        if "content" in pool_result:
            for c in pool_result["content"]:
                if c.get("type") == "text":
                    pdata = json.loads(c["text"])
                    candidates = pdata.get("data", {}).get("candidates", [])
                    if not candidates:
                        candidates = pdata.get("candidates", [])
                    print(f"   Candidates ({len(candidates)}):")
                    for cand in candidates[:5]:
                        name = cand.get("repo", cand.get("full_name", "?"))
                        print(
                            f"     - {name:30s} "
                            f"★{cand.get('stars', 0):>6} "
                            f"score={cand.get('discovery_score', 0):.2f} "
                            f"{cand.get('language', '?')}"
                        )
                    break

        # 7. Quick screen a single repo
        print("\n6. Quick screening a single repo...")
        resp = await send(
            "tools/call",
            {
                "name": "quick_screen",
                "arguments": {
                    "repo_url": "https://github.com/astral-sh/ruff",
                    "gate_levels": "1",
                },
            },
        )
        screen_result = resp.get("result", {})
        if "content" in screen_result:
            for c in screen_result["content"]:
                if c.get("type") == "text":
                    data = json.loads(c["text"])
                    screen_data = data.get("data", data)
                    repo_name = screen_data.get("repo", screen_data.get("full_name", "?"))
                    print(f"   Repo: {repo_name}")
                    print(
                        f"   Gate 1 total: {screen_data.get('gate1_score', screen_data.get('gate1_total', '?'))}"
                    )
                    print(f"   Gate 1 pass:  {screen_data.get('gate1_pass', '?')}")
                    break

        print("\n✅ MCP server smoke test complete!")

    except asyncio.TimeoutError:
        print("\n❌ TIMEOUT waiting for response")
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
    finally:
        proc.stdin.close()
        proc.terminate()
        await proc.wait()


if __name__ == "__main__":
    asyncio.run(main())
