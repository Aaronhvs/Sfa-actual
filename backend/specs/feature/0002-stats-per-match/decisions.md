# 0002 — Stats por partido en player_events

## Contexto de negocio

Los stats de partido (duelos, regates, tackles, recuperaciones) se calculan en la ingesta pero nunca se persisten como `player_events`. El resultado concreto:

- Un jugador que no marca ni asiste en un partido **no tiene ningún registro** de ese partido en `player_events`.
- `matches_played` en `sfa_season_scores` queda erróneamente bajo (solo cuenta partidos con goles/asistencias).
- El frontend no puede mostrar desglose por partido para acciones físicas (regates, duelos, tackles).
- Lamine Yamal, por ejemplo, aparece con 14 partidos cuando jugó 27.

La corrección es persistir un evento de tipo STATS por jugador por partido, después de calcular los puntos de stats con `score_match_stats()`.

---

## Decisiones

| ID | Decisión | Valor |
|----|----------|-------|
| D1 | Granularidad del evento STATS | Un row agregado por player-fixture (no uno por acción) |
| D2 | EventType a usar | `EventType.STATS` — ya existe en el enum, no hay cambio de schema |
| D3 | Minuto sentinel | 90 — satisface el CHECK constraint de la BD, representa "match stats" |
| D4 | Campos nulos en el row STATS | `score_before=NULL`, `score_diff=NULL`, `psxg=NULL` |
| D5 | Multiplicadores almacenados | m1 y m2 del partido; m3=1.0, m4=1.0, mvisit=1.0 (neutral, igual a como score_match_stats los calcula) |
| D6 | Idempotencia | Gratuita — `delete_player_events_for_fixture` ya borra todos los eventos del player-fixture antes de escribir |
| D7 | Cuándo escribir el row | Siempre que el jugador haya jugado ≥20 min, aunque `stats_pts == 0` |
| D8 | Nuevas acciones (fouls.drawn, clearances, penalty.won) | **Datos crudos solamente en este spec** — se extraen y guardan en `player_stats`, no se puntúan. Su scoring es decisión de producto, va en `0003-new-stat-actions` con @DDD-Designer |
| D9 | No se necesita @DDD-Designer | No hay nuevos ActionType, ni EventType, ni multiplicadores. El fix es wiring de persistencia |
| D10 | `matches_played` no requiere fix directo | Ya se incrementa en línea 224 para todo jugador con ≥20 min. El bug era que jugadores con `total_pts=0` no pasaban el filtro de `upsert_season_score`. Con el row STATS sus puntos siempre entran |

---

## Modelo de dominio — sin cambios

No se crean nuevas entidades ni value objects. `EventType.STATS` ya existe. `upsert_player_event` ya acepta todos los tipos. El motor de scoring no cambia.

---

## Cambios de infra

### `PlayerStatsRawDTO` (domain/ingestion_ports.py)
Tres campos nuevos con default 0 (no rompe call sites existentes):
- `fouls_drawn: int = 0`
- `clearances: int = 0`
- `dribbles_attempts: int = 0`

### `PlayerStats` model (infrastructure/models/player_stats/models.py)
Tres columnas nuevas SmallInteger default 0:
- `fouls_drawn`
- `clearances`
- `dribbles_attempts`

Requiere migración Alembic.

### Provider (infrastructure/providers/api_football.py)
Extraer de la respuesta `fixtures/players`:
- `fouls.drawn` → `fouls_drawn`
- `tackles.clearances` → `clearances`
- `dribbles.attempts` → `dribbles_attempts`

### Use case (application/use_cases/ingest_competition.py)
1. Pasar nuevos campos a `upsert_player_stats`.
2. Después del loop `for s in stat_scores:`, calcular `stats_pts` y llamar a `upsert_player_event` con `EventType.STATS`.

### Repository (infrastructure/repositories/ingestion_repository.py)
Añadir las 3 nuevas claves al dict de `upsert_player_stats` (INSERT + ON CONFLICT DO UPDATE).
