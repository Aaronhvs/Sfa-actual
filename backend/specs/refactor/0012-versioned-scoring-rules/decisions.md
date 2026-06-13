# Versioned Scoring Rules & Raw-Event Recalculation

## Contexto de negocio

El sistema de scoring calcula puntos por cada acción de un jugador usando multiplicadores de
contexto (M1–M4, Mvisit, Mrating). Las reglas están hardcodeadas en `BASE_POINTS_TABLE` y en
los value objects de `domain/scoring/`. Si cualquier regla cambia (base points, clamps,
thresholds de Mrating, lógica de multiplicadores), actualmente no hay forma de recalcular una
temporada completa sin volver a correr la ingesta completa desde la API o borrar la DB.

El objetivo es separar los **hechos crudos** (qué ocurrió en el partido) del **cálculo de
puntos** (qué vale ese hecho según las reglas vigentes), de modo que cambiar una regla equivalga
a ejecutar un comando de recálculo, no a re-ingestar datos.

Impacto en el producto: permite iterar las reglas de scoring con seguridad, comparar rankings
entre versiones de reglas, y auditar cualquier cálculo con trazabilidad completa
(`calculation_details`).

## Restricciones

- No se modifica `IngestCompetitionUseCase` ni el flujo de ingesta. Sigue grabando en
  `player_events` y `player_stats` exactamente igual que hoy.
- Backward-compatible: los rankings actuales (scores legacy con `rules_version_id = NULL`)
  siguen funcionando sin ningún cambio en los endpoints existentes.
- No se borran ni migran datos existentes de `player_events`.
- Las nuevas tablas siguen arquitectura hexagonal estricta: modelos SQLAlchemy en
  `infrastructure/models/`, Protocols en `domain/`, repositorios en
  `infrastructure/repositories/`.
- El `config_json` de `ScoringRulesVersion` debe ser suficiente para reproducir cualquier
  cálculo sin leer código fuente.
- Team Strength queda fuera de esta iteración (requiere datos externos adicionales no
  disponibles). El campo se reserva en el schema con valor fijo 1.0.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Arquitectura completa (nueva tabla `player_event_scores` + `scoring_rules_versions`) | MVP: agregar solo `rules_version` a `player_events` y `force_recalculate` | El MVP no permite comparar rankings entre versiones simultáneamente, que es requisito explícito. La arquitectura completa no es más compleja dado que los datos crudos ya existen en `player_stats`. |
| `player_event_scores` como tabla separada de `player_events` | Agregar columnas de resultado a `player_events` | Un mismo evento debe poder tener cálculos distintos según versión de reglas. Colapsar impide comparar versiones. |
| `rules_version_id = NULL` en `sfa_season_scores` para scores legacy | Migrar datos existentes a una versión "v0-legacy" | No migrar es más seguro: cero riesgo de corrupción de datos existentes; los endpoints legacy siguen funcionando sin tocarlos. |
| No duplicar conteos de stats en `player_events` | Guardar action values en `player_events` | Los conteos crudos ya existen en `player_stats`. Duplicarlos viola DRY y crea riesgo de divergencia. Solo se agregan los 3 campos de contexto de partido que son irrecuperables: `player_team_pos`, `rival_team_pos`, `is_away`. |
| `ScoringConfig` como value object que reemplaza `BASE_POINTS_TABLE` hardcodeado | Leer config desde archivo externo (YAML/JSON) | El value object es tipado, validable, testeable y serializable a JSONB. No hay dependencia de sistema de archivos. `BASE_POINTS_TABLE` queda como constante pública para backward-compat. |
| `SFAScoringService` acepta `ScoringConfig` opcional en constructor | Nuevo servicio separado para recálculo versionado | Reusar el servicio existente evita duplicación de lógica de scoring. `SFAScoringService()` sin argumentos sigue funcionando (usa `ScoringConfig.default()`). |
| PostgreSQL NULL en `rules_version_id` trata cada fila como única para el índice legacy | Partial unique index `WHERE rules_version_id IS NULL` | PostgreSQL trata NULLs como distintos en UNIQUE constraints, lo que permitiría múltiples filas legacy para el mismo jugador. El partial index garantiza exactamente una fila legacy por `(player_id, competition_id, season)`. |

## Domain Model

### Nuevo value object: `ScoringConfig`

Ubicación: `domain/scoring/value_objects.py`

```python
@dataclass(frozen=True)
class ScoringConfig:
    base_points: dict[PositionGroup, dict[ActionType, int]]
    m1_clamp: tuple[float, float]                          # default (0.5, 2.0)
    m1_divisor: float                                      # default 20.0
    m3_table: dict                                         # lookup minute/score_diff → factor
    m4_formula: dict                                       # psxg_multiplier + clamp
    mvisit_bonus: float                                    # default 1.3
    mvisit_eligible_actions: set[ActionType]
    mrating_thresholds: list[tuple[float, float]]          # [(7.0, 0.3), (8.0, 0.5), ...]
    combined_clamp: tuple[float, float]                    # default (0.3, 4.0)
```

Invariantes (validadas en constructor vía `__post_init__` o factory):
- `m1_clamp[0] < m1_clamp[1]`, ambos positivos
- `m1_divisor > 0`
- `mvisit_bonus >= 1.0`
- `mrating_thresholds` en orden creciente de threshold
- `combined_clamp[0] < combined_clamp[1]`, ambos positivos
- `base_points` no vacío

Factories:
- `ScoringConfig.default() -> ScoringConfig` — construye desde los valores hardcodeados actuales
- `ScoringConfig.from_dict(d: dict) -> ScoringConfig` — deserializa desde `config_json`
- `ScoringConfig.to_dict() -> dict` — serializa a `config_json`

### Nueva entidad: `ScoringRulesVersion`

Ubicación: `domain/scoring/entities.py`

```python
@dataclass(frozen=True)
class ScoringRulesVersion:
    id: int
    name: str           # e.g. "v1.0-initial", "v2.0-mrating-tuned"
    version: str        # semver string
    description: str
    is_active: bool
    config: ScoringConfig
    created_at: datetime
```

Invariante de negocio: no puede haber dos versiones activas simultáneamente.
La entidad es inmutable (frozen); la activación es responsabilidad del use case + repositorio.

### Nuevo DTO: `PlayerEventScore`

Ubicación: `domain/scoring/entities.py`

```python
@dataclass(frozen=True)
class PlayerEventScore:
    id: int | None          # None si es nuevo, int si ya persiste
    event_id: int
    player_id: int
    fixture_id: int
    season: str
    competition_id: int
    rules_version_id: int
    action_type: str
    position: str
    base_points: float
    m1: float
    m2: float
    m3: float
    m4: float
    mvisit: float
    mrating: float
    combined_before_clamp: float
    combined_after_clamp: float
    final_points: float
    calculation_details: dict   # JSON de trazabilidad para debug
    created_at: datetime | None
```

### Ubicación propuesta en domain/

```
domain/scoring/
├── value_objects.py   ← agregar ScoringConfig
├── entities.py        ← agregar ScoringRulesVersion, PlayerEventScore
└── services.py        ← modificar SFAScoringService (acepta ScoringConfig opcional)

domain/
└── scoring_ports.py   ← nuevo archivo: ScoringRulesVersionRepositoryPort,
                          PlayerEventScoreRepositoryPort, PlayerEventRawContextDTO
```

## Integraciones externas

Ninguna nueva. El recálculo lee exclusivamente desde la DB (tablas existentes
`player_events`, `player_stats`, `fixtures`, `competition_stages`, `standings`).
No se realizan llamadas a APIs externas durante el recálculo.

---

## Decisiones de implementación detalladas

### D1: Nuevos campos en `player_events`

Tres columnas nuevas, nullable (no rompen datos existentes):
- `player_team_pos` (SmallInteger nullable) — posición del equipo del jugador en tabla
- `rival_team_pos` (SmallInteger nullable) — posición del equipo rival en tabla
- `is_away` (Boolean nullable) — si el jugador juega como visitante

El ingester (`IngestCompetitionUseCase`) los empieza a llenar a partir de este refactor.
Para eventos históricos (NULL), el recálculo usa fallback: leer standings más recientes
de `standings_snapshots`.

### D2: Nueva tabla `scoring_rules_versions`

```sql
CREATE TABLE scoring_rules_versions (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    version     VARCHAR(20) NOT NULL,
    description TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT FALSE,
    config_json JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Garantiza máximo una versión activa:
CREATE UNIQUE INDEX uq_scoring_rules_active ON scoring_rules_versions (is_active)
    WHERE is_active = TRUE;
```

### D3: Nueva tabla `player_event_scores`

```sql
CREATE TABLE player_event_scores (
    id                      SERIAL PRIMARY KEY,
    event_id                INTEGER NOT NULL REFERENCES player_events(id) ON DELETE CASCADE,
    player_id               INTEGER NOT NULL REFERENCES players(id),
    fixture_id              INTEGER NOT NULL REFERENCES fixtures(id),
    season                  VARCHAR(10) NOT NULL,
    competition_id          INTEGER NOT NULL REFERENCES competitions(id),
    rules_version_id        INTEGER NOT NULL REFERENCES scoring_rules_versions(id),
    action_type             VARCHAR(50) NOT NULL,
    position                VARCHAR(10) NOT NULL,
    base_points             NUMERIC(10,2) NOT NULL,
    m1                      NUMERIC(5,3) NOT NULL,
    m2                      NUMERIC(5,3) NOT NULL,
    m3                      NUMERIC(5,3) NOT NULL,
    m4                      NUMERIC(5,3) NOT NULL,
    mvisit                  NUMERIC(3,2) NOT NULL DEFAULT 1.0,
    mrating                 NUMERIC(3,2) NOT NULL DEFAULT 1.0,
    combined_before_clamp   NUMERIC(8,4) NOT NULL,
    combined_after_clamp    NUMERIC(8,4) NOT NULL,
    final_points            NUMERIC(10,2) NOT NULL,
    calculation_details     JSONB,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (event_id, rules_version_id)
);
CREATE INDEX ix_pes_player_season ON player_event_scores(player_id, season, rules_version_id);
CREATE INDEX ix_pes_competition   ON player_event_scores(competition_id, season, rules_version_id);
```

### D4: Modificar `sfa_season_scores`

```sql
ALTER TABLE sfa_season_scores
    ADD COLUMN rules_version_id INTEGER REFERENCES scoring_rules_versions(id);

ALTER TABLE sfa_season_scores DROP CONSTRAINT uq_sfa_season_score;

-- Para scores versionados (rules_version_id NOT NULL):
CREATE UNIQUE INDEX uq_sfa_season_score_versioned
    ON sfa_season_scores (player_id, competition_id, season, rules_version_id)
    WHERE rules_version_id IS NOT NULL;

-- Para scores legacy (rules_version_id IS NULL):
CREATE UNIQUE INDEX uq_sfa_season_score_legacy
    ON sfa_season_scores (player_id, competition_id, season)
    WHERE rules_version_id IS NULL;
```

### D5: `ScoringConfig` reemplaza `BASE_POINTS_TABLE` en `SFAScoringService`

- `SFAScoringService.__init__(self, config: ScoringConfig | None = None)`
- Si `config is None` → `self._config = ScoringConfig.default()`
- Los métodos `score_event()` y `score_match_stats()` leen de `self._config.base_points`
  en lugar de `BASE_POINTS_TABLE`
- `BASE_POINTS_TABLE` permanece en el módulo como constante pública para backward-compat

### D6: `CalculateScoresForRulesVersionUseCase`

Parámetros: `rules_version_id`, `season`, `competition_id?`, `match_id?`, `player_id?`,
`force_recalculate: bool = False`

Flujo:
1. Cargar `ScoringRulesVersion` por `rules_version_id` → construir `ScoringConfig`
2. Construir `SFAScoringService(config)` con esa config
3. Cargar todos los `PlayerEvent` en el scope con su contexto raw (JOIN con `player_stats`,
   `fixtures`, `competition_stages`, `standings_snapshots` para fallback de posiciones)
4. Para cada evento:
   a. Si no `force_recalculate` y ya existe fila en `player_event_scores` para
      `(event_id, rules_version_id)` → skip
   b. Para evento GOAL/ASSIST/GOAL_PENALTY/GOAL_SHOOTOUT/CORNER_ASSIST:
      recalcular con `score_event()` usando `score_diff`, `minute`, `psxg`, `is_away`
   c. Para evento STATS: leer conteos desde `player_stats`, recalcular con
      `score_match_stats()` incluyendo `rating` para Mrating
   d. Guardar en `player_event_scores` con `calculation_details` completo:
      `{"action": "GOAL", "position": "FW", "base": 500, "M1": 1.55, ...}`
5. Para cada jugador afectado: reconstruir fila en `sfa_season_scores` con
   `rules_version_id` sumando desde `player_event_scores`

### D7–D9: API, Celery, Rankings

- `POST /api/v1/scoring/recalculate` — lanza Celery task, devuelve `task_id`
- `GET/POST/PATCH /api/v1/scoring/rules-versions` — gestión de versiones
- `GET /api/v1/ranking?rules_version_id=N` — ranking de versión específica
  (sin param → devuelve legacy, backward-compatible)
