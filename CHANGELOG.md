# Changelog

All notable changes to GitHub Discovery will be documented in this file.

## [0.3.0-beta] — 2026-04-27

### Added
- MCP server: /health endpoint, API key auth (GHDISC_MCP_API_KEYS)
- MCP server: graceful shutdown (SIGTERM handler)
- MCP server: session pruning (ghdisc db sessions, 30d TTL)
- Anti-bias invariant tests (28 tests, INV-1 through INV-10)
- Adaptive activity filter for discovery (domain-aware pushed:> threshold)
- Recency boost for recently pushed repos
- Channel observability (structured logging per channel)
- Clone reuse across Gate 2 + Gate 3 (CloneManager)
- OSV batch query adoption (POST /v1/querybatch)
- Registry channels: crates.io, Maven Central
- GitHub Topic search fallback for Curated channel
- Seed expansion auto-seed from query
- Docker image (multi-stage distroless)
- .github/workflows/release.yml (PyPI + Docker)
- SECURITY.md, CODEOWNERS
- pip-audit in CI

### Changed
- Version bumped from 0.1.0-alpha to 0.3.0-beta
- CLI aliases: github-discovery, github-discovery-mcp
- DiscoveryQuery now has auto_seed field
- ChannelResult now has errors field
- DomainProfile now has activity_threshold_days

### Fixed
- 1773 tests passing (ruff clean, mypy --strict clean)

## [0.1.0-alpha] — 2026-04-22

### Added
- Initial release
- 4-gate scoring pipeline
- MCP-native interface (16 tools, 4 resources, 5 prompts)
- CLI interface (ghdisc)
- Star-neutral scoring
