# Plan: Refactor 0036 — Ingest API Call Reduction

## Objetivo

Reducir los API calls de `IngestCompetitionUseCase` de ~141 a ~10 por ejecución cuando
el Mundial está activo, sin perder datos de partidos en vivo ni romper ligas de club.

Dos optimizaciones ortogonales:
1. **Bulk fixtures** — 1 llamada de liga (`/fixtures?league=X&season=Y`) en vez de 1 por equipo.
2. **Skip completed** — no re-fetchear events/players para fixtures ya completados en DB.

---

## Archivos a crear

- [ ] `migrations/versions/XXXX_add_status_to_fixtures.py` — migración Alembic que añade
  columna `status VARCHAR(10) NOT NULL DEFAULT 'FT'` a la tabla `fixtures`

## Archivos a modificar

- [ ] `src/sfa/domain/ingestion_ports.py` — tres cambios:
  1. Añadir campo `status: str = "FT"` a `FixtureRawDTO`
  2. Añadir `fetch_league_fixtures(league_id, season) -> list[FixtureRawDTO]` a `FootballDataProviderPort`
  3. Añadir `get_completed_fixture_ids(competition_id, season) -> set[int]` a `IngestionRepositoryPort`

- [ ] `src/sfa/infrastructure/models/fixtures/models.py` — añadir columna
  `status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="FT")`

- [ ] `src/sfa/infrastructure/providers/api_football.py` — añadir método
  `fetch_league_fixtures(league_id, season) -> list[FixtureRawDTO]` que llama a
  `/fixtures?league=X&season=Y` y mapea incluyendo el campo `status` del fixture

- [ ] `src/sfa/infrastructure/repositories/ingestion_repository.py` — añadir método
  `get_completed_fixture_ids(competition_id, season) -> set[int]` que devuelve los
  `external_id` de fixtures con `status IN ('FT', 'AET', 'PEN')`; también actualizar
  `upsert_fixture` para persistir el campo `status`

- [ ] `src/sfa/application/use_cases/ingest_competition.py` — dos cambios en `execute()`:
  1. Phase 2: si `league.top_n is None`, sustituir el bucle de `fetch_team_fixtures` por
     una sola llamada `fetch_league_fixtures`; si `top_n` tiene valor, conservar el bucle actual
  2. Phase 3: consultar `get_completed_fixture_ids` antes del bucle de fixtures y saltar
     `fetch_fixture_events` + `fetch_fixture_players` para los fixtures ya completados en DB

- [ ] `tests/use_cases/test_ingest_stats_event.py` — actualizar `FakeFootballProvider` para
  implementar el nuevo método `fetch_league_fixtures` del Protocol
- [ ] `tests/use_cases/test_calculate_scores_for_rules_version.py` — ídem si el Fake ahí
  implementa `FootballDataProviderPort`
- [ ] `tests/use_cases/test_get_world_cup.py` — ídem si aplica

---

## Checklist de implementación

### Paso 0 — Baseline

- [ ] Correr `pytest tests/` y documentar los fallos preexistentes antes de tocar nada

### Paso 1 — Domain: `FixtureRawDTO.status`

- [ ] En `src/sfa/domain/ingestion_ports.py`, añadir campo `status: str = "FT"` al final
  de `FixtureRawDTO` (campo con default para no romper constructores existentes)

### Paso 2 — Domain: nuevo método en `FootballDataProviderPort`

- [ ] En `FootballDataProviderPort` (Protocol), añadir:
  ```python
  async def fetch_league_fixtures(
      self, league_id: int, season: int,
  ) -> list[FixtureRawDTO]: ...
  ```

### Paso 3 — Domain: nuevo método en `IngestionRepositoryPort`

- [ ] En `IngestionRepositoryPort` (Protocol), añadir:
  ```python
  async def get_completed_fixture_ids(
      self, competition_id: int, season: str,
  ) -> set[int]: ...
  ```

### Paso 4 — Modelo SQLAlchemy: columna `status`

- [ ] En `src/sfa/infrastructure/models/fixtures/models.py`, añadir:
  ```python
  status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="FT")
  ```

### Paso 5 — Migración Alembic

- [ ] Generar migración:
  ```bash
  alembic revision --autogenerate -m "add_status_to_fixtures"
  ```
- [ ] Revisar el archivo generado; asegurar que el `upgrade()` añade la columna con
  `server_default='FT'` y que `downgrade()` la elimina
- [ ] Aplicar: `alembic upgrade head`

### Paso 6 — Provider: `fetch_league_fixtures`

- [ ] En `src/sfa/infrastructure/providers/api_football.py`, añadir método:
  ```python
  async def fetch_league_fixtures(
      self, league_id: int, season: int,
  ) -> list[FixtureRawDTO]:
      data = await self._get("fixtures", {"league": league_id, "season": season})
      result: list[FixtureRawDTO] = []
      for f in data.get("response", []):
          try:
              played_at = datetime.fromisoformat(f["fixture"]["date"])
              result.append(
                  FixtureRawDTO(
                      external_id=f["fixture"]["id"],
                      home_team_external_id=f["teams"]["home"]["id"],
                      away_team_external_id=f["teams"]["away"]["id"],
                      home_team_name=f["teams"]["home"]["name"],
                      away_team_name=f["teams"]["away"]["name"],
                      round_str=f["league"]["round"],
                      league_name=f["league"]["name"],
                      played_at=played_at,
                      home_goals=f["goals"].get("home") or 0,
                      away_goals=f["goals"].get("away") or 0,
                      status=f["fixture"]["status"].get("short") or "NS",
                  )
              )
          except (KeyError, TypeError, ValueError) as exc:
              logger.warning("[fetch_league_fixtures] Skipping malformed fixture: %s", exc)
      return result
  ```
  - Nota: a diferencia de `fetch_team_fixtures`, este método NO filtra por status en la
    query (sin `status=FT-AET-PEN`) porque necesitamos ver todos los statuses para tomar
    decisiones en el use case.

### Paso 7 — Repository: `upsert_fixture` persiste `status`

- [ ] En `IngestionRepository.upsert_fixture`, añadir `status=fixture.status` (o recibir
  `status: str` como parámetro) en el `pg_insert().values(...)` y en el `on_conflict_do_update`
  para que siempre se actualice el status al último conocido
- [ ] Actualizar la firma del método en el Protocol `IngestionRepositoryPort` para incluir
  `status: str`
- [ ] Actualizar todas las llamadas a `upsert_fixture` en el use case para pasar `status`

### Paso 8 — Repository: `get_completed_fixture_ids`

- [ ] En `IngestionRepository`, añadir:
  ```python
  async def get_completed_fixture_ids(
      self, competition_id: int, season: str,
  ) -> set[int]:
      COMPLETED = {"FT", "AET", "PEN"}
      result = await self._session.execute(
          select(Fixture.external_id)
          .where(
              Fixture.competition_id == competition_id,
              Fixture.season == season,
              Fixture.status.in_(COMPLETED),
          )
      )
      return {row[0] for row in result.all()}
  ```

### Paso 9 — Use case: Phase 2 bulk fixtures

- [ ] En `IngestCompetitionUseCase.execute`, reemplazar la sección de Phase 2 con:
  ```python
  if league.top_n is None:
      # Bulk: 1 API call para toda la liga
      all_fixtures = await self._provider.fetch_league_fixtures(league.id, season)
  else:
      # Per-team: comportamiento original para ligas con top_n
      top_teams = sorted(standings, key=lambda s: s.position)[: league.top_n]
      all_fixtures = []
      seen: set[int] = set()
      for team_standing in top_teams:
          for fx in await self._provider.fetch_team_fixtures(
              team_standing.team_external_id, league.id, season
          ):
              if fx.external_id not in seen:
                  seen.add(fx.external_id)
                  all_fixtures.append(fx)
  ```
- [ ] Adaptar el bucle de procesamiento de fixtures para iterar sobre `all_fixtures`
  (ya deduplicado) y mantener `processed_fixture_ids` solo para el caso per-team

### Paso 10 — Use case: Phase 3 skip completed

- [ ] Tras obtener `competition_id` en Phase 1 (después de `upsert_competition`), consultar:
  ```python
  completed_ids = await self._repo.get_completed_fixture_ids(competition_id, season_str)
  ```
- [ ] Al inicio del procesamiento de cada fixture en Phase 3, añadir:
  ```python
  if fixture.external_id in completed_ids:
      # Fixture ya está en DB con datos completos — solo upsert fixture row y seguir
      fixture_db_id = await self._repo.upsert_fixture(
          fixture.external_id, competition_id,
          home_db_id, away_db_id,
          stage, season_str, fixture.played_at, matchday_num,
          status=fixture.status,
      )
      fixtures_processed += 1
      continue
  ```
  - Importante: hacer el `upsert_fixture` de todas formas (para actualizar status si cambió),
    pero saltar `fetch_fixture_events` y `fetch_fixture_players`
  - Solo ejecutar Phase 3 completa para fixtures con status vivo o no terminado

### Paso 11 — Fakes en tests

- [ ] Actualizar `FakeFootballProvider` en `tests/use_cases/test_ingest_stats_event.py`
  para implementar `fetch_league_fixtures` (puede retornar `[]` o los mismos fixtures
  que `fetch_team_fixtures` en el fixture de test)
- [ ] Verificar que todos los Fakes que implementan `FootballDataProviderPort` tienen
  el nuevo método (buscar con `grep -r "FakeFootball" tests/`)
- [ ] Verificar que los Fakes de `IngestionRepositoryPort` tienen `get_completed_fixture_ids`
  (por defecto puede retornar `set()`)

### Paso 12 — Tests nuevos

- [ ] En `tests/use_cases/test_ingest_stats_event.py` (o archivo nuevo
  `tests/use_cases/test_ingest_competition_api_reduction.py`), añadir:

  **Test A — bulk fixtures se usa cuando `top_n is None`:**
  - `LeagueConfig(top_n=None)` → el Fake registra que `fetch_league_fixtures` fue llamado
    y `fetch_team_fixtures` NO fue llamado

  **Test B — skip completed cuando el fixture ya está en DB como completado:**
  - `get_completed_fixture_ids` retorna `{9001}` (el fixture del test)
  - Verificar que `fetch_fixture_events` NO fue llamado para ese fixture
  - Verificar que `fetch_fixture_players` NO fue llamado para ese fixture
  - Verificar que `upsert_fixture` SÍ fue llamado (para actualizar status)

  **Test C — no skip cuando el fixture está en vivo (status "1H"):**
  - `get_completed_fixture_ids` retorna `set()` (fixture no está completado)
  - Verificar que `fetch_fixture_events` SÍ fue llamado

  **Test D — comportamiento per-team preservado cuando `top_n` tiene valor:**
  - `LeagueConfig(top_n=2)` → el Fake registra que `fetch_team_fixtures` fue llamado
    y `fetch_league_fixtures` NO fue llamado

### Paso 13 — Verificación CI

- [ ] `pytest tests/` pasa con coverage ≥80%
- [ ] `flake8 src/ tests/` sin errores
- [ ] `isort --check-only src/ tests/` sin errores

---

## Agent Routing Brief

**DDD Designer needed:** no

Este refactor no introduce nuevas entidades de dominio. Los cambios son:
- Un campo adicional en un DTO existente (`FixtureRawDTO.status`)
- Dos nuevos métodos en Protocols existentes (`FootballDataProviderPort`, `IngestionRepositoryPort`)
- Lógica de branch en el use case existente (no nueva entidad)
- Una columna nueva en un modelo de infraestructura existente

Ninguno de estos cambios requiere modelado DDD.

---

## Verificación end-to-end

1. **Contar calls antes del refactor** (en staging o local con logs):
   ```
   grep "requests_used" logs o añadir log al final de IngestCompetitionUseCase
   ```
   Resultado esperado pre-refactor: ~141 calls para el Mundial con 36 fixtures jugados.

2. **Aplicar migración** en la DB de desarrollo:
   ```bash
   alembic upgrade head
   ```

3. **Lanzar ingesta manual del Mundial**:
   ```bash
   # Via task o directamente
   ingest_competition_task(league_id=1, season=2026, force=True)
   ```
   Resultado esperado: ~10 calls (1 standings + 1 bulk fixtures + calls solo para
   fixtures vivos/nuevos).

4. **Verificar que los datos de partidos terminados no cambiaron**:
   - Player stats, events y player_events para fixtures FT deben ser idénticos
     a antes del refactor.

5. **Verificar que partidos en vivo se siguen ingestando completos**:
   - Simular un fixture con status "1H" en el Fake y confirmar que Phase 3 ejecuta.

6. **Confirmar columna status en DB**:
   ```sql
   SELECT external_id, status FROM fixtures WHERE competition_id = <wc_id> LIMIT 10;
   ```
   Todos los partidos terminados deben tener status `FT`, `AET` o `PEN`.
