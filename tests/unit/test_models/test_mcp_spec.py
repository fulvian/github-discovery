"""Tests for MCP tool spec models."""

from __future__ import annotations

from github_discovery.models.mcp_spec import (
    DEEP_ASSESS_SPEC,
    DISCOVER_REPOS_SPEC,
    DISCOVER_UNDERRATED_WORKFLOW,
    AgentWorkflowConfig,
    MCPOutputFormat,
    MCPToolSpec,
)


class TestMCPToolSpec:
    """Test MCP tool specification model."""

    def test_predefined_specs(self) -> None:
        """Predefined specs are valid and well-formed."""
        assert DISCOVER_REPOS_SPEC.name == "discover_repos"
        assert DISCOVER_REPOS_SPEC.gate_level == 0
        assert DISCOVER_REPOS_SPEC.session_aware is True
        assert DEEP_ASSESS_SPEC.gate_level == 3
        assert DEEP_ASSESS_SPEC.category == "assessment"

    def test_tool_spec_serialization(self) -> None:
        """Tool specs serialize to/from JSON."""
        spec = MCPToolSpec(
            name="test_tool",
            description="A test tool",
            category="testing",
        )
        json_str = spec.model_dump_json()
        restored = MCPToolSpec.model_validate_json(json_str)
        assert restored.name == "test_tool"

    def test_custom_tool_spec(self) -> None:
        """Custom tool specs can be created."""
        spec = MCPToolSpec(
            name="compare_repos",
            description="Compare repositories side-by-side",
            session_aware=True,
            max_context_tokens=3000,
            category="ranking",
        )
        assert spec.default_output_format == MCPOutputFormat.SUMMARY


class TestAgentWorkflowConfig:
    """Test agent workflow configuration model."""

    def test_predefined_workflow(self) -> None:
        """Discover underrated workflow has 5 steps."""
        assert len(DISCOVER_UNDERRATED_WORKFLOW.steps) == 5
        assert DISCOVER_UNDERRATED_WORKFLOW.steps[0].tool_name == "discover_repos"
        assert DISCOVER_UNDERRATED_WORKFLOW.category == "discovery"

    def test_workflow_serialization(self) -> None:
        """Workflow configs serialize to/from JSON."""
        workflow = DISCOVER_UNDERRATED_WORKFLOW
        json_str = workflow.model_dump_json()
        restored = AgentWorkflowConfig.model_validate_json(json_str)
        assert restored.name == "discover_underrated"
        assert len(restored.steps) == 5
