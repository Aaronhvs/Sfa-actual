# Plan: Compare Extended — Comparador enriquecido head-to-head

## Archivos a crear

- [ ] `src/sfa/application/use_cases/compare_extended.py` — use case + result dataclasses
- [ ] `tests/use_cases/test_compare_extended.py` — suite completa con Fakes
- [ ] `http/compare_extended.http` — ejemplos del nuevo endpoint

## Archivos a modificar

- [ ] `src/sfa/domain/ports.py` — añadir método al Protocol
- [ ] `src/sfa/infrastructure/repositories/player_event_repository.py` — implementar método nuevo
- [ ] `src/sfa/api/v1/schemas/compare.py` — añadir schemas del response extendido
- [ ] `src/sfa/api/v1/compare.py` — añadir handler GET /compare/extended
- [ ] `src/sfa/core/dependencies.py` — nueva factory DI

---

## Checklist de implementación

### Fase 1 — Domain: nuevo método en el Protocol

- [ ] En `domain/ports.py`, añadir método a `PlayerEventRepositoryProtocol`:

  ```python
  async def get_all_season_stats_for_player(
      self,
      player_id: int,
      season: str,
  ) -> PlayerSeasonStatsDTO | None: ...
  ```

  **Criterio:** el Protocol es `@runtime_checkable`; añadir el método no rompe
  implementaciones existentes si se agrega también en `PlayerEventRepository`.

- [ ] Verificar que `PlayerSeasonStatsDTO` en `domain/ports.py` tiene todos los campos
  necesarios: `passes_key`, `fouls_committed`, `cards_yellow`, `cards_red`,
  `dribble_success_rate`, `duel_win_rate`. Confirmar leyendo el dataclass existente.
  **No crear campos nuevos** — todos existen desde spec 0010.

### Fase 2 — Infrastructure: implementar get_all_season_stats_for_player

- [ ] En `infrastructure/repositories/player_event_repository.py`, añadir método
  `get_all_season_stats_for_player`:
  - JOIN: `player_stats` → `fixtures` (para filtrar por `season`)
  - WHERE: `player_stats.player_id = :player_id` AND `fixtures.season = :season`
  - SIN filtro `competition_id`
  - SELECT: mismo conjunto de columnas que `get_player_season_stats` (SUM, AVG)
  - Si no hay filas o `matches == 0`, retornar `None`
  - Retornar `PlayerSeasonStatsDTO` con `competition_id=0` como sentinel
  - `dribble_success_rate` y `duel_win_rate`: calcular igual que en el método existente

  **Criterio:** ejecutar `pytest tests/` y que no haya regresiones; el Fake de los
  tests del use case debe implementar también este método.

### Fase 3 — Application: PlayerExtendedStats + CompareExtendedResult

- [ ] Crear `src/sfa/application/use_cases/compare_extended.py` con:

  **Dataclasses de resultado** (todos `frozen=True`):

  ```
  PlayerExtendedStats
  CompareExtendedResult
  ```

  Campos exactos descritos en `decisions.md` sección "Domain Model".

  **Regla de seguridad:** ningún campo de `PlayerExtendedStats` puede contener
  `rating`, `rating_avg` ni nada derivado de ellos.

- [ ] Implementar `CompareExtendedUseCaseProtocol` (`@runtime_checkable`, `Protocol`):

  ```python
  async def execute(
      self,
      player_a_id: int,
      player_b_id: int,
      season: str | None = None,
  ) -> CompareExtendedResult: ...
  ```

- [ ] Implementar `CompareExtendedUseCase`:
  - Constructor recibe `score_repo: SFAScoreRepositoryProtocol` y
    `event_repo: PlayerEventRepositoryProtocol`
  - Internamente reutiliza `GetPlayerDetailUseCase(score_repo)` para resolver
    identidad y breakdown de ambos jugadores (mismo patrón que `ComparePlayersUseCase`)
  - Llama `event_repo.get_events_by_player(player_id, season)` para cada jugador
  - Llama `event_repo.get_fixtures_by_player(player_id, season)` para cada jugador
  - Llama `event_repo.get_all_season_stats_for_player(player_id, season)` para cada jugador
  - Delega el cálculo de `PlayerExtendedStats` a una función privada `_build_extended_stats`
  - Propaga `PlayerNotFoundError` sin atraparla (el router la traduce a 404)

- [ ] Implementar `_build_extended_stats(detail, events, fixtures, season_stats)`:

  **Bloque 2 — Goles:**
  - `goals_open_play` = count de events donde `event_type == "goal"`
  - `goals_penalty` = count donde `event_type == "goal_penalty"`
  - `goals_shootout` = count donde `event_type == "goal_shootout"`
  - `goals_total` = suma de los tres
  - `penalty_goal_pct` = `goals_penalty / goals_total * 100` si `goals_total > 0` else `None`
  - `total_minutes` = `sum(f.minutes for f in fixtures)`
  - `goals_open_play_per90` = `goals_open_play / total_minutes * 90` si `total_minutes > 0` else `None`
  - `minutes_per_goal` = `total_minutes / goals_total` si `goals_total > 0` else `None`

  **Bloque 3 — Asistencias:**
  - `assists_total` = `detail.total_assists` (ya incluye corner_assist)
  - `corner_assists` = `detail.breakdown["corner_assist"].count` si existe en breakdown else `0`
  - `minutes_per_assist` = `total_minutes / assists_total` si `assists_total > 0` else `None`
  - `minutes_per_goal_contribution` = `total_minutes / (goals_total + assists_total)`
    si `(goals_total + assists_total) > 0` else `None`

  **Bloque 4 — Impacto crítico:**
  - `critical_goals_assists` = count de events donde `event_type in {"goal", "goal_penalty",
    "goal_shootout", "assist", "corner_assist"}` AND `m3 >= 1.6`
  - `avg_m3_on_goals` = media de `event.m3` donde `event_type == "goal"` (solo jugada,
    excluir penalty y shootout); `None` si no hay ninguno
  - `avg_m1_on_goals` = media de `event.m1` donde `event_type == "goal"`; `None` si no hay
  - `elite_performances` = count de fixtures donde `sfa_pts >= 2500`
  - `decisive_goals` = count de events donde `event_type in {"goal", "goal_penalty"}`
    AND `score_diff is not None` AND `score_diff in {-1, 0}`

  **Bloque 5 — Eficiencia:**
  - `avg_sfa_pts_per_match` = `detail.sfa_pts / detail.matches` si `detail.matches > 0` else `None`
  - `home_sfa_pts_avg`: filtrar fixtures donde `f.home_team == detail.team`;
    media de `sfa_pts`; `None` si lista vacía
  - `away_sfa_pts_avg`: filtrar fixtures donde `f.away_team == detail.team`;
    media de `sfa_pts`; `None` si lista vacía
  - `max_scoring_streak`:
    1. Construir `scored_fixture_ids = {e.fixture_id for e in events if e.event_type in
       {"goal", "goal_penalty", "goal_shootout", "assist", "corner_assist"}}`
    2. Ordenar fixtures por `played_at ASC` (invertir la lista que viene DESC)
    3. Calcular racha máxima: recorrer, acumular `current` si `fixture_id in scored_fixture_ids`,
       resetear a 0 si no; actualizar `max_streak = max(max_streak, current)`
    4. Resultado: `max_streak` (int, nunca None)

  **Bloque 6 — Métricas por posición** (todos desde `season_stats`, `None` si `season_stats is None`):
  - `dribble_success_rate` = `season_stats.dribble_success_rate`
  - `shots_on_per_game` = `season_stats.shots_on / detail.matches` si `detail.matches > 0` else `None`
  - `passes_key_per_game` = `season_stats.passes_key / detail.matches` si `detail.matches > 0` else `None`
  - `xa_no_assist_pts` = `detail.breakdown["xa_no_assist"].pts` si existe else `None`
  - `duel_win_rate` = `season_stats.duel_win_rate`
  - `tackles_interceptions_per_game` = `(season_stats.tackles_won + season_stats.interceptions)
    / detail.matches` si `detail.matches > 0` else `None`

  **Bloque 7 — Disciplina** (desde `season_stats` y `detail.breakdown`):
  - `cards_yellow` = `season_stats.cards_yellow` si `season_stats` else `0`
  - `cards_red` = `season_stats.cards_red` si `season_stats` else `0`
  - `fouls_committed_per_game` = `season_stats.fouls_committed / detail.matches`
    si `season_stats and detail.matches > 0` else `None`
  - `pts_lost_discipline`:
    - Sumar `detail.breakdown["yellow_card"].pts` + `detail.breakdown["red_card"].pts`
      + `detail.breakdown["fouls_committed"].pts` (cada uno si existe en breakdown)
    - Resultado es negativo o cero; `None` si ninguno existe en breakdown

  **Criterio de completitud:** cada campo nombrado en el domain model de `decisions.md`
  tiene su lógica implementada. Los campos `None` siguen reglas documentadas arriba.
  No hay acceso a `f.rating` ni `season_stats.rating_avg` en ninguna parte.

### Fase 4 — Schemas Pydantic

- [ ] En `src/sfa/api/v1/schemas/compare.py`, añadir (sin modificar `CompareResponseSchema`):

  ```python
  class PlayerExtendedStatsSchema(BaseModel):
      # identidad
      id: int
      name: str
      team: str
      position: str
      competition: str
      photo_url: str | None
      global_rank: int
      competitions: list[str]
      # bloque 1
      sfa_pts: float
      matches: int
      # bloque 2
      goals_open_play: int
      goals_penalty: int
      goals_shootout: int
      goals_total: int
      penalty_goal_pct: float | None
      goals_open_play_per90: float | None
      minutes_per_goal: float | None
      total_minutes: int
      # bloque 3
      assists_total: int
      corner_assists: int
      minutes_per_assist: float | None
      minutes_per_goal_contribution: float | None
      # bloque 4
      critical_goals_assists: int
      avg_m3_on_goals: float | None
      avg_m1_on_goals: float | None
      elite_performances: int
      decisive_goals: int
      # bloque 5
      avg_sfa_pts_per_match: float | None
      home_sfa_pts_avg: float | None
      away_sfa_pts_avg: float | None
      max_scoring_streak: int
      # bloque 6
      dribble_success_rate: float | None
      shots_on_per_game: float | None
      passes_key_per_game: float | None
      xa_no_assist_pts: float | None
      duel_win_rate: float | None
      tackles_interceptions_per_game: float | None
      # bloque 7
      cards_yellow: int
      cards_red: int
      fouls_committed_per_game: float | None
      pts_lost_discipline: float | None

  class CompareExtendedResponseSchema(BaseModel):
      season: str
      player_a: PlayerExtendedStatsSchema
      player_b: PlayerExtendedStatsSchema
  ```

  **Criterio:** `rating` no aparece en ningún campo del schema. `CompareResponseSchema`
  no se toca.

### Fase 5 — Router: GET /compare/extended

- [ ] En `src/sfa/api/v1/compare.py`, añadir handler en el mismo `router`:

  ```python
  @router.get("/compare/extended", response_model=CompareExtendedResponseSchema)
  async def compare_players_extended(
      use_case: Annotated[CompareExtendedUseCase, Depends(get_compare_extended_use_case)],
      player_a: int = Query(...),
      player_b: int = Query(...),
      season: str | None = Query(default=None),
  ):
  ```

  - Importar `CompareExtendedUseCase` y `get_compare_extended_use_case`
  - Capturar `PlayerNotFoundError` → HTTP 404
  - Función `_extended_to_schema(r: PlayerExtendedStats) -> PlayerExtendedStatsSchema`
    que mapea campo a campo (sin lógica, solo mapping)

  **Criterio:** `GET /compare` sigue funcionando exactamente igual. El nuevo endpoint
  aparece en `/docs` bajo el tag "compare".

### Fase 6 — Wiring DI

- [ ] En `src/sfa/core/dependencies.py`, añadir:

  ```python
  from sfa.application.use_cases.compare_extended import CompareExtendedUseCase

  async def get_compare_extended_use_case(
      score_repo: Annotated[SFAScoreRepository, Depends(get_sfa_score_repository)],
      event_repo: Annotated[PlayerEventRepository, Depends(get_player_event_repository)],
  ) -> CompareExtendedUseCase:
      return CompareExtendedUseCase(score_repo, event_repo)
  ```

  **Criterio:** no hay wiring fuera de `dependencies.py`.

### Fase 7 — Tests

- [ ] Crear `tests/use_cases/test_compare_extended.py`

  **Estructura mínima de Fakes:**

  ```python
  class FakeSFAScoreRepository(SFAScoreRepositoryProtocol):
      # Implementa TODOS los métodos del Protocol
      # incluyendo get_total_player_stats

  class FakePlayerEventRepository(PlayerEventRepositoryProtocol):
      # Implementa TODOS los métodos del Protocol
      # incluyendo get_all_season_stats_for_player (nuevo)
  ```

  **Tests obligatorios (cada uno con `@pytest.mark.anyio`):**

  - `test_goals_breakdown_open_play_penalty_shootout` — verificar que los tres contadores
    se calculan correctamente desde events con distintos event_type
  - `test_penalty_goal_pct_zero_when_no_goals` — `penalty_goal_pct` es `None` cuando
    `goals_total == 0`
  - `test_goals_open_play_per90_none_when_no_minutes` — `None` cuando `total_minutes == 0`
  - `test_corner_assists_extracted_from_breakdown` — `corner_assists` viene del breakdown
    de `PlayerDetailResult`, no de events
  - `test_minutes_per_goal_contribution_none_when_no_contributions` — `None` cuando
    goals + assists == 0
  - `test_critical_goals_assists_m3_threshold` — solo cuenta eventos con `m3 >= 1.6`
  - `test_decisive_goals_score_diff_minus1_and_0` — solo cuenta goles con score_diff in {-1, 0}
  - `test_elite_performances_threshold_2500` — fixtures con sfa_pts >= 2500
  - `test_home_away_sfa_pts_avg_separation` — home vs away se separan por team name
  - `test_max_scoring_streak_consecutive_fixtures` — racha de 3 seguidos con gol
  - `test_max_scoring_streak_zero_when_no_goals` — racha 0 si el jugador no marcó/asistió
  - `test_pts_lost_discipline_sums_breakdown_keys` — suma yellow_card + red_card +
    fouls_committed del breakdown; `None` si no existen esas keys
  - `test_rating_not_exposed_in_result` — usar `dataclasses.fields(result.player_a)` para
    verificar que ningún campo se llama `rating` ni contiene "rating" en su nombre
  - `test_raises_player_not_found_when_player_a_missing`
  - `test_raises_player_not_found_when_player_b_missing`
  - `test_season_resolved_from_latest_when_none` — sin season explícita, se resuelve
    desde `latest_season_for_player`

  **Criterio:** `pytest tests/use_cases/test_compare_extended.py` pasa sin warnings.
  Cobertura del módulo `compare_extended.py` ≥ 90%.

### Fase 8 — HTTP file

- [ ] Crear `http/compare_extended.http`:
  - Happy path: dos jugadores reales con season explícita
  - Happy path: sin season (auto-resolve)
  - Error 404: player_a inexistente
  - Error 404: player_b inexistente

  **Criterio:** el archivo sigue el estilo de otros archivos en `http/` del proyecto.

### Fase 9 — Validación final

- [ ] `pytest tests/` pasa completo sin regresiones
- [ ] `flake8 src/ tests/` sin errores (max-line-length 120)
- [ ] `isort --check-only src/ tests/` sin errores
- [ ] `GET /api/v1/compare` sigue devolviendo `CompareResponseSchema` sin cambios
- [ ] `GET /api/v1/compare/extended` aparece en `/docs` con los 7 bloques
- [ ] Verificar manualmente que ningún campo del response de `/compare/extended`
  contiene `rating` o `rating_avg`

---

## Agent Routing Brief

**DDD Designer needed:** no

Los nuevos dataclasses (`PlayerExtendedStats`, `CompareExtendedResult`) son DTOs de
resultado del use case, no entidades de dominio con identidad ni invariantes. Son
equivalentes a `PlayerDetailResult` o `CompareResult` — plain frozen dataclasses.

El nuevo método `get_all_season_stats_for_player` es una variante query del método
existente `get_player_season_stats`, reutiliza el DTO existente `PlayerSeasonStatsDTO`.

No hay nuevos agregados, value objects, ni reglas de negocio que requieran diseño DDD.
