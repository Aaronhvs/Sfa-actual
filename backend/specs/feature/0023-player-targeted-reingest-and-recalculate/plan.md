# Plan: 0023 — Player Targeted Re-ingest and Recalculate

## Archivos a crear

- [ ] `src/sfa/application/use_cases/reingest_player.py` — `ReingestPlayerUseCase` + `ReingestPlayerResult`
- [ ] `src/sfa/tasks/reingest_player_task.py` — Celery task `reingest_player_task`
- [ ] `tests/use_cases/test_reingest_player.py` — Tests con Fakes

## Archivos a modificar

- [ ] `src/sfa/domain/ingestion_ports.py` — Agregar `PlayerFixtureInfoRow` DTO y método `get_fixtures_for_player` al Protocol
- [ ] `src/sfa/domain/name_matching.py` — Exponer `name_matches(event_name, player_name) -> bool` (mover desde `ingest_competition.py` si no existe)
- [ ] `src/sfa/application/use_cases/ingest_competition.py` — Reemplazar `_name_matches` local por import desde `domain/name_matching.py` (si se movió)
- [ ] `src/sfa/infrastructure/repositories/ingestion_repository.py` — Implementar `get_fixtures_for_player`
- [ ] `src/sfa/core/dependencies.py` — Agregar factory `get_reingest_player_use_case`
- [ ] `src/sfa/api/v1/admin.py` — Agregar endpoint `POST /players/{player_id}/reingest`
- [ ] `http/admin.http` — Agregar casos de prueba para el nuevo endpoint

## Checklist de implementación

### Fase 1 — Domain: name_matches helper

- [ ] **1.1** Inspeccionar `src/sfa/domain/name_matching.py` — verificar si ya existe una función
  `name_matches(a: str, b: str) -> bool` compatible con la lógica de `_name_matches` en
  `ingest_competition.py`. La lógica a replicar:
  ```python
  def name_matches(event_name: str | None, stats_name: str) -> bool:
      if not event_name:
          return False
      a = event_name.lower().strip()
      b = stats_name.lower().strip()
      if a == b or a in b or b in a:
          return True
      # Abbreviated first names: "E. Haaland" → "haaland" in "erling haaland"
      import re
      abbr = re.match(r'^[a-záéíóúàèìòùäëïöüâêîôûñç]\.\s+(.+)$', a)
      if abbr and abbr.group(1) in b:
          return True
      return False
  ```
- [ ] **1.2** Si la función no existe en `domain/name_matching.py`, agregarla con ese nombre exacto
  y signature. No duplicar — mover la lógica.
- [ ] **1.3** En `ingest_competition.py`, reemplazar la función `_name_matches` local por:
  ```python
  from sfa.domain.name_matching import name_matches as _name_matches
  ```
  Verificar que todos los call sites internos del use case siguen funcionando.

### Fase 2 — Domain: nuevo DTO y método en IngestionRepositoryPort

- [ ] **2.1** Agregar al final de `src/sfa/domain/ingestion_ports.py`, antes de la clase
  `ScoringRepositoryPort`, el siguiente DTO:
  ```python
  @dataclass(frozen=True)
  class PlayerFixtureInfoRow:
      fixture_id: int            # internal DB id
      fixture_external_id: int   # API-Football fixture id
      season: str
      competition_id: int
      home_team_id: int
      away_team_id: int
      player_team_id: int        # team the player belongs to in this fixture
      player_name: str           # player name (for name matching against event names)
      stage: str                 # competition stage string (e.g. "regular", "final")
  ```
- [ ] **2.2** Agregar el método `get_fixtures_for_player` al Protocol `IngestionRepositoryPort`:
  ```python
  async def get_fixtures_for_player(
      self,
      player_id: int,
      season: str,
      competition_id: int | None = None,
  ) -> list[PlayerFixtureInfoRow]: ...
  ```
  Ubicarlo junto a los demás métodos `get_*` del Protocol (después de `get_fixture_counts_by_competition`).

### Fase 3 — Infrastructure: implementación SQL

- [ ] **3.1** Implementar `get_fixtures_for_player` en `IngestionRepository`
  (`src/sfa/infrastructure/repositories/ingestion_repository.py`).

  Query base con SQLAlchemy 2.0 async (sin texto plano):
  ```
  SELECT
      f.id,
      f.external_id,
      f.season,
      f.competition_id,
      f.home_team_id,
      f.away_team_id,
      ps.team_id AS player_team_id,
      p.name     AS player_name,
      COALESCE(cs.stage, 'regular') AS stage
  FROM fixtures f
  JOIN player_stats ps ON ps.fixture_id = f.id
  JOIN players p ON p.id = ps.player_id
  LEFT JOIN competition_stages cs
      ON cs.competition_id = f.competition_id
      AND cs.stage = f.stage
  WHERE
      ps.player_id = :player_id
      AND f.season = :season
      [AND f.competition_id = :competition_id]
  ORDER BY f.id
  ```

  Retornar `list[PlayerFixtureInfoRow]`. Si la lista está vacía, retornar `[]` sin
  lanzar excepción.

  Nota: `PlayerStats` puede no tener `team_id` — verificar el modelo ORM. Si
  `PlayerStats.team_id` no existe, deducir `player_team_id` desde `Player.team_id` (JOIN
  con players ya está en la query). Usar `p.team_id` como fallback si `ps.team_id` es NULL.

### Fase 4 — Application: ReingestPlayerUseCase

- [ ] **4.1** Crear `src/sfa/application/use_cases/reingest_player.py`.

  Cabecera obligatoria:
  ```python
  from __future__ import annotations
  ```

  Result DTO:
  ```python
  @dataclass(frozen=True)
  class ReingestPlayerResult:
      player_id: int
      season: str
      fixtures_reingested: int
      events_ingested: int       # goal/assist events insertados en esta ejecución
      scores_recalculated: int   # eventos re-scored (de CalculateScoresForRulesVersionResult)
      status: str                # "ok" | "failed" | "no_fixtures"
      error: str | None
  ```

  Constructor del use case:
  ```python
  class ReingestPlayerUseCase:
      def __init__(
          self,
          provider: FootballDataProviderPort,
          ingestion_repo: IngestionRepositoryPort,
          rules_version_repo: ScoringRulesVersionRepositoryPort,
          scoring_use_case: CalculateScoresForRulesVersionUseCase,
      ) -> None:
  ```
  (Nota: `PlayerEventScoreRepositoryPort` no es necesario como dependencia directa;
  `CalculateScoresForRulesVersionUseCase` ya lo encapsula internamente.)

- [ ] **4.2** Implementar `execute(player_id: int, season: int, competition_id: int | None = None)`:

  ```
  1. rules_version = await rules_version_repo.get_active_version()
     → si None: return ReingestPlayerResult(status="failed", error="no active rules version", ...)

  2. season_str = str(season)

  3. fixtures = await ingestion_repo.get_fixtures_for_player(player_id, season_str, competition_id)
     → si []: return ReingestPlayerResult(status="no_fixtures", fixtures_reingested=0, ...)

  4. player_name = fixtures[0].player_name  # mismo jugador en todos los rows

  5. events_ingested = 0
     for row in fixtures:
       a. await ingestion_repo.delete_player_events_for_fixture(player_id, row.fixture_id)

       b. raw_events = await provider.fetch_fixture_events(row.fixture_external_id)
          is_away = (row.player_team_id == row.away_team_id)

          # Calcular score_before para M3 context
          home_goals, away_goals = _compute_score_at_start(raw_events)  # helper interno

          for evt in raw_events:
              evt_type = _map_event_type(evt.type, evt.detail)  # GOAL, ASSIST, YELLOW_CARD, etc.
              if evt_type is None:
                  continue
              target_name = evt.player_name if evt_type != EventType.ASSIST else evt.assist_name
              if not name_matches(target_name, player_name):
                  continue
              score_diff = _score_diff_at_minute(raw_events, evt.minute, row.home_team_id, is_away)
              score_before_str = _format_score_before(raw_events, evt.minute, row.home_team_id)
              await ingestion_repo.upsert_player_event(
                  player_id=player_id,
                  fixture_id=row.fixture_id,
                  minute=evt.minute + evt.extra_minute,
                  event_type=evt_type,
                  score_before=score_before_str,
                  score_diff=score_diff,
                  psxg=None,          # no disponible en /fixtures/events
                  m1=1.0, m2=1.0, m3=1.0, m4=1.0, mvisit=1.0, pts=0.0,
                  player_team_pos=None,
                  rival_team_pos=None,
                  is_away=is_away,
              )
              events_ingested += 1

       c. all_stats = await provider.fetch_all_fixture_players(row.fixture_external_id)
          player_stats = next(
              (s for s in all_stats if s.player_external_id == player_external_id),
              None,
          )
          if player_stats:
              stats_dict = _stats_to_dict(player_stats)  # helper: DTO → dict
              await ingestion_repo.upsert_player_stats(
                  player_id, row.fixture_id, season_str, stats_dict
              )

  6. scoring_result = await scoring_use_case.execute(
         rules_version_id=rules_version.id,
         season=season_str,
         competition_id=competition_id,
         player_id=player_id,
         force_recalculate=True,
     )

  7. return ReingestPlayerResult(
         player_id=player_id,
         season=season_str,
         fixtures_reingested=len(fixtures),
         events_ingested=events_ingested,
         scores_recalculated=scoring_result.events_calculated,
         status="ok",
         error=None,
     )
  ```

- [ ] **4.3** Determinar cómo obtener `player_external_id` dentro del execute para filtrar stats.
  Opciones en orden de preferencia:
  1. Agregar campo `player_external_id: int` al `PlayerFixtureInfoRow` (JOIN con `players.external_id`)
  2. O pasar `player_external_id` como parámetro opcional al `execute` (el router lo puede incluir)

  **Decisión de implementación**: agregar `player_external_id: int` al DTO `PlayerFixtureInfoRow`
  y al JOIN en `get_fixtures_for_player`. Es O(0) de complejidad extra en la query.

- [ ] **4.4** Helpers privados del módulo (no métodos del use case, funciones libres en el mismo archivo):
  - `_map_event_type(type_str: str, detail_str: str) -> EventType | None` — mapea strings de
    API-Football ("Goal", "Card", etc.) a `EventType`. Solo GOAL, ASSIST, YELLOW_CARD,
    RED_CARD relevantes. Retorna None para tipos irrelevantes.
  - `_score_diff_at_minute(events, minute, home_team_id, is_away) -> int | None` — diferencia
    de score desde la perspectiva del equipo del jugador justo antes del minuto dado.
  - `_format_score_before(events, minute, home_team_id) -> str | None` — formato "1-0" antes
    del evento.

  Reutilizar la lógica ya existente en `APIFootballProvider.get_score_at_minute` si es posible
  (pero no importar infra desde application). Reimplementar localmente o extraer a
  `domain/` si la lógica se reutiliza.

### Fase 5 — Celery Task

- [ ] **5.1** Crear `src/sfa/tasks/reingest_player_task.py`:
  ```python
  from celery import shared_task

  @shared_task(
      name="sfa.reingest_player",
      bind=True,
      max_retries=2,
      default_retry_delay=60,
  )
  def reingest_player_task(
      self,
      player_id: int,
      season: int,
      competition_id: int | None = None,
  ) -> dict:
      # Late imports para evitar circular imports
      import asyncio
      from sfa.infrastructure.database import AsyncSessionLocal
      from sfa.infrastructure.repositories.ingestion_repository import IngestionRepository
      from sfa.infrastructure.repositories.scoring_rules_version_repository import ScoringRulesVersionRepository
      from sfa.infrastructure.providers.api_football import APIFootballProvider
      from sfa.core.config import get_settings
      from sfa.application.use_cases.reingest_player import ReingestPlayerUseCase
      from sfa.application.use_cases.calculate_scores_for_rules_version import CalculateScoresForRulesVersionUseCase
      from sfa.infrastructure.repositories.player_event_score_repository import PlayerEventScoreRepository

      async def _run() -> dict:
          settings = get_settings()
          provider = APIFootballProvider(settings.api_football_key, settings.api_football_base_url)
          async with AsyncSessionLocal() as session:
              ingestion_repo = IngestionRepository(session)
              rules_version_repo = ScoringRulesVersionRepository(session)
              event_score_repo = PlayerEventScoreRepository(session)
              scoring_uc = CalculateScoresForRulesVersionUseCase(rules_version_repo, event_score_repo)
              uc = ReingestPlayerUseCase(provider, ingestion_repo, rules_version_repo, scoring_uc)
              result = await uc.execute(player_id, season, competition_id)
              await session.commit()
              return {
                  "player_id": result.player_id,
                  "season": result.season,
                  "fixtures_reingested": result.fixtures_reingested,
                  "events_ingested": result.events_ingested,
                  "scores_recalculated": result.scores_recalculated,
                  "status": result.status,
                  "error": result.error,
              }

      try:
          return asyncio.run(_run())
      except Exception as exc:
          raise self.retry(exc=exc)
  ```

### Fase 6 — DI Wiring

- [ ] **6.1** Agregar factory en `src/sfa/core/dependencies.py`:
  ```python
  async def get_reingest_player_use_case(
      provider: Annotated[APIFootballProvider, Depends(get_api_football_provider)],
      ingestion_repo: Annotated[IngestionRepository, Depends(get_ingestion_repository)],
      rules_version_repo: Annotated[ScoringRulesVersionRepository, Depends(get_scoring_rules_version_repository)],
      scoring_uc: Annotated[CalculateScoresForRulesVersionUseCase, Depends(get_calculate_scores_for_rules_version_use_case)],
  ) -> ReingestPlayerUseCase:
      from sfa.application.use_cases.reingest_player import ReingestPlayerUseCase
      return ReingestPlayerUseCase(provider, ingestion_repo, rules_version_repo, scoring_uc)
  ```
  Agregar junto a las demás factories de use cases de admin.

### Fase 7 — Router

- [ ] **7.1** Agregar al final de `src/sfa/api/v1/admin.py`:
  ```python
  from sfa.tasks.reingest_player_task import reingest_player_task

  @router.post("/players/{player_id}/reingest", status_code=status.HTTP_202_ACCEPTED)
  async def trigger_player_reingest(
      player_id: int,
      season: int = Query(default=CURRENT_SEASON),
      competition_id: int | None = Query(default=None),
  ) -> dict:
      """Re-ingest events and stats for a specific player, then recalculate their scores."""
      task = reingest_player_task.delay(player_id, season, competition_id)
      return {
          "task_id": task.id,
          "player_id": player_id,
          "season": season,
          "competition_id": competition_id,
          "status": "queued",
      }
  ```

- [ ] **7.2** Agregar casos de prueba en `http/admin.http`:
  ```http
  ### Re-ingest + recalculate Vinicius Jr in La Liga 2025
  POST http://localhost:8000/api/v1/admin/players/889/reingest?season=2025
  Content-Type: application/json

  ###

  ### Re-ingest with competition filter
  POST http://localhost:8000/api/v1/admin/players/889/reingest?season=2025&competition_id=3
  Content-Type: application/json

  ###

  ### Re-ingest player with no fixtures (expects no_fixtures)
  POST http://localhost:8000/api/v1/admin/players/99999/reingest?season=2025
  Content-Type: application/json
  ```

### Fase 8 — Tests

- [ ] **8.1** Crear `tests/use_cases/test_reingest_player.py`.

  Fakes requeridos (todos implementan el Protocol completo):
  - `FakeIngestionRepository(IngestionRepositoryPort)` — `get_fixtures_for_player` retorna
    lista configurable; `delete_player_events_for_fixture` registra llamadas;
    `upsert_player_event` registra llamadas; `upsert_player_stats` registra llamadas.
    Todos los demás métodos del Protocol retornan valores dummy.
  - `FakeFootballDataProvider(FootballDataProviderPort)` — `fetch_fixture_events` retorna
    lista configurable de `FixtureEventRawDTO`; `fetch_all_fixture_players` retorna lista
    configurable de `PlayerStatsRawDTO`.
  - `FakeScoringRulesVersionRepository(ScoringRulesVersionRepositoryPort)` — `get_active_version`
    retorna `ScoringRulesVersion` configurable o `None`.
  - `FakeCalculateScoresForRulesVersionUseCase` — clase simple con método `execute` que
    retorna `CalculateScoresForRulesVersionResult(events_calculated=N, status="ok", ...)`.
    No implementa un Protocol (el use case no tiene Protocol en SFA).

  Tests obligatorios (marker `@pytest.mark.anyio` en todos):

  - [ ] `test_execute_ok_reingests_fixtures_and_calls_scoring` —
    Dado un jugador con 2 fixtures, `fetch_fixture_events` retorna un goal event que matchea
    el nombre, `fetch_all_fixture_players` retorna stats. Verificar:
    - `delete_player_events_for_fixture` llamado 2 veces (una por fixture)
    - `upsert_player_event` llamado al menos 1 vez (el goal que matcheó)
    - `upsert_player_stats` llamado 2 veces
    - `scoring_use_case.execute` llamado con `player_id` correcto
    - resultado `status="ok"`, `fixtures_reingested=2`

  - [ ] `test_execute_no_fixtures_returns_no_fixtures_status` —
    `get_fixtures_for_player` retorna `[]`. Verificar `status="no_fixtures"`,
    `fixtures_reingested=0`, `scoring_use_case.execute` NO llamado.

  - [ ] `test_execute_no_active_rules_version_returns_failed` —
    `get_active_version()` retorna `None`. Verificar `status="failed"`,
    `error` contiene "no active rules version".

  - [ ] `test_execute_goal_event_matched_creates_event` —
    `fetch_fixture_events` devuelve un `FixtureEventRawDTO(type="Goal", detail="Normal Goal",
    player_name="V. Junior", ...)`. Player name en DB es "Vinicius Junior". Verificar que
    `upsert_player_event` es llamado con `event_type=EventType.GOAL`.

  - [ ] `test_execute_goal_event_name_no_match_skips_event` —
    `fetch_fixture_events` devuelve goal con `player_name="K. Benzema"`. Player name es
    "Vinicius Junior". Verificar que `upsert_player_event` NO es llamado.

  - [ ] `test_execute_assist_event_matched_creates_event` —
    `fetch_fixture_events` devuelve evento con `type="Goal"`, `assist_name="V. Junior"`.
    Verificar que `upsert_player_event` es llamado con `event_type=EventType.ASSIST`.

- [ ] Verificar `pytest tests/` pasa con coverage ≥80%
- [ ] Verificar `flake8 src/ tests/` sin errores
- [ ] Verificar `isort --check-only src/ tests/` sin errores

## Agent Routing Brief

**DDD Designer needed:** no

Esta feature no requiere nuevas entidades de dominio. El problema es datos corruptos
en infraestructura: eventos de goles/asistencias que no fueron asociados al jugador correcto
durante la ingesta original. La solución es un nuevo use case de aplicación que orquesta
ports existentes con una extensión mínima al `IngestionRepositoryPort` (nuevo método
`get_fixtures_for_player` y DTO `PlayerFixtureInfoRow`). Todos los value objects y entidades
de scoring ya existen en el dominio.

## Verificación

1. Confirmar que Vinicius (player_id=889) tiene 0 eventos GOAL en `player_events` para
   season=2025 antes de ejecutar:
   ```sql
   SELECT event_type, count(*) FROM player_events pe
   JOIN fixtures f ON f.id = pe.fixture_id
   WHERE pe.player_id = 889 AND f.season = '2025'
   GROUP BY event_type;
   ```

2. Disparar el endpoint:
   ```
   POST http://localhost:8000/api/v1/admin/players/889/reingest?season=2025
   ```
   Verificar respuesta `202` con `task_id`.

3. Monitorear tarea Celery hasta completar. Verificar en logs que se procesaron ~36 fixtures
   y se ingresaron eventos GOAL/ASSIST.

4. Confirmar eventos creados:
   ```sql
   SELECT event_type, count(*) FROM player_events pe
   JOIN fixtures f ON f.id = pe.fixture_id
   WHERE pe.player_id = 889 AND f.season = '2025'
   GROUP BY event_type;
   -- Esperado: GOAL ≥ 9, ASSIST ≥ 8, STATS = 36
   ```

5. Confirmar score actualizado en `sfa_season_scores`:
   ```sql
   SELECT total_pts, breakdown FROM sfa_season_scores
   WHERE player_id = 889 AND season = '2025'
   ORDER BY total_pts DESC;
   ```
   El `breakdown` debe mostrar `goals` y `assists` > 0.

6. Verificar idempotencia: disparar el endpoint una segunda vez. Los conteos en
   `player_events` deben ser idénticos (no duplicados).
