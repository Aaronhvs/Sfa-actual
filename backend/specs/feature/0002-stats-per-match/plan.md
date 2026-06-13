# 0002 — Stats por partido en player_events: Plan de implementación

## TL;DR

Persistir un `player_event` de tipo STATS por jugador por partido. Ampliar el provider y el DTO para capturar 3 campos nuevos de API-Football (`fouls.drawn`, `tackles.clearances`, `dribbles.attempts`) sin coste de requests adicionales. El fix central está en `ingest_competition.py` — añadir una llamada a `upsert_player_event` después de `score_match_stats()`.

No se necesita @DDD-Designer. No hay nuevos ActionType, EventType ni multiplicadores.

---

## Checklist de implementación

Procesar en orden. Cada ítem debe completarse y verificarse antes de avanzar al siguiente.

### Task 1 — Ampliar `PlayerStatsRawDTO` y provider

**Archivos:** `domain/ingestion_ports.py`, `infrastructure/providers/api_football.py`

- [ ] En `PlayerStatsRawDTO`, añadir al final del dataclass:
  ```
  fouls_drawn: int = 0
  clearances: int = 0
  dribbles_attempts: int = 0
  ```
  (con `= 0` como default para no romper ningún call site existente)

- [ ] En `fetch_fixture_players()` del provider, dentro del bloque de extracción de stats:
  - Leer `fouls = stats.get("fouls") or {}`
  - Leer `fouls_drawn = fouls.get("drawn") or 0`
  - Leer `clearances = (tackles.get("clearances") or 0)`  — `tackles` ya está extraído
  - Leer `dribbles_attempts = dribbles.get("attempts") or 0` — `dribbles` ya está extraído
  - Pasar los 3 valores al constructor de `PlayerStatsRawDTO`

- [ ] Verificar: los tests existentes siguen pasando sin modificación (los defaults en 0 los protegen)

---

### Task 2 — Ampliar modelo `PlayerStats` y migración

**Archivos:** `infrastructure/models/player_stats/models.py`, nueva migración Alembic

- [ ] Añadir tres columnas al modelo `PlayerStats`:
  ```
  fouls_drawn:      SmallInteger, nullable=False, default=0
  clearances:       SmallInteger, nullable=False, default=0
  dribbles_attempts: SmallInteger, nullable=False, default=0
  ```
  Con sus `CheckConstraint` correspondientes (`>= 0`).

- [ ] Generar migración:
  ```
  alembic revision --autogenerate -m "add fouls_drawn clearances dribbles_attempts to player_stats"
  ```

- [ ] Revisar el archivo generado: confirmar que solo hay `add_column` para las 3 columnas nuevas, sin drops ni cambios en otras tablas.

- [ ] Aplicar:
  ```
  alembic upgrade head
  ```

- [ ] Verificar en psql:
  ```sql
  \d player_stats
  ```
  Las 3 columnas deben aparecer con default 0.

---

### Task 3 — Ampliar `upsert_player_stats` en el repositorio

**Archivo:** `infrastructure/repositories/ingestion_repository.py`

- [ ] En el dict de `VALUES` del `pg_insert(PlayerStats)`, añadir las 3 claves:
  ```
  fouls_drawn=stats.get("fouls_drawn", 0),
  clearances=stats.get("clearances", 0),
  dribbles_attempts=stats.get("dribbles_attempts", 0),
  ```

- [ ] En la cláusula `ON CONFLICT DO UPDATE SET`, añadir las mismas 3 claves.

---

### Task 4 — Pasar nuevos campos desde el use case

**Archivo:** `application/use_cases/ingest_competition.py`

- [ ] En el dict pasado a `upsert_player_stats` (líneas ~226-239), añadir:
  ```
  "fouls_drawn": ps.fouls_drawn,
  "clearances": ps.clearances,
  "dribbles_attempts": ps.dribbles_attempts,
  ```

---

### Task 5 — Persistir row STATS en `player_events` (fix principal)

**Archivo:** `application/use_cases/ingest_competition.py`

Este es el cambio central. Después del bloque de stats (líneas 302-315 actuales):

```python
# Match stats
stats_for_scoring = {
    ActionType.DUELS_WON: ps.duels_won,
    ActionType.TACKLES_INTERCEPTIONS: ps.tackles + ps.interceptions,
    ActionType.BLOCKS: ps.blocks,
    ActionType.DRIBBLES_WON: ps.dribbles_success,
}
stat_scores = self._scoring.score_match_stats(
    group, stats_for_scoring,
    player_team_pos, rival_pos, stage_factor,
)
for s in stat_scores:
    accum.total_pts += s.total
    _add_to_breakdown(accum.breakdown, "stats", s.total)
```

- [ ] Calcular `stats_pts = round(sum(s.total for s in stat_scores), 2)` después del loop.

- [ ] Calcular `m1_value` (ya se calcula dentro de `score_match_stats` pero no está expuesto directamente — usar `M1RivalDifficulty(player_team_pos, rival_pos).value` para obtenerlo en el use case).

- [ ] Llamar a `upsert_player_event` inmediatamente después:
  ```
  await self._repo.upsert_player_event(
      player_id=player_db_id,
      fixture_id=fixture_db_id,
      minute=90,
      event_type=EventType.STATS,
      score_before=None,
      score_diff=None,
      psxg=None,
      m1=m1_value,
      m2=stage_factor,
      m3=1.0,
      m4=1.0,
      mvisit=1.0,
      pts=stats_pts,
  )
  ```

- [ ] Verificar que NO se produce doble-conteo en `accum.total_pts` — el `stats_pts` ya está sumado en el loop anterior. El `upsert_player_event` solo persiste, no suma de nuevo.

- [ ] Verificar idempotencia: correr la ingesta dos veces para el mismo fixture y confirmar que `player_events` tiene exactamente 1 row STATS por player-fixture (el `delete_player_events_for_fixture` al inicio del loop lo garantiza).

---

### Task 6 — Tests

**Archivo:** `tests/use_cases/test_ingest_stats_event.py`

- [ ] Implementar `FakeIngestionRepository` que implemente `IngestionRepositoryPort` completo (todos los métodos, usando Fake pattern — sin MagicMock).

- [ ] Implementar `FakeFootballProvider` que retorne:
  - 1 standing (equipo en pos 5)
  - 1 fixture
  - 1 evento de partido vacío (sin goles)
  - 1 jugador con: `minutes=90`, `goals=0`, `assists=0`, `dribbles_success=3`, `duels_won=2`, `tackles=1`, `interceptions=0`, `blocks=0`

- [ ] Test `test_player_without_goal_gets_stats_event`:
  - Ejecutar `IngestCompetitionUseCase`
  - Verificar que el Fake repo registró exactamente 1 llamada a `upsert_player_event` con `event_type=EventType.STATS`
  - Verificar que `pts > 0`

- [ ] Test `test_stats_event_not_duplicated_on_second_run`:
  - Ejecutar el use case dos veces con el mismo fixture
  - Verificar que el Fake repo solo tiene 1 row STATS final (la idempotencia funciona)

- [ ] Test `test_matches_played_counts_stat_only_games`:
  - Jugador con 0 goles/asistencias pero 3 regates en 2 fixtures distintos
  - Verificar que `upsert_season_score` se llama con `matches_played=2`

- [ ] Correr `pytest tests/` antes y después — documentar si algún test pre-existente falla

---

## Agent Routing Brief

No se requiere `@DDD-Designer` para ningún ítem de este plan.

| Tarea | Agente |
|-------|--------|
| Tasks 1-6 | Implementación directa — usar `/sfa-use-case` para task 5 si se quiere scaffold |

---

## Criterio de completitud

El spec está completo cuando:
1. `pytest tests/` pasa al 100% (incluyendo los 3 tests nuevos)
2. En la BD, tras una ingesta de La Liga: `SELECT COUNT(*) FROM player_events WHERE event_type = 'stats'` > 0
3. Yamal aparece con ≥27 `matches_played` en `sfa_season_scores`
4. El endpoint `GET /players/{id}/fixtures` retorna fixtures aunque el jugador no haya marcado ni asistido
