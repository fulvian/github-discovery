"""GitHub Discovery data models.

This package defines the complete vocabulary of the GitHub Discovery domain:
- Enums: DomainType, GateLevel, ScoreDimension, DiscoveryChannel, CandidateStatus
- Candidate: RepoCandidate, CandidatePool (flow through all gates)
- Screening: Gate 1 (metadata) and Gate 2 (static/security) sub-scores and results
- Assessment: Gate 3 (deep LLM) dimension scores and results
- Scoring: ScoreResult, ValueScore, RankedRepo, ExplainabilityReport, DomainProfile
- Features: RepoFeatures (caching/dedup by commit SHA)
- API: Request/response models for REST interface
- Agent: MCPToolResult, DiscoverySession (MCP integration)
- Session: SessionState, SessionConfig, ProgressInfo
- MCP Spec: MCPToolSpec, AgentWorkflowConfig (tool definitions)
"""

from __future__ import annotations

from github_discovery.models.agent import DiscoverySession, MCPToolResult
from github_discovery.models.api import (
    AssessmentRequest,
    AssessmentResponse,
    DiscoveryQuery,
    DiscoveryResponse,
    ExportFormat,
    ExportRequest,
    ExportResponse,
    PaginatedResponse,
    PaginationParams,
    RankingQuery,
    RankingResponse,
    ScreeningRequest,
    ScreeningResponse,
)
from github_discovery.models.assessment import (
    DeepAssessmentResult,
    DimensionScore,
    TokenUsage,
)
from github_discovery.models.candidate import CandidatePool, RepoCandidate
from github_discovery.models.enums import (
    CandidateStatus,
    DiscoveryChannel,
    DomainType,
    GateLevel,
    ScoreDimension,
)
from github_discovery.models.features import FeatureStoreKey, RepoFeatures
from github_discovery.models.mcp_spec import (
    DEEP_ASSESS_SPEC,
    DISCOVER_REPOS_SPEC,
    DISCOVER_UNDERRATED_WORKFLOW,
    QUICK_QUALITY_CHECK_WORKFLOW,
    RANK_REPOS_SPEC,
    SCREEN_CANDIDATES_SPEC,
    AgentWorkflowConfig,
    MCPOutputFormat,
    MCPToolSpec,
    WorkflowStep,
)
from github_discovery.models.scoring import (
    CLI_PROFILE,
    DEFAULT_PROFILE,
    DEVOPS_PROFILE,
    DOMAIN_PROFILES,
    LIBRARY_PROFILE,
    DomainProfile,
    ExplainabilityReport,
    RankedRepo,
    ScoreResult,
    get_domain_profile,
)
from github_discovery.models.screening import (
    CiCdScore,
    ComplexityScore,
    DependencyQualityScore,
    HygieneScore,
    MaintenanceScore,
    MetadataScreenResult,
    ReleaseDisciplineScore,
    ReviewPracticeScore,
    ScreeningResult,
    SecretHygieneScore,
    SecurityHygieneScore,
    StaticScreenResult,
    SubScore,
    TestFootprintScore,
    VulnerabilityScore,
)
from github_discovery.models.session import (
    ProgressInfo,
    SessionConfig,
    SessionState,
    SessionStatus,
)

__all__ = [
    # Scoring (Layer D)
    "CLI_PROFILE",
    # MCP Spec
    "DEEP_ASSESS_SPEC",
    "DEFAULT_PROFILE",
    "DEVOPS_PROFILE",
    "DISCOVER_REPOS_SPEC",
    "DISCOVER_UNDERRATED_WORKFLOW",
    "DOMAIN_PROFILES",
    "LIBRARY_PROFILE",
    "QUICK_QUALITY_CHECK_WORKFLOW",
    "RANK_REPOS_SPEC",
    "SCREEN_CANDIDATES_SPEC",
    "AgentWorkflowConfig",
    # API
    "AssessmentRequest",
    "AssessmentResponse",
    # Candidate
    "CandidatePool",
    # Enums
    "CandidateStatus",
    # Screening (Gate 1 + Gate 2)
    "CiCdScore",
    "ComplexityScore",
    # Assessment (Gate 3)
    "DeepAssessmentResult",
    "DependencyQualityScore",
    "DimensionScore",
    "DiscoveryChannel",
    "DiscoveryQuery",
    "DiscoveryResponse",
    # Agent
    "DiscoverySession",
    "DomainProfile",
    "DomainType",
    "ExplainabilityReport",
    "ExportFormat",
    "ExportRequest",
    "ExportResponse",
    # Feature Store
    "FeatureStoreKey",
    "GateLevel",
    "HygieneScore",
    "MCPOutputFormat",
    "MCPToolResult",
    "MCPToolSpec",
    "MaintenanceScore",
    "MetadataScreenResult",
    "PaginatedResponse",
    "PaginationParams",
    # Session
    "ProgressInfo",
    "RankedRepo",
    "RankingQuery",
    "RankingResponse",
    "ReleaseDisciplineScore",
    "RepoCandidate",
    "RepoFeatures",
    "ReviewPracticeScore",
    "ScoreDimension",
    "ScoreResult",
    "ScreeningRequest",
    "ScreeningResponse",
    "ScreeningResult",
    "SecretHygieneScore",
    "SecurityHygieneScore",
    "SessionConfig",
    "SessionState",
    "SessionStatus",
    "StaticScreenResult",
    "SubScore",
    "TestFootprintScore",
    "TokenUsage",
    "VulnerabilityScore",
    "WorkflowStep",
    "get_domain_profile",
]
