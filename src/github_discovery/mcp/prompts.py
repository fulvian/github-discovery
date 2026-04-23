"""MCP agent skill definitions (prompt registry).

Defines 5 prompt skills that guide agents through structured workflows
(Blueprint §21.5). Each prompt returns a string with step-by-step instructions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_all_prompts(mcp: FastMCP) -> None:
    """Register all MCP prompt skill definitions."""

    @mcp.prompt()
    def discover_underrated(
        query: str,
        domain: str = "",
        max_candidates: int = 100,
    ) -> str:
        """Find technically excellent repos that are underrated by star count.

        This skill guides you through a 5-step progressive deepening workflow:
        discover → screen → deep assess → rank → explain.

        Args:
            query: What to search for (e.g., "python static analysis")
            domain: Domain focus (e.g., "library", "cli", "ml_lib")
            max_candidates: How many candidates to discover (default: 100)
        """
        return f"""You are looking for technically excellent GitHub repositories
that are underrated by star count. Follow this workflow:

**Step 1: Discover** — Create a session and discover candidates:
- create_session(name="underrated-{query}")
- discover_repos(query="{query}", max_candidates={max_candidates}, session_id=<from_above>)

**Step 2: Screen** — Progressive screening through Gate 1 and Gate 2:
- screen_candidates(pool_id=<from_discover>, gate_level="both", session_id=<session_id>)

**Step 3: Deep Assess** — Evaluate top candidates (only repos that passed Gate 1+2):
- deep_assess(repo_urls=<top_10_from_shortlist>, session_id=<session_id>)

**Step 4: Rank** — Anti-star bias ranking to find hidden gems:
- rank_repos(domain="{domain}", max_results=20, session_id=<session_id>)

**Step 5: Explain** — Understand why top repos scored high:
- explain_repo(repo_url=<top_repo>, detail_level="full", session_id=<session_id>)

Key principle: Stars are context only. The value_score (quality_score / log10(stars + 10))
identifies repos that are technically excellent but not yet widely known.
"""

    @mcp.prompt()
    def quick_quality_check(repo_url: str) -> str:
        """Quick quality check on a specific repository.

        Args:
            repo_url: GitHub repository URL to check
        """
        return f"""Perform a quick quality check on: {repo_url}

1. quick_screen(repo_url="{repo_url}", gate_levels="1,2")
2. If passed, quick_assess(repo_url="{repo_url}",
   dimensions=["code_quality", "testing", "security"])
3. Summarize findings: what's good, what needs improvement
"""

    @mcp.prompt()
    def compare_for_adoption(
        repo_urls: str,
        key_dimensions: str = "code_quality,architecture,testing,maintenance",
    ) -> str:
        """Compare multiple repos for an adoption decision.

        Args:
            repo_urls: Comma-separated repository URLs
            key_dimensions: Comma-separated dimensions to evaluate
        """
        return f"""Compare these repositories for adoption: {repo_urls}

1. Screen each: quick_screen(repo_url=<url>) for each repo
2. Assess key dimensions: quick_assess(repo_url=<url>, dimensions=[{key_dimensions}])
3. Compare: compare_repos(repo_urls=[{repo_urls}], dimensions=[{key_dimensions}])
4. Provide a recommendation with rationale
"""

    @mcp.prompt()
    def domain_deep_dive(
        domain: str,
        query: str = "",
    ) -> str:
        """Deep exploration of a specific domain.

        Args:
            domain: Domain to explore (e.g., "web_framework", "data_tool")
            query: Optional specific search query
        """
        return f"""Deep exploration of domain: {domain}

1. Discover: discover_repos(query="{query or domain}", max_candidates=200)
2. Screen: screen_candidates(pool_id=<pool>, gate_level="both")
3. Deep assess: deep_assess(repo_urls=<top_15_from_shortlist>)
4. Domain rank: rank_repos(domain="{domain}", max_results=30)
5. For each hidden gem: explain_repo(repo_url=<url>, detail_level="full")
"""

    @mcp.prompt()
    def security_audit(repo_urls: str) -> str:
        """Security-first assessment of repositories.

        Args:
            repo_urls: Comma-separated repository URLs to audit
        """
        return f"""Perform a security-first assessment on: {repo_urls}

1. Heavy Gate 2 screening: screen_candidates with strict security thresholds
2. Security-focused assessment: deep_assess with dimensions ["security", "code_quality"]
3. For each repo: explain_repo(repo_url=<url>, detail_level="full")
4. Provide security report with risk ratings
"""
