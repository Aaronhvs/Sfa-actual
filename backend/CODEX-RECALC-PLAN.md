# CODEX EXECUTION PLAN — SFA Recalculation Optimization

> **Objetivo:** reemplazar el proceso manual de 45-50 min por un único endpoint que haga
> scoring + achievement bonuses en ~3-5 min. Sin preguntas: todo lo que necesitás está aquí.
>
> **Reglas:** arquitectura hexagonal estricta. Nunca pongas lógica en routers.
> Todo pasa por Use Case → Repository. Leer `backend/CLAUDE.md` antes de empezar.
>
> **Estado:** recálculo completo exitoso (92,700 eventos, reglas v3). El problema NO es
> la correctitud sino la velocidad y la cantidad de pasos manuales.

---

## Diagnóstico

### Problema 1 — Season score rebuild O(n) (el cuello de botella)

En `application/use_cases/calculate_scores_for_rules_version.py`, líneas 128–155:

```python
# LENTO: ~21,000 queries individuales (10,896 jugadores × ~2 competiciones promedio)
for pid, cid in affected_player_competition_pairs:
    total_pts, matches_played = await self._event_score_repo.get_player_event_totals_for_season(...)
    breakdown = await self._event_score_repo.get_season_score_breakdown(...)
    await self._scoring_repo.upsert_season_score(...)
```

**Fix:** reemplazar con un único `INSERT ... SELECT ... ON CONFLICT DO UPDATE` en PostgreSQL.
Estimado: ~21,000 queries → 1 query. 30-35 min → <1 min en este paso.

### Problema 2 — Achievement bonuses se calculan dos veces

En `application/use_cases/calculate_achievement_bonuses.py`, líneas 143–183:
el segundo loop recalcula `_compute_player_bonus` para cada jugador para sumar el total.
La información ya está disponible del primer loop — es redundante.

**Fix:** acumular el total en el primer loop, eliminar el segundo.

### Problema 3 — No hay "recalculation completa" de una sola llamada

Para actualizar el ranking hay que hacer manualmente:
1. `POST /scoring/recalculate` (con competition_id=None) → esperar ~35-40 min
2. `POST /scoring/achievements/calculate-bonuses` × 19 veces (una por competición)

**Fix:** nuevo endpoint `POST /scoring/recalculate-full` que orquesta todo en un Celery task.

---

## Archivos a modificar / crear

```
MODIFICAR:
  backend/src/sfa/domain/scoring_ports.py
  backend/src/sfa/infrastructure/repositories/player_event_score_repository.py
  backend/src/sfa/infrastructure/repositories/competition_achievement_repository.py
  backend/src/sfa/application/use_cases/calculate_scores_for_rules_version.py
  backend/src/sfa/application/use_cases/calculate_achievement_bonuses.py
  backend/src/sfa/api/v1/scoring_rules_router.py
  backend/src/sfa/core/dependencies.py

CREAR:
  backend/src/sfa/application/use_cases/run_full_recalculation.py
  backend/src/sfa/tasks/run_full_recalculation_task.py
  backend/src/sfa/api/v1/schemas/full_recalculation_schemas.py
  backend/http/recalculate_full.http
```

---

## PASO 1 — Agregar `bulk_rebuild_season_scores` al Port

**Archivo:** `backend/src/sfa/domain/scoring_ports.py`

Agregar este método a `PlayerEventScoreRepositoryPort` (después de `get_competition_name_map`):

```python
async def bulk_rebuild_season_scores(
    self,
    rules_version_id: int,
    season: str,
    competition_id: int | None = None,
) -> int:
    """Rebuild sfa_season_scores for all (player, competition) pairs in scope.
    
    Uses a single SQL bulk INSERT ... ON CONFLICT DO UPDATE.
    Does NOT overwrite achievement_bonus_pts (preserved from previous run).
    Returns number of rows upserted.
    """
    ...
```

Agregar este método a `CompetitionAchievementRepositoryPort` (después de `get_player_avg_rating`):

```python
async def get_competition_ids_for_season(self, season: str) -> list[int]:
    """Return distinct competition_ids that have registered achievements for the season."""
    ...
```

---

## PASO 2 — Implementar `bulk_rebuild_season_scores` en el Repository

**Archivo:** `backend/src/sfa/infrastructure/repositories/player_event_score_repository.py`

> ⚠️ **TRES requisitos críticos verificados en el modelo real (`SFASeasonScore`):**
>
> 1. `last_updated` es `nullable=False` — debe incluirse en el INSERT (NO tiene server_default).
> 2. `achievement_bonus_pts` tiene `default=0` en Python pero NO `server_default` en DB →
>    debe incluirse explícitamente como `0` en el INSERT para nuevas filas.
> 3. El UNIQUE es un **partial index**, no un constraint simple:
>    `index_elements=["player_id","competition_id","season","rules_version_id"]`
>    `index_where=rules_version_id IS NOT NULL`
>    → El SQL raw necesita `ON CONFLICT (...) WHERE rules_version_id IS NOT NULL`

Agregar al final de la clase `PlayerEventScoreRepository`.
Imports necesarios en la cabecera del archivo (si no están):
```python
from datetime import datetime, timezone
from sqlalchemy import text
```

```python
async def bulk_rebuild_season_scores(
    self,
    rules_version_id: int,
    season: str,
    competition_id: int | None = None,
) -> int:
    """Rebuild sfa_season_scores for all (player, competition) pairs in a single SQL query.

    - Preserves achievement_bonus_pts (not touched in ON CONFLICT DO UPDATE).
    - Requires rules_version_id IS NOT NULL (versioned scores only).
    - Returns number of rows upserted.
    """
    base_filter = "rules_version_id = :rules_version_id AND season = :season"
    if competition_id is not None:
        base_filter += " AND competition_id = :competition_id"

    now_iso = datetime.now(timezone.utc).isoformat()

    sql = text(f"""
        WITH per_action AS (
            SELECT
                player_id,
                competition_id,
                season,
                rules_version_id,
                action_type,
                COUNT(*)                               AS cnt,
                ROUND(SUM(final_points)::numeric, 2)   AS action_pts
            FROM player_event_scores
            WHERE {base_filter}
            GROUP BY player_id, competition_id, season, rules_version_id, action_type
        ),
        player_totals AS (
            SELECT
                player_id,
                competition_id,
                season,
                rules_version_id,
                ROUND(SUM(action_pts)::numeric, 2) AS total_pts
            FROM per_action
            GROUP BY player_id, competition_id, season, rules_version_id
        ),
        breakdown_agg AS (
            SELECT
                pa.player_id,
                pa.competition_id,
                pa.season,
                pa.rules_version_id,
                jsonb_object_agg(
                    pa.action_type,
                    jsonb_build_object(
                        'count', pa.cnt,
                        'pts',   pa.action_pts,
                        'pct',   ROUND(
                            (pa.action_pts / NULLIF(pt.total_pts, 0) * 100)::numeric,
                            1
                        )
                    )
                ) AS breakdown
            FROM per_action pa
            JOIN player_totals pt
                ON  pa.player_id        = pt.player_id
                AND pa.competition_id   = pt.competition_id
                AND pa.season           = pt.season
                AND pa.rules_version_id = pt.rules_version_id
            GROUP BY pa.player_id, pa.competition_id, pa.season, pa.rules_version_id
        ),
        match_counts AS (
            SELECT
                player_id,
                competition_id,
                season,
                rules_version_id,
                COUNT(DISTINCT fixture_id) AS matches_played
            FROM player_event_scores
            WHERE {base_filter}
            GROUP BY player_id, competition_id, season, rules_version_id
        )
        INSERT INTO sfa_season_scores
            (player_id, competition_id, season, rules_version_id,
             total_pts, matches_played, breakdown,
             achievement_bonus_pts,
             last_updated)
        SELECT
            pt.player_id,
            pt.competition_id,
            pt.season,
            pt.rules_version_id,
            pt.total_pts,
            mc.matches_played,
            ba.breakdown,
            0,
            :now_ts::timestamptz
        FROM player_totals pt
        JOIN match_counts mc
            ON  pt.player_id        = mc.player_id
            AND pt.competition_id   = mc.competition_id
            AND pt.season           = mc.season
            AND pt.rules_version_id = mc.rules_version_id
        JOIN breakdown_agg ba
            ON  pt.player_id        = ba.player_id
            AND pt.competition_id   = ba.competition_id
            AND pt.season           = ba.season
            AND pt.rules_version_id = ba.rules_version_id
        ON CONFLICT (player_id, competition_id, season, rules_version_id)
        WHERE rules_version_id IS NOT NULL
        DO UPDATE SET
            total_pts      = EXCLUDED.total_pts,
            matches_played = EXCLUDED.matches_played,
            breakdown      = EXCLUDED.breakdown,
            last_updated   = EXCLUDED.last_updated
        RETURNING player_id
    """)

    params: dict = {
        "rules_version_id": rules_version_id,
        "season": season,
        "now_ts": now_iso,
    }
    if competition_id is not None:
        params["competition_id"] = competition_id

    result = await self._session.execute(sql, params)
    await self._session.flush()
    rows = result.fetchall()
    return len(rows)
```

**Por qué el SQL es así:**

| Campo | Comportamiento |
|---|---|
| `achievement_bonus_pts` | `0` en INSERT → para nuevas filas. NO está en `DO UPDATE SET` → preservado en filas existentes |
| `last_updated` | `NOW()` en INSERT y en `DO UPDATE SET` — campo NOT NULL sin server_default |
| `WHERE rules_version_id IS NOT NULL` | Necesario para que PostgreSQL use el partial index correcto. Sin esto, el ON CONFLICT no matchea el índice y falla |

---

## PASO 3 — Reemplazar el loop lento en el Use Case

**Archivo:** `backend/src/sfa/application/use_cases/calculate_scores_for_rules_version.py`

### 3a. Eliminar `scoring_repo` del `__init__`

`scoring_repo` solo se usa para `upsert_season_score` (el loop que eliminamos).

Cambiar el `__init__` de:
```python
def __init__(
    self,
    rules_version_repo: ScoringRulesVersionRepositoryPort,
    event_score_repo: PlayerEventScoreRepositoryPort,
    scoring_repo: ScoringRepositoryPort,
) -> None:
    self._rules_version_repo = rules_version_repo
    self._event_score_repo = event_score_repo
    self._scoring_repo = scoring_repo
```
A:
```python
def __init__(
    self,
    rules_version_repo: ScoringRulesVersionRepositoryPort,
    event_score_repo: PlayerEventScoreRepositoryPort,
) -> None:
    self._rules_version_repo = rules_version_repo
    self._event_score_repo = event_score_repo
```

Remover el import de `ScoringRepositoryPort`:
```python
# Eliminar del bloque de imports:
from sfa.domain.ingestion_ports import ScoringRepositoryPort
```

### 3b. Reemplazar el loop (líneas 111–155 del archivo original)

Dentro del método `execute`, **eliminar**:
- La línea `affected_player_competition_pairs: set[tuple[int, int]] = set()`
- La línea `affected_player_competition_pairs.add((event.player_id, event.competition_id))` dentro del for loop
- Todo el bloque `for pid, cid in affected_player_competition_pairs:` (líneas 128–155)

**Agregar** al final del método, después del `for event in events:` loop:
```python
# Bulk rebuild all season scores in a single SQL query (replaces per-player loop)
players_updated = await self._event_score_repo.bulk_rebuild_season_scores(
    rules_version_id=rules_version_id,
    season=season,
    competition_id=competition_id,
)
```

El `return` al final del método queda igual; `players_updated` ahora es el int devuelto
por `bulk_rebuild_season_scores`.

### 3c. Actualizar el task

**Archivo:** `backend/src/sfa/tasks/calculate_scores_for_rules_version_task.py`

En `_run_calculate_scores_for_rules_version`, eliminar el import y uso de `ScoringRepository`:

```python
# Eliminar este import (dentro de la función async):
from sfa.infrastructure.repositories.scoring_repository import ScoringRepository

# Eliminar esta instanciación:
scoring_repo = ScoringRepository(session)

# Cambiar el constructor del use case a:
use_case = CalculateScoresForRulesVersionUseCase(
    rules_version_repo=rules_version_repo,
    event_score_repo=event_score_repo,
    # scoring_repo ya no se pasa
)
```

### 3d. Actualizar `dependencies.py`

**Archivo:** `backend/src/sfa/core/dependencies.py`

La factory actual pasa `scoring_repo` al use case. Actualizarla a:
```python
async def get_calculate_scores_for_rules_version_use_case(
    rules_version_repo: Annotated[
        ScoringRulesVersionRepository, Depends(get_scoring_rules_version_repository)
    ],
    event_score_repo: Annotated[
        PlayerEventScoreRepository, Depends(get_player_event_score_repository)
    ],
    # scoring_repo eliminado — ya no lo necesita el use case
) -> CalculateScoresForRulesVersionUseCase:
    return CalculateScoresForRulesVersionUseCase(
        rules_version_repo=rules_version_repo,
        event_score_repo=event_score_repo,
    )
```

---

## PASO 4 — Fix del double-computation en Achievement Bonuses

**Archivo:** `backend/src/sfa/application/use_cases/calculate_achievement_bonuses.py`

El segundo loop (líneas 143–183) recalcula todos los bonuses otra vez para sumar el total.
La información ya está disponible del primer loop.

**Reemplazar** las líneas 85–183 (todo desde `bonuses_created = 0` hasta el final del método)
con esta versión optimizada:

```python
bonuses_created = 0
players_updated: set[int] = set()
# Accumulate total bonus per player to avoid second loop
player_bonus_totals: dict[int, float] = {}

for achievement in achievements:
    team_total_minutes = await self._achievement_repo.get_team_total_minutes(
        achievement.team_id, competition_id, season
    )
    if team_total_minutes == 0:
        logger.warning(
            "[CalculateAchievementBonusesUseCase] team_id=%d has 0 total minutes, skipping",
            achievement.team_id,
        )
        continue

    player_ids = await self._achievement_repo.get_players_for_team_season(
        achievement.team_id, competition_id, season
    )

    for player_id in player_ids:
        player_minutes = await self._achievement_repo.get_player_minutes_in_competition(
            player_id, competition_id, season
        )
        final_bonus, details = await self._compute_player_bonus(
            player_id=player_id,
            player_minutes=player_minutes,
            achievement=achievement,
            team_total_minutes=team_total_minutes,
            competition_id=competition_id,
            season=season,
            rules_version_id=rules_version_id,
            config=config,
        )

        try:
            bonus = PlayerAchievementBonus(
                id=None,
                player_id=player_id,
                team_id=achievement.team_id,
                competition_id=competition_id,
                season=season,
                rules_version_id=rules_version_id,
                achievement_id=achievement.id,  # type: ignore[arg-type]
                participation_ratio=min(1.0, player_minutes / team_total_minutes),
                final_bonus=final_bonus,
                calculation_details=details,
                created_at=None,
            )
        except ValueError as exc:
            logger.warning(
                "[CalculateAchievementBonusesUseCase] Skipping player_id=%d: %s",
                player_id, exc,
            )
            continue

        await self._achievement_repo.upsert_player_bonus(bonus)
        bonuses_created += 1
        players_updated.add(player_id)
        # Accumulate total bonus for this player (across all achievements in competition)
        player_bonus_totals[player_id] = player_bonus_totals.get(player_id, 0.0) + final_bonus

# Update season_score.achievement_bonus_pts using accumulated totals (no second loop)
for player_id, total_bonus in player_bonus_totals.items():
    await self._achievement_repo.update_season_score_bonus(
        player_id=player_id,
        competition_id=competition_id,
        season=season,
        rules_version_id=rules_version_id,
        bonus_pts=round(total_bonus, 2),
    )

logger.info(
    "[CalculateAchievementBonusesUseCase] season=%s competition_id=%d "
    "bonuses_created=%d players_updated=%d",
    season, competition_id, bonuses_created, len(players_updated),
)
return CalculateAchievementBonusesResult(
    season=season,
    competition_id=competition_id,
    players_updated=len(players_updated),
    bonuses_created=bonuses_created,
    status="completed",
    error=None,
)
```

---

## PASO 5 — Agregar `get_competition_ids_for_season` al Repository

**Archivo:** `backend/src/sfa/infrastructure/repositories/competition_achievement_repository.py`

Agregar al final de la clase:

```python
async def get_competition_ids_for_season(self, season: str) -> list[int]:
    stmt = (
        select(CompetitionAchievementModel.competition_id)
        .where(CompetitionAchievementModel.season == season)
        .distinct()
    )
    result = await self._session.execute(stmt)
    return [row[0] for row in result.all()]
```

---

## PASO 6 — Crear `RunFullRecalculationUseCase`

**Archivo nuevo:** `backend/src/sfa/application/use_cases/run_full_recalculation.py`

```python
from __future__ import annotations

import logging
from dataclasses import dataclass

from sfa.domain.scoring_ports import (
    CompetitionAchievementRepositoryPort,
    PlayerEventScoreRepositoryPort,
    ScoringRulesVersionRepositoryPort,
)
from sfa.domain.ingestion_ports import ScoringRepositoryPort
from sfa.application.use_cases.calculate_scores_for_rules_version import (
    CalculateScoresForRulesVersionUseCase,
)
from sfa.application.use_cases.calculate_achievement_bonuses import (
    CalculateAchievementBonusesUseCase,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunFullRecalculationResult:
    rules_version_id: int
    season: str
    events_calculated: int
    players_updated: int
    competitions_with_bonuses: int
    achievement_bonuses_created: int
    status: str
    error: str | None


class RunFullRecalculationUseCase:
    def __init__(
        self,
        rules_version_repo: ScoringRulesVersionRepositoryPort,
        event_score_repo: PlayerEventScoreRepositoryPort,
        scoring_repo: ScoringRepositoryPort,
        achievement_repo: CompetitionAchievementRepositoryPort,
    ) -> None:
        self._rules_version_repo = rules_version_repo
        self._event_score_repo = event_score_repo
        self._scoring_repo = scoring_repo
        self._achievement_repo = achievement_repo

    async def execute(
        self,
        rules_version_id: int,
        season: str,
        force_recalculate: bool = True,
    ) -> RunFullRecalculationResult:
        # Step 1: Score all events + bulk rebuild season scores
        scoring_uc = CalculateScoresForRulesVersionUseCase(
            rules_version_repo=self._rules_version_repo,
            event_score_repo=self._event_score_repo,
            scoring_repo=self._scoring_repo,
        )
        scoring_result = await scoring_uc.execute(
            rules_version_id=rules_version_id,
            season=season,
            force_recalculate=force_recalculate,
        )
        if scoring_result.status == "failed":
            return RunFullRecalculationResult(
                rules_version_id=rules_version_id,
                season=season,
                events_calculated=0,
                players_updated=0,
                competitions_with_bonuses=0,
                achievement_bonuses_created=0,
                status="failed",
                error=scoring_result.error,
            )

        # Step 2: Calculate achievement bonuses for all competitions with registered achievements
        competition_ids = await self._achievement_repo.get_competition_ids_for_season(season)
        total_bonuses_created = 0
        bonus_uc = CalculateAchievementBonusesUseCase(
            achievement_repo=self._achievement_repo,
            rules_version_repo=self._rules_version_repo,
        )
        for comp_id in competition_ids:
            bonus_result = await bonus_uc.execute(
                season=season,
                competition_id=comp_id,
                rules_version_id=rules_version_id,
            )
            total_bonuses_created += bonus_result.bonuses_created
            logger.info(
                "[RunFullRecalculationUseCase] competition_id=%d bonuses=%d",
                comp_id, bonus_result.bonuses_created,
            )

        logger.info(
            "[RunFullRecalculationUseCase] COMPLETE season=%s rules_version_id=%d "
            "events=%d players=%d competitions_with_bonuses=%d total_bonuses=%d",
            season, rules_version_id, scoring_result.events_calculated,
            scoring_result.players_updated, len(competition_ids), total_bonuses_created,
        )
        return RunFullRecalculationResult(
            rules_version_id=rules_version_id,
            season=season,
            events_calculated=scoring_result.events_calculated,
            players_updated=scoring_result.players_updated,
            competitions_with_bonuses=len(competition_ids),
            achievement_bonuses_created=total_bonuses_created,
            status="completed",
            error=None,
        )
```

---

## PASO 7 — Crear Celery Task

**Archivo nuevo:** `backend/src/sfa/tasks/run_full_recalculation_task.py`

```python
import asyncio
import logging

logger = logging.getLogger(__name__)


def run_full_recalculation_task(rules_version_id: int, season: str, force_recalculate: bool = True):
    """Sync entry point called by Celery. Delegates to async helper."""
    asyncio.run(_run(rules_version_id, season, force_recalculate))


async def _run(rules_version_id: int, season: str, force_recalculate: bool) -> None:
    # Late imports to avoid circular dependencies at module load time
    from sfa.application.use_cases.run_full_recalculation import RunFullRecalculationUseCase
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.repositories.player_event_score_repository import (
        PlayerEventScoreRepository,
    )
    from sfa.infrastructure.repositories.scoring_repository import ScoringRepository
    from sfa.infrastructure.repositories.competition_achievement_repository import (
        CompetitionAchievementRepository,
    )
    from sfa.infrastructure.repositories.scoring_rules_version_repository import (
        ScoringRulesVersionRepository,
    )

    logger.info(
        "[run_full_recalculation_task] START rules_version_id=%d season=%s force=%s",
        rules_version_id, season, force_recalculate,
    )

    async with AsyncSessionLocal() as session:
        use_case = RunFullRecalculationUseCase(
            rules_version_repo=ScoringRulesVersionRepository(session),
            event_score_repo=PlayerEventScoreRepository(session),
            scoring_repo=ScoringRepository(session),
            achievement_repo=CompetitionAchievementRepository(session),
        )
        result = await use_case.execute(
            rules_version_id=rules_version_id,
            season=season,
            force_recalculate=force_recalculate,
        )
        if result.status == "completed":
            await session.commit()
        else:
            await session.rollback()

    logger.info(
        "[run_full_recalculation_task] DONE status=%s events=%s players=%s bonuses=%s",
        result.status, result.events_calculated, result.players_updated,
        result.achievement_bonuses_created,
    )
```

**IMPORTANTE:** registrar la task en `backend/src/sfa/celery_app.py`.
Buscar dónde están declaradas las otras tasks con `@celery_app.task` y agregar el import:

```python
# En celery_app.py, en la lista de includes o autodiscover:
"sfa.tasks.run_full_recalculation_task",
```

Si el archivo usa `app.autodiscover_tasks`, verificar que el módulo `sfa.tasks` esté en el path.
Si las tasks se declaran con `@celery_app.task` directamente, wrap con decorator:

```python
# Archivo: run_full_recalculation_task.py — versión con decorator
from sfa.celery_app import celery_app

@celery_app.task(bind=True, name="sfa.tasks.run_full_recalculation_task", max_retries=0, time_limit=600)
def run_full_recalculation_task(self, rules_version_id: int, season: str, force_recalculate: bool = True):
    asyncio.run(_run(rules_version_id, season, force_recalculate))
```

Verificar el patrón exacto mirando `backend/src/sfa/tasks/calculate_scores_for_rules_version_task.py`.

---

## PASO 8 — Crear Pydantic Schemas

**Archivo nuevo:** `backend/src/sfa/api/v1/schemas/full_recalculation_schemas.py`

```python
from pydantic import BaseModel


class FullRecalculateRequestSchema(BaseModel):
    rules_version_id: int
    season: str
    force_recalculate: bool = True


class FullRecalculateResponseSchema(BaseModel):
    task_id: str
    status: str
    message: str
```

---

## PASO 9 — Agregar endpoint al router

**Archivo:** `backend/src/sfa/api/v1/scoring_rules_router.py`

Agregar el import del schema al bloque de imports existente:

```python
from sfa.api.v1.schemas.full_recalculation_schemas import (
    FullRecalculateRequestSchema,
    FullRecalculateResponseSchema,
)
```

Agregar el endpoint al final del archivo (antes del último closing):

```python
@router.post(
    "/recalculate-full",
    response_model=FullRecalculateResponseSchema,
    status_code=202,
)
async def trigger_full_recalculate(body: FullRecalculateRequestSchema):
    """Full recalculation: scoring + bulk season score rebuild + all achievement bonuses."""
    from sfa.tasks.run_full_recalculation_task import run_full_recalculation_task

    task = run_full_recalculation_task.delay(
        rules_version_id=body.rules_version_id,
        season=body.season,
        force_recalculate=body.force_recalculate,
    )
    return FullRecalculateResponseSchema(
        task_id=task.id,
        status="queued",
        message=(
            f"Full recalculation queued for rules_version_id={body.rules_version_id} "
            f"season={body.season}. Includes scoring + achievement bonuses for all competitions."
        ),
    )
```

---

## PASO 10 — Wiring en dependencies.py

**Archivo:** `backend/src/sfa/core/dependencies.py`

Si el `CalculateScoresForRulesVersionUseCase` ya no necesita `ScoringRepository` (después de
eliminar el loop lento), actualizar su factory. Buscar `get_calculate_scores_for_rules_version_use_case`
y verificar qué repos necesita el use case actualizado.

Si el use case eliminó `scoring_repo` del `__init__`, actualizar la factory accordingly.

No es necesario añadir una factory para `RunFullRecalculationUseCase` porque la task lo
instancia directamente con late imports (mismo patrón que otras tasks).

---

## PASO 11 — Archivo HTTP de prueba

**Archivo nuevo:** `backend/http/recalculate_full.http`

```http
### Full recalculation (scoring + achievement bonuses) — rules_version_id=3, season=2024
POST http://localhost:8000/api/v1/scoring/recalculate-full
Content-Type: application/json

{
  "rules_version_id": 3,
  "season": "2024",
  "force_recalculate": true
}

###
### Solo scoring (sin achievement bonuses) — existing endpoint
POST http://localhost:8000/api/v1/scoring/recalculate
Content-Type: application/json

{
  "rules_version_id": 3,
  "season": "2024",
  "force_recalculate": true
}

###
### Achievement bonuses para competición específica
POST http://localhost:8000/api/v1/scoring/achievements/calculate-bonuses
Content-Type: application/json

{
  "season": "2024",
  "competition_id": 1,
  "rules_version_id": 3
}
```

---

## PASO 12 — Estado verificado del modelo SFASeasonScore

Archivo: `backend/src/sfa/infrastructure/models/scores/models.py`

El modelo real es:
```python
total_pts:              Numeric(12, 2), nullable=False, default=0
achievement_bonus_pts:  Numeric(12, 2), nullable=False, default=0  # solo Python default, NO server_default
matches_played:         SmallInteger,   nullable=False, default=0
breakdown:              JSONB,          nullable=True
last_updated:           DateTime(tz),   nullable=False              # NO tiene server_default
```

**Constraint de unicidad:** dos partial indexes (no una UniqueConstraint simple):
- `uq_sfa_season_score_legacy` WHERE rules_version_id IS NULL
- `uq_sfa_season_score_versioned` WHERE rules_version_id IS NOT NULL

El SQL del PASO 2 ya está escrito correctamente para esta realidad. No se necesita
ningún cambio adicional al modelo.

---

## PASO 13 — Verificar que scoring_repo todavía se necesita en CalculateScoresForRulesVersion

Después del PASO 3, el `CalculateScoresForRulesVersionUseCase` llama a:
- `self._rules_version_repo.get_version_by_id`
- `self._event_score_repo.get_events_for_recalc`
- `self._event_score_repo.event_score_exists`
- `self._event_score_repo.upsert_event_score`
- `self._event_score_repo.get_competition_name_map`
- `self._event_score_repo.bulk_rebuild_season_scores` (NUEVO)

El `self._scoring_repo` se usaba solo para `upsert_season_score`. Si ya no se usa, removerlo:
1. Eliminar `scoring_repo` del `__init__`
2. Eliminar `ScoringRepositoryPort` de imports
3. Actualizar la factory en `dependencies.py`
4. Actualizar `RunFullRecalculationUseCase` si pasaba `scoring_repo` al use case interno

---

## ORDEN DE EJECUCIÓN

```
1.  scoring_ports.py          → agregar bulk_rebuild_season_scores + get_competition_ids_for_season
2.  player_event_score_repository.py  → implementar bulk_rebuild_season_scores
3.  competition_achievement_repository.py → implementar get_competition_ids_for_season
4.  calculate_scores_for_rules_version.py → reemplazar loop lento
5.  calculate_achievement_bonuses.py  → fix double-computation
6.  run_full_recalculation.py         → crear use case nuevo
7.  run_full_recalculation_task.py    → crear celery task
8.  full_recalculation_schemas.py     → crear schemas
9.  scoring_rules_router.py           → agregar endpoint
10. dependencies.py                   → actualizar wiring si necesario
11. recalculate_full.http             → crear archivo de prueba
```

---

## VERIFICACIÓN FINAL

Después de implementar, verificar en WSL:

```bash
cd /mnt/c/Users/formu/OneDrive/Escritorio/sfa-project/backend
docker compose -f docker-compose-development.yml up -d

# Test: recalculación completa
curl -X POST http://localhost:8000/api/v1/scoring/recalculate-full \
  -H "Content-Type: application/json" \
  -d '{"rules_version_id": 3, "season": "2024", "force_recalculate": true}'
# → debe retornar {"task_id": "...", "status": "queued", ...}

# Monitorear progreso en logs del worker:
docker compose -f docker-compose-development.yml logs -f celery_worker

# Verificar resultados en DB:
docker compose -f docker-compose-development.yml exec db psql -U sfa -d sfa -c \
  "SELECT COUNT(*) FROM player_event_scores WHERE rules_version_id=3;"
# → 92700

docker compose -f docker-compose-development.yml exec db psql -U sfa -d sfa -c \
  "SELECT COUNT(*) FROM sfa_season_scores WHERE rules_version_id=3;"
# → debería cubrir todos los (player, competition) pares

docker compose -f docker-compose-development.yml exec db psql -U sfa -d sfa -c \
  "SELECT COUNT(*) FROM player_achievement_bonuses WHERE rules_version_id=3;"
# → 1858+ (igual o más que antes)

# Top 5 ranking con achievement bonuses:
docker compose -f docker-compose-development.yml exec db psql -U sfa -d sfa -c \
  "SELECT p.name, SUM(s.total_pts + s.achievement_bonus_pts) as grand_total
   FROM sfa_season_scores s
   JOIN players p ON s.player_id = p.id
   WHERE s.rules_version_id = 3 AND s.season = '2024'
   GROUP BY p.id, p.name
   ORDER BY grand_total DESC
   LIMIT 5;"
```

---

## NOTAS / PROBLEMAS CONOCIDOS

### Bruno Fernandes sigue inflado
La inflación de jugadores de equipos débiles en múltiples competiciones menores es un problema
de calibración del modelo, no un bug de código. El M1 damping (spec 0015) reduce pero no
elimina el efecto. La solución completa requiere un nuevo spec (0017) que aplique
`competition_weight` a TODAS las stats (no solo a MC bonuses). Por ahora no forma parte de
este plan — no modificar ese comportamiento aquí.

### ScoringRepo puede quedar sin uso
Si `CalculateScoresForRulesVersionUseCase` ya no necesita `scoring_repo`, la dependency
factory también debe actualizarse. No eliminar el repositorio en sí — puede ser usado por
otros use cases (`GetRankingUseCase`, etc.).

### Timeout del Celery task
El proceso completo con bulk rebuild debería tardar <5 min. Sin embargo, configurar
`time_limit=600` (10 min) en el decorator de la task como margen de seguridad.

### Celery Beat no debe disparar este task
No agregar este task al beat schedule. Es de ejecución manual (one-shot al final de temporada).
