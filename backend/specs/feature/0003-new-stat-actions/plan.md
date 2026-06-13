# 0003 — Nuevas acciones de stat: Plan de implementación

## TL;DR

Activar 5 `ActionType` en el pipeline de scoring conectando campos ya almacenados en `player_stats` al dict `stats_for_scoring` de `ingest_competition.py`, y actualizando los valores de `BASE_POINTS_TABLE`. Requiere @DDD-Designer para los 2 ActionType nuevos (`FOULS_DRAWN`, `CLEARANCES`) antes de proceder con el resto.

No hay migración de BD. No hay cambio de provider. No hay cambio en el motor de scoring.

---

## Checklist de implementación

Procesar en orden. Tasks 1–2 requieren @DDD-Designer. Tasks 3–5 son implementación directa tras la aprobación.

---

### Task 1 — [DDD-Designer] Añadir `ActionType.FOULS_DRAWN` al enum

**Archivos:** `domain/scoring/value_objects.py`

- [ ] Añadir al enum `ActionType` el miembro:
  ```
  FOULS_DRAWN = "fouls_drawn"
  ```
  Ubicar después de `CLEARANCES_GOAL_LINE` para mantener el orden temático (acciones defensivas/físicas).

- [ ] Confirmar que el valor string `"fouls_drawn"` es único en el enum (no colisiona con ningún miembro existente).

- [ ] Verificar: `from sfa.domain.scoring.value_objects import ActionType; ActionType.FOULS_DRAWN` no lanza excepción.

---

### Task 2 — [DDD-Designer] Añadir `ActionType.CLEARANCES` al enum

**Archivos:** `domain/scoring/value_objects.py`

- [ ] Añadir al enum `ActionType` el miembro:
  ```
  CLEARANCES = "clearances"
  ```
  Ubicar inmediatamente después de `FOULS_DRAWN`.

- [ ] Confirmar que el valor string `"clearances"` es único en el enum.

- [ ] Verificar: `ActionType.CLEARANCES` importable sin error.

---

### Task 3 — Actualizar `BASE_POINTS_TABLE` con los nuevos valores

**Archivo:** `domain/scoring/services.py`

Depende de: Tasks 1 y 2 completados (los nuevos ActionType deben existir para poder añadirlos a la tabla).

- [ ] En el bloque `PositionGroup.FW`, reemplazar los valores actuales (0) y añadir las nuevas entradas:
  ```
  ActionType.BLOCKS:        150,
  ActionType.XA_NO_ASSIST:  150,   # ya en tabla con 150 — confirmar, no tocar
  ActionType.XG_NO_GOAL:     70,
  ActionType.FOULS_DRAWN:    50,
  ActionType.CLEARANCES:      0,
  ```

- [ ] En el bloque `PositionGroup.MF`:
  ```
  ActionType.BLOCKS:        100,
  ActionType.XA_NO_ASSIST:  120,   # ya en tabla con 120 — confirmar, no tocar
  ActionType.XG_NO_GOAL:     50,
  ActionType.FOULS_DRAWN:    35,
  ActionType.CLEARANCES:     20,
  ```

- [ ] En el bloque `PositionGroup.DF`:
  ```
  ActionType.BLOCKS:         70,
  ActionType.XA_NO_ASSIST:  180,   # ya en tabla con 180 — confirmar, no tocar
  ActionType.XG_NO_GOAL:     30,
  ActionType.FOULS_DRAWN:    20,
  ActionType.CLEARANCES:     25,
  ```

- [ ] Verificar que `XA_NO_ASSIST` ya tenía los valores correctos (FW=150, MF=120, DF=180) — si es así, no modificar esas entradas.

- [ ] Verificar que cada uno de los 3 bloques de la tabla tiene exactamente una entrada por cada miembro de `ActionType`. Si falta alguna entrada de los nuevos miembros, `score_match_stats()` lanzará `KeyError` en runtime.

---

### Task 4 — Conectar los nuevos stats al dict `stats_for_scoring` en el use case

**Archivo:** `application/use_cases/ingest_competition.py`

Depende de: Task 3 completado.

- [ ] Localizar el dict `stats_for_scoring` (líneas ~306-311 actuales):
  ```python
  stats_for_scoring = {
      ActionType.DUELS_WON: ps.duels_won,
      ActionType.TACKLES_INTERCEPTIONS: ps.tackles + ps.interceptions,
      ActionType.BLOCKS: ps.blocks,
      ActionType.DRIBBLES_WON: ps.dribbles_success,
  }
  ```

- [ ] Reemplazar por:
  ```python
  stats_for_scoring = {
      ActionType.DUELS_WON: ps.duels_won,
      ActionType.TACKLES_INTERCEPTIONS: ps.tackles + ps.interceptions,
      ActionType.BLOCKS: ps.blocks,
      ActionType.DRIBBLES_WON: ps.dribbles_success,
      ActionType.XA_NO_ASSIST: max(0, ps.passes_key - ps.assists),
      ActionType.XG_NO_GOAL: max(0, ps.shots_on - ps.goals),
      ActionType.FOULS_DRAWN: ps.fouls_drawn,
      ActionType.CLEARANCES: ps.clearances,
  }
  ```

- [ ] Confirmar que `ps.fouls_drawn` y `ps.clearances` están disponibles en `PlayerStatsRawDTO` (ya están, añadidos en 0002 — verificar imports si hubiera cambio).

- [ ] Confirmar que `max(0, ...)` se aplica solo a los valores derivados por resta (`XA_NO_ASSIST`, `XG_NO_GOAL`). Los campos directos (`fouls_drawn`, `clearances`) vienen del provider ya como `>= 0`.

- [ ] Verificar que no se necesita tocar `_add_to_breakdown` — los nuevos puntos se acumulan en el bucket `"stats"` igual que los existentes.

---

### Task 5 — Tests

**Archivos:** `tests/domain/scoring/test_base_points_table.py` (nuevo o existente), `tests/use_cases/test_new_stat_actions.py` (nuevo)

- [ ] **Test de tabla completa:** Para cada `PositionGroup`, verificar que todos los miembros de `ActionType` tienen una entrada en `BASE_POINTS_TABLE` (no hay `KeyError`):
  ```python
  def test_base_points_table_covers_all_action_types():
      for group in PositionGroup:
          for action in ActionType:
              assert action in BASE_POINTS_TABLE[group]
  ```

- [ ] **Test de valores acordados:** Verificar que los valores nuevos son exactamente los del acuerdo de producto:
  ```python
  assert BASE_POINTS_TABLE[PositionGroup.FW][ActionType.BLOCKS] == 150
  assert BASE_POINTS_TABLE[PositionGroup.MF][ActionType.BLOCKS] == 100
  assert BASE_POINTS_TABLE[PositionGroup.DF][ActionType.BLOCKS] == 70
  assert BASE_POINTS_TABLE[PositionGroup.FW][ActionType.XG_NO_GOAL] == 70
  assert BASE_POINTS_TABLE[PositionGroup.MF][ActionType.XG_NO_GOAL] == 50
  assert BASE_POINTS_TABLE[PositionGroup.DF][ActionType.XG_NO_GOAL] == 30
  assert BASE_POINTS_TABLE[PositionGroup.FW][ActionType.FOULS_DRAWN] == 50
  assert BASE_POINTS_TABLE[PositionGroup.MF][ActionType.FOULS_DRAWN] == 35
  assert BASE_POINTS_TABLE[PositionGroup.DF][ActionType.FOULS_DRAWN] == 20
  assert BASE_POINTS_TABLE[PositionGroup.FW][ActionType.CLEARANCES] == 0
  assert BASE_POINTS_TABLE[PositionGroup.MF][ActionType.CLEARANCES] == 20
  assert BASE_POINTS_TABLE[PositionGroup.DF][ActionType.CLEARANCES] == 25
  ```

- [ ] **Test de scoring end-to-end (FakeRepo pattern):** Usando el `FakeIngestionRepository` ya creado en 0002 (o extenderlo):
  - Jugador MF con `passes_key=3`, `assists=1`, `shots_on=4`, `goals=1`, `fouls_drawn=2`, `clearances=0`, `blocks=2`
  - Calcular manualmente: `XA_NO_ASSIST = max(0, 3-1) = 2`, `XG_NO_GOAL = max(0, 4-1) = 3`, `FOULS_DRAWN = 2`, `CLEARANCES = 0`, `BLOCKS = 2`
  - Verificar que `stats_pts > 0` y que el row STATS persisted tiene `pts` que incluye la contribución de estos nuevos campos.

- [ ] **Test de floor a cero:** Jugador con `passes_key=0`, `assists=1` (negativo sin floor) y `shots_on=1`, `goals=2` (negativo sin floor):
  - Verificar que `XA_NO_ASSIST = 0` y `XG_NO_GOAL = 0` (el `max(0, ...)` funciona).
  - Verificar que `stats_pts` no es negativo.

- [ ] **Test de FW sin clearances:** Jugador FW con `clearances=5`:
  - Verificar que los puntos de CLEARANCES para ese jugador son 0 (el `base_pts == 0` en FW hace que `score_match_stats` lo omita).

- [ ] Correr `pytest tests/` antes y después — los tests previos (0001, 0002) deben seguir pasando sin modificación.

---

## Agent Routing Brief

| Task | Agente requerido | Motivo |
|------|------------------|--------|
| Task 1 | @DDD-Designer | Nuevo miembro de enum `ActionType` — es un value object del dominio de scoring |
| Task 2 | @DDD-Designer | Nuevo miembro de enum `ActionType` — es un value object del dominio de scoring |
| Task 3 | Implementación directa | Actualización de tabla de configuración de dominio; no hay nuevo comportamiento |
| Task 4 | Implementación directa | Wiring de capa de aplicación |
| Task 5 | Implementación directa | Tests unitarios |

**Orden de despacho:** Tasks 1 y 2 deben ir a @DDD-Designer primero. Una vez aprobados y mergeados, Tasks 3–5 pueden implementarse en secuencia por un único agente de implementación.

---

## Criterio de completitud

El spec está completo cuando:

1. `pytest tests/` pasa al 100% incluyendo los tests nuevos del Task 5.
2. `ActionType.FOULS_DRAWN` y `ActionType.CLEARANCES` existen en el enum y son importables.
3. Todos los ActionType tienen entrada en `BASE_POINTS_TABLE` para los 3 grupos posicionales (el test de tabla completa lo garantiza).
4. Tras una ingesta de La Liga: un jugador MF con `blocks > 0` o `passes_key > assists` acumula `stats_pts > 0` en el row STATS de `player_events`.
5. Un jugador DEL con `clearances > 0` pero `base_pts == 0` para CLEARANCES-FW no genera puntos extra (verificable vía el test de FW sin clearances).
6. No hay regresión en `matches_played` ni en los puntos de acciones previas (DUELS_WON, TACKLES_INTERCEPTIONS, DRIBBLES_WON).
