# Bulk Season Score Rebuild — Eliminación del loop O(n×c) en el rebuild de season_scores

## Contexto del problema

En `CalculateScoresForRulesVersionUseCase.execute()`, después de calcular los
`PlayerEventScore`, existe el siguiente bloque de rebuild (líneas 128-155):

```python
for pid, cid in affected_player_competition_pairs:
    total_pts, matches_played = await self._event_score_repo.get_player_event_totals_for_season(
        player_id=pid, season=season, competition_id=cid, rules_version_id=rules_version_id,
    )
    breakdown = await self._event_score_repo.get_season_score_breakdown(
        player_id=pid, season=season, competition_id=cid, rules_version_id=rules_version_id,
    )
    # ... calcula pct ...
    await self._scoring_repo.upsert_season_score(...)
```

Con 10,896 jugadores × ~2 competiciones promedio = **~21,000 queries individuales** ejecutados
secuencialmente. Esto representa el cuello de botella principal de los 35-40 minutos que
tarda el recálculo completo.

La solución es reemplazar este triple-loop de queries por una sola instrucción SQL bulk:

```sql
INSERT INTO sfa_season_scores (player_id, competition_id, season, rules_version_id,
    total_pts, matches_played, breakdown, achievement_bonus_pts)
SELECT
    pes.player_id,
    pes.competition_id,
    pes.season,
    :rules_version_id,
    SUM(pes.final_points),
    COUNT(DISTINCT pes.fixture_id),
    jsonb_object_agg(
        pes.action_type,
        jsonb_build_object(
            'count', action_counts.cnt,
            'pts',   action_counts.pts,
            'pct',   ROUND(action_counts.pts / NULLIF(player_totals.total_pts, 0) * 100, 1)
        )
    ),
    0  -- achievement_bonus_pts inicial; se actualiza por CalculateAchievementBonusesUseCase
FROM player_event_scores pes
JOIN (...) action_counts ON ...
JOIN (...) player_totals ON ...
WHERE pes.rules_version_id = :rules_version_id
  AND pes.season = :season
GROUP BY pes.player_id, pes.competition_id, pes.season
ON CONFLICT (player_id, competition_id, season, rules_version_id)
DO UPDATE SET
    total_pts = EXCLUDED.total_pts,
    matches_played = EXCLUDED.matches_played,
    breakdown = EXCLUDED.breakdown
    -- NO SE TOCA achievement_bonus_pts
```

## Restricciones técnicas

1. **Separación de capas:** la query SQL bulk va exclusivamente en `PlayerEventScoreRepository`.
   El `CalculateScoresForRulesVersionUseCase` solo llama al método del repo; no conoce SQL.
2. **`achievement_bonus_pts` intacto:** el `DO UPDATE SET` NO incluye `achievement_bonus_pts`.
   PostgreSQL preserva el valor existente en la columna cuando no aparece en la cláusula SET.
   El valor inicial en un INSERT nuevo es `0`; se actualiza más tarde por
   `CompetitionAchievementRepository.update_season_score_bonus()`.
3. **Breakdown JSONB con `pct`:** el porcentaje requiere conocer el total de puntos del
   jugador en esa competición. Se resuelve con una subquery `player_totals` que calcula
   `SUM(final_points)` por `(player_id, competition_id)` dentro del mismo SELECT, evitando
   un segundo roundtrip.
4. **Backward compatibility del Port Protocol:** el método `bulk_rebuild_season_scores()` se
   agrega al `PlayerEventScoreRepositoryPort`. Los Fakes existentes en tests deben actualizarse
   para implementar el nuevo método (puede devolver `None` silenciosamente).
5. **`ScoringRepositoryPort` (de `ingestion_ports.py`):** el método `upsert_season_score()`
   existente en `ScoringRepository` se mantiene sin cambios. Se usará para el scope específico
   (by match, by player). El bulk rebuild no lo reemplaza para llamadas individuales.
6. **Scope opcional (`competition_id`):** `bulk_rebuild_season_scores` acepta
   `competition_id: int | None`. Si se pasa, filtra por esa competición. Si es `None`, procesa
   todas las competiciones de la season para ese `rules_version_id`.
7. **La query SQL se ejecuta vía `text()` de SQLAlchemy** con parámetros bound. No se usa
   el ORM para este statement porque `jsonb_object_agg` con subqueries correlacionadas es
   difícil de expresar con el API de SQLAlchemy Core sin perder legibilidad.

## Análisis del breakdown JSONB

El breakdown actual se construye en Python así:
```python
# get_season_score_breakdown retorna:
{ "goal": {"count": 3, "pts": 450.0}, "assist": {"count": 2, "pts": 180.0}, ... }
# luego en el use case se agrega "pct":
{ "goal": {"count": 3, "pts": 450.0, "pct": 42.5}, ... }
```

En SQL, el equivalente usando `jsonb_object_agg` sobre una subquery que ya calcula count, pts
y pct por action_type:

```sql
-- Subquery action_data: cuenta y suma por (player, competition, action_type)
WITH action_data AS (
    SELECT
        player_id,
        competition_id,
        action_type,
        COUNT(*) AS cnt,
        ROUND(SUM(final_points)::numeric, 2) AS pts
    FROM player_event_scores
    WHERE rules_version_id = :rules_version_id
      AND season = :season
    GROUP BY player_id, competition_id, action_type
),
-- Subquery player_totals: total de puntos por (player, competition) para calcular pct
player_totals AS (
    SELECT
        player_id,
        competition_id,
        ROUND(SUM(final_points)::numeric, 2) AS total_pts,
        COUNT(DISTINCT fixture_id) AS matches_played
    FROM player_event_scores
    WHERE rules_version_id = :rules_version_id
      AND season = :season
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
            'pct',   ROUND(ad.pts / NULLIF(pt.total_pts, 0) * 100, 1)
        )
    ) AS breakdown,
    0 AS achievement_bonus_pts
FROM player_totals pt
JOIN action_data ad
    ON ad.player_id = pt.player_id
    AND ad.competition_id = pt.competition_id
GROUP BY pt.player_id, pt.competition_id, pt.total_pts, pt.matches_played
ON CONFLICT (player_id, competition_id, season, rules_version_id)
DO UPDATE SET
    total_pts      = EXCLUDED.total_pts,
    matches_played = EXCLUDED.matches_played,
    breakdown      = EXCLUDED.breakdown
```

La cláusula `ON CONFLICT` usa la constraint única de `sfa_season_scores` cuyo nombre es
`uq_sfa_season_scores` (a verificar en los modelos). Si no existe nombre, usar
`(player_id, competition_id, season, rules_version_id)`.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| `text()` con SQL raw para el bulk INSERT | SQLAlchemy Core `insert().from_select()` | `jsonb_object_agg` dentro de un FROM correlacionado es muy verbose con el Core API; el SQL raw es más legible y mantenible |
| `WITH` CTEs para separar action_data y player_totals | Subqueries inline | Las CTEs son más legibles y el query planner de PG las materializa eficientemente |
| `achievement_bonus_pts = 0` en el INSERT (no DO UPDATE) | `COALESCE(EXCLUDED.ach..., 0)` | El `DO UPDATE` no toca el campo, preservando el valor existente. El `0` en el INSERT solo aplica a filas nuevas. |
| Nuevo método `bulk_rebuild_season_scores(rules_version_id, season, competition_id?)` en `PlayerEventScoreRepository` | Método en `ScoringRepository` | El método lee de `player_event_scores` y escribe en `sfa_season_scores`. Que el método esté en `PlayerEventScoreRepository` es discutible, pero es donde ya vive la query de `get_season_score_breakdown`. Alternativa aceptable: `ScoringRepository`. **Decisión final: `PlayerEventScoreRepository`** porque el input son los `player_event_scores`. |
| El use case llama a `bulk_rebuild_season_scores()` en vez del loop | Mantener el loop y añadir batching | El bulk SQL es O(1) roundtrips vs O(n) roundtrips; batching mejoraría el loop pero seguiría siendo N/batch_size roundtrips |
| El loop `for pid, cid in affected_player_competition_pairs` se ELIMINA del use case | Mantenerlo como fallback | El bulk rebuild cubre exactamente el mismo scope (season + rules_version_id + optional competition_id). No hay caso de uso donde necesitemos el loop individual después del bulk. |
| El método en el Protocol retorna `int` (número de filas insertadas/actualizadas) | `None` | Útil para logging y para los tests de verificación. PostgreSQL no expone este dato directamente con `INSERT ... ON CONFLICT`, pero `rowcount` del cursor lo aproxima. |

## Impacto en el flujo de recálculo

**Antes:** ~21,000 queries secuenciales, parte del bottleneck de 35-40 min.

**Después:** 1 query SQL (o 2 si se filtra por competition_id de forma diferente). El tiempo
estimado para el bulk rebuild es de 2-10 segundos dependiendo del hardware de DB.

El bottleneck restante (el loop sobre 92,700 eventos para calcular `PlayerEventScore` uno
a uno) no se aborda en este spec. Es un problema diferente que requeriría batch processing.

## Archivos modificados

```
backend/src/sfa/
├── domain/scoring_ports.py
│   └── PlayerEventScoreRepositoryPort: +bulk_rebuild_season_scores()
├── infrastructure/repositories/player_event_score_repository.py
│   └── PlayerEventScoreRepository: +bulk_rebuild_season_scores()
└── application/use_cases/calculate_scores_for_rules_version.py
    └── execute(): eliminar loop, llamar bulk_rebuild_season_scores()
```
