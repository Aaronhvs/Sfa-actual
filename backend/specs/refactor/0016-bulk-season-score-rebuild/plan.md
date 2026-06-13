# Plan: Bulk Season Score Rebuild (refactor/0016)

## Orden de implementación

Este refactor debe completarse ANTES de `feature/0016-full-recalculation-pipeline`,
ya que esa feature depende del método `bulk_rebuild_season_scores()` en el repo y del
comportamiento corregido del use case.

---

## Archivos a modificar

- [ ] `src/sfa/domain/scoring_ports.py`
- [ ] `src/sfa/infrastructure/repositories/player_event_score_repository.py`
- [ ] `src/sfa/application/use_cases/calculate_scores_for_rules_version.py`

## Archivos a crear

- [ ] `tests/use_cases/test_bulk_season_score_rebuild.py`

---

## Checklist de implementación

### 1. Verificación previa — constraint de `sfa_season_scores`

Antes de escribir la query SQL, verificar el nombre exacto de la constraint única en la
tabla `sfa_season_scores`. Buscar en:

- `src/sfa/infrastructure/models/scores/models.py` (o equivalente).
- Buscar `UniqueConstraint` o `uq_` en ese archivo.

El nombre de la constraint se usará en el `ON CONFLICT ON CONSTRAINT <nombre>`.

Alternativa si no hay nombre de constraint: usar la forma column-list:
```sql
ON CONFLICT (player_id, competition_id, season, rules_version_id)
```

- [ ] Anotar el nombre de la constraint (o confirmar que se usará column-list).

---

### 2. Port: nuevo método en `PlayerEventScoreRepositoryPort`

**Archivo:** `src/sfa/domain/scoring_ports.py`

- [ ] Agregar el método al Protocol `PlayerEventScoreRepositoryPort`. Ubicarlo DESPUÉS de
  `get_competition_name_map` y ANTES del cierre del Protocol:

```python
async def bulk_rebuild_season_scores(
    self,
    rules_version_id: int,
    season: str,
    competition_id: int | None = None,
) -> int: ...
```

  El `int` retornado es el número de filas afectadas (insertadas + actualizadas).

  **Criterio de completitud:** el Protocol tiene el método. Si en el codebase existen Fakes
  que implementan `PlayerEventScoreRepositoryPort`, deben actualizarse para incluir este método
  (retornando `0` silenciosamente en los Fakes).

---

### 3. Implementación del método bulk en `PlayerEventScoreRepository`

**Archivo:** `src/sfa/infrastructure/repositories/player_event_score_repository.py`

- [ ] Agregar el import de `text` de SQLAlchemy al inicio del archivo (verificar que ya esté;
  si no, agregar: `from sqlalchemy import delete, func, select, text`).

- [ ] Implementar el método al final de la clase `PlayerEventScoreRepository`:

```python
async def bulk_rebuild_season_scores(
    self,
    rules_version_id: int,
    season: str,
    competition_id: int | None = None,
) -> int:
    """Rebuild sfa_season_scores for all (player, competition) pairs in one SQL statement.

    Uses INSERT ... ON CONFLICT DO UPDATE to upsert totals and JSONB breakdown.
    achievement_bonus_pts is intentionally NOT updated — it is managed by
    CompetitionAchievementRepository.update_season_score_bonus().
    """
    competition_filter_cte = (
        "AND competition_id = :competition_id"
        if competition_id is not None
        else ""
    )

    sql = text(f"""
        WITH action_data AS (
            SELECT
                player_id,
                competition_id,
                action_type,
                COUNT(*)                              AS cnt,
                ROUND(SUM(final_points)::numeric, 2)  AS pts
            FROM player_event_scores
            WHERE rules_version_id = :rules_version_id
              AND season            = :season
              {competition_filter_cte}
            GROUP BY player_id, competition_id, action_type
        ),
        player_totals AS (
            SELECT
                player_id,
                competition_id,
                ROUND(SUM(final_points)::numeric, 2)  AS total_pts,
                COUNT(DISTINCT fixture_id)             AS matches_played
            FROM player_event_scores
            WHERE rules_version_id = :rules_version_id
              AND season            = :season
              {competition_filter_cte}
            GROUP BY player_id, competition_id
        )
        INSERT INTO sfa_season_scores
            (player_id, competition_id, season, rules_version_id,
             total_pts, matches_played, breakdown, achievement_bonus_pts)
        SELECT
            pt.player_id,
            pt.competition_id,
            :season,
            :rules_version_id,
            pt.total_pts,
            pt.matches_played,
            jsonb_object_agg(
                ad.action_type,
                jsonb_build_object(
                    'count', ad.cnt,
                    'pts',   ad.pts,
                    'pct',   ROUND(
                        ad.pts / NULLIF(pt.total_pts, 0) * 100,
                        1
                    )
                )
            )  AS breakdown,
            0  AS achievement_bonus_pts
        FROM player_totals pt
        JOIN action_data ad
            ON  ad.player_id      = pt.player_id
            AND ad.competition_id  = pt.competition_id
        GROUP BY
            pt.player_id,
            pt.competition_id,
            pt.total_pts,
            pt.matches_played
        ON CONFLICT (player_id, competition_id, season, rules_version_id)
        DO UPDATE SET
            total_pts      = EXCLUDED.total_pts,
            matches_played = EXCLUDED.matches_played,
            breakdown      = EXCLUDED.breakdown
    """)

    params: dict = {
        "rules_version_id": rules_version_id,
        "season": season,
    }
    if competition_id is not None:
        params["competition_id"] = competition_id

    result = await self._session.execute(sql, params)
    await self._session.flush()
    return result.rowcount if result.rowcount is not None else 0
```

  **Notas de implementación:**
  - `competition_filter_cte` es una string de filtro SQL que se interpola en el template.
    Es seguro porque `competition_id` proviene de parámetros internos tipados, no de entrada
    de usuario. El valor `:competition_id` sí se pasa como parámetro bound.
  - `ROUND(...::numeric, 2)` garantiza que el tipo sea NUMERIC en PostgreSQL, compatible con
    la columna `total_pts NUMERIC`.
  - `COUNT(DISTINCT fixture_id)` para `matches_played` es consistente con el método
    `get_player_event_totals_for_season` existente.
  - `NULLIF(pt.total_pts, 0)` previene división por cero cuando un jugador tiene solo eventos
    con 0 puntos.
  - El `ON CONFLICT` usa column-list; si la DB tiene un constraint con nombre (verificado en
    el paso 1), preferir `ON CONFLICT ON CONSTRAINT <nombre>`.

  **Criterio de completitud:** el método existe, compila sin errores de importación, y en
  un test de integración básico (o test con Fake) retorna un entero.

---

### 4. Modificar `CalculateScoresForRulesVersionUseCase`

**Archivo:** `src/sfa/application/use_cases/calculate_scores_for_rules_version.py`

#### 4a. Eliminar el loop de rebuild

- [ ] Localizar el bloque que empieza en la línea 128 del archivo actual:

```python
# Rebuild season scores for all affected (player, competition) pairs
players_updated = 0
for pid, cid in affected_player_competition_pairs:
    total_pts, matches_played = await self._event_score_repo.get_player_event_totals_for_season(
        player_id=pid,
        season=season,
        competition_id=cid,
        rules_version_id=rules_version_id,
    )
    breakdown = await self._event_score_repo.get_season_score_breakdown(
        player_id=pid,
        season=season,
        competition_id=cid,
        rules_version_id=rules_version_id,
    )
    if total_pts > 0:
        for key in breakdown:
            pts_val = breakdown[key]["pts"]
            breakdown[key]["pct"] = round(pts_val / total_pts * 100, 1) if total_pts > 0 else 0.0

    await self._scoring_repo.upsert_season_score(
        player_id=pid,
        competition_id=cid,
        season=season,
        total_pts=total_pts,
        matches_played=matches_played,
        breakdown=breakdown,
        rules_version_id=rules_version_id,
    )
    players_updated += 1
```

- [ ] **Reemplazar** ese bloque completo con:

```python
# Bulk rebuild season scores for all affected (player, competition) pairs
# Replaces the O(n*c) loop with a single SQL INSERT ... ON CONFLICT DO UPDATE.
# achievement_bonus_pts is preserved by the bulk query (not overwritten).
players_updated = await self._event_score_repo.bulk_rebuild_season_scores(
    rules_version_id=rules_version_id,
    season=season,
    competition_id=competition_id,  # None = all competitions; specific = scoped rebuild
)
```

#### 4b. Actualizar el log final

- [ ] El log al final del método usa `players_updated` — verificar que sigue siendo correcto.
  Con el bulk rebuild, `players_updated` es ahora el `rowcount` de la query SQL (número de
  filas de `sfa_season_scores` insertadas o actualizadas). El log se mantiene como está.

#### 4c. Verificar que `_scoring_repo` puede eliminarse del constructor si ya no se usa

- [ ] Verificar si `self._scoring_repo` se usa en algún otro método del use case además del
  loop de rebuild. Buscar todas las ocurrencias de `self._scoring_repo` en el archivo.
  - Si no hay otras ocurrencias: eliminar `scoring_repo` del constructor y del parámetro.
  - Si hay otras ocurrencias: mantener el constructor tal cual.

  **Nota:** el parámetro `scoring_repo: ScoringRepositoryPort` en `__init__` puede eliminarse
  si no queda ninguna referencia. Esto simplifica el wiring en `dependencies.py`.

- [ ] Si se elimina `scoring_repo` del constructor, actualizar:
  - `core/dependencies.py`: `get_calculate_scores_for_rules_version_use_case()` — eliminar
    el parámetro `scoring_repo`.
  - `tasks/calculate_scores_for_rules_version_task.py`: eliminar la instanciación de
    `ScoringRepository` y el argumento correspondiente.

  **Criterio de completitud:** el use case compila sin errores, y el loop O(n×c) ya no existe.

---

### 5. Actualizar Fakes existentes en tests

- [ ] Buscar en `tests/` todos los archivos que usan un Fake de `PlayerEventScoreRepositoryPort`.
  Comando: buscar `PlayerEventScoreRepositoryPort` o `FakePlayerEventScoreRepository` en el
  directorio `tests/`.

- [ ] Para cada Fake encontrado, agregar la implementación del nuevo método:

```python
async def bulk_rebuild_season_scores(
    self,
    rules_version_id: int,
    season: str,
    competition_id: int | None = None,
) -> int:
    return 0  # Fake: no-op, returns 0 rows
```

  **Criterio de completitud:** `pytest tests/` pasa sin `AttributeError` relacionado con
  `bulk_rebuild_season_scores`.

---

### 6. Tests del nuevo método

**Archivo:** `tests/use_cases/test_bulk_season_score_rebuild.py`

Los tests de este archivo validan la lógica del use case con el nuevo path. No testean el
SQL directamente (eso sería un test de integración).

- [ ] Crear `FakePlayerEventScoreRepository` que implementa `PlayerEventScoreRepositoryPort`:

  - `get_events_for_recalc(...)` → retorna lista configurable de `PlayerEventRawContextDTO`.
  - `upsert_event_score(...)` → registra en `self.upserted_scores: list`.
  - `event_score_exists(...)` → retorna `False` siempre (force mode).
  - `bulk_rebuild_season_scores(...)` → registra los parámetros recibidos en
    `self.rebuild_calls: list[dict]` y retorna el número de pares únicos
    (player_id, competition_id) que habría afectado (calculado de los scores upserted).
  - `get_competition_name_map()` → retorna `{}`.
  - Resto de métodos → implementación mínima (retornar defaults o `NotImplementedError`).

- [ ] Crear `FakeScoringRulesVersionRepository` que implementa
  `ScoringRulesVersionRepositoryPort`:
  - `get_version_by_id(version_id)` → retorna un `ScoringRulesVersion` válido con
    `ScoringConfig.default_v2()`.

- [ ] Tests:

  **`test_bulk_rebuild_called_instead_of_loop`**
  - Setup: 2 eventos de 2 jugadores distintos en 2 competiciones.
  - Ejecutar `CalculateScoresForRulesVersionUseCase.execute(...)`.
  - Assert: `fake_repo.rebuild_calls` tiene exactamente 1 llamada (no el loop).
  - Assert: `result.players_updated == 0` o el valor retornado por el Fake.

  **`test_bulk_rebuild_receives_correct_scope_all_competitions`**
  - Setup: `competition_id=None` en el execute.
  - Assert: `bulk_rebuild_season_scores` fue llamado con `competition_id=None`.

  **`test_bulk_rebuild_receives_correct_scope_single_competition`**
  - Setup: `competition_id=39` en el execute.
  - Assert: `bulk_rebuild_season_scores` fue llamado con `competition_id=39`.

  **`test_bulk_rebuild_receives_correct_rules_version_and_season`**
  - Assert: `rules_version_id` y `season` pasados al bulk rebuild coinciden con los del execute.

  **`test_no_events_skips_bulk_rebuild`**
  - Setup: `get_events_for_recalc` retorna `[]`.
  - Assert: `bulk_rebuild_season_scores` NO fue llamado (ya que `affected_player_competition_pairs`
    es vacío y no hay nada que rebuild).
  - **IMPORTANTE:** verificar si el use case llama a `bulk_rebuild_season_scores` incluso cuando
    no hay eventos afectados. Si el use case llama siempre al bulk (no condicional), ajustar el
    test para reflejar eso. La decisión de si llamar incondicionalmente o solo cuando hay pares
    afectados se toma durante la implementación.

  **`test_result_has_status_completed_on_success`**
  - Assert: `result.status == "completed"`.

  **Criterio de completitud:** `pytest tests/use_cases/test_bulk_season_score_rebuild.py -v`
  pasa todos los tests.

---

### 7. Verificación de la query SQL (manual o test de integración)

La query SQL no se puede verificar con Fakes. Después de implementar el paso 3, ejecutar
manualmente contra la DB de desarrollo:

```sql
-- Verificación 1: la query no falla en vacío
-- (ejecutar con rules_version_id y season que no existan)
WITH action_data AS (
    SELECT player_id, competition_id, action_type, COUNT(*) AS cnt,
           ROUND(SUM(final_points)::numeric, 2) AS pts
    FROM player_event_scores
    WHERE rules_version_id = 999999 AND season = 'test'
    GROUP BY player_id, competition_id, action_type
),
player_totals AS (
    SELECT player_id, competition_id,
           ROUND(SUM(final_points)::numeric, 2) AS total_pts,
           COUNT(DISTINCT fixture_id) AS matches_played
    FROM player_event_scores
    WHERE rules_version_id = 999999 AND season = 'test'
    GROUP BY player_id, competition_id
)
SELECT COUNT(*) FROM player_totals;
-- Resultado esperado: 0 filas, sin error

-- Verificación 2: el breakdown tiene la estructura correcta para un jugador conocido
-- (ejecutar DESPUÉS de llamar al método con datos reales)
SELECT player_id, competition_id, total_pts, matches_played, breakdown
FROM sfa_season_scores
WHERE rules_version_id = <rv_id> AND season = '2024'
LIMIT 5;
-- Resultado esperado: breakdown es JSONB con estructura {"goal": {"count": N, "pts": X, "pct": Y}, ...}
```

- [ ] La query de verificación 1 retorna 0 filas sin error.
- [ ] La query de verificación 2 retorna breakdown con la estructura esperada.
- [ ] Comparar un jugador específico (ej. Bruno Fernandes, player_id conocido) entre el breakdown
  del loop antiguo y el nuevo bulk: los valores de `count`, `pts` y `pct` deben coincidir
  (con tolerancia de ±0.1 en `pct` por diferencias de redondeo).

---

### 8. Verificación final

- [ ] `pytest tests/` pasa sin errores nuevos.
- [ ] `flake8 src/ tests/` sin errores nuevos (max-line-length=120).
- [ ] `isort --check-only src/ tests/` sin errores.
- [ ] Smoke test de rendimiento: disparar recálculo completo y comparar tiempo total.
  Antes: ~35-40 min. Después del refactor: el rebuild debe completarse en <30 segundos
  (la mayor parte del tiempo será el loop de scoring de los 92k eventos, no el rebuild).

---

## Agent Routing Brief

**DDD Designer needed:** No. Este refactor no crea nuevas entidades de dominio ni nuevos
Protocols. Modifica un Port existente con un método adicional e implementa ese método en
el repositorio y el use case correspondiente.

| Item | Skill a usar |
|---|---|
| Paso 1 (verificación constraint) | Ninguno — inspección directa del modelo SQLAlchemy |
| Paso 2 (Port) | `/sfa-repository` |
| Paso 3 (Repository) | `/sfa-repository` |
| Paso 4 (Use Case) | `/sfa-use-case` |
| Paso 5 (Fakes existentes) | `/sfa-test` |
| Paso 6 (Tests nuevos) | `/sfa-test` |
| Paso 7 (verificación SQL) | Bash / psql directo |

## Riesgo principal

La query SQL con `jsonb_object_agg` en un INSERT ... ON CONFLICT no es trivial. El riesgo
mayor es que el `breakdown` generado difiera del esperado (ej. formato de tipos, redondeo
diferente). Mitigación: el paso 7 incluye una comparación explícita para un jugador conocido.

Si se detecta una discrepancia estructural en el `pct`, la causa más probable es que
`ROUND(...::numeric, 1)` en PostgreSQL redondee diferente a `round(..., 1)` de Python para
valores en el límite de .5. Tolerancia aceptable: ±0.1 en `pct`.
