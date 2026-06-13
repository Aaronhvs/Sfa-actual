# Plan: Full Recalculation Pipeline (0016)

## Orden de implementación

Los pasos deben ejecutarse en el orden indicado. Cada paso tiene un criterio de completitud
verificable. No saltear ninguno.

---

## PASO 0 — Prerequisito: refactor/0016-bulk-season-score-rebuild

**Este spec DEPENDE de refactor/0016-bulk-season-score-rebuild.**

Antes de comenzar la implementación de este feature, verificar que el spec de refactor
0016 está completo. Concretamente:
- `PlayerEventScoreRepository` tiene el método `bulk_rebuild_season_scores()`
- `PlayerEventScoreRepositoryPort` declara `bulk_rebuild_season_scores()` en el Protocol
- El método `_rebuild_season_scores()` en `CalculateScoresForRulesVersionUseCase` ya usa
  el bulk rebuild en vez del loop

Sin ese prerequisito, este spec no puede implementarse.

---

## Archivos a crear

- [ ] `src/sfa/application/use_cases/run_all_achievement_bonuses.py`
- [ ] `src/sfa/tasks/run_full_recalculation_task.py`
- [ ] `tests/use_cases/test_run_all_achievement_bonuses.py`

## Archivos a modificar

- [ ] `src/sfa/domain/scoring_ports.py` — método nuevo en `PlayerEventScoreRepositoryPort`
- [ ] `src/sfa/infrastructure/repositories/player_event_score_repository.py` — método nuevo
- [ ] `src/sfa/api/v1/schemas/scoring_rules_schemas.py` — schemas nuevos
- [ ] `src/sfa/api/v1/scoring_rules_router.py` — 2 endpoints nuevos
- [ ] `src/sfa/core/dependencies.py` — factory nueva

---

## Checklist de implementación

### 1. Port nuevo en `scoring_ports.py`

**Archivo:** `src/sfa/domain/scoring_ports.py`

- [ ] Agregar el método `get_distinct_competition_ids_for_season` al Protocol
  `PlayerEventScoreRepositoryPort`:

  ```python
  async def get_distinct_competition_ids_for_season(
      self,
      season: str,
      rules_version_id: int,
  ) -> list[int]: ...
  ```

  Ubicarlo después de `get_competition_name_map` y antes del cierre del Protocol.

  **Criterio de completitud:** el Protocol tiene el método; `isinstance` con la clase
  concreta no lanza error (el decorador `@runtime_checkable` lo verifica en los tests).

---

### 2. Implementación en `PlayerEventScoreRepository`

**Archivo:** `src/sfa/infrastructure/repositories/player_event_score_repository.py`

- [ ] Agregar el método `get_distinct_competition_ids_for_season` a la clase
  `PlayerEventScoreRepository`. Retorna todas las `competition_id` distintas que tienen
  al menos un `PlayerEventScore` para esa `season` y `rules_version_id`:

  ```python
  async def get_distinct_competition_ids_for_season(
      self,
      season: str,
      rules_version_id: int,
  ) -> list[int]:
      stmt = (
          select(PlayerEventScoreModel.competition_id)
          .where(
              PlayerEventScoreModel.season == season,
              PlayerEventScoreModel.rules_version_id == rules_version_id,
          )
          .distinct()
          .order_by(PlayerEventScoreModel.competition_id)
      )
      result = await self._session.execute(stmt)
      return [row[0] for row in result.all()]
  ```

  **Criterio de completitud:** método presente y retorna `list[int]` sin lanzar excepciones
  en un test con Fake.

---

### 3. Nuevo Use Case: `RunAllAchievementBonusesUseCase`

**Archivo:** `src/sfa/application/use_cases/run_all_achievement_bonuses.py`

```python
from __future__ import annotations

import logging
from dataclasses import dataclass

from sfa.domain.scoring_ports import (
    CompetitionAchievementRepositoryPort,
    PlayerEventScoreRepositoryPort,
    ScoringRulesVersionRepositoryPort,
)
from sfa.application.use_cases.calculate_achievement_bonuses import (
    CalculateAchievementBonusesUseCase,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunAllAchievementBonusesResult:
    season: str
    rules_version_id: int
    competitions_processed: int
    total_bonuses_created: int
    total_players_updated: int
    status: str
    error: str | None


class RunAllAchievementBonusesUseCase:
    """Executes CalculateAchievementBonusesUseCase for every competition in a season."""

    def __init__(
        self,
        achievement_repo: CompetitionAchievementRepositoryPort,
        event_score_repo: PlayerEventScoreRepositoryPort,
        rules_version_repo: ScoringRulesVersionRepositoryPort,
    ) -> None:
        self._achievement_repo = achievement_repo
        self._event_score_repo = event_score_repo
        self._rules_version_repo = rules_version_repo

    async def execute(
        self,
        season: str,
        rules_version_id: int,
    ) -> RunAllAchievementBonusesResult:
        competition_ids = await self._event_score_repo.get_distinct_competition_ids_for_season(
            season=season,
            rules_version_id=rules_version_id,
        )
        if not competition_ids:
            logger.warning(
                "[RunAllAchievementBonusesUseCase] No competitions found for "
                "season=%s rules_version_id=%d",
                season, rules_version_id,
            )
            return RunAllAchievementBonusesResult(
                season=season,
                rules_version_id=rules_version_id,
                competitions_processed=0,
                total_bonuses_created=0,
                total_players_updated=0,
                status="completed",
                error=None,
            )

        sub_uc = CalculateAchievementBonusesUseCase(
            achievement_repo=self._achievement_repo,
            rules_version_repo=self._rules_version_repo,
        )

        total_bonuses = 0
        total_players: set[int] = set()

        for comp_id in competition_ids:
            result = await sub_uc.execute(
                season=season,
                competition_id=comp_id,
                rules_version_id=rules_version_id,
            )
            if result.status == "failed":
                logger.error(
                    "[RunAllAchievementBonusesUseCase] competition_id=%d failed: %s",
                    comp_id, result.error,
                )
                continue
            total_bonuses += result.bonuses_created
            logger.info(
                "[RunAllAchievementBonusesUseCase] competition_id=%d done: "
                "bonuses=%d players=%d",
                comp_id, result.bonuses_created, result.players_updated,
            )

        logger.info(
            "[RunAllAchievementBonusesUseCase] season=%s rv=%d competitions=%d "
            "total_bonuses=%d",
            season, rules_version_id, len(competition_ids), total_bonuses,
        )
        return RunAllAchievementBonusesResult(
            season=season,
            rules_version_id=rules_version_id,
            competitions_processed=len(competition_ids),
            total_bonuses_created=total_bonuses,
            total_players_updated=0,  # not tracked at aggregate level
            status="completed",
            error=None,
        )
```

- [ ] El archivo existe con este contenido exacto.
- [ ] `from __future__ import annotations` presente al inicio.
- [ ] El import de `CalculateAchievementBonusesUseCase` es un import tardío de módulo (no
  circular). Verificar: `from sfa.application.use_cases.calculate_achievement_bonuses import ...`
  no crea import circular.

  **Criterio de completitud:** `python -c "from sfa.application.use_cases.run_all_achievement_bonuses import RunAllAchievementBonusesUseCase"` sin errores.

---

### 4. Nuevo Celery task: `run_full_recalculation_task`

**Archivo:** `src/sfa/tasks/run_full_recalculation_task.py`

- [ ] Crear el archivo con el siguiente contenido:

```python
import asyncio
import json
import logging

from sfa.celery_app import celery_app

logger = logging.getLogger(__name__)

_PROGRESS_KEY_TTL = 86400  # 24 horas en segundos


@celery_app.task(bind=True, max_retries=1, default_retry_delay=600)
def run_full_recalculation_task(
    self,
    rules_version_id: int,
    season: str,
    force_recalculate: bool = False,
):
    """Full pipeline: score events → bulk rebuild season_scores → achievement bonuses."""
    task_id = self.request.id
    try:
        asyncio.run(
            _run(
                task_id=task_id,
                rules_version_id=rules_version_id,
                season=season,
                force_recalculate=force_recalculate,
            )
        )
    except Exception as exc:
        logger.error(
            "[run_full_recalculation_task] Failed rules_version_id=%d season=%s: %s",
            rules_version_id, season, exc,
        )
        raise self.retry(exc=exc)


async def _set_progress(redis_client, task_id: str, data: dict) -> None:
    key = f"sfa:recalc:{task_id}:progress"
    await redis_client.set(key, json.dumps(data), ex=_PROGRESS_KEY_TTL)


async def _run(
    task_id: str,
    rules_version_id: int,
    season: str,
    force_recalculate: bool,
) -> None:
    from sfa.application.use_cases.calculate_scores_for_rules_version import (
        CalculateScoresForRulesVersionUseCase,
    )
    from sfa.application.use_cases.run_all_achievement_bonuses import (
        RunAllAchievementBonusesUseCase,
    )
    from sfa.infrastructure.database import AsyncSessionLocal
    from sfa.infrastructure.redis_client import get_redis_client
    from sfa.infrastructure.repositories.competition_achievement_repository import (
        CompetitionAchievementRepository,
    )
    from sfa.infrastructure.repositories.player_event_score_repository import (
        PlayerEventScoreRepository,
    )
    from sfa.infrastructure.repositories.scoring_repository import ScoringRepository
    from sfa.infrastructure.repositories.scoring_rules_version_repository import (
        ScoringRulesVersionRepository,
    )

    redis = get_redis_client()

    # ── FASE 1: Scoring de eventos + bulk rebuild de season_scores ────────────
    await _set_progress(redis, task_id, {
        "phase": "scoring",
        "pct": 0,
        "message": "Calculando player_event_scores y reconstruyendo season_scores...",
    })

    scoring_result = None
    async with AsyncSessionLocal() as session:
        rules_version_repo = ScoringRulesVersionRepository(session)
        event_score_repo = PlayerEventScoreRepository(session)
        scoring_repo = ScoringRepository(session)

        scoring_uc = CalculateScoresForRulesVersionUseCase(
            rules_version_repo=rules_version_repo,
            event_score_repo=event_score_repo,
            scoring_repo=scoring_repo,
        )
        scoring_result = await scoring_uc.execute(
            rules_version_id=rules_version_id,
            season=season,
            force_recalculate=force_recalculate,
        )
        await session.commit()

    if scoring_result.status == "failed":
        await _set_progress(redis, task_id, {
            "phase": "failed",
            "pct": 0,
            "error": scoring_result.error,
        })
        raise RuntimeError(f"Scoring phase failed: {scoring_result.error}")

    await _set_progress(redis, task_id, {
        "phase": "scoring_done",
        "pct": 50,
        "events_calculated": scoring_result.events_calculated,
        "players_updated": scoring_result.players_updated,
        "message": "Scoring completado. Calculando achievement bonuses...",
    })

    logger.info(
        "[run_full_recalculation_task] Phase 1 done: events=%d players=%d",
        scoring_result.events_calculated, scoring_result.players_updated,
    )

    # ── FASE 2: Achievement bonuses para todas las competiciones ─────────────
    await _set_progress(redis, task_id, {
        "phase": "achievements",
        "pct": 50,
        "message": "Calculando achievement bonuses para todas las competiciones...",
    })

    achievements_result = None
    async with AsyncSessionLocal() as session:
        achievement_repo = CompetitionAchievementRepository(session)
        event_score_repo = PlayerEventScoreRepository(session)
        rules_version_repo = ScoringRulesVersionRepository(session)

        achievements_uc = RunAllAchievementBonusesUseCase(
            achievement_repo=achievement_repo,
            event_score_repo=event_score_repo,
            rules_version_repo=rules_version_repo,
        )
        achievements_result = await achievements_uc.execute(
            season=season,
            rules_version_id=rules_version_id,
        )
        await session.commit()

    # ── COMPLETADO ────────────────────────────────────────────────────────────
    await _set_progress(redis, task_id, {
        "phase": "done",
        "pct": 100,
        "summary": {
            "events_calculated": scoring_result.events_calculated,
            "players_updated": scoring_result.players_updated,
            "competitions_processed": achievements_result.competitions_processed,
            "bonuses_created": achievements_result.total_bonuses_created,
        },
        "message": "Pipeline completo.",
    })

    logger.info(
        "[run_full_recalculation_task] Done: season=%s rv=%d events=%d players=%d "
        "competitions=%d bonuses=%d",
        season, rules_version_id,
        scoring_result.events_calculated, scoring_result.players_updated,
        achievements_result.competitions_processed, achievements_result.total_bonuses_created,
    )
```

- [ ] Los imports dentro de `_run` son late imports (patrón existente en todos los tasks).
- [ ] `max_retries=1` porque el task es idempotente con `force_recalculate=True`.

  **Criterio de completitud:** `python -c "from sfa.tasks.run_full_recalculation_task import run_full_recalculation_task"` sin errores.

---

### 5. Schemas nuevos

**Archivo:** `src/sfa/api/v1/schemas/scoring_rules_schemas.py`

- [ ] Agregar al final del archivo los dos nuevos schemas:

```python
class FullRecalculateRequestSchema(BaseModel):
    rules_version_id: int
    season: str
    force_recalculate: bool = False


class FullRecalculateResponseSchema(BaseModel):
    task_id: str
    status: str
    message: str


class RecalculateProgressSchema(BaseModel):
    task_id: str
    phase: str      # "scoring" | "scoring_done" | "achievements" | "done" | "failed" | "not_found"
    pct: float
    message: str | None = None
    events_calculated: int | None = None
    players_updated: int | None = None
    competitions_processed: int | None = None
    bonuses_created: int | None = None
    error: str | None = None
```

  **Criterio de completitud:** los tres schemas existen en el archivo y son importables.

---

### 6. Endpoints en `scoring_rules_router.py`

**Archivo:** `src/sfa/api/v1/scoring_rules_router.py`

- [ ] Agregar los imports necesarios al inicio del archivo:

```python
import json

from sfa.api.v1.schemas.scoring_rules_schemas import (
    # (imports existentes)
    FullRecalculateRequestSchema,
    FullRecalculateResponseSchema,
    RecalculateProgressSchema,
)
```

- [ ] Agregar el endpoint de disparo (al final del router):

```python
@router.post(
    "/recalculate-full",
    response_model=FullRecalculateResponseSchema,
    status_code=202,
)
async def trigger_full_recalculate(body: FullRecalculateRequestSchema):
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
            f"season={body.season}"
        ),
    )
```

- [ ] Agregar el endpoint de consulta de progreso:

```python
@router.get(
    "/recalculate-full/{task_id}/status",
    response_model=RecalculateProgressSchema,
)
async def get_full_recalculate_status(task_id: str):
    from sfa.infrastructure.redis_client import get_redis_client

    redis = get_redis_client()
    key = f"sfa:recalc:{task_id}:progress"
    raw = await redis.get(key)

    if raw is None:
        return RecalculateProgressSchema(
            task_id=task_id,
            phase="not_found",
            pct=0,
            message="Task not found or expired (TTL 24h)",
        )

    data = json.loads(raw)
    return RecalculateProgressSchema(
        task_id=task_id,
        phase=data.get("phase", "unknown"),
        pct=float(data.get("pct", 0)),
        message=data.get("message"),
        events_calculated=data.get("events_calculated"),
        players_updated=data.get("players_updated"),
        competitions_processed=data.get("summary", {}).get("competitions_processed"),
        bonuses_created=data.get("summary", {}).get("bonuses_created"),
        error=data.get("error"),
    )
```

  **Criterio de completitud:** `GET /api/v1/scoring/recalculate-full/{task_id}/status` retorna
  200 con el schema correcto (incluso si la key no existe en Redis → `phase: "not_found"`).

---

### 7. Wiring en `dependencies.py`

**Archivo:** `src/sfa/core/dependencies.py`

- [ ] Agregar el import del nuevo use case:

```python
from sfa.application.use_cases.run_all_achievement_bonuses import RunAllAchievementBonusesUseCase
```

- [ ] Agregar la factory:

```python
async def get_run_all_achievement_bonuses_use_case(
    achievement_repo: Annotated[
        CompetitionAchievementRepository, Depends(get_competition_achievement_repository)
    ],
    event_score_repo: Annotated[
        PlayerEventScoreRepository, Depends(get_player_event_score_repository)
    ],
    rules_version_repo: Annotated[
        ScoringRulesVersionRepository, Depends(get_scoring_rules_version_repository)
    ],
) -> RunAllAchievementBonusesUseCase:
    return RunAllAchievementBonusesUseCase(
        achievement_repo=achievement_repo,
        event_score_repo=event_score_repo,
        rules_version_repo=rules_version_repo,
    )
```

  **Criterio de completitud:** la factory existe y retorna una instancia de
  `RunAllAchievementBonusesUseCase` sin errores de importación.

---

### 8. Archivo HTTP de pruebas

**Archivo:** `http/scoring_full_recalculation.http`

- [ ] Crear el archivo con los siguientes casos:

```http
### Trigger full recalculation pipeline
POST http://localhost:8000/api/v1/scoring/recalculate-full
Content-Type: application/json

{
  "rules_version_id": 1,
  "season": "2024",
  "force_recalculate": true
}

###

### Check progress of a running full recalculation
GET http://localhost:8000/api/v1/scoring/recalculate-full/{{task_id}}/status

###

### Error: missing rules_version_id
POST http://localhost:8000/api/v1/scoring/recalculate-full
Content-Type: application/json

{
  "season": "2024"
}
```

---

### 9. Tests de `RunAllAchievementBonusesUseCase`

**Archivo:** `tests/use_cases/test_run_all_achievement_bonuses.py`

- [ ] Crear Fakes para los tres Protocols usados:

  `FakePlayerEventScoreRepository` que implementa `PlayerEventScoreRepositoryPort`:
  - `get_distinct_competition_ids_for_season(season, rules_version_id)` → retorna lista configurable.
  - Todos los demás métodos del Protocol → levantan `NotImplementedError`.

  `FakeCompetitionAchievementRepository` que implementa `CompetitionAchievementRepositoryPort`:
  - `get_achievements_for_season(competition_id, season)` → retorna `[]` (sin achievements = UC retorna 0 bonuses).
  - Todos los demás métodos → levantan `NotImplementedError` o retornan defaults mínimos.

  `FakeScoringRulesVersionRepository` que implementa `ScoringRulesVersionRepositoryPort`:
  - `get_version_by_id(version_id)` → retorna un `ScoringRulesVersion` de prueba válido.

- [ ] Tests:

  **`test_no_competitions_returns_completed_with_zero_counts`**
  - Fake retorna `[]` en `get_distinct_competition_ids_for_season`.
  - El result tiene `status="completed"`, `competitions_processed=0`, `total_bonuses_created=0`.

  **`test_three_competitions_processes_all`**
  - Fake retorna `[1, 2, 3]` en `get_distinct_competition_ids_for_season`.
  - `get_achievements_for_season` retorna `[]` para todas (sin achievements → bonuses=0).
  - El result tiene `competitions_processed=3`, `status="completed"`.

  **`test_result_is_frozen_dataclass`**
  - El result retornado no es mutable (intentar `result.season = "x"` lanza `FrozenInstanceError`).

  **`test_invalid_rules_version_returns_completed_gracefully`**
  - `get_version_by_id` retorna `None` → `CalculateAchievementBonusesUseCase` retorna
    `status="failed"` → el UC orquestador loguea error pero continúa y retorna `status="completed"`.

  **Criterio de completitud:** `pytest tests/use_cases/test_run_all_achievement_bonuses.py -v`
  pasa todos los tests.

---

### 10. Verificación final

- [ ] `pytest tests/` pasa sin errores nuevos.
- [ ] `flake8 src/ tests/` sin errores nuevos (max-line-length=120).
- [ ] `isort --check-only src/ tests/` sin errores.
- [ ] Smoke test manual:
  ```
  POST /api/v1/scoring/recalculate-full
  { "rules_version_id": 1, "season": "2024", "force_recalculate": false }
  → 202 { task_id: "...", status: "queued" }

  GET /api/v1/scoring/recalculate-full/{task_id}/status
  → { phase: "scoring"|"achievements"|"done", pct: N }
  ```

---

## Agent Routing Brief

**DDD Designer needed:** No. No se crean nuevas entidades de dominio. El cambio es:
- Un nuevo método en un Port Protocol existente (`PlayerEventScoreRepositoryPort`).
- Un nuevo use case orquestador que reutiliza use cases existentes.
- Un nuevo Celery task.
- Dos endpoints nuevos.

| Item | Skill a usar |
|---|---|
| Paso 1-2 (Port + Repository) | `/sfa-repository` |
| Paso 3 (RunAllAchievementBonusesUseCase) | `/sfa-use-case` |
| Paso 4 (Celery task) | `/sfa-celery-task` |
| Paso 5-6 (Schemas + Router) | `/sfa-router` |
| Paso 7 (Wiring) | `/sfa-use-case` (sección wiring) |
| Paso 9 (Tests) | `/sfa-test` |
