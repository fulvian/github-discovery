# GitHub Discovery — Phase 3 Implementation Plan

## Meta

- **Stato**: Draft v1
- **Data**: 2026-04-22
- **Riferimento roadmap**: `docs/roadmaps/github-discovery_foundation_roadmap.md` — Phase 3
- **Riferimento blueprint**: `docs/foundation/github-discovery_foundation_blueprint.md` — §6 (Layer B), §16.2-16.5
- **Riferimento wiki**: `docs/llm-wiki/wiki/` — articoli su screening gates, tiered pipeline, GitHub API patterns, tech stack
- **Durata stimata**: 2-3 settimane
- **Milestone**: M2 — Screening MVP (Gate 1+2 operativi, hard gate enforcement, 4+ tool integrati)
- **Dipendenza**: Phase 0+1+2 completate (320 tests passing, `make ci` verde)

---

## Indice

1. [Obiettivo](#1-obiettivo)
2. [Task Overview](#2-task-overview)
3. [Architettura del modulo screening](#3-architettura-del-modulo-screening)
4. [Task 3.1 — Gate 1 Metadata Screening Engine](#4-task-31--gate-1-metadata-screening-engine)
5. [Task 3.2 — Hygiene Files Checker](#5-task-32--hygiene-files-checker)
6. [Task 3.3 — CI/CD Detection](#6-task-33--cicd-detection)
7. [Task 3.4 — Test Footprint Analyzer](#7-task-34--test-footprint-analyzer)
8. [Task 3.5 — Release Discipline Scorer](#8-task-35--release-discipline-scorer)
9. [Task 3.6 — Maintenance Signal Analyzer](#9-task-36--maintenance-signal-analyzer)
10. [Task 3.7 — Issue/PR Practices Scorer](#10-task-37--issuepr-practices-scorer)
11. [Task 3.8 — Dependency Quality Scorer](#11-task-38--dependency-quality-scorer)
12. [Task 3.9 — Gate 2 Static/Security Screening Engine](#12-task-39--gate-2-staticsecurity-screening-engine)
13. [Task 3.10 — OpenSSF Scorecard Integration](#13-task-310--openssf-scorecard-integration)
14. [Task 3.11 — Secret Hygiene Check](#14-task-311--secret-hygiene-check)
15. [Task 3.12 — Dependency Vulnerability Scan](#15-task-312--dependency-vulnerability-scan)
16. [Task 3.13 — Code Complexity Metrics](#16-task-313--code-complexity-metrics)
17. [Task 3.14 — Screening Orchestrator & Gating Policy](#17-task-314--screening-orchestrator--gating-policy)
18. [Sequenza di implementazione](#18-sequenza-di-implementazione)
19. [Test plan](#19-test-plan)
20. [Criteri di accettazione](#20-criteri-di-accettazione)
21. [Rischi e mitigazioni](#21-rischi-e-mitigazioni)
22. [Verifica Context7 completata](#22-verifica-context7-completata)

---

## 1) Obiettivo

Implementare Gate 1 (metadata screening, zero LLM cost) e Gate 2 (static/security screening, zero o low cost) per ridurre il pool di candidati ai soli meritevoli di deep assessment (Gate 3).

Al completamento della Phase 3:

- Gate 1 operativo con 7 sub-scores (hygiene, maintenance, release discipline, review practices, test footprint, CI/CD, dependency quality)
- Gate 2 operativo con 4 sub-scores (security hygiene via Scorecard, vulnerability via OSV, complexity via scc, secret hygiene via gitleaks)
- Hard gate enforcement: nessun candidato passa a Gate 3 senza Gate 1 + Gate 2 pass
- Almeno 4 tool esterni integrati (Scorecard, gitleaks, OSV, scc)
- Graceful degradation: se un tool esterno fallisce, il pipeline continua con heuristic fallback e confidence più bassa
- Screening riproducibile: stessi input → stessi output (determinismo)
- Tutti i moduli passano `mypy --strict` e `ruff check`
- Test coverage >80% sulla logica di screening

### Regola critica (Blueprint §16.5)

> Nessun deep-scan LLM sotto soglia minima Gate 1+2. Implementare come hard constraint nel codice.

---

## 2) Task Overview

| Task ID | Task | Priorità | Dipendenze | Output verificabile |
|---------|------|----------|------------|---------------------|
| 3.1 | Gate 1 Metadata Screening Engine | Critica | Phase 2 (GitHubRestClient) | Orchestrazione sub-scores Gate 1, gating policy |
| 3.2 | Hygiene Files Checker | Critica | 3.1 | LICENSE, CONTRIBUTING.md, SECURITY.md, etc. scoring |
| 3.3 | CI/CD Detection | Alta | 3.1 | .github/workflows, CI badge detection |
| 3.4 | Test Footprint Analyzer | Alta | 3.1 | Test dir/pattern detection, test/source ratio |
| 3.5 | Release Discipline Scorer | Alta | 3.1 | Semver tagging, release cadence scoring |
| 3.6 | Maintenance Signal Analyzer | Critica | 3.1 | PyDriller commit churn, contributors, recency |
| 3.7 | Issue/PR Practices Scorer | Media | 3.1 | PR template, review evidence, label usage |
| 3.8 | Dependency Quality Scorer | Alta | 3.1 | Lockfile, pinning, dependabot/renovate config |
| 3.9 | Gate 2 Static/Security Screening Engine | Critica | 3.1 | Orchestrazione sub-scores Gate 2, security gating |
| 3.10 | OpenSSF Scorecard Integration | Critica | 3.9 | Scorecard API → SecurityHygieneScore |
| 3.11 | Secret Hygiene Check | Alta | 3.9 | gitleaks subprocess → SecretHygieneScore |
| 3.12 | Dependency Vulnerability Scan | Alta | 3.9 | OSV API query → VulnerabilityScore |
| 3.13 | Code Complexity Metrics | Media | 3.9 | scc subprocess → ComplexityScore |
| 3.14 | Screening Orchestrator & Gating Policy | Critica | 3.1-3.13 | Policy engine, hard gate enforcement, batch screening |

---

## 3) Architettura del modulo screening

### Struttura directory

```
src/github_discovery/screening/
├── __init__.py                # Export pubblici del package screening
├── gate1_metadata.py          # Gate 1 orchestration engine
├── gate2_static.py            # Gate 2 orchestration engine
├── hygiene.py                 # Hygiene files checker
├── ci_cd.py                   # CI/CD detection and scoring
├── test_footprint.py          # Test infrastructure analyzer
├── release_discipline.py      # Release/tagging practices scorer
├── maintenance.py             # Maintenance signal analyzer (PyDriller)
├── practices.py               # Issue/PR practices scorer
├── dependency_quality.py      # Dependency management quality scorer
├── scorecard_adapter.py       # OpenSSF Scorecard API integration
├── secrets_check.py           # gitleaks subprocess integration
├── osv_adapter.py             # OSV API dependency vulnerability scan
├── complexity.py              # scc/cloc code complexity metrics
├── orchestrator.py            # Screening orchestrator + Policy Engine
├── subprocess_runner.py       # Shared async subprocess execution utility
└── types.py                   # Tipi condivisi screening

tests/
├── unit/
│   └── screening/
│       ├── test_gate1_metadata.py
│       ├── test_gate2_static.py
│       ├── test_hygiene.py
│       ├── test_ci_cd.py
│       ├── test_test_footprint.py
│       ├── test_release_discipline.py
│       ├── test_maintenance.py
│       ├── test_practices.py
│       ├── test_dependency_quality.py
│       ├── test_scorecard_adapter.py
│       ├── test_secrets_check.py
│       ├── test_osv_adapter.py
│       ├── test_complexity.py
│       ├── test_orchestrator.py
│       ├── test_subprocess_runner.py
│       └── conftest.py         # Shared fixtures
└── integration/
    └── screening/
        └── test_screening_e2e.py  # End-to-end with real APIs (marked @pytest.mark.integration)
```

### Modelli esistenti riutilizzati (Phase 1)

Da `models/screening.py` — tutti già implementati e testati:

| Modello | Utilizzo in Phase 3 |
|---------|---------------------|
| `SubScore` | Base pattern per tutti i sub-scores (value, weight, details, confidence, notes) |
| `HygieneScore` | Output di `screening/hygiene.py` |
| `MaintenanceScore` | Output di `screening/maintenance.py` |
| `ReleaseDisciplineScore` | Output di `screening/release_discipline.py` |
| `ReviewPracticeScore` | Output di `screening/practices.py` |
| `TestFootprintScore` | Output di `screening/test_footprint.py` |
| `CiCdScore` | Output di `screening/ci_cd.py` |
| `DependencyQualityScore` | Output di `screening/dependency_quality.py` |
| `MetadataScreenResult` | Output composito Gate 1 con `compute_total()` |
| `SecurityHygieneScore` | Output di `screening/scorecard_adapter.py` |
| `VulnerabilityScore` | Output di `screening/osv_adapter.py` |
| `ComplexityScore` | Output di `screening/complexity.py` |
| `SecretHygieneScore` | Output di `screening/secrets_check.py` |
| `StaticScreenResult` | Output composito Gate 2 con `compute_total()` |
| `ScreeningResult` | Risultato combinato Gate 1+2 con `can_proceed_to_gate3` |

### Modelli Phase 2 riutilizzati

| Modello | File | Utilizzo |
|---------|------|----------|
| `RepoCandidate` | `models/candidate.py` | Input dello screening — repo da valutare |
| `GitHubRestClient` | `discovery/github_client.py` | HTTP client per GitHub API (rate limit, auth, pagination) |
| `GitHubSettings` | `config.py` | Token, URLs, timeout |
| `ScreeningSettings` | `config.py` | `min_gate1_score`, `min_gate2_score`, `hard_gate_enforcement` |
| `ScreeningError` | `exceptions.py` | Errore dominio screening |
| `HardGateViolationError` | `exceptions.py` | Violazione hard gate |

### Tipi nuovi necessari (types.py)

```python
# Tipi condivisi per il screening engine — definiti qui per evitare
# import circolari tra i moduli del package.

class RepoContext(BaseModel):
    """Context gathered about a repo for screening decisions.
    
    Collected via GitHub API calls before/during screening.
    Contains all metadata needed by Gate 1 sub-score checkers.
    """
    candidate: RepoCandidate
    repo_metadata: dict[str, object]          # Raw /repos/{owner}/{repo} response
    repo_contents: list[str]                  # Root directory listing (filenames)
    recent_releases: list[dict[str, object]]  # Last 10 releases from API
    recent_commits: list[dict[str, object]]   # Last 30 commits from API
    recent_issues: list[dict[str, object]]    # Last 30 issues from API
    recent_prs: list[dict[str, object]]       # Last 30 PRs from API
    languages: dict[str, int]                 # Language breakdown {name: bytes}
    topics: list[str]                         # Repository topics

class ScreeningContext(BaseModel):
    """Full context for a screening operation on a pool."""
    pool_id: str
    candidates: list[RepoCandidate]
    gate_level: GateLevel                     # "1" or "2" or "both"
    min_gate1_score: float = 0.4
    min_gate2_score: float = 0.5
    session_id: str | None = None

class SubprocessResult(BaseModel):
    """Result of an async subprocess execution."""
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
```

### Flusso dati

```
RepoCandidate (from PoolManager)
    │
    ├── [Context Gathering] ── GitHubRestClient.get() × N endpoints
    │       ├── GET /repos/{owner}/{repo}               → repo_metadata
    │       ├── GET /repos/{owner}/{repo}/contents/      → repo_contents (root dir)
    │       ├── GET /repos/{owner}/{repo}/releases       → recent_releases
    │       ├── GET /repos/{owner}/{repo}/commits        → recent_commits
    │       ├── GET /repos/{owner}/{repo}/issues         → recent_issues
    │       ├── GET /repos/{owner}/{repo}/pulls          → recent_prs
    │       └── GET /repos/{owner}/{repo}/languages      → languages
    │
    ├── [Gate 1] ── Gate1MetadataScreener.screen(ctx)
    │       ├── HygieneChecker.score(ctx)          → HygieneScore
    │       ├── MaintenanceAnalyzer.score(ctx)     → MaintenanceScore
    │       ├── ReleaseDisciplineScorer.score(ctx)  → ReleaseDisciplineScore
    │       ├── PracticesScorer.score(ctx)          → ReviewPracticeScore
    │       ├── TestFootprintAnalyzer.score(ctx)    → TestFootprintScore
    │       ├── CiCdDetector.score(ctx)             → CiCdScore
    │       └── DependencyQualityScorer.score(ctx)  → DependencyQualityScore
    │       → MetadataScreenResult (gate1_total, gate1_pass)
    │
    ├── [Gate 2] ── Gate2StaticScreener.screen(ctx) [only if gate1_pass]
    │       ├── ScorecardAdapter.score(candidate)    → SecurityHygieneScore
    │       ├── OsvAdapter.score(candidate)           → VulnerabilityScore
    │       ├── ComplexityAnalyzer.score(candidate)   → ComplexityScore
    │       └── SecretsChecker.score(candidate)       → SecretHygieneScore
    │       → StaticScreenResult (gate2_total, gate2_pass)
    │
    └── [Screening Result] ── ScreeningResult
            ├── gate1: MetadataScreenResult
            ├── gate2: StaticScreenResult
            └── can_proceed_to_gate3: bool (hard gate)
```

---

## 4) Task 3.1 — Gate 1 Metadata Screening Engine

### Obiettivo

Motore di orchestrazione Gate 1 che coordina i 7 sub-score checkers, raccoglie il contesto necessario via GitHub API, e produce `MetadataScreenResult`.

### Design

```python
# screening/gate1_metadata.py

class Gate1MetadataScreener:
    """Gate 1 — Metadata screening engine (zero LLM cost).
    
    Orchestrates 7 sub-score checkers using repository metadata
    from GitHub API. All checks are zero-cost (API calls only,
    no LLM, no clone, no external tools).
    """

    def __init__(
        self,
        rest_client: GitHubRestClient,
        settings: ScreeningSettings,
    ) -> None: ...

    async def gather_context(
        self,
        candidate: RepoCandidate,
    ) -> RepoContext:
        """Gather all metadata needed for Gate 1 scoring.
        
        Makes parallel API calls to collect: repo metadata, contents,
        releases, commits, issues, PRs, languages.
        Uses asyncio.gather with rate limit awareness.
        """
        ...

    async def screen(
        self,
        candidate: RepoCandidate,
        *,
        threshold: float | None = None,    # Override default threshold
    ) -> MetadataScreenResult:
        """Screen a single candidate through Gate 1.
        
        1. Gather context via GitHub API
        2. Run all 7 sub-score checkers
        3. Compute weighted composite (gate1_total)
        4. Apply threshold → gate1_pass
        5. Return MetadataScreenResult
        """
        ...

    async def screen_batch(
        self,
        candidates: list[RepoCandidate],
        *,
        threshold: float | None = None,
        max_concurrent: int = 5,
    ) -> list[MetadataScreenResult]:
        """Screen a batch of candidates with concurrency control.
        
        Uses asyncio.Semaphore for rate limit safety.
        """
        ...
```

### Implementazione dettagliata

1. **Context gathering**: Parallelo con `asyncio.gather` e `Semaphore(max_concurrent)`:
   - `GET /repos/{owner}/{repo}` → metadata base (già in RepoCandidate, ma refresh per commit_sha)
   - `GET /repos/{owner}/{repo}/contents/` → root directory listing (nomi file per hygiene, CI, test detection)
   - `GET /repos/{owner}/{repo}/releases?per_page=10` → ultimi 10 releases per release discipline
   - `GET /repos/{owner}/{repo}/commits?per_page=30` → ultimi 30 commits per maintenance
   - `GET /repos/{owner}/{repo}/issues?state=all&per_page=30` → issues per practices
   - `GET /repos/{owner}/{repo}/pulls?state=all&per_page=30` → PRs per review practices
   - `GET /repos/{owner}/{repo}/languages` → breakdown linguaggi
2. **Sub-score execution**: Ogni checker riceve `RepoContext` e ritorna il suo sub-score
3. **Composite computation**: Usa `MetadataScreenResult.compute_total()` (già implementato)
4. **Threshold application**: `gate1_pass = gate1_total >= threshold` (default 0.4)
5. **Error isolation**: Fallimento di un sub-score → sub-score con value=0.0, confidence=0.0, notes=["Error: ..."]

### Test plan

- `test_gate1_metadata.py`:
  - `test_screen_returns_metadata_result`: Mock context → MetadataScreenResult con 7 sub-scores
  - `test_screen_computes_gate1_total`: Verifica compute_total() → gate1_total corretto
  - `test_screen_applies_threshold_pass`: Score sopra threshold → gate1_pass=True
  - `test_screen_applies_threshold_fail`: Score sotto threshold → gate1_pass=False
  - `test_screen_custom_threshold`: Override threshold via parametro
  - `test_gather_context_collects_all`: Mock 7 API calls → RepoContext completo
  - `test_gather_context_rate_limit_aware`: Mock rate limit → backoff
  - `test_screen_batch_concurrent`: Mock 5 candidati → tutti screenati
  - `test_screen_error_isolation`: Mock 1 sub-score fallisce → resto continua
  - `test_screen_archived_repo_auto_fail`: Repo archiviato → gate1_pass=False

### Criterio di verifica

```bash
pytest tests/unit/screening/test_gate1_metadata.py -v   # 10 tests passing
mypy src/github_discovery/screening/gate1_metadata.py --strict
```

---

## 5) Task 3.2 — Hygiene Files Checker

### Obiettivo

Verificare presenza e qualità dei file di igiene del repository: LICENSE, CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md, CHANGELOG.md, README.md.

### Design

```python
# screening/hygiene.py

# Hygiene files to check with expected paths and scoring weights
_HYGIENE_FILES: dict[str, dict[str, object]] = {
    "license": {
        "paths": ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"],
        "weight": 0.25,
        "required": True,
        "description": "Valid open-source license (SPDX)",
    },
    "readme": {
        "paths": ["README.md", "README.rst", "README.txt", "README"],
        "weight": 0.20,
        "required": True,
        "description": "README with minimum content",
    },
    "contributing": {
        "paths": ["CONTRIBUTING.md", "CONTRIBUTING.rst", ".github/CONTRIBUTING.md"],
        "weight": 0.15,
        "required": False,
        "description": "Contributing guidelines",
    },
    "code_of_conduct": {
        "paths": ["CODE_OF_CONDUCT.md", ".github/CODE_OF_CONDUCT.md"],
        "weight": 0.10,
        "required": False,
        "description": "Code of Conduct",
    },
    "security": {
        "paths": ["SECURITY.md", ".github/SECURITY.md", "SECURITY.txt"],
        "weight": 0.15,
        "required": False,
        "description": "Security policy",
    },
    "changelog": {
        "paths": ["CHANGELOG.md", "CHANGELOG.rst", "CHANGES.md", "HISTORY.md"],
        "weight": 0.15,
        "required": False,
        "description": "Changelog/release notes",
    },
}

class HygieneChecker:
    """Checks presence and quality of repository hygiene files.
    
    Uses repo contents listing (already in RepoContext) to detect files.
    LICENSE gets additional SPDX validation via repo_metadata.license_info.
    README gets a minimum-content check (non-trivial content).
    """

    def score(self, ctx: RepoContext) -> HygieneScore: ...
```

### Implementazione dettagliata

1. **File detection**: Match `repo_contents` (root filenames) contro i path attesi. Case-insensitive matching.
2. **LICENSE quality**: Se `repo_metadata.license_info.spdx_id` presente e non "NOASSERTION" → full score per license
3. **README quality**: Se presente ma vuoto (< 100 chars) → score parziale (0.3 invece di 1.0)
4. **Weighted composite**: Ogni file trovato contribuisce `file_weight * quality` al totale
5. **Details**: Dict `{license: True, readme: True, ...}` indicando quali file sono stati trovati
6. **Confidence**: 1.0 se contents listing disponibile, 0.5 se basato solo su metadata (listing parziale)

### Test plan

- `test_hygiene.py`:
  - `test_all_hygiene_files_present`: Tutti i file → score 1.0
  - `test_only_required_files_present`: LICENSE + README → score parziale
  - `test_no_hygiene_files`: Nessun file → score 0.0
  - `test_license_spdx_validation`: LICENSE con SPDX valido → full score
  - `test_license_noassertion`: LICENSE con spdx_id="NOASSERTION" → score parziale
  - `test_readme_minimal_content`: README < 100 chars → score ridotto
  - `test_case_insensitive_matching`: "license" match "LICENSE"
  - `test_hygiene_details_list_files_found`: Details dict elenca file trovati

### Criterio di verifica

```bash
pytest tests/unit/screening/test_hygiene.py -v   # 8 tests passing
```

---

## 6) Task 3.3 — CI/CD Detection

### Obiettivo

Rilevare presenza e qualità di configurazioni CI/CD: GitHub Actions, Travis CI, CircleCI, GitLab CI, Jenkins.

### Design

```python
# screening/ci_cd.py

_CI_CONFIG_PATHS: dict[str, list[str]] = {
    "github_actions": [".github/workflows/"],
    "travis": [".travis.yml"],
    "circleci": [".circleci/config.yml"],
    "gitlab_ci": [".gitlab-ci.yml"],
    "jenkins": ["Jenkinsfile"],
}

class CiCdDetector:
    """Detects CI/CD pipelines and evaluates their configuration.
    
    Primary signal: .github/workflows/ presence (most common).
    Secondary: CI badge in README, config file validity.
    """

    def score(self, ctx: RepoContext) -> CiCdScore: ...
```

### Implementazione dettagliata

1. **GitHub Actions**: Check `.github/workflows/` in contents listing (directory presence). Se directory contiene `.yml`/`.yaml` files → strong signal
2. **Other CI**: Check for Travis, Circle, GitLab, Jenkins config files
3. **CI badge**: Optional — regex per CI badge nel README (`[![Build Status](...)` patterns)
4. **Scoring**: GitHub Actions = 1.0, other CI = 0.7, badge only = 0.3, nothing = 0.0
5. **Multiple CI**: Se più sistemi CI presenti → bonus (0.1 extra) per thoroughness
6. **Details**: `{has_github_actions: bool, workflow_count: int, has_ci_badge: bool, ci_systems: [...]}`

### Test plan

- `test_ci_cd.py`:
  - `test_github_actions_detected`: .github/workflows/ → score alto
  - `test_travis_detected`: .travis.yml → score > 0
  - `test_no_ci`: Nessun CI → score 0.0
  - `test_multiple_ci_systems`: GitHub Actions + Travis → bonus
  - `test_ci_badge_in_readme`: Badge nel README → score parziale
  - `test_details_list_ci_systems`: Details elenca CI trovati

### Criterio di verifica

```bash
pytest tests/unit/screening/test_ci_cd.py -v   # 6 tests passing
```

---

## 7) Task 3.4 — Test Footprint Analyzer

### Obiettivo

Rilevare infrastruttura di testing: directory test, file di configurazione test, rapporto file test/source.

### Design

```python
# screening/test_footprint.py

_TEST_DIR_PATTERNS: list[str] = ["test", "tests", "spec", "specs", "__tests__"]
_TEST_FILE_PATTERNS: list[str] = ["test_", "_test.", "_spec.", ".test.", ".spec."]
_TEST_CONFIG_FILES: list[str] = [
    "pytest.ini", "pyproject.toml", "setup.cfg",     # Python
    "conftest.py",                                      # Python
    "jest.config.js", "jest.config.ts",                 # JavaScript
    ".mocharc.yml", ".mocharc.json",                    # JavaScript
    "vitest.config.ts",                                 # JavaScript
    "Cargo.toml",                                       # Rust (built-in testing)
]

class TestFootprintAnalyzer:
    """Analyzes test infrastructure presence and coverage indicators.
    
    Checks: test directories, test file patterns, test config files,
    and estimates test/source file ratio from contents listing.
    """

    def score(self, ctx: RepoContext) -> TestFootprintScore: ...
```

### Implementazione dettagliata

1. **Test directories**: Cerca directory con nomi in `_TEST_DIR_PATTERNS` nel contents listing
2. **Test config files**: Cerca file in `_TEST_CONFIG_FILES` nel contents listing (root level)
3. **Test file ratio**: Stima approssimativa: conta file con pattern `test_`/`_test.` vs totali. Non è preciso dal contents listing — è un indicatore
4. **Scoring**:
   - Test dir presente: +0.3
   - Test config file presente: +0.3
   - Test file ratio > 0.1: +0.2
   - Test file ratio > 0.3: +0.2 (bonus)
5. **Details**: `{has_test_dir: bool, test_frameworks: [...], test_file_ratio: float, has_conftest: bool}`

### Test plan

- `test_test_footprint.py`:
  - `test_test_dir_detected`: tests/ directory → has_test_dir=True
  - `test_pytest_config_detected`: pytest.ini + conftest.py → test_frameworks includes "pytest"
  - `test_no_test_infrastructure`: Nessun test → score 0.0
  - `test_test_file_ratio_calculated`: 5 test files, 20 source files → ratio 0.25
  - `test_jest_config_detected`: jest.config.js → test_frameworks includes "jest"
  - `test_details_report_signals`: Details contain expected keys

### Criterio di verifica

```bash
pytest tests/unit/screening/test_test_footprint.py -v   # 6 tests passing
```

---

## 8) Task 3.5 — Release Discipline Scorer

### Obiettivo

Valutare la disciplina di release: tagging semver, cadenza release, changelog per release, release notes.

### Design

```python
# screening/release_discipline.py

import re

_SEMVER_RE = re.compile(r'^v?\d+\.\d+\.\d+')

class ReleaseDisciplineScorer:
    """Scores release discipline and versioning practices.
    
    Uses recent_releases from RepoContext (already fetched).
    Checks: semver tagging, release cadence, changelog per release,
    release notes quality.
    """

    def score(self, ctx: RepoContext) -> ReleaseDisciplineScore: ...
```

### Implementazione dettagliata

1. **Semver tagging**: Conta releases con tag_name che matcha `_SEMVER_RE`. Ratio = semver_count / total_releases
2. **Release cadence**: Differenza media in giorni tra release consecutive. < 90 giorni = good, > 365 = poor, 0 releases = zero
3. **Release notes**: Conta releases con `body` non vuoto e > 100 chars
4. **Changelog per release**: Check se CHANGELOG.md esiste (da hygiene) e se i contenuti delle release sono dettagliati
5. **Scoring**:
   - Has any release: +0.2
   - Semver ratio > 0.8: +0.2
   - Cadence < 90 days: +0.2
   - Release notes > 50%: +0.2
   - Changelog file exists: +0.2
6. **Details**: `{has_semver_tags: bool, release_count: int, release_cadence_days: float, has_changelog_per_release: bool}`

### Test plan

- `test_release_discipline.py`:
  - `test_regular_semver_releases`: 10 releases con semver → score alto
  - `test_no_releases`: 0 releases → score basso
  - `test_non_semver_tags`: Tag non semver → score parziale
  - `test_release_cadence_calculated`: Cadence < 90 giorni → bonus
  - `test_release_notes_quality`: Release con body dettagliato → bonus
  - `test_details_report_signals`: Details contain expected keys

### Criterio di verifica

```bash
pytest tests/unit/screening/test_release_discipline.py -v   # 6 tests passing
```

---

## 9) Task 3.6 — Maintenance Signal Analyzer

### Obiettivo

Analizzare segnali di manutenzione: recency ultimo commit, cadenza commit, bus factor proxy, risoluzione issue. Questo è il sub-score più complesso — usa i dati dei commit API e potenzialmente PyDriller per metriche avanzate.

### Context7: Pattern verificati

Da `/websites/pydriller_readthedocs_io_en`:
- `Repository(path_to_repo).traverse_commits()` — iterazione commits
- `commit.modified_files` → `file.complexity`, `file.nloc`, `file.added_lines`, `file.deleted_lines`
- `CodeChurn(path_to_repo, from_commit, to_commit).count()` — code churn per file
- `ContributorsCount(path_to_repo, from_commit, to_commit).count()` — contributor totali per file
- `ContributorsExperience(path_to_repo, from_commit, to_commit).count()` — % top contributor
- PyDriller richiede clone locale — usare solo per analysis approfondite, non per screening base

### Design

```python
# screening/maintenance.py

from datetime import UTC, datetime

_MAINTENANCE_THRESHOLD_DAYS = 365  # Active if commit within last year
_COMMIT_CADENCE_GOOD_DAYS = 30     # Good cadence: commit at least monthly
_BUS_FACTOR_LOW = 2                # Bus factor ≤ 2 is risky
_BUS_FACTOR_GOOD = 5               # Bus factor ≥ 5 is healthy

class MaintenanceAnalyzer:
    """Analyzes maintenance signals from commit history and activity.
    
    Primary (API-based, zero clone): commit recency, cadence from recent_commits,
    contributor count from commits, issue resolution from issues.
    
    Optional (PyDriller, requires clone): code churn, detailed contributor analysis.
    PyDriller is used only when a local clone is available — otherwise
    API-based heuristics are used with lower confidence.
    """

    def score(self, ctx: RepoContext) -> MaintenanceScore: ...
```

### Implementazione dettagliata

1. **Commit recency** (API): `days_since_last_commit = (now - recent_commits[0].commit.author.date).days`
   - < 30 days: 1.0
   - < 90 days: 0.8
   - < 180 days: 0.5
   - < 365 days: 0.3
   - > 365 days: 0.1 (nearly dead)
2. **Commit cadence** (API): Media giorni tra commits nei recent_commits
   - < 7 days: 1.0 (very active)
   - < 30 days: 0.7 (active)
   - < 90 days: 0.4 (slow)
   - > 90 days: 0.2 (very slow)
3. **Bus factor proxy** (API): Conta unique authors nei recent_commits
   - ≥ 5: 1.0 (healthy)
   - 3-4: 0.7
   - 2: 0.4 (risky)
   - 1: 0.2 (single maintainer)
4. **Issue resolution** (API): Conta issues chiuse vs aperte nei recent_issues
   - Ratio closed/open > 2.0: 1.0
   - Ratio 1.0-2.0: 0.7
   - Ratio 0.5-1.0: 0.4
   - Ratio < 0.5: 0.2
5. **Composite**: Media pesata dei 4 segnali
6. **PyDriller (optional)**: Se clone disponibile, usa `CodeChurn` e `ContributorsCount` per metriche più precise con confidence=1.0. Altrimenti confidence=0.7 per metriche API-based.

### Dipendenze pyproject.toml

```toml
dependencies = [
    # ... existing ...
    "pydriller>=2.6",    # Git repository mining for maintenance metrics
]
```

### Test plan

- `test_maintenance.py`:
  - `test_active_repo_score`: Repo con commit recente → score alto
  - `test_inactive_repo_score`: Repo con commit > 1 anno fa → score basso
  - `test_commit_cadence_active`: Commits ogni settimana → cadence score alto
  - `test_bus_factor_healthy`: 6+ contributors → bus factor 1.0
  - `test_bus_factor_single_maintainer**: 1 contributor → bus factor 0.2
  - `test_issue_resolution_good`: Many closed issues → resolution score alto
  - `test_composite_weighted**: Verifica media pesata dei 4 segnali
  - `test_details_report_signals**: Details contain expected keys
  - `test_confidence_api_based**: API-based metrics → confidence 0.7

### Criterio di verifica

```bash
pytest tests/unit/screening/test_maintenance.py -v   # 9 tests passing
```

---

## 10) Task 3.7 — Issue/PR Practices Scorer

### Obiettivo

Valutare le pratiche di gestione issue/PR: template, review presence, label usage, response latency proxy.

### Design

```python
# screening/practices.py

_ISSUE_TEMPLATE_PATHS = [
    ".github/ISSUE_TEMPLATE/",
    ".github/ISSUE_TEMPLATE.md",
]
_PR_TEMPLATE_PATHS = [
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/PULL_REQUEST_TEMPLATE/",
    "PULL_REQUEST_TEMPLATE.md",
]

class PracticesScorer:
    """Scores code review practices and PR/issue management.
    
    Checks: PR/issue templates, review presence in PRs,
    label usage, response latency proxy.
    """

    def score(self, ctx: RepoContext) -> ReviewPracticeScore: ...
```

### Implementazione dettagliata

1. **Templates**: Check `.github/ISSUE_TEMPLATE/` e `.github/PULL_REQUEST_TEMPLATE.md` in contents
2. **Review presence**: Conta PRs con `review_comments > 0` o `requested_reviewers` nei recent_prs
3. **Label usage**: Conta PRs/issues con `labels` non vuoto
4. **Response latency**: Proxy = media ore tra creazione PR e primo commento/review. Usa `created_at` e comment timestamps se disponibili
5. **Scoring**: Template presence (0.3) + review rate (0.3) + label usage (0.2) + response latency (0.2)
6. **Details**: `{has_pr_template: bool, has_issue_template: bool, review_rate: float, label_usage: float, avg_response_hours: float}`

### Test plan

- `test_practices.py`:
  - `test_templates_detected`: PR + issue templates → score alto
  - `test_review_presence_scored**: PRs con review comments → review_rate > 0
  - `test_label_usage_scored**: Issues con labels → label_usage > 0
  - `test_no_practices**: Nessun template, 0 reviews → score basso
  - `test_details_report_signals**: Details contain expected keys

### Criterio di verifica

```bash
pytest tests/unit/screening/test_practices.py -v   # 5 tests passing
```

---

## 11) Task 3.8 — Dependency Quality Scorer

### Obiettivo

Valutare la gestione delle dipendenze: lockfile presence, dependency pinning, update signals (dependabot/renovate).

### Design

```python
# screening/dependency_quality.py

_LOCKFILE_PATTERNS: dict[str, list[str]] = {
    "python": ["poetry.lock", "Pipfile.lock", "pdm.lock", "uv.lock"],
    "javascript": ["package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb"],
    "rust": ["Cargo.lock"],
    "go": ["go.sum"],
    "ruby": ["Gemfile.lock"],
}
_DEPENDABOT_CONFIG = [".github/dependabot.yml", ".github/dependabot.yaml"]
_RENOVATE_CONFIG = ["renovate.json", ".github/renovate.json", "renovate.json5"]

class DependencyQualityScorer:
    """Scores dependency management quality.
    
    Checks: lockfile presence, dependency pinning signals,
    automated update configuration (dependabot/renovate).
    """

    def score(self, ctx: RepoContext) -> DependencyQualityScore: ...
```

### Implementazione dettagliata

1. **Lockfile detection**: Cerca lockfile per linguaggio dominante (candidate.language) + multi-language lockfiles
2. **Dependabot/renovate config**: Cerca config files in contents listing
3. **Pinning signals**: Se `requirements.txt` o `pyproject.toml` presente → heuristica per pinning (non preciso senza clone)
4. **Scoring**:
   - Lockfile presente: +0.4
   - Dependabot/renovate: +0.3
   - Multi-ecosystem lockfiles: +0.2
   - Pinning signals: +0.1
5. **Details**: `{has_lockfile: bool, lockfiles_found: [...], has_dependabot: bool, has_renovate: bool, pinning_ratio: float}`

### Test plan

- `test_dependency_quality.py`:
  - `test_python_lockfile_detected**: poetry.lock → has_lockfile=True
  - `test_javascript_lockfile_detected**: package-lock.json → has_lockfile=True
  - `test_dependabot_config_detected**: .github/dependabot.yml → has_dependabot=True
  - `test_renovate_config_detected**: renovate.json → has_renovate=True
  - `test_no_dependency_management**: Nessun lockfile → score basso
  - `test_multi_ecosystem_lockfiles**: Python + JS lockfiles → bonus
  - `test_details_report_signals**: Details contain expected keys

### Criterio di verifica

```bash
pytest tests/unit/screening/test_dependency_quality.py -v   # 7 tests passing
```

---

## 12) Task 3.9 — Gate 2 Static/Security Screening Engine

### Obiettivo

Motore di orchestrazione Gate 2 che coordina i 4 sub-score checkers (Scorecard, gitleaks, OSV, scc). Gate 2 è più costoso di Gate 1 perché richiede chiamate API esterne e/o subprocess — eseguito solo su candidati che hanno passato Gate 1.

### Design

```python
# screening/gate2_static.py

class Gate2StaticScreener:
    """Gate 2 — Static/security screening engine (zero or low cost).
    
    Orchestrates 4 sub-score checkers using external tools:
    - OpenSSF Scorecard API (HTTP)
    - OSV API (HTTP)
    - gitleaks (subprocess on shallow clone)
    - scc (subprocess for LOC/complexity)
    
    Only runs on candidates that passed Gate 1 (hard gate enforcement).
    Implements graceful degradation: tool failures → heuristic fallback.
    """

    def __init__(
        self,
        rest_client: GitHubRestClient,
        settings: ScreeningSettings,
        github_settings: GitHubSettings,
    ) -> None: ...

    async def screen(
        self,
        candidate: RepoCandidate,
        gate1_result: MetadataScreenResult,
        *,
        threshold: float | None = None,
    ) -> StaticScreenResult:
        """Screen a single candidate through Gate 2.
        
        Precondition: gate1_result.gate1_pass must be True.
        Raises HardGateViolationError if not.
        
        1. Check Gate 1 pass (hard gate)
        2. Run 4 sub-score checkers (parallel where possible)
        3. Compute weighted composite (gate2_total)
        4. Apply threshold → gate2_pass
        5. Return StaticScreenResult with tools_used/tools_failed
        """
        ...

    async def screen_batch(
        self,
        candidates: list[tuple[RepoCandidate, MetadataScreenResult]],
        *,
        threshold: float | None = None,
        max_concurrent: int = 3,
    ) -> list[StaticScreenResult]:
        """Screen a batch. Only candidates that passed Gate 1 are screened."""
        ...
```

### Implementazione dettagliata

1. **Hard gate check**: Se `gate1_result.gate1_pass is False` → `HardGateViolationError`
2. **Parallel execution**: Scorecard + OSV API calls in parallelo (indipendenti). gitleaks + scc sono sequenziali (entrambi richiedono clone)
3. **Graceful degradation**: Se un tool fallisce (non installato, timeout, API error):
   - Sub-score con value=0.3 (default moderate), confidence=0.0
   - Aggiungere a `tools_failed` list
   - Log warning con structlog
4. **Timeout management**: Ogni tool ha timeout configurabile (default 60s per subprocess, 30s per API)
5. **Clone management**: Shallow clone (`git clone --depth=1`) in temp directory per gitleaks + scc. Cleanup dopo screening.

### Test plan

- `test_gate2_static.py`:
  - `test_screen_returns_static_result**: Mock tools → StaticScreenResult con 4 sub-scores
  - `test_screen_hard_gate_enforcement**: gate1_pass=False → HardGateViolationError
  - `test_screen_computes_gate2_total**: Verifica compute_total() → gate2_total
  - `test_screen_applies_threshold**: Score sopra/sotto threshold → pass/fail
  - `test_screen_tools_used_tracking**: Mock tutti tools → tools_used populated
  - `test_screen_graceful_degradation**: Mock tool failure → sub-score fallback, tools_failed populated
  - `test_screen_batch_filters_gate1_failed**: Batch con mix pass/fail → solo pass vengono screenati
  - `test_screen_custom_threshold**: Override threshold via parametro

### Criterio di verifica

```bash
pytest tests/unit/screening/test_gate2_static.py -v   # 8 tests passing
mypy src/github_discovery/screening/gate2_static.py --strict
```

---

## 13) Task 3.10 — OpenSSF Scorecard Integration

### Obiettivo

Integrare OpenSSF Scorecard API per ottenere security posture assessment standardizzato.

### Design

```python
# screening/scorecard_adapter.py

_SCORECARD_API_BASE = "https://api.scorecard.dev"
_SCORECARD_ENDPOINT = "/projects/github.com/{owner}/{repo}"

class ScorecardAdapter:
    """OpenSSF Scorecard API integration.
    
    Queries scorecard.dev for security posture assessment.
    Returns SecurityHygieneScore based on aggregate score
    and individual checks.
    
    Falls back gracefully if API is unavailable or repo
    has not been scored.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None: ...

    async def score(self, candidate: RepoCandidate) -> SecurityHygieneScore: ...
```

### Implementazione dettagliata

1. **API call**: `GET https://api.scorecard.dev/projects/github.com/{owner}/{repo}` — no auth required
2. **Response parsing**: `response.json()` → `{"repo": {"name": "..."}, "score": 8.5, "checks": [{"name": "Branch-Protection", "score": 9}, ...]}`
3. **Score normalization**: Scorecard range 0-10 → normalize to 0.0-1.0 (`score / 10.0`)
4. **Check details**: Estrai check scores rilevanti: Branch-Protection, Token-Permissions, Dangerous-Workflow, Pinned-Dependencies, Signed-Releases
5. **Graceful fallback**: 404 (repo not scored) → SecurityHygieneScore(value=0.5, confidence=0.0, notes=["Scorecard: repo not scored"])
6. **Timeout**: 30 secondi default

### Test plan

- `test_scorecard_adapter.py`:
  - `test_score_from_api**: Mock scorecard response con score 8.5 → value 0.85
  - `test_score_normalization**: Score 10 → value 1.0, Score 0 → value 0.0
  - `test_repo_not_scored**: Mock 404 → value=0.5, confidence=0.0
  - `test_api_timeout**: Mock timeout → value=0.5, confidence=0.0
  - `test_details_contain_checks**: Details include individual check scores
  - `test_score_with_zero**: Mock score 0 → value 0.0

### Criterio di verifica

```bash
pytest tests/unit/screening/test_scorecard_adapter.py -v   # 6 tests passing
```

---

## 14) Task 3.11 — Secret Hygiene Check

### Obiettivo

Integrare gitleaks per secret detection via subprocess su shallow clone.

### Context7: Pattern verificati

Da `/python/cpython`:
- `asyncio.create_subprocess_exec(program, *args, stdout=PIPE, stderr=PIPE)` per esecuzione async
- `process.communicate()` per leggere stdout + stderr
- `process.returncode` per exit code
- Timeout via `asyncio.wait_for(process.communicate(), timeout=seconds)`

### Design

```python
# screening/secrets_check.py

_GITLEAKS_BINARY = "gitleaks"
_GITLEAKS_TIMEOUT = 60  # seconds
_GITLEAKS_SARIF_FORMAT = "sarif"

class SecretsChecker:
    """Secret detection using gitleaks subprocess.
    
    Runs gitleaks detect on a shallow clone of the repository.
    Parses SARIF JSON output for findings count.
    
    Falls back to heuristic (confidence=0.0) if gitleaks
    is not installed or fails.
    """

    def __init__(self, subprocess_runner: SubprocessRunner | None = None) -> None: ...

    async def score(
        self,
        candidate: RepoCandidate,
        clone_dir: Path | None = None,
    ) -> SecretHygieneScore: ...
```

### Implementazione dettagliata

1. **Shallow clone**: `git clone --depth=1 {repo_url} {tmpdir}` in temp directory (gestita dal Gate 2 engine)
2. **Gitleaks execution**: `gitleaks detect --source {clone_dir} --report-format sarif --report-path {tmpdir}/report.sarif --no-git`
3. **SARIF parsing**: Leggi JSON output → conta `results` array length per findings count
4. **Scoring**:
   - 0 findings: value=1.0 (clean)
   - 1-2 findings: value=0.7 (minor issues, could be false positives)
   - 3-5 findings: value=0.4 (concerning)
   - > 5 findings: value=0.1 (serious hygiene problem)
5. **Fallback**: Se gitleaks non installato → `value=0.5, confidence=0.0, notes=["gitleaks not available"]`

### Dipendenza esterna

Gitleaks deve essere installato nel sistema (`go install github.com/gitleaks/gitleaks/v8/cmd/gitleaks@latest` o package manager). Non è una dipendenza Python — è un tool CLI esterno. Lo screening continua senza di esso.

### Test plan

- `test_secrets_check.py`:
  - `test_no_secrets_found**: Mock SARIF con 0 results → value=1.0
  - `test_minor_secrets**: Mock SARIF con 2 results → value=0.7
  - `test_many_secrets**: Mock SARIF con 10 results → value=0.1
  - `test_gitleaks_not_installed**: Mock FileNotFoundError → value=0.5, confidence=0.0
  - `test_gitleaks_timeout**: Mock timeout → value=0.5, confidence=0.0
  - `test_sarif_parsing**: Mock SARIF JSON → findings count corretto
  - `test_details_report_findings**: Details include findings count and tool info

### Criterio di verifica

```bash
pytest tests/unit/screening/test_secrets_check.py -v   # 7 tests passing
```

---

## 15) Task 3.12 — Dependency Vulnerability Scan

### Obiettivo

Query OSV API per vulnerability scanning delle dipendenze dichiarate.

### Design

```python
# screening/osv_adapter.py

_OSV_API_BASE = "https://api.osv.dev"
_OSV_QUERY_ENDPOINT = "/v1/query"

class OsvAdapter:
    """OSV API dependency vulnerability scanning.
    
    Queries OSV.dev for known vulnerabilities in declared
    dependencies. Uses ecosystem/package/version from
    manifest files (if available).
    
    Falls back gracefully if no manifest data available
    or API is unreachable.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None: ...

    async def score(self, candidate: RepoCandidate) -> VulnerabilityScore: ...
```

### Implementazione dettagliata

1. **Manifest detection**: Dai contents listing, identifica lockfile/manifest files per ecosistema
2. **OSV query**: `POST https://api.osv.dev/v1/query` con body:
   ```json
   {
     "package": {"name": "requests", "ecosystem": "PyPI"},
     "version": "2.28.0"
   }
   ```
   Nota: Per lo screening iniziale, possiamo usare un approccio semplificato: query OSV con solo il nome del repo se è un package noto, oppure saltare se non abbiamo info sulle dipendenze.
3. **Response parsing**: `{"vulns": [{"id": "GHSA-xxx", "severity": "HIGH", ...}]}`
4. **Scoring**:
   - No vulnerabilities: value=1.0
   - Only LOW vulnerabilities: value=0.8
   - Any MEDIUM: value=0.5
   - Any HIGH: value=0.3
   - Any CRITICAL: value=0.1
5. **No manifest available**: value=0.5 (neutral), confidence=0.0, notes=["No dependency manifest available for OSV query"]
6. **Details**: `{vuln_count: int, critical_count: int, high_count: int, osv_packages_checked: int}`

### Test plan

- `test_osv_adapter.py`:
  - `test_no_vulnerabilities**: Mock OSV con vuoto → value=1.0
  - `test_low_vulnerabilities**: Mock OSV con solo LOW → value=0.8
  - `test_high_vulnerabilities**: Mock OSV con HIGH → value=0.3
  - `test_critical_vulnerabilities**: Mock OSV con CRITICAL → value=0.1
  - `test_no_manifest_available**: Nessun lockfile → value=0.5, confidence=0.0
  - `test_api_unavailable**: Mock API error → value=0.5, confidence=0.0
  - `test_details_report_vulns**: Details include vulnerability counts

### Criterio di verifica

```bash
pytest tests/unit/screening/test_osv_adapter.py -v   # 7 tests passing
```

---

## 16) Task 3.13 — Code Complexity Metrics

### Obiettivo

Integrare `scc` per metriche di LOC, linguaggi e complessità. Fallback a GitHub API data (languages, size_kb) se scc non disponibile.

### Design

```python
# screening/complexity.py

_SCC_BINARY = "scc"
_SCC_TIMEOUT = 60  # seconds
_SCC_ARGS = ["--format", "json", "--by-file", "--no-cocomo"]

class ComplexityAnalyzer:
    """Code complexity and size metrics via scc subprocess.
    
    Runs scc on a shallow clone to get LOC, language breakdown,
    and complexity metrics. Falls back to GitHub API language
    data if scc is not available.
    """

    def __init__(self, subprocess_runner: SubprocessRunner | None = None) -> None: ...

    async def score(
        self,
        candidate: RepoCandidate,
        clone_dir: Path | None = None,
    ) -> ComplexityScore: ...
```

### Implementazione dettagliata

1. **scc execution**: `scc {clone_dir} --format json --by-file --no-cocomo`
2. **JSON parsing**: scc output → `{"Python": {"Code": 12000, "Comment": 3000, "Blank": 2000, "Complexity": 450, "Files": 85, ...}}`
3. **Scoring** (size-based sanity check):
   - LOC < 10K: small project → value=0.7 (fine, small scope)
   - LOC 10K-100K: medium → value=1.0 (sweet spot)
   - LOC 100K-500K: large → value=0.8 (complexity risk)
   - LOC > 500K: very large → value=0.5 (high complexity risk)
   - Adjust based on complexity/LOC ratio (> 0.5 = high complexity per LOC)
4. **Multi-language**: Language count bonus (> 2 languages → lower score, fragmentation risk)
5. **Fallback**: Se scc non disponibile → usa `candidate.size_kb` e `candidate.languages` come proxy con confidence=0.3
6. **Details**: `{total_loc: int, languages: dict, file_count: int, avg_complexity: float}`

### Dipendenza esterna

`scc` deve essere installato (`go install github.com/boyter/scc/v3@latest` o package manager). Non è una dipendenza Python.

### Test plan

- `test_complexity.py`:
  - `test_small_project**: Mock scc con 5K LOC → value=0.7
  - `test_medium_project**: Mock scc con 50K LOC → value=1.0
  - `test_large_project**: Mock scc con 200K LOC → value=0.8
  - `test_scc_not_available**: Mock FileNotFoundError → fallback a size_kb, confidence=0.3
  - `test_scc_timeout**: Mock timeout → fallback
  - `test_multi_language**: Mock 5+ languages → complexity risk
  - `test_json_parsing**: Mock scc JSON output → details corretti
  - `test_details_report_metrics**: Details contain expected metrics

### Criterio di verifica

```bash
pytest tests/unit/screening/test_complexity.py -v   # 8 tests passing
```

---

## 17) Task 3.14 — Screening Orchestrator & Gating Policy

### Obiettivo

Orchestratore centrale che coordina Gate 1 e Gate 2 screening, applica la gating policy con soglie configurabili, e produce `ScreeningResult` per ogni candidato. Contiene il Policy Engine per domain-specific thresholds.

### Design

```python
# screening/orchestrator.py

class ScreeningOrchestrator:
    """Central orchestrator for the screening pipeline.
    
    Coordinates Gate 1 and Gate 2 screening with:
    - Hard gate enforcement (no Gate 3 without Gate 1+2 pass)
    - Domain-specific thresholds via Policy Engine
    - Batch processing with concurrency control
    - Graceful error handling and progress tracking
    """

    def __init__(
        self,
        settings: Settings,
        gate1_screener: Gate1MetadataScreener,
        gate2_screener: Gate2StaticScreener,
    ) -> None: ...

    async def screen(
        self,
        context: ScreeningContext,
    ) -> list[ScreeningResult]:
        """Screen a pool of candidates through configured gates.
        
        1. For each candidate:
           a. If gate_level includes Gate 1: screen through Gate 1
           b. If gate1_pass and gate_level includes Gate 2: screen through Gate 2
        2. Apply hard gate enforcement
        3. Return list of ScreeningResult
        
        Respects ScreeningContext.gate_level:
        - GateLevel.METADATA: only Gate 1
        - GateLevel.STATIC_SECURITY: only Gate 2 (requires Gate 1 pass)
        - "both": Gate 1 then Gate 2 for passers
        """
        ...

    def _get_threshold(
        self,
        gate: GateLevel,
        domain: DomainType | None = None,
        override: float | None = None,
    ) -> float:
        """Get threshold for a gate, considering domain and override.
        
        Priority: override > domain-specific > global default
        """
        ...

    async def _quick_screen(
        self,
        candidate: RepoCandidate,
        gate_levels: str = "1",
    ) -> ScreeningResult:
        """Quick screen a single repo without full pool context.
        
        Used by MCP tool quick_screen for single-repo checks.
        """
        ...
```

### Implementazione dettagliata

1. **Policy Engine**: Soglie configurabili per dominio:
   ```python
   DOMAIN_THRESHOLDS: dict[DomainType, dict[str, float]] = {
       DomainType.LIBRARY: {"gate1": 0.5, "gate2": 0.6},
       DomainType.SECURITY_TOOL: {"gate1": 0.6, "gate2": 0.7},
       # ... altri domini con soglie custom
       DomainType.OTHER: {"gate1": 0.4, "gate2": 0.5},  # default
   }
   ```
2. **Hard gate enforcement**: Implementato come hard constraint:
   ```python
   if gate1_result.gate1_pass is False:
       return ScreeningResult(
           full_name=candidate.full_name,
           gate1=gate1_result,
           gate2=None,
       )  # can_proceed_to_gate3 is False
   ```
3. **Batch processing**: `asyncio.Semaphore(max_concurrent)` per rate limit. Update status per candidate.
4. **Progress tracking**: Log + optional callback per progress notifications
5. **Error recovery**: Se screening fallisce per un candidato, log error + ScreeningResult con gate=None + EXCLUDED status
6. **Domain-specific weights**: Configurabili via YAML/env — default pesi nei model SubScore

### Test plan

- `test_orchestrator.py`:
  - `test_screen_gate1_only**: Screening solo Gate 1 → ScreeningResult con gate2=None
  - `test_screen_both_gates**: Gate 1 pass → Gate 2 screening → ScreeningResult completo
  - `test_screen_gate1_fail_no_gate2**: Gate 1 fail → Gate 2 NON eseguito
  - `test_hard_gate_enforcement**: can_proceed_to_gate3 solo se entrambi passano
  - `test_domain_specific_threshold**: Library domain → threshold più alta
  - `test_threshold_override**: Override esplicito > domain > default
  - `test_batch_screening**: 10 candidati → tutti screenati
  - `test_batch_concurrency**: Verifica Semaphore limita concorrenza
  - `test_error_recovery**: 1 candidato fallisce → altri continuano
  - `test_quick_screen_single_repo**: Quick screen senza pool context
  - `test_screen_updates_candidate_status**: Status aggiornato per ogni gate
  - `test_screen_empty_pool**: Pool vuoto → lista vuota

### Criterio di verifica

```bash
pytest tests/unit/screening/test_orchestrator.py -v   # 12 tests passing
mypy src/github_discovery/screening/orchestrator.py --strict
```

### Shared Utility: SubprocessRunner

```python
# screening/subprocess_runner.py

class SubprocessRunner:
    """Async subprocess execution utility with timeout and error handling.
    
    Wraps asyncio.create_subprocess_exec with:
    - Configurable timeout
    - stdout/stderr capture
    - Return code checking
    - Logging
    """

    async def run(
        self,
        command: list[str],
        *,
        timeout: float = 60.0,
        cwd: str | Path | None = None,
    ) -> SubprocessResult:
        """Execute a command and return structured result."""
        ...

# tests/unit/screening/test_subprocess_runner.py
# - test_run_success: Mock echo → returncode=0
# - test_run_timeout: Mock sleep → timed_out=True
# - test_run_nonzero_exit: Mock false → returncode=1
# - test_run_captures_stdout: Mock output → stdout captured
# - test_run_captures_stderr: Mock error → stderr captured
```

### Criterio di verifica

```bash
pytest tests/unit/screening/test_subprocess_runner.py -v   # 5 tests passing
```

---

## 18) Sequenza di implementazione

```
Fase A — Fondamentali (Settimana 1)
  Task 3.1  Gate 1 Metadata Screening Engine    [critico, blocca sub-scores]
  Task 3.14 SubprocessRunner utility             [usato da Gate 2 tools]
  
Fase B — Gate 1 Sub-Scores (Settimana 1-2)
  Task 3.2  Hygiene Files Checker               [semplice, zero external deps]
  Task 3.3  CI/CD Detection                      [semplice, zero external deps]
  Task 3.4  Test Footprint Analyzer              [semplice, zero external deps]
  Task 3.5  Release Discipline Scorer            [semplice, usa releases API]
  Task 3.7  Issue/PR Practices Scorer            [semplice, usa issues/PRs API]
  Task 3.8  Dependency Quality Scorer            [semplice, contents listing]
  Task 3.6  Maintenance Signal Analyzer          [complesso, PyDriller opzionale]

Fase C — Gate 2 Sub-Scores (Settimana 2)
  Task 3.9  Gate 2 Static/Security Engine        [critico, coordina Gate 2]
  Task 3.10 OpenSSF Scorecard Integration        [HTTP API, no clone needed]
  Task 3.12 Dependency Vulnerability Scan         [HTTP API, no clone needed]
  Task 3.11 Secret Hygiene Check                  [subprocess, richiede clone]
  Task 3.13 Code Complexity Metrics               [subprocess, richiede clone]

Fase D — Integrazione (Settimana 2-3)
  Task 3.14 Screening Orchestrator               [integra Gate 1 + Gate 2]
```

### Ordine consigliato per l'implementazione

1. **3.14a** — `SubprocessRunner` utility (fondazione per Gate 2 tools)
2. **3.1** — Gate 1 Metadata Screening Engine (fondazione Gate 1)
3. **3.2** — Hygiene Files Checker (il più semplice, valida pattern)
4. **3.3** — CI/CD Detection (semplice)
5. **3.4** — Test Footprint Analyzer (semplice)
6. **3.5** — Release Discipline Scorer (semplice)
7. **3.8** — Dependency Quality Scorer (semplice)
8. **3.7** — Issue/PR Practices Scorer (medio)
9. **3.6** — Maintenance Signal Analyzer (complesso, PyDriller)
10. **3.9** — Gate 2 Static/Security Engine (fondazione Gate 2)
11. **3.10** — OpenSSF Scorecard (HTTP API, il più semplice Gate 2)
12. **3.12** — OSV Adapter (HTTP API)
13. **3.11** — Secrets Checker (subprocess)
14. **3.13** — Complexity Analyzer (subprocess)
15. **3.14b** — Screening Orchestrator (integra tutto)

Ogni task deve essere completato con test passing e mypy strict prima di procedere al successivo.

---

## 19) Test plan

### Test unitari (per modulo)

| Modulo | File test | Tests stimati | Dipendenza mock |
|--------|-----------|---------------|-----------------|
| `subprocess_runner.py` | `test_subprocess_runner.py` | 5 | asyncio subprocess mock |
| `gate1_metadata.py` | `test_gate1_metadata.py` | 10 | pytest-httpx |
| `hygiene.py` | `test_hygiene.py` | 8 | Nessuna (pure logic) |
| `ci_cd.py` | `test_ci_cd.py` | 6 | Nessuna (pure logic) |
| `test_footprint.py` | `test_test_footprint.py` | 6 | Nessuna (pure logic) |
| `release_discipline.py` | `test_release_discipline.py` | 6 | Nessuna (pure logic) |
| `maintenance.py` | `test_maintenance.py` | 9 | Nessuna (pure logic) |
| `practices.py` | `test_practices.py` | 5 | Nessuna (pure logic) |
| `dependency_quality.py` | `test_dependency_quality.py` | 7 | Nessuna (pure logic) |
| `gate2_static.py` | `test_gate2_static.py` | 8 | pytest-httpx + subprocess mock |
| `scorecard_adapter.py` | `test_scorecard_adapter.py` | 6 | pytest-httpx |
| `secrets_check.py` | `test_secrets_check.py` | 7 | SubprocessRunner mock |
| `osv_adapter.py` | `test_osv_adapter.py` | 7 | pytest-httpx |
| `complexity.py` | `test_complexity.py` | 8 | SubprocessRunner mock |
| `orchestrator.py` | `test_orchestrator.py` | 12 | Mock screeners |
| **Totale** | | **~116** | |

### Fixtures condivise (conftest.py)

```python
# tests/unit/screening/conftest.py

@pytest.fixture
def mock_rest_client(): ...
    """GitHubRestClient mock with canned API responses."""

@pytest.fixture
def sample_repo_context() -> RepoContext:
    """Fully populated RepoContext for testing."""

@pytest.fixture
def sample_repo_contents() -> list[str]:
    """Root directory listing with typical files."""

@pytest.fixture
def sample_releases() -> list[dict[str, object]]:
    """10 releases with semver tags and release notes."""

@pytest.fixture
def sample_commits() -> list[dict[str, object]]:
    """30 commits with dates and authors."""

@pytest.fixture
def sample_issues() -> list[dict[str, object]]:
    """30 issues with labels and state."""

@pytest.fixture
def sample_prs() -> list[dict[str, object]]:
    """30 PRs with reviews, labels, and state."""

@pytest.fixture
def sample_scorecard_response() -> dict[str, object]:
    """OpenSSF Scorecard API response."""

@pytest.fixture
def sample_osv_response() -> dict[str, object]:
    """OSV API response with vulnerabilities."""

@pytest.fixture
def sample_sarif_output() -> dict[str, object]:
    """gitleaks SARIF output."""

@pytest.fixture
def sample_scc_output() -> dict[str, object]:
    """scc JSON output."""

@pytest.fixture
def screening_settings() -> ScreeningSettings:
    """Default screening settings."""

@pytest.fixture
def mock_subprocess_runner(): ...
    """SubprocessRunner mock with configurable responses."""
```

### Test di integrazione

```python
# tests/integration/screening/test_screening_e2e.py

@pytest.mark.integration
@pytest.mark.slow
class TestScreeningE2E:
    """End-to-end screening tests against real GitHub API.
    
    These tests require GHDISC_GITHUB_TOKEN set and count against rate limits.
    Run with: pytest -m integration tests/integration/screening/
    """

    async def test_gate1_screen_real_repo(self): ...
        """Screen a known good repo (e.g., pallets/flask) through Gate 1."""

    async def test_gate2_scorecard_real_repo(self): ...
        """Get Scorecard for a known repo."""

    async def test_screening_pipeline_real_pool(self): ...
        """Screen a small pool of real candidates through Gate 1."""
```

### Target coverage

- **gate1_metadata.py**: >90% (core orchestration)
- **gate2_static.py**: >85% (security gate)
- **orchestrator.py**: >85% (policy engine)
- **Sub-score checkers**: >80% each
- **External adapters**: >80% (con fallback paths testati)

---

## 20) Criteri di accettazione

### Checkpoint Phase 3 (Roadmap)

> Gate 1+2 operativi con scoring riproducibile, hard gate enforcement, almeno 4 tool esterni integrati (Scorecard, gitleaks, OSV, scc).

### Criteri verificabili

1. **`make ci` verde**: ruff check + mypy --strict + pytest tutti passing
2. **Test count**: Almeno 116 nuovi test unitari passing
3. **Gate 1 operativo**: 7 sub-scores calcolati da metadata API, gating riproducibile
4. **Gate 2 operativo**: 4 sub-scores calcolati (Scorecard + OSV + gitleaks + scc), con graceful fallback
5. **Hard gate enforcement**: `ScreeningResult.can_proceed_to_gate3` è `True` solo se `gate1_pass AND gate2_pass`
6. **4+ tool esterni integrati**: Scorecard, gitleaks, OSV, scc (almeno 3 con test mock + 1 con integration test)
7. **Policy Engine**: Domain-specific thresholds, override capability, hard constraint in codice
8. **Graceful degradation**: Tool failure → sub-score con confidence bassa, pipeline non si blocca
9. **Screening riproducibile**: Stessi input → stessi output (determinismo nei sub-score checkers)
10. **mypy --strict**: 0 errors in `src/github_discovery/screening/`
11. **Integration test**: Almeno 1 test E2E con API reale (marked `@pytest.mark.integration`)

### Comandi di verifica

```bash
make ci                                                # Full CI: lint + typecheck + test
pytest tests/unit/screening/ -v                        # All screening unit tests
pytest tests/unit/screening/ --cov=github_discovery.screening --cov-report=term-missing
pytest -m integration tests/integration/screening/ -v  # E2E tests (needs token)
mypy src/github_discovery/screening/ --strict          # Type check screening module
```

---

## 21) Rischi e mitigazioni

| Rischio | Impatto | Probabilità | Mitigazione |
|---------|---------|-------------|-------------|
| **GitHub API rate limit su context gathering (7+ calls per repo)** | Alto — screening lento | Media | Batch con Semaphore, caching per repo (Feature Store), conditional requests, rate limit monitoring |
| **PyDriller richiede clone locale** | Medio — maintenance analysis costoso | Alta | PyDriller opzionale — usare solo quando clone disponibile. Default: API-based heuristics con confidence=0.7 |
| **gitleaks/scc non installati** | Medio — Gate 2 incompleto | Alta | Graceful degradation con fallback heuristic, confidence=0.0 per sub-scores con tool mancanti, documentare installazione |
| **OpenSSF Scorecard non ha score per repo piccoli/nuovi** | Basso — security score mancante | Media | Fallback a value=0.5 con confidence=0.0 e note. Scorecard coverage è ampia ma non universale |
| **OSV API: dipendenze non dichiarate nel contents listing** | Medio — vulnerability scan incompleto | Media | Limitato a repo con lockfile/manifest visibili. Se nessun manifest → neutral score con confidence=0.0 |
| **Shallow clone timeout per repo grandi** | Basso — screening fallisce | Bassa | Timeout configurabile (60s default), size_kb check prima del clone (skip > 1GB), graceful fallback |
| **Sub-score pesi non calibrati** | Alto — screening non significativo | Media | Default pesi ragionevoli da best practices. Calibrazione in Phase 9 Sprint 0. Configurabili via env |
| **Screening determinismo: API responses variano nel tempo** | Basso — risultati non stabili | Media | Commit SHA per dedup. Caching risultati in Feature Store per TTL. Accettare variazione minore per dati temporali |

---

## 22) Verifica Context7 completata

Le seguenti librerie e pattern sono stati verificati tramite Context7 prima della stesura di questo piano:

| Libreria | ID Context7 | Pattern verificati |
|----------|-------------|-------------------|
| **PyDriller** | `/websites/pydriller_readthedocs_io_en` | `Repository.traverse_commits()`, `commit.modified_files` (complexity, nloc, added_lines, deleted_lines), `CodeChurn.count()`, `ContributorsCount.count()` / `.count_minor()`, `ContributorsExperience.count()`, `LinesCount`, `since`/`to` date filtering, `only_modifications_with_file_types`, `only_no_merge` |
| **Pydantic v2** | `/websites/pydantic_dev_validation` | `model_validator(mode='before'/'after')`, `field_validator`, `computed_field`, `BaseModel` inheritance, `Field(ge=, le=, default_factory=)` |
| **aiosqlite** | `/omnilib/aiosqlite` | `async with aiosqlite.connect() as db`, `db.execute()`, `db.commit()`, `cursor.fetchall()`, `execute_fetchall()`, in-memory `:memory:`, parameterized queries with `?` |
| **Python asyncio subprocess** | `/python/cpython` | `asyncio.create_subprocess_exec()`, `stdout=asyncio.subprocess.PIPE`, `process.communicate()`, `process.returncode`, `asyncio.wait_for()` for timeout |
| **structlog** | `/hynek/structlog` | `structlog.get_logger()`, structured context binding, JSON output |
| **pytest** | `/websites/pytest_en_stable` | Fixtures, markers, parametrize, conftest.py sharing |
| **pytest-asyncio** | `/pytest-dev/pytest-asyncio` | Async test support, `@pytest.mark.asyncio` |

### Pattern chiave verificati

1. **PyDriller commit mining**: `Repository(path_to_repo, since=start, to=end).traverse_commits()` → `commit.hash`, `commit.author`, `commit.author_date`, `commit.insertions`, `commit.deletions`, `commit.modified_files`
2. **PyDriller process metrics**: `CodeChurn(path_to_repo, from_commit, to_commit).count()` → per-file churn. `ContributorsCount(...)` → `{filepath: count}`. `ContributorsExperience(...)` → `{filepath: top_percentage}`
3. **PyDriller complexity**: `file.complexity` (via Lizard), `file.nloc`, `file.methods`, `file.language_supported`
4. **Async subprocess**: `proc = await asyncio.create_subprocess_exec(cmd, *args, stdout=PIPE, stderr=PIPE)` → `stdout, stderr = await proc.communicate()` → `proc.returncode`
5. **aiosqlite patterns**: `async with aiosqlite.connect(":memory:") as db:` → `await db.execute("CREATE TABLE ...")` → `await db.commit()` → `async with db.execute("SELECT ...") as cursor:` → `await cursor.fetchall()`
6. **Pydantic sub-score pattern**: `SubScore(value=float, weight=float, details=dict, confidence=float, notes=list)` — già implementato in Phase 1

### API esterne verificate (documentazione web)

| API | Endpoint | Pattern |
|-----|----------|---------|
| **OpenSSF Scorecard** | `GET https://api.scorecard.dev/projects/github.com/{owner}/{repo}` | No auth, response: `{"score": 8.5, "checks": [{"name": "...", "score": N}]}`, 404 if not scored |
| **OSV API** | `POST https://api.osv.dev/v1/query` | Body: `{"package": {"name": "...", "ecosystem": "..."}, "version": "..."}`, response: `{"vulns": [...]}` |
| **GitHub REST API** (per context) | `/repos/{o}/{r}/contents/`, `/repos/{o}/{r}/releases`, `/repos/{o}/{r}/commits`, `/repos/{o}/{r}/issues`, `/repos/{o}/{r}/pulls`, `/repos/{o}/{r}/languages` | Già verificato in Phase 2 Context7 research |

### Tool CLI esterni verificati

| Tool | Comando | Output |
|------|---------|--------|
| **gitleaks** | `gitleaks detect --source {dir} --report-format sarif --report-path {file} --no-git` | SARIF JSON con `results` array |
| **scc** | `scc {dir} --format json --by-file --no-cocomo` | JSON per language: `{Language: {Code, Comment, Blank, Complexity, Files, Lines}}` |

---

*Stato documento: Draft v1 — Phase 3 Lightweight Quality Screening Implementation Plan*
*Data: 2026-04-22*
*Basato su: roadmap Phase 3 + blueprint §6 Layer B + §16.2-16.5 + wiki screening-gates.md*
*Context7 verification: PyDriller, Pydantic v2, aiosqlite, asyncio subprocess, structlog*
