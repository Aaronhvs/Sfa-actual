# 0039 - Auto Ranking Explanation Refresh

## Contexto de negocio

Las explicaciones con IA del Top 3/Top 10 ya existen y estan cacheadas, pero hoy dependen de
ejecutar manualmente `generate_ranking_explanations_task` o de que el recalculo completo la
encole. Para el producto, la expectativa correcta es que el banner narrativo se mantenga fresco
automaticamente cuando cambia el ranking:

- Si entra un jugador nuevo al Top 3, debe generarse su explicacion.
- Si un jugador que ya estaba en Top 3 suma nuevo contexto relevante, debe regenerarse solo el.
- Si Messi y Mbappe siguen iguales, no deben gastar tokens de IA otra vez.
- Si cambia el orden pero la evidencia de un jugador no cambia salvo rank, hay que decidir si el
  rank forma parte de la evidencia narrativa para evitar textos inconsistentes.

El objetivo es convertir la generacion de explicaciones en una extension eventual del pipeline de
scoring: barata, automatica, auditable y sin riesgo para el calculo de puntos.

## Restricciones

- No se debe llamar IA desde requests publicos del frontend.
- No se debe regenerar todo el Top 3/Top 10 en cada recalculo si el `source_hash` no cambio.
- La generacion narrativa no puede bloquear, revertir ni romper el recalculo de puntos.
- La task debe respetar `AI_EXPLANATIONS_TOP_N`, `AI_EXPLANATIONS_ENABLED`,
  `AI_EXPLANATIONS_DAILY_BUDGET_USD` y fallback deterministico.
- El flujo debe convivir con `ingest_today_task`, `ingest_competition_task` y
  `run_full_recalculation_task`.
- El comportamiento debe evitar gasto cuando solo se visita la pagina o se lee el ranking.
- La consistencia aceptada es eventual: el ranking puede actualizarse segundos antes que el texto.

## Codebase analizado

- `backend/.claude/agents/Architecture-Engineer.md`: reglas del agente de arquitectura.
- `backend/.claude/skills/sfa-spec/SKILL.md`: formato y numeracion del spec.
- `backend/specs/feature/0037-ai-ranking-explanations/decisions.md`: decision original de cache,
  evidence package, `source_hash`, fallback y generacion post-recalculo.
- `backend/specs/feature/0037-ai-ranking-explanations/plan.md`: checklist original de task,
  endpoints, frontend y rollout.
- `backend/src/sfa/domain/ranking_explanation_ports.py`: DTOs y ports existentes.
- `backend/src/sfa/application/use_cases/generate_ranking_explanations.py`: logica actual de
  `source_hash`, stale y skip cuando `force=False`.
- `backend/src/sfa/tasks/generate_ranking_explanations_task.py`: task actual de generacion.
- `backend/src/sfa/tasks/run_full_recalculation_task.py`: hoy encola explicaciones si el recalculo
  termina completed.
- `backend/src/sfa/tasks/ingestion_tasks.py`: al terminar ingesta dispara recalculo completo.
- `backend/src/sfa/celery_app.py`: beat schedule actual para ingesta y enriquecimiento.
- `backend/src/sfa/core/config.py`: settings `AI_EXPLANATIONS_*`.

## Decisiones tomadas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Mantener `generate_ranking_explanations_task` como el unico escritor de textos | Generar explicaciones dentro de `run_full_recalculation_task` en la misma transaccion | Aisla fallos/costos de IA del pipeline critico de scoring. |
| Usar `force=False` para el flujo automatico | Usar siempre `force=True` post-recalculo | Permite que el `source_hash` salte jugadores sin cambios y evita gasto innecesario. |
| Hacer que el Top N automatico se configure por `AI_EXPLANATIONS_TOP_N` | Hardcodear Top 3 | Permite probar Top 3 barato y luego ampliar a Top 10 sin cambiar codigo. |
| Incluir `rank` y evidencia de contexto en el `source_hash` | Hashear solo eventos/puntos del jugador | Si el jugador cambia de puesto, el texto puede necesitar cambiar para no decir "va primero" cuando ya no va primero. |
| No crear entidad nueva | Crear una entidad `ExplanationRefreshRun` | La entidad `RankingPlayerExplanation` y el hash existente ya cubren frescura por jugador/scope. Solo hace falta orquestacion. |
| Registrar logs claros de generated/skipped/fallback | Confiar solo en filas DB | Operaciones necesita saber si una corrida gasto IA o solo salto hashes. |
| Mantener consistencia eventual | Hacer request sincrono desde frontend cuando falta texto | Evita latencia y costo por visita. |
| No agregar nuevo endpoint en esta fase | Endpoint admin nuevo para auto-sync | Ya existe task manual y endpoint de generacion; el cambio central es automatizar y endurecer el skip. |

## Flujo esperado

1. `ingest_today_task` detecta partidos activos o recientemente finalizados.
2. `ingest_competition_task` actualiza fixtures, eventos y stats.
3. `run_full_recalculation_task` recalcula scores, achievements y bonus.
4. Si el recalculo termina `completed`, encola `generate_ranking_explanations_task` con:
   - `season` del recalculo.
   - `rules_version_id` activo.
   - `competition_id=350` y `scope=world_cup` para Mundial 2026.
   - `limit=AI_EXPLANATIONS_TOP_N`.
   - `force=False`.
   - `use_total=True`.
5. `GenerateRankingExplanationsUseCase` arma evidencia del Top N actual.
6. Por cada jugador:
   - Si no existe fila cacheada para ese scope, genera.
   - Si existe pero el `source_hash` cambio, genera.
   - Si existe y el `source_hash` es igual, salta.
7. La task loguea `generated`, `fallback`, `skipped`, `failed` y costo estimado.

## Casos de producto cubiertos

### Entra Vinicius al Top 3

Vinicius aparece dentro del Top N automatico y no tiene fila para ese scope/rank actual. La task
debe generar solo Vinicius. Messi y Mbappe se saltan si sus hashes siguen iguales.

### Mbappe sigue en Top 3 pero suma nuevo contexto

Mbappe mantiene fila cacheada, pero cambia su evidence package por goles/asistencias/eventos/puntos.
Su `source_hash` cambia. La task regenera Mbappe y salta los jugadores sin cambios.

### Top 3 se mantiene igual

La task se ejecuta despues del recalc, pero si los tres hashes son iguales, `generated=0` y
`skipped=3` para Top 3. No debe llamar al provider externo.

### Cambia solo el orden

Si el `rank` forma parte del evidence package, el `source_hash` cambia y se regenera el texto para
evitar frases incoherentes sobre puesto. Esta decision puede generar una llamada extra, pero protege
la calidad del banner cuando cambia la narrativa de "por que es #1" a "por que sigue en el podio".

## Domain Model

No aplica entidad nueva.

La feature usa la entidad existente `RankingPlayerExplanation` del spec 0037 y sus invariantes:

- `source_hash` representa frescura del paquete de evidencia.
- `scope` delimita donde se puede reutilizar una explicacion.
- `status=generated|fallback` es visible; `failed|stale` es interno.

La decision de dominio clave es conservar `source_hash` como frontera de confianza y como llave
logica de regeneracion incremental.

## Integraciones externas

No se agrega integracion externa nueva.

Se reutiliza el provider IA ya configurado por `AI_EXPLANATIONS_PROVIDER`,
`AI_EXPLANATIONS_BASE_URL`, `AI_EXPLANATIONS_MODEL` y `AI_EXPLANATIONS_API_KEY`.

Fallback:

- Si el provider falla, se guarda explicacion deterministica.
- Si el presupuesto diario se excede, se debe usar fallback sin romper el pipeline.
- Si la IA esta deshabilitada, el flujo automatico puede seguir usando fallback o quedar inactivo
  segun la decision operativa de settings.
