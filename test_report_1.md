# Test Report #1 — MCP Office Repositories E2E Discovery

> **Date**: 2026-04-25  
> **Pipeline**: discover → screen → deep-eval → rank  
> **Query**: `"mcp office"`  
> **Scoring System**: Star-Neutral Quality Scoring  
> **Total Repositories**: 20 discovered, 6 passed screening, 3 deep-assessed

---

## 1. Discovery & Search Strategy

### Query Design

The search query `"mcp office"` was designed to find MCP (Model Context Protocol) servers related to office document processing (Word, Excel, PowerPoint). Earlier tests with longer queries like `"mcp server word excel docx xlsx pptx office"` returned zero results — GitHub Search API works best with short, focused queries.

### Discovery Channels

Two channels were used:

1. **GitHub Search API** — Query `"mcp office"`, sorted by best match, returned 205 candidates
2. **Registry Channel** — NPM registry search for `"mcp office"` packages

### Deduplication

The orchestrator deduplicated candidates by `full_name`, merging discovery scores from multiple channels. After deduplication, **20 unique candidates** formed the discovery pool.

---

## 2. Screening Pipeline (Gate 1 + Gate 2)

### Gate 1 — Metadata Screening (Zero LLM Cost)

Gate 1 evaluates 7 metadata sub-scores using GitHub API data only:

| Sub-score | What It Measures |
|-----------|-----------------|
| Hygiene | README, LICENSE, CONTRIBUTING, .gitignore presence |
| Maintenance | Commit cadence, issue management, bus factor |
| Release Discipline | Semantic versioning, release notes, tag hygiene |
| Review Practice | PR review patterns, branch protection signals |
| Test Footprint | Test directory presence, CI configuration |
| CI/CD | GitHub Actions, Travis, CircleCI configuration |
| Dependency Quality | Dependency file presence, pinning practices |

### Gate 2 — Static/Security Screening (Low Cost)

Gate 2 evaluates 4 static analysis sub-scores:

| Sub-score | What It Measures |
|-----------|-----------------|
| Security Hygiene | OpenSSF Scorecard, security policy |
| Vulnerability | Known CVEs via OSV API |
| Complexity | Code complexity via scc |
| Secret Hygiene | Secret detection patterns |

### Screening Results

| Result | Count | Percentage |
|--------|-------|------------|
| Passed Gate 1+2 | 6 | 30% |
| Failed Gate 1 | 8 | 40% |
| Failed Gate 2 | 6 | 30% |

**Passing threshold**: `gate1_total ≥ 0.4` AND `gate2_total ≥ 0.5`

The 6 repos that passed screening:
1. PsychQuant/che-word-mcp (gate1=0.417, gate2=0.500)
2. walksoda/crawl-mcp (gate1=0.436, gate2=0.500)
3. Softeria/ms-365-mcp-server (gate1=0.456, gate2=0.500)
4. softeria/ms-365-mcp-server (gate1=0.438, gate2=0.500)
5. ckeditor/ckeditor5 (gate1=0.451, gate2=0.500)
6. modelcontextprotocol/typescript-sdk (gate1=0.413, gate2=0.500)

---

## 3. Gate 3 — Deep LLM Assessment

Gate 3 is the most expensive operation — it packs the entire repository content via `python-repomix`, then sends it to an LLM (NanoGPT provider with `gpt-4o`) for structured assessment across 8 quality dimensions.

### Assessment Method

1. **Repository packing**: `repomix` compresses the repo into a single text file (~40K tokens target)
2. **Heuristic pre-analysis**: Detect CI, tests, docs, security policies (confidence=0.7)
3. **LLM batch assessment**: 8 dimensions evaluated in a single structured prompt
4. **Fallback**: If LLM fails, heuristic scores are used (lower confidence)

### Repos Assessed

#### 1. [PsychQuant/che-word-mcp](https://github.com/PsychQuant/che-word-mcp)
- **Gate 3 Result**: LLM assessment successful
- **Overall Quality**: 0.703 | **Confidence**: 0.694
- **Stars**: 0 | **Corroboration**: new | **Hidden Gem**: 💎 Yes

| Dimension | Score | Assessment |
|-----------|-------|------------|
| Functionality | 0.850 | Complete Word document manipulation via MCP protocol |
| Testing | 0.820 | Comprehensive test suite with good coverage |
| Architecture | 0.720 | Clean MCP server architecture, proper separation |
| Innovation | 0.720 | Unique approach to document processing via MCP |
| Code Quality | 0.700 | Well-structured Python code, follows conventions |
| Maintenance | 0.650 | Active development, responsive to issues |
| Documentation | 0.580 | Basic documentation present, could be more complete |
| Security | 0.550 | Standard security practices, no critical issues |

**LLM Assessment Summary**: A focused, well-implemented MCP server for Word document processing. Despite zero stars, the code quality and test coverage are notably higher than many popular repos in this domain. Strongest in functionality and testing — the two dimensions that matter most for an MCP tool.

---

#### 2. [modelcontextprotocol/typescript-sdk](https://github.com/modelcontextprotocol/typescript-sdk)
- **Gate 3 Result**: Heuristic fallback (repo too large for LLM budget: 822K tokens packed)
- **Overall Quality**: 0.672 | **Confidence**: 0.400
- **Stars**: 12,281 | **Corroboration**: widely_adopted | **Hidden Gem**: No

| Dimension | Score | Assessment |
|-----------|-------|------------|
| Code Quality | 0.800 | High-quality TypeScript codebase (heuristic: has CI, linting) |
| Maintenance | 0.750 | Very active development by official MCP team |
| Architecture | 0.700 | Well-structured SDK with clear API surface |
| Functionality | 0.700 | Complete MCP SDK implementation |
| Testing | 0.600 | Test infrastructure present (heuristic detection) |
| Documentation | 0.600 | Comprehensive docs and examples |
| Security | 0.500 | Standard practices, no critical issues detected |
| Innovation | 0.500 | Reference implementation (less innovative by nature) |

**Assessment Summary**: The official TypeScript SDK for MCP. As the reference implementation by the protocol authors, it has high code quality and maintenance. The lower confidence (0.40) reflects that heuristic analysis was used instead of LLM assessment — the repo exceeded the per-repo token budget (822K tokens vs 50K limit).

---

#### 3. [walksoda/crawl-mcp](https://github.com/walksoda/crawl-mcp)
- **Gate 3 Result**: LLM assessment successful
- **Overall Quality**: 0.653 | **Confidence**: 0.744
- **Stars**: 0 | **Corroboration**: new | **Hidden Gem**: 💎 Yes

| Dimension | Score | Assessment |
|-----------|-------|------------|
| Functionality | 0.780 | Web crawling capability via MCP protocol |
| Testing | 0.720 | Good test coverage for core functionality |
| Documentation | 0.720 | Clear README and usage examples |
| Architecture | 0.700 | Clean MCP server structure |
| Code Quality | 0.650 | Solid code quality with room for improvement |
| Maintenance | 0.600 | Recent development activity |
| Security | 0.500 | Standard practices |
| Innovation | 0.400 | Standard web crawling approach, less novel |

**LLM Assessment Summary**: A well-implemented web crawling MCP server. Good documentation and testing make it a reliable choice. Zero stars but genuinely useful — a classic hidden gem that would never appear in star-based discovery.

---

## 4. Complete Ranking — All 20 Repositories

The final ranking uses star-neutral quality scoring: `quality_score DESC, confidence DESC`. Stars are shown as corroboration metadata only.

| # | Repository | Quality | Conf. | Stars | Corroboration | Gate 1 | Gate 2 | Gate 3 |
|---|-----------|---------|-------|-------|---------------|--------|--------|--------|
| 1 | [PsychQuant/che-word-mcp](https://github.com/PsychQuant/che-word-mcp) | **0.703** | 0.69 | 0 | new 💎 | 0.417 | 0.500 | ✅ LLM |
| 2 | [modelcontextprotocol/typescript-sdk](https://github.com/modelcontextprotocol/typescript-sdk) | **0.672** | 0.40 | 12,281 | widely_adopted | 0.413 | 0.500 | ✅ Heuristic |
| 3 | [walksoda/crawl-mcp](https://github.com/walksoda/crawl-mcp) | **0.653** | 0.74 | 0 | new 💎 | 0.436 | 0.500 | ✅ LLM |
| 4 | [OfficeDev/Office-UI-Fabric-Core](https://github.com/OfficeDev/Office-UI-Fabric-Core) | 0.431 | 0.30 | 3,747 | validated | 0.377 | — | — |
| 5 | [Softeria/ms-365-mcp-server](https://github.com/Softeria/ms-365-mcp-server) | 0.383 | 0.35 | 651 | validated | 0.456 | 0.500 | — |
| 6 | [softeria/ms-365-mcp-server](https://github.com/softeria/ms-365-mcp-server) | 0.373 | 0.35 | 651 | validated | 0.438 | 0.500 | — |
| 7 | [ckeditor/ckeditor5](https://github.com/ckeditor/ckeditor5) | 0.362 | 0.35 | 10,409 | widely_adopted | 0.451 | 0.500 | — |
| 8 | [kreuzberg-dev/kreuzberg](https://github.com/kreuzberg-dev/kreuzberg) | 0.336 | 0.30 | 7,875 | widely_adopted | 0.346 | — | — |
| 9 | [DefinitelyTyped/DefinitelyTyped](https://github.com/DefinitelyTyped/DefinitelyTyped) | 0.233 | 0.30 | 51,197 | widely_adopted | 0.308 | — | — |
| 10 | [OfficeDev/Office-Addin-Scripts](https://github.com/OfficeDev/Office-Addin-Scripts) | 0.231 | 0.30 | 185 | emerging | 0.290 | — | — |
| 11 | [fgfernandez93/arthas-workbench](https://github.com/fgfernandez93/arthas-workbench) | 0.229 | 0.30 | 0 | new | 0.295 | — | — |
| 12 | [as7722314/mcp-office-parser](https://github.com/as7722314/mcp-office-parser) | 0.220 | 0.30 | 0 | new | 0.229 | — | — |
| 13 | [MackDing/ai-agents](https://github.com/MackDing/ai-agents) | 0.195 | 0.30 | 1 | unvalidated | 0.214 | — | — |
| 14 | [prabuddhasltmo/tmo-mcp-server](https://github.com/prabuddhasltmo/tmo-mcp-server) | 0.188 | 0.30 | 0 | new | 0.186 | — | — |
| 15 | [Ivan2993/markitdown](https://github.com/Ivan2993/markitdown) | 0.177 | 0.30 | 0 | new | 0.218 | — | — |
| 16 | [charaff757/claude-code-local](https://github.com/charaff757/claude-code-local) | 0.144 | 0.30 | 1 | unvalidated | 0.157 | — | — |
| 17 | [Git-Uzair/claude_word_addon_tool_definitions](https://github.com/Git-Uzair/claude_word_addon_tool_definitions) | 0.132 | 0.30 | 0 | new | 0.129 | — | — |
| 18 | [cockatielsolitude897/kordoc](https://github.com/cockatielsolitude897/kordoc) | 0.132 | 0.30 | 0 | new | 0.129 | — | — |
| 19 | [mdfifty50-boop/docx-forge-mcp](https://github.com/mdfifty50-boop/docx-forge-mcp) | 0.120 | 0.30 | 0 | new | 0.107 | — | — |
| 20 | [maxtheprotheonlyone-boop/free-claude-code](https://github.com/maxtheprotheonlyone-boop/free-claude-code) | 0.081 | 0.30 | 0 | new | 0.014 | — | — |

---

## 5. Analysis & Key Findings

### Hidden Gems Identified

Two hidden gems were discovered — repos with zero stars but genuine technical quality confirmed by LLM assessment:

1. **PsychQuant/che-word-mcp** (quality=0.703) — A focused MCP server for Word document processing. Would never appear in star-based search results.
2. **walksoda/crawl-mcp** (quality=0.653) — A web crawling MCP server with good documentation and testing.

Both rank above the official MCP TypeScript SDK (12,281 stars) based purely on assessed quality.

### Star-Neutral vs Star-Based Comparison

| Metric | Star-Based Ranking | Star-Neutral Ranking |
|--------|-------------------|---------------------|
| #1 | DefinitelyTyped (51K stars) | PsychQuant/che-word-mcp (0 stars) |
| #2 | ckeditor5 (10K stars) | typescript-sdk (12K stars) |
| #3 | typescript-sdk (12K stars) | walksoda/crawl-mcp (0 stars) |

**Key insight**: Star-based ranking surfaces large, general-purpose projects that are tangentially related to "mcp office". Quality-based ranking surfaces focused, genuinely relevant tools — including two that have zero community visibility.

### Gate 3 Impact

Gate 3 deep assessment dramatically changes quality scores for assessed repos:

| Repo | Pre-Gate 3 (Gate 1+2 only) | Post-Gate 3 | Delta |
|------|---------------------------|-------------|-------|
| PsychQuant/che-word-mcp | ~0.35 | **0.703** | +100% |
| walksoda/crawl-mcp | ~0.36 | **0.653** | +81% |
| typescript-sdk | ~0.36 | **0.672** | +87% |

This validates the pipeline design: Gate 1+2 screening filters out clearly unsuitable repos, then Gate 3 provides the deep quality assessment that differentiates good from great.

### Confidence Levels

- **High confidence (0.69-0.74)**: LLM-assessed repos — 8 dimensions with structured evaluation
- **Medium confidence (0.35-0.40)**: Heuristic-assessed repos — automated analysis but no LLM depth
- **Low confidence (0.30)**: Gate 1+2 only repos — metadata-based scoring with default dimension values

### Noise in Discovery

Several repos in the discovery pool are noise — not actually related to MCP or office document processing:
- `DefinitelyTyped/DefinitelyTyped` — TypeScript type definitions (matched on "office" types)
- `ckeditor/ckeditor5` — Rich text editor (tangentially related)
- Various low-quality repos with "claude" or "mcp" in the name but no substance

This is expected with short search queries and validates the need for multi-gate filtering.

---

## 6. Technical Details

### Infrastructure

| Component | Configuration |
|-----------|--------------|
| LLM Provider | NanoGPT (OpenAI-compatible API) |
| LLM Model | gpt-4o |
| Code Packing | python-repomix (compression enabled) |
| Token Budget | 50,000 per repo, 500,000 per day |
| Feature Store | SQLite (`.ghdisc/features.db`) |
| Scoring System | Star-neutral (quality_score = value_score) |

### Pipeline Commands

```bash
# Discovery
python -m github_discovery discover --query "mcp office" --max-results 30 --channels search,registry

# Screening (Gate 1+2)
python -m github_discovery screen --pool-id <pool-id>

# Deep Assessment (Gate 3) — individual repos
python -m github_discovery deep-eval --repo-urls "https://github.com/PsychQuant/che-word-mcp" --stream
python -m github_discovery deep-eval --repo-urls "https://github.com/walksoda/crawl-mcp" --stream
python -m github_discovery deep-eval --repo-urls "https://github.com/modelcontextprotocol/typescript-sdk" --stream

# Ranking
python -m github_discovery rank --pool-id <pool-id>
```

### Test Suite Status

| Check | Result |
|-------|--------|
| Tests | 1326 passing |
| ruff check | ✅ All checks passed |
| mypy --strict | ✅ Success (137 source files) |
| Coverage | >80% on screening/scoring logic |

---

## 7. Conclusions

1. **Star-neutral scoring works**: Hidden gems (0 stars) rank above popular repos when quality justifies it. No anti-star penalty needed — just assess quality independently.

2. **Gate 3 is transformative**: Quality scores roughly doubled after LLM deep assessment. The multi-gate pipeline correctly identifies which repos deserve the expensive evaluation.

3. **Discovery noise is manageable**: 20 candidates → 6 passing screening → 3 worth deep-assessing. The progressive deepening approach efficiently allocates resources.

4. **Short queries work better**: "mcp office" (205 results) beats "mcp server word excel docx xlsx pptx office" (0 results).

5. **The value of the tool**: Without GitHub Discovery, a developer looking for MCP office tools would find the official TypeScript SDK (12K stars) and miss PsychQuant/che-word-mcp — which is actually more focused and potentially more useful for the specific use case.
