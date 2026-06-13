# Plan: Auto-infer competition achievements from fixtures

## Archivos a crear

- [ ] `src/sfa/domain/infer_achievements_ports.py` — Protocol `InferAchievementsRepositoryPort` + DTOs `KnockoutFixtureDTO`, `InferAchievementsResult`, `InferAllAchievementsResult`
- [ ] `src/sfa/application/use_cases/infer_competition_achievements.py` — `InferCompetitionAchievementsUseCase` + `InferAllCompetitionAchievementsUseCase`
- [ ] `src/sfa/infrastructure/repositories/infer_achievements_repository.py` — `InferAchievementsRepository` implementando el Protocol
- [ ] `src/sfa/tasks/infer_competition_achievements_task.py` — Celery task single-competition
- [ ] `src/sfa/tasks/infer_all_competition_achievements_task.py` — Celery task all-competitions
- [ ] `http/infer_achievements.http` — casos happy path + error para ambos endpoints
- [ ] `tests/use_cases/test_infer_competition_achievements.py` — tests con FakeInferAchievementsRepository

## Archivos a modificar

- [ ] `src/sfa/api/v1/scoring_rules_router.py` — añadir endpoints `POST /scoring/infer-achievements` y `POST /scoring/infer-achievements-all`
- [ ] `src/sfa/api/v1/schemas/scoring_rules_schemas.py` — añadir `InferAchievementsRequestSchema`, `InferAchievementsAllRequestSchema`, `InferAchievementsResponseSchema`
- [ ] `src/sfa/core/dependencies.py` — añadir factories `get_infer_achievements_repository`, `get_infer_competition_achievements_use_case`, `get_infer_all_competition_achievements_use_case`
- [ ] `src/sfa/infrastructure/repositories/__init__.py` — exportar `InferAchievementsRepository`
- [ ] `src/sfa/application/use_cases/run_full_recalculation.py` — añadir paso de inferencia antes de achievement bonuses, controlado por flag `infer_achievements: bool`
- [ ] `src/sfa/tasks/run_full_recalculation_task.py` — añadir parámetro `infer_achievements: bool = True` y pasarlo al use case

## Checklist de implementación

### 1. Domain port + DTOs

- [ ] Crear `src/sfa/domain/infer_achievements_ports.py` con:
  - `from __future__ import annotations` en cabecera
  - `KnockoutFixtureDTO(frozen=True)`: `fixture_id: int`, `stage: str`, `home_team_id: int`, `away_team_id: int`
  - `InferAchievementsResult(frozen=True)`: `competition_id: int`, `season: str`, `skipped: bool`, `achievements_upserted: int`, `phases_found: list[str]`
  - `InferAllAchievementsResult(frozen=True)`: `season: str`, `competitions_processed: int`, `competitions_skipped: int`, `total_achievements_upserted: int`
  - `@runtime_checkable class InferAchievementsRepositoryPort(Protocol)` con los 4 métodos definidos en decisions.md

### 2. Use cases

- [ ] Crear `src/sfa/application/use_cases/infer_competition_achievements.py` con:

  **Constantes en módulo:**
  ```python
  COMPETITION_CATEGORY_MAP: dict[str, str]  # ver decisions.md
  STAGE_TO_PHASE: dict[str, str]            # ver decisions.md
  STAGE_ORDER: dict[str, int]               # round_of_16→1, quarter→2, semi→3, final→4
  ```

  **`InferCompetitionAchievementsUseCase`:**
  - Constructor: `__init__(self, infer_repo, achievement_repo, rules_version_repo)`
  - `async execute(competition_id, season, rules_version_id) → InferAchievementsResult`
  - Algoritmo completo:
    1. Cargar `rules_version`; si no existe → return result con `skipped=True, error`
    2. Llamar `infer_repo.get_knockout_stage_fixtures(competition_id, season)`
    3. Si lista vacía → `return InferAchievementsResult(skipped=True, achievements_upserted=0)`
    4. Construir `teams_at_stage: dict[str, set[int]]` iterando fixtures
    5. Ordenar stages presentes por `STAGE_ORDER` descendente
    6. Para stage "final": determinar winner/runner_up vía `_resolve_final_winner(fixture)`
       - Contar goles normales con `get_goals_for_fixture`
       - Si empate: contar goles de tanda con `get_shootout_goals_for_fixture`
       - Si aún empate: winner = equipo con menor `team_id`, log WARNING
    7. Para cada stage en orden descendente (excepto "final"):
       - next_stage = stage de orden inmediatamente superior presentes
       - `eliminated = teams_at_stage[stage] - teams_at_stage.get(next_stage, set())`
       - Asignar `phase = STAGE_TO_PHASE[stage]` a cada equipo eliminado
    8. Resolver `bonus_points` y `weight` desde `config.achievement_phase_bonuses[category][phase]` y `config.competition_bonus_weights[comp_name]`
       - Si category no encontrada en COMPETITION_CATEGORY_MAP → log WARNING, usar `bonus_points=0, weight=1.0`
    9. `upsert_achievement()` para cada `(team_id, phase)` via `achievement_repo`
    10. Retornar `InferAchievementsResult`

  **`InferAllCompetitionAchievementsUseCase`:**
  - Constructor: `__init__(self, infer_repo, achievement_repo, rules_version_repo)`
  - `async execute(season, rules_version_id) → InferAllAchievementsResult`
  - Llama `infer_repo.get_all_knockout_competition_ids(season)`
  - Para cada `competition_id`: instancia y llama `InferCompetitionAchievementsUseCase.execute()`
  - Agrega resultados en `InferAllAchievementsResult`
  - Log progreso por competición

### 3. Repository

- [ ] Crear `src/sfa/infrastructure/repositories/infer_achievements_repository.py` con `InferAchievementsRepository(InferAchievementsRepositoryPort)`:

  **`get_knockout_stage_fixtures(competition_id, season) → list[KnockoutFixtureDTO]`:**
  ```sql
  SELECT id, stage, home_team_id, away_team_id
  FROM fixtures
  WHERE competition_id = :cid AND season = :season AND stage != 'regular'
  ```

  **`get_goals_for_fixture(fixture_id) → dict[int, int]`:**
  - Join `player_events` con `players` para obtener `team_id`
  - WHERE `fixture_id = :fid AND event_type IN ('goal', 'goal_penalty')`
  - GROUP BY team_id → COUNT(*)
  - Retornar dict; si no hay eventos → `{}`

  **`get_shootout_goals_for_fixture(fixture_id) → dict[int, int]`:**
  - Igual pero `event_type = 'goal_shootout'`

  **`get_competition_name(competition_id) → str`:**
  ```sql
  SELECT name FROM competitions WHERE id = :cid
  ```
  - Si no existe → raise `ValueError(f"Competition {competition_id} not found")`

  **`get_all_knockout_competition_ids(season) → list[int]`:**
  ```sql
  SELECT DISTINCT competition_id FROM fixtures
  WHERE season = :season AND stage != 'regular'
  ```

  Nota: todas las queries usan `select()` de SQLAlchemy 2.0 async; no raw SQL.

### 4. Pydantic schemas

- [ ] En `src/sfa/api/v1/schemas/scoring_rules_schemas.py` añadir al final:
  ```python
  class InferAchievementsRequestSchema(BaseModel):
      competition_id: int
      season: str
      rules_version_id: int

  class InferAchievementsAllRequestSchema(BaseModel):
      season: str
      rules_version_id: int

  class InferAchievementsResponseSchema(BaseModel):
      task_id: str
      status: str
      message: str
  ```

### 5. Endpoints

- [ ] En `src/sfa/api/v1/scoring_rules_router.py` añadir al final:

  ```python
  @router.post("/infer-achievements", response_model=InferAchievementsResponseSchema, status_code=202)
  async def trigger_infer_achievements(body: InferAchievementsRequestSchema):
      from sfa.tasks.infer_competition_achievements_task import infer_competition_achievements_task
      task = infer_competition_achievements_task.delay(
          competition_id=body.competition_id,
          season=body.season,
          rules_version_id=body.rules_version_id,
      )
      return InferAchievementsResponseSchema(
          task_id=task.id, status="queued",
          message=f"Achievement inference queued for competition_id={body.competition_id} season={body.season}",
      )

  @router.post("/infer-achievements-all", response_model=InferAchievementsResponseSchema, status_code=202)
  async def trigger_infer_achievements_all(body: InferAchievementsAllRequestSchema):
      from sfa.tasks.infer_all_competition_achievements_task import infer_all_competition_achievements_task
      task = infer_all_competition_achievements_task.delay(
          season=body.season,
          rules_version_id=body.rules_version_id,
      )
      return InferAchievementsResponseSchema(
          task_id=task.id, status="queued",
          message=f"Achievement inference queued for ALL competitions season={body.season}",
      )
  ```

### 6. Celery tasks

- [ ] Crear `src/sfa/tasks/infer_competition_achievements_task.py`:
  - `@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)`
  - `def infer_competition_achievements_task(self, competition_id, season, rules_version_id)`
  - Patrón sync→async idéntico a `calculate_achievement_bonuses_task.py`
  - Late imports dentro de `_run()` para evitar circular imports
  - `async with AsyncSessionLocal() as session:` → instanciar repos → use case → `await session.commit()`
  - Log resultado al final

- [ ] Crear `src/sfa/tasks/infer_all_competition_achievements_task.py`:
  - `@celery_app.task(bind=True, max_retries=0, time_limit=3600)`
  - `def infer_all_competition_achievements_task(self, season, rules_version_id)`
  - Mismo patrón; usar `InferAllCompetitionAchievementsUseCase`
  - Log con totales (`competitions_processed`, `total_achievements_upserted`)

### 7. Wiring (DI)

- [ ] En `src/sfa/core/dependencies.py` añadir:

  ```python
  from sfa.infrastructure.repositories.infer_achievements_repository import InferAchievementsRepository

  async def get_infer_achievements_repository(
      db: Annotated[AsyncSession, Depends(get_db)],
  ) -> InferAchievementsRepository:
      return InferAchievementsRepository(db)

  async def get_infer_competition_achievements_use_case(
      infer_repo: Annotated[InferAchievementsRepository, Depends(get_infer_achievements_repository)],
      achievement_repo: Annotated[CompetitionAchievementRepository, Depends(get_competition_achievement_repository)],
      rules_version_repo: Annotated[ScoringRulesVersionRepository, Depends(get_scoring_rules_version_repository)],
  ) -> InferCompetitionAchievementsUseCase:
      from sfa.application.use_cases.infer_competition_achievements import InferCompetitionAchievementsUseCase
      return InferCompetitionAchievementsUseCase(infer_repo, achievement_repo, rules_version_repo)

  async def get_infer_all_competition_achievements_use_case(
      infer_repo: Annotated[InferAchievementsRepository, Depends(get_infer_achievements_repository)],
      achievement_repo: Annotated[CompetitionAchievementRepository, Depends(get_competition_achievement_repository)],
      rules_version_repo: Annotated[ScoringRulesVersionRepository, Depends(get_scoring_rules_version_repository)],
  ) -> InferAllCompetitionAchievementsUseCase:
      from sfa.application.use_cases.infer_competition_achievements import InferAllCompetitionAchievementsUseCase
      return InferAllCompetitionAchievementsUseCase(infer_repo, achievement_repo, rules_version_repo)
  ```

### 8. Export en __init__.py de repositories

- [ ] En `src/sfa/infrastructure/repositories/__init__.py` añadir `InferAchievementsRepository` al import y al `__all__` (si existe).

### 9. Integración en RunFullRecalculationUseCase

- [ ] En `src/sfa/application/use_cases/run_full_recalculation.py`:
  - Añadir parámetro `infer_repo` al constructor (tipo `InferAchievementsRepositoryPort`)
  - Añadir `infer_achievements: bool = True` al método `execute()`
  - Si `infer_achievements=True`: antes del paso de achievement bonuses, llamar `InferAllCompetitionAchievementsUseCase(infer_repo, achievement_repo, rules_version_repo).execute(season, rules_version_id)`
  - Log el resultado de inferencia dentro del flujo del use case

- [ ] En `src/sfa/tasks/run_full_recalculation_task.py`:
  - Añadir `infer_achievements: bool = True` como parámetro de la task
  - Instanciar `InferAchievementsRepository` dentro de `_run()` y pasarlo al `RunFullRecalculationUseCase`
  - Pasar `infer_achievements` al `use_case.execute()`

### 10. HTTP file

- [ ] Crear `http/infer_achievements.http`:
  ```http
  ### Infer achievements for Champions League 2025
  POST http://localhost:8000/api/v1/scoring/infer-achievements
  Content-Type: application/json

  {
    "competition_id": 10,
    "season": "2025",
    "rules_version_id": 3
  }

  ### Infer achievements for ALL competitions 2025
  POST http://localhost:8000/api/v1/scoring/infer-achievements-all
  Content-Type: application/json

  {
    "season": "2025",
    "rules_version_id": 3
  }

  ### Error: competition without knockout stages (domestic league)
  POST http://localhost:8000/api/v1/scoring/infer-achievements
  Content-Type: application/json

  {
    "competition_id": 1,
    "season": "2025",
    "rules_version_id": 3
  }
  ```

### 11. Tests

- [ ] Crear `tests/use_cases/test_infer_competition_achievements.py` con:

  **`FakeInferAchievementsRepository`** implementando `InferAchievementsRepositoryPort` completo:
  - Constructor acepta `fixtures: list[KnockoutFixtureDTO]`, `goals: dict[int, dict[int, int]]`, `shootout_goals: dict[int, dict[int, int]]`, `competition_name: str`
  - Implementa los 4 métodos del Protocol con datos en memoria

  **`FakeCompetitionAchievementRepository`** (stub mínimo para `upsert_achievement`):
  - Guarda llamadas en `self.upserted: list[CompetitionAchievement]`
  - Retorna IDs incrementales

  **`FakeScoringRulesVersionRepository`** (stub para `get_version_by_id`):
  - Retorna una `ScoringRulesVersion` con `ScoringConfig.default_v2()`

  **Escenarios de test (todos con `@pytest.mark.anyio`):**

  ```python
  class TestInferCompetitionAchievementsUseCase:

      async def test_domestic_league_skipped_when_no_knockout_fixtures(self):
          # fixtures vacíos → skipped=True, achievements_upserted=0

      async def test_final_winner_correctly_assigned_from_goals(self):
          # fixture final: home=1 vs away=2, goles: {1: 2, 2: 1}
          # → team 1 = winner, team 2 = runner_up

      async def test_final_winner_assigned_from_shootout_when_regular_time_tied(self):
          # goles normales empate 1-1, tanda: {1: 4, 2: 3}
          # → team 1 = winner, team 2 = runner_up

      async def test_final_winner_fallback_to_lower_id_when_all_tied(self):
          # goles normales 1-1, tanda 3-3 → team con menor id = winner, WARNING loggeado

      async def test_semi_final_eliminated_teams_get_semi_final_phase(self):
          # 2 semis + 1 final: equipos que no llegan a la final → semi_final

      async def test_full_tournament_all_phases_assigned(self):
          # round_of_16 (8 fixtures) + quarter (4) + semi (2) + final (1)
          # → 16 round_of_16, 8 quarter_final, 4 semi_final, 1 winner, 1 runner_up
          # total achievements_upserted = 30

      async def test_unknown_competition_name_uses_zero_bonus_with_warning(self):
          # competition_name no está en COMPETITION_CATEGORY_MAP
          # → bonus_points=0, no exception, log warning
  ```

### 12. Verificación de calidad

- [ ] Ejecutar `pytest tests/` antes de escribir tests nuevos — documentar fallos preexistentes
- [ ] Verificar `pytest tests/use_cases/test_infer_competition_achievements.py -v` pasa al 100%
- [ ] Verificar `pytest tests/` global no introduce regresiones
- [ ] Verificar `flake8 src/ tests/` sin errores nuevos
- [ ] Verificar `isort --check-only src/ tests/` sin errores

## Agent Routing Brief

**DDD Designer needed: no**

Los únicos artefactos de dominio nuevos son DTOs planos (`KnockoutFixtureDTO`,
`InferAchievementsResult`, `InferAllAchievementsResult`) y un Protocol. No hay entidades
con identidad, invariantes de negocio complejas ni value objects con reglas de construcción.
La lógica de inferencia (algoritmo de diferencia de conjuntos + conteo de goles) es
coordinación de datos, no modelado de dominio profundo. Todo encaja directamente en el
use case sin necesidad de entidades de dominio independientes.

## Verificación end-to-end

1. **Verificar fixtures KO en DB para temporada 2025:**
   ```sql
   SELECT competition_id, stage, COUNT(*) FROM fixtures
   WHERE season = '2025' AND stage != 'regular'
   GROUP BY 1, 2 ORDER BY 1, 2;
   ```
   Debe mostrar filas para CL (competition_id=10), EL (253), Conference (254), copas.

2. **Lanzar inferencia para CL 2025:**
   ```http
   POST /api/v1/scoring/infer-achievements
   { "competition_id": 10, "season": "2025", "rules_version_id": 3 }
   ```
   Respuesta: `{ "task_id": "...", "status": "queued" }`

3. **Verificar logros registrados en DB:**
   ```sql
   SELECT team_id, phase, bonus_points, weight FROM competition_achievements
   WHERE competition_id = 10 AND season = '2025'
   ORDER BY phase;
   ```
   Debe mostrar winner (1 equipo), semi_final (2+ equipos), quarter_final, round_of_16.

4. **Lanzar inferencia para TODAS las competiciones:**
   ```http
   POST /api/v1/scoring/infer-achievements-all
   { "season": "2025", "rules_version_id": 3 }
   ```

5. **Verificar que `run_full_recalculation_task` con `infer_achievements=True` infiere + calcula bonuses en una sola pasada:**
   ```http
   POST /api/v1/scoring/recalculate-full
   { "rules_version_id": 3, "season": "2025", "force_recalculate": true }
   ```
   Logs de Celery deben mostrar el paso de inferencia antes del de achievement bonuses.

6. **Verificar que los players tienen `achievement_bonus_pts > 0` en `sfa_season_scores`:**
   ```sql
   SELECT player_id, competition_id, achievement_bonus_pts FROM sfa_season_scores
   WHERE season = '2025' AND achievement_bonus_pts > 0
   LIMIT 20;
   ```
