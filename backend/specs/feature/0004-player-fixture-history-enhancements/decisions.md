# 0004 — Historial de partidos: desglose por acción, filtro por competición y búsqueda de rival

## Contexto de negocio

El endpoint `GET /players/{id}/fixtures` ya devuelve el historial de partidos de un jugador con
`sfa_pts` total y `events_count`. Sin embargo, la UI necesita tres capacidades adicionales:

1. **Desglose de acciones por partido** — para cada partido, mostrar cuántos puntos aportó
   cada tipo de acción (goal, assist, stats, etc.) y cuántos eventos hubo de cada tipo.
2. **Filtro por competición** — el parámetro actual `competition_id` (entero) funciona
   pero obliga al cliente a conocer el ID interno. Se añade un parámetro alternativo
   `competition_name` (string, case-insensitive, partial match) para filtrar por nombre legible.
3. **Búsqueda de partido específico** — parámetro `rival` (string, partial match contra
   el nombre del equipo rival) y parámetro `date` (fecha ISO 8601) para filtrar por día exacto.

---

## Análisis de datos disponibles

### Tablas relevantes y su contenido

| Tabla | Campo clave | Disponibilidad |
|-------|-------------|----------------|
| `player_events` | `event_type`, `pts`, `player_id`, `fixture_id` | Ya existe, ya se lee |
| `fixtures` | `played_at`, `home_team_id`, `away_team_id`, `competition_id`, `season` | Ya existe |
| `competitions` | `name` | Ya existe |
| `teams` | `name` | Ya existe (join home/away alias) |

El desglose de acciones se puede calcular con un `GROUP BY fixture_id, event_type` sobre
`player_events`. No se necesita ninguna columna nueva en la BD.

Los filtros `rival` y `date` son predicados adicionales sobre columnas ya presentes
(`played_at`, `home_team_id`/`away_team_id`).

---

## Restricciones

- No se introduce paginación — el historial de un jugador en una temporada es acotado (máx ~50 partidos).
- El filtro `rival` aplica OR sobre ambos equipos (local y visitante) porque el endpoint no
  conoce qué equipo pertenece al jugador — decisión de usabilidad máxima.
- `competition_id` y `competition_name` pueden coexistir; el repositorio los combina en AND.
- No se modifica el endpoint `/players/{id}/events` — opera a distinto nivel de granularidad.

---

## Decisiones tomadas

| ID | Decisión | Alternativa descartada | Razón |
|----|----------|------------------------|-------|
| D1 | Desglose se incorpora al `GetPlayerFixturesUseCase` existente con `include_breakdown: bool = True` | Nuevo use case `GetPlayerFixtureBreakdownUseCase` | Redundante — mismos datos, mismo repositorio, mismo jugador |
| D2 | El breakdown se calcula en el repositorio (segunda query batch) | Post-procesamiento en Python sobre la lista de eventos | La agregación `GROUP BY fixture_id + event_type` en SQL es más eficiente que traer todos los eventos crudos y agrupar en memoria |
| D3 | `PlayerFixtureDTO` se amplía con `breakdown: dict[str, FixtureActionBreakdown] | None = None` | Campo separado en nuevo DTO | El campo con default `None` no rompe call sites existentes; el DTO sigue siendo la unidad de retorno canónica |
| D4 | Las claves del breakdown son los valores string del `EventType` enum | Enum objects como claves | Los strings son directamente serializables por Pydantic sin mapeo adicional |
| D5 | `competition_name` usa ILIKE con wildcards `%` en el repositorio | Búsqueda exacta / full-text search | ILIKE es suficiente para este volumen; full-text search añadiría complejidad innecesaria |
| D6 | `rival` aplica OR sobre `home_team.name` y `away_team.name` | Filtrar solo el equipo rival real | El endpoint no tiene contexto del equipo del jugador; OR sobre ambos equipos maximiza usabilidad sin falsos positivos relevantes |
| D7 | `date` se filtra con `func.date(Fixture.played_at) == date` | Rango `[date 00:00, date+1 00:00)` | El cast SQL `DATE(played_at)` es más limpio y PostgreSQL lo optimiza correctamente |
| D8 | `PlayerEventRepositoryProtocol` se amplía con `get_fixture_breakdown_by_player` | Reusar `get_events_by_player` y agrupar en el use case | Una query batch dedicada evita traer filas individuales innecesarias; el Protocol mantiene la separación de concerns |
| D9 | No se necesita `@DDD-Designer` | — | `FixtureActionBreakdown` es un DTO de lectura (frozen dataclass); no hay invariantes de negocio, nuevos multiplicadores ni nuevos ActionType |
| D10 | `pct` en `BreakdownEntrySchema` se pasa como `None` en el contexto de fixture | Calcular porcentaje por fixture | El porcentaje no tiene semántica clara a nivel de partido individual — aplica solo al resumen de temporada |

---

## Modelo de dominio — cambios mínimos

No se crean nuevas entidades de dominio ni value objects de scoring.

### Nuevo DTO en `domain/ports.py`

```
FixtureActionBreakdown(frozen=True)
  count: int
  pts:   float
```

### `PlayerFixtureDTO` ampliado

Campo nuevo al final del dataclass (compatible con call sites existentes):
```
breakdown: dict[str, FixtureActionBreakdown] | None = None
```

### `PlayerEventRepositoryProtocol` ampliado

Nuevo método tras `get_fixtures_by_player`:
```
async def get_fixture_breakdown_by_player(
    self,
    player_id: int,
    fixture_ids: list[int],
) -> dict[int, dict[str, FixtureActionBreakdown]]: ...
```

La clave exterior es `fixture_id` (int); la clave interior es el valor string del `EventType`.

---

## Impacto en capas

| Capa | Archivo | Tipo de cambio |
|------|---------|----------------|
| `domain/` | `ports.py` | Nuevo DTO `FixtureActionBreakdown`, campo nuevo en `PlayerFixtureDTO`, nuevo método en `PlayerEventRepositoryProtocol` |
| `application/` | `get_player_fixtures.py` | Nuevos parámetros en `execute()`, lógica de ensamblado del breakdown con `dataclasses.replace` |
| `infrastructure/repositories/` | `player_event_repository.py` | Implementar nuevo método + predicados SQL para los 3 nuevos filtros en `get_fixtures_by_player` |
| `api/v1/schemas/` | `players.py` | Campo `breakdown` en `PlayerFixtureSchema` |
| `api/v1/` | `players.py` | Nuevos query params `include_breakdown`, `competition_name`, `rival`, `date` |
| `http/` | `players.http` | Casos de prueba para los nuevos parámetros |

No hay cambios en modelos SQLAlchemy. No hay migración Alembic. No hay Celery tasks.
