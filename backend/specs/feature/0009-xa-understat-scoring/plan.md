# Plan: Spec 0009 — xa (Understat) como señal de scoring de creatividad ofensiva

## Archivos a crear

_Ninguno. Esta feature no requiere archivos nuevos._

## Archivos a modificar

### Paso 1 — Enrich: escribir xa desde Understat a player_stats

- [ ] `src/sfa/application/use_cases/enrich_with_understat.py` — después del name matching,
  llamar a `update_player_stats_from_fbref` con `{"xa": dto.xa}` para escribir el xa de
  temporada a todas las filas del player-season. Actualizar `stats_enriched` en el resultado.

### Paso 2 — Score: usar xa en el recálculo

- [ ] `src/sfa/domain/enrichment_ports.py` — extender `PlayerStatsEventRecalcRow` con campo
  `xa: float`
- [ ] `src/sfa/infrastructure/repositories/enrichment_repository.py` — incluir `PlayerStats.xa`
  en la query de `get_stats_events_for_recalc` y mapearlo en el constructor del DTO
- [ ] `src/sfa/application/use_cases/recalculate_scores.py` — cambiar el valor de
  `ActionType.XA_NO_ASSIST` en Phase 2 para usar `xa` con fallback a `passes_key`

### Tests

- [ ] `tests/use_cases/test_enrich_with_understat.py` — añadir casos que verifican que `xa`
  se escribe a `player_stats` cuando el jugador es matcheado
- [ ] `tests/use_cases/test_recalculate_scores.py` — añadir casos para los tres escenarios:
  xa disponible, xa == 0 (fallback), xa parcialmente disponible

---

## Checklist de implementación

### 1. Extender `EnrichWithUnderstatUseCase` para escribir xa

- [ ] En `src/sfa/application/use_cases/enrich_with_understat.py`, después del bloque de
  PSxG (líneas 97-106), añadir la escritura de `xa` a `player_stats`:

  ```python
  # Write xa season total to player_stats (only where still 0)
  await self._repo.update_player_stats_from_fbref(
      player.id,
      season,
      {"xa": dto.xa},
  )
  stats_enriched += 1
  ```

  Notas de implementación:
  - El método `update_player_stats_from_fbref` ya implementa `CASE WHEN xa = 0 THEN :val
    ELSE xa END`. Si Understat devuelve `xa = 0.0` para un jugador (muy raro pero posible),
    no sobrescribe nada — correcto.
  - La variable `stats_enriched` ya existe en el scope del método (inicializada en la firma
    del `EnrichmentResult`). Actualmente siempre retorna `0` — hay que inicializarla antes
    del loop: `stats_enriched = 0`.
  - `dto.xa` es `float` directamente de `UnderstatPlayerDTO`. No requiere conversión.
  - La escritura de `xa` debe ocurrir **independientemente** de si hay eventos sin PSxG.
    Actualmente el bloque de PSxG tiene un `continue` temprano si `not events`. Hay que
    asegurarse de que `update_player_stats_from_fbref` se llame **antes** del `if not events:
    continue`, o moverlo fuera del condicional.

  Estructura correcta del loop interno:

  ```python
  for dto in players:
      player, score = find_best_match(dto.player_name, db_index)

      if player is None:
          players_skipped += 1
          continue

      players_matched += 1

      # Save understat_id
      await self._repo.update_player_external_ids(
          player.id,
          fbref_id=None,
          understat_id=int(dto.understat_id),
      )

      # Write xa season total to player_stats (only where still 0)
      if dto.xa > 0:
          await self._repo.update_player_stats_from_fbref(
              player.id, season, {"xa": dto.xa},
          )
          stats_enriched += 1

      # Only enrich PSxG where FBref has not already covered it
      events = await self._repo.get_player_events_without_psxg(
          player.id, competition_id, season
      )
      if not events:
          continue

      for event in events:
          await self._repo.update_event_psxg(event.id, dto.xg_per_shot)
          events_enriched += 1
  ```

  La guarda `if dto.xa > 0` evita llamadas de DB innecesarias para los casos raros donde
  Understat reporta xa=0.0 (el jugador tuvo 0 xA en la temporada).

- [ ] Actualizar el `return EnrichmentResult(...)` al final del bloque `try` para que
  `stats_enriched=stats_enriched` en lugar de `stats_enriched=0`.

### 2. Extender el DTO `PlayerStatsEventRecalcRow`

- [ ] En `src/sfa/domain/enrichment_ports.py`, añadir `xa: float` como campo en el dataclass
  `PlayerStatsEventRecalcRow`, después de `assists` y antes de `rating`:

  ```python
  @dataclass(frozen=True)
  class PlayerStatsEventRecalcRow:
      event_id: int
      player_id: int
      player_position: str
      m1: float
      m2: float
      current_pts: float
      duels_won: int
      tackles_won: int
      interceptions: int
      blocks: int
      dribbles_won: int
      passes_key: int
      shots_on: int
      fouls_drawn: int
      clearances: int
      goals: int
      assists: int
      xa: float          # ← nuevo campo
      rating: float | None
  ```

  El campo no tiene valor por defecto porque el repositorio siempre lo provee.

### 3. Extender la query `get_stats_events_for_recalc` en el repositorio

- [ ] En `src/sfa/infrastructure/repositories/enrichment_repository.py`, en el método
  `get_stats_events_for_recalc`:

  Añadir `PlayerStats.xa` al `select(...)` después de `PlayerStats.assists` (index 16).
  `xa` quedará en index 17, `rating` en index 18.

  Actualizar el constructor de `PlayerStatsEventRecalcRow` en el list comprehension:

  ```python
  PlayerStatsEventRecalcRow(
      event_id=row[0],
      player_id=row[1],
      player_position=row[2].value if hasattr(row[2], "value") else str(row[2]),
      m1=float(row[3]),
      m2=float(row[4]),
      current_pts=float(row[5]),
      duels_won=int(row[6]),
      tackles_won=int(row[7]),
      interceptions=int(row[8]),
      blocks=int(row[9]),
      dribbles_won=int(row[10]),
      passes_key=int(row[11]),
      shots_on=int(row[12]),
      fouls_drawn=int(row[13]),
      clearances=int(row[14]),
      goals=int(row[15]),
      assists=int(row[16]),
      xa=float(row[17]),           # ← nuevo
      rating=float(row[18]) if row[18] is not None else None,
  )
  ```

### 4. Modificar Phase 2 en `recalculate_scores.py`

- [ ] En `src/sfa/application/use_cases/recalculate_scores.py`, dentro del loop de Phase 2,
  reemplazar la línea:

  ```python
  ActionType.XA_NO_ASSIST: max(0, event.passes_key - event.assists),
  ```

  por la lógica con fallback:

  ```python
  ActionType.XA_NO_ASSIST: (
      event.xa
      if event.xa > 0
      else max(0, event.passes_key - event.assists)
  ),
  ```

  **Regla de fallback completa:**
  - Si `event.xa > 0.0` → usar `event.xa` directamente como float.
    Ejemplo: jugador con xa=2.3 en temporada → `2.3 × base_pts × combined` para MF.
  - Si `event.xa == 0.0` → usar `max(0, event.passes_key - event.assists)`.
    Aplica para: Champions League (Understat no cubre UCL), jugadores no matcheados en
    Understat, o enrichment no ejecutado aún.

  No hay cambios en `BASE_POINTS_TABLE` ni en `SFAScoringService`. El servicio ya acepta
  `float` como value en `dict[ActionType, int | float]`.

### 5. Tests — `EnrichWithUnderstatUseCase`

- [ ] En `tests/use_cases/test_enrich_with_understat.py` (crear si no existe), extender o
  crear la clase `FakeEnrichmentRepository` implementando `EnrichmentRepositoryPort`
  completo (todos los métodos del Protocol — obligatorio por `@runtime_checkable`).

  El Fake debe registrar las llamadas a `update_player_stats_from_fbref`:

  ```python
  class FakeEnrichmentRepository:
      def __init__(self):
          self.stats_updates: list[tuple[int, str, dict]] = []
          # ... resto de listas de seguimiento

      async def update_player_stats_from_fbref(
          self, player_id: int, season: str, stats: dict,
      ) -> None:
          self.stats_updates.append((player_id, season, stats))
  ```

  Scenarios a cubrir:

  **a) `test_xa_written_to_player_stats_when_player_matched`**
  - Setup: un jugador matcheado con `dto.xa = 1.8`
  - Assertion: `repo.stats_updates` contiene exactamente una entrada con `{"xa": 1.8}` para
    el `player_id` correcto

  **b) `test_xa_not_written_when_player_not_matched`**
  - Setup: Understat devuelve un jugador con nombre que no matchea ningún player en DB
  - Assertion: `repo.stats_updates` está vacío

  **c) `test_xa_not_written_when_dto_xa_is_zero`**
  - Setup: jugador matcheado con `dto.xa = 0.0`
  - Assertion: `repo.stats_updates` está vacío (la guarda `if dto.xa > 0` lo evita)

  **d) `test_stats_enriched_count_reflects_xa_writes`**
  - Setup: 3 jugadores matcheados, 2 con `dto.xa > 0`, 1 con `dto.xa = 0.0`
  - Assertion: `result.stats_enriched == 2`

  **e) `test_champions_league_returns_early_without_xa_writes`**
  - Setup: `competition_name = "Champions League"`
  - Assertion: `result.stats_enriched == 0`, `repo.stats_updates` vacío

### 6. Tests — `RecalculateScoresUseCase`

- [ ] En `tests/use_cases/test_recalculate_scores.py` (crear si no existe), extender o
  crear la clase `FakeEnrichmentRepository` implementando `EnrichmentRepositoryPort`
  completo.

  Scenarios a cubrir en `TestRecalculateScoresUseCase`:

  **a) `test_xa_available_uses_xa_for_scoring`**
  - Fixture: jugador MF con `xa=2.3`, `passes_key=4`, `assists=1`
  - Assertion: `update_event_pts` recibe pts calculados con `2.3` (no con `3`)

  **b) `test_xa_zero_falls_back_to_passes_key`**
  - Fixture: jugador MF con `xa=0.0`, `passes_key=4`, `assists=1`
  - Assertion: el valor de `XA_NO_ASSIST` es `3` (fallback a `max(0, 4-1)`)

  **c) `test_xa_zero_with_no_key_passes_produces_zero_contribution`**
  - Fixture: jugador MF con `xa=0.0`, `passes_key=0`, `assists=0`
  - Assertion: `XA_NO_ASSIST` contribuye 0 pts

  **d) `test_xa_positive_smaller_than_key_pass_count_still_used`**
  - Fixture: jugador FW con `xa=0.4`, `passes_key=3`, `assists=2`
  - Assertion: valor usado es `0.4`, no `1`. Valida que `xa=0.4 > 0` activa la rama xa.

  Todos los tests son `@pytest.mark.anyio`. Usar Fakes — nunca `MagicMock`.

### 7. Lint y formato

- [ ] Verificar `flake8 src/ tests/` — sin errores E302, E501, F401, F821
- [ ] Verificar `isort --check-only src/ tests/` — sin errores de orden de imports
- [ ] Verificar `pytest tests/` pasa con coverage ≥80%

---

## Agent Routing Brief

**DDD Designer needed:** no

Esta feature no requiere nuevas entidades de dominio. `ActionType.XA_NO_ASSIST` ya existe
y es semánticamente correcto para el dato que ahora lo alimenta. `BASE_POINTS_TABLE` y
`SFAScoringService` no cambian. Los cambios son: (1) escribir un campo nuevo desde un use
case de enrich existente, (2) leer ese campo en el DTO de recálculo, (3) usarlo en el loop
de Phase 2. Todo dentro de la capa de aplicación e infraestructura.

---

## Verificación

1. Ejecutar `EnrichWithUnderstatUseCase` para La Liga 2024-2025. Verificar que
   `SELECT DISTINCT xa FROM player_stats WHERE season = '2024-2025' AND xa > 0` retorna
   resultados (antes del fix todas las filas tienen `xa = 0`).

2. Ejecutar `RecalculateScoresUseCase(competition_id=<la_liga>, season="2024-2025")` y
   comparar puntos totales de jugadores creativos (Pedri, Vitinha, Bellingham) antes y
   después del cambio.

3. Verificar via query que el breakdown de `SFASeasonScore` para un jugador con `xa > 0`
   muestra `xa_no_assist.pts` diferente al calculado con `passes_key - assists`.

4. Verificar que un jugador de Champions League (UCL, no enriquecido por Understat —
   `xa=0.0` en DB) sigue recibiendo puntos via fallback `passes_key - assists`.

5. `pytest tests/use_cases/test_enrich_with_understat.py -v` — todos los 5 tests verdes.

6. `pytest tests/use_cases/test_recalculate_scores.py -v` — todos los 4 tests verdes.
