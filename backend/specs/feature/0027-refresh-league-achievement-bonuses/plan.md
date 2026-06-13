# Plan: Refresh League Achievement Bonuses on Full Recalculation

## Archivos a crear

- [ ] `src/sfa/application/use_cases/refresh_league_achievement_bonuses.py` — use case que lee
  achievements de ligas domésticas desde DB, recalcula `bonus_points` y `weight` desde la
  config activa de la rules version, y re-upserta cada achievement.

- [ ] `tests/use_cases/test_refresh_league_achievement_bonuses.py` — tests con Fakes que cubren:
  achievements actualizados cuando el valor en config difiere del almacenado, ligas sin
  achievements registrados (no-op), rules version no encontrada (early return con error).

## Archivos a modificar

- [ ] `src/sfa/domain/scoring_ports.py` — añadir método
  `get_achievements_for_domestic_leagues(season: str, league_names: list[str]) -> list[CompetitionAchievement]`
  al Protocol `CompetitionAchievementRepositoryPort`.

- [ ] `src/sfa/infrastructure/repositories/competition_achievement_repository.py` — implementar
  `get_achievements_for_domestic_leagues`: SELECT con JOIN a `competitions` filtrando por
  `Competition.name IN league_names` y `season`.

- [ ] `src/sfa/application/use_cases/run_full_recalculation.py` — insertar
  `RefreshLeagueAchievementBonusesUseCase` en el pipeline entre
  `InferAllCompetitionAchievementsUseCase` y el loop de `CalculateAchievementBonusesUseCase`.
  Añadir resultado parcial al log final.

- [ ] `src/sfa/core/dependencies.py` — añadir factory
  `get_refresh_league_achievement_bonuses_use_case` inyectando los ports ya disponibles
  (`CompetitionAchievementRepository`, `ScoringRulesVersionRepository`). También actualizar
  `get_run_full_recalculation_use_case` para que pase el nuevo use case al constructor (o
  instanciarlo internamente como los otros sub-use-cases del pipeline).

## Checklist de implementación

- [ ] **Paso 1 — Port:** En `src/sfa/domain/scoring_ports.py`, añadir a
  `CompetitionAchievementRepositoryPort` el método:
  ```python
  async def get_achievements_for_domestic_leagues(
      self, season: str, league_names: list[str]
  ) -> list[CompetitionAchievement]: ...
  ```
  Este método debe retornar `CompetitionAchievement` completo (incluyendo `id`, `competition_id`,
  `team_id`, `phase`, `bonus_points`, `weight`) de todas las competiciones cuyo nombre esté en
  `league_names` para la temporada dada.

- [ ] **Paso 2 — Implementación del repositorio:** En
  `CompetitionAchievementRepository.get_achievements_for_domestic_leagues`:
  - JOIN `CompetitionAchievementModel` con `Competition` sobre `competition_id`
  - WHERE `Competition.name IN league_names` AND `CompetitionAchievementModel.season == season`
  - Retornar lista de `CompetitionAchievement` (frozen dataclass, no ORM model)

- [ ] **Paso 3 — Use case `RefreshLeagueAchievementBonusesUseCase`:**
  Crear `src/sfa/application/use_cases/refresh_league_achievement_bonuses.py` con:

  ```python
  DOMESTIC_LEAGUE_NAMES: list[str] = [
      "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
      "Primeira Liga", "Eredivisie", "Jupiler Pro League", "Süper Lig",
      "Scottish Premiership",
  ]
  ```

  Resultado frozen dataclass:
  ```python
  @dataclass(frozen=True)
  class RefreshLeagueAchievementBonusesResult:
      season: str
      rules_version_id: int
      achievements_refreshed: int
      achievements_skipped: int
      status: str
      error: str | None
  ```

  Lógica del `execute(season, rules_version_id)`:
  1. Cargar rules version; si no existe, retornar status `"failed"`.
  2. Obtener `domestic_league_bonuses = config.achievement_phase_bonuses.get("domestic_league", {})`.
     Si vacío, retornar status `"completed"` con 0 actualizaciones (no hay fases configuradas).
  3. Llamar `achievement_repo.get_achievements_for_domestic_leagues(season, DOMESTIC_LEAGUE_NAMES)`.
  4. Para cada achievement:
     - `new_bonus = domestic_league_bonuses.get(achievement.phase)` — si `None`, skip (fase no
       conocida en `domestic_league`; puede ser una fase de copa registrada en esa competition).
     - `new_weight = config.competition_bonus_weights.get(competition_name, 1.0)` — **problema:**
       `CompetitionAchievement` no lleva `competition_name`. Resolución: el método de repo
       retorna una lista enriquecida. Ver nota abajo.
     - Construir nuevo `CompetitionAchievement` con mismo `id`, `competition_id`, `team_id`,
       `season`, `phase`, pero `bonus_points=new_bonus` y `weight=new_weight`.
     - Llamar `achievement_repo.upsert_achievement(achievement)`.
     - Incrementar `achievements_refreshed`.

  **Nota sobre `competition_name` para `weight`:** el repositorio necesita retornar también
  el nombre de la competición para que el use case pueda resolver el `weight`. Dos opciones:
  - a) Crear un DTO local enriquecido `LeagueAchievementDTO` que extiende `CompetitionAchievement`
    con `competition_name: str`.
  - b) Añadir un segundo método de repo que retorne pares `(CompetitionAchievement, competition_name)`.
  - c) (elegida por simplicidad) El método de repo retorna
    `list[tuple[CompetitionAchievement, str]]` donde el segundo elemento es el nombre de la
    competición. No requiere nueva entidad de dominio.

  Actualizar el Port y la implementación para retornar `list[tuple[CompetitionAchievement, str]]`.

- [ ] **Paso 4 — Integrar en `RunFullRecalculationUseCase`:**
  - Importar `RefreshLeagueAchievementBonusesUseCase`.
  - Después del bloque `if infer_achievements`, añadir:
    ```python
    refresh_uc = RefreshLeagueAchievementBonusesUseCase(
        achievement_repo=self._achievement_repo,
        rules_version_repo=self._rules_version_repo,
    )
    refresh_result = await refresh_uc.execute(
        season=season,
        rules_version_id=rules_version_id,
    )
    logger.info(
        "[RunFullRecalculationUseCase] refresh_league_bonuses: "
        "refreshed=%d skipped=%d status=%s",
        refresh_result.achievements_refreshed,
        refresh_result.achievements_skipped,
        refresh_result.status,
    )
    ```
  - No se necesita propagar el resultado parcial al `RunFullRecalculationResult` (no hay campo
    nuevo en el DTO de resultado — evitar breaking change). Solo se loggea.

- [ ] **Paso 5 — Wiring en `core/dependencies.py`:**
  `RefreshLeagueAchievementBonusesUseCase` se instancia inline dentro de
  `RunFullRecalculationUseCase.execute` (igual que `CalculateScoresForRulesVersionUseCase` y
  `InferAllCompetitionAchievementsUseCase`). No requiere factory independiente en
  `dependencies.py` salvo que se quiera exponer como endpoint propio (no está en el scope
  de esta feature).

- [ ] **Paso 6 — Tests:** Crear
  `tests/use_cases/test_refresh_league_achievement_bonuses.py` con:

  `FakeCompetitionAchievementRepository` que implemente el Protocol completo incluyendo el
  nuevo método `get_achievements_for_domestic_leagues`. Almacena achievements en dict interno.

  `FakeScoringRulesVersionRepository` con un método `get_version_by_id` que retorne una
  `ScoringRulesVersion` con config de prueba.

  Casos de test obligatorios:
  - `test_updates_bonus_points_when_config_changed`: achievements con `bonus_points=7000`
    para fase `champion`; config tiene `champion: 12000`; after execute, el achievement
    en el fake tiene `bonus_points=12000`.
  - `test_skips_unknown_phase`: achievement con `phase="qualify_ko"` (copa, no `domestic_league`);
    debe quedar sin actualizar (`achievements_skipped=1`).
  - `test_no_op_when_no_achievements`: `get_achievements_for_domestic_leagues` retorna lista
    vacía; `achievements_refreshed=0`, `status="completed"`.
  - `test_fails_when_rules_version_not_found`: `get_version_by_id` retorna `None`;
    `status="failed"`, `error` contiene el id.
  - `test_updates_weight_from_config`: achievement con `weight=0.9` para "La Liga"; config
    tiene `competition_bonus_weights["La Liga"]=0.90` pero se cambia a `0.95`; after execute,
    weight es `0.95`.

- [ ] Verificar `pytest tests/` pasa con coverage ≥80%
- [ ] Verificar `flake8 src/ tests/` sin errores
- [ ] Verificar `isort --check-only src/ tests/` sin errores

## Agent Routing Brief

**DDD Designer needed:** no

Esta feature no requiere nuevas entidades de dominio. `CompetitionAchievement` ya modela
exactamente lo que se necesita actualizar (`bonus_points`, `weight`). El único cambio en
el modelo de datos es la firma de retorno del nuevo método de repositorio
(`list[tuple[CompetitionAchievement, str]]`), que es una convención de capa de aplicación,
no una entidad de dominio nueva.

## Verificación

1. Crear una nueva `ScoringRulesVersion` con `achievement_phase_bonuses.domestic_league.champion = 12000`
   (diferente al valor registrado en DB para los achievements existentes).
2. Lanzar `POST /api/v1/scoring/recalculate/full` con `rules_version_id=<nuevo>` y `season=2024`.
3. En los logs, verificar la línea:
   `[RunFullRecalculationUseCase] refresh_league_bonuses: refreshed=N skipped=M status=completed`
   donde `N > 0`.
4. Consultar `SELECT competition_id, team_id, phase, bonus_points FROM competition_achievements
   WHERE season='2024'` y verificar que los rows de ligas domésticas muestran `bonus_points=12000`
   para `phase='champion'`.
5. Consultar `SELECT player_id, achievement_bonus_pts FROM sfa_season_scores WHERE season='2024'`
   para un jugador campeón de liga y verificar que `achievement_bonus_pts` refleja el nuevo valor.
6. Ejecutar el mismo recálculo por segunda vez y verificar que los resultados son idénticos
   (idempotencia).
