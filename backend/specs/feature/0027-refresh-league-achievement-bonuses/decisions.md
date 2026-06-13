# Refresh League Achievement Bonuses on Full Recalculation

## Contexto de negocio

Cuando el usuario crea una nueva `ScoringRulesVersion` y cambia los valores de
`achievement_phase_bonuses.domestic_league` (ej. `champion: 7000 → 12000`), y
luego lanza `RunFullRecalculationUseCase`, los jugadores campeones de liga
doméstica siguen acumulando el bonus del valor antiguo. El cambio de config
no tiene efecto sobre ligas.

Esto hace que el sistema de scoring sea **inconsistente**: cambiar una rules
version actualiza correctamente los bonuses de copas y UCL (porque
`InferAllCompetitionAchievementsUseCase` los re-upserta desde config antes de
calcular), pero deja las ligas congeladas en el valor del momento del registro
manual. El usuario solo lo descubre comparando manualmente los totales.

## Causa raíz

El pipeline de recálculo tiene una asimetría de cobertura:

1. `InferAllCompetitionAchievementsUseCase` solo procesa competiciones con
   fixtures de eliminación directa (knockout). Obtiene su lista de
   `_infer_repo.get_all_knockout_competition_ids(season)`. Las ligas
   round-robin nunca aparecen aquí.

2. Las ligas tienen sus `competition_achievements` creados manualmente vía
   `RegisterCompetitionAchievementUseCase`, que escribe `bonus_points` leídos
   de la config activa **en el momento del registro**. Ese valor queda
   congelado en DB.

3. `CalculateAchievementBonusesUseCase._compute_player_bonus()` usa
   `achievement.bonus_points` leído de `competition_achievements` (líneas 195
   y 213 del archivo). Si el row fue insertado con la versión anterior, el
   cálculo usa el valor viejo.

4. El `upsert_achievement` del repositorio sí actualiza `bonus_points` y
   `weight` en el `ON CONFLICT DO UPDATE`, pero nadie llama a ese upsert para
   ligas durante el recálculo.

## Restricciones

- No romper el flujo de inference existente para copas y UCL.
- No añadir nuevas entidades de dominio ni migraciones de schema.
- La solución debe ser idempotente: lanzar el recálculo N veces con la misma
  rules version produce el mismo resultado.
- `CompetitionAchievement` solo lleva `competition_id`, no el nombre de la
  competición; el nuevo use case necesita resolver el nombre para hacer el
  lookup en `config.achievement_phase_bonuses["domestic_league"]`.
- Las ligas a cubrir son las que aparecen en
  `_DEFAULT_COMPETITION_BONUS_WEIGHTS` pero no en `COMPETITION_CATEGORY_MAP`.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Nuevo use case `RefreshLeagueAchievementBonusesUseCase` que re-upserta achievements de ligas desde config antes del cálculo de bonuses | **Opción A:** `CalculateAchievementBonusesUseCase` lee `bonus_points` directamente desde `config.achievement_phase_bonuses[category][phase]` | `CompetitionAchievement` no lleva `category`; el use case de cálculo tendría que resolver nombres de competición, rompiendo la separación de responsabilidades. Tampoco resolvería `weight` stale. |
| Nuevo use case `RefreshLeagueAchievementBonusesUseCase` | **Opción C:** Añadir `domestic_league` a `COMPETITION_CATEGORY_MAP` con lógica de standings | Requiere nuevo método de repositorio para standings finales de liga, lógica de desempate por puntos, y añade riesgo de regresión en el flujo de inference de copas. Las ligas ya tienen achievements registrados manualmente; re-inferirlos es innecesario. |
| Lista estática `DOMESTIC_LEAGUE_NAMES` en el módulo del nuevo use case | Campo `category` en tabla `competitions` | Over-engineering para este bug. Las ligas objetivo son un conjunto cerrado y bien conocido. |
| Nuevo método `get_achievements_for_domestic_leagues(season, league_names)` en `CompetitionAchievementRepositoryPort` | Reusar `get_achievements_for_season` en un loop | Requeriría conocer de antemano todos los `competition_id` de ligas; el nuevo método encapsula el JOIN con `competitions` y resuelve el problema en una sola query. |
| Insertar el nuevo use case entre `InferAll...` y `CalculateAchievementBonuses...` en el pipeline | Insertarlo al final del pipeline | `CalculateAchievementBonusesUseCase` debe leer los `bonus_points` ya actualizados; ejecutarlo antes garantiza la consistencia. |

## Domain Model

No aplica. Esta feature no requiere nuevas entidades de dominio. `CompetitionAchievement`
ya tiene `bonus_points` y `weight`. El new use case solo re-upserta rows existentes
con valores frescos leídos de la config activa.

## Integraciones externas

Ninguna. Opera solo sobre datos ya almacenados en DB.
