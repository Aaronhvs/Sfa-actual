# Plan: 0017 — ELO Team Ratings

## Archivos a crear

- [ ] `src/sfa/infrastructure/providers/clubelo_provider.py` — HTTP client CSV para ClubElo API; incluye `CLUBELO_NAME_MAP` y `ClubEloSnapshot` dataclass
- [ ] `src/sfa/infrastructure/services/elo_calculator.py` — `EloCalculatorService`: fórmula ELO, K-factors, normalización, función pura sin IO
- [ ] `src/sfa/application/use_cases/seed_clubelo.py` — `SeedClubEloUseCase`: descarga snapshot, hace name matching, escribe `team_strengths` con `source='clubelo_seed'`
- [ ] `src/sfa/application/use_cases/calculate_elo_ratings.py` — `CalculateEloRatingsUseCase`: ordena fixtures cronológicamente, itera, actualiza ELO, escribe con `source='elo_v1'`
- [ ] `src/sfa/tasks/elo_tasks.py` — `seed_clubelo_task` y `apply_elo_update_task` (wrappers sync→async)
- [ ] `src/sfa/api/v1/schemas/elo_schemas.py` — Pydantic schemas para request/response de endpoints admin
- [ ] `src/sfa/api/v1/elo_router.py` — Router `/admin/elo/` con seed y recalc endpoints
- [ ] `http/elo.http` — Archivo HTTP con todos los casos (happy path + errores)
- [ ] `tests/use_cases/test_seed_clubelo.py` — Tests `SeedClubEloUseCase` con Fake
- [ ] `tests/use_cases/test_calculate_elo_ratings.py` — Tests `CalculateEloRatingsUseCase` con Fake
- [ ] `alembic/versions/XXXX_add_elo_raw_to_team_strengths.py` — Migración: columna `elo_raw`, ampliar CHECK de `source`

## Archivos a modificar

- [ ] `src/sfa/domain/scoring_ports.py` — Agregar `TeamEloRow`, `FixtureEloRow` DTOs y 4 métodos nuevos a `TeamStrengthRepositoryPort`
- [ ] `src/sfa/infrastructure/models/team_strengths/models.py` — Agregar columna `elo_raw NUMERIC(7,2) NULLABLE`; ampliar `ck_team_strength_source` a incluir `'clubelo_seed'` y `'elo_v1'`
- [ ] `src/sfa/infrastructure/repositories/team_strength_repository.py` — Implementar 4 métodos nuevos del Protocol
- [ ] `src/sfa/tasks/ingestion_tasks.py` — En `_run_ingest_competition`, después del commit, disparar `apply_elo_update_task.delay(season, league_id)`
- [ ] `src/sfa/core/dependencies.py` — Factories para `SeedClubEloUseCase` y `CalculateEloRatingsUseCase`
- [ ] `src/sfa/api/v1/main.py` — Registrar `elo_router`

## Checklist de implementación

### Paso 1 — Migración de DB

- [ ] Crear migración Alembic en `alembic/versions/`:
  ```sql
  -- up
  ALTER TABLE team_strengths ADD COLUMN elo_raw NUMERIC(7,2) NULL;
  ALTER TABLE team_strengths DROP CONSTRAINT ck_team_strength_source;
  ALTER TABLE team_strengths ADD CONSTRAINT ck_team_strength_source
      CHECK (source IN ('calculated', 'default', 'override', 'clubelo_seed', 'elo_v1'));

  -- down
  ALTER TABLE team_strengths DROP COLUMN elo_raw;
  ALTER TABLE team_strengths DROP CONSTRAINT ck_team_strength_source;
  ALTER TABLE team_strengths ADD CONSTRAINT ck_team_strength_source
      CHECK (source IN ('calculated', 'default', 'override'));
  ```

### Paso 2 — DTOs de dominio en `scoring_ports.py`

- [ ] Agregar al final de `src/sfa/domain/scoring_ports.py` (sin tocar los existentes):
  ```python
  @dataclass(frozen=True)
  class TeamEloRow:
      team_id: int
      season: str
      elo_raw: float       # ELO bruto (rango ~1400-2100)
      strength: float      # normalizado 0-100

  @dataclass(frozen=True)
  class FixtureEloRow:
      fixture_id: int
      home_team_id: int
      away_team_id: int
      played_at: datetime  # from datetime import datetime en el import block
      competition_id: int
      home_goals: int
      away_goals: int
      season: str
  ```
- [ ] Agregar los 4 métodos a `TeamStrengthRepositoryPort` (son non-breaking porque
  `Protocol` con `runtime_checkable` no fuerza implementación en instancias existentes,
  pero la implementación concreta DEBE tenerlos):
  ```python
  async def get_team_strength_with_elo(
      self, team_id: int, season: str, competition_id: int
  ) -> tuple[float | None, float | None]: ...
  # Returns (normalized_strength, elo_raw)

  async def upsert_team_elo(
      self,
      team_id: int,
      season: str,
      elo_raw: float,
      strength_normalized: float,
      source: str,
      competition_ids: list[int],
  ) -> None: ...

  async def get_all_teams_with_elo(self, season: str) -> list[TeamEloRow]: ...

  async def get_fixtures_for_elo_recalc(
      self, season: str, competition_ids: list[int]
  ) -> list[FixtureEloRow]: ...
  ```

### Paso 3 — ORM Model

- [ ] En `src/sfa/infrastructure/models/team_strengths/models.py`:
  - Agregar campo: `elo_raw: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)`
  - Reemplazar `CheckConstraint` de source:
    ```python
    CheckConstraint(
        "source IN ('calculated', 'default', 'override', 'clubelo_seed', 'elo_v1')",
        name="ck_team_strength_source",
    )
    ```

### Paso 4 — Repository: implementar métodos nuevos

- [ ] En `src/sfa/infrastructure/repositories/team_strength_repository.py`, implementar
  los 4 métodos nuevos:

  **`get_team_strength_with_elo`:**
  ```python
  stmt = select(TeamStrength.strength, TeamStrength.elo_raw).where(
      TeamStrength.team_id == team_id,
      TeamStrength.season == season,
      TeamStrength.competition_id == competition_id,
  )
  row = (await self._session.execute(stmt)).one_or_none()
  if row is None:
      return None, None
  return float(row.strength), float(row.elo_raw) if row.elo_raw is not None else None
  ```

  **`upsert_team_elo`:**
  Itera sobre `competition_ids` y para cada uno hace `pg_insert(TeamStrength).on_conflict_do_update`
  con `set_={"strength": strength_normalized, "elo_raw": elo_raw, "source": source}`.
  Si `competition_ids` está vacío, no escribe nada y loguea warning.

  **`get_all_teams_with_elo`:**
  ```python
  # Distinct por team_id (ELO es global — tomamos el primero encontrado)
  stmt = (
      select(TeamStrength.team_id, TeamStrength.elo_raw, TeamStrength.strength)
      .where(
          TeamStrength.season == season,
          TeamStrength.elo_raw.is_not(None),
      )
      .distinct(TeamStrength.team_id)
  )
  ```
  Retorna `list[TeamEloRow]`.

  **`get_fixtures_for_elo_recalc`:**
  ```python
  # JOIN fixtures + fixture_scores, WHERE competition_id IN (...) AND status='FT'
  # ORDER BY played_at ASC NULLS LAST
  # Retorna list[FixtureEloRow]
  ```
  Usar los modelos ORM de fixtures existentes. Si no existe modelo `FixtureScore`,
  verificar en `infrastructure/models/` el modelo correcto para goles.

### Paso 5 — `EloCalculatorService`

- [ ] Crear `src/sfa/infrastructure/services/elo_calculator.py`:
  ```python
  # Constantes
  ELO_FLOOR = 1400.0
  ELO_RANGE = 700.0   # 1400 + 700 = 2100 (max observado)
  ELO_DEFAULT = 1500.0  # ELO inicial para equipos sin seed

  # K factors por competition_id (configurable como parámetro)
  DEFAULT_K_FACTORS: dict[int, float] = {}  # vacío — se pasa por parámetro al use case

  class EloCalculatorService:

      @staticmethod
      def normalize(elo: float) -> float:
          """Convierte ELO bruto (1400-2100) a escala 0-100."""
          normalized = (elo - ELO_FLOOR) / ELO_RANGE * 100.0
          return max(0.0, min(100.0, normalized))

      @staticmethod
      def expected_score(player_elo: float, rival_elo: float) -> float:
          return 1.0 / (1.0 + 10 ** ((rival_elo - player_elo) / 400.0))

      @staticmethod
      def actual_score(home_goals: int, away_goals: int, is_home: bool) -> float:
          if home_goals > away_goals:
              return 1.0 if is_home else 0.0
          elif home_goals == away_goals:
              return 0.5
          else:
              return 0.0 if is_home else 1.0

      @staticmethod
      def update_elo(
          current_elo: float,
          rival_elo: float,
          home_goals: int,
          away_goals: int,
          is_home: bool,
          k_factor: float,
      ) -> float:
          expected = EloCalculatorService.expected_score(current_elo, rival_elo)
          actual = EloCalculatorService.actual_score(home_goals, away_goals, is_home)
          return current_elo + k_factor * (actual - expected)
  ```

### Paso 6 — `ClubEloProvider`

- [ ] Crear `src/sfa/infrastructure/providers/clubelo_provider.py`:

  ```python
  import csv, io
  import difflib
  import httpx
  from dataclasses import dataclass

  CLUBELO_BASE_URL = "http://api.clubelo.com"
  CLUBELO_NAME_MAP: dict[str, str] = { ... }  # Dict completo de decisions.md

  @dataclass(frozen=True)
  class ClubEloEntry:
      club_name: str        # nombre original de ClubElo
      country: str
      level: int
      elo: float

  class ClubEloProvider:

      def __init__(self, timeout: float = 30.0) -> None:
          self._timeout = timeout

      async def fetch_snapshot(self, date_str: str) -> list[ClubEloEntry]:
          """
          Descarga el CSV de todos los equipos para una fecha dada.
          date_str format: 'YYYY-MM-DD'
          Raises: httpx.HTTPError si la API no responde
          """
          url = f"{CLUBELO_BASE_URL}/{date_str}"
          async with httpx.AsyncClient(timeout=self._timeout) as client:
              response = await client.get(url)
              response.raise_for_status()
          return _parse_csv(response.text)

      def resolve_team_name(self, clubelo_name: str, sfa_team_names: list[str]) -> str | None:
          """
          Resuelve nombre ClubElo → nombre SFA.
          1. Busca en CLUBELO_NAME_MAP
          2. Si no está, fuzzy match con difflib (cutoff 0.75)
          3. Si no hay match, retorna None
          """
          normalized = CLUBELO_NAME_MAP.get(clubelo_name, clubelo_name)
          if normalized in sfa_team_names:
              return normalized
          matches = difflib.get_close_matches(normalized, sfa_team_names, n=1, cutoff=0.75)
          return matches[0] if matches else None


  def _parse_csv(text: str) -> list[ClubEloEntry]:
      reader = csv.DictReader(io.StringIO(text))
      entries = []
      for row in reader:
          try:
              entries.append(ClubEloEntry(
                  club_name=row["Club"],
                  country=row["Country"],
                  level=int(row["Level"]),
                  elo=float(row["Elo"]),
              ))
          except (KeyError, ValueError):
              continue  # fila malformada — ignorar
      return entries
  ```

### Paso 7 — `SeedClubEloUseCase`

- [ ] Crear `src/sfa/application/use_cases/seed_clubelo.py`:

  ```python
  @dataclass(frozen=True)
  class SeedClubEloResult:
      date_str: str
      season: str
      matched: int           # equipos matcheados y escritos
      unmatched: list[str]   # nombres ClubElo sin match en SFA
      status: str
      error: str | None

  class SeedClubEloUseCase:
      def __init__(
          self,
          repo: TeamStrengthRepositoryPort,
          provider: ClubEloProvider,
      ) -> None: ...

      async def execute(
          self,
          date_str: str,    # 'YYYY-MM-DD' — fecha del snapshot ClubElo
          season: str,      # temporada SFA e.g. '2024'
      ) -> SeedClubEloResult:
          """
          1. Descarga snapshot de ClubElo para date_str
          2. Carga todos los team.name de la DB para el season
          3. Para cada entry de ClubElo Level=1 (solo 1ª división):
             a. resolve_team_name() → sfa_name
             b. Si match: normalizar ELO → strength; buscar team_id por sfa_name
             c. Obtener competition_ids activas del equipo en esa season
             d. upsert_team_elo(source='clubelo_seed', ...)
          4. Retorna SeedClubEloResult con matched/unmatched
          """
  ```

  **Detalles importantes:**
  - Solo se procesan entries con `level=1` del CSV de ClubElo (primera división).
    Equipos de copas sin ELO seed recibirán fallback por standings.
  - El repo debe exponer un método para obtener `team_name → team_id` y
    `team_id → [competition_ids activos en esa season]`. Añadir estos a `TeamStrengthRepositoryPort`:

    ```python
    async def get_team_name_id_map(self, season: str) -> dict[str, int]: ...
    # {team.name: team.id} para equipos con partidos en esa temporada

    async def get_active_competition_ids_for_team(
        self, team_id: int, season: str
    ) -> list[int]: ...
    # competition_ids donde el equipo tiene fixtures en esa temporada
    ```
  - Estos 2 métodos adicionales hacen un total de **6 métodos nuevos** en el Protocol.

### Paso 8 — `CalculateEloRatingsUseCase`

- [ ] Crear `src/sfa/application/use_cases/calculate_elo_ratings.py`:

  ```python
  # K factors por defecto (pueden sobreescribirse vía parámetro)
  DEFAULT_K_FACTORS = {
      # competition_name → K
      # Champions League / Europa League / Conference League → 35
      # Ligas domésticas → 30
      # Copas domésticas → 25
  }
  # En la práctica se pasa como dict[int, float] (competition_id → K)
  # Los IDs se resuelven al momento de la llamada

  @dataclass(frozen=True)
  class CalculateEloRatingsResult:
      season: str
      fixtures_processed: int
      teams_updated: int
      status: str
      error: str | None

  class CalculateEloRatingsUseCase:
      def __init__(
          self,
          repo: TeamStrengthRepositoryPort,
          calculator: EloCalculatorService,
      ) -> None: ...

      async def execute(
          self,
          season: str,
          competition_ids: list[int],
          k_factors: dict[int, float],  # competition_id → K; default K=30 si no está
          default_k: float = 30.0,
      ) -> CalculateEloRatingsResult:
          """
          1. Cargar ELOs actuales: get_all_teams_with_elo(season) → dict[team_id, elo]
             Si equipo no tiene ELO seed, usar ELO_DEFAULT=1500.0
          2. Cargar fixtures ordenados: get_fixtures_for_elo_recalc(season, competition_ids)
             → list[FixtureEloRow] ORDER BY played_at ASC
          3. Para cada fixture en orden:
             a. Obtener elo_home, elo_away (del dict mutable en memoria)
             b. k = k_factors.get(fixture.competition_id, default_k)
             c. new_elo_home = EloCalculatorService.update_elo(elo_home, elo_away, ..., is_home=True, k)
             d. new_elo_away = EloCalculatorService.update_elo(elo_away, elo_home, ..., is_home=False, k)
             e. Actualizar dict en memoria
          4. Al final, para cada team_id en el dict:
             a. strength = EloCalculatorService.normalize(elo)
             b. competition_ids_team = get_active_competition_ids_for_team(team_id, season)
             c. upsert_team_elo(source='elo_v1', ...)
          5. Retornar result
          """
  ```

  **Punto crítico:** el ELO se calcula **en memoria** para todos los fixtures, luego se
  escribe al final en batch. No se escribe a DB después de cada fixture (evita N queries).

### Paso 9 — Tasks Celery

- [ ] Crear `src/sfa/tasks/elo_tasks.py`:

  ```python
  @celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
  def seed_clubelo_task(self, date_str: str, season: str):
      """One-time seed: descarga ClubElo y popula team_strengths."""
      try:
          asyncio.run(_run_seed(date_str, season))
      except Exception as exc:
          raise self.retry(exc=exc)

  @celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
  def apply_elo_update_task(self, season: str, competition_ids: list[int]):
      """Recalcula ELO para la season completa. Se dispara después de cada ingesta."""
      try:
          asyncio.run(_run_elo_update(season, competition_ids))
      except Exception as exc:
          raise self.retry(exc=exc)

  async def _run_seed(date_str: str, season: str) -> None:
      # late imports para evitar circular imports
      from sfa.application.use_cases.seed_clubelo import SeedClubEloUseCase
      from sfa.infrastructure.database import AsyncSessionLocal
      from sfa.infrastructure.providers.clubelo_provider import ClubEloProvider
      from sfa.infrastructure.repositories.team_strength_repository import TeamStrengthRepository
      ...

  async def _run_elo_update(season: str, competition_ids: list[int]) -> None:
      from sfa.application.use_cases.calculate_elo_ratings import CalculateEloRatingsUseCase
      from sfa.infrastructure.services.elo_calculator import EloCalculatorService
      from sfa.infrastructure.database import AsyncSessionLocal
      from sfa.infrastructure.repositories.team_strength_repository import TeamStrengthRepository
      ...
  ```

### Paso 10 — Hook en `ingestion_tasks.py`

- [ ] En `src/sfa/tasks/ingestion_tasks.py`, modificar `_run_ingest_competition`:
  ```python
  async def _run_ingest_competition(league_id: int, season: int):
      # ... código existente sin cambios ...
      await session.commit()

  # AGREGAR al final de la función (fuera del async with):
  from sfa.tasks.elo_tasks import apply_elo_update_task
  apply_elo_update_task.delay(str(season), [league_id])
  ```
  **Nota:** `league_id` aquí es el `competition_id` interno de SFA, que coincide con
  el `league_id` de API-Football. Verificar el mapeo en `IngestCompetitionUseCase`.

### Paso 11 — Router y Schemas

- [ ] Crear `src/sfa/api/v1/schemas/elo_schemas.py`:
  ```python
  class SeedClubEloRequest(BaseModel):
      date_str: str   # "YYYY-MM-DD"
      season: str     # "2024"

  class SeedClubEloResponse(BaseModel):
      date_str: str
      season: str
      matched: int
      unmatched: list[str]
      status: str
      error: str | None

  class RecalculateEloRequest(BaseModel):
      season: str
      competition_ids: list[int]
      k_factors: dict[int, float] = {}  # vacío = usar defaults
      default_k: float = 30.0

  class RecalculateEloResponse(BaseModel):
      season: str
      fixtures_processed: int
      teams_updated: int
      status: str
      error: str | None
  ```

- [ ] Crear `src/sfa/api/v1/elo_router.py`:
  ```python
  router = APIRouter(prefix="/admin/elo", tags=["elo"])

  @router.post("/seed", response_model=SeedClubEloResponse)
  async def seed_clubelo(
      body: SeedClubEloRequest,
      use_case: Annotated[SeedClubEloUseCase, Depends(get_seed_clubelo_use_case)],
  ) -> SeedClubEloResponse:
      """Descarga snapshot ClubElo y popula team_strengths (source=clubelo_seed)."""
      result = await use_case.execute(date_str=body.date_str, season=body.season)
      if result.status == "failed":
          raise HTTPException(status_code=503, detail=result.error)
      return SeedClubEloResponse(...)

  @router.post("/recalculate", response_model=RecalculateEloResponse)
  async def recalculate_elo(
      body: RecalculateEloRequest,
      use_case: Annotated[CalculateEloRatingsUseCase, Depends(get_calculate_elo_use_case)],
  ) -> RecalculateEloResponse:
      """Recalcula ELO propio procesando todos los fixtures en orden cronológico."""
      result = await use_case.execute(
          season=body.season,
          competition_ids=body.competition_ids,
          k_factors=body.k_factors,
          default_k=body.default_k,
      )
      if result.status == "failed":
          raise HTTPException(status_code=500, detail=result.error)
      return RecalculateEloResponse(...)
  ```

### Paso 12 — Wiring en `dependencies.py`

- [ ] En `src/sfa/core/dependencies.py`, agregar factories:
  ```python
  async def get_seed_clubelo_use_case(
      repo: Annotated[TeamStrengthRepository, Depends(get_team_strength_repository)],
  ) -> SeedClubEloUseCase:
      from sfa.infrastructure.providers.clubelo_provider import ClubEloProvider
      return SeedClubEloUseCase(repo=repo, provider=ClubEloProvider())

  async def get_calculate_elo_use_case(
      repo: Annotated[TeamStrengthRepository, Depends(get_team_strength_repository)],
  ) -> CalculateEloRatingsUseCase:
      from sfa.infrastructure.services.elo_calculator import EloCalculatorService
      return CalculateEloRatingsUseCase(repo=repo, calculator=EloCalculatorService())
  ```

### Paso 13 — Registrar router en `main.py`

- [ ] En `src/sfa/api/v1/main.py` (o donde se registran los routers):
  ```python
  from sfa.api.v1.elo_router import router as elo_router
  app.include_router(elo_router)
  ```

### Paso 14 — Archivo HTTP

- [ ] Crear `http/elo.http`:
  ```http
  ### Seed ClubElo snapshot
  POST http://localhost:8000/admin/elo/seed
  Content-Type: application/json

  {
    "date_str": "2024-08-01",
    "season": "2024"
  }

  ###

  ### Recalculate ELO ratings (todas las ligas)
  POST http://localhost:8000/admin/elo/recalculate
  Content-Type: application/json

  {
    "season": "2024",
    "competition_ids": [39, 140, 135, 78, 61],
    "k_factors": {"39": 30, "140": 30, "135": 30, "78": 30, "61": 30},
    "default_k": 30.0
  }

  ###

  ### Recalculate ELO con K alto para CL
  POST http://localhost:8000/admin/elo/recalculate
  Content-Type: application/json

  {
    "season": "2024",
    "competition_ids": [39, 2],
    "k_factors": {"2": 35, "39": 30},
    "default_k": 30.0
  }

  ###

  ### Error case: fecha inválida
  POST http://localhost:8000/admin/elo/seed
  Content-Type: application/json

  {
    "date_str": "not-a-date",
    "season": "2024"
  }
  ```

### Paso 15 — Tests

- [ ] Crear `tests/use_cases/test_seed_clubelo.py`:
  ```python
  # FakeTeamStrengthRepository implementa TeamStrengthRepositoryPort completo
  # FakeClubEloProvider retorna lista hardcodeada de ClubEloEntry

  class TestSeedClubEloUseCase:
      @pytest.mark.anyio
      async def test_seed_known_team_writes_elo_entry(self): ...
      # Dado: provider retorna ManCity con ELO=1950
      # Cuando: execute("2024-08-01", "2024")
      # Entonces: upsert llamado con elo_raw≈1950, strength≈(1950-1400)/700*100≈78.57, source='clubelo_seed'

      @pytest.mark.anyio
      async def test_seed_unknown_team_reported_as_unmatched(self): ...
      # Dado: provider retorna equipo sin match en SFA
      # Entonces: matched=0, len(unmatched)=1

      @pytest.mark.anyio
      async def test_seed_only_processes_level_1_entries(self): ...
      # Dado: provider retorna Level=1 y Level=2
      # Entonces: solo Level=1 procesado

      @pytest.mark.anyio
      async def test_seed_provider_error_returns_failed_result(self): ...
  ```

- [ ] Crear `tests/use_cases/test_calculate_elo_ratings.py`:
  ```python
  class TestCalculateEloRatingsUseCase:
      @pytest.mark.anyio
      async def test_single_fixture_updates_both_teams(self): ...
      # Dado: 1 fixture, home gana, ELO inicial iguales (1500)
      # Entonces: home_elo sube, away_elo baja

      @pytest.mark.anyio
      async def test_fixtures_processed_in_chronological_order(self): ...
      # Dado: 2 fixtures desordenados por date
      # Entonces: ELO final difiere si se procesa en el orden correcto vs invertido

      @pytest.mark.anyio
      async def test_team_without_seed_gets_default_elo(self): ...
      # Dado: equipo sin ELO en repo
      # Entonces: se usa ELO_DEFAULT=1500

      @pytest.mark.anyio
      async def test_k_factor_applied_per_competition(self): ...
      # Dado: 2 fixtures en competitions distintas con K diferente
      # Entonces: el delta ELO es proporcional al K factor

      @pytest.mark.anyio
      async def test_elo_written_normalized_and_raw(self): ...
      # Entonces: elo_raw=valor bruto, strength=normalizado 0-100
  ```

### Paso 16 — Verificaciones finales

- [ ] Correr migración Alembic en ambiente de desarrollo: `alembic upgrade head`
- [ ] Verificar que `pytest tests/` pasa con coverage ≥80%
- [ ] Verificar `flake8 src/ tests/` sin errores nuevos
- [ ] Verificar `isort --check-only src/ tests/` sin errores
- [ ] Seed manual: `POST /admin/elo/seed` con `date_str="2024-08-01"` y `season="2024"`;
  verificar que la respuesta muestra `matched >= 20` y lista de `unmatched` razonable
- [ ] Recalcular ELO: `POST /admin/elo/recalculate` con `season="2024"` y los
  `competition_ids` de las ligas en DB; verificar `fixtures_processed > 0`
- [ ] Consultar `team_strengths` en DB: `SELECT team_id, season, strength, elo_raw, source FROM team_strengths WHERE source='elo_v1' LIMIT 10;`
  — verificar que `elo_raw` es plausible (1400-2100) y `strength` está entre 0-100
- [ ] Disparar ingesta de un partido: verificar que `apply_elo_update_task` se encola
  automáticamente en Celery (revisar logs del worker)

## Agent Routing Brief

**DDD Designer needed: no**

La feature no requiere nuevas entidades de dominio. Las únicas adiciones al dominio son
dos DTOs frozen (`TeamEloRow`, `FixtureEloRow`) y extensiones no-breaking del Protocol
`TeamStrengthRepositoryPort` — ambos son agregados estructurales menores que el
Architecture-Engineer puede especificar directamente sin modelado DDD adicional.

`EloCalculatorService` es un servicio de infraestructura (funciones puras matemáticas)
que no encapsula invariantes de negocio complejas ni identidad de dominio. No aplica
crear un aggregate raíz nuevo.

## Orden de ejecución recomendado

1. Migración Alembic (Paso 1) — prerequisito para todo lo demás
2. DTOs + Protocol extension (Paso 2)
3. ORM Model (Paso 3)
4. Repository (Paso 4)
5. `EloCalculatorService` (Paso 5) — sin dependencias
6. `ClubEloProvider` (Paso 6) — sin dependencias de SFA
7. `SeedClubEloUseCase` (Paso 7) — depende de 4, 5, 6
8. `CalculateEloRatingsUseCase` (Paso 8) — depende de 4, 5
9. Tasks (Paso 9) — depende de 7, 8
10. Hook en ingestion_tasks (Paso 10) — depende de 9
11. Schemas + Router (Pasos 11-13) — depende de 7, 8
12. Archivo HTTP (Paso 14)
13. Tests (Paso 15) — pueden escribirse en paralelo con 7-8
14. Verificaciones finales (Paso 16)

## Verificación end-to-end

1. `POST /admin/elo/seed` con `{"date_str": "2024-08-01", "season": "2024"}` → respuesta
   con `matched >= 20`, `status="completed"`, `unmatched` lista breve de equipos no
   cubiertos (esperado: copas, divisiones menores).
2. `SELECT COUNT(*) FROM team_strengths WHERE source='clubelo_seed' AND season='2024';`
   → número > 0.
3. `POST /admin/elo/recalculate` con `season="2024"` y todos los `competition_ids` →
   `fixtures_processed > 0`, `teams_updated > 0`.
4. `SELECT team_id, strength, elo_raw FROM team_strengths WHERE source='elo_v1' AND season='2024' ORDER BY elo_raw DESC LIMIT 5;`
   → los 5 equipos más fuertes del dataset tienen ELO plausible (>1700) y `strength` >50.
5. Disparar ingesta manual de un partido y observar en logs de Celery worker que
   `apply_elo_update_task` se ejecuta automáticamente.
6. Calcular un score SFA para un partido con rival fuerte post-ELO y verificar que M1
   > 1.0 cuando el rival tiene ELO superior al equipo del jugador.
