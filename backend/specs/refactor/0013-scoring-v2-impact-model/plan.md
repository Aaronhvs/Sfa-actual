# Plan: Scoring v2 — Impact Model

## Archivos a crear

- [ ] `src/sfa/infrastructure/models/team_strengths/models.py` — `TeamStrengthModel` (tabla `team_strengths`)
- [ ] `src/sfa/infrastructure/models/team_strengths/__init__.py`
- [ ] `src/sfa/infrastructure/models/competition_achievements/models.py` — `CompetitionAchievementModel`, `PlayerAchievementBonusModel`
- [ ] `src/sfa/infrastructure/models/competition_achievements/__init__.py`
- [ ] `src/sfa/infrastructure/repositories/team_strength_repository.py` — `TeamStrengthRepository`
- [ ] `src/sfa/infrastructure/repositories/competition_achievement_repository.py` — `CompetitionAchievementRepository`
- [ ] `src/sfa/application/use_cases/calculate_team_strengths.py` — `CalculateTeamStrengthsUseCase`
- [ ] `src/sfa/application/use_cases/register_competition_achievement.py` — `RegisterCompetitionAchievementUseCase`
- [ ] `src/sfa/application/use_cases/calculate_achievement_bonuses.py` — `CalculateAchievementBonusesUseCase`
- [ ] `src/sfa/api/v1/schemas/achievements_schemas.py` — Pydantic schemas para achievements y team strengths
- [ ] `src/sfa/api/v1/achievements_router.py` — endpoints de logros y strengths
- [ ] `src/sfa/tasks/calculate_team_strengths_task.py` — Celery task
- [ ] `src/sfa/tasks/calculate_achievement_bonuses_task.py` — Celery task
- [ ] `migrations/0013_scoring_v2_impact_model.sql` — migración completa
- [ ] `http/achievements.http` — casos HTTP para achievements y team strengths
- [ ] `tests/use_cases/test_calculate_team_strengths.py`
- [ ] `tests/use_cases/test_register_competition_achievement.py`
- [ ] `tests/use_cases/test_calculate_achievement_bonuses.py`
- [ ] `tests/domain/test_scoring_v2_value_objects.py`

## Archivos a modificar

- [ ] `src/sfa/domain/scoring/value_objects.py` — PositionGroup (5 grupos), DiminishingReturnsConfig (nuevo), TeamStrengthBlend (nuevo), M1RivalDifficulty (constructor extendido), ScoringConfig (campos v2)
- [ ] `src/sfa/domain/scoring/entities.py` — CompetitionAchievement (nueva entidad), PlayerAchievementBonus (nuevo DTO)
- [ ] `src/sfa/domain/scoring/services.py` — BASE_POINTS_TABLE_V2 (nueva constante), ScoringConfig.default_v2() factory
- [ ] `src/sfa/domain/scoring_ports.py` — PlayerEventRawContextDTO (+ minutes, player_team_strength, rival_team_strength), TeamStrengthRepositoryPort, CompetitionAchievementRepositoryPort
- [ ] `src/sfa/infrastructure/models/__init__.py` — importar TeamStrengthModel, CompetitionAchievementModel, PlayerAchievementBonusModel
- [ ] `src/sfa/infrastructure/models/events/models.py` — actualizar CheckConstraints: m1 [0.6,1.8], m4 [1.0,1.5], mvisit IN(1.0,1.15)
- [ ] `src/sfa/infrastructure/repositories/player_event_score_repository.py` — `get_events_for_recalc` añade LEFT JOIN team_strengths y player_stats.minutes
- [ ] `src/sfa/infrastructure/repositories/__init__.py` — exportar nuevos repositorios
- [ ] `src/sfa/application/use_cases/calculate_scores_for_rules_version.py` — `_score_stats_event` (minutes threshold, diminishing returns, passes avg, M1 strength), `_score_individual_event` (M1 strength)
- [ ] `src/sfa/application/use_cases/get_ranking.py` — añadir `use_total: bool = False` para ordenar por `sfa_total_pts`
- [ ] `src/sfa/core/dependencies.py` — wiring de nuevos repositorios y use cases
- [ ] `src/sfa/main.py` — registrar `achievements_router`

## Checklist de implementación

### Fase 1: Domain — Value Objects y Entidades [DDD]

- [ ] **[DDD] 1.1** Modificar `PositionGroup` en `domain/scoring/value_objects.py`
  - Reemplazar FW/MF/DF por DEL/EXT/MF/LAT/DC (5 valores)
  - Actualizar `position_to_group()`: DEL→DEL, EXT→EXT, MC→MF, LAT→LAT, DC→DC
  - GK sigue lanzando ValueError
  - Verificar que `ScoringConfig.from_dict` acepta los 5 nuevos valores de grupo en `base_points`

- [ ] **[DDD] 1.2** Añadir `DiminishingReturnsConfig` a `domain/scoring/value_objects.py`
  - Frozen dataclass con `cap: int` y `extra_factor: float`
  - `__post_init__`: `cap > 0`, `0 < extra_factor < 1` — lanzar ValueError si fallan
  - Método estático `apply(n: float, base_pts_per_unit: float, cfg: DiminishingReturnsConfig) -> float`
    - `full = min(n, cfg.cap) * base_pts_per_unit`
    - `extra = max(0.0, n - cfg.cap) * base_pts_per_unit * cfg.extra_factor`
    - Retorna `full + extra`

- [ ] **[DDD] 1.3** Añadir `TeamStrengthBlend` a `domain/scoring/value_objects.py`
  - Frozen dataclass con `value: float` (resultado en [0.0, 100.0])
  - Constructor acepta `prev_season_strength: float | None`, `current_season_strength: float | None`, `matchday: int | None`, `fallback_strength: float = 30.0`
  - Lógica de mezcla según matchday (1-5: 80/20, 6-10: 60/40, 11-15: 40/60, 16+: 20/80, None: 50/50)
  - Si ambas son None → usa fallback_strength
  - Si solo una es None → 100% de la que existe
  - Clamp final: `max(0.0, min(100.0, value))`

- [ ] **[DDD] 1.4** Modificar `M1RivalDifficulty` en `domain/scoring/value_objects.py`
  - Nuevo constructor: acepta `player_team_strength: float | None`, `rival_team_strength: float | None`, `player_team_pos: int | None`, `rival_team_pos: int | None`, `config: ScoringConfig | None`
  - Si ambos strengths son not None: `M1 = 1.0 + (rival_strength - player_strength) / divisor`, clamp config.m1_clamp
  - Fallback si cualquier strength es None: formula legacy `1.0 + (player_team_pos - rival_team_pos) / config.m1_divisor`
  - Si fallback y pos son None también: M1 = 1.0 (neutral)

- [ ] **[DDD] 1.5** Extender `ScoringConfig` en `domain/scoring/value_objects.py`
  - Añadir campos nuevos (ver decisions.md D3)
  - `diminishing_returns: dict[ActionType, DiminishingReturnsConfig]`
  - `passes_avg_by_position: dict[PositionGroup, int]`
  - `minutes_threshold_stats: int`
  - `minutes_penalty_factor: float`
  - `ranking_min_minutes_global: int`
  - `ranking_min_minutes_competition: int`
  - `m1_strength_divisor: float`
  - `league_strength_factors: dict[str, float]`
  - `promoted_champion_strength: float`, `promoted_runner_up_strength: float`, `promoted_playoff_strength: float`, `promoted_default_strength: float`
  - `cup_lower_div_strengths: dict[str, float]`
  - `achievement_phase_bonuses: dict[str, dict[str, int]]`
  - `competition_bonus_weights: dict[str, float]`
  - Actualizar `__post_init__` con nuevas invariantes
  - Actualizar `from_dict` / `to_dict` para todos los campos nuevos
  - Añadir `default_v2() -> ScoringConfig` factory con todos los valores v2.0 (ver decisions.md)

- [ ] **[DDD] 1.6** Añadir `CompetitionAchievement` y `PlayerAchievementBonus` a `domain/scoring/entities.py`
  - `CompetitionAchievement`: frozen dataclass con id, competition_id, team_id, season, phase, bonus_points, weight, created_at
  - Invariantes: `bonus_points >= 0`, `0 < weight <= 1.0`
  - `PlayerAchievementBonus`: frozen dataclass con todos los campos de decisions.md
  - Invariantes: `0 <= participation_ratio <= 1.0`, `final_bonus >= 0`

### Fase 2: Domain — Services

- [ ] 2.1 Añadir `BASE_POINTS_TABLE_V2` a `domain/scoring/services.py`
  - Nueva constante con los 5 grupos y todos los puntos base v2 (ver tabla completa en decisions.md)
  - No eliminar `BASE_POINTS_TABLE` (backward-compat con v1)

- [ ] 2.2 Añadir `ScoringConfig.default_v2()` factory en `domain/scoring/value_objects.py`
  - Construye desde `BASE_POINTS_TABLE_V2` con todos los parámetros v2:
    - `m1_clamp=(0.6, 1.8)`, `m1_divisor=20.0`, `m1_strength_divisor=100.0`
    - `m4_psxg_multiplier=0.8`, `m4_clamp=(1.0, 1.5)`
    - `mvisit_bonus=1.15`
    - `mrating_thresholds=[(6.5, 0.50), (7.0, 0.70), (7.5, 0.85), (8.0, 1.00), (8.5, 1.15)]`
    - `mrating_top_value=1.30`, `mrating_none_value=0.75`
    - `combined_clamp=(0.3, 4.0)`
    - `diminishing_returns` con los 6 acciones configuradas
    - `passes_avg_by_position` con los 5 grupos
    - `minutes_threshold_stats=15`, `minutes_penalty_factor=0.50`
    - `ranking_min_minutes_global=600`, `ranking_min_minutes_competition=180`
    - `achievement_phase_bonuses` con Champions/EL/Conference/copas nacionales
    - `competition_bonus_weights` con todos los pesos
    - `league_strength_factors` con todos los factores

### Fase 3: Domain Ports

- [ ] 3.1 Actualizar `PlayerEventRawContextDTO` en `domain/scoring_ports.py`
  - Añadir `minutes: int | None`
  - Añadir `player_team_strength: float | None`
  - Añadir `rival_team_strength: float | None`

- [ ] 3.2 Añadir `TeamStrengthRepositoryPort` a `domain/scoring_ports.py`
  ```python
  @runtime_checkable
  class TeamStrengthRepositoryPort(Protocol):
      async def get_team_strength(self, team_id: int, season: str, competition_id: int) -> float | None: ...
      async def upsert_team_strength(self, team_id: int, season: str, competition_id: int, strength: float, source: str) -> None: ...
      async def get_team_standings_for_season(self, competition_id: int, season: str) -> list[TeamStandingRow]: ...
  ```
  Añadir `TeamStandingRow` DTO: `(team_id, season, competition_id, avg_position, total_points, matchdays_played)`

- [ ] 3.3 Añadir `CompetitionAchievementRepositoryPort` a `domain/scoring_ports.py`
  ```python
  @runtime_checkable
  class CompetitionAchievementRepositoryPort(Protocol):
      async def upsert_achievement(self, achievement: CompetitionAchievement) -> int: ...
      async def get_achievements_for_season(self, competition_id: int, season: str) -> list[CompetitionAchievement]: ...
      async def upsert_player_bonus(self, bonus: PlayerAchievementBonus) -> None: ...
      async def get_team_total_minutes(self, team_id: int, competition_id: int, season: str) -> int: ...
      async def get_player_minutes_in_competition(self, player_id: int, competition_id: int, season: str) -> int: ...
      async def get_players_for_team_season(self, team_id: int, competition_id: int, season: str) -> list[int]: ...
      async def update_season_score_bonus(self, player_id: int, competition_id: int, season: str, rules_version_id: int, bonus_pts: float) -> None: ...
  ```

### Fase 4: Infrastructure — Modelos SQLAlchemy

- [ ] 4.1 Crear `infrastructure/models/team_strengths/models.py`
  - `TeamStrengthModel`: tabla `team_strengths`
  - Columnas: id, team_id (FK teams.id), season, competition_id (FK competitions.id), strength (Numeric 5,2), source (String 20), created_at
  - CheckConstraint: `strength BETWEEN 0 AND 100`, `source IN ('calculated', 'default', 'override')`
  - UniqueConstraint: `(team_id, season, competition_id)`

- [ ] 4.2 Crear `infrastructure/models/competition_achievements/models.py`
  - `CompetitionAchievementModel`: tabla `competition_achievements`
  - `PlayerAchievementBonusModel`: tabla `player_achievement_bonuses`
  - Ver schema exacto en decisions.md D1

- [ ] 4.3 Crear `__init__.py` para ambos nuevos subdirectorios de modelos

- [ ] 4.4 Actualizar `infrastructure/models/__init__.py`
  - Importar y exportar `TeamStrengthModel`, `CompetitionAchievementModel`, `PlayerAchievementBonusModel`

- [ ] 4.5 Actualizar CheckConstraints en `infrastructure/models/events/models.py`
  - `ck_event_m1`: cambiar a `BETWEEN 0.6 AND 1.8`
  - `ck_event_m4`: cambiar a `BETWEEN 1.0 AND 1.5`
  - `ck_event_mvisit`: cambiar a `IN (1.0, 1.15)`

- [ ] 4.6 Crear `migrations/0013_scoring_v2_impact_model.sql`
  - Incluir todos los ALTER TABLE, CREATE TABLE del D1 en decisions.md
  - Incluir índices auxiliares

### Fase 5: Infrastructure — Repositorios

- [ ] 5.1 Crear `infrastructure/repositories/team_strength_repository.py`
  - `TeamStrengthRepository` implementando `TeamStrengthRepositoryPort`
  - `get_team_strength`: SELECT strength FROM team_strengths WHERE team_id=? AND season=? AND competition_id=?
  - `upsert_team_strength`: INSERT ... ON CONFLICT (team_id, season, competition_id) DO UPDATE
  - `get_team_standings_for_season`: query sobre `standing_snapshots` agrupando por team_id, calculando avg_position y total_points para la temporada

- [ ] 5.2 Crear `infrastructure/repositories/competition_achievement_repository.py`
  - `CompetitionAchievementRepository` implementando `CompetitionAchievementRepositoryPort`
  - `upsert_achievement`: INSERT ... ON CONFLICT DO UPDATE
  - `get_achievements_for_season`: SELECT WHERE competition_id=? AND season=?
  - `upsert_player_bonus`: INSERT ... ON CONFLICT DO UPDATE
  - `get_team_total_minutes`: SUM(ps.minutes) JOIN players JOIN fixtures WHERE team_id=? AND competition_id=? AND season=?
  - `get_player_minutes_in_competition`: SUM(ps.minutes) WHERE player_id=? AND competition_id=? AND season=?
  - `get_players_for_team_season`: SELECT DISTINCT player_id JOIN players WHERE team_id=? con apariciones en fixtures de esa competición
  - `update_season_score_bonus`: UPDATE sfa_season_scores SET achievement_bonus_pts=? WHERE player_id=? AND competition_id=? AND season=? AND rules_version_id=?

- [ ] 5.3 Actualizar `infrastructure/repositories/player_event_score_repository.py`
  - `get_events_for_recalc`: añadir al JOIN existente:
    - `LEFT JOIN team_strengths ts_home ON (fixture.home_team_id = ts_home.team_id AND fixture.season = ts_home.season AND fixture.competition_id = ts_home.competition_id)`
    - `LEFT JOIN team_strengths ts_away ON (fixture.away_team_id = ts_away.team_id AND fixture.season = ts_away.season AND fixture.competition_id = ts_away.competition_id)`
    - Incluir `ps.minutes` en el SELECT
    - Derivar `player_team_strength` y `rival_team_strength` según si el jugador es local o visitante

- [ ] 5.4 Actualizar `infrastructure/repositories/__init__.py`
  - Exportar `TeamStrengthRepository`, `CompetitionAchievementRepository`

### Fase 6: Application — Use Cases

- [ ] 6.1 Crear `application/use_cases/calculate_team_strengths.py`
  - `CalculateTeamStrengthsResult(season, competition_id, teams_processed, status, error)`
  - `CalculateTeamStrengthsUseCase(team_strength_repo, scoring_rules_version_repo)`
  - `execute(season: str, competition_id: int, matchday: int | None) -> CalculateTeamStrengthsResult`
  - Flujo (ver D4 en decisions.md):
    1. Leer standings de la temporada actual (`get_team_standings_for_season`)
    2. Leer standings de temporada anterior (season - 1)
    3. Para cada equipo: construir `TeamStrengthBlend` y guardar via `upsert_team_strength`
    4. Para equipos sin standings previos: usar `config.promoted_*_strength` según clasificación

- [ ] 6.2 Crear `application/use_cases/register_competition_achievement.py`
  - `RegisterAchievementResult(achievement_id, status, error)`
  - `RegisterCompetitionAchievementUseCase(achievement_repo, scoring_rules_version_repo)`
  - `execute(competition_id, team_id, season, phase, rules_version_id) -> RegisterAchievementResult`
  - Flujo (ver D7 en decisions.md):
    1. Cargar versión de reglas activa para obtener config
    2. Validar que `phase` es clave válida en `config.achievement_phase_bonuses`
    3. Leer bonus_points y weight de la config
    4. Upsert en `competition_achievements`

- [ ] 6.3 Crear `application/use_cases/calculate_achievement_bonuses.py`
  - `CalculateAchievementBonusesResult(season, competition_id, players_updated, bonuses_created, status, error)`
  - `CalculateAchievementBonusesUseCase(achievement_repo, scoring_rules_version_repo)`
  - `execute(season: str, competition_id: int, rules_version_id: int) -> CalculateAchievementBonusesResult`
  - Flujo completo (ver D6 en decisions.md)

- [ ] 6.4 Actualizar `application/use_cases/calculate_scores_for_rules_version.py`
  - `_score_stats_event`: añadir lógica de minutes threshold (ver D5 en decisions.md)
  - `_score_stats_event`: aplicar `DiminishingReturnsConfig.apply()` para las 6 acciones configuradas
  - `_score_stats_event`: aplicar `passes_avg_by_position` para PASSES_COMPLETED
  - `_score_stats_event` y `_score_individual_event`: pasar `player_team_strength` y `rival_team_strength` a `M1RivalDifficulty`
  - Actualizar `calculation_details` para incluir `minutes`, `passes_threshold`, `diminishing_applied`, `strength_used`

- [ ] 6.5 Actualizar `application/use_cases/get_ranking.py`
  - Añadir `use_total: bool = False`
  - Cuando `use_total=True` y hay `rules_version_id`: ordenar por `sfa_total_pts` en lugar de `total_pts`

### Fase 7: API

- [ ] 7.1 Crear `api/v1/schemas/achievements_schemas.py`
  - `RegisterAchievementRequestSchema`: competition_id, team_id, season, phase, rules_version_id
  - `RegisterAchievementResponseSchema`: achievement_id, status, message
  - `CalculateAchievementBonusesRequestSchema`: season, competition_id, rules_version_id
  - `CalculateAchievementBonusesResponseSchema`: players_updated, bonuses_created, status
  - `CalculateTeamStrengthsRequestSchema`: season, competition_id, matchday (optional)
  - `CalculateTeamStrengthsResponseSchema`: teams_processed, status
  - `TeamStrengthResponseSchema`: team_id, season, competition_id, strength, source

- [ ] 7.2 Crear `api/v1/achievements_router.py`
  - `POST /api/v1/scoring/achievements` → `RegisterCompetitionAchievementUseCase`
  - `POST /api/v1/scoring/achievements/calculate-bonuses` → lanza `calculate_achievement_bonuses_task`
  - `POST /api/v1/scoring/team-strengths/calculate` → lanza `calculate_team_strengths_task`
  - `GET /api/v1/scoring/team-strengths?competition_id=&season=` → query de strengths calculados

- [ ] 7.3 Registrar `achievements_router` en `main.py`

- [ ] 7.4 Actualizar ranking router existente
  - Añadir query param `use_total: bool = False`
  - Pasar a `GetRankingUseCase.execute()`

### Fase 8: Celery Tasks

- [ ] 8.1 Crear `tasks/calculate_team_strengths_task.py`
  - `calculate_team_strengths_task(season, competition_id, matchday=None)`
  - Patrón sync→async estándar con late imports

- [ ] 8.2 Crear `tasks/calculate_achievement_bonuses_task.py`
  - `calculate_achievement_bonuses_task(season, competition_id, rules_version_id)`
  - Patrón sync→async estándar con late imports

### Fase 9: DI Wiring

- [ ] 9.1 Actualizar `core/dependencies.py`
  - `get_team_strength_repository(db) -> TeamStrengthRepository`
  - `get_competition_achievement_repository(db) -> CompetitionAchievementRepository`
  - `get_calculate_team_strengths_use_case(team_strength_repo, rules_version_repo) -> CalculateTeamStrengthsUseCase`
  - `get_register_competition_achievement_use_case(achievement_repo, rules_version_repo) -> RegisterCompetitionAchievementUseCase`
  - `get_calculate_achievement_bonuses_use_case(achievement_repo, rules_version_repo) -> CalculateAchievementBonusesUseCase`

### Fase 10: HTTP Files

- [ ] 10.1 Crear `http/achievements.http`
  - `POST /api/v1/scoring/team-strengths/calculate` con body `{"season": "2024", "competition_id": 1}`
  - `GET /api/v1/scoring/team-strengths?competition_id=1&season=2024`
  - `POST /api/v1/scoring/achievements` con body de ejemplo (Champions, Real Madrid, winner)
  - `POST /api/v1/scoring/achievements/calculate-bonuses`
  - Error case: phase inválida → 400
  - Error case: versión de reglas inexistente → 404

### Fase 11: Tests

- [ ] **[DDD] 11.1** Crear `tests/domain/test_scoring_v2_value_objects.py`
  - `TestPositionGroupV2`:
    - `test_five_groups_exist` — DEL, EXT, MF, LAT, DC presentes; FW y DF ausentes
    - `test_position_to_group_all_five_positions`
    - `test_gk_raises_value_error`
  - `TestDiminishingReturnsConfig`:
    - `test_apply_below_cap_uses_full_base`
    - `test_apply_at_cap_uses_full_base`
    - `test_apply_above_cap_uses_extra_factor`
    - `test_invalid_cap_raises_value_error`
    - `test_invalid_extra_factor_raises_value_error`
  - `TestTeamStrengthBlend`:
    - `test_early_matchday_weights_prev_heavily`
    - `test_late_matchday_weights_current_heavily`
    - `test_no_prev_uses_current_only`
    - `test_no_current_uses_prev_only`
    - `test_both_none_uses_fallback`
    - `test_result_clamped_to_0_100`
  - `TestM1RivalDifficultyV2`:
    - `test_with_strengths_uses_strength_formula`
    - `test_without_strengths_uses_legacy_formula`
    - `test_clamp_min_0_6`
    - `test_clamp_max_1_8`
  - `TestScoringConfigV2`:
    - `test_default_v2_produces_5_position_groups`
    - `test_default_v2_has_diminishing_returns_for_6_actions`
    - `test_from_dict_roundtrip_v2`
    - `test_invalid_minutes_threshold_raises_value_error`
    - `test_invalid_minutes_penalty_factor_raises_value_error`

- [ ] **[sfa-test] 11.2** Crear `tests/use_cases/test_calculate_team_strengths.py`
  - Fakes: `FakeTeamStrengthRepository`, `FakeScoringRulesVersionRepository`
  - `TestCalculateTeamStrengthsUseCase`:
    - `test_early_season_weights_previous_heavily`
    - `test_late_season_weights_current_heavily`
    - `test_promoted_team_without_history_uses_default_strength`
    - `test_upserts_strength_for_all_teams_in_competition`

- [ ] **[sfa-test] 11.3** Crear `tests/use_cases/test_register_competition_achievement.py`
  - Fakes: `FakeCompetitionAchievementRepository`, `FakeScoringRulesVersionRepository`
  - `TestRegisterCompetitionAchievementUseCase`:
    - `test_valid_phase_creates_achievement`
    - `test_invalid_phase_raises_value_error`
    - `test_duplicate_phase_upserts_not_duplicates`

- [ ] **[sfa-test] 11.4** Crear `tests/use_cases/test_calculate_achievement_bonuses.py`
  - `TestCalculateAchievementBonusesUseCase`:
    - `test_player_with_full_participation_gets_full_bonus`
    - `test_player_with_partial_participation_gets_proportional_bonus`
    - `test_no_achievements_produces_zero_bonus`
    - `test_season_score_updated_with_correct_bonus`

- [ ] **[sfa-test] 11.5** Actualizar `tests/use_cases/test_calculate_scores_for_rules_version.py`
  - Añadir tests para lógica v2:
    - `test_stats_event_under_15_minutes_applies_penalty_factor`
    - `test_stats_event_at_or_above_15_minutes_no_penalty`
    - `test_diminishing_returns_applied_for_duels_won`
    - `test_passes_threshold_subtracted_before_scoring`
    - `test_m1_uses_strength_when_available`
    - `test_m1_falls_back_to_position_when_no_strength`

- [ ] Verificar `pytest tests/` pasa con coverage ≥80%
- [ ] Verificar `flake8 src/ tests/` sin errores
- [ ] Verificar `isort --check-only src/ tests/` sin errores

## Agent Routing Brief

**DDD Designer needed:** yes

Los ítems marcados `[DDD]` requieren @DDD-Designer antes de iniciar Fase 2:

1. **`PositionGroup` v2 (ítem 1.1)** — Cambiar de 3 a 5 grupos es un cambio estructural de dominio que
   afecta a `position_to_group()`, a `ScoringConfig.base_points`, a `BASE_POINTS_TABLE_V2`, y a
   `ScoringConfig.from_dict`. Debe modelarse con cuidado para no romper la deserialización de
   versiones v1 existentes en DB.

2. **`DiminishingReturnsConfig` (ítem 1.2)** — Value object con invariantes de negocio (`cap > 0`,
   `0 < extra_factor < 1`) y un método estático que es el corazón del cálculo decreciente.
   Un error en `apply()` afecta todos los scores de stats acumulativas.

3. **`TeamStrengthBlend` (ítem 1.3)** — Value object con lógica de mezcla ponderada por matchday,
   manejo de casos None, y clamp de resultado. La lógica de pesos es regla de negocio explícita.

4. **`M1RivalDifficulty` modificado (ítem 1.4)** — El cambio de fórmula (posición → strength) con
   fallback legacy requiere un constructor con lógica condicional no trivial. Las invariantes de
   clamp cambian de [0.5, 2.0] a [0.6, 1.8].

5. **`ScoringConfig` extendido (ítem 1.5)** — Añadir ~15 campos nuevos con sus invariantes,
   serialización/deserialización (from_dict/to_dict), y la nueva factory `default_v2()`.
   Es la base sobre la que se construyen todos los use cases de v2.

6. **`CompetitionAchievement` y `PlayerAchievementBonus` (ítem 1.6)** — Nuevas entidades de dominio
   con invariantes de negocio (participación ratio, bonus positivo) que estructuran el cálculo
   de la nueva capa SFA_TOTAL.

Todos estos elementos deben completarse y ser correctos antes de iniciar Fase 2 (services) y
Fase 3 (ports), que dependen directamente de ellos.

## Orden de ejecución recomendado

```
Fase 1 [DDD] → Fase 2 → Fase 3 → Fase 4 → Fase 5 → Fase 6 → Fase 7 → Fase 8 → Fase 9 → Fase 10 → Fase 11
```

Fase 4 (modelos SQLAlchemy) y la migración SQL pueden ejecutarse en paralelo con Fase 2-3
siempre que Fase 1 esté completa.

## Verificación end-to-end

1. **Crear versión de reglas v2.0:**
   ```
   POST /api/v1/scoring/rules-versions
   Body: {"name": "v2.0-impact-model", "version": "2.0.0", "description": "...",
          "config_json": <output de ScoringConfig.default_v2().to_dict()>}
   → 201 con version_id
   ```

2. **Calcular team strengths antes de recalcular scores:**
   ```
   POST /api/v1/scoring/team-strengths/calculate
   Body: {"season": "2024", "competition_id": 1, "matchday": 20}
   → 202 con task_id
   ```
   Verificar que `team_strengths` tiene filas con `source = "calculated"`.

3. **Recalcular scores bajo v2.0:**
   ```
   POST /api/v1/scoring/recalculate
   Body: {"rules_version_id": <id_v2>, "season": "2024", "force_recalculate": true}
   → 202 con task_id
   ```
   Verificar que `player_event_scores` tiene filas con `rules_version_id = <id_v2>`.
   Verificar que `calculation_details` contiene `"minutes"`, `"strength_used"`, `"passes_threshold"`.

4. **Registrar logro competitivo:**
   ```
   POST /api/v1/scoring/achievements
   Body: {"competition_id": 2, "team_id": 5, "season": "2024",
          "phase": "winner", "rules_version_id": <id_v2>}
   → 201
   ```

5. **Calcular bonuses:**
   ```
   POST /api/v1/scoring/achievements/calculate-bonuses
   Body: {"season": "2024", "competition_id": 2, "rules_version_id": <id_v2>}
   → 202 con task_id
   ```
   Verificar que `player_achievement_bonuses` tiene filas.
   Verificar que `sfa_season_scores.achievement_bonus_pts > 0` para el equipo campeón.
   Verificar que `sfa_season_scores.sfa_total_pts = total_pts + achievement_bonus_pts`.

6. **Verificar ranking con sfa_total:**
   ```
   GET /api/v1/ranking?season=2024&rules_version_id=<id_v2>&use_total=true
   → jugadores del equipo campeón tienen bonus visible en sus pts
   ```

7. **Verificar backward-compat v1.x:**
   ```
   GET /api/v1/ranking?season=2024
   → mismos resultados legacy (rules_version_id IS NULL)
   ```

8. **Verificar diminishing returns:** Tomar un jugador con > 8 duels_won en un partido.
   Verificar en `calculation_details.stats_breakdown` que los puntos de DUELS_WON
   no son lineales (los primeros 8 a valor completo, el exceso al 25%).

9. **Verificar umbral de minutos:** Tomar un jugador con `minutes < 15` en un partido.
   Verificar que sus stats acumulativas tienen `minutes_penalty_applied = true` en
   `calculation_details`.
