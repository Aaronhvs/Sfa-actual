# Plan: 0020 — Soporte multi-temporada + selector de temporada

## Archivos a crear

- [x] `backend/src/sfa/infrastructure/repositories/season_repository.py` — repositorio que implementa `SeasonRepositoryProtocol`; query `SELECT DISTINCT season FROM sfa_season_scores ORDER BY season DESC`
- [x] `backend/src/sfa/application/use_cases/get_seasons.py` — use case `GetSeasonsUseCase`; devuelve `list[SeasonDTO]` marcando el más reciente como `is_latest=True`
- [x] `backend/src/sfa/api/v1/seasons.py` — router FastAPI con `GET /seasons`; devuelve `SeasonsResponseSchema`
- [x] `backend/src/sfa/api/v1/schemas/seasons.py` — Pydantic schemas: `SeasonSchema`, `SeasonsResponseSchema`
- [x] `backend/http/seasons.http` — archivo de pruebas HTTP para el nuevo endpoint
- [x] `backend/tests/use_cases/test_get_seasons.py` — tests para `GetSeasonsUseCase` con `FakeSeasonRepository`
- [x] `backend/tests/use_cases/test_get_ranking_multi_season.py` — tests para `GetRankingUseCase` con `season=all`
- [x] `backend/tests/use_cases/test_get_player_detail_multi_season.py` — tests para `GetPlayerDetailUseCase` con `season=all` y `available_seasons`

## Archivos a modificar

- [x] `backend/src/sfa/infrastructure/models/scores/models.py` — añadir columna `team_id: Mapped[int | None]` con FK a `teams.id`, nullable=True
- [x] `backend/src/sfa/domain/ports.py` — añadir `SeasonDTO`, `SeasonRepositoryProtocol`, y tres métodos nuevos a `SFAScoreRepositoryProtocol`
- [x] `backend/src/sfa/infrastructure/repositories/sfa_score_repository.py` — implementar los tres métodos nuevos del protocolo; corregir query de `get_ranking` y `get_best_score_for_player_season` para usar `SFASeasonScore.team_id` con fallback a `Player.team_id`
- [x] `backend/src/sfa/infrastructure/repositories/__init__.py` — exportar `SeasonRepository`
- [x] `backend/src/sfa/infrastructure/repositories/ingestion_repository.py` — en `upsert_season_score` (o donde se escribe `SFASeasonScore`), añadir `team_id` al INSERT/UPDATE
- [x] `backend/src/sfa/application/use_cases/get_ranking.py` — manejar `season="all"` delegando a los nuevos métodos del repo; mantener comportamiento existente para cualquier otro valor
- [x] `backend/src/sfa/application/use_cases/get_player_detail.py` — manejar `season="all"`; añadir `available_seasons` al `PlayerDetailResult`; poblar el campo en todos los paths
- [x] `backend/src/sfa/api/v1/schemas/players.py` — añadir campo `available_seasons: list[str]` a `PlayerDetailSchema`
- [x] `backend/src/sfa/core/dependencies.py` — añadir `get_season_repository` y `get_seasons_use_case`
- [x] `backend/src/sfa/main.py` — registrar `seasons_router` con `prefix="/api/v1"` y tag `"seasons"`
- [x] `backend/http/ranking.http` — añadir ejemplos con `season=all` y `season=2025`
- [x] `backend/http/players.http` — añadir ejemplos con `season=all`

## Checklist de implementación

### Paso 1 — Migración DB: añadir `team_id` a `sfa_season_scores`

- [x] En `backend/src/sfa/infrastructure/models/scores/models.py`, añadir al modelo `SFASeasonScore`:
  ```python
  team_id: Mapped[int | None] = mapped_column(
      ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True
  )
  ```
  La columna es nullable para retrocompatibilidad con todas las filas existentes.
- [x] Verificar que `Base.metadata.create_all` en el lifespan levanta sin error (el campo nullable no requiere DEFAULT en PostgreSQL).
- [x] Escribir la sentencia SQL equivalente como comentario en el modelo (igual que los comentarios existentes para `fbref_id`, `understat_id`):
  ```
  # ALTER TABLE sfa_season_scores ADD COLUMN IF NOT EXISTS team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL;
  # CREATE INDEX IF NOT EXISTS ix_sfa_season_scores_team_id ON sfa_season_scores(team_id);
  ```

### Paso 2 — Poblar `team_id` durante ingesta

- [x] Localizar en `ingestion_repository.py` el método que hace `upsert` / `INSERT ... ON CONFLICT DO UPDATE` sobre `SFASeasonScore`. Actualmente el método que escribe scores de temporada vive en `scoring_repository.py` (o similar); rastrear con `grep -rn "sfa_season_scores"` para confirmar el archivo exacto.
- [x] En ese método, añadir `team_id` al `values(...)` del `pg_insert`. El valor se obtiene del parámetro `player_id` → `Player.team_id` que ya está disponible en el contexto de scoring (el `upsert_player` devuelve el `team_id` vigente).
- [x] Si el método de scoring no recibe `team_id` directamente, añadirlo como parámetro opcional con `None` por defecto para no romper llamadas existentes.
- [x] En el `on_conflict_do_update`, incluir `"team_id": insert_stmt.excluded.team_id` para que re-ingestas actualicen el equipo.

### Paso 3 — Nuevos DTOs y Protocols en `domain/ports.py`

- [x] Añadir al final de la sección de DTOs:
  ```python
  @dataclass(frozen=True)
  class SeasonDTO:
      season: str
      is_latest: bool
  ```
- [x] Añadir al final del archivo el nuevo Protocol:
  ```python
  @runtime_checkable
  class SeasonRepositoryProtocol(Protocol):
      async def get_available_seasons(self) -> list[SeasonDTO]: ...
  ```
- [x] Añadir a `SFAScoreRepositoryProtocol` los tres métodos nuevos (antes del cierre del Protocol):
  ```python
  async def get_available_seasons_for_player(self, player_id: int) -> list[str]: ...

  async def get_ranking_all_seasons(
      self,
      position: str | None = None,
      competition_id: int | None = None,
      limit: int = 50,
      name: str | None = None,
      rules_version_id: int | None = None,
      use_total: bool = False,
  ) -> list[RankedPlayerDTO]: ...

  async def get_ranking_total_all_seasons(
      self,
      position: str | None = None,
      competition_id: int | None = None,
      name: str | None = None,
      rules_version_id: int | None = None,
  ) -> int: ...

  async def get_total_player_stats_all_seasons(
      self, player_id: int, rules_version_id: int | None = None,
  ) -> tuple[int, int, int, float]: ...
  ```
- [x] Añadir `SeasonDTO` y `SeasonRepositoryProtocol` a los imports del módulo (no hay `__all__` explícito, basta con que estén definidos en el archivo).

### Paso 4 — Implementar `SeasonRepository`

- [x] Crear `backend/src/sfa/infrastructure/repositories/season_repository.py`:
  ```python
  from sqlalchemy import func, select
  from sqlalchemy.ext.asyncio import AsyncSession
  from sfa.domain.ports import SeasonDTO, SeasonRepositoryProtocol
  from sfa.infrastructure.models.scores.models import SFASeasonScore

  class SeasonRepository(SeasonRepositoryProtocol):
      def __init__(self, session: AsyncSession) -> None:
          self._session = session

      async def get_available_seasons(self) -> list[SeasonDTO]:
          stmt = (
              select(SFASeasonScore.season)
              .distinct()
              .order_by(SFASeasonScore.season.desc())
          )
          rows = (await self._session.execute(stmt)).scalars().all()
          seasons = list(rows)
          latest = seasons[0] if seasons else None
          return [
              SeasonDTO(season=s, is_latest=(s == latest))
              for s in seasons
          ]
  ```
- [x] Exportar `SeasonRepository` desde `backend/src/sfa/infrastructure/repositories/__init__.py`:
  añadir `from .season_repository import SeasonRepository` y agregar `"SeasonRepository"` a `__all__`.

### Paso 5 — Implementar tres métodos nuevos en `SFAScoreRepository`

**5a. `get_available_seasons_for_player`**
- [x] Añadir al final de la clase `SFAScoreRepository` en `sfa_score_repository.py`:
  ```python
  async def get_available_seasons_for_player(self, player_id: int) -> list[str]:
      stmt = (
          select(SFASeasonScore.season)
          .distinct()
          .where(SFASeasonScore.player_id == player_id)
          .order_by(SFASeasonScore.season.desc())
      )
      return list((await self._session.execute(stmt)).scalars().all())
  ```

**5b. `get_ranking_all_seasons`**
- [x] Añadir `get_ranking_all_seasons`. La lógica es idéntica a `get_ranking` existente excepto que **no** incluye el filtro `SFASeasonScore.season == season`. El subquery `score_filters` parte vacío (solo el filtro de `rules_version_id`).
  - Copiar la estructura completa de `get_ranking` y eliminar la línea `score_filters = [SFASeasonScore.season == season]`; reemplazar por `score_filters = []`.
  - Para el equipo en modo `all`, el JOIN usa `Player.team_id` directamente (equipo actual), igual que hoy. No se usa `SFASeasonScore.team_id` aquí.
  - Añadir parámetros: `position`, `competition_id`, `limit`, `name`, `rules_version_id`, `use_total` (misma firma que `get_ranking` sin `season`).

**5c. `get_ranking_total_all_seasons`**
- [x] Igual que `get_ranking_total` pero sin el filtro de season. Copiar la estructura y eliminar `score_filters = [SFASeasonScore.season == season]`; reemplazar por `score_filters = []`.

**5d. `get_total_player_stats_all_seasons`**
- [x] Añadir método que replica `get_total_player_stats` sin filtro de season:
  ```python
  async def get_total_player_stats_all_seasons(
      self, player_id: int, rules_version_id: int | None = None,
  ) -> tuple[int, int, int, float]:
      rv_filter = (
          SFASeasonScore.rules_version_id == rules_version_id
          if rules_version_id is not None
          else SFASeasonScore.rules_version_id.is_(None)
      )
      stmt = (
          select(
              SFASeasonScore.matches_played,
              SFASeasonScore.breakdown,
              SFASeasonScore.total_pts,
              SFASeasonScore.achievement_bonus_pts,
          )
          .where(
              SFASeasonScore.player_id == player_id,
              rv_filter,
          )
      )
      rows = (await self._session.execute(stmt)).fetchall()
      # misma lógica de suma que get_total_player_stats
      ...
  ```

### Paso 6 — Corregir query de team logo para temporada específica

- [x] En `get_ranking` de `SFAScoreRepository`, el JOIN actual es:
  ```python
  .join(Team, Player.team_id == Team.id)
  ```
  Cambiar por un `outerjoin` que prefiera `SFASeasonScore.team_id` con fallback a `Player.team_id`:
  ```python
  # Alias para el team de la temporada (desde SFASeasonScore.team_id)
  from sqlalchemy.orm import aliased
  SeasonTeam = aliased(Team)
  # En el SELECT añadir:
  func.coalesce(SeasonTeam.external_id, Team.external_id).label("team_external_id"),
  func.coalesce(SeasonTeam.name, Team.name).label("team_name"),
  # En los JOINs:
  .join(Team, Player.team_id == Team.id)  # equipo actual (fallback)
  .outerjoin(SeasonTeam, SFASeasonScore.team_id == SeasonTeam.id)  # equipo de la temporada
  ```
  El `_logo()` helper ya usa `team_external_id` desde el row, así que el cambio es transparente para el mapeo a DTO.

- [x] Aplicar la misma corrección en `get_best_score_for_player_season` para que `PlayerScoreDTO.team_name` refleje el equipo de la temporada consultada (no el actual).

### Paso 7 — Modificar `GetRankingUseCase` para `season=all`

- [x] En `backend/src/sfa/application/use_cases/get_ranking.py`, en el método `execute`:
  ```python
  ALL_SEASONS_SENTINEL = "all"

  async def execute(self, season: str | None = None, ...) -> RankingResult:
      if season is None:
          season = await self._score_repo.latest_season()

      if season is None:
          return RankingResult(season="", total=0, ranking=[])

      if season == ALL_SEASONS_SENTINEL:
          ranking = await self._score_repo.get_ranking_all_seasons(
              position, competition_id, limit, name, rules_version_id, use_total,
          )
          total = await self._score_repo.get_ranking_total_all_seasons(
              position, competition_id, name, rules_version_id,
          )
          return RankingResult(season="all", total=total, ranking=ranking)

      # comportamiento existente para season específica
      ranking = await self._score_repo.get_ranking(...)
      ...
  ```
- [x] Exportar la constante `ALL_SEASONS_SENTINEL = "all"` en el módulo para que pueda usarse en tests.

### Paso 8 — Modificar `GetPlayerDetailUseCase` para `season=all` y `available_seasons`

- [x] En `backend/src/sfa/application/use_cases/get_player_detail.py`:
  - Añadir `available_seasons: list[str]` a `PlayerDetailResult` dataclass.
  - En el método `execute`, después de resolver `season`:
    ```python
    # Obtener temporadas disponibles en todos los paths
    available_seasons = await self._score_repo.get_available_seasons_for_player(player_id)
    ```
  - Manejar `season="all"`:
    ```python
    if season == "all":
        total_matches, total_goals, total_assists, total_pts = (
            await self._score_repo.get_total_player_stats_all_seasons(player_id, rules_version_id)
        )
        if total_pts == 0.0 and total_matches == 0:
            raise PlayerNotFoundError(player_id)
        # Para all, usar el score de la última temporada como "mejor score"
        # para obtener team_name, competition_name, etc.
        latest = await self._score_repo.latest_season_for_player(player_id)
        score = await self._score_repo.get_best_score_for_player_season(
            player_id, latest, rules_version_id,
        )
        if score is None:
            raise PlayerNotFoundError(player_id)
        global_rank = await self._score_repo.get_global_rank(
            player_id, "all_sentinel", total_pts, rules_version_id,
        )
        # NOTA: global_rank para season=all no es significativo con la lógica actual;
        # devolver 0 o calcular sobre todas las temporadas según lo que decida el equipo.
        # Decisión: devolver rank global calculado sobre el acumulado (implementar en repo).
        return PlayerDetailResult(
            ...,
            season="all",
            available_seasons=available_seasons,
        )
    ```
  - Para el path de `season` específica (existente), poblar `available_seasons` con el resultado ya obtenido.
  - **NOTA IMPORTANTE para Codex**: el `global_rank` para `season=all` debe calcularse sumando pts de TODAS las temporadas por jugador y comparando. Añadir método `get_global_rank_all_seasons(player_id, total_pts, rules_version_id)` en el repositorio (misma lógica que `get_global_rank` pero sin filtro de season).

### Paso 9 — Añadir `get_global_rank_all_seasons` al repositorio y Protocol

- [x] Añadir a `SFAScoreRepositoryProtocol` en `ports.py`:
  ```python
  async def get_global_rank_all_seasons(
      self, player_id: int, total_pts: float, rules_version_id: int | None = None,
  ) -> int: ...
  ```
- [x] Implementar en `SFAScoreRepository` replicando `get_global_rank` pero sin filtro `SFASeasonScore.season == season`.

### Paso 10 — Actualizar `PlayerDetailResult` y schema API

- [x] En `get_player_detail.py` añadir campo al dataclass:
  ```python
  available_seasons: list[str] = dataclasses.field(default_factory=list)
  ```
  (usar `default_factory` para no romper código existente que construye `PlayerDetailResult` sin el campo)
- [x] En `backend/src/sfa/api/v1/schemas/players.py`, añadir campo a `PlayerDetailSchema`:
  ```python
  available_seasons: list[str] = []
  ```
- [x] En `backend/src/sfa/api/v1/players.py`, en el handler `get_player`, añadir al construir el schema:
  ```python
  available_seasons=result.available_seasons,
  ```

### Paso 11 — Crear `GetSeasonsUseCase`

- [x] Crear `backend/src/sfa/application/use_cases/get_seasons.py`:
  ```python
  from __future__ import annotations
  from dataclasses import dataclass
  from typing import Protocol, runtime_checkable
  from sfa.domain.ports import SeasonDTO, SeasonRepositoryProtocol

  @dataclass(frozen=True)
  class SeasonsResult:
      seasons: list[SeasonDTO]

  @runtime_checkable
  class GetSeasonsUseCaseProtocol(Protocol):
      async def execute(self) -> SeasonsResult: ...

  class GetSeasonsUseCase(GetSeasonsUseCaseProtocol):
      def __init__(self, season_repo: SeasonRepositoryProtocol) -> None:
          self._season_repo = season_repo

      async def execute(self) -> SeasonsResult:
          seasons = await self._season_repo.get_available_seasons()
          return SeasonsResult(seasons=seasons)
  ```

### Paso 12 — Crear schemas Pydantic para /seasons

- [x] Crear `backend/src/sfa/api/v1/schemas/seasons.py`:
  ```python
  from pydantic import BaseModel

  class SeasonSchema(BaseModel):
      season: str
      is_latest: bool

  class SeasonsResponseSchema(BaseModel):
      seasons: list[SeasonSchema]
  ```

### Paso 13 — Crear router `GET /seasons`

- [x] Crear `backend/src/sfa/api/v1/seasons.py`:
  ```python
  from typing import Annotated
  from fastapi import APIRouter, Depends
  from sfa.api.v1.schemas.seasons import SeasonSchema, SeasonsResponseSchema
  from sfa.application.use_cases.get_seasons import GetSeasonsUseCase
  from sfa.core.dependencies import get_seasons_use_case

  router = APIRouter()

  @router.get("/seasons", response_model=SeasonsResponseSchema)
  async def get_seasons(
      use_case: Annotated[GetSeasonsUseCase, Depends(get_seasons_use_case)],
  ):
      result = await use_case.execute()
      return SeasonsResponseSchema(
          seasons=[SeasonSchema(season=s.season, is_latest=s.is_latest) for s in result.seasons]
      )
  ```

### Paso 14 — Wiring en `dependencies.py`

- [x] Añadir import de `SeasonRepository`:
  ```python
  from sfa.infrastructure.repositories import SeasonRepository
  ```
- [x] Añadir factory de repositorio:
  ```python
  async def get_season_repository(
      db: Annotated[AsyncSession, Depends(get_db)],
  ) -> SeasonRepository:
      return SeasonRepository(db)
  ```
- [x] Añadir import de use case:
  ```python
  from sfa.application.use_cases.get_seasons import GetSeasonsUseCase
  ```
- [x] Añadir factory de use case:
  ```python
  async def get_seasons_use_case(
      season_repo: Annotated[SeasonRepository, Depends(get_season_repository)],
  ) -> GetSeasonsUseCase:
      return GetSeasonsUseCase(season_repo)
  ```

### Paso 15 — Registrar router en `main.py`

- [x] Añadir import:
  ```python
  from sfa.api.v1.seasons import router as seasons_router
  ```
- [x] Añadir a `tags_metadata`:
  ```python
  {"name": "seasons", "description": "Temporadas disponibles en el sistema"},
  ```
- [x] Añadir `include_router`:
  ```python
  app.include_router(seasons_router, prefix="/api/v1", tags=["seasons"])
  ```

### Paso 16 — Archivo `.http` para seasons

- [x] Crear `backend/http/seasons.http`:
  ```http
  ### Listar temporadas disponibles
  GET http://localhost:8000/api/v1/seasons

  ###
  ```
- [x] En `backend/http/ranking.http`, añadir al final:
  ```http
  ### Ranking acumulado de todas las temporadas
  GET http://localhost:8000/api/v1/ranking?season=all&limit=10

  ###

  ### Ranking temporada 2025-26
  GET http://localhost:8000/api/v1/ranking?season=2025&limit=10

  ###
  ```
- [x] En `backend/http/players.http`, añadir al final:
  ```http
  ### Detalle de jugador — stats acumuladas de todas las temporadas
  GET http://localhost:8000/api/v1/players/1?season=all

  ###
  ```

### Paso 17 — Tests de `GetSeasonsUseCase`

- [x] Crear `backend/tests/use_cases/test_get_seasons.py`:
  ```python
  import pytest
  from sfa.application.use_cases.get_seasons import GetSeasonsUseCase, SeasonsResult
  from sfa.domain.ports import SeasonDTO, SeasonRepositoryProtocol

  class FakeSeasonRepository(SeasonRepositoryProtocol):
      def __init__(self, seasons: list[SeasonDTO] | None = None):
          self._seasons = seasons or []
      async def get_available_seasons(self) -> list[SeasonDTO]:
          return self._seasons

  class TestGetSeasons:
      @pytest.mark.anyio
      async def test_returns_seasons_list(self):
          seasons = [SeasonDTO("2025", True), SeasonDTO("2024", False)]
          uc = GetSeasonsUseCase(FakeSeasonRepository(seasons))
          result = await uc.execute()
          assert isinstance(result, SeasonsResult)
          assert len(result.seasons) == 2
          assert result.seasons[0].season == "2025"
          assert result.seasons[0].is_latest is True

      @pytest.mark.anyio
      async def test_returns_empty_when_no_seasons(self):
          uc = GetSeasonsUseCase(FakeSeasonRepository([]))
          result = await uc.execute()
          assert result.seasons == []

      @pytest.mark.anyio
      async def test_fake_isinstance_protocol(self):
          repo = FakeSeasonRepository()
          assert isinstance(repo, SeasonRepositoryProtocol)
  ```

### Paso 18 — Tests de `GetRankingUseCase` con `season=all`

- [x] Crear `backend/tests/use_cases/test_get_ranking_multi_season.py`.
- [x] El `FakeSFAScoreRepository` debe implementar los nuevos métodos del Protocol: `get_ranking_all_seasons`, `get_ranking_total_all_seasons`, `get_available_seasons_for_player`, `get_total_player_stats_all_seasons`, `get_global_rank_all_seasons`.
- [x] Tests obligatorios:
  - `test_season_all_calls_all_seasons_methods` — verificar que al pasar `season="all"` el use case llama a `get_ranking_all_seasons` (no a `get_ranking` con season específica).
  - `test_season_all_returns_season_all_in_result` — el campo `RankingResult.season` debe ser `"all"`.
  - `test_season_specific_still_works` — pasar `season="2024"` sigue usando el camino existente.
  - `test_season_none_resolves_latest` — sin season, resuelve con `latest_season()`.

### Paso 19 — Tests de `GetPlayerDetailUseCase` con `season=all` y `available_seasons`

- [x] Crear `backend/tests/use_cases/test_get_player_detail_multi_season.py`.
- [x] El `FakeSFAScoreRepository` debe implementar los métodos nuevos.
- [x] Tests obligatorios:
  - `test_season_all_returns_aggregated_stats` — `season=all` suma stats de todas las temporadas.
  - `test_season_all_result_has_season_all` — `result.season == "all"`.
  - `test_available_seasons_populated` — `result.available_seasons` no está vacío para un jugador con datos.
  - `test_available_seasons_in_schema` — el campo existe en `PlayerDetailSchema` (instanciar y verificar).
  - `test_specific_season_still_returns_available_seasons` — incluso con `season="2024"`, el campo `available_seasons` está poblado.

### Paso 20 — Actualizar `FakeSFAScoreRepository` en tests existentes

- [x] En `backend/tests/use_cases/test_get_ranking.py`, añadir los métodos stub del Protocol a `FakeSFAScoreRepository`:
  ```python
  async def get_ranking_all_seasons(self, position=None, competition_id=None, limit=50,
                                    name=None, rules_version_id=None, use_total=False):
      return self._ranking

  async def get_ranking_total_all_seasons(self, position=None, competition_id=None,
                                          name=None, rules_version_id=None):
      return self._total

  async def get_available_seasons_for_player(self, player_id):
      return ["2024-25"]

  async def get_total_player_stats_all_seasons(self, player_id, rules_version_id=None):
      return (0, 0, 0, 0.0)

  async def get_global_rank_all_seasons(self, player_id, total_pts, rules_version_id=None):
      return 1
  ```
- [x] Aplicar el mismo update al `FakeSFAScoreRepository` en `test_get_player_detail.py`.
- [x] Aplicar el mismo update en cualquier otro test que tenga un `FakeSFAScoreRepository` (buscar con `grep -rn "FakeSFAScoreRepository" tests/`).

### Paso 21 — Verificación final

- [x] `pytest tests/ -x` sin errores.
- [ ] `flake8 src/ tests/` sin errores.
- [ ] `isort --check-only src/ tests/` sin errores.
- [ ] Arrancar el servidor con `uvicorn sfa.main:app --reload` y verificar:
  - `GET /api/v1/seasons` devuelve `{"seasons": [{"season": "2025", "is_latest": true}, ...]}`.
  - `GET /api/v1/ranking?season=all&limit=5` devuelve `{"season": "all", "total": N, "ranking": [...]}`.
  - `GET /api/v1/ranking?season=2025&limit=5` devuelve datos de la temporada 2025-26.
  - `GET /api/v1/players/1?season=all` devuelve el campo `available_seasons` con al menos una entrada.
  - `GET /api/v1/players/1?season=2024` devuelve el equipo correcto para 2024-25 (no el equipo actual si el jugador fue traspasado).

## Agent Routing Brief

**DDD Designer needed:** no

Los cambios de dominio son menores y mecánicos: un nuevo `SeasonDTO`, un nuevo Protocol `SeasonRepositoryProtocol`, y la extensión de `SFAScoreRepositoryProtocol` con métodos nuevos. No hay nuevos agregados, invariantes de negocio complejas ni value objects con lógica de construcción. El diseño está completamente especificado en `decisions.md`. Codex puede implementarlo directamente.

## Verificación

1. `GET http://localhost:8000/api/v1/seasons` → JSON con lista de temporadas y `is_latest=true` en la más reciente.
2. `GET http://localhost:8000/api/v1/ranking?season=all&limit=10` → `season` en la respuesta es `"all"`; `total` > 0; los jugadores tienen `team` y `team_logo_url` del equipo ACTUAL.
3. `GET http://localhost:8000/api/v1/ranking?season=2025&limit=10` → datos exclusivos de temporada 2025-26; el `team_logo_url` corresponde al equipo EN ESA temporada (requiere que la re-ingesta de 2025 ya haya poblado `SFASeasonScore.team_id`).
4. `GET http://localhost:8000/api/v1/players/1?season=all` → `season` = `"all"`; `available_seasons` con todas las temporadas del jugador; `sfa_pts` es la suma acumulada.
5. `GET http://localhost:8000/api/v1/players/1?season=2024` → `available_seasons` incluye `"2024"` y otras temporadas del jugador; `team` refleja el equipo de 2024-25.
6. Ingestar datos de prueba de temporada `2025` y comprobar que `SFASeasonScore.team_id` se rellena correctamente (verificar en DB: `SELECT player_id, season, team_id FROM sfa_season_scores WHERE season = '2025' LIMIT 5;`).
