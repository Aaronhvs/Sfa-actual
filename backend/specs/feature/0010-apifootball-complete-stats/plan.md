# Plan: API-Football Complete Stats — Fuente única de datos

## Archivos a crear

- [ ] `alembic/versions/XXXX_apifootball_complete_stats.py` — migración: drop 8 columnas muertas, add 11 columnas nuevas
- [ ] `tests/use_cases/test_apifootball_complete_stats.py` — tests de ingesta + scoring con nuevos campos
- [ ] `http/admin_backfill.http` — request de ejemplo para el endpoint de backfill

## Archivos a modificar

- [ ] `src/sfa/infrastructure/models/player_stats/models.py` — eliminar 8 columnas muertas, añadir 11 nuevas, actualizar CheckConstraints
- [ ] `src/sfa/domain/ingestion_ports.py` — añadir 11 campos en `PlayerStatsRawDTO`
- [ ] `src/sfa/infrastructure/providers/api_football.py` — extraer todos los campos nuevos en `fetch_fixture_players`
- [ ] `src/sfa/infrastructure/repositories/ingestion_repository.py` — `upsert_player_stats` con nuevos campos
- [ ] `src/sfa/domain/enrichment_ports.py` — `PlayerStatsEventRecalcRow`: eliminar campos muertos, añadir nuevos
- [ ] `src/sfa/infrastructure/repositories/enrichment_repository.py` — `get_stats_events_for_recalc`: SELECT con nuevos campos, eliminar muertos
- [ ] `src/sfa/domain/scoring/value_objects.py` — añadir 6 nuevos `ActionType`
- [ ] `src/sfa/domain/scoring/services.py` — pesos en `BASE_POINTS_TABLE` para las 6 nuevas acciones
- [ ] `src/sfa/application/use_cases/recalculate_scores.py` — `stat_counts` con nuevos campos y señales negativas
- [ ] `src/sfa/api/v1/players.py` — endpoint `GET /players/{id}/stats` con aggregates de temporada
- [ ] `src/sfa/tasks/enrichment_tasks.py` — `backfill_fixture_stats_task`
- [ ] `src/sfa/api/v1/admin.py` — endpoint `POST /admin/backfill-fixture-stats?competition_id=X&season=Y`
- [ ] `src/sfa/application/use_cases/enrich_with_understat.py` — eliminar (o marcar obsoleto si se prefiere conservar histórico)
- [ ] `src/sfa/infrastructure/providers/understat_scraper.py` — eliminar (o marcar obsoleto)
- [ ] `src/sfa/infrastructure/providers/fbref_scraper.py` — eliminar (o marcar obsoleto)

## Checklist de implementación

### Fase 1 — Modelo y migración

- [ ] Generar migración Alembic con `alembic revision --autogenerate -m "apifootball_complete_stats"`
- [ ] Editar migración generada: confirmar drop de columnas muertas y add de columnas nuevas con `server_default='0'`
- [ ] Actualizar `player_stats/models.py`: eliminar columnas, añadir las 11 nuevas con tipos apropiados
- [ ] Actualizar `CheckConstraint`s: eliminar los de columnas borradas, añadir `>= 0` para todas las nuevas
- [ ] Aplicar migración en dev: `alembic upgrade head`

### Fase 2 — Ingesta

- [ ] Añadir 11 campos a `PlayerStatsRawDTO` en `ingestion_ports.py`
- [ ] Actualizar `fetch_fixture_players` en `api_football.py`: extraer `shots.total`, `passes.total`, `passes.accuracy` (cast a int), `dribbles.past`, `duels.total`, `fouls.committed`, `cards.yellow`, `cards.red`, `penalty.won`, `goals.saves`, `goals.conceded`
- [ ] Actualizar `upsert_player_stats` en `ingestion_repository.py`: incluir 11 campos nuevos, eliminar 8 muertos del INSERT y UPDATE
- [ ] Verificar con fixture real: `docker exec backend-api-1 python3 scripts/test_ingestion_new_fields.py`

### Fase 3 — Scoring

- [ ] Añadir a `value_objects.py`: `PASSES_COMPLETED`, `FOULS_COMMITTED`, `YELLOW_CARD`, `RED_CARD`, `PENALTY_WON`, `DRIBBLES_PAST`
- [ ] Añadir pesos en `BASE_POINTS_TABLE` de `services.py`:

  | Acción | FW | MF | DF |
  |---|---|---|---|
  | `PASSES_COMPLETED` | 0 | 5 | 1 |
  | `FOULS_COMMITTED` | -30 | -20 | -15 |
  | `YELLOW_CARD` | -150 | -150 | -150 |
  | `RED_CARD` | -500 | -500 | -500 |
  | `PENALTY_WON` | 200 | 180 | 80 |
  | `DRIBBLES_PAST` | 0 | -20 | -50 |

- [ ] Actualizar `PlayerStatsEventRecalcRow` en `enrichment_ports.py`: eliminar `xa`, `progressive_passes`, `progressive_carries`, `recoveries_opp_half`, `pressures_success`, `clearances`; añadir `passes_total`, `passes_accuracy`, `shots_total`, `dribbles_past`, `duels_total`, `fouls_committed`, `cards_yellow`, `cards_red`, `penalty_won`
- [ ] Actualizar `get_stats_events_for_recalc` en `enrichment_repository.py`: SELECT con nuevos campos (eliminar campos muertos, añadir nuevos)
- [ ] Actualizar `stat_counts` en `recalculate_scores.py`:
  ```python
  ActionType.PASSES_COMPLETED: int(event.passes_total * event.passes_accuracy / 100),
  ActionType.FOULS_COMMITTED:  event.fouls_committed,
  ActionType.YELLOW_CARD:      event.cards_yellow,
  ActionType.RED_CARD:         event.cards_red,
  ActionType.PENALTY_WON:      event.penalty_won,
  ActionType.DRIBBLES_PAST:    event.dribbles_past,
  ```
  > Nota: los pesos negativos en `BASE_POINTS_TABLE` ya se encargan de la penalización; no hace falta lógica especial en `stat_counts`.

### Fase 4 — Endpoint de stats de perfil

- [ ] Añadir endpoint `GET /players/{player_id}/stats` en `players.py`:
  - Query: `SELECT SUM(passes_total), AVG(passes_accuracy), SUM(passes_key), SUM(shots_total), SUM(shots_on), SUM(dribbles_won), SUM(dribbles_attempts), SUM(duels_won), SUM(duels_total), SUM(fouls_drawn), SUM(fouls_committed), SUM(cards_yellow), SUM(cards_red), SUM(penalty_won), SUM(minutes) FROM player_stats WHERE player_id=? AND season=? AND fixture competition_id=?`
  - Response: JSON con todos los aggregates + ratios calculados (dribble_success_rate, duel_win_rate, pass_accuracy_avg)
- [ ] Registrar router si no estaba ya en `main.py`
- [ ] Crear `http/players_stats.http` con ejemplo de llamada

### Fase 5 — Backfill de fixtures existentes

- [ ] Añadir `backfill_fixture_stats_task` en `enrichment_tasks.py`: recibe `competition_id`, `season`; obtiene todos los `fixture_id`s de esa competición/temporada; llama `fetch_fixture_players` para cada uno y hace `upsert_player_stats` con los nuevos campos
- [ ] Añadir endpoint admin `POST /admin/backfill-fixture-stats?competition_id=X&season=Y` en `admin.py` que dispara la tarea Celery
- [ ] Crear `http/admin_backfill.http`

### Fase 6 — Limpieza de scrapers obsoletos

- [ ] Evaluar si eliminar `enrich_with_understat.py`, `understat_scraper.py`, `fbref_scraper.py` o moverlos a `_deprecated/`
- [ ] Eliminar `enrich_understat_task` y `enrich_fbref_task` de `enrichment_tasks.py` (o dejarlos inertes si hay endpoints admin que los referencian)
- [ ] Actualizar `enrich_all_task` para que solo llame API-Football + recalculate

### Fase 7 — Tests y validación

- [ ] Escribir tests en `tests/use_cases/test_apifootball_complete_stats.py`:
  - Test: todos los campos nuevos se extraen correctamente del DTO mock
  - Test: `PASSES_COMPLETED` = floor(passes_total × accuracy/100)
  - Test: tarjeta amarilla reduce puntuación
  - Test: tarjeta roja reduce puntuación más que amarilla
  - Test: `PENALTY_WON` suma puntos para FW y MF, menos para DF
  - Test: `DRIBBLES_PAST` no penaliza a FW, sí a DF
- [ ] Actualizar `tests/use_cases/test_mrating_factor.py` y otros tests que usen `PlayerStatsEventRecalcRow` — añadir campos nuevos, eliminar los borrados
- [ ] Verificar `pytest tests/` pasa con coverage ≥ 80%
- [ ] Verificar `flake8 src/ tests/` sin errores
- [ ] Verificar `isort --check-only src/ tests/` sin errores

## Agent Routing Brief

**DDD Designer needed:** no

Los nuevos campos son extensiones del modelo de datos existente (`PlayerStats`), no
entidades de dominio nuevas. Los nuevos `ActionType` son value objects simples (enums)
ya contemplados en la arquitectura actual. No hay nuevos agregados ni invariantes de
dominio que diseñar.

## Verificación

1. Lanzar backfill para La Liga 2024:
   ```
   POST /api/v1/admin/backfill-fixture-stats?competition_id=1&season=2024
   ```
2. Verificar cobertura de campos nuevos:
   ```bash
   docker exec backend-api-1 python3 scripts/check_new_fields_coverage.py
   ```
   Esperar: `passes_total > 0` en ≥ 80% de filas de esa competición/temporada.
3. Lanzar recalculate para La Liga 2024:
   ```
   POST /api/v1/admin/recalculate/1?season=2024
   ```
4. Verificar endpoint de perfil:
   ```
   GET /api/v1/players/{pedri_id}/stats?competition_id=1&season=2024
   ```
   Esperar: `passes_total` > 0, `passes_accuracy` entre 70-95, `dribbles_past` >= 0.
5. Comprobar que Pedri sube en el ranking respecto a su posición anterior al recalculate.
