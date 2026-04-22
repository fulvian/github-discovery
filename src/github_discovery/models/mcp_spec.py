"""MCP tool and agent workflow specification models.

These models define the contract for each MCP tool and agent workflow,
enabling progressive deepening (Blueprint §21.2) and context-efficient
design (Blueprint §21.8).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class MCPOutputFormat(StrEnum):
    """Supported output formats for MCP tools."""

    SUMMARY = "summary"
    FULL = "full"
    JSON = "json"


class MCPToolSpec(BaseModel):
    """Specification for an MCP tool in the GitHub Discovery system.

    Each tool is documented with its parameters, output schema,
    session awareness, and context budget.
    """

    name: str = Field(description="Tool name (e.g., 'discover_repos')")
    description: str = Field(description="Human-readable tool description")
    parameters_schema: dict[str, object] = Field(
        default_factory=dict,
        description="JSON Schema for tool parameters",
    )
    output_schema: dict[str, object] = Field(
        default_factory=dict,
        description="JSON Schema for tool output",
    )
    session_aware: bool = Field(
        default=True,
        description="Whether the tool supports session_id for cross-session workflows",
    )
    default_output_format: MCPOutputFormat = Field(
        default=MCPOutputFormat.SUMMARY,
        description="Default output format (summary-first for context efficiency)",
    )
    max_context_tokens: int = Field(
        default=2000,
        description="Maximum context tokens per invocation (default output)",
    )
    gate_level: int | None = Field(
        default=None,
        description="Gate level this tool belongs to (0-3), None for management tools",
    )
    category: str = Field(
        description="Tool category: discovery, screening, assessment, ranking, session",
    )


class WorkflowStep(BaseModel):
    """A single step in an agent workflow."""

    tool_name: str = Field(description="MCP tool to invoke")
    description: str = Field(description="What this step accomplishes")
    default_params: dict[str, object] = Field(
        default_factory=dict,
        description="Default parameters for the tool invocation",
    )
    optional: bool = Field(
        default=False,
        description="Whether this step can be skipped",
    )


class AgentWorkflowConfig(BaseModel):
    """Configuration for an agent workflow (MCP prompt/skill).

    Defines a structured multi-step workflow that guides an agent
    through progressive deepening (Blueprint §21.7).
    """

    name: str = Field(description="Workflow name (e.g., 'discover_underrated')")
    description: str = Field(description="Human-readable workflow description")
    steps: list[WorkflowStep] = Field(
        description="Ordered sequence of tool invocations",
    )
    category: str = Field(
        description="Workflow category: discovery, assessment, comparison, security",
    )
    output_format: MCPOutputFormat = Field(
        default=MCPOutputFormat.SUMMARY,
        description="Recommended default output format",
    )


# --- Predefined Tool Specifications ---


DISCOVER_REPOS_SPEC = MCPToolSpec(
    name="discover_repos",
    description="Find candidate repositories matching a query across multiple channels",
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query for repositories"},
            "channels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Discovery channels to use",
            },
            "max_candidates": {"type": "integer", "description": "Max candidates to return"},
            "session_id": {"type": "string", "description": "Session ID for workflow continuity"},
        },
        "required": ["query"],
    },
    session_aware=True,
    max_context_tokens=2000,
    gate_level=0,
    category="discovery",
)

SCREEN_CANDIDATES_SPEC = MCPToolSpec(
    name="screen_candidates",
    description="Screen candidate repositories at specified gate level(s)",
    parameters_schema={
        "type": "object",
        "properties": {
            "pool_id": {"type": "string", "description": "Candidate pool ID"},
            "gate_level": {"type": "string", "description": "Gate level: '1', '2', or 'both'"},
            "min_gate1_score": {"type": "number", "description": "Minimum Gate 1 score threshold"},
            "min_gate2_score": {"type": "number", "description": "Minimum Gate 2 score threshold"},
            "session_id": {"type": "string", "description": "Session ID"},
        },
        "required": ["pool_id", "gate_level"],
    },
    session_aware=True,
    max_context_tokens=2000,
    gate_level=1,
    category="screening",
)

DEEP_ASSESS_SPEC = MCPToolSpec(
    name="deep_assess",
    description="Deep LLM assessment of top candidates (Gate 3) — requires Gate 1+2 pass",
    parameters_schema={
        "type": "object",
        "properties": {
            "repo_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Repository URLs to assess",
            },
            "dimensions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Assessment dimensions to evaluate",
            },
            "budget_tokens": {
                "type": "integer",
                "description": "Token budget for this assessment",
            },
            "session_id": {"type": "string", "description": "Session ID"},
        },
        "required": ["repo_urls"],
    },
    session_aware=True,
    max_context_tokens=2000,
    gate_level=3,
    category="assessment",
)

RANK_REPOS_SPEC = MCPToolSpec(
    name="rank_repos",
    description="Rank repositories within a domain using anti-star bias scoring",
    parameters_schema={
        "type": "object",
        "properties": {
            "domain": {"type": "string", "description": "Domain type for ranking"},
            "min_confidence": {"type": "number", "description": "Minimum confidence score"},
            "min_value_score": {"type": "number", "description": "Minimum value score"},
            "max_results": {"type": "integer", "description": "Max results to return"},
            "session_id": {"type": "string", "description": "Session ID"},
        },
    },
    session_aware=True,
    max_context_tokens=2000,
    gate_level=None,
    category="ranking",
)

# --- Predefined Workflow Configurations ---

DISCOVER_UNDERRATED_WORKFLOW = AgentWorkflowConfig(
    name="discover_underrated",
    description="Find technically excellent repos that are underrated by star count",
    steps=[
        WorkflowStep(
            tool_name="discover_repos",
            description="Discover candidate pool",
            default_params={"max_candidates": 50},
        ),
        WorkflowStep(
            tool_name="screen_candidates",
            description="Screen candidates through Gate 1 and 2",
            default_params={"gate_level": "both"},
        ),
        WorkflowStep(
            tool_name="deep_assess",
            description="Deep assess top candidates",
            default_params={"dimensions": ["code_quality", "architecture", "testing"]},
            optional=True,
        ),
        WorkflowStep(
            tool_name="rank_repos",
            description="Rank with anti-star bias value score",
        ),
        WorkflowStep(
            tool_name="explain_repo",
            description="Explain top findings",
            default_params={"detail_level": "summary"},
            optional=True,
        ),
    ],
    category="discovery",
)

QUICK_QUALITY_CHECK_WORKFLOW = AgentWorkflowConfig(
    name="quick_quality_check",
    description="Quick quality assessment of a specific repository",
    steps=[
        WorkflowStep(
            tool_name="quick_screen",
            description="Quick screen (Gate 1) of repository",
            default_params={"gate_levels": "1"},
        ),
        WorkflowStep(
            tool_name="explain_repo",
            description="Report quality signals",
            default_params={"detail_level": "summary"},
        ),
    ],
    category="assessment",
)
