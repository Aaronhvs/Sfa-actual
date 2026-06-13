# Plan: Versioned Scoring Rules & Raw-Event Recalculation

## Archivos a crear

- [ ] `src/sfa/domain/scoring_ports.py` — Protocols + DTOs para repositorios de scoring versionado
- [ ] `src/sfa/infrastructure/models/scoring_rules/__init__.py`
- [ ] `src/sfa/infrastructure/models/scoring_rules/models.py` — `ScoringRulesVersionModel`
- [ ] `src/sfa/infrastructure/models/player_event_scores/__init__.py`
- [ ] `src/sfa/infrastructure/models/player_event_scores/models.py` — `PlayerEventScoreModel`
- [ ] `src/sfa/infrastructure/repositories/scoring_rules_version_repository.py`
- [ ] `src/sfa/infrastructure/repositories/player_event_score_repository.py`
- [ ] `src/sfa/application/use_cases/calculate_scores_for_rules_version.py`
- [ ] `src/sfa/application/use_cases/manage_scoring_rules_version.py`
- [ ] `src/sfa/api/v1/schemas/scoring_rules_schemas.py`
- [ ] `src/sfa/api/v1/scoring_rules_router.py`
- [ ] `src/sfa/tasks/calculate_scores_for_rules_version_task.py`
- [ ] `http/scoring_rules.http`
- [ ] `tests/use_cases/test_calculate_scores_for_rules_version.py`
- [ ] `tests/use_cases/test_manage_scoring_rules_version.py`
- [ ] `tests/domain/test_scoring_config.py`

## Archivos a modificar

- [ ] `src/sfa/domain/scoring/value_objects.py` — agregar `ScoringConfig`
- [ ] `src/sfa/domain/scoring/entities.py` — agregar `ScoringRulesVersion`, `PlayerEventScore`
- [ ] `src/sfa/domain/scoring/services.py` — `SFAScoringService` acepta `ScoringConfig` opcional
- [ ] `src/sfa/domain/ingestion_ports.py` — agregar `player_team_pos`, `rival_team_pos`, `is_away` a `upsert_player_event` en `IngestionRepositoryPort`
- [ ] `src/sfa/infrastructure/models/events/models.py` — agregar columnas `player_team_pos`, `rival_team_pos`, `is_away`
- [ ] `src/sfa/infrastructure/models/scores/models.py` — agregar `rules_version_id`, reemplazar UniqueConstraint por partial indexes
- [ ] `src/sfa/infrastructure/models/__init__.py` — exportar nuevos modelos
- [ ] `src/sfa/infrastructure/repositories/__init__.py` — exportar nuevos repositorios
- [ ] `src/sfa/infrastructure/repositories/ingestion_repository.py` — pasar nuevos campos en `upsert_player_event`
- [ ] `src/sfa/infrastructure/repositories/scoring_repository.py` — `upsert_season_score` acepta `rules_version_id`
- [ ] `src/sfa/infrastructure/repositories/sfa_score_repository.py` — queries de ranking filtran por `rules_version_id`
- [ ] `src/sfa/application/use_cases/get_ranking.py` — aceptar `rules_version_id` opcional
- [ ] `src/sfa/application/use_cases/ingest_competition.py` — pasar `player_team_pos`, `rival_team_pos`, `is_away` en `upsert_player_event`
- [ ] `src/sfa/core/dependencies.py` — wiring de nuevos repos y use cases
- [ ] `src/sfa/main.py` — registrar `scoring_rules_router`

## Checklist de implementación

### Fase 1: Domain — Value Objects y Entidades [DDD]

- [ ] **[DDD] 1.1** Agregar `ScoringConfig` a `domain/scoring/value_objects.py`
  - Frozen dataclass con todos los parámetros configurables del scoring
  - Factory `ScoringConfig.default() -> ScoringConfig` — construye desde valores actuales de `BASE_POINTS_TABLE` y los value objects M1–Mrating
  - Factory `ScoringConfig.from_dict(d: dict) -> ScoringConfig` — deserializa desde `config_json` de DB; lanza `ValueError` si datos inválidos
  - Método `ScoringConfig.to_dict() -> dict` — serializa para guardar en `config_json`
  - Invariantes: `m1_clamp[0] < m1_clamp[1]`, `m1_divisor > 0`, `mvisit_bonus >= 1.0`, `mrating_thresholds` en orden creciente de threshold, `combined_clamp[0] < combined_clamp[1]`, `base_points` no vacío

- [ ] **[DDD] 1.2** Agregar `ScoringRulesVersion` a `domain/scoring/entities.py`
  - Frozen dataclass: `id`, `name`, `version`, `description`, `is_active`, `config: ScoringConfig`, `created_at`
  - Sin métodos de mutación; inmutable por diseño

- [ ] **[DDD] 1.3** Agregar `PlayerEventScore` a `domain/scoring/entities.py`
  - Frozen dataclass con todos los campos del resultado de cálculo (ver D3 en decisions.md)
  - Incluye `calculation_details: dict` para trazabilidad completa

- [ ] 1.4 Modificar `SFAScoringService` en `domain/scoring/services.py`
  - `__init__(self, config: ScoringConfig | None = None)` — si `None` usa `ScoringConfig.default()`
  - Reemplazar todas las referencias a `BASE_POINTS_TABLE` (módulo global) por `self._config.base_points`
  - Mantener `BASE_POINTS_TABLE` como constante pública en el módulo (backward-compat)
  - Aplicar los clamps y thresholds desde `self._config` en lugar de hardcodeados

### Fase 2: Infrastructure — Modelos SQLAlchemy

- [ ] 2.1 Crear `infrastructure/models/scoring_rules/models.py`
  - `ScoringRulesVersionModel`: tabla `scoring_rules_versions`
  - Columnas: `id`, `name` (unique), `version`, `description`, `is_active`, `config_json` (JSONB), `created_at`

- [ ] 2.2 Crear `infrastructure/models/scoring_rules/__init__.py`

- [ ] 2.3 Crear `infrastructure/models/player_event_scores/models.py`
  - `PlayerEventScoreModel`: tabla `player_event_scores`
  - FKs: `event_id → player_events.id ON DELETE CASCADE`, `player_id → players.id`, `fixture_id → fixtures.id`, `competition_id → competitions.id`, `rules_version_id → scoring_rules_versions.id`
  - UniqueConstraint: `(event_id, rules_version_id)`
  - Índices: `ix_pes_player_season (player_id, season, rules_version_id)`, `ix_pes_competition (competition_id, season, rules_version_id)`

- [ ] 2.4 Crear `infrastructure/models/player_event_scores/__init__.py`

- [ ] 2.5 Actualizar `infrastructure/models/__init__.py`
  - Importar y exportar `ScoringRulesVersionModel`, `PlayerEventScoreModel`

- [ ] 2.6 Modificar `infrastructure/models/events/models.py`
  - Agregar columnas nullable: `player_team_pos` (SmallInteger), `rival_team_pos` (SmallInteger), `is_away` (Boolean)

- [ ] 2.7 Modificar `infrastructure/models/scores/models.py`
  - Agregar columna: `rules_version_id` (Integer nullable, FK a `scoring_rules_versions.id`)
  - Eliminar `UniqueConstraint("player_id", "competition_id", "season", name="uq_sfa_season_score")`
  - Nota: los partial indexes SQL (`uq_sfa_season_score_legacy` y `uq_sfa_season_score_versioned`) se crean en la migración, no como `__table_args__` de SQLAlchemy (SQLAlchemy no soporta partial unique indexes nativamente en `__table_args__`)

- [ ] 2.8 Crear script de migración SQL `migrations/0012_versioned_scoring_rules.sql`
  - Verificar si existe directorio `alembic/` en `backend/`; si hay Alembic: crear revisión Alembic en su lugar
  - Incluir: ALTER TABLE player_events (3 columnas), CREATE TABLE scoring_rules_versions, CREATE TABLE player_event_scores, ALTER TABLE sfa_season_scores, DROP CONSTRAINT uq_sfa_season_score, CREATE UNIQUE INDEX para legacy y versioned, CREATE UNIQUE INDEX uq_scoring_rules_active

### Fase 3: Domain Ports

- [ ] 3.1 Crear `domain/scoring_ports.py`
  - `PlayerEventRawContextDTO` (frozen dataclass) — campos: `event_id`, `player_id`, `fixture_id`, `competition_id`, `season`, `event_type`, `minute`, `score_diff`, `psxg`, `player_team_pos`, `rival_team_pos`, `is_away`, `stage_factor`, más todos los campos de PlayerStats para eventos STATS (`goals`, `assists`, `shots_on`, `passes_total`, `passes_accuracy`, `dribbles_won`, `duels_won`, `tackles_won`, `interceptions`, `blocks`, `fouls_drawn`, `fouls_committed`, `cards_yellow`, `cards_red`, `penalty_won`, `dribbles_past`, `rating`)
  - `ScoringRulesVersionRepositoryPort` (Protocol, `@runtime_checkable`):
    - `get_active_version() -> ScoringRulesVersion | None`
    - `get_version_by_id(version_id: int) -> ScoringRulesVersion | None`
    - `list_versions() -> list[ScoringRulesVersion]`
    - `save_version(name: str, version: str, description: str, config: ScoringConfig) -> int`
    - `set_active_version(version_id: int) -> None` — desactiva todas las demás en la misma transacción
  - `PlayerEventScoreRepositoryPort` (Protocol, `@runtime_checkable`):
    - `get_events_for_recalc(season: str, competition_id: int | None, match_id: int | None, player_id: int | None) -> list[PlayerEventRawContextDTO]`
    - `upsert_event_score(score: PlayerEventScore) -> None`
    - `event_score_exists(event_id: int, rules_version_id: int) -> bool`
    - `delete_event_scores_for_version(rules_version_id: int, season: str, competition_id: int | None) -> None`
    - `get_player_event_totals_for_season(player_id: int, season: str, competition_id: int, rules_version_id: int) -> tuple[float, int]` — (total_pts, matches_played)
    - `get_players_with_events_in_scope(season: str, competition_id: int | None, rules_version_id: int) -> list[int]` — lista de player_ids
    - `get_season_score_breakdown(player_id: int, season: str, competition_id: int, rules_version_id: int) -> dict` — breakdown por action_type para el JSON de `sfa_season_scores`

- [ ] 3.2 Actualizar `domain/ingestion_ports.py`
  - `IngestionRepositoryPort.upsert_player_event`: agregar parámetros opcionales `player_team_pos: int | None = None`, `rival_team_pos: int | None = None`, `is_away: bool | None = None`

### Fase 4: Infrastructure — Repositorios

- [ ] 4.1 Crear `infrastructure/repositories/scoring_rules_version_repository.py`
  - Clase `ScoringRulesVersionRepository` implementando `ScoringRulesVersionRepositoryPort`
  - `get_active_version`: `SELECT ... WHERE is_active = TRUE`
  - `get_version_by_id`: select por PK
  - `list_versions`: `SELECT ... ORDER BY created_at DESC`
  - `save_version`: INSERT retornando id
  - `set_active_version`: UPDATE SET is_active = FALSE WHERE id != version_id; UPDATE SET is_active = TRUE WHERE id = version_id (en transacción)
  - Serialización: `ScoringConfig.to_dict()` → `config_json`; `ScoringConfig.from_dict()` al leer

- [ ] 4.2 Crear `infrastructure/repositories/player_event_score_repository.py`
  - Clase `PlayerEventScoreRepository` implementando `PlayerEventScoreRepositoryPort`
  - `get_events_for_recalc`: JOIN complejo `player_events LEFT JOIN player_stats ON (player_id, fixture_id) JOIN fixtures JOIN competition_stages LEFT JOIN standings_snapshots` para obtener todo el contexto en un solo fetch; fallback `player_team_pos = 10` si standings NULL
  - `upsert_event_score`: pg INSERT ... ON CONFLICT (event_id, rules_version_id) DO UPDATE
  - `event_score_exists`: SELECT EXISTS(...)
  - `get_player_event_totals_for_season`: SUM(final_points), COUNT(DISTINCT fixture_id)
  - `get_season_score_breakdown`: GROUP BY action_type, SUM(final_points), COUNT(*)
  - `get_players_with_events_in_scope`: SELECT DISTINCT player_id filtrado por scope

- [ ] 4.3 Actualizar `infrastructure/repositories/__init__.py`
  - Exportar `ScoringRulesVersionRepository`, `PlayerEventScoreRepository`

- [ ] 4.4 Actualizar `infrastructure/repositories/ingestion_repository.py`
  - `upsert_player_event`: incluir `player_team_pos`, `rival_team_pos`, `is_away` en el INSERT/UPDATE

### Fase 5: Application — Use Cases

- [ ] 5.1 Crear `application/use_cases/calculate_scores_for_rules_version.py`
  - `CalculateScoresForRulesVersionResult(rules_version_id, season, competition_id, events_calculated, players_updated, status, error)`
  - `CalculateScoresForRulesVersionUseCase(rules_version_repo, event_score_repo, scoring_repo)`
  - `execute(rules_version_id, season, competition_id?, match_id?, player_id?, force_recalculate=False)`
  - Flujo según D6 en decisions.md
  - Para cada evento: construir `calculation_details` dict con todos los intermedios
  - Reconstruir `sfa_season_scores` via `scoring_repo.upsert_season_score` pasando `rules_version_id`

- [ ] 5.2 Crear `application/use_cases/manage_scoring_rules_version.py`
  - `CreateScoringRulesVersionResult(version_id, name, version, status, error)`
  - `CreateScoringRulesVersionUseCase(rules_version_repo)` — valida config, llama `save_version`
  - `ActivateScoringRulesVersionResult(version_id, status, error)`
  - `ActivateScoringRulesVersionUseCase(rules_version_repo)` — llama `set_active_version`; error si id inexistente
  - `ListScoringRulesVersionsResult(versions: list[ScoringRulesVersion])`
  - `ListScoringRulesVersionsUseCase(rules_version_repo)` — llama `list_versions`

- [ ] 5.3 Modificar `application/use_cases/get_ranking.py`
  - Agregar `rules_version_id: int | None = None` al método `execute`
  - Pasar al repositorio en la query

- [ ] 5.4 Actualizar `application/use_cases/ingest_competition.py`
  - En `_process_event` y en el bloque de stats: pasar `player_team_pos=player_team_pos`, `rival_team_pos=rival_pos`, `is_away=is_away` a `upsert_player_event`

### Fase 6: Infrastructure — Actualizar Repositorios de Lectura

- [ ] 6.1 Actualizar `infrastructure/repositories/sfa_score_repository.py`
  - Todos los métodos de ranking/query que lean de `sfa_season_scores`: agregar filtro
    `WHERE (sfa_season_scores.rules_version_id = :v)` si `rules_version_id` es not None,
    o `WHERE sfa_season_scores.rules_version_id IS NULL` si es None (legacy)

- [ ] 6.2 Actualizar `infrastructure/repositories/scoring_repository.py`
  - `upsert_season_score`: agregar parámetro `rules_version_id: int | None = None`
  - Incluirlo en INSERT VALUES y en el ON CONFLICT constraint (usar el nombre correcto del índice según si es NULL o no)

### Fase 7: API

- [ ] 7.1 Crear `api/v1/schemas/scoring_rules_schemas.py`
  - `ScoringRulesVersionResponseSchema`: id, name, version, description, is_active, config_json, created_at
  - `CreateScoringRulesVersionRequestSchema`: name, version, description, config_json (dict)
  - `RecalculateRequestSchema`: rules_version_id, season, competition_id (optional), match_id (optional), player_id (optional), force_recalculate (default False)
  - `RecalculateResponseSchema`: task_id, status, message

- [ ] 7.2 Crear `api/v1/scoring_rules_router.py`
  - `GET /api/v1/scoring/rules-versions` → `ListScoringRulesVersionsUseCase`
  - `POST /api/v1/scoring/rules-versions` → `CreateScoringRulesVersionUseCase`
  - `PATCH /api/v1/scoring/rules-versions/{version_id}/activate` → `ActivateScoringRulesVersionUseCase`
  - `POST /api/v1/scoring/recalculate` → lanza `calculate_scores_for_rules_version_task.delay(...)`, devuelve `task_id`
  - Traducción de errores: `ValueError` → 400, id inexistente → 404

- [ ] 7.3 Registrar `scoring_rules_router` en `main.py`

- [ ] 7.4 Actualizar router de ranking existente
  - Agregar query param `rules_version_id: int | None = None`
  - Pasar a `GetRankingUseCase.execute()`

### Fase 8: Celery Task

- [ ] 8.1 Crear `tasks/calculate_scores_for_rules_version_task.py`
  - `calculate_scores_for_rules_version_task(rules_version_id, season, competition_id=None, match_id=None, player_id=None, force_recalculate=False)`
  - Patrón sync→async estándar: `asyncio.run(...)` wrapping `CalculateScoresForRulesVersionUseCase.execute(...)`
  - Late imports para evitar circular imports
  - Log al inicio y al final con resultado

### Fase 9: DI Wiring

- [ ] 9.1 Actualizar `core/dependencies.py`
  - `get_scoring_rules_version_repository(db) -> ScoringRulesVersionRepository`
  - `get_player_event_score_repository(db) -> PlayerEventScoreRepository`
  - `get_calculate_scores_for_rules_version_use_case(rules_version_repo, event_score_repo, scoring_repo) -> CalculateScoresForRulesVersionUseCase`
  - `get_create_scoring_rules_version_use_case(rules_version_repo) -> CreateScoringRulesVersionUseCase`
  - `get_activate_scoring_rules_version_use_case(rules_version_repo) -> ActivateScoringRulesVersionUseCase`
  - `get_list_scoring_rules_versions_use_case(rules_version_repo) -> ListScoringRulesVersionsUseCase`

### Fase 10: HTTP Files

- [ ] 10.1 Crear `http/scoring_rules.http`
  - `GET {{base_url}}/api/v1/scoring/rules-versions` — listar versiones
  - `POST {{base_url}}/api/v1/scoring/rules-versions` con body de config_json completo
  - `PATCH {{base_url}}/api/v1/scoring/rules-versions/1/activate`
  - `POST {{base_url}}/api/v1/scoring/recalculate` con `{"rules_version_id": 1, "season": "2024", "force_recalculate": false}`
  - Error case: versión inexistente → 404
  - Error case: temporada sin eventos → respuesta vacía exitosa

### Fase 11: Tests

- [ ] 11.1 Crear `tests/domain/test_scoring_config.py`
  - `TestScoringConfigInvariants`:
    - `test_invalid_clamp_raises_value_error` — `m1_clamp[0] > m1_clamp[1]` → ValueError
    - `test_invalid_m1_divisor_raises_value_error` — divisor = 0 → ValueError
    - `test_invalid_mvisit_bonus_raises_value_error` — bonus < 1.0 → ValueError
    - `test_unordered_mrating_thresholds_raises_value_error`
  - `TestScoringConfigFactories`:
    - `test_default_produces_same_results_as_hardcoded_base_points_table`
    - `test_from_dict_roundtrip` — `from_dict(to_dict(config)) == config`
    - `test_from_dict_minimal_valid_config`
    - `test_from_dict_invalid_config_raises_value_error`

- [ ] **[sfa-test] 11.2** Crear `tests/use_cases/test_calculate_scores_for_rules_version.py`
  - `FakeScoringRulesVersionRepository(ScoringRulesVersionRepositoryPort)` — implementa Protocol completo
  - `FakePlayerEventScoreRepository(PlayerEventScoreRepositoryPort)` — implementa Protocol completo
  - `FakeScoringRepository(ScoringRepositoryPort)` — implementa Protocol completo
  - `TestCalculateScoresForRulesVersionUseCase`:
    - `test_goal_event_recalculated_with_new_config` — cambia base_points de GOAL, verifica final_points correcto
    - `test_stats_event_recalculated_with_new_config` — cambia base_points de DUELS_WON, verifica total
    - `test_skip_existing_when_force_false` — evento ya calculado, `force_recalculate=False` → no se sobreescribe
    - `test_overwrite_existing_when_force_true` — evento ya calculado, `force_recalculate=True` → se sobreescribe
    - `test_nonexistent_rules_version_raises_value_error`
    - `test_season_scores_rebuilt_after_recalculation` — verifica que `sfa_season_scores` se reconstruye con `rules_version_id`
    - `test_calculation_details_contains_all_intermediates` — verifica keys en `calculation_details`

- [ ] **[sfa-test] 11.3** Crear `tests/use_cases/test_manage_scoring_rules_version.py`
  - `FakeScoringRulesVersionRepository` (mismo que 11.2, compartir en conftest o duplicar)
  - `TestCreateScoringRulesVersionUseCase`:
    - `test_create_valid_version_returns_id`
    - `test_create_version_with_invalid_config_raises_value_error`
  - `TestActivateScoringRulesVersionUseCase`:
    - `test_activate_version_sets_is_active_true`
    - `test_activate_version_deactivates_others`
    - `test_activate_nonexistent_version_raises_value_error`
  - `TestListScoringRulesVersionsUseCase`:
    - `test_list_returns_all_versions_ordered_by_created_at`

- [ ] Verificar `pytest tests/` pasa con coverage ≥80%
- [ ] Verificar `flake8 src/ tests/` sin errores
- [ ] Verificar `isort --check-only src/ tests/` sin errores

## Agent Routing Brief

**DDD Designer needed: yes**

Los ítems 1.1, 1.2 y 1.3 requieren @DDD-Designer porque:

1. **`ScoringConfig` (ítem 1.1)** — Es un value object con invariantes de negocio no triviales
   (clamps, thresholds en orden, divisores positivos) y dos factories (`default()`, `from_dict()`)
   que deben ser correctas para que todo el sistema de recálculo produzca resultados válidos. Un
   error aquí invalida todos los cálculos posteriores. Requiere modelado cuidadoso de las reglas
   del scoring domain.

2. **`ScoringRulesVersion` (ítem 1.2)** — Entidad de dominio con un invariante de negocio
   crítico: no puede haber dos versiones activas simultáneamente. La entidad encapsula el contrato
   entre el dominio y la capa de persistencia para ese invariante.

3. **`PlayerEventScore` (ítem 1.3)** — Aunque es un DTO, pertenece al subdomain de scoring y
   debe diseñarse coherentemente con `ScoringRulesVersion` y `ScoringConfig`. El DDD Designer
   garantiza que la estructura de `calculation_details` sea suficiente para auditoría y que los
   tipos de los campos sean correctos.

Estos tres elementos son la base sobre la que se construyen todos los repositorios y use cases.
Deben completarse antes de iniciar la Fase 2.

## Verificación

1. Crear una versión de reglas:
   ```
   POST /api/v1/scoring/rules-versions
   Body: {"name": "v1.0-test", "version": "1.0.0", "description": "...", "config_json": {...}}
   → 201 con version_id
   ```

2. Activar la versión:
   ```
   PATCH /api/v1/scoring/rules-versions/1/activate
   → 200
   ```

3. Disparar recálculo para una temporada:
   ```
   POST /api/v1/scoring/recalculate
   Body: {"rules_version_id": 1, "season": "2024", "force_recalculate": true}
   → 202 con task_id
   ```

4. Verificar que `player_event_scores` tiene filas con `rules_version_id = 1` y
   `calculation_details` no nulo.

5. Verificar que `sfa_season_scores` tiene filas con `rules_version_id = 1` y que el
   `total_pts` coincide con la suma de `player_event_scores.final_points` del mismo jugador.

6. Verificar que el ranking legacy sigue funcionando:
   ```
   GET /api/v1/ranking?season=2024
   → mismos resultados que antes del refactor (scores con rules_version_id = NULL)
   ```

7. Verificar el ranking de la nueva versión:
   ```
   GET /api/v1/ranking?season=2024&rules_version_id=1
   → ranking calculado con las nuevas reglas
   ```
