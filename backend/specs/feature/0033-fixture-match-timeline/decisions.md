# 0033 — Fixture Match Timeline

## Contexto de negocio

La página de partido del Mundial (`MundialMatchPage`) muestra alineaciones, estadísticas y
rendimiento SFA, pero no tiene una cronología de eventos del partido (goles, tarjetas, cambios).
API-Football ya nos entrega esos eventos por partido —  la función `fetch_fixture_events()` ya
existe y se llama durante el ingestion— pero solo se usan para detectar goles y asistencias de
scoring. Cards y substituciones se descartan.

Esta feature persiste todos los eventos de partido relevantes en una nueva tabla `fixture_events`
y los expone en el endpoint `GET /wc/fixtures/{fixture_id}`, para que el frontend pueda renderizar
un componente `MatchTimeline` encima de las formaciones.

## Restricciones

- API-Football `/fixtures/events` ya se llama por fixture durante el ingestion; no se añaden
  requests extra al quota en partidos nuevos. Para partidos ya ingested se requiere una task
  de backfill que sí consume quota (1 request por partido = 5–10 calls para el WC actual).
- El campo `fixture_events.team_external_id` se guarda como INT sin FK a `teams` para evitar
  problemas de mapeo en fixtures donde el equipo no está en DB (friendlies, futuros).
- La tabla solo se alimenta desde ingestion (no se fetcha on-demand al leer el endpoint).
- El schema de `fixture_events` debe tolerar `player_name` vacío (VAR puede traer nombre null).

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Nueva tabla `fixture_events` separada de `player_events` | Reutilizar `player_events` para cards/subs | `player_events` es una tabla de scoring (M1-M4, pts); cards y subs no generan SFA pts y no encajan en el schema |
| Normalización de event_type en use case (`_normalize_event_type`) | Normalizar en el provider o en el repository | El provider devuelve raw strings de API-Football; la regla de negocio sobre qué tipos son válidos pertenece a la application layer |
| Guardar VAR=False, skip VAR events | Guardar VAR como `var` | VAR es ruido visual; no aporta información accionable en la timeline del frontend |
| `save_fixture_events` en `IngestionRepositoryProtocol` | Nuevo protocol separado | El ingestion ya escribe a la DB usando este protocol; extenderlo es consistente con el patrón establecido |
| `get_fixture_events` en `WorldCupRepositoryProtocol` | Protocol separado `FixtureTimelineRepositoryProtocol` | Los eventos se leen exclusivamente en el contexto del WC detail; un protocol separado sería YAGNI |
| Extender `WcFixtureDetailResponseSchema` con `events` | Nuevo endpoint `GET /wc/fixtures/{id}/events` | El frontend ya fetcha el detail completo en un solo call; añadir un segundo endpoint requeriría un segundo fetch y lógica de loading adicional |
| Nueva Celery task `ingest_fixture_events_task` para backfill | Script one-off | Permite reingesta selectiva desde el admin HTTP para cualquier fixture existente o futuro |

## Integraciones externas

- **API-Football** `/fixtures/events?fixture={id}`: devuelve lista de eventos con `type`, `detail`,
  `player.name`, `assist.name`, `team.id`, `time.elapsed`, `time.extra`.
  Ya implementado en `infrastructure/providers/api_football.py:fetch_fixture_events()`.
  Tipos relevantes: `"Goal"`, `"Card"`, `"subst"`. Se descarta `"Var"`.
