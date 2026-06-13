# Separación de Ingestion y Scoring como flujos independientes

## Contexto de negocio

`IngestCompetitionUseCase.execute()` tiene actualmente 5 fases inline. La Fase 4 (Season scores)
agrega los `player_events` en memoria durante el loop y escribe `sfa_season_scores`. El problema
es que cuando solo cambian pesos en `BASE_POINTS_TABLE`, hay que re-ejecutar toda la ingestion
(Fases 1-3 con llamadas a API-Football) simplemente para recalcular la Fase 4. Esto desperdicia
quota de API (7500 req/día en el plan real).

La solución es separar en dos flujos ortogonales:

- **INGESTION** (costoso, quota API): escribe `players`, `player_stats`, `player_events`,
  `fixtures`, `standings`. No toca `sfa_season_scores`.
- **SCORING** (gratis, solo DB): lee `player_events` ya almacenados con `pts` calculados
  y re-agrega `sfa_season_scores` directamente desde la DB.

Esto permite recalcular scores en segundos sin consumir quota, y también permite que el scoring
corra en paralelo o con un schedule distinto al de ingestion.

## Restricciones

- Los `player_events` ya almacenan `pts` con todos los multiplicadores aplicados (M1-M4 + Mvisit),
  incluyendo el `EventType.STATS` que agrupa todas las stats de un fixture. El flujo de scoring
  puede simplemente hacer `SUM(pts)` sobre `player_events` — no recalcula multiplicadores.
- El `event_type` en `player_events` mapea directamente a las keys del breakdown dict
  (`goal`, `goal_penalty`, `assist`, `corner_assist`, `stats`, etc.).
- La Fase 4 actual usa `_PlayerAccum` (estado en memoria del loop). La nueva tarea de scoring
  hace el equivalente con `SQL GROUP BY` directamente en la DB.
- El umbral de 90 min totales en `sfa_season_scores` debe preservarse. Se calcula sumando
  `player_stats.minutes` por (jugador, competition, season).
- La función `_reconcile_breakdown_counts` ya no es necesaria en el nuevo flujo: los eventos
  escritos en `player_events` (tipos `GOAL`, `GOAL_PENALTY`, `ASSIST`, `CORNER_ASSIST`) son
  autoritativos sobre goals/assists. El breakdown se construye directamente por `event_type`.
- `matches_played` = `COUNT(DISTINCT fixture_id)` sobre `player_events` del jugador en esa
  competition+season, filtrando solo fixtures donde `player_stats.minutes >= 1`.
- No hay nuevas entidades de dominio ni value objects nuevos.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Nuevo `ScoringRepositoryPort` Protocol en `domain/ingestion_ports.py` con 3 métodos mínimos | Reutilizar `IngestionRepositoryPort` para el scoring use case | Viola SRP: el scoring use case no necesita `upsert_fixture`, `upsert_player`, etc. Un port mínimo mejora testabilidad con Fakes pequeños |
| `ScoringRepository` dedicado en `infrastructure/repositories/scoring_repository.py` | Agregar los métodos de scoring a `IngestionRepository` | `IngestionRepository` ya tiene muchas responsabilidades y su ciclo de sesión está acoplado al flujo de ingestion |
| `CalculateCompetitionScoresUseCase(competition_id, season)` — solo DB, sin provider | Hacer el cálculo directamente en la Celery task | Viola arquitectura hexagonal; la lógica (filtro 90 min, pct breakdown) pertenece al use case |
| `CalculateAllScoresUseCase(season)` que itera competitions y llama al use case anterior | Un único use case consolidado sin granularidad | La granularidad por competition permite re-calcular una sola liga, facilita tests independientes y evita transacciones monolíticas |
| Eliminar completamente la Fase 4 de `IngestCompetitionUseCase` | Mantener Fase 4 + agregar nueva task como duplicado | Duplica lógica y no resuelve el problema de quota: si Fase 4 sigue existiendo, la ingestion siempre tocará `sfa_season_scores` |
| Lanzar `calculate_all_scores_task` desde `_run_ingest_all` via `.delay()` después del commit | Encadenar con Celery chord/callback | Si la ingestion falla a medias, el scoring puede correr sobre datos parciales y eso es válido y deseable; además es más simple |

## Domain Model

No aplica. Este refactor no requiere nuevas entidades de dominio, value objects ni aggregates.
Solo se agrega un nuevo Protocol (port) y DTOs de lectura simples (frozen dataclasses).

## Integraciones externas

Ninguna. El flujo de scoring es puramente DB — no consume API-Football ni ninguna API externa.
