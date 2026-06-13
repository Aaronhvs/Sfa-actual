# 0020 — Soporte multi-temporada + selector de temporada

## Contexto de negocio

SFA lleva operando con datos de la temporada 2024-25. La temporada 2025-26 está próxima
a ingestarse. El producto necesita que ambas temporadas (y futuras) coexistan en la DB sin
colisiones, que el ranking refleje cualquier temporada seleccionada o el acumulado histórico,
y que el perfil del jugador muestre datos correctos por temporada (incluyendo el equipo en
el que estaba en ESA temporada, no el actual).

El frontend tiene `SEASON = '2024'` hardcodeado en `RankingPage.tsx` y `PlayerPage.tsx`.
Con esta feature el front puede llamar a `GET /api/v1/seasons` para renderizar el selector
y pasar `season=all` o `season=2025` a los endpoints existentes.

## Restricciones

- API-Football usa `season=2025` para referirse a la temporada 2025-26 (año de inicio).
  La columna `SFASeasonScore.season` ya almacena ese formato de string; no hay conflicto.
- No se pueden hacer migraciones breaking. `Player.team_id` refleja el equipo ACTUAL;
  no puede eliminarse ni alterarse de forma incompatible.
- `SFASeasonScore` NO guarda `team_id` por temporada. Tampoco existe tabla de historial
  de traspasos. La ingesta hace `upsert_player` y sobreescribe `Player.team_id` con el
  equipo de la temporada que se está ingiriendo.
- El modelo `SFASeasonScore` ya tiene unicidad por `(player_id, competition_id, season,
  rules_version_id)` vía dos partial indexes. Varias temporadas ya conviven en la tabla
  sin migración adicional.
- `SFASeasonScore` es la única fuente de verdad de scores; `PlayerEvent` y `PlayerStats`
  también tienen `season` implícito vía `Fixture.season`. No se crean nuevas tablas de
  eventos.
- El proyecto NO usa Alembic; las migraciones se aplican con `ALTER TABLE` manual o
  mediante `Base.metadata.create_all` en el lifespan.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Añadir columna `team_id` a `SFASeasonScore` para guardar el equipo del jugador EN ESA temporada | Tabla separada `player_team_season` | Solución mínima, no rompe la ingesta actual. La columna es nullable para filas históricas ya existentes. |
| Rellenar `SFASeasonScore.team_id` durante la ingesta existente (`upsert_player` ya recibe `team_id`) | Trigger de DB o proceso batch separado | La ingesta ya tiene el dato disponible; añadir una línea al `upsert_season_score` es suficiente. |
| Para filas antiguas (donde `team_id IS NULL` en SFASeasonScore) hacer fallback a `Player.team_id` en la query | Forzar backfill obligatorio como precondición | Retrocompatibilidad; el fallback es transparente para el consumer. |
| `season=all` implementado en el repositorio con GROUP BY player_id sobre todas las seasons | Endpoint separado `/ranking/all-time` | Consistencia de API; el parámetro `season` ya existe en todos los endpoints. |
| Nuevo endpoint `GET /api/v1/seasons` implementado como use case + repositorio dedicado | Inline en el ranking endpoint | Hexagonal pura; el use case es trivial pero mantiene la arquitectura. |
| `GET /api/v1/players/{id}?season=all` devuelve stats agregadas sumando SFASeasonScore de todas las temporadas | Stats de la temporada más reciente por defecto | Consistencia con el comportamiento de `season=all` en ranking. |
| `PlayerDetailResult` extiende con campo `available_seasons: list[str]` | Endpoint separado `/players/{id}/seasons` | Evita un round-trip extra desde el front para renderizar el selector. |
| Para `season=all` en ranking, el equipo/logo mostrado es el ACTUAL (`Player.team_id`) | Equipo de la temporada más reciente con datos | Es el comportamiento esperado en un ranking acumulado histórico. |
| Para `season=<específica>` en ranking, el equipo/logo usa `SFASeasonScore.team_id` con fallback a `Player.team_id` | Solo `Player.team_id` | Corrección del bug de team_logo histórico sin romper nada existente. |

## Domain Model

No se crean nuevas entidades de dominio. Los cambios son:

### Nuevas columnas en modelos existentes

**`SFASeasonScore`** — añadir:
```
team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
```
Nullable para retrocompatibilidad con filas ya existentes.

### Nuevos DTOs en `domain/ports.py`

**`SeasonDTO`**
```python
@dataclass(frozen=True)
class SeasonDTO:
    season: str       # ej: "2024", "2025"
    is_latest: bool
```

**Extensión de `RankedPlayerDTO`** — sin cambio de campos; el `team_logo_url` ya existe.
La corrección es en la query del repositorio, no en el DTO.

**Extensión de `PlayerDetailResult`** (en `get_player_detail.py`) — añadir campo:
```python
available_seasons: list[str]   # ordenadas desc, ej: ["2025", "2024"]
```

### Nuevos Protocols en `domain/ports.py`

**`SeasonRepositoryProtocol`**
```python
@runtime_checkable
class SeasonRepositoryProtocol(Protocol):
    async def get_available_seasons(self) -> list[SeasonDTO]: ...
```

**Extensión de `SFAScoreRepositoryProtocol`** — añadir método:
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

## Integraciones externas

Ninguna nueva. La ingestión de temporada 2025-26 usa el mismo flujo de API-Football
con `season=2025` (ya soportado por el sistema actual).
