# Refactor 0036: Ingest API Call Reduction

## Contexto de negocio

`ingest_today_task` corre cada 30 minutos via Celery Beat. Con el Mundial 2026 activo,
cada ejecución consume ~141 API calls de API-Football:

- 1 call para standings
- 32 calls para fixtures (1 por equipo × 32 equipos del Mundial)
- 108 calls para events + players (3 calls × 36 fixtures ya jugados)

Con 48 ejecuciones/día eso supone ~6.768 calls/día, casi al límite del plan real (7.500/día).
No queda margen para el resto de competiciones ni para picos de actividad.

Las dos fuentes de desperdicio son estructuralmente evitables:
1. La API permite obtener todos los fixtures de una liga en 1 sola llamada.
2. Los fixtures con status FT/AET/PEN ya tienen datos inmutables — re-fetchear events/players
   cada 30 minutos es un gasto innecesario.

## Restricciones

- API-Football: `/fixtures?league=X&season=Y` devuelve todos los partidos con su status
  en 1 request. Ya existe `fetch_world_cup_fixtures` en el provider que usa exactamente
  este endpoint; sin embargo devuelve `WorldCupFixtureDTO`, no `FixtureRawDTO`, y no es
  parte del `FootballDataProviderPort`.
- El modelo `Fixture` en DB **no tiene columna `status`**. Para implementar el skip de
  completed fixtures es necesario añadir esa columna.
- No debe haber regresión en el comportamiento para ligas de club (Premier League, La Liga,
  etc.) donde `top_n` no es `None` y el flujo actual funciona correctamente.
- El refactor no puede romper la idempotencia: reingestar el mismo fixture debe producir
  el mismo estado en DB.
- El `FootballDataProviderPort` es un `@runtime_checkable` Protocol; cualquier método nuevo
  debe añadirse ahí para que los Fakes de tests lo implementen.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Añadir `fetch_league_fixtures(league_id, season) -> list[FixtureRawDTO]` al port y al provider | Reutilizar `fetch_world_cup_fixtures` que ya existe | `fetch_world_cup_fixtures` retorna `WorldCupFixtureDTO` (distinto DTO, distinto port), mezclar dominios violaría la separación de contextos |
| Incluir el campo `status` en `FixtureRawDTO` | DTO nuevo `FixtureRawWithStatusDTO` | El status forma parte natural del fixture raw; no justifica un DTO separado |
| Añadir columna `status VARCHAR(10)` a la tabla `fixtures` | Tabla auxiliar o campo en memoria | El status es un dato de ciclo de vida del fixture, pertenece al modelo |
| Añadir `get_completed_fixture_ids(competition_id, season) -> set[int]` al `IngestionRepositoryPort` | Consulta inline dentro del use case | Mantiene el patrón: el use case nunca accede a SQLAlchemy directamente |
| En Phase 2: si `league.top_n is None`, usar `fetch_league_fixtures` (1 call); si `top_n` tiene valor, mantener `fetch_team_fixtures` por equipo | Usar `fetch_league_fixtures` siempre | `fetch_team_fixtures` con `status=FT-AET-PEN` filtra ya en API-Football; para ligas de club con `top_n` el volumen es manejable y el comportamiento ha sido validado |
| En Phase 3: consultar `get_completed_fixture_ids` al inicio del bucle y saltar si el `external_id` ya está completado en DB | Flag `force` para saltar todo | El `force=True` del `ingest_today_task` es necesario para detectar partidos que cambian de estado (en vivo → terminado); la granularidad debe ser por fixture, no por ejecución completa |
| Migración Alembic para añadir `status` a `fixtures` | Script SQL manual | Alembic es el mecanismo estándar del proyecto para cambios de esquema |

## Domain Model

No se requieren nuevas entidades de dominio. Los cambios son:

- **`FixtureRawDTO`**: añadir campo `status: str = "FT"` (default "FT" preserva compatibilidad
  con los tests existentes que no proveen status).
- **`FootballDataProviderPort`**: nuevo método `fetch_league_fixtures`.
- **`IngestionRepositoryPort`**: nuevo método `get_completed_fixture_ids`.

## Integraciones externas

- **API-Football v3** — endpoint `/fixtures?league=X&season=Y`:
  - Devuelve todos los fixtures de la liga con su campo `fixture.status.short`
    (NS, 1H, HT, 2H, ET, BT, P, SUSP, INT, LIVE, FT, AET, PEN, PST, CANC, ABD, AWD, WO).
  - Statuses considerados "completed" para el skip: `{"FT", "AET", "PEN"}`.
  - 1 request por ejecución en vez de 32. Resultado esperado: pasa de 141 a ~10 calls/ejecución
    cuando el Mundial tiene 36 fixtures terminados y 0 en juego.
