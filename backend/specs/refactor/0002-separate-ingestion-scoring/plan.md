# Plan: Separación de Ingestion y Scoring como flujos independientes

## Archivos a crear

- [ ] `src/sfa/application/use_cases/calculate_competition_scores.py` — use case de scoring para una competition específica; lee `player_events` de DB y upserta `sfa_season_scores`
- [ ] `src/sfa/application/use_cases/calculate_all_scores.py` — use case orquestador que itera todas las competitions con fixtures en esa season y llama al anterior
- [ ] `src/sfa/infrastructure/repositories/scoring_repository.py` — `ScoringRepository` implementando `ScoringRepositoryPort`; contiene las queries de agregación SQL
- [ ] `src/sfa/tasks/scoring_tasks.py` — Celery tasks `calculate_competition_scores_task` y `calculate_all_scores_task` con helpers async y late imports
- [ ] `tests/use_cases/test_calculate_competition_scores.py` — tests del use case de scoring con `FakeScoringRepository`

## Archivos a modificar

- [ ] `src/sfa/domain/ingestion_ports.py` — agregar `PlayerSeasonScoreRow` DTO y `ScoringRepositoryPort` Protocol
- [ ] `src/sfa/application/use_cases/ingest_competition.py` — eliminar Fase 4, `_PlayerAccum`, `_reconcile_breakdown_counts`, `player_accum` dict, y el contador `players_processed`
- [ ] `src/sfa/infrastructure/repositories/__init__.py` — exportar `ScoringRepository`
- [ ] `src/sfa/core/dependencies.py` — agregar factories `get_scoring_repository`, `get_calculate_competition_scores_use_case`, `get_calculate_all_scores_use_case`
- [ ] `src/sfa/tasks/ingestion_tasks.py` — en `_run_ingest_all`, después del `await session.commit()`, llamar `calculate_all_scores_task.delay(season)` con late import

## Checklist de implementación

### Paso 1 — Agregar `PlayerSeasonScoreRow` DTO y `ScoringRepositoryPort` en `domain/ingestion_ports.py`

- [ ] Agregar dataclass frozen `PlayerSeasonScoreRow` con campos:
  `player_id: int`, `total_pts: float`, `matches_played: int`,
  `breakdown: dict`, `total_minutes: int`
- [ ] Agregar `@runtime_checkable class ScoringRepositoryPort(Protocol)` con tres métodos:
  - `async def get_competition_ids_with_season(self, season: str) -> list[int]`
  - `async def get_player_scores_for_competition(self, competition_id: int, season: str) -> list[PlayerSeasonScoreRow]`
  - `async def upsert_season_score(self, player_id: int, competition_id: int, season: str, total_pts: float, matches_played: int, breakdown: dict) -> None`
- [ ] Criterio: el Protocol es `@runtime_checkable` y `ScoringRepository` lo satisface en tiempo de ejecución

### Paso 2 — Crear `ScoringRepository` en `infrastructure/repositories/scoring_repository.py`

- [ ] Implementar `get_competition_ids_with_season(season)`:
  `SELECT DISTINCT competition_id FROM fixtures WHERE season = :season`
- [ ] Implementar `get_player_scores_for_competition(competition_id, season)`:
  - JOIN `player_events` → `fixtures` → `player_stats` (LEFT OUTER JOIN en `player_stats`)
  - WHERE `fixtures.competition_id = :competition_id AND fixtures.season = :season`
  - GROUP BY `player_events.player_id, player_events.event_type` para construir el breakdown como dict `{event_type.value: {"count": n, "pts": x}}`
  - En una segunda query (o subquery), sumar `player_stats.minutes` por jugador para `total_minutes`
  - `matches_played` = `COUNT(DISTINCT fixture_id)` WHERE `player_stats.minutes >= 1`
  - Retornar `list[PlayerSeasonScoreRow]`
- [ ] Implementar `upsert_season_score`: mismo pattern `pg_insert(...).on_conflict_do_update(constraint="uq_sfa_season_score", ...)` con `last_updated = datetime.now(timezone.utc)`
- [ ] Criterio: la clase pasa `isinstance(repo, ScoringRepositoryPort)` en tiempo de ejecución

### Paso 3 — Crear `CalculateCompetitionScoresUseCase`

- [ ] Archivo: `src/sfa/application/use_cases/calculate_competition_scores.py`
- [ ] Dataclass frozen `CalculateScoresResult` con campos: `competition_id: int`, `season: str`, `players_scored: int`, `status: str`, `error: str | None`
- [ ] Clase `CalculateCompetitionScoresUseCase` con `__init__(self, repo: ScoringRepositoryPort)`
- [ ] Método `async execute(self, competition_id: int, season: str) -> CalculateScoresResult`:
  1. Llama `repo.get_player_scores_for_competition(competition_id, season)`
  2. Filtra jugadores con `total_minutes < 90` (excluir)
  3. Para los jugadores que pasan el filtro, calcula `pct` en cada breakdown key:
     `pct = round(breakdown[key]["pts"] / total_pts * 100, 1) if total_pts > 0 else 0.0`
  4. Llama `repo.upsert_season_score(...)` por cada jugador
  5. Retorna `CalculateScoresResult` con `players_scored`, `status="completed"`, `error=None`
- [ ] Maneja excepción genérica: loguea y retorna `status="failed"`, `error=str(exc)`
- [ ] No importa nada de `infrastructure/` — solo `domain/`
- [ ] Criterio: el use case existe, tiene `CalculateScoresResult` como tipo de retorno y no importa SQLAlchemy

### Paso 4 — Crear `CalculateAllScoresUseCase`

- [ ] Archivo: `src/sfa/application/use_cases/calculate_all_scores.py`
- [ ] Clase `CalculateAllScoresUseCase` con `__init__(self, repo: ScoringRepositoryPort)`
- [ ] Método `async execute(self, season: str) -> list[CalculateScoresResult]`:
  1. Llama `repo.get_competition_ids_with_season(season)`
  2. Para cada `competition_id`, instancia y ejecuta `CalculateCompetitionScoresUseCase(self._repo).execute(competition_id, season)`
  3. Acumula y retorna todos los resultados
- [ ] Criterio: el use case existe y puede recibir una lista vacía de competitions sin error

### Paso 5 — Eliminar Fase 4 de `IngestCompetitionUseCase`

- [ ] Eliminar dataclass `_PlayerAccum` (líneas 76-83 aprox)
- [ ] Eliminar función `_reconcile_breakdown_counts` (líneas 112-133 aprox)
- [ ] Eliminar inicialización de `player_accum: dict[int, _PlayerAccum] = {}` en `execute()`
- [ ] Eliminar todas las referencias a `accum` y `player_accum` dentro del loop de Phase 3
  (acumulación `accum.matches_played`, `accum.real_goals`, `accum.real_assists`, `accum.total_minutes`,
  `accum.total_pts`, `_add_to_breakdown(accum.breakdown, ...)`)
- [ ] Eliminar el bloque completo "Phase 4: Season scores" (el `for player_db_id, accum in player_accum.items()` con el `upsert_season_score`)
- [ ] Eliminar `players_processed` del método `execute()` y de `IngestionResult` **solo si no se usa en ningún otro lugar**; si se mantiene `IngestionResult`, dejar el campo con valor `0` fijo o eliminarlo
- [ ] Criterio: `IngestCompetitionUseCase.execute()` ya no importa ni escribe en `sfa_season_scores`; los tests de ingestion existentes siguen pasando

### Paso 6 — Crear `tasks/scoring_tasks.py`

- [ ] Archivo: `src/sfa/tasks/scoring_tasks.py`
- [ ] Task `calculate_competition_scores_task(self, competition_id: int, season: int)`:
  `@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)`
  llama `asyncio.run(_run_calculate_competition_scores(competition_id, season))` con retry en excepción
- [ ] Task `calculate_all_scores_task(self, season: int)`:
  `@celery_app.task(bind=True, max_retries=1)`
  llama `asyncio.run(_run_calculate_all_scores(season))` con retry en excepción
- [ ] Helper `_run_calculate_competition_scores(competition_id, season)` con late imports:
  importa `CalculateCompetitionScoresUseCase`, `ScoringRepository`, `AsyncSessionLocal`;
  abre sesión, ejecuta use case, commit
- [ ] Helper `_run_calculate_all_scores(season)` con late imports:
  importa `CalculateAllScoresUseCase`, `ScoringRepository`, `AsyncSessionLocal`;
  abre sesión, ejecuta use case, commit
- [ ] Criterio: los tasks se pueden importar desde `sfa.tasks.scoring_tasks` sin error de imports

### Paso 7 — Actualizar `tasks/ingestion_tasks.py`

- [ ] En `_run_ingest_all`, después de `await session.commit()`, agregar late import y llamada:
  ```
  from sfa.tasks.scoring_tasks import calculate_all_scores_task
  calculate_all_scores_task.delay(season)
  ```
- [ ] El late import va dentro del helper `_run_ingest_all`, no en el nivel superior del módulo
- [ ] Criterio: cuando `ingest_all_competitions_task` se ejecuta, encola automáticamente `calculate_all_scores_task`

### Paso 8 — Exportar `ScoringRepository` en `infrastructure/repositories/__init__.py`

- [ ] Agregar `from .scoring_repository import ScoringRepository` al `__init__.py`
- [ ] Agregar `"ScoringRepository"` al `__all__`
- [ ] Criterio: `from sfa.infrastructure.repositories import ScoringRepository` funciona sin error

### Paso 9 — Agregar factories en `core/dependencies.py`

- [ ] Importar `ScoringRepository` desde `sfa.infrastructure.repositories`
- [ ] Importar `CalculateCompetitionScoresUseCase` y `CalculateAllScoresUseCase`
- [ ] Agregar factory `get_scoring_repository(db: Annotated[AsyncSession, Depends(get_db)]) -> ScoringRepository`
- [ ] Agregar factory `get_calculate_competition_scores_use_case(repo: Annotated[ScoringRepository, Depends(get_scoring_repository)]) -> CalculateCompetitionScoresUseCase`
- [ ] Agregar factory `get_calculate_all_scores_use_case(repo: Annotated[ScoringRepository, Depends(get_scoring_repository)]) -> CalculateAllScoresUseCase`
- [ ] Criterio: las factories están disponibles para inyección en futuros routers; no hay imports circulares

### Paso 10 — Escribir tests en `tests/use_cases/test_calculate_competition_scores.py`

- [ ] Implementar `FakeScoringRepository(ScoringRepositoryPort)` que cubra los 3 métodos del protocol
  (almacena resultados en atributos de instancia para assertions)
- [ ] `test_no_players_returns_empty_result`: competición sin jugadores → `players_scored == 0`, `status == "completed"`
- [ ] `test_player_below_90_min_threshold_excluded`: jugador con `total_minutes = 45` → no aparece en `upserted`
- [ ] `test_player_above_threshold_gets_upserted_with_breakdown`: jugador con `total_minutes = 180` y `breakdown` → `upsert_season_score` llamado 1 vez con los valores correctos
- [ ] `test_breakdown_pct_calculated_correctly`: verificar que el campo `pct` en cada breakdown key es `round(pts / total_pts * 100, 1)`
- [ ] Todos los tests llevan `@pytest.mark.anyio`
- [ ] Criterio: `pytest tests/use_cases/test_calculate_competition_scores.py` pasa sin errores

### Paso 11 — Verificación final

- [ ] Verificar `pytest tests/` pasa con coverage ≥ 80%
- [ ] Verificar `flake8 src/ tests/` sin errores (max-line-length 120)
- [ ] Verificar `isort --check-only src/ tests/` sin errores

## Agent Routing Brief

**DDD Designer needed:** no

Este refactor no introduce nuevas entidades de dominio, value objects ni aggregates. El
`PlayerSeasonScoreRow` es un DTO de lectura simple (frozen dataclass) sin invariantes de negocio.
El `ScoringRepositoryPort` es un Port (Protocol) de infraestructura, no un concepto de dominio
nuevo. La lógica de scoring (multiplicadores, BASE_POINTS_TABLE) ya existe en `domain/scoring/`
y no se modifica.

## Verificación

1. Ejecutar `calculate_all_scores_task.delay(2024)` via Celery shell y verificar que
   `sfa_season_scores` se actualiza sin ninguna llamada a API-Football
   (confirmar con `SELECT COUNT(*) FROM sfa_season_scores WHERE season = '2024'` antes y después)
2. Modificar un peso en `BASE_POINTS_TABLE` (e.g., subir `ActionType.GOAL` de FW de 500 a 600),
   ejecutar `calculate_all_scores_task.delay(2024)` y verificar que los `total_pts` cambian
   en `sfa_season_scores` **sin** ningún request a API-Football en los logs
3. Ejecutar `ingest_all_competitions_task.delay(2024)` y verificar que en los logs aparece
   el encolado automático de `calculate_all_scores_task` después del commit
4. Verificar que `IngestCompetitionUseCase.execute()` ya no escribe en `sfa_season_scores`
   ejecutando una ingestion de una sola liga y comprobando que el count en `sfa_season_scores`
   no cambia hasta que corre el scoring task por separado
5. `pytest tests/` pasa con coverage ≥ 80% y sin regresiones en tests existentes
