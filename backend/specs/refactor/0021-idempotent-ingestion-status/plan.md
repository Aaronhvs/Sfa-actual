# Plan: Refactor 0021 — Idempotent Ingestion & Status Visibility

## Archivos a crear

- [x] `src/sfa/application/use_cases/get_ingestion_status.py` — `GetIngestionStatusUseCase`: consulta IngestionLog + fixture counts y devuelve lista de `CompetitionIngestionStatusDTO`, uno por cada entrada de `LEAGUES` para la season solicitada
- [x] `tests/use_cases/test_get_ingestion_status.py` — tests del use case con `FakeIngestionStatusRepository`

## Archivos a modificar

- [x] `src/sfa/domain/ingestion_ports.py` — añadir `IngestionLogRow`, `CompetitionIngestionStatusDTO`; extender `IngestionRepositoryPort` con 3 métodos nuevos
- [x] `src/sfa/infrastructure/repositories/ingestion_repository.py` — implementar los 3 métodos nuevos del port
- [x] `src/sfa/tasks/ingestion_tasks.py` — añadir `force: bool = False` a ambas tasks; añadir pre-check de idempotencia antes de llamar al use case
- [x] `src/sfa/api/v1/admin.py` — implementar `GET /admin/ingestion-status`, corregir `GET /admin/ingestion-logs`, añadir `force` query param a los dos endpoints de ingest
- [x] `src/sfa/core/dependencies.py` — añadir factory `get_ingestion_status_use_case`
- [x] `src/sfa/celery_app.py` — añadir comentario explícito y constante `BEAT_SCHEDULE_DISABLED`

## Checklist de implementación

### Paso 1 — Extender `domain/ingestion_ports.py`

- [x] Añadir frozen dataclass `IngestionLogRow` con campos: `competition_id: int`, `season: str`, `status: IngestionStatus`, `started_at: datetime`, `finished_at: datetime | None`, `error_msg: str | None`
- [x] Añadir frozen dataclass `CompetitionIngestionStatusDTO` con campos: `competition_name: str`, `league_id: int`, `season: str`, `status: str`, `fixtures_in_db: int`, `last_ingested_at: datetime | None`, `error_msg: str | None`
- [x] Añadir al `IngestionRepositoryPort` (Protocol) los tres métodos:
  - `get_last_ingestion_log(self, competition_id: int, season: str) -> IngestionLogRow | None`
  - `get_ingestion_logs_by_season(self, season: str) -> list[IngestionLogRow]`
  - `get_fixture_counts_by_competition(self, season: str) -> dict[int, int]`

### Paso 2 — Implementar métodos en `infrastructure/repositories/ingestion_repository.py`

- [x] `get_last_ingestion_log(competition_id, season)`: query `SELECT ... FROM ingestion_logs WHERE competition_id=? AND season=? ORDER BY started_at DESC LIMIT 1`, retorna `IngestionLogRow | None`
- [x] `get_ingestion_logs_by_season(season)`: query todos los logs de la season ordenados por `competition_id, started_at DESC`, retorna `list[IngestionLogRow]` (un row por cada log existente, sin deduplicar — el use case consolida)
- [x] `get_fixture_counts_by_competition(season)`: `SELECT competition_id, COUNT(*) FROM fixtures WHERE season=? GROUP BY competition_id`, retorna `dict[int, int]`

### Paso 3 — Crear `application/use_cases/get_ingestion_status.py`

- [x] Clase `GetIngestionStatusUseCase` con constructor `__init__(self, repo: IngestionRepositoryPort)`
- [x] Método `execute(self, season: str) -> list[CompetitionIngestionStatusDTO]`
- [x] Lógica interna:
  1. Llamar `repo.get_ingestion_logs_by_season(season)` — obtiene todos los logs existentes
  2. Llamar `repo.get_fixture_counts_by_competition(season)` — obtiene counts de fixtures
  3. Para cada `LeagueConfig` en `LEAGUES` (importado de `ingest_competition.py`):
     - Buscar el competition_id correspondiente en los logs (match por nombre de competición en los logs es indirecto — usar la tabla `competitions` no está disponible en este use case; el repo debe exponer `get_competition_id_by_name` O los logs ya traen `competition_id` que se mapea contra un dict precargado)
     - **Decisión de implementación**: el repo `get_ingestion_logs_by_season` debe también retornar el `competition_name` para poder cruzar con `LEAGUES`. Añadir `competition_name: str` a `IngestionLogRow` (join con `competitions` en el repo).
     - Si no hay log para esa liga: `status="MISSING"`, `fixtures_in_db=0`, `last_ingested_at=None`
     - Si hay log: tomar el más reciente, usar su `status.value.upper()` y `finished_at` como `last_ingested_at`
     - `fixtures_in_db` se toma del dict de counts (default 0 si no aparece)
  4. Retornar lista ordenada: primero por `status` (MISSING primero, luego FAILED, luego RUNNING, luego COMPLETED), luego por `competition_name`

> **Nota**: `IngestionLogRow` debe incluir `competition_name: str` (JOIN con `competitions` en el repo). Actualizar el dataclass en `domain/ingestion_ports.py` y la implementación del repo en consecuencia.

### Paso 4 — Documentar `celery_app.py`

- [x] Añadir constante `BEAT_SCHEDULE_DISABLED: bool = True` antes de la asignación de `beat_schedule`
- [x] Reemplazar el comentario actual por: `# INTENTIONALLY EMPTY — no scheduled tasks. All ingestion triggered via admin API only.`

### Paso 5 — Añadir guard de idempotencia en `tasks/ingestion_tasks.py`

- [x] Añadir `force: bool = False` al decorador y firma de `ingest_competition_task(self, league_id: int, season: int, force: bool = False)`
- [x] Antes de llamar a `_run_ingest_competition`, añadir bloque async que:
  1. Abre `AsyncSessionLocal`
  2. Instancia `IngestionRepository(session)`
  3. Llama `repo.get_last_ingestion_log(competition_id, season_str)` — necesita el `competition_id` que se obtiene de la tabla `competitions` por nombre de liga
  4. Si log existe con `status=COMPLETED` y `force=False`: retorna `{"skipped": True, "reason": "already_completed", "league_id": league_id, "season": season}`
- [x] Para obtener el `competition_id` en la task, añadir helper async `_get_competition_id_by_league(league: LeagueConfig) -> int | None` que hace SELECT sobre `competitions` por nombre
- [x] Aplicar la misma lógica de skip por liga en `_run_ingest_all(season, force)`: iterar `LEAGUES`, verificar cada una, skipear las COMPLETED, continuar con las demás
- [x] Añadir `force: bool = False` a la firma de `ingest_all_competitions_task` y propagarlo a `_run_ingest_all`
- [x] Añadir logging: `logger.info("[ingest_competition_task] Skipping league_id=%s season=%s — already completed", league_id, season)`

### Paso 6 — Actualizar `api/v1/admin.py`

- [x] Añadir `force: bool = Query(default=False)` a `trigger_ingest_competition` y pasarlo a `ingest_competition_task.delay(league_id, season, force)`
- [x] Añadir `force: bool = Query(default=False)` a `trigger_ingest_all` y pasarlo a `ingest_all_competitions_task.delay(season, force)`
- [x] Implementar `GET /admin/ingestion-logs`:
  - Añadir `season: int = Query(default=CURRENT_SEASON)` como parámetro
  - Inyectar `GetIngestionStatusUseCase` vía `Depends(get_ingestion_status_use_case)`
  - Llamar `use_case.execute(str(season))` y retornar la lista serializada
- [x] Añadir `GET /admin/ingestion-status`:
  - Mismo handler que `/ingestion-logs` pero ruta diferente para compatibilidad futura
  - Mismo use case, mismo parámetro `season`
  - Responde con `list[CompetitionIngestionStatusResponseSchema]`
- [x] Crear Pydantic schema `CompetitionIngestionStatusResponseSchema` en `api/v1/schemas/` con los mismos campos que `CompetitionIngestionStatusDTO`

### Paso 7 — Wiring en `core/dependencies.py`

- [x] Añadir import de `GetIngestionStatusUseCase`
- [x] Añadir factory:
  ```python
  async def get_ingestion_status_use_case(
      db: Annotated[AsyncSession, Depends(get_db)],
  ) -> GetIngestionStatusUseCase:
      from sfa.infrastructure.repositories.ingestion_repository import IngestionRepository
      return GetIngestionStatusUseCase(IngestionRepository(db))
  ```

### Paso 8 — Crear archivo `.http`

- [x] Crear `http/ingestion_status.http` con:
  - `GET /admin/ingestion-status?season=2024` — happy path
  - `GET /admin/ingestion-status?season=2025` — temporada sin datos (todo MISSING)
  - `GET /admin/ingestion-logs?season=2024`
  - `POST /admin/ingest/140?season=2024&force=false` — skip si ya existe
  - `POST /admin/ingest/140?season=2024&force=true` — forzar re-ingesta
  - `POST /admin/ingest-all?season=2025&force=false`

### Paso 9 — Tests

- [x] Crear `tests/use_cases/test_get_ingestion_status.py`
- [x] Implementar `FakeIngestionStatusRepository` que implementa el `IngestionRepositoryPort` completo (todos los métodos, los nuevos con datos en memoria)
- [x] Escenario 1: todas las ligas COMPLETED para season=2024 → lista con todos en status COMPLETED
- [x] Escenario 2: una liga FAILED → aparece en el resultado con status FAILED y error_msg
- [x] Escenario 3: liga sin ningún log → aparece con status MISSING, fixtures_in_db=0
- [x] Escenario 4: mix de estados (COMPLETED, FAILED, MISSING) → ordenación correcta (MISSING primero)
- [x] Escenario 5: liga con log RUNNING → aparece como RUNNING

### Paso 10 — Validación final

- [ ] Verificar `pytest tests/` pasa con coverage ≥80%
- [ ] Verificar `flake8 src/ tests/` sin errores
- [ ] Verificar `isort --check-only src/ tests/` sin errores

## Agent Routing Brief

**DDD Designer needed:** no

Este refactor no introduce entidades de dominio con invariantes de negocio. `IngestionLogRow`
y `CompetitionIngestionStatusDTO` son DTOs de lectura (frozen dataclasses) sin reglas de
construcción ni ciclo de vida. El guard de idempotencia es lógica de orquestación en la task,
no una regla de dominio. El repositorio ya existe; solo se extiende con métodos de lectura.

## Verificación

1. Levantar el stack: `docker compose up -d`
2. `GET /admin/ingestion-status?season=2024` → retorna lista de 19 competiciones, cada una con su status real (COMPLETED/FAILED/MISSING) y `fixtures_in_db > 0` para las que tienen datos
3. `GET /admin/ingestion-status?season=2099` → retorna 19 competiciones todas con `status="MISSING"` y `fixtures_in_db=0`
4. `POST /admin/ingest/140?season=2024&force=false` (La Liga, season ya ingestada) → respuesta `{"skipped": true, "reason": "already_completed"}`, sin consumir quota de API
5. `POST /admin/ingest/140?season=2024&force=true` → lanza la ingesta normalmente
6. `GET /admin/ingestion-logs?season=2024` → retorna la misma información que `/ingestion-status` (mismo use case)
7. Verificar en logs de Celery worker que aparece `[ingest_competition_task] Skipping league_id=140 season=2024 — already completed`
