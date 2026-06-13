# Unificar pipeline scoring v2: eliminar v1 legacy, auto-trigger post-ingestion con versión activa

## Contexto de negocio

SFA acumula dos pipelines de scoring en paralelo que producen resultados inconsistentes.
El pipeline viejo (v1-style) opera sin conocimiento de `rules_versions` y escribe scores directamente
desde los pts calculados durante la ingestion. El pipeline nuevo (v2) carga la config desde
`scoring_rules_versions`, rescore desde eventos crudos, y soporta posiciones granulares
(MCO, DEL, EXT, LAT, DC). Mientras ambos coexistan, el frontend puede mostrar scores de v1
y el recálculo manual es necesario tras cada ingestion. Este refactor elimina el pipeline viejo,
hace que la ingestion dispare automáticamente v2, y limpia el código de compatibilidad temporal.

## Restricciones

- La tabla `player_events` debe conservarse — es el almacén de eventos crudos que el pipeline v2 lee para (re)calcular.
- La tabla `player_stats` debe conservarse — almacena stats crudas que `PlayerEventRawContextDTO` consume.
- No hay cambios al esquema de la DB salvo la migración que activa `is_active=TRUE` en `id=3`.
- El endpoint `POST /scoring/recalculate-full` ya existe y funciona — no se crea endpoint nuevo.
- `ScoringRulesVersionRepository.get_active_version()` ya está implementado y disponible.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Eliminar scoring inline en `IngestCompetitionUseCase` | Mantener scoring inline y sincronizarlo con v2 | La responsabilidad de ingestion es persistir datos crudos, no calcular scores. Tener dos cálculos en paralelo es fuente de bugs. |
| Post-ingestion trigger consulta versión activa en DB | Hardcodear `rules_version_id=3` | Si en el futuro se activa v4, el código no necesita cambiar. Desacopla el trigger del ID concreto. |
| Eliminar `_resolve_group()` sin reemplazar por otro fallback | Mantener el fallback silencioso | El fallback silencioso enmascara configs incorrectas. Con v2 activa y MCO en `base_points`, una posición sin entry es un error de configuración que debe ser visible (warning + skip). |
| Deprecar (no eliminar) `calculate_all_scores_task` en esta pasada | Eliminar directamente | Puede haber referencias en Celery beat schedule o llamadas internas que no se hayan auditado. La eliminación definitiva va en Fase 8 tras verificar. |
| Migración Alembic para activar v2 | Script SQL manual one-time | La migración es reproducible al reiniciar Docker o desplegar en un entorno nuevo. El PATCH HTTP es transitorio. |

## Protección de posiciones Transfermarkt — CONFIRMADA CORRECTA

`IngestionRepository.upsert_player()` implementa la protección mediante SQL `CASE`:

```sql
CASE WHEN position_source = 'transfermarkt' THEN position ELSE excluded.position END
```

Esto preserva la posición enriquecida (MCO, DEL, EXT, LAT) frente a cualquier re-ingestion
de API-Football. El flag `update_position=False` en el use case de ingestion solo se activa
cuando el jugador no está en `KNOWN_POSITIONS` Y la posición de API-Football es `MC` genérica,
que es el caso correcto. **No se requieren cambios en este mecanismo.**

## Inventario de código muerto a eliminar

| Artefacto | Ubicación | Motivo |
|---|---|---|
| `_V2_TO_V1_GROUP` dict | `ingest_competition.py:84` | Solo alimenta `_v1_group()` |
| `_v1_group()` función | `ingest_competition.py:87-99` | Mapeo v2→v1 que no aplica a v2 |
| `SFAScoringService` en constructor | `IngestCompetitionUseCase.__init__` | Scoring inline eliminado |
| Imports de scoring en ingest | `ingest_competition.py:13-24` | `BASE_POINTS_TABLE`, `CombinedMultiplier`, `M1-M4`, `MvisitFactor`, `SFAScore` |
| `_resolve_group()` función | `calculate_scores_for_rules_version.py:57-61` | Fallback v1-compat ya innecesario con v2 |
| Cálculo inline de pts en ingestion | `ingest_competition.py:363-387` | Score calculado durante ingestion, no en recálculo v2 |

## Lo que NO cambia

- `IngestionRepository.upsert_player()` — protección de posición Transfermarkt correcta.
- Tabla `player_events` — sigue recibiendo eventos crudos; `pts` se escribe como `0.0`.
- Tabla `player_stats` — sigue recibiendo stats crudas sin cambios.
- `CalculateScoresForRulesVersionUseCase` — solo se elimina `_resolve_group`; toda la lógica de scoring v2 se mantiene.
- `RunFullRecalculationUseCase` — correcto, no se toca.
- `ScoringRulesVersionRepository.get_active_version()` — ya implementado.
- El endpoint `POST /scoring/recalculate-full` — ya existe y funciona.
- `position_to_group()` — se mantiene en `ingest_competition.py` para computar el grupo del evento crudo.

## Integraciones externas

Ninguna nueva. Este refactor es puramente interno.
