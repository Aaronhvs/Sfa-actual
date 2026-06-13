# Scoring v2 — Impact Model

## Contexto de negocio

El sistema de scoring actual mide "quién acumula más estadísticas". El objetivo del rediseño
es medir "quién tuvo más impacto real contra rivales importantes, en torneos importantes,
en momentos importantes, con participación real en los logros del equipo".

Los cambios son aditivos sobre la infraestructura del spec 0012 (scoring versionado ya
implementado): se crea una nueva versión de reglas v2.0, no se borra la v1.x existente.
El sistema de versionado garantiza que los rankings legacy siguen operando sin cambios.

Impacto en el producto: los rankings dejan de favorecer a jugadores que acumulan estadísticas
menores en partidos cómodos y empiezan a reflejar contribución real al rendimiento del equipo
en contextos de alta presión competitiva.

## Restricciones

- No se toca `IngestCompetitionUseCase` ni el flujo de ingesta. Los datos crudos son inmutables.
- Backward-compatible: v1.x sigue activa hasta que el operador decida activar v2.0.
- El spec 0012 ya está implementado: `scoring_rules_versions`, `player_event_scores`,
  `CalculateScoresForRulesVersionUseCase`, `ScoringConfig.from_dict/to_dict` operativos.
- `player_stats.minutes` ya existe en DB y en `PlayerEventRawContextDTO` (accesible vía JOIN).
- Las constraints CHECK en `player_events` (m1, m4, mvisit) deben actualizarse en migración
  para reflejar los nuevos rangos válidos, pero NO bloquean el recálculo bajo la nueva versión
  porque `player_event_scores` tiene sus propios campos sin esas constraints.
- Team Strength requiere datos históricos de temporadas anteriores en `standing_snapshots`.
  Si no existen, se usa el valor de fallback definido en config.
- El bonus competitivo requiere ingreso manual de logros (qué equipo llegó a qué fase).
  No se infiere automáticamente desde la API.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| 5 PositionGroups (DEL, EXT, MF, LAT, DC) — FW y DF desaparecen | Mantener 3 grupos y añadir sub-tablas de puntos | Los grupos actuales ocultan diferencias reales: un lateral y un central tienen roles defensivos opuestos. 5 grupos permite calibración fina sin complejidad excesiva. |
| DiminishingReturnsConfig como value object en `value_objects.py` con método `apply(n, base)` | Lógica inline en el use case | Encapsula invariantes (cap > 0, 0 < extra_factor < 1), es testeable de forma aislada, y puede extenderse a otras acciones sin tocar el use case. |
| `passes_avg_by_position` en ScoringConfig (dict[PositionGroup, int]) | Umbral fijo global | Cada posición tiene un volumen de pases estructuralmente distinto. El umbral posicional evita penalizar a centrales por tener menos pases que un mediocampista. |
| Nueva tabla `team_strengths` (team_id, season, competition_id, strength, source) | Añadir columna strength a `teams` | Un equipo tiene distintos strengths en distintas competiciones (ej: equipo europeo tiene strength diferente en liga vs. Champions). La tabla separada permite historial por temporada y fuente auditable. |
| M1 pasa de posición-en-tabla a strength diferencial: `1.0 + (rival_strength - player_strength) / 100`, clamp [0.6, 1.8] | Mantener fórmula de posición | La posición en tabla es ruidosa (un equipo puede estar 15º con jugadores top). El strength 0-100 con mezcla ponderada prev/actual es más estable y semánticamente correcto. |
| Fallback M1: si team_strength es NULL, usar posición-en-tabla con fórmula legacy | Error hard / skip evento | No rompe datos históricos ni eventos donde no se haya calculado team_strength todavía. |
| `CalculateTeamStrengthsUseCase` separado que corre antes del recálculo de scores | Calcular strength inline en `CalculateScoresForRulesVersionUseCase` | Separar los cálculos hace cada use case testeable de forma independiente y permite recalcular strengths sin re-score y vice versa. |
| Factores de liga en `ScoringConfig.league_strength_factors: dict[str, float]` | Hardcodeados en use case | Los factores de liga son reglas de negocio versionables. Si cambia la percepción de una liga, se crea nueva versión sin tocar código. |
| Mezcla ponderada prev/actual calculada en `CalculateTeamStrengthsUseCase` usando `standing_snapshots` | Scraping externo de ratings | Los datos ya están en DB. No hay dependencia externa para este cálculo. |
| Equipos recién ascendidos sin historial: strengths por defecto en ScoringConfig (`promoted_champion_strength=35`, etc.) | NULL / skip | Un strength de 30 por defecto es neutro (M1 ≈ 1.0 con rival similar), no distorsiona más de lo que distorsionaría ignorar el partido. |
| `PlayerEventRawContextDTO` añade `player_team_strength: float | None` y `rival_team_strength: float | None` | Nuevo DTO separado | El DTO existente ya encapsula todo el contexto raw necesario para re-score. Añadir dos campos float es mínimamente invasivo. |
| Umbral de minutos para STATS event: si `minutes < 15` aplicar factor de penalización (0.50) al base_total | Excluir el evento completamente | Excluir el evento distorsionaría el recuento de `matches_played`. Una penalización preserva el registro pero reduce el impacto de entradas testimoniales. |
| Acciones decisivas (GOAL, ASSIST, GOAL_PENALTY, GOAL_SHOOTOUT, CORNER_ASSIST, PENALTY_WON, YELLOW_CARD, RED_CARD) exentas de umbral de minutos | Aplicar umbral a todo | Un gol a los 89' en sustitución es tan real como uno al 10'. Las acciones discretas no son función del tiempo de juego. |
| `minutes_threshold_stats`, `minutes_penalty_factor`, `ranking_min_minutes_global`, `ranking_min_minutes_competition` almacenados en ScoringConfig | Constantes en el use case | Son parámetros de reglas de negocio, deben ser versionables junto con el resto de la config. |
| `ScoringConfig.mrating_none_value` sube de 0.5 a 0.75 | Mantener penalización por dato ausente | El dato de rating de API-Football no siempre se ingesta para todos los partidos. 0.5 penalizaba injustamente partidos con datos incompletos. 0.75 es neutral-ligeramente-negativo. |
| Nueva tabla `competition_achievements` para registrar qué equipo llegó a qué fase | Inferir desde `competition_stages` | Las fases de competición en DB son configuración de scoring (stage_factor), no registros de resultados deportivos. Son conceptos distintos. |
| Nueva tabla `player_achievement_bonuses` para el bonus calculado por jugador/fase | Columna JSONB en sfa_season_scores | La tabla separada permite auditoría, recálculo independiente, y queries eficientes por fase/competición. |
| `sfa_season_scores` añade `achievement_bonus_pts NUMERIC(12,2) DEFAULT 0` y `sfa_total_pts GENERATED ALWAYS AS (total_pts + achievement_bonus_pts) STORED` | Calcular sfa_total en la query | La columna GENERATED garantiza consistencia absoluta sin lógica en la capa de aplicación. Cualquier UPDATE a `achievement_bonus_pts` o `total_pts` actualiza `sfa_total_pts` automáticamente. |
| `CalculateAchievementBonusesUseCase` corre independientemente de `CalculateScoresForRulesVersionUseCase` | Bonus calculado dentro del mismo use case | El bonus requiere datos que pueden no estar listos cuando se recalculan los scores (un equipo puede avanzar de fase después de la última jornada). La independencia permite disparar cada use case cuando corresponde. |
| Bonus fase y pesos de competición en `ScoringConfig.achievement_phase_bonuses` y `competition_bonus_weights` | Tabla de configuración separada en DB | Los bonus son parte de las reglas de scoring. Deben versionarse junto con los base_points y multiplicadores. |
| `M4ShotDifficulty` clamp baja de [1.0, 1.8] a [1.0, 1.5] | Mantener clamp original | PSxG raramente llega a valores tan bajos que justifiquen M4 > 1.5. El clamp anterior inflaba artificialmente goles difíciles. |
| `MvisitFactor` baja de 1.3 a 1.15 | Mantener 1.3 | El factor visitante de 1.3 estaba sobreinflado. Los datos de home advantage moderno muestran una ventaja más modesta. |
| DB constraints CHECK en `player_events` (m1, m4, mvisit) se actualizan en migración | No actualizar | Los constraints históricos rechazan valores válidos bajo v2.0 si se reingestan partidos. La migración los alinea con el nuevo rango. |

## Domain Model

### Value objects nuevos / modificados

**PositionGroup (modificado)**
Ubicación: `domain/scoring/value_objects.py`

```python
class PositionGroup(str, Enum):
    DEL = "DEL"   # Delantero centro
    EXT = "EXT"   # Extremo
    MF  = "MF"    # Mediocampista central
    LAT = "LAT"   # Lateral
    DC  = "DC"    # Defensa central
```

`position_to_group()` actualizado: DEL→DEL, EXT→EXT, MC→MF, LAT→LAT, DC→DC. GK sigue lanzando ValueError.
FW y DF eliminados. Backward-compat: `ScoringConfig.from_dict` leerá "DEL"/"EXT"/"LAT"/"DC" del JSONB v2.

**DiminishingReturnsConfig (nuevo)**
Ubicación: `domain/scoring/value_objects.py`

```python
@dataclass(frozen=True)
class DiminishingReturnsConfig:
    cap: int          # número de unidades a base_pts completo; cap > 0
    extra_factor: float  # factor para unidades > cap; 0 < extra_factor < 1
```

Invariantes validadas en `__post_init__`: `cap > 0`, `0 < extra_factor < 1`.

Método estático:
```python
@staticmethod
def apply(n: float, base_pts_per_unit: float, cfg: DiminishingReturnsConfig) -> float:
    full  = min(n, cfg.cap) * base_pts_per_unit
    extra = max(0.0, n - cfg.cap) * base_pts_per_unit * cfg.extra_factor
    return full + extra
```

**TeamStrengthBlend (nuevo)**
Ubicación: `domain/scoring/value_objects.py`

```python
@dataclass(frozen=True)
class TeamStrengthBlend:
    """Calcula el strength efectivo de un equipo en un partido dado su matchday."""
    value: float  # strength efectivo [0, 100]

    def __init__(
        self,
        prev_season_strength: float | None,
        current_season_strength: float | None,
        matchday: int | None,
        fallback_strength: float = 30.0,
    ) -> None: ...
```

Invariantes: `value` siempre en [0.0, 100.0]. Si ambas temporadas son None → usa fallback.
Mezcla ponderada según matchday:
- 1–5:   80% prev + 20% current
- 6–10:  60% prev + 40% current
- 11–15: 40% prev + 60% current
- 16+:   20% prev + 80% current
- Si matchday is None: 50/50

Si prev_season_strength is None y current_season_strength is not None → 100% current.
Si current_season_strength is None y prev_season_strength is not None → 100% prev.

**M1RivalDifficulty (modificado)**
Nueva fórmula cuando se usan strengths:
```
M1 = 1.0 + (rival_strength - player_team_strength) / 100
clamp [0.6, 1.8]
```
Fallback a fórmula legacy (posición en tabla) cuando team_strength es None.

Constructor actualizado:
```python
def __init__(
    self,
    player_team_strength: float | None = None,
    rival_team_strength: float | None = None,
    # legacy fallback:
    player_team_pos: int | None = None,
    rival_team_pos: int | None = None,
    config: ScoringConfig | None = None,
) -> None
```

**ScoringConfig (extendido)**
Campos nuevos a añadir en `from_dict`/`to_dict`/`__post_init__`:

```python
# Nuevos campos v2.0
diminishing_returns: dict[ActionType, DiminishingReturnsConfig]
passes_avg_by_position: dict[PositionGroup, int]
minutes_threshold_stats: int          # default 15
minutes_penalty_factor: float         # default 0.50
ranking_min_minutes_global: int       # default 600
ranking_min_minutes_competition: int  # default 180
m1_strength_divisor: float            # default 100.0
league_strength_factors: dict[str, float]   # competition name → factor
promoted_champion_strength: float     # default 35.0
promoted_runner_up_strength: float    # default 30.0
promoted_playoff_strength: float      # default 25.0
promoted_default_strength: float      # default 30.0
cup_lower_div_strengths: dict[str, float]   # "segunda"→35.0, "tercera"→18.0, "amateur"→10.0
achievement_phase_bonuses: dict[str, dict[str, int]]  # competition_key → phase → bonus_pts
competition_bonus_weights: dict[str, float]           # competition name → weight
```

Invariantes adicionales en `__post_init__`:
- `minutes_threshold_stats >= 0`
- `0 < minutes_penalty_factor <= 1`
- `ranking_min_minutes_global >= 0`
- `ranking_min_minutes_competition >= 0`
- `m1_strength_divisor > 0`

### Entidades de dominio nuevas

**CompetitionAchievement (nueva entidad)**
Ubicación: `domain/scoring/entities.py`

```python
@dataclass(frozen=True)
class CompetitionAchievement:
    id: int | None
    competition_id: int
    team_id: int
    season: str
    phase: str          # "winner", "runner_up", "sf", "qf", "r16", "classify_ko"
    bonus_points: int   # bonus base para esa fase (de config)
    weight: float       # peso de la competición (de config)
    created_at: datetime | None
```

Invariante: `bonus_points >= 0`, `0 < weight <= 1.0`.

**PlayerAchievementBonus (nuevo DTO)**
Ubicación: `domain/scoring/entities.py`

```python
@dataclass(frozen=True)
class PlayerAchievementBonus:
    id: int | None
    player_id: int
    competition_id: int
    team_id: int
    season: str
    phase: str
    participation_ratio: float   # min(1.0, jugador_mins / equipo_total_mins)
    base_bonus: int
    weight: float
    final_bonus: float           # base_bonus × weight × participation_ratio
    rules_version_id: int
    created_at: datetime | None
```

Invariante: `0 <= participation_ratio <= 1.0`, `final_bonus >= 0`.

### Ubicación propuesta en domain/

```
domain/scoring/
├── value_objects.py   ← modificar: PositionGroup(5), DiminishingReturnsConfig(nuevo),
│                         TeamStrengthBlend(nuevo), M1RivalDifficulty(modificado),
│                         ScoringConfig(extendido)
├── entities.py        ← modificar: CompetitionAchievement(nueva),
│                         PlayerAchievementBonus(nuevo)
└── services.py        ← sin cambios estructurales (lógica pasa a use case)

domain/
├── scoring_ports.py   ← añadir: TeamStrengthRepositoryPort,
│                         CompetitionAchievementRepositoryPort,
│                         PlayerEventRawContextDTO (+ 3 campos nuevos)
└── ingestion_ports.py ← sin cambios
```

## Integraciones externas

Ninguna nueva. El cálculo de team_strength usa exclusivamente `standing_snapshots` ya en DB.
El registro de logros competitivos es manual (operador llama al endpoint).

---

## Decisiones de implementación detalladas

### D1: Migración SQL (0013_scoring_v2_impact_model.sql)

```sql
-- 1. Actualizar constraints históricas en player_events
ALTER TABLE player_events DROP CONSTRAINT ck_event_m1;
ALTER TABLE player_events ADD CONSTRAINT ck_event_m1 CHECK (m1 BETWEEN 0.6 AND 1.8);

ALTER TABLE player_events DROP CONSTRAINT ck_event_m4;
ALTER TABLE player_events ADD CONSTRAINT ck_event_m4 CHECK (m4 BETWEEN 1.0 AND 1.5);

ALTER TABLE player_events DROP CONSTRAINT ck_event_mvisit;
ALTER TABLE player_events ADD CONSTRAINT ck_event_mvisit CHECK (mvisit IN (1.0, 1.15));

-- 2. Nueva tabla team_strengths
CREATE TABLE team_strengths (
    id             SERIAL PRIMARY KEY,
    team_id        INTEGER NOT NULL REFERENCES teams(id),
    season         VARCHAR(10) NOT NULL,
    competition_id INTEGER NOT NULL REFERENCES competitions(id),
    strength       NUMERIC(5,2) NOT NULL CHECK (strength BETWEEN 0 AND 100),
    source         VARCHAR(20) NOT NULL DEFAULT 'calculated'
                   CHECK (source IN ('calculated', 'default', 'override')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (team_id, season, competition_id)
);
CREATE INDEX ix_ts_competition_season ON team_strengths(competition_id, season);

-- 3. Nueva tabla competition_achievements
CREATE TABLE competition_achievements (
    id             SERIAL PRIMARY KEY,
    competition_id INTEGER NOT NULL REFERENCES competitions(id),
    team_id        INTEGER NOT NULL REFERENCES teams(id),
    season         VARCHAR(10) NOT NULL,
    phase          VARCHAR(30) NOT NULL,
    bonus_points   INTEGER NOT NULL CHECK (bonus_points >= 0),
    weight         NUMERIC(4,2) NOT NULL CHECK (weight > 0 AND weight <= 1),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (competition_id, team_id, season, phase)
);

-- 4. Nueva tabla player_achievement_bonuses
CREATE TABLE player_achievement_bonuses (
    id                  SERIAL PRIMARY KEY,
    player_id           INTEGER NOT NULL REFERENCES players(id),
    competition_id      INTEGER NOT NULL REFERENCES competitions(id),
    team_id             INTEGER NOT NULL REFERENCES teams(id),
    season              VARCHAR(10) NOT NULL,
    phase               VARCHAR(30) NOT NULL,
    participation_ratio NUMERIC(5,4) NOT NULL CHECK (participation_ratio BETWEEN 0 AND 1),
    base_bonus          INTEGER NOT NULL,
    weight              NUMERIC(4,2) NOT NULL,
    final_bonus         NUMERIC(10,2) NOT NULL,
    rules_version_id    INTEGER NOT NULL REFERENCES scoring_rules_versions(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (player_id, competition_id, season, phase, rules_version_id)
);
CREATE INDEX ix_pab_player_season ON player_achievement_bonuses(player_id, season, rules_version_id);

-- 5. Extender sfa_season_scores
ALTER TABLE sfa_season_scores
    ADD COLUMN achievement_bonus_pts NUMERIC(12,2) NOT NULL DEFAULT 0;

ALTER TABLE sfa_season_scores
    ADD COLUMN sfa_total_pts NUMERIC(12,2)
    GENERATED ALWAYS AS (total_pts + achievement_bonus_pts) STORED;
```

### D2: PlayerEventRawContextDTO — 3 campos nuevos

```python
# Añadir a scoring_ports.py
player_team_strength: float | None   # de team_strengths, None si no calculado
rival_team_strength: float | None    # de team_strengths, None si no calculado
minutes: int | None                  # de player_stats.minutes
```

`get_events_for_recalc` actualiza su JOIN para incluir `team_strengths` via LEFT JOIN
usando `fixture.home_team_id` / `fixture.away_team_id` + `fixture.season` + `fixture.competition_id`.

### D3: BASE_POINTS_TABLE_V2

Nueva constante en `services.py` con los 5 grupos. La constante v1 `BASE_POINTS_TABLE`
permanece para backward-compat. `ScoringConfig.default()` sigue usando v1.
`ScoringConfig.default_v2()` construye desde `BASE_POINTS_TABLE_V2` con todos los parámetros v2.

### D4: CalculateTeamStrengthsUseCase

```
execute(season, competition_id, matchday) -> CalculateTeamStrengthsResult
```

Flujo:
1. Leer equipos de la competición para el season dado.
2. Para cada equipo: leer strength actual (avg posición temporada actual ponderada por puntos)
   y strength temporada anterior desde `standing_snapshots`.
3. Para competiciones europeas: aplicar `league_strength_factors` al strength doméstico.
4. Calcular `TeamStrengthBlend` según matchday.
5. Guardar en `team_strengths` con `source="calculated"`.

Nota: cuando no hay datos de posición en tabla (fase de grupos europea o copa) → usar strength
doméstico del equipo en su liga nacional si existe, si no → promoted_default_strength.

### D5: _score_stats_event actualizado en CalculateScoresForRulesVersionUseCase

Cambios respecto a v1:
1. Leer `event.minutes`. Si `minutes < config.minutes_threshold_stats` y `minutes is not None`:
   aplicar `config.minutes_penalty_factor` al `base_total` antes de multiplicar por `combined`.
2. Para PASSES_COMPLETED: restar `config.passes_avg_by_position[group]` antes de calcular pts.
3. Para acciones con diminishing_returns: usar `DiminishingReturnsConfig.apply()` en lugar de `n × base`.
4. M1 construido con `M1RivalDifficulty(player_team_strength=..., rival_team_strength=..., fallback_pos=...)`.

### D6: CalculateAchievementBonusesUseCase

```
execute(season, competition_id, rules_version_id) -> CalculateAchievementBonusesResult
```

Flujo:
1. Leer todos los `competition_achievements` para (season, competition_id).
2. Para cada achievement: leer minutos totales del equipo en la competición
   (SUM de player_stats.minutes del equipo en fixtures de esa competición/temporada).
3. Para cada jugador del equipo: calcular `participation_ratio =
   min(1.0, jugador_total_mins / equipo_total_mins)`.
4. `final_bonus = achievement.bonus_points × achievement.weight × participation_ratio`.
5. Upsert en `player_achievement_bonuses`.
6. UPDATE `sfa_season_scores.achievement_bonus_pts = SUM(final_bonus)` donde
   `player_id = jugador AND competition_id = X AND season = Y AND rules_version_id = Z`.

### D7: RegisterCompetitionAchievementUseCase

```
execute(competition_id, team_id, season, phase, rules_version_id) -> RegisterAchievementResult
```

Flujo:
1. Validar que `phase` es una clave válida en `config.achievement_phase_bonuses`.
2. Leer `bonus_points` de `config.achievement_phase_bonuses[competition_key][phase]`.
3. Leer `weight` de `config.competition_bonus_weights[competition_name]`.
4. Upsert en `competition_achievements`.
5. Disparar `CalculateAchievementBonusesUseCase` para recalcular bonuses afectados.

`competition_key` se deriva del nombre de la competición (ej: "UEFA Champions League" → "champions").

### D8: Ranking con sfa_total_pts

Los endpoints de ranking existentes que usan `total_pts` deben añadir soporte opcional
para ordenar por `sfa_total_pts` cuando hay una `rules_version_id` activa.
`GetRankingUseCase` acepta nuevo parámetro `use_total: bool = False`.
