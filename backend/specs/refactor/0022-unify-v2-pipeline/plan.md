# Plan: Unificar pipeline scoring v2: eliminar v1 legacy, auto-trigger post-ingestion con versión activa

## Archivos a modificar

- [ ] `src/sfa/application/use_cases/ingest_competition.py` — eliminar scoring inline, `_v1_group`, `_V2_TO_V1_GROUP`, `SFAScoringService` del constructor, imports de scoring
- [ ] `src/sfa/tasks/ingestion_tasks.py` — eliminar construcción de `SFAScoringService`; reemplazar post-ingestion trigger por `run_full_recalculation_task` con versión activa
- [ ] `src/sfa/application/use_cases/calculate_scores_for_rules_version.py` — eliminar `_resolve_group()`, reemplazar usos por acceso directo con manejo de `KeyError`
- [ ] `src/sfa/tasks/scoring_tasks.py` — agregar docstring DEPRECATED en `calculate_all_scores_task` y `calculate_competition_scores_task`

## Archivos a crear

- [ ] `alembic/versions/<hash>_activate_scoring_rules_v2.py` — migración que activa `is_active=TRUE` en `id=3`

## Checklist de implementación

### Fase 1: Eliminar scoring inline de IngestCompetitionUseCase

- [ ] **1.1** `src/sfa/application/use_cases/ingest_competition.py` — eliminar dict `_V2_TO_V1_GROUP` y función `_v1_group()` (bloque completo líneas 84-99).

- [ ] **1.2** `src/sfa/application/use_cases/ingest_competition.py` — eliminar del bloque `from sfa.domain.scoring.services import ...` los imports `BASE_POINTS_TABLE` y `SFAScoringService`; eliminar completamente el bloque `from sfa.domain.scoring.value_objects import ...` que importa `CombinedMultiplier`, `M1RivalDifficulty`, `M2CompetitionStage`, `M3MinuteScore`, `M4ShotDifficulty`, `MvisitFactor`, `SFAScore`. Conservar `position_to_group` y `ActionType` si se siguen usando para el evento crudo STATS.

- [ ] **1.3** `src/sfa/application/use_cases/ingest_competition.py` — eliminar el parámetro `scoring: SFAScoringService` del método `__init__` de `IngestCompetitionUseCase` y el campo `self._scoring`.

- [ ] **1.4** `src/sfa/application/use_cases/ingest_competition.py` — en el loop de `player_stats_list`, eliminar el bloque completo "Match stats" que construye `stats_for_scoring`, llama a `self._scoring.score_match_stats(...)`, calcula `stats_pts` y construye el `upsert_player_event` con pts calculados. Reemplazar por un `upsert_player_event` minimal con `pts=0.0` para el evento STATS crudo, manteniendo `m1=m1_value` (calculado de `M1RivalDifficulty`) si se desea preservar el context, o simplificando todos los multiplicadores a `1.0`. **Decisión**: escribir `pts=0.0` y mantener `m1` para contexto de recálculo; `m2=1.0`, `m3=1.0`, `m4=1.0`, `mvisit=1.0`.

- [ ] **1.5** `src/sfa/application/use_cases/ingest_competition.py` — en `_process_event()`, eliminar el cálculo de `base_pts`, la construcción de objetos `M1RivalDifficulty`, `M2CompetitionStage`, `M3MinuteScore`, `M4ShotDifficulty`, `MvisitFactor`, `CombinedMultiplier`, `SFAScore`. El método pasa a llamar `upsert_player_event` con `pts=0.0` y multiplicadores como `None` o `1.0`. Mantener los campos de contexto (`score_before_str`, `score_diff`, `db_minute`, `event_type`, `player_team_pos`, `rival_team_pos`, `is_away`) que el pipeline v2 necesita para el recálculo.

- [ ] **1.6** Verificar que `_process_event()` ya no referencia nada de `domain/scoring/value_objects` excepto posiblemente `ActionType` para determinar `event_type`. Si `ActionType` se usa solo para comparaciones internas, puede conservarse o moverse a una constante local.

- [ ] **1.7** Correr `flake8 src/sfa/application/use_cases/ingest_competition.py` y resolver imports no usados.

### Fase 2: Actualizar tasks de ingestion

- [ ] **2.1** `src/sfa/tasks/ingestion_tasks.py`, función `_run_ingest_competition`:
  - Eliminar la importación y construcción de `SFAScoringService` y `scoring`.
  - Actualizar la construcción: `IngestCompetitionUseCase(provider, repo)` (sin `scoring`).

- [ ] **2.2** `src/sfa/tasks/ingestion_tasks.py`, función `_run_ingest_all`:
  - Eliminar la importación y construcción de `SFAScoringService` y `scoring`.
  - Actualizar la construcción: `IngestCompetitionUseCase(provider, repo)` (sin `scoring`).
  - Reemplazar al final del helper:
    ```python
    from sfa.tasks.scoring_tasks import calculate_all_scores_task
    calculate_all_scores_task.delay(season)
    ```
    por:
    ```python
    from sfa.infrastructure.repositories.scoring_rules_version_repository import ScoringRulesVersionRepository
    async with AsyncSessionLocal() as _ver_session:
        active_version = await ScoringRulesVersionRepository(_ver_session).get_active_version()
    if active_version is None:
        logger.error("[_run_ingest_all] No active scoring rules version found — skipping recalculation")
    else:
        from sfa.tasks.run_full_recalculation_task import run_full_recalculation_task
        run_full_recalculation_task.delay(
            rules_version_id=active_version.id,
            season=str(season),
            force_recalculate=True,
        )
    ```

- [ ] **2.3** `src/sfa/tasks/ingestion_tasks.py`, función `_run_ingest_competition`:
  - Agregar al final (después del trigger de ELO) el mismo bloque de trigger de `run_full_recalculation_task` con versión activa (igual que 2.2).
  - Criterio: tanto ingestion individual como bulk disparan el recálculo v2 al terminar.

- [ ] **2.4** Correr `flake8 src/sfa/tasks/ingestion_tasks.py` y resolver imports no usados.

### Fase 3: Eliminar `_resolve_group` de CalculateScoresForRulesVersionUseCase

- [ ] **3.1** `src/sfa/application/use_cases/calculate_scores_for_rules_version.py` — eliminar la función `_resolve_group()` (líneas 57-61 aprox.).

- [ ] **3.2** En `_score_individual_event()`, reemplazar:
  ```python
  base = float(config.base_points[_resolve_group(config, group)][action])
  ```
  por:
  ```python
  try:
      base = float(config.base_points[group][action])
  except KeyError:
      logger.warning(
          "[CalculateScoresForRulesVersionUseCase] No base_points entry for group=%r action=%r "
          "in rules_version_id=%d — skipping event_id=%d",
          group, action, rules_version_id, event.event_id,
      )
      return None
  ```

- [ ] **3.3** En `_score_stats_event()`, reemplazar:
  ```python
  resolved_group = _resolve_group(config, group)
  ```
  por `resolved_group = group`, y envolver el acceso a `config.base_points[resolved_group]` en un bloque `try/except KeyError` que loguee warning y retorne `None`.

- [ ] **3.4** Correr `flake8 src/sfa/application/use_cases/calculate_scores_for_rules_version.py` y resolver imports no usados (si `_resolve_group` era la única referencia a algún import).

### Fase 4: Deprecar pipeline viejo

- [ ] **4.1** `src/sfa/tasks/scoring_tasks.py` — agregar al principio del docstring de `calculate_all_scores_task`:
  `DEPRECATED: use run_full_recalculation_task instead. This task uses the legacy pipeline without rules_version_id.`

- [ ] **4.2** `src/sfa/tasks/scoring_tasks.py` — agregar el mismo aviso DEPRECATED en `calculate_competition_scores_task`.

- [ ] **4.3** `src/sfa/api/v1/admin.py` — verificar que `recalculate_task` importado de `enrichment_tasks` es exclusivamente enrich (FBref/Understat), no scoring. Confirmar que el endpoint `/admin/recalculate/{competition_id}` no toca `sfa_season_scores`. Si solo hace enrich: agregar comentario `# enrich-only: does NOT recalculate SFA scores`. Si hace scoring: reemplazar por `run_full_recalculation_task`.

### Fase 5: Migración Alembic — activar v2 de forma persistente

- [ ] **5.1** Generar migración con:
  ```
  alembic revision -m "activate_scoring_rules_v2"
  ```
  En `upgrade()`:
  ```python
  op.execute("UPDATE scoring_rules_versions SET is_active = FALSE")
  op.execute("UPDATE scoring_rules_versions SET is_active = TRUE WHERE id = 3")
  ```
  En `downgrade()`:
  ```python
  op.execute("UPDATE scoring_rules_versions SET is_active = FALSE WHERE id = 3")
  op.execute("UPDATE scoring_rules_versions SET is_active = TRUE WHERE id = 2")
  ```

- [ ] **5.2** Ejecutar `alembic upgrade head` y verificar:
  ```sql
  SELECT id, name, version, is_active FROM scoring_rules_versions ORDER BY id;
  ```
  Resultado esperado: `id=3` tiene `is_active=true`; todos los demás tienen `is_active=false`.

### Fase 6: Tests

- [ ] **6.1** Correr suite completa antes de escribir tests nuevos y documentar fallos preexistentes:
  ```
  pytest tests/ -x --tb=short
  ```

- [ ] **6.2** `tests/use_cases/test_ingest_competition.py` — crear o actualizar:
  - `FakeIngestionRepository` implementa `IngestionRepositoryPort` completo (todos los métodos del Protocol).
  - Test `test_execute_stores_raw_events_with_zero_pts`: después de `execute()`, los `PlayerEvent` creados tienen `pts=0.0`, no un valor calculado.
  - Test `test_execute_constructor_does_not_accept_scoring`: `IngestCompetitionUseCase(provider, repo)` se construye sin error; la firma no acepta tercer argumento `scoring`.
  - Usar `@pytest.mark.anyio` en todos los tests async.

- [ ] **6.3** `tests/use_cases/test_calculate_scores_for_rules_version.py` — actualizar:
  - Test `test_mco_position_resolves_correctly_in_v2_config`: un evento con `player_position="MCO"` se scorea usando la entry MCO de `config.base_points`, no la de MF.
  - Test `test_unknown_group_skips_event_with_warning`: un grupo no presente en `config.base_points` resulta en el evento siendo skipped (retorna None), sin excepción.
  - Usar `FakeScoringRulesVersionRepository` y `FakePlayerEventScoreRepository` que implementan sus Protocols completos.

- [ ] **6.4** Correr suite completa tras los cambios y verificar que no hay regresiones:
  ```
  pytest tests/ --tb=short
  ```
  Correr también:
  ```
  flake8 src/ tests/
  isort --check-only src/ tests/
  ```

### Fase 7: Recálculo 2024 y 2025 con v2 (operación one-time)

- [ ] **7.1** Verificar que la versión activa en DB es id=3 (después de la migración Fase 5):
  ```http
  GET /api/v1/scoring/rules-versions
  ```
  Resultado esperado: objeto con `id=3` tiene `"is_active": true`.

- [ ] **7.2** Disparar recálculo completo para temporada 2024:
  ```http
  POST /api/v1/scoring/recalculate-full
  Content-Type: application/json

  {"rules_version_id": 3, "season": "2024", "force_recalculate": true}
  ```
  Guardar `task_id` del response y monitorear en logs de Celery hasta `status=completed`.

- [ ] **7.3** Disparar recálculo completo para temporada 2025:
  ```http
  POST /api/v1/scoring/recalculate-full
  Content-Type: application/json

  {"rules_version_id": 3, "season": "2025", "force_recalculate": true}
  ```
  Monitorear igual que 7.2.

- [ ] **7.4** Verificar ranking frontend con datos reales:
  ```http
  GET /api/v1/ranking?season=2024
  GET /api/v1/ranking?season=2025
  ```
  Criterio: ambos endpoints retornan jugadores con `score > 0` y posiciones MCO/DEL/EXT/LAT/DC reflejadas correctamente.

### Fase 8: Limpieza post-verificación (segunda pasada — después de confirmar Fase 7)

- [ ] **8.1** Auditar dependencias de `CalculateAllScoresUseCase` y `CalculateCompetitionScoresUseCase`:
  - Buscar referencias en tests, routers, tasks.
  - Si no hay referencias activas: eliminar los archivos `calculate_all_scores.py` y `calculate_competition_scores.py`.

- [ ] **8.2** Auditar `calculate_all_scores_task` y `calculate_competition_scores_task` en `scoring_tasks.py`:
  - Si no hay Celery beat schedule ni endpoint HTTP que los llame: eliminar las tasks y el archivo si queda vacío.

- [ ] **8.3** Auditar `ScoringRepository` en `infrastructure/repositories/scoring_repository.py`:
  - Si solo lo usan las use cases eliminadas en 8.1: eliminar el archivo.

---

## Agent Routing Brief

**DDD Designer needed:** no

Este refactor no introduce nuevas entidades de dominio, nuevos value objects ni nuevas reglas
de negocio. Todos los cambios son:
- Eliminación de código legacy (funciones, imports, parámetros de constructor).
- Redirección de un trigger Celery a otro task ya existente.
- Una migración de datos (activar fila en tabla de configuración).
- Tests de los cambios anteriores.

No se modelan nuevos conceptos de fútbol ni se expanden las reglas de scoring.

## Verificación end-to-end

1. Correr `pytest tests/ --tb=short` sin nuevas regresiones.
2. Correr `flake8 src/ tests/` sin errores en los archivos modificados.
3. `GET /api/v1/scoring/rules-versions` retorna `id=3` con `is_active=true`.
4. Disparar `POST /admin/ingest-all?season=2025&force=false` (o cualquier ingestion); verificar en logs de Celery que al terminar se lanza `run_full_recalculation_task` (no `calculate_all_scores_task`).
5. `GET /api/v1/ranking?season=2025` retorna jugadores con `score > 0`.
6. Jugadores con `position_source=transfermarkt` (e.g., MCO) aparecen con su posición preservada y puntuados correctamente bajo v2.
