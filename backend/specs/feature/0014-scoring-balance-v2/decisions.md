# Scoring Balance v2 — Decisiones arquitectónicas

## Contexto de negocio

El ranking SFA v2 con midfield bonuses (spec 0013) produjo un resultado no deseado: Bruno
Fernandes subió de #14 a #3 por acumulación de CREATIVE_CONTROL_BONUS partido a partido. El
problema tiene tres causas:

1. Los valores de los bonuses MC (120/100/100) son demasiado altos y el cap (220) también.
2. Las acciones acumulativas de MF en BASE_POINTS_TABLE_V2 (XA_NO_ASSIST, FOULS_DRAWN,
   DUELS_WON, TACKLES, INTERCEPTIONS) tienen valores que, multiplicados por volumen de
   partidos, generan scores inflados respecto a posiciones menos acumulativas.
3. Los achievement bonuses actuales no diferencian entre jugadores titulares clave y
   suplentes marginales, ni entre rendimiento alto y bajo.

Este spec ajusta los tres vectores sin cambios de schema ni nuevos endpoints.

---

## Restricciones

- No hay cambios de schema de DB (cero migraciones).
- No se crean nuevas entidades de dominio ni nuevos `ActionType`.
- Toda lógica nueva vive en use cases y value objects existentes.
- Los cambios a constantes y `_DEFAULT_*` dicts solo afectan a `ScoringConfig.default_v2()`
  y versiones creadas a partir de ella. Las versiones ya guardadas en DB (config_json JSONB)
  NO se modifican automáticamente — la recalibración requiere crear una versión v3 nueva via
  el flujo existente de `CreateScoringRulesVersionUseCase`.
- `from_dict` / `to_dict` deben soportar los nuevos campos con defaults retrocompatibles.

---

## Ajuste 1: Midfield bonuses — nuevos valores y competition_weight

### Nuevos valores de constantes en `calculate_scores_for_rules_version.py`

| Constante | Valor actual | Valor nuevo |
|---|---|---|
| `_MC_BONUS_CONTROL` | 120 | **140** |
| `_MC_BONUS_TWO_WAY` | 100 | **90** |
| `_MC_BONUS_CREATIVE` | 100 | **70** |

Cap en `ScoringConfig.midfield_control_bonus_cap_per_match`:
- `default_v2()`: 220 → **180**
- `from_dict()` default fallback: 220 → **180**

### Nuevas condiciones para CREATIVE_CONTROL_BONUS

| Condicion | Valor actual | Valor nuevo |
|---|---|---|
| `_MC_CREATIVE_MIN_RATING` | 7.5 | **7.7** |
| `_MC_CREATIVE_MIN_PASSES` | 50 | **55** |
| Nueva condicion | — | `passes_accuracy >= 85.0` |

Nueva constante: `_MC_CREATIVE_MIN_PASSES_ACCURACY = 85.0`

La condicion `creative_earned` en `_apply_midfield_bonuses` pasa a ser:
```python
creative_earned = (
    rating is not None
    and rating >= _MC_CREATIVE_MIN_RATING
    and passes_completed >= _MC_CREATIVE_MIN_PASSES
    and passes_accuracy >= _MC_CREATIVE_MIN_PASSES_ACCURACY
    and passes_key >= _MC_CREATIVE_MIN_PASSES_KEY
)
```

### Nueva formula con competition_weight

Formula actual:
```
mc_bonus_final = mc_bonus_total_base * M2 * Mrating
```

Formula nueva (spec 0014):
```
mc_bonus_final = mc_bonus_total_base * M2 * Mrating * competition_weight
```

### Decision: como resolver competition_id -> competition_name sin query de DB

**Problema:** `_apply_midfield_bonuses` recibe `event.competition_id` (int), pero
`config.competition_bonus_weights` esta indexado por nombre de competicion (string). No
existe un mapping id→nombre en el dominio.

**Alternativas analizadas:**

| Alternativa | Descripcion | Problema |
|---|---|---|
| A | Query DB dentro de `_apply_midfield_bonuses` | Viola arquitectura hexagonal: el dominio/use case no accede directamente a DB. |
| B | Pasar `competition_name: str` como parametro extra a `_apply_midfield_bonuses` | El llamador `_score_stats_event` tampoco tiene el nombre — tendria que venir de arriba. |
| C | Pasar `competition_name` como campo de `PlayerEventRawContextDTO` | Requiere cambiar el DTO + la query del repositorio. |
| D | Resolver `competition_weight` en `_score_stats_event` antes de llamar al metodo, pasandolo como `float` | El use case tiene `event.competition_id` y puede resolver el peso via un dict `id→weight` precargado en `execute()`. Cero impacto en el dominio. |

**Decision: opcion D — precargar `competition_id_to_weight: dict[int, float]` en `execute()`.**

El use case `CalculateScoresForRulesVersionUseCase` ya recibe `scoring_repo` (que puede hacer
queries). Se añade al `CompetitionAchievementRepositoryPort` (o mejor: al port ya existente
`ScoringRulesVersionRepositoryPort`) un nuevo metodo:

```
get_competition_name_map() -> dict[int, str]
```

Implementado en `CompetitionAchievementRepository` (ya tiene acceso a la sesion). En `execute()`
se llama una sola vez: `name_map = await repo.get_competition_name_map()`, luego se pasa a
`_score_stats_event` que deriva `competition_weight = config.competition_bonus_weights.get(name_map.get(event.competition_id, ""), 1.0)`.

**Justificacion:** Una sola query O(1) al inicio de `execute()` evita N queries individuales
(una por evento). El dict resultante se pasa por valor a `_score_stats_event` y luego a
`_apply_midfield_bonuses`. No contamina el dominio ni rompe la arquitectura hexagonal.

**Donde vive el metodo:** En `CompetitionAchievementRepositoryPort` (scoring_ports.py), porque
`CalculateScoresForRulesVersionUseCase` ya inyecta `PlayerEventScoreRepositoryPort` y
`ScoringRulesVersionRepositoryPort`, pero NO `CompetitionAchievementRepositoryPort`. Para evitar
añadir una dependencia nueva al use case, el metodo `get_competition_name_map` se añade al
`PlayerEventScoreRepositoryPort` — que ya es una dependencia existente del use case.

Implementacion en `PlayerEventScoreRepository`:
```python
async def get_competition_name_map(self) -> dict[int, str]:
    stmt = select(Competition.id, Competition.name)
    rows = await self._session.execute(stmt)
    return {row.id: row.name for row in rows.all()}
```

**Firma actualizada de `_apply_midfield_bonuses`:**
```python
def _apply_midfield_bonuses(
    self,
    event: PlayerEventRawContextDTO,
    group: PositionGroup,
    m2: M2CompetitionStage,
    mrating: MratingFactor,
    config: ScoringConfig,
    competition_weight: float,   # nuevo parametro
) -> tuple[float, dict]:
    ...
    mc_bonus_final = mc_bonus_total_base * m2.value * mrating.value * competition_weight
```

**Firma actualizada de `_score_stats_event`:**
```python
def _score_stats_event(
    self,
    event,
    service,
    group,
    position,
    rules_version_id,
    competition_name_map: dict[int, str],   # nuevo parametro
) -> PlayerEventScore | None:
    ...
    comp_name = competition_name_map.get(event.competition_id, "")
    competition_weight = config.competition_bonus_weights.get(comp_name, 1.0)
    mc_bonus, mc_audit = self._apply_midfield_bonuses(
        event, group, m2, mrating, config, competition_weight
    )
```

El audit incluira `competition_weight` como campo nuevo.

---

## Ajuste 2: BASE_POINTS_TABLE_V2 para PositionGroup.MF

### Decision: modificar directamente en `services.py` vs. solo en DB

**Problema:** `BASE_POINTS_TABLE_V2` es el dict fuente que usa `ScoringConfig.default_v2()`.
Modificarlo afecta solo a configs creadas con `default_v2()` en el futuro (version v3 nueva).
Las versiones ya guardadas en DB tienen su `config_json` serializado con los valores actuales
y no cambian automaticamente.

**Decision: modificar `BASE_POINTS_TABLE_V2` en `services.py`.**

Razon: es la fuente de verdad para nuevas versiones. La creacion de la version v3 en DB (via
`CreateScoringRulesVersionUseCase`) leera el nuevo `default_v2()` y persistira los valores
correctos. Las versiones anteriores en DB quedan intactas, lo cual es el comportamiento
correcto para un sistema versionado de reglas de scoring.

### Cambios en `BASE_POINTS_TABLE_V2[PositionGroup.MF]`

| ActionType | Valor actual | Valor nuevo |
|---|---|---|
| `XA_NO_ASSIST` | 100 | **85** |
| `FOULS_DRAWN` | 35 | **25** |
| `DUELS_WON` | 15 | **12** |
| `TACKLES` | 75 | **70** |
| `INTERCEPTIONS` | 100 | **95** |

### Verificacion de `passes_avg_by_position[MF]`

`_DEFAULT_PASSES_AVG_V2` en `value_objects.py` ya tiene `"MF": 50`. Ningun cambio necesario.

---

## Ajuste 3: Achievement bonuses basados en rendimiento

### Nuevos valores en `_DEFAULT_ACHIEVEMENT_PHASE_BONUSES`

Reemplazo completo de las claves existentes. El formato de claves NO cambia — las claves
actuales son `champions_league`, `europa_league`, `conference_league`, `domestic_cup_major`,
`domestic_cup_minor`. Se añade la clave nueva `domestic_league`.

| Competicion | Phase | bonus_base actual | bonus_base nuevo |
|---|---|---|---|
| champions_league | qualify_ko | 400 | **1000** |
| champions_league | round_of_16 | 700 | **1500** |
| champions_league | quarter_final | 1000 | **2200** |
| champions_league | semi_final | 1400 | **3000** |
| champions_league | runner_up | 1200 | eliminado |
| champions_league | winner | 2200 | **5000** |
| europa_league | qualify_ko | 300 | **700** |
| europa_league | round_of_16 | 500 | **1000** |
| europa_league | quarter_final | 750 | **1500** |
| europa_league | semi_final | 1000 | **2000** |
| europa_league | runner_up | 800 | eliminado |
| europa_league | winner | 1500 | **3500** |
| conference_league | qualify_ko | 200 | **500** |
| conference_league | round_of_16 | 350 | **700** |
| conference_league | quarter_final | 550 | **1000** |
| conference_league | semi_final | 750 | **1400** |
| conference_league | runner_up | 600 | eliminado |
| conference_league | winner | 1100 | **2500** |
| domestic_cup_major | semi_final | 450 | **800** |
| domestic_cup_major | runner_up | 400 | **1200** |
| domestic_cup_major | winner | 800 | **3000** |
| domestic_cup_major | quarter_final | 250 | eliminado |
| domestic_cup_minor | runner_up | 150 | **300** |
| domestic_cup_minor | winner | 300 | **1000** |
| **domestic_league** (nueva) | champion | — | **7000** |
| **domestic_league** (nueva) | runner_up | — | **2500** |
| **domestic_league** (nueva) | top_4 | — | **1000** |

Nota: `runner_up` se elimina de UCL/UEL/UECL porque la nueva logica distingue entre fases
(qualify, round_of_16, quarter_final, semi_final, winner). El `runner_up` de esas
competiciones se modela como `semi_final` (llegar a la final = semi) o como fase independiente
si se requiere en el futuro. Para simplificar, se elimina de los europeos en este spec.

### Nueva formula: performance_factor

Formula completa:
```
achievement_bonus = bonus_base * competition_weight * participation_ratio * performance_factor
performance_factor = clamp(rank_factor * rating_factor, 0.50, 1.35)
```

**rank_factor** basado en la posicion del jugador en el ranking interno de su equipo por
SFA pts en esa competicion/temporada:

| Rango en equipo | rank_factor |
|---|---|
| top 1-3 | 1.20 |
| top 4-7 | 1.10 |
| top 8-11 | 1.00 |
| fuera del top 11 | 0.85 |
| participation_ratio < 0.20 | override: 0.50 (ignora rango) |

**rating_factor** por avg_rating del jugador en esa competicion/temporada:

| avg_rating | rating_factor |
|---|---|
| >= 8.0 | 1.20 |
| >= 7.5 | 1.10 |
| >= 7.0 | 1.00 |
| >= 6.5 | 0.90 |
| < 6.5 | 0.75 |
| None (sin rating) | 1.00 |

### Decision: use case existente vs. nuevo

**La nueva logica se implementa en `CalculateAchievementBonusesUseCase` existente.**

Razon: el use case ya calcula `participation_ratio` y aplica el bonus. Anadir
`performance_factor` es una extension de la formula existente, no un flujo nuevo. Crear un
use case separado duplicaria la logica de iteracion sobre achievements/jugadores.

### Nuevos datos requeridos por el use case

El use case necesita dos datos nuevos por jugador:
1. **rank_factor**: posicion del jugador en el ranking de su equipo por SFA pts en la
   competicion. Requiere saber cuantos jugadores del equipo tienen mas pts que este jugador.
2. **rating_factor**: avg_rating del jugador en la competicion/temporada.

Ambos se resuelven via nuevos metodos en `CompetitionAchievementRepositoryPort`:

```python
async def get_player_rank_in_team(
    self,
    player_id: int,
    team_id: int,
    competition_id: int,
    season: str,
    rules_version_id: int,
) -> int:
    """Retorna la posicion 1-based del jugador en su equipo por total_pts (menor = mejor)."""
    ...

async def get_player_avg_rating(
    self,
    player_id: int,
    competition_id: int,
    season: str,
) -> float | None:
    """Retorna el avg de PlayerStats.rating para el jugador en la competicion/temporada."""
    ...
```

Implementacion en `CompetitionAchievementRepository`:

`get_player_rank_in_team`: query a `sfa_season_scores` con `func.rank().over(partition_by=team,
order_by=total_pts.desc())` filtrando por `competition_id`, `season`, `rules_version_id`. El
resultado es la posicion 1-based.

`get_player_avg_rating`: query a `player_stats JOIN fixtures` por `competition_id`, `season`,
`player_id`, promediando `PlayerStats.rating` donde `rating IS NOT NULL`.

### Nuevo flag en ScoringConfig

```python
enable_performance_based_achievement_bonus: bool = False
```

`default_v2()`: `enable_performance_based_achievement_bonus=True`
`default()` (v1): no cambia (default=False ya desactiva)
`from_dict()`: `bool(d.get("enable_performance_based_achievement_bonus", False))`
`to_dict()`: `"enable_performance_based_achievement_bonus": self.enable_performance_based_achievement_bonus`

Cuando `enable_performance_based_achievement_bonus=False`, el use case usa la formula
original: `final_bonus = bonus_base * weight * participation_ratio` (retrocompatible).

### PlayerAchievementBonus: cambios en entidad

El campo `final_bonus` sigue siendo el unico resultado final. El `calculation_details` JSONB
se extiende con los nuevos campos de auditoria:

```json
{
  "phase": "winner",
  "bonus_base": 5000,
  "competition_weight": 1.0,
  "player_minutes": 2340,
  "team_total_minutes": 9900,
  "participation_ratio": 0.2364,
  "rank_in_team": 2,
  "rank_factor": 1.20,
  "avg_rating": 7.8,
  "rating_factor": 1.10,
  "performance_factor": 1.32,
  "final_bonus": 1558.08
}
```

No hay cambios estructurales en la entidad `PlayerAchievementBonus` ni en la tabla DB.

### Competition_weight en achievements

El `weight` ya se almacena en `CompetitionAchievement.weight` (campo de la entidad). Este
campo se persiste cuando se registra el achievement via `RegisterCompetitionAchievementUseCase`.

**Bug detectado en implementacion actual:** `register_competition_achievement.py` linea 69 hace:
```python
weight = config.competition_bonus_weights.get(str(competition_id), 1.0)
```
Esto es incorrecto — el dict usa nombres de competicion como clave, no IDs. Debe corregirse
pasando el nombre de la competicion al use case (via `competition_name: str` como parametro
de `execute()`). El router o la task que llama al use case ya tiene el nombre disponible.

Este fix se incluye en este spec como parte del saneamiento del sistema de achievements.

---

## Domain model — impacto

### `src/sfa/domain/scoring/value_objects.py`

1. `_DEFAULT_ACHIEVEMENT_PHASE_BONUSES`: reemplazar dict completo con nuevos valores + clave
   `domestic_league` nueva.
2. `ScoringConfig`: nuevo campo opcional:
   ```python
   enable_performance_based_achievement_bonus: bool = False
   ```
3. `ScoringConfig.default_v2()`: activar el campo y actualizar
   `midfield_control_bonus_cap_per_match=180`.
4. `ScoringConfig.from_dict()`: leer nuevo campo con default `False`.
5. `ScoringConfig.to_dict()`: serializar nuevo campo.

### `src/sfa/domain/scoring/services.py`

Modificar `BASE_POINTS_TABLE_V2[PositionGroup.MF]`:
- `XA_NO_ASSIST`: 100 → 85
- `FOULS_DRAWN`: 35 → 25
- `DUELS_WON`: 15 → 12
- `TACKLES`: 75 → 70
- `INTERCEPTIONS`: 100 → 95

### `src/sfa/domain/scoring_ports.py`

1. Anadir a `PlayerEventScoreRepositoryPort`:
   ```python
   async def get_competition_name_map(self) -> dict[int, str]: ...
   ```

2. Anadir a `CompetitionAchievementRepositoryPort`:
   ```python
   async def get_player_rank_in_team(
       self, player_id: int, team_id: int,
       competition_id: int, season: str, rules_version_id: int,
   ) -> int: ...

   async def get_player_avg_rating(
       self, player_id: int, competition_id: int, season: str,
   ) -> float | None: ...
   ```

### `src/sfa/application/use_cases/calculate_scores_for_rules_version.py`

1. Actualizar constantes:
   - `_MC_BONUS_CONTROL = 140`
   - `_MC_BONUS_TWO_WAY = 90`
   - `_MC_BONUS_CREATIVE = 70`
   - Nueva: `_MC_CREATIVE_MIN_PASSES_ACCURACY = 85.0`
   - `_MC_CREATIVE_MIN_RATING = 7.7`
   - `_MC_CREATIVE_MIN_PASSES = 55`
   - `_MC_BONUS_CAP`: mover a `ScoringConfig.midfield_control_bonus_cap_per_match` (ya existia);
     eliminar la constante `_MC_BONUS_CAP` del modulo (ya no se usa — el cap siempre viene del
     config).

2. En `execute()`: cargar `competition_name_map` una vez antes del loop de eventos.

3. `_score_stats_event`: recibir `competition_name_map`, derivar `competition_weight`,
   pasarlo a `_apply_midfield_bonuses`.

4. `_apply_midfield_bonuses`: recibir `competition_weight: float`, incluirlo en la formula
   y en el audit dict.

5. `creative_earned`: anadir condicion `passes_accuracy >= _MC_CREATIVE_MIN_PASSES_ACCURACY`.

### `src/sfa/application/use_cases/calculate_achievement_bonuses.py`

1. Implementar helpers de calculo de `rank_factor` y `rating_factor` como metodos privados
   (o funciones de modulo) en el mismo archivo.

2. En el loop de jugadores: si `config.enable_performance_based_achievement_bonus`, calcular
   `rank_in_team`, `avg_rating`, derivar factores, aplicar la nueva formula.

3. Anadir auditoria extendida en `calculation_details`.

### `src/sfa/application/use_cases/register_competition_achievement.py`

Fix del bug de `competition_bonus_weights.get(str(competition_id), 1.0)`:
- `execute()` recibe nuevo parametro `competition_name: str`.
- `weight = config.competition_bonus_weights.get(competition_name, 1.0)`

### `src/sfa/infrastructure/repositories/player_event_score_repository.py`

Implementar `get_competition_name_map()`.

### `src/sfa/infrastructure/repositories/competition_achievement_repository.py`

Implementar `get_player_rank_in_team()` y `get_player_avg_rating()`.

### No-changes explícitos

- Ningun cambio de schema de DB (cero migraciones).
- `PlayerEventScore` entity: sin cambios.
- `CompetitionAchievement` entity: sin cambios.
- `PlayerAchievementBonus` entity: sin cambios estructurales (solo `calculation_details` JSONB).
- `SFAScoringService`: sin cambios.
- `ScoringConfig.default()` (v1): sin cambios funcionales.
- Ningun endpoint nuevo, ningun router nuevo.
