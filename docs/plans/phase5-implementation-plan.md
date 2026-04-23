# GitHub Discovery — Phase 5 Implementation Plan

## Meta

- **Stato**: Draft v1
- **Data**: 2026-04-23
- **Riferimento roadmap**: `docs/roadmaps/github-discovery_foundation_roadmap.md` — Phase 5
- **Riferimento blueprint**: `docs/foundation/github-discovery_foundation_blueprint.md` — §6 (Layer D), §7, §10, §15
- **Riferimento wiki**: `docs/llm-wiki/wiki/` — articoli su scoring dimensions, anti-star bias, domain strategy, tiered pipeline
- **Durata stimata**: 1-2 settimane
- **Milestone**: M4 — Ranking MVP (Anti-star bias funzionante, explainability leggibile, domain-aware, confidence score significativo)
- **Dipendenza**: Phase 0+1+2+3+4 completate (700 tests passing, `make ci` verde)

---

## Indice

1. [Obiettivo](#1-obiettivo)
2. [Task Overview](#2-task-overview)
3. [Architettura del modulo scoring](#3-architettura-del-modulo-scoring)
4. [Dati in ingresso — Cosa consuma Layer D](#4-dati-in-ingresso--cosa-consuma-layer-d)
5. [Task 5.1 — Multi-Dimensional Scoring Engine](#5-task-51--multi-dimensional-scoring-engine)
6. [Task 5.2 — Domain Taxonomy & Weight Profiles](#6-task-52--domain-taxonomy--weight-profiles)
7. [Task 5.3 — Anti-Star Bias Value Score](#7-task-53--anti-star-bias-value-score)
8. [Task 5.4 — Confidence Score Calculator](#8-task-54--confidence-score-calculator)
9. [Task 5.5 — Intra-Domain Ranking Engine](#9-task-55--intra-domain-ranking-engine)
10. [Task 5.6 — Cross-Domain Comparison Guard](#10-task-56--cross-domain-comparison-guard)
11. [Task 5.7 — Explainability Report Generator](#11-task-57--explainability-report-generator)
12. [Task 5.8 — Feature Store & Caching](#12-task-58--feature-store--caching)
13. [Sequenza di implementazione](#13-sequenza-di-implementazione)
14. [Test plan](#14-test-plan)
15. [Criteri di accettazione](#15-criteri-di-accettazione)
16. [Rischi e mitigazioni](#16-rischi-e-mitigazioni)
17. [Verifica Context7](#17-verifica-context7)

---

## 1) Obiettivo

Implementare il motore di ranking finale anti-star bias (Layer D) che trasforma i risultati di Gate 1+2+3 in un ranking intra-dominio spiegabile, con gestione della confidence e identificazione delle hidden gems.

Al completamento della Phase 5:

- **Scoring engine** che combina Gate 1+2+3 in un composite multi-score per dimensione con pesi configurabili
- **Domain profiles** completi per tutti i 12 DomainType (almeno 3 profili specifici + default)
- **Anti-star bias** operativo: `ValueScore = quality_score / log10(stars + 10)` con normalizzazione edge-case
- **Confidence score** basato su completezza dati, qualità segnali, profondità assessment
- **Ranking intra-dominio** deterministico e stabile tra run identiche
- **Cross-domain guard** con warning esplicito quando si confrontano domini diversi
- **Explainability report** leggibile per sviluppatore con breakdown per dimensione
- **Feature store** SQLite-backed con TTL, SHA dedup, CRUD completo
- Tutti i moduli passano `mypy --strict` e `ruff check`
- Test coverage >80% sulla logica di scoring/ranking

### Principi fondamentali

1. **Anti-star bias**: stars sono contesto, mai criterio primario di ranking (Blueprint §3, §15)
2. **Intra-domain**: ranking separato per dominio, confronto cross-domain richiede warning
3. **Explainability**: ogni score spiegabile per feature e dimensione (Blueprint §3)
4. **Confidence**: il consumatore del ranking sa quanto fidarsi del risultato
5. **Determinismo**: stesse input → stesse output (no randomità non controllata)

---

## 2) Task Overview

| Task ID | Task | Priorità | Dipendenze | Output verificabile |
|---------|------|----------|------------|---------------------|
| 5.1 | Multi-Dimensional Scoring Engine | Critica | Phase 4 (DeepAssessmentResult), Phase 3 (ScreeningResult) | Score composito calcolato con pesi configurabili |
| 5.2 | Domain Taxonomy & Weight Profiles | Critica | 5.1 | Almeno 6 profili dominio definiti (4 esistenti + 2 nuovi) |
| 5.3 | Anti-Star Bias Value Score | Critica | 5.1 | Hidden gems rankano sopra repo popolari medi |
| 5.4 | Confidence Score Calculator | Critica | 5.1 | Repo con dati incompleti ha confidence bassa |
| 5.5 | Intra-Domain Ranking Engine | Critica | 5.1, 5.3 | Ranking stabile su 2 run successive |
| 5.6 | Cross-Domain Comparison Guard | Alta | 5.5 | Warning emesso quando si confrontano domini diversi |
| 5.7 | Explainability Report Generator | Critica | 5.1, 5.3, 5.4 | Report leggibile per sviluppatore su repo reale |
| 5.8 | Feature Store & Caching | Alta | 5.1 | Recupero feature cached senza ricalcolo |

---

## 3) Architettura del modulo scoring

### Struttura directory

```
src/github_discovery/scoring/
├── __init__.py                # Export pubblici del package scoring
├── types.py                   # ScoringContext, ScoringInput, RankingResult
├── engine.py                  # Multi-dimensional scoring engine (Task 5.1)
├── profiles.py                # Domain taxonomy & weight profiles (Task 5.2)
├── value_score.py             # Anti-star bias formula (Task 5.3)
├── confidence.py              # Confidence score calculator (Task 5.4)
├── ranker.py                  # Intra-domain ranking engine (Task 5.5)
├── cross_domain.py            # Cross-domain comparison guard (Task 5.6)
├── explainability.py          # Explainability report generator (Task 5.7)
└── feature_store.py           # SQLite-backed feature store (Task 5.8)
```

### Test structure

```
tests/unit/scoring/
├── __init__.py
├── conftest.py                # Shared fixtures (sample candidates, screening, assessment)
├── test_types.py              # ScoringContext, ScoringInput validation
├── test_engine.py             # ScoringEngine unit tests
├── test_profiles.py           # DomainProfile loading, weight validation
├── test_value_score.py        # ValueScore calculation, edge cases
├── test_confidence.py         # Confidence calculation
├── test_ranker.py             # Ranking stability, intra-domain, tie-breaking
├── test_cross_domain.py       # Cross-domain warning, normalization
├── test_explainability.py     # Report generation
└── test_feature_store.py      # CRUD, TTL, SHA dedup
```

### Data flow

```
RepoCandidate (Phase 2)
    │
    ├── ScreeningResult (Phase 3)  ← Gate 1 + Gate 2 sub-scores
    │
    ├── DeepAssessmentResult (Phase 4) ← Gate 3 dimension scores
    │                                    (optional — solo top 10-15%)
    │
    └─► ScoringInput
            │
            ▼
    ScoringEngine (5.1)
        │   ├── Mappa Gate 1+2 sub-scores → 8 dimensioni
        │   ├── Se Gate 3 disponibile: usa score LLM (alta priorità)
        │   ├── Se no: deriva score da Gate 1+2 (confidence più bassa)
        │   └── Produce dimension_scores: dict[ScoreDimension, float]
            │
            ├── DomainProfile (5.2) ← pesi per dominio
            │       → quality_score = Σ(dim_score × dim_weight)
            │
            ├── ConfidenceCalculator (5.4)
            │       → confidence basata su completezza + qualità segnali
            │
            └── ScoreResult
                    │
                    ├── ValueScoreCalculator (5.3)
                    │       → value_score = quality_score / log10(stars + 10)
                    │
                    ├── Ranker (5.5) ← intra-domain
                    │       → RankedRepo list per dominio
                    │
                    ├── ExplainabilityGenerator (5.7)
                    │       → ExplainabilityReport leggibile
                    │
                    └── FeatureStore (5.8) ← persistenza
```

---

## 4) Dati in ingresso — Cosa consuma Layer D

Layer D riceve i risultati di tutte le fasi precedenti. Ecco il mapping completo:

### Gate 1 Sub-Scores → Dimension Mapping

| Gate 1 Sub-Score | Dimensione Target | Rationale |
|-------------------|-------------------|-----------|
| `hygiene` | DOCUMENTATION, MAINTENANCE | File essenziali indicano maturità |
| `maintenance` | MAINTENANCE | Commit cadence, bus factor, recency |
| `release_discipline` | MAINTENANCE | Semver, cadence, changelog |
| `review_practice` | CODE_QUALITY, MAINTENANCE | Review → qualità codice + manutenibilità |
| `test_footprint` | TESTING | Presenza test, framework, ratio |
| `ci_cd` | TESTING, MAINTENANCE | CI/CD → testing + operations |
| `dependency_quality` | SECURITY | Pinning, lockfile, update automation |

### Gate 2 Sub-Scores → Dimension Mapping

| Gate 2 Sub-Score | Dimensione Target | Rationale |
|-------------------|-------------------|-----------|
| `security_hygiene` | SECURITY | Scorecard score, branch protection |
| `vulnerability` | SECURITY | CVE nei dependency |
| `complexity` | ARCHITECTURE | LOC, language breakdown, file count |
| `secret_hygiene` | SECURITY | Leaked secrets nel git history |

### Gate 3 Dimension Scores → Direct Mapping

| Gate 3 Dimensione | ScoreDimension | Priorità vs Gate 1+2 |
|--------------------|---------------|---------------------|
| Code Quality | CODE_QUALITY | **Sovrascrive** derivazione Gate 1+2 |
| Architecture | ARCHITECTURE | **Sovrascrive** derivazione Gate 1+2 |
| Testing | TESTING | **Sovrascrive** derivazione Gate 1+2 |
| Documentation | DOCUMENTATION | **Sovrascrive** derivazione Gate 1+2 |
| Maintenance | MAINTENANCE | **Sovrascrive** derivazione Gate 1+2 |
| Security | SECURITY | **Sovrascrive** derivazione Gate 1+2 |
| Functionality | FUNCTIONALITY | **Unica fonte** (non derivabile da Gate 1+2) |
| Innovation | INNOVATION | **Unica fonte** (non derivabile da Gate 1+2) |

### Priorità di composizione

Per ogni dimensione:
1. **Gate 3 score disponibile** → usa quello (confidence alta)
2. **Gate 3 non disponibile** → deriva da Gate 1+2 sub-score mappati (confidence media-bassa)
3. **Nessun dato** → score neutrale 0.5 con confidence 0.0

---

## 5) Task 5.1 — Multi-Dimensional Scoring Engine

### Obiettivo

Il cuore di Layer D: combina Gate 1+2+3 in un composite score per dimensione, applica pesi di dominio, gestisce dati mancanti.

### File: `scoring/engine.py`

### Design

```python
class ScoringEngine:
    """Multi-dimensional scoring engine (Layer D).
    
    Combines Gate 1 + Gate 2 + Gate 3 results into a composite
    quality score with per-dimension breakdown.
    
    Priority for each dimension:
    1. Gate 3 (LLM deep assessment) — highest confidence
    2. Gate 1+2 derived scores — medium confidence
    3. Neutral default (0.5, confidence 0.0) — no data
    """
    
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
    
    def score(
        self,
        candidate: RepoCandidate,
        screening: ScreeningResult | None = None,
        assessment: DeepAssessmentResult | None = None,
        profile: DomainProfile | None = None,
    ) -> ScoreResult:
        """Score a single candidate.
        
        Args:
            candidate: Repo metadata (includes stars for ValueScore).
            screening: Gate 1+2 screening result (optional).
            assessment: Gate 3 deep assessment (optional, only for top %).
            profile: Domain profile for weighting (auto-detected if None).
        
        Returns:
            ScoreResult with composite quality_score, per-dimension scores,
            confidence, and value_score (computed field).
        """
        ...
    
    def score_batch(
        self,
        inputs: list[ScoringInput],
        profile: DomainProfile | None = None,
    ) -> list[ScoreResult]:
        """Score a batch of candidates.
        
        All candidates are scored with the same domain profile
        (or their own if profile is None).
        """
        ...
    
    def _compute_dimension_scores(
        self,
        screening: ScreeningResult | None,
        assessment: DeepAssessmentResult | None,
    ) -> dict[ScoreDimension, DimensionScoreInfo]:
        """Compute per-dimension scores from available data.
        
        Returns DimensionScoreInfo with value, confidence, source
        for each of the 8 dimensions.
        """
        ...
    
    def _derive_from_screening(
        self,
        screening: ScreeningResult,
    ) -> dict[ScoreDimension, float]:
        """Derive preliminary dimension scores from Gate 1+2.
        
        Maps sub-scores to dimensions using weighted composition.
        Confidence is lower than Gate 3 assessment.
        """
        ...
    
    def _apply_weights(
        self,
        dimension_scores: dict[ScoreDimension, DimensionScoreInfo],
        profile: DomainProfile,
    ) -> float:
        """Apply domain-specific weights to compute composite quality_score."""
        ...
```

### Tipi di supporto — `scoring/types.py`

```python
class DimensionScoreInfo(BaseModel):
    """Internal representation of a dimension's score with metadata."""
    dimension: ScoreDimension
    value: float  # 0.0-1.0
    confidence: float  # 0.0-1.0
    source: str  # "gate3_llm", "gate12_derived", "default_neutral"
    contributing_signals: list[str]  # Which sub-scores contributed


class ScoringInput(BaseModel):
    """Complete input for scoring a single candidate."""
    candidate: RepoCandidate
    screening: ScreeningResult | None = None
    assessment: DeepAssessmentResult | None = None


class ScoringContext(BaseModel):
    """Context for a batch scoring operation."""
    inputs: list[ScoringInput]
    domain_override: DomainType | None = None
    profile_override: DomainProfile | None = None
    session_id: str | None = None


class RankingResult(BaseModel):
    """Complete ranking result for a domain."""
    domain: DomainType
    ranked_repos: list[RankedRepo]
    total_candidates: int
    hidden_gems: list[RankedRepo]  # Top value_score repos with low stars
    generated_at: datetime
    session_id: str | None = None
```

### Derivazione Gate 1+2 → Dimensioni

La mappatura concreta per `_derive_from_screening`:

```python
# Dimensione → (sub-score Gate 1/2, peso nella derivazione)
_DERIVATION_MAP: dict[ScoreDimension, list[tuple[str, float]]] = {
    ScoreDimension.CODE_QUALITY: [
        ("review_practice", 0.5),
        ("ci_cd", 0.3),
        ("dependency_quality", 0.2),
    ],
    ScoreDimension.ARCHITECTURE: [
        ("complexity", 0.7),
        ("ci_cd", 0.3),
    ],
    ScoreDimension.TESTING: [
        ("test_footprint", 0.7),
        ("ci_cd", 0.3),
    ],
    ScoreDimension.DOCUMENTATION: [
        ("hygiene", 0.6),
        ("review_practice", 0.4),
    ],
    ScoreDimension.MAINTENANCE: [
        ("maintenance", 0.4),
        ("release_discipline", 0.3),
        ("ci_cd", 0.2),
        ("hygiene", 0.1),
    ],
    ScoreDimension.SECURITY: [
        ("security_hygiene", 0.35),
        ("vulnerability", 0.25),
        ("secret_hygiene", 0.25),
        ("dependency_quality", 0.15),
    ],
    ScoreDimension.FUNCTIONALITY: [],  # Solo Gate 3
    ScoreDimension.INNOVATION: [],      # Solo Gate 3
}
```

Per FUNCTIONALITY e INNOVATION: non derivabili da Gate 1+2. Senza Gate 3: valore neutrale 0.5, confidence 0.0.

### Accettazione

- [ ] `ScoringEngine.score()` produce `ScoreResult` con 8 dimensioni
- [ ] Gate 3 disponibile → dimension score sovrascrive derivazione Gate 1+2
- [ ] Gate 3 non disponibile → dimension score deriva da Gate 1+2 con confidence più bassa
- [ ] Nessun dato → neutrale 0.5, confidence 0.0
- [ ] `quality_score` calcolato con pesi di dominio
- [ ] `value_score` calcolato automaticamente (computed_field)
- [ ] Batch scoring funziona su lista di ScoringInput
- [ ] ≥15 unit tests

---

## 6) Task 5.2 — Domain Taxonomy & Weight Profiles

### Obiettivo

Completare i profili di dominio per tutti i 12 DomainType con pesi specifici, supporto YAML/env per personalizzazione, e validazione rigorosa.

### File: `scoring/profiles.py`

### Design

```python
class ProfileRegistry:
    """Registry of domain profiles with loading and validation.
    
    Supports:
    - Built-in profiles for all 12 DomainType values
    - YAML/env override for custom weights
    - Validation: weights must sum to 1.0
    """
    
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._profiles = self._load_profiles()
    
    def get(self, domain: DomainType) -> DomainProfile:
        """Get profile for a domain (built-in or default)."""
        ...
    
    def all_profiles(self) -> dict[DomainType, DomainProfile]:
        """Return all registered profiles."""
        ...
    
    def register(self, profile: DomainProfile) -> None:
        """Register a custom profile (replaces built-in)."""
        ...
    
    def _load_profiles(self) -> dict[DomainType, DomainProfile]:
        """Load profiles: built-in → YAML override → env override."""
        ...
    
    @staticmethod
    def validate_profile(profile: DomainProfile) -> None:
        """Validate a profile: weights sum, threshold ranges."""
        ...
```

### Profili da aggiungere (oltre ai 4 esistenti)

```python
# models/scoring.py ha già: LIBRARY, CLI, DEVOPS, BACKEND, DEFAULT
# Aggiungere in profiles.py:

WEB_FRAMEWORK_PROFILE = DomainProfile(
    domain_type=DomainType.WEB_FRAMEWORK,
    display_name="Web Framework",
    description="Web frameworks and servers",
    dimension_weights={
        ScoreDimension.CODE_QUALITY: 0.15,
        ScoreDimension.ARCHITECTURE: 0.15,
        ScoreDimension.TESTING: 0.15,
        ScoreDimension.DOCUMENTATION: 0.15,  # Docs critici per framework
        ScoreDimension.MAINTENANCE: 0.15,
        ScoreDimension.SECURITY: 0.10,
        ScoreDimension.FUNCTIONALITY: 0.10,
        ScoreDimension.INNOVATION: 0.05,
    },
    star_baseline=5000.0,  # Frameworks tendono ad avere più stars
    preferred_channels=["search", "registry", "dependency"],
)

DATA_TOOL_PROFILE = DomainProfile(
    domain_type=DomainType.DATA_TOOL,
    display_name="Data Tool",
    description="Data processing and analysis tools",
    dimension_weights={
        ScoreDimension.CODE_QUALITY: 0.15,
        ScoreDimension.ARCHITECTURE: 0.10,
        ScoreDimension.TESTING: 0.10,
        ScoreDimension.DOCUMENTATION: 0.15,  # Docs critici per data tools
        ScoreDimension.MAINTENANCE: 0.15,
        ScoreDimension.SECURITY: 0.10,
        ScoreDimension.FUNCTIONALITY: 0.20,  # Functional completeness > testing
        ScoreDimension.INNOVATION: 0.05,
    },
    star_baseline=800.0,
    preferred_channels=["search", "registry", "awesome_list"],
)

ML_LIB_PROFILE = DomainProfile(
    domain_type=DomainType.ML_LIB,
    display_name="ML Library",
    description="Machine learning libraries",
    dimension_weights={
        ScoreDimension.CODE_QUALITY: 0.10,
        ScoreDimension.ARCHITECTURE: 0.10,
        ScoreDimension.TESTING: 0.10,
        ScoreDimension.DOCUMENTATION: 0.10,
        ScoreDimension.MAINTENANCE: 0.15,
        ScoreDimension.SECURITY: 0.05,  # Security meno critica per ML
        ScoreDimension.FUNCTIONALITY: 0.25,  # Functional completeness matters
        ScoreDimension.INNOVATION: 0.15,  # Innovation peso più alto
    },
    star_baseline=2000.0,
    preferred_channels=["search", "registry", "dependency"],
)

# SECURITY_TOOL, LANG_TOOL, TEST_TOOL, DOC_TOOL
# usano DEFAULT_PROFILE con piccole variazioni di threshold
```

### Configurazione aggiuntiva — `ScoringSettings`

Aggiungere a `config.py`:

```python
class ScoringSettings(BaseSettings):
    """Scoring and ranking settings (Layer D)."""
    
    model_config = SettingsConfigDict(
        env_prefix="GHDISC_SCORING_",
        env_file=".env",
    )
    
    min_confidence: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum confidence to include in ranking",
    )
    hidden_gem_star_threshold: int = Field(
        default=500,
        description="Max stars for a repo to be considered 'hidden gem'",
    )
    hidden_gem_min_quality: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Min quality_score to qualify as hidden gem",
    )
    feature_store_ttl_hours: int = Field(
        default=48,
        description="Feature store TTL in hours",
    )
    ranking_seed: int = Field(
        default=42,
        description="Seed for deterministic tie-breaking in ranking",
    )
    cross_domain_warning: bool = Field(
        default=True,
        description="Emit warning on cross-domain comparisons",
    )
    custom_profiles_path: str = Field(
        default="",
        description="Path to YAML file with custom domain profiles",
    )
```

### Accettazione

- [ ] Profili definiti per almeno 6 DomainType (4 esistenti + 2 nuovi da roadmap: WEB_FRAMEWORK, DATA_TOOL)
- [ ] Tutti i pesi sommano a 1.0 (±0.01)
- [ ] `ProfileRegistry.get()` ritorna profilo corretto per dominio
- [ ] `DEFAULT_PROFILE` fallback per domini senza profilo specifico
- [ ] `ScoringSettings` aggiunto a `config.py` con env prefix `GHDISC_SCORING_`
- [ ] ≥10 unit tests

---

## 7) Task 5.3 — Anti-Star Bias Value Score

### Obiettivo

Implementare il calcolo del Value Score anti-star bias con gestione edge-case, normalizzazione, e identificazione hidden gems.

### File: `scoring/value_score.py`

### Design

```python
class ValueScoreCalculator:
    """Anti-star bias Value Score calculation.
    
    Formula: ValueScore = quality_score / log10(star_count + 10)
    
    This identifies hidden gems: repos with high quality but low visibility.
    
    Reference: Blueprint §5, §15 — anti-popularity debiasing.
    """
    
    # Constants
    _STAR_OFFSET = 10  # Prevents division issues at zero stars
    _MAX_VALUE_SCORE = 1.0  # Cap for normalization
    _HIDDEN_GEM_STAR_THRESHOLD = 500  # Max stars for hidden gem
    _HIDDEN_GEM_MIN_QUALITY = 0.7  # Min quality for hidden gem
    
    def __init__(self, settings: ScoringSettings | None = None) -> None:
        ...
    
    def compute(self, quality_score: float, stars: int) -> float:
        """Compute Value Score with edge-case handling.
        
        Args:
            quality_score: Domain-weighted composite (0.0-1.0).
            stars: Star count at scoring time.
        
        Returns:
            Value score (0.0+). Higher = more undervalued.
        """
        ...
    
    def is_hidden_gem(
        self,
        quality_score: float,
        stars: int,
        value_score: float,
    ) -> tuple[bool, str]:
        """Determine if repo qualifies as a hidden gem.
        
        Returns (is_gem, reason).
        """
        ...
    
    def star_context(self, quality_score: float, stars: int, domain: DomainType) -> str:
        """Generate human-readable star context string.
        
        Examples:
        - "42 stars — low visibility for this quality level"
        - "15,000 stars — quality consistent with popularity"
        - "0 stars — new/unknown, quality assessment valuable"
        """
        ...
    
    def normalize_batch(
        self,
        scores: list[tuple[str, float, int]],  # (full_name, quality, stars)
    ) -> list[tuple[str, float]]:
        """Normalize value scores across a batch to 0.0-1.0 range.
        
        Useful for cross-domain comparison where absolute value_score
        may vary significantly between domains.
        """
        ...
```

### Edge-case handling

| Scenario | stars | quality_score | value_score | Note |
|----------|-------|---------------|-------------|------|
| Repo nuova, 0 stars | 0 | 0.8 | 0.800 | log10(10) = 1.0 |
| Repo piccola, 10 stars | 10 | 0.8 | 0.514 | log10(20) ≈ 1.30 |
| Repo media, 100 stars | 100 | 0.8 | 0.400 | log10(110) ≈ 2.04 |
| Repo popolare, 1k stars | 1000 | 0.8 | 0.267 | log10(1010) ≈ 3.00 |
| Repo molto popolare, 10k stars | 10000 | 0.8 | 0.200 | log10(10010) ≈ 4.00 |
| Quality 0 | any | 0.0 | 0.0 | Evita divisione |
| Hidden gem: 50 stars, quality 0.9 | 50 | 0.9 | 0.531 | Alto! |
| Non gem: 5000 stars, quality 0.6 | 5000 | 0.6 | 0.150 | Basso |

### Accettazione

- [ ] Formula `quality_score / log10(stars + 10)` implementata correttamente
- [ ] Edge case: quality_score = 0 → value_score = 0
- [ ] Edge case: stars = 0 → denominatore = 1.0 (log10(10))
- [ ] Hidden gem detection: stars < threshold AND quality > min_quality
- [ ] `star_context()` genera stringhe leggibili
- [ ] `normalize_batch()` normalizza a [0.0, 1.0]
- [ ] Hidden gems rankano sopra repo popolari medi (verificabile con test)
- [ ] ≥12 unit tests

---

## 8) Task 5.4 — Confidence Score Calculator

### Obiettivo

Calcolare un confidence score significativo basato su completezza dei dati, qualità dei segnali, e profondità dell'assessment.

### File: `scoring/confidence.py`

### Design

```python
class ConfidenceCalculator:
    """Confidence score calculator for scoring results.
    
    Confidence reflects how reliable the scoring result is, based on:
    - Data completeness: how many dimensions have actual data vs defaults
    - Signal quality: Gate 3 LLM (high) vs Gate 1+2 derived (medium) vs default (low)
    - Assessment depth: which gates were completed
    
    Reference: Blueprint §7 — confidence indicators per dimension.
    """
    
    def compute(
        self,
        dimension_infos: dict[ScoreDimension, DimensionScoreInfo],
        screening: ScreeningResult | None = None,
        assessment: DeepAssessmentResult | None = None,
    ) -> float:
        """Compute overall confidence for a scoring result.
        
        Returns weighted average of dimension confidences,
        with bonus for complete gate coverage.
        
        Args:
            dimension_infos: Per-dimension score metadata.
            screening: Gate 1+2 results (if available).
            assessment: Gate 3 results (if available).
        
        Returns:
            Overall confidence (0.0-1.0).
        """
        ...
    
    def compute_dimension_confidence(
        self,
        dimension: ScoreDimension,
        source: str,
        screening: ScreeningResult | None,
        assessment: DeepAssessmentResult | None,
    ) -> float:
        """Compute confidence for a single dimension.
        
        Source-based confidence:
        - "gate3_llm": use LLM-reported confidence (typically 0.6-0.9)
        - "gate12_derived": 0.3-0.5 (indirect signal)
        - "default_neutral": 0.0 (no data)
        """
        ...
    
    def gate_coverage_bonus(
        self,
        screening: ScreeningResult | None,
        assessment: DeepAssessmentResult | None,
    ) -> float:
        """Bonus for having completed more gates.
        
        - Gate 1 only: +0.0
        - Gate 1+2: +0.05
        - Gate 1+2+3: +0.10
        """
        ...
```

### Confidence ranges attesi

| Scenario | Confidence Range | Rationale |
|----------|-----------------|-----------|
| Solo Gate 1 | 0.25-0.40 | Solo metadata, no static analysis |
| Gate 1+2, no Gate 3 | 0.35-0.55 | Derived scores, limited precision |
| Gate 1+2+3 (partial dims) | 0.50-0.70 | Mix of LLM and derived |
| Gate 1+2+3 (all 8 dims) | 0.65-0.90 | Full assessment coverage |
| No data at all | 0.00 | All defaults |

### Accettazione

- [ ] Confidence calcolata come media pesata delle dimensione confidences
- [ ] Gate 3 source → confidence alta (usa LLM-reported value)
- [ ] Gate 1+2 derived → confidence media (0.3-0.5)
- [ ] Default neutral → confidence 0.0
- [ ] Gate coverage bonus aggiunto (+0.05 per gate aggiuntivo)
- [ ] Range output sempre [0.0, 1.0]
- [ ] ≥10 unit tests

---

## 9) Task 5.5 — Intra-Domain Ranking Engine

### Obiettivo

Ranking intra-dominio deterministico e stabile. Nessun confronto diretto cross-domain.

### File: `scoring/ranker.py`

### Design

```python
class Ranker:
    """Intra-domain ranking engine.
    
    Ranks repos within a single domain by value_score.
    Cross-domain comparison requires explicit normalization + warning.
    
    Properties:
    - Deterministic: same inputs → same ranking (seed-based tie-breaking)
    - Stable: small score changes → small rank changes
    - Intra-domain: separate ranking per DomainType
    """
    
    def __init__(self, settings: ScoringSettings | None = None) -> None:
        ...
    
    def rank(
        self,
        results: list[ScoreResult],
        domain: DomainType,
        *,
        min_confidence: float = 0.3,
        min_value_score: float = 0.0,
        max_results: int | None = None,
    ) -> RankingResult:
        """Rank repos within a domain.
        
        Steps:
        1. Filter by domain, min_confidence, min_value_score
        2. Sort by value_score (descending)
        3. Assign rank positions (1-based)
        4. Identify hidden gems
        5. Return RankingResult
        
        Args:
            results: Scored repos to rank.
            domain: Domain to rank within.
            min_confidence: Minimum confidence to include.
            min_value_score: Minimum value_score to include.
            max_results: Limit results (None = all).
        
        Returns:
            RankingResult with ranked repos and hidden gems.
        """
        ...
    
    def rank_multi_domain(
        self,
        results: list[ScoreResult],
        *,
        min_confidence: float = 0.3,
    ) -> dict[DomainType, RankingResult]:
        """Rank repos across all domains (separate rankings).
        
        Returns a dict of RankingResult keyed by DomainType.
        Each domain has its own independent ranking.
        """
        ...
    
    def _sort_key(self, result: ScoreResult) -> tuple[float, float, str]:
        """Deterministic sort key for ranking.
        
        Primary: value_score (descending → negate)
        Secondary: quality_score (descending → negate)
        Tertiary: full_name (ascending → alphabetical)
        
        This ensures deterministic ranking even with identical scores.
        """
        ...
    
    def _identify_hidden_gems(
        self,
        ranked: list[RankedRepo],
        domain: DomainType,
    ) -> list[RankedRepo]:
        """Identify hidden gems from ranked list.
        
        Hidden gem criteria:
        - stars < hidden_gem_star_threshold
        - quality_score >= hidden_gem_min_quality
        - value_score in top 25% of domain
        """
        ...
```

### Stabilità del ranking

- Sort deterministico: `(-value_score, -quality_score, full_name)`
- `full_name` come tie-breaker garantisce ordine stabile
- Nessun random: no `random.shuffle` o `random.choice`
- `ranking_seed` nelle settings riservato per uso futuro (es. sampling)

### Accettazione

- [ ] Ranking intra-dominio: repos ordinate per value_score descending
- [ ] Tie-breaking deterministico (quality_score, poi alphabetical)
- [ ] Ranking stabile: stesse input → stesso ordine
- [ ] Filtri: min_confidence, min_value_score, max_results funzionano
- [ ] Hidden gem identification con criteri configurabili
- [ ] `rank_multi_domain()` produce ranking separati per dominio
- [ ] ≥15 unit tests (inclusi test stabilità)

---

## 10) Task 5.6 — Cross-Domain Comparison Guard

### Obiettivo

Prevenire confronti cross-domain ingiusti. Se richiesto, normalizzare con warning esplicito.

### File: `scoring/cross_domain.py`

### Design

```python
class CrossDomainGuard:
    """Guard against unfair cross-domain comparisons.
    
    Different domains have different quality baselines, star expectations,
    and weight profiles. Direct comparison is misleading.
    
    When cross-domain comparison is requested:
    1. Emit warning with explanation
    2. Normalize scores relative to domain mean
    3. Return results with explicit domain labels
    """
    
    def __init__(self, settings: ScoringSettings | None = None) -> None:
        ...
    
    def compare(
        self,
        results: list[ScoreResult],
    ) -> CrossDomainComparison:
        """Compare repos potentially across domains.
        
        If all repos are same domain → direct comparison (no warning).
        If mixed domains → normalized comparison with warning.
        
        Returns CrossDomainComparison with:
        - results sorted by normalized_value_score
        - warnings if cross-domain
        - per-domain context for interpretation
        """
        ...
    
    def _check_cross_domain(self, results: list[ScoreResult]) -> bool:
        """Check if results span multiple domains."""
        ...
    
    def _normalize_scores(
        self,
        results: list[ScoreResult],
    ) -> list[NormalizedScore]:
        """Normalize scores relative to domain mean.
        
        For each domain:
        1. Compute domain mean quality_score
        2. normalized = (quality_score - domain_mean) / domain_std + 0.5
        
        This centers each domain around 0.5 with relative positioning.
        """
        ...
    
    def _generate_warning(
        self,
        domains: set[DomainType],
    ) -> str:
        """Generate human-readable warning about cross-domain comparison."""
        ...
```

### Tipi aggiuntivi

```python
class NormalizedScore(BaseModel):
    """Score normalized for cross-domain comparison."""
    full_name: str
    domain: DomainType
    original_quality: float
    normalized_quality: float  # Relative to domain mean
    original_value_score: float
    normalized_value_score: float
    domain_mean: float
    domain_std: float


class CrossDomainComparison(BaseModel):
    """Result of a cross-domain comparison with warnings."""
    results: list[NormalizedScore]
    is_cross_domain: bool
    warnings: list[str]
    domain_summaries: dict[DomainType, dict[str, float]]  # mean, std, count
```

### Accettazione

- [ ] Same-domain comparison → no warning
- [ ] Cross-domain comparison → warning emesso
- [ ] Normalizzazione relativa al dominio (mean-centering)
- [ ] `CrossDomainComparison` contiene warning leggibile
- [ ] Domain summaries con mean/std per contesto
- [ ] ≥8 unit tests

---

## 11) Task 5.7 — Explainability Report Generator

### Obiettivo

Generare report leggibili per sviluppatore con breakdown per dimensione, contesto stellare, e confronto con baseline star-based.

### File: `scoring/explainability.py`

### Design

```python
class ExplainabilityGenerator:
    """Generate human-readable explainability reports.
    
    Every score must be explainable per feature and dimension (Blueprint §3).
    Reports provide both human-readable explanations and machine-readable
    feature breakdowns for transparency.
    
    Two detail levels:
    - "summary": top-5 features, overall assessment, hidden gem indicator
    - "full": complete dimension breakdown, all evidence, recommendations
    """
    
    def __init__(
        self,
        value_calculator: ValueScoreCalculator | None = None,
        profile_registry: ProfileRegistry | None = None,
    ) -> None:
        ...
    
    def explain(
        self,
        score_result: ScoreResult,
        dimension_infos: dict[ScoreDimension, DimensionScoreInfo] | None = None,
        screening: ScreeningResult | None = None,
        assessment: DeepAssessmentResult | None = None,
        *,
        detail_level: str = "summary",  # "summary" or "full"
    ) -> ExplainabilityReport:
        """Generate explainability report for a scored repo.
        
        Args:
            score_result: The scoring result to explain.
            dimension_infos: Per-dimension metadata (sources, signals).
            screening: Gate 1+2 results for evidence extraction.
            assessment: Gate 3 results for evidence extraction.
            detail_level: "summary" (concise) or "full" (complete).
        
        Returns:
            ExplainabilityReport with breakdown, strengths, weaknesses.
        """
        ...
    
    def compare_reports(
        self,
        reports: list[ExplainabilityReport],
    ) -> str:
        """Generate side-by-side comparison text for multiple repos.
        
        Used by MCP tool compare_repos for decision-making.
        """
        ...
    
    def _extract_strengths(
        self,
        dimension_infos: dict[ScoreDimension, DimensionScoreInfo],
        score_result: ScoreResult,
    ) -> list[str]:
        """Extract top 3-5 strengths from dimension scores.
        
        Strengths are dimensions where score > 0.7 * max_dimension_score.
        """
        ...
    
    def _extract_weaknesses(
        self,
        dimension_infos: dict[ScoreDimension, DimensionScoreInfo],
        score_result: ScoreResult,
    ) -> list[str]:
        """Extract top 3-5 weaknesses from dimension scores.
        
        Weaknesses are dimensions where score < 0.5 or confidence < 0.3.
        """
        ...
    
    def _generate_recommendations(
        self,
        weaknesses: list[str],
        dimension_infos: dict[ScoreDimension, DimensionScoreInfo],
    ) -> list[str]:
        """Generate actionable recommendations based on weaknesses."""
        ...
    
    def _build_star_context(
        self,
        score_result: ScoreResult,
        profile: DomainProfile,
    ) -> str:
        """Build star context string with domain awareness."""
        ...
    
    def _dimension_breakdown(
        self,
        score_result: ScoreResult,
        dimension_infos: dict[ScoreDimension, DimensionScoreInfo],
        detail_level: str,
    ) -> dict[str, dict[str, object]]:
        """Build per-dimension breakdown for the report."""
        ...
```

### Formato output

**Summary** (≤500 tokens):
```
## python-httpstat — Library Domain

**Quality: 0.82/1.0** | **Value Score: 0.41** | ⭐ 892 stars

**Hidden Gem** ✓ — High quality with moderate visibility

### Top Strengths
- Testing (0.90): Comprehensive test suite with pytest, CI integration
- Code Quality (0.85): Clean codebase, consistent style

### Key Weaknesses  
- Documentation (0.55): Missing API docs, minimal README
- Security (0.50): No SECURITY.md, no dependabot config

### Star Context
892 stars — moderate visibility. Quality suggests it deserves wider adoption.
```

**Full** (≤2000 tokens): include per-dimension breakdown with score, weight, source, evidence, explanation.

### Accettazione

- [ ] Report "summary" con strengths, weaknesses, star context
- [ ] Report "full" con per-dimension breakdown completo
- [ ] Hidden gem indicator con reason
- [ ] Star context leggibile e domain-aware
- [ ] `compare_reports()` genera confronto side-by-side
- [ ] Recommendations basate su weaknesses
- [ ] ≥12 unit tests

---

## 12) Task 5.8 — Feature Store & Caching

### Obiettivo

Persistenza feature calcolate per repo (evita ricalcolo), con key su `repo_full_name + commit_sha`, TTL configurabile, invalidazione su nuovo commit.

### File: `scoring/feature_store.py`

### Design

```python
class FeatureStore:
    """SQLite-backed feature store for caching computed scores.
    
    Stores ScoreResult per repo+SHA. Avoids expensive recomputation
    when the same repo at the same commit is scored again.
    
    Key: full_name + commit_sha (same as models/features.py)
    TTL: configurable (default 48 hours)
    Invalidation: automatic on new commit_sha or TTL expiry
    
    Consistent with discovery/pool.py SQLite pattern.
    """
    
    def __init__(
        self,
        db_path: str = ":memory:",
        ttl_hours: int = 48,
    ) -> None:
        ...
    
    async def initialize(self) -> None:
        """Create tables if not exist."""
        ...
    
    async def get(
        self,
        full_name: str,
        commit_sha: str,
    ) -> ScoreResult | None:
        """Get cached score result. Returns None if not found or expired."""
        ...
    
    async def put(self, result: ScoreResult) -> None:
        """Store a score result. Upsert on full_name + commit_sha."""
        ...
    
    async def get_batch(
        self,
        keys: list[tuple[str, str]],  # (full_name, commit_sha)
    ) -> dict[str, ScoreResult | None]:
        """Get multiple cached results at once."""
        ...
    
    async def put_batch(self, results: list[ScoreResult]) -> None:
        """Store multiple results at once."""
        ...
    
    async def delete(self, full_name: str, commit_sha: str) -> bool:
        """Delete a cached result. Returns True if existed."""
        ...
    
    async def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        ...
    
    async def get_stats(self) -> FeatureStoreStats:
        """Get store statistics (total entries, expired, by domain)."""
        ...
    
    async def close(self) -> None:
        """Close database connection."""
        ...


class FeatureStoreStats(BaseModel):
    """Statistics about the feature store."""
    total_entries: int
    expired_entries: int
    domains: dict[str, int]  # domain → count
    oldest_entry: datetime | None
    newest_entry: datetime | None
```

### Schema SQLite

```sql
CREATE TABLE IF NOT EXISTS score_features (
    full_name TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    domain TEXT NOT NULL DEFAULT 'other',
    quality_score REAL NOT NULL,
    value_score REAL NOT NULL,
    confidence REAL NOT NULL,
    stars INTEGER NOT NULL DEFAULT 0,
    gate1_total REAL NOT NULL DEFAULT 0.0,
    gate2_total REAL NOT NULL DEFAULT 0.0,
    gate3_available INTEGER NOT NULL DEFAULT 0,
    dimension_scores TEXT NOT NULL DEFAULT '{}',  -- JSON
    scored_at TEXT NOT NULL,
    ttl_hours INTEGER NOT NULL DEFAULT 48,
    PRIMARY KEY (full_name, commit_sha)
);

CREATE INDEX IF NOT EXISTS idx_score_features_domain ON score_features(domain);
CREATE INDEX IF NOT EXISTS idx_score_features_scored_at ON score_features(scored_at);
```

### Accettazione

- [ ] SQLite persistence con schema sopra
- [ ] `get()` ritorna ScoreResult se non scaduto, None altrimenti
- [ ] `put()` upsert su full_name + commit_sha
- [ ] TTL scadenza verificata (entries oltre TTL non ritornate)
- [ ] Batch operations funzionano
- [ ] `cleanup_expired()` rimuove entries scadute
- [ ] `get_stats()` ritorna statistiche aggregate
- [ ] Consistente con discovery/pool.py (aiosqlite pattern)
- [ ] ≥15 unit tests

---

## 13) Sequenza di implementazione

Implementazione in 4 onde, ciascuna testabile indipendentemente:

### Wave 1 — Types & Infrastructure (Task 5.1 partial, 5.2)
- `scoring/types.py` — ScoringInput, ScoringContext, DimensionScoreInfo, RankingResult
- `scoring/profiles.py` — ProfileRegistry + nuovi profili dominio
- `config.py` — Aggiungere ScoringSettings
- **Test**: test_types.py, test_profiles.py
- **~25 tests**

### Wave 2 — Core Scoring (Task 5.1, 5.3, 5.4)
- `scoring/engine.py` — ScoringEngine (combinazione Gate 1+2+3)
- `scoring/value_score.py` — ValueScoreCalculator (anti-star bias)
- `scoring/confidence.py` — ConfidenceCalculator
- **Test**: test_engine.py, test_value_score.py, test_confidence.py
- **~37 tests**

### Wave 3 — Ranking & Comparison (Task 5.5, 5.6)
- `scoring/ranker.py` — Ranker (intra-domain)
- `scoring/cross_domain.py` — CrossDomainGuard
- **Test**: test_ranker.py, test_cross_domain.py
- **~23 tests**

### Wave 4 — Explainability & Persistence (Task 5.7, 5.8)
- `scoring/explainability.py` — ExplainabilityGenerator
- `scoring/feature_store.py` — FeatureStore (SQLite)
- `scoring/__init__.py` — Aggiornare exports
- **Test**: test_explainability.py, test_feature_store.py
- **~27 tests**

**Totale stimato: ~112 tests**

### Dipendenze tra onde

```
Wave 1 (types, profiles, config)
    │
    └─► Wave 2 (engine, value_score, confidence)
            │
            └─► Wave 3 (ranker, cross_domain)
                    │
                    └─► Wave 4 (explainability, feature_store, exports)
```

---

## 14) Test plan

### Unit Tests per modulo

| Modulo | File test | # Tests stimati | Focus |
|--------|-----------|-----------------|-------|
| `types.py` | `test_types.py` | 8 | Model validation, defaults, edge cases |
| `engine.py` | `test_engine.py` | 15 | Gate 1+2+3 → dimension scores, weight application, batch |
| `profiles.py` | `test_profiles.py` | 10 | Profile loading, weight validation, registry, YAML override |
| `value_score.py` | `test_value_score.py` | 12 | Formula, edge cases (0 stars, 0 quality), hidden gem, normalization |
| `confidence.py` | `test_confidence.py` | 10 | Confidence ranges, gate coverage bonus, dimension source |
| `ranker.py` | `test_ranker.py` | 15 | Intra-domain sort, tie-breaking, stability, filters, hidden gems |
| `cross_domain.py` | `test_cross_domain.py` | 8 | Same/cross domain detection, normalization, warning |
| `explainability.py` | `test_explainability.py` | 12 | Summary/full reports, strengths/weaknesses, star context |
| `feature_store.py` | `test_feature_store.py` | 15 | CRUD, TTL, batch, cleanup, stats |
| **Totale** | | **~105** | |

### Fixture condivise — `conftest.py`

```python
@pytest.fixture
def sample_candidate() -> RepoCandidate:
    """Repo candidate with realistic metadata."""
    ...

@pytest.fixture
def sample_screening_result() -> ScreeningResult:
    """Screening result with Gate 1+2 passed."""
    ...

@pytest.fixture
def sample_assessment_result() -> DeepAssessmentResult:
    """Deep assessment result with all 8 dimensions."""
    ...

@pytest.fixture
def sample_scoring_input(
    sample_candidate,
    sample_screening_result,
    sample_assessment_result,
) -> ScoringInput:
    """Complete scoring input with all gates."""
    ...

@pytest.fixture
def scoring_engine() -> ScoringEngine:
    """ScoringEngine with default settings."""
    ...

@pytest.fixture
def value_calculator() -> ValueScoreCalculator:
    """ValueScoreCalculator with default settings."""
    ...

@pytest.fixture
def ranker() -> Ranker:
    """Ranker with default settings."""
    ...

@pytest.fixture
def feature_store(tmp_path) -> FeatureStore:
    """FeatureStore with temp SQLite database."""
    ...
```

### Test critici per accettazione

1. **Anti-star bias**: Hidden gem (50 stars, quality 0.9) rankano sopra mediocre popolare (5000 stars, quality 0.5)
2. **Determinismo**: `ranker.rank()` su stesso input produce stesso ordine
3. **Confidence gradient**: Gate 1+2+3 > Gate 1+2 > Gate 1 > no data
4. **Feature store TTL**: Entry scaduta non ritornata da `get()`
5. **Cross-domain warning**: Warning emesso quando domini diversi
6. **Explainability**: Report generato con strengths e weaknesses validi

---

## 15) Criteri di accettazione

### Must-have (tutti richiesti per Milestone M4)

| # | Criterio | Verifica |
|---|----------|----------|
| 1 | `make ci` verde: ruff + mypy --strict + pytest | CI passing |
| 2 | ≥100 unit tests nella directory `tests/unit/scoring/` | `pytest tests/unit/scoring/ -v` |
| 3 | ScoreResult prodotto con 8 dimensioni per ogni repo | Test end-to-end |
| 4 | Anti-star bias: hidden gems rankano sopra repo popolari medi | Test specifico |
| 5 | Ranking intra-dominio deterministico | 2 run identiche → stesso ordine |
| 6 | Confidence score significativo (range corretto per scenario) | Test per scenario |
| 7 | Explainability report leggibile (summary + full) | Visual inspection + test |
| 8 | Feature store CRUD + TTL funzionante | Test CRUD |
| 9 | Cross-domain warning emesso quando appropriato | Test warning |
| 10 | Almeno 6 profili dominio definiti | Code review |
| 11 | `scoring/__init__.py` esporta tutte le classi pubbliche | Import check |
| 12 | Nessuna duplicazione con models/scoring.py (modelli restano lì) | Code review |

### Nice-to-have

- YAML custom profile loading
- Feature store SQLite compaction/vacuum
- Explainability report in Markdown format
- Cross-domain normalization with min-population filter

---

## 16) Rischi e mitigazioni

| Rischio | Impatto | Probabilità | Mitigazione |
|---------|---------|-------------|-------------|
| Pesi dimensione non calibrati | Alto — ranking non significativo | Alta (prima iterazione) | Default sensati + calibrazione in Phase 9 Sprint 0 |
| Derivazione Gate 1+2 → dimensioni inaccurata | Medio — score distorti | Media | Confidence basso per derived scores; Gate 3 sovrascrive sempre |
| Value score estremi (repo 0 stars molto alta) | Basso — ranking distorto | Bassa | Cap value_score a 1.0, normalizzazione batch |
| Feature store SQLite non scalabile | Basso | Bassa | Inizialmente SQLite, evolvibile verso Redis (come pool manager) |
| Cross-domain comparison abusata | Medio — decisioni errate | Media | Warning esplicito + normalized scores |
| Explainability report troppo verboso | Medio — contest waste per MCP | Media | Summary mode di default (≤500 token), full on demand |

---

## 17) Verifica Context7

Verifica Context7 eseguita **prima della stesura del piano** come previsto dalle regole operative.

### 17.1 Pydantic v2 (`/websites/pydantic_dev_validation`, Benchmark: 91.98)

**API verificate:**

| API | Risultato | Impatto su Phase 5 |
|-----|-----------|-------------------|
| `@computed_field` + `@property` | Include campo in `model_dump()` e JSON schema di default | `ScoreResult.value_score` è già computed_field. FeatureStore deve gestire serializzazione correttamente. |
| `model_dump(mode='json')` | Converte enum in stringhe, datetime in ISO format | **Critico per FeatureStore**: `dimension_scores: dict[ScoreDimension, float]` serializza a `{"code_quality": 0.8}` in mode JSON. |
| `model_dump(exclude_computed_fields=True)` | Esclude computed fields | FeatureStore: possiamo escludere `value_score` dalla persistenza (viene ricalcolato). |
| `model_validate(dict)` | Ricostruisce modello da dict | FeatureStore: deserializzazione da JSON column. **Nota**: `dict[ScoreDimension, float]` con chiavi stringa richiede conversione esplicita. |
| `use_enum_values` config | Popola con enum.value invece di enum instance | Non usiamo questa config (StrEnum serializza naturalmente in JSON mode). |
| `exclude=True` su Field | Esclude dalla serializzazione | Utile per campi interni che non devono essere persistiti. |

**Decisione architetturale — FeatureStore serialization:**

```python
# Serializzazione per SQLite JSON column
data = score_result.model_dump(mode='json', exclude={'value_score'})
# value_score è computed_field → viene ricalcolato automaticamente alla deserializzazione

# Deserializzazione da SQLite
raw = json.loads(json_column)
raw['dimension_scores'] = {
    ScoreDimension(k): v for k, v in raw.get('dimension_scores', {}).items()
}
result = ScoreResult.model_validate(raw)
# result.value_score viene ricalcolato dal computed_field
```

### 17.2 aiosqlite (`/omnilib/aiosqlite`, Benchmark: 96)

**Pattern verificati:**

| Pattern | API | Uso in FeatureStore |
|---------|-----|---------------------|
| Connection persistente | `db = await aiosqlite.connect(path)` poi `await db.close()` | FeatureStore mantiene connessione aperta (come `discovery/pool.py`) |
| CREATE TABLE | `await db.execute("CREATE TABLE IF NOT EXISTS ...")` | `initialize()` crea schema |
| INSERT/UPSERT | `await db.execute("INSERT OR REPLACE INTO ...", (params))` | `put()` upsert su PK `(full_name, commit_sha)` |
| SELECT | `async with db.execute("SELECT ...", (params,)) as cursor:` | `get()` con fetchone |
| Batch INSERT | `await db.executemany("INSERT ...", [(params), ...])` | `put_batch()` per multi-insert |
| Transaction | `await db.commit()` / `await db.rollback()` | Ogni write operation followed by commit |
| In-memory | `aiosqlite.connect(":memory:")` | Usato nei test (fixture) |

**Decisione architetturale — coerente con Phase 2 pool.py:**

FeatureStore segue lo stesso pattern di `discovery/pool.py` (già implementato e testato):
- `__init__` riceve `db_path` (default `:memory:` per test)
- `initialize()` crea tabelle
- Metodi async con `await db.execute()` + `await db.commit()`
- `close()` chiude connessione

### 17.3 pydantic-settings (`/pydantic/pydantic-settings`, Benchmark: 86.25)

**Pattern verificati:**

| Pattern | Risultato | Uso in Phase 5 |
|---------|-----------|----------------|
| `BaseSettings` con `env_prefix` | `SettingsConfigDict(env_prefix='GHDISC_SCORING_')` | `ScoringSettings` con env prefix |
| Sub-modelli `BaseModel` (non BaseSettings) | I sub-settings ereditano da `BaseSettings`, i tipi annidati da `BaseModel` | `ScoringSettings` è un `BaseSettings` flat, senza sub-modelli |
| `env_nested_delimiter='__'` | Permette `GHDISC_SCORING__MIN_CONFIDENCE=0.5` | Non necessario: `ScoringSettings` è flat |
| `env_file='.env'` | Carica da .env file | Consistente con altre settings |
| `validate_default=True` | Valida i default values | Utile per `min_confidence`, `hidden_gem_star_threshold` |

**Decisione architetturale — ScoringSettings:**

```python
class ScoringSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GHDISC_SCORING_",
        env_file=".env",
    )
    # Flat fields, no sub-models
    min_confidence: float = Field(default=0.3, ge=0.0, le=1.0)
    hidden_gem_star_threshold: int = Field(default=500)
    ...
```

Da aggiungere a `Settings` in `config.py`:
```python
scoring: ScoringSettings = Field(default_factory=ScoringSettings)
```

### 17.4 PyYAML (`/yaml/pyyaml`, Benchmark: 80.75)

**API verificate per custom_profiles_path (nice-to-have):**

| API | Risultato |
|-----|-----------|
| `yaml.safe_load(stream)` | Parsing sicuro, previene code execution |
| Error handling | `yaml.scanner.ScannerError`, `yaml.parser.ParserError`, `yaml.constructor.ConstructorError` |
| File loading | `with open(path) as f: yaml.safe_load(f)` |

**Decisione**: PyYAML è un nice-to-have per il caricamento di profili custom da YAML. Non incluso come dipendenza in questa fase. Se implementato:
- Usare `yaml.safe_load()` (non `yaml.load()`)
- Gestire `YAMLError` con logging strutturato
- Fallback a profili built-in se YAML non leggibile

### 17.5 Riepilogo dipendenze

| Dipendenza | Stato | Azione Phase 5 |
|------------|-------|-----------------|
| Pydantic v2 | Già in pyproject.toml | Nessuna azione |
| pydantic-settings | Già in pyproject.toml | Aggiungere `ScoringSettings` |
| aiosqlite | Già in pyproject.toml (Phase 2) | Nessuna azione |
| structlog | Già in pyproject.toml | Nessuna azione |
| pyyaml | **Non presente** | Nice-to-have, non aggiunto in questa fase |
| Nuova dipendenza | — | **Nessuna nuova dipendenza** |

### 17.6 Findings azionabili per l'implementazione

1. **FeatureStore serialization**: usare `model_dump(mode='json', exclude={'value_score'})` per persistenza. `value_score` viene ricalcolato dal computed_field alla deserializzazione.

2. **Enum dict key handling**: `dimension_scores` serializzato come `dict[str, float]` in JSON. Alla deserializzazione, convertire chiavi esplicitamente: `{ScoreDimension(k): v for k, v in raw.items()}`.

3. **aiosqlite UPSERT**: usare `INSERT OR REPLACE INTO` per upsert su PK composite `(full_name, commit_sha)`, coerente con pool.py.

4. **ScoringSettings**: flat BaseSettings con `env_prefix='GHDISC_SCORING_'`, aggiungere a `Settings.scoring` field.

---

*Stato documento: Draft v1 — Context7 verification completata, pronto per implementazione*
*Basato su: github-discovery_foundation_blueprint.md + roadmap Phase 5 + wiki scoring dimensions + anti-star bias + Context7 verification*
