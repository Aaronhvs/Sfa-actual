# Plan: 0039 - Auto Ranking Explanation Refresh

## Archivos a crear

- [x] `backend/tests/use_cases/test_generate_ranking_explanations_incremental.py` - cubre
  generacion incremental por `source_hash`, entrantes al Top N y skip de jugadores sin cambios.
- [x] `backend/tests/tasks/test_run_full_recalculation_explanation_refresh.py` - cubre que el
  recalculo encola la task de explicaciones con `force=False` y parametros correctos.

## Archivos a modificar

- [ ] `backend/src/sfa/application/use_cases/generate_ranking_explanations.py` - reforzar
  comportamiento incremental y logs/summary si falta distinguir `new`, `changed`, `skipped`.
- [ ] `backend/src/sfa/infrastructure/repositories/ranking_explanation_repository.py` - confirmar
  que `source_hash` incluye rank, puntos, evidence de eventos, B1, achievement bonus y contexto
  necesario para decidir frescura.
- [x] `backend/src/sfa/tasks/run_full_recalculation_task.py` - asegurar que el flujo automatico
  encola explicaciones con `force=False`, Top N desde settings y scope correcto.
- [ ] `backend/src/sfa/tasks/generate_ranking_explanations_task.py` - mejorar logs para auditoria
  de automatic refresh si hace falta.
- [ ] `backend/src/sfa/core/config.py` - agregar settings solo si se necesita separar Top N del
  banner y Top N del perfil.
- [ ] `backend/specs/feature/0037-ai-ranking-explanations/decisions.md` - opcional, agregar nota
  cruzada hacia este spec si se quiere documentar la evolucion.

## Checklist de implementacion

- [x] Confirmar en codigo que `run_full_recalculation_task` ya encola
  `generate_ranking_explanations_task` solo cuando `result.status == "completed"`.
  - Criterio: una prueba o lectura valida que estados no completed no encolan IA.
- [x] Confirmar que el enqueue automatico usa `force=False`.
  - Criterio: jugadores con `source_hash` igual quedan en `skipped` y no llaman al writer.
- [x] Confirmar que el enqueue automatico usa `settings.AI_EXPLANATIONS_TOP_N`.
  - Criterio: cambiar el setting a 3 genera solo Top 3; cambiarlo a 10 evalua Top 10.
- [x] Confirmar scope Mundial 2026.
  - Criterio: para `season="2026"` se usa `competition_id=350` y `scope="world_cup"`.
- [x] Revisar la composicion actual de `source_hash`.
  - Criterio: el hash cambia si cambian rank, total SFA, achievement bonus, B1, eventos clave,
    match summaries o breakdown relevante.
- [x] Si `source_hash` no incluye rank o contexto narrativo suficiente, ampliarlo.
  - Criterio: cambio de rank dentro del Top N produce hash distinto.
- [x] Mantener el hash canonico deterministico.
  - Criterio: misma evidencia ordenada produce el mismo hash entre corridas.
- [x] Agregar tests del caso "entra Vinicius".
  - Criterio: repository fake devuelve Top 3 con un jugador nuevo; use case llama writer solo para
    ese jugador y reporta `generated=1`, `skipped=2`.
- [x] Agregar tests del caso "Mbappe cambia contexto".
  - Criterio: hash viejo distinto al nuevo; writer se llama solo para Mbappe.
- [x] Agregar tests del caso "Top 3 igual".
  - Criterio: todos los hashes coinciden; writer no se llama y summary muestra `skipped=3`.
- [x] Agregar tests del caso "cambia solo orden".
  - Criterio: si rank esta incluido en hash, el jugador afectado se regenera; si se decide no
    incluir rank, dejar decision explicita en `decisions.md`.
- [ ] Revisar `mark_stale_for_scope`.
  - Criterio: jugadores que salen del Top N quedan stale o dejan de servirse para ese scope.
- [x] Asegurar que una excepcion del writer no corta la corrida completa.
  - Criterio: un fallo guarda fallback/error y continua con los demas jugadores.
- [x] Mejorar logs de task si hace falta.
  - Criterio: logs de Celery muestran `generated`, `fallback`, `skipped`, `failed`, `cost` y
    permiten detectar si hubo gasto real.
- [ ] Verificar que los endpoints publicos solo leen cache.
  - Criterio: `GET /ranking/explanations` y perfil no disparan provider IA.
- [ ] Documentar comando operativo de smoke test.
  - Criterio: plan o HTTP file incluye comando para ejecutar recalc y luego revisar logs/filas.

## Agent Routing Brief

**DDD Designer needed:** no

No se crean nuevas entidades, value objects ni reglas de scoring. La feature es una mejora de
orquestacion sobre la entidad y ports existentes de `ranking_explanations`. El trabajo se concentra
en Celery, use case incremental, composicion de `source_hash`, tests y observabilidad.

## Verificacion

1. Ejecutar tests unitarios del use case incremental.
   - Criterio: entrante nuevo genera, hash cambiado genera, hash igual salta.
2. Ejecutar test de task/recalculo con mock de Celery.
   - Criterio: `run_full_recalculation_task` encola explicaciones con `force=False`.
3. Ejecutar verificacion manual en VPS despues de un recalc del Mundial:
   - Criterio: logs muestran que solo se generaron jugadores nuevos o cambiados.
4. Consultar cache:
   - Criterio: las filas de `ranking_player_explanations` para Top N tienen `prompt_version`
     actual y `generated_at` solo cambia para jugadores regenerados.
5. Verificar frontend:
   - Criterio: el banner muestra el texto actualizado cuando entra un nuevo Top 3 y no desaparece
     mientras la task termina.
