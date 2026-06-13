# Auto-infer competition achievements from fixtures

## Contexto de negocio

SFA premia a los jugadores cuyo equipo llegó lejos en una competición de copa mediante
registros en `competition_achievements` → `player_achievement_bonuses`. Actualmente estos
registros se crean **manualmente** con el script `register_achievements.py`. Para la
temporada 2025 nadie ejecutó el script: 0 jugadores tienen bonificaciones de logro en 2025.

Esta feature automatiza el proceso: a partir de los fixtures ya almacenados en DB infiere
qué fase alcanzó cada equipo en las competiciones eliminatorias y hace upsert de los logros
de forma automática, garantizando que futuras temporadas no queden sin bonificaciones.

El impacto en producto es directo: los scores SFA de los jugadores que participaron en CL,
EL, Conference League y copas domésticas quedarán correctamente incrementados por sus
logros de equipo sin depender de una acción manual.

## Restricciones

- Solo aplicable a competiciones con fases eliminatorias (al menos un fixture con
  `stage != "regular"`). Las ligas domésticas (todos los stages son `"regular"`) se
  saltan silenciosamente — no hay forma de inferir campeón desde fixtures sin standings.
- El modelo `Fixture` no tiene columnas de goles (`home_goals`, `away_goals`). Para
  determinar el ganador de la final hay que contar eventos de gol desde `player_events`
  (EventType GOAL + GOAL_PENALTY + GOAL_SHOOTOUT como desempate).
- Sin migraciones de DB: se reutilizan las tablas `competition_achievements`,
  `competition_stages`, `fixtures` y `player_events` existentes.
- El `bonus_points` y `weight` de cada logro se resuelven desde la config de la
  `ScoringRulesVersion` activa (campo `achievement_phase_bonuses` y
  `competition_bonus_weights`), igual que hace `RegisterCompetitionAchievementUseCase`.
- La inferencia es idempotente: usa el `upsert_achievement` existente con constraint
  `uq_competition_achievement (competition_id, team_id, season, phase)`.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Nuevo Protocol `InferAchievementsRepositoryPort` separado de `CompetitionAchievementRepositoryPort` | Añadir métodos al port existente | SRP: el port existente maneja lectura de logros ya registrados y bonificaciones de jugadores; las consultas de inferencia sobre fixtures/events son responsabilidad distinta |
| Detectar competición eliminatoria si ANY fixture tiene `stage != "regular"` | Tabla de configuración explícita de tipo de competición | Los datos ya existen en `fixtures.stage`; no se necesita nueva tabla ni migración |
| Algoritmo de eliminación por diferencia de conjuntos: `teams_at_stage[N] − teams_at_stage[N+1]` | Rastrear progresión partido a partido | Más simple, menos propenso a errores con multi-leg o replays; produce el mismo resultado correcto |
| Ganador de la final: contar goals en `player_events` (GOAL + GOAL_PENALTY; GOAL_SHOOTOUT como desempate; menor team_id como último fallback) | Columna `home_goals`/`away_goals` en fixtures | El modelo Fixture no tiene esas columnas; player_events sí tiene los datos |
| Mapeo competición → categoría de bonus mediante dict constante en el use case (por nombre de competición) | Campo `achievement_category` en Competition model | Evita migración; los nombres de competición ya son únicos en DB; el mismo patrón lo usa `competition_bonus_weights` en `ScoringConfig` |
| Dos endpoints separados: `/infer-achievements` (single) y `/infer-achievements-all` (all) | Un único endpoint con `competition_id` opcional | Mayor claridad semántica; el endpoint "all" puede tardar minutos y se despacha como task Celery independiente |
| Integración en `run_full_recalculation_task` como paso opcional controlado por flag `infer_achievements: bool = True` | Tarea encadenada separada | El pipeline completo ya incluye scoring + bulk rebuild + achievement bonuses; añadir inferencia al inicio de ese flujo cierra el ciclo automáticamente |
| STAGE_ORDER hardcodeado: `round_of_16→1, quarter→2, semi→3, final→4` | Leer `competition_stages.stage_factor` para ordenar | stage_factor puede ser igual para varios stages; el orden semántico de eliminación es siempre el mismo independientemente del factor |

## Domain Model

No se requieren nuevas entidades de dominio con invariantes propias. Los DTOs nuevos son
estructuras de datos planas (frozen dataclasses) que viven en el port de dominio.

### Nuevas DTOs de dominio

**`KnockoutFixtureDTO`** — fixture eliminatorio leído desde infra:
- `fixture_id: int`
- `stage: str` — valor raw del campo `fixtures.stage` (e.g. "final", "semi", "quarter", "round_of_16")
- `home_team_id: int`
- `away_team_id: int`

**`InferAchievementsResult`** — resultado del use case por competición:
- `competition_id: int`
- `season: str`
- `skipped: bool` — True si no es competición eliminatoria
- `achievements_upserted: int`
- `phases_found: list[str]` — fases inferidas, para logging

**`InferAllAchievementsResult`** — resultado del use case all-seasons:
- `season: str`
- `competitions_processed: int`
- `competitions_skipped: int`
- `total_achievements_upserted: int`

### Protocol nuevo

```python
# domain/infer_achievements_ports.py

@runtime_checkable
class InferAchievementsRepositoryPort(Protocol):
    async def get_knockout_stage_fixtures(
        self, competition_id: int, season: str
    ) -> list[KnockoutFixtureDTO]: ...
    # Devuelve fixtures donde stage != "regular". Si vacío → no es competición KO.

    async def get_goals_for_fixture(
        self, fixture_id: int
    ) -> dict[int, int]: ...
    # team_id → nº de goles (GOAL + GOAL_PENALTY). Excluye GOAL_SHOOTOUT.
    # Si empate de goles normales, llamar a get_shootout_goals_for_fixture.

    async def get_shootout_goals_for_fixture(
        self, fixture_id: int
    ) -> dict[int, int]: ...
    # team_id → nº de goles de penalti en tanda (GOAL_SHOOTOUT).

    async def get_competition_name(self, competition_id: int) -> str: ...

    async def get_all_knockout_competition_ids(self, season: str) -> list[int]: ...
    # Devuelve competition_ids que tienen al menos un fixture con stage != "regular"
    # para esa temporada.
```

### Mapeo nombre competición → categoría bonus (constante en use case)

```python
COMPETITION_CATEGORY_MAP: dict[str, str] = {
    "Champions League":    "champions_league",
    "Europa League":       "europa_league",
    "Conference League":   "conference_league",
    "FA Cup":              "domestic_cup_major",
    "Copa del Rey":        "domestic_cup_major",
    "DFB-Pokal":           "domestic_cup_major",
    "Coppa Italia":        "domestic_cup_major",
    "Coupe de France":     "domestic_cup_major",
    "EFL Cup":             "domestic_cup_minor",
    "Community Shield":    "domestic_cup_minor",
    "Supercopa de España": "domestic_cup_minor",
    "Supercoppa Italiana": "domestic_cup_minor",
    "DFL-Supercup":        "domestic_cup_minor",
    "Trophée des Champions": "domestic_cup_minor",
}
```

### Mapeo fixture stage → achievement phase (constante en use case)

```python
STAGE_TO_PHASE: dict[str, str] = {
    "final":        "winner",       # ganador
    # "final"       → "runner_up"  # perdedor (caso especial)
    "semi":         "semi_final",
    "quarter":      "quarter_final",
    "round_of_16":  "round_of_16",
}

STAGE_ORDER: dict[str, int] = {
    "round_of_16": 1,
    "quarter":     2,
    "semi":        3,
    "final":       4,
}
```

## Integraciones externas

Ninguna. La feature opera exclusivamente sobre datos ya presentes en la DB PostgreSQL.
