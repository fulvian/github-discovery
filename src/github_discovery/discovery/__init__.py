"""Discovery engine — Layer A / Gate 0."""

from __future__ import annotations

from github_discovery.discovery.code_search_channel import CodeSearchChannel
from github_discovery.discovery.curated_channel import CuratedChannel
from github_discovery.discovery.dependency_channel import DependencyChannel
from github_discovery.discovery.github_client import GitHubRestClient
from github_discovery.discovery.graphql_client import GitHubGraphQLClient
from github_discovery.discovery.orchestrator import DiscoveryOrchestrator
from github_discovery.discovery.pool import PoolManager
from github_discovery.discovery.registry_channel import RegistryChannel
from github_discovery.discovery.search_channel import SearchChannel
from github_discovery.discovery.seed_expansion import SeedExpansion
from github_discovery.discovery.types import ChannelResult, DiscoveryQuery, DiscoveryResult

__all__ = [
    "ChannelResult",
    "CodeSearchChannel",
    "CuratedChannel",
    "DependencyChannel",
    "DiscoveryOrchestrator",
    "DiscoveryQuery",
    "DiscoveryResult",
    "GitHubGraphQLClient",
    "GitHubRestClient",
    "PoolManager",
    "RegistryChannel",
    "SearchChannel",
    "SeedExpansion",
]
