# 0023 — Player Targeted Re-ingest and Recalculate

## Contexto de negocio

Vinicius Júnior (internal player_id=889, external_id=762) muestra 0 eventos GOAL/ASSIST en
`player_events` para La Liga 2025, pese a tener 9 goles y 8 asistencias documentadas. En la
temporada 2024 sí tiene 9 GOAL + 8 ASSIST correctamente ingresados. Causa probable: la ingesta
de `/fixtures/events` no asoció los eventos al player_id correcto (nombre mismatch) o el
endpoint no fue invocado para esos fixtures. El problema es estructuralmente reproducible para
cualquier jugador.

El mecanismo actual de corrección exige:
- Relanzar `ingest_competition_task` — re-procesa todos los equipos y fixtures de La Liga (~300
  fixtures, cientos de requests a API-Football)
- O relanzar `run_full_recalculation_task` — recalcula 86K eventos, ~2 minutos, no resuelve
  la ausencia de datos en `player_events`

Se necesita una operación quirúrgica: dado un `player_id` interno y una `season`, re-ingestar
solo los fixtures en que ese jugador participó (ya existentes en DB) y recalcular únicamente
sus scores, sin tocar ningún otro jugador ni competition.

Impacto: permite corregir scores incorrectos de jugadores individuales en producción sin
lanzar pipelines completos. Costo: ~72 requests para Vinicius (36 fixtures × 2 endpoints),
menos del 1% del cupo diario de 7500.

## Restricciones

- El use case solo re-ingesta fixtures **ya existentes** en la DB (vía `player_stats`). No
  descubre fixtures nuevos desde API-Football. Si un fixture completo falta en DB, se necesita
  `ingest_competition_task`.
- El endpoint es admin-only (`/api/v1/admin/`). Sin autenticación adicional por ahora (mismo
  nivel que los demás endpoints de admin existentes).
- La re-ingesta de eventos de goal/assist requiere name matching por nombre de jugador porque
  `/fixtures/events` no devuelve player_id directamente. Se usa el helper `name_matches` del
  dominio.
- Rate limit API-Football: 7500 req/día. Un jugador con 38 fixtures cuesta 76 requests.
  Peticiones en secuencia (no paralelas) para no saturar el rate limiter.
- El use case es **idempotente**: borra los eventos del jugador en cada fixture antes de
  re-ingestarlos. Puede llamarse N veces sin duplicar datos.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Iterar sobre fixtures ya en DB (via `player_stats`) | Llamar `GET /fixtures?player=X&season=Y` a API-Football | Los fixtures ya están en DB; añadir nuevos fixtures fuera de scope. Evita N requests extra y riesgo de inconsistencia. |
| Un único use case `ReingestPlayerUseCase` que hace reingest + recalculate | Dos use cases separados | El flujo siempre necesita ambos pasos en orden. Componer un use case desde otro (scoring) es válido en SFA. |
| `CalculateScoresForRulesVersionUseCase` como dependencia directa de `ReingestPlayerUseCase` | Llamar la task de Celery desde el use case | Use cases componen use cases. Tasks llaman use cases. El scoring UC ya acepta `player_id` filter. |
| Nuevo DTO `PlayerFixtureInfoRow` en `ingestion_ports.py` | Reutilizar `FixtureInfoRow` existente | `FixtureInfoRow` no tiene `competition_id`, `home_team_id`, `away_team_id`, `player_team_id`, `stage` — campos necesarios para re-ingestar correctamente. |
| `player_name` incluido en `PlayerFixtureInfoRow` (JOIN con players) | Pasar `player_name` como parámetro al use case | La query de `get_fixtures_for_player` ya hace JOIN con `player_stats`; agregar JOIN con `players` es O(0) de complejidad extra y evita un parámetro extra en la API. |
| Mover `name_matches` a `domain/name_matching.py` | Importar desde `ingest_competition.py` | Use cases en `application/` no deben importar desde otros use cases. `domain/name_matching.py` ya existe y es el lugar correcto. |
| Endpoint `POST /admin/players/{player_id}/reingest` despachado como Celery task 202 | Ejecución síncrona en el request | La re-ingesta puede tardar 1-2 minutos. Patrón consistente con los demás endpoints de admin. |
| No crear entidades de dominio nuevas | Modelar `PlayerReingestRequest` como entidad | El problema es de datos corruptos en infra, no un concepto de dominio nuevo. No se invoca @DDD-Designer. |

## Domain Model

No aplica. Esta feature no requiere nuevas entidades de dominio. Se reutilizan ports y DTOs
existentes con extensiones mínimas al `IngestionRepositoryPort`.

## Integraciones externas

**API-Football v3**
- `GET /fixtures/events?fixture={id}` — eventos de un partido (goal, assist, card, etc.)
  Respuesta por nombre de jugador, no por ID. Requiere name matching.
- `GET /fixtures/players?fixture={id}` — estadísticas de todos los jugadores del partido
  (ambos equipos). Respuesta por player external_id.
- Autenticación: header `x-apisports-key` (ya configurado en `APIFootballProvider`)
- Rate limit: 7500 req/día en el plan actual
- Fallback: si un request falla después de 3 reintentos, el use case retorna
  `status="failed"` con el error. No hay reintentos a nivel de use case (la Celery task
  tiene `max_retries=2`).
