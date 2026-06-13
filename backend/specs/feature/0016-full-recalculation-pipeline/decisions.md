# Full Recalculation Pipeline — Pipeline completo de recálculo en un solo disparo

## Contexto del problema

El flujo de recalculación actual requiere dos pasos manuales y 45-50 minutos:

1. `POST /api/v1/scoring/recalculate` → Celery task que recalcula los 92,700 eventos y hace
   un rebuild de season_scores con ~21,000 queries individuales (~35-40 min).
2. Script manual `scripts/calc_achievement_bonuses.py` → itera 14 competiciones,
   llama a `CalculateAchievementBonusesUseCase` por cada una (~10 min adicionales).

Problemas concretos:
- El usuario debe recordar ejecutar el paso 2 manualmente después del paso 1.
- No hay ningún endpoint que orqueste el ciclo completo.
- No hay visibilidad de progreso durante los 45 min de ejecución.
- Si el paso 1 falla a mitad, no hay mecanismo de recovery parcial.
- `CalculateAchievementBonusesUseCase` solo acepta `competition_id` individual; no existe
  un use case que lo ejecute para todas las competiciones de una temporada.

## Restricciones técnicas

1. **Separación de capas estricta:** el Use Case no puede importar SQLAlchemy ni ORM models.
   El bulk SQL del rebuild va en el Repository; el Use Case solo orquesta llamadas de alto nivel.
2. **Un solo `AsyncSession` por Celery task:** el patrón existente usa `async with
   AsyncSessionLocal()` en el async runner de cada task. La sesión se hace commit al final.
   No se puede pasar la sesión entre tasks distintos.
3. **`CalculateAchievementBonusesUseCase` existente no se modifica:** funciona correctamente
   para una competición. Se crea un use case orquestador que lo invoca N veces.
4. **No se usa Celery chain ni Celery canvas** para encadenar los pasos. La razón: las chains
   de Celery dificultan el tracking de progreso unificado y requieren serialización del estado
   entre tasks. Un solo task con awaits secuenciales es más simple y más fácil de reintentar.
5. **El progreso se expone via Redis key**, no via WebSocket ni polling de Celery result. Es
   el patrón más simple dado que ya existe un cliente Redis en la infra.
6. **`achievement_bonus_pts` no se sobreescribe en el bulk rebuild** de season_scores: el
   bulk SQL usa `DO UPDATE SET total_pts=EXCLUDED.total_pts, matches_played=EXCLUDED.matches_played,
   breakdown=EXCLUDED.breakdown` y NO toca `achievement_bonus_pts`. Ese campo se actualiza
   únicamente por `update_season_score_bonus()` en `CompetitionAchievementRepository`.
7. **El endpoint retorna 202 inmediatamente** con `task_id`. El progreso se consulta en
   `GET /api/v1/scoring/recalculate-full/{task_id}/status`.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Nuevo `RunFullRecalculationUseCase` que encadena los 3 pasos | Reusar `CalculateScoresForRulesVersionUseCase` | El UC existente hace el scoring + el rebuild lento por loops; el nuevo UC llamará al scoring UC (que mantendrá su lógica) + luego el bulk rebuild + luego el achievement loop. Tener un UC orquestador evita duplicar lógica. |
| Nuevo `RunAllAchievementBonusesUseCase` que itera competitions | Modificar `CalculateAchievementBonusesUseCase` | El UC existente funciona y tiene tests. Crear un orquestador nuevo que lo llame en loop respeta el Single Responsibility y no rompe nada. |
| Progreso via Redis key `sfa:recalc:{task_id}:progress` | Polling de Celery result backend | El result backend de Celery no da progreso granular. Redis ya existe en la infra. El key expira en 24h automáticamente. |
| Un solo Celery task `run_full_recalculation_task` sin chain | Celery chain de 3 tasks | Un task monolítico es más sencillo de reintentar; la chain requiere serialización de resultado entre tasks y complica el tracking de progreso unificado. |
| El task nuevo llama a `CalculateScoresForRulesVersionUseCase` via su runner async | Duplicar la lógica del scoring | Reutilización: el scoring UC ya tiene toda la lógica correcta; el nuevo task solo lo orquesta. |
| `competition_ids` para achievement bonuses: se obtienen de la DB consultando las competiciones que tienen eventos para esa season + rules_version | Hardcodear lista | Dinámico; funciona aunque cambien las competiciones en el futuro. |
| La session de DB para el task full-recalculation se hace commit después de cada paso (scoring, luego achievement bonuses) con sesiones independientes | Una sola sesión para todo | Con 92k eventos, mantener una sola transacción abierta 5 min es arriesgado. Alineado con el patrón existente en tasks. |
| Endpoint `POST /api/v1/scoring/recalculate-full` en el router existente `scoring_rules_router.py` | Router nuevo | El router ya tiene el prefijo `/scoring` y el tag correcto. Agregar un endpoint es coherente con el patrón de `recalculate`. |
| `GET /api/v1/scoring/recalculate-full/{task_id}/status` retorna JSON con phase/pct | Retorno de texto plano | Más consumible por el frontend. Puede evolucionar sin romper contrato. |

## Flujo nuevo

```
POST /api/v1/scoring/recalculate-full
  body: { rules_version_id, season, force_recalculate }
  → 202 { task_id, status: "queued", message }
       ↓
  Celery: run_full_recalculation_task(rules_version_id, season, force_recalculate)
       ↓
  [FASE 1 — Scoring de eventos]
  Redis SET sfa:recalc:{task_id}:progress → { phase: "scoring", pct: 0 }
  Sesión 1: CalculateScoresForRulesVersionUseCase.execute(
      rules_version_id, season, force_recalculate=force_recalculate
  )
  → (internamente: score events + rebuild season_scores via BULK SQL)
  await session.commit()
  Redis SET → { phase: "scoring", pct: 100, events_calculated: N }
       ↓
  [FASE 2 — Achievement bonuses para todas las competiciones]
  Redis SET → { phase: "achievements", pct: 0, competitions_total: C }
  Obtener competition_ids con eventos en season (nueva query en repo)
  For idx, comp_id in enumerate(competition_ids):
      Sesión nueva: CalculateAchievementBonusesUseCase.execute(season, comp_id, rv_id)
      await session.commit()
      Redis SET → { phase: "achievements", pct: (idx+1)/C*100 }
       ↓
  [COMPLETADO]
  Redis SET → { phase: "done", pct: 100, summary: {...} }
  Key expires en 24h

GET /api/v1/scoring/recalculate-full/{task_id}/status
  → Lee Redis key → retorna JSON de progreso
```

## Nuevos archivos

```
backend/src/sfa/
├── application/use_cases/
│   └── run_all_achievement_bonuses.py     # RunAllAchievementBonusesUseCase
├── tasks/
│   └── run_full_recalculation_task.py     # Celery task orquestador
└── api/v1/schemas/
    └── (inline en scoring_rules_schemas.py — schemas nuevos)
```

## Archivos modificados

```
backend/src/sfa/
├── api/v1/scoring_rules_router.py         # 2 endpoints nuevos
├── domain/scoring_ports.py               # método nuevo en PlayerEventScoreRepositoryPort
├── core/dependencies.py                  # factory para RunAllAchievementBonusesUseCase
└── infrastructure/repositories/
    └── player_event_score_repository.py   # get_distinct_competition_ids_for_season()
```
