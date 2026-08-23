# Plan: Resilient Live Ingestion And Final Fixture Scoring

## Archivos a crear

- [ ] `src/sfa/tasks/reconcile_recent_ingestion_task.py` - catch-up diario y manual de una ventana movil, con recalculacion consolidada.
- [ ] `tests/test_reconcile_recent_ingestion_task.py` - cobertura de recuperacion, cuota, lock e idempotencia de orquestacion.

## Archivos a modificar

- [ ] `src/sfa/core/config.py` - cambiar `INGEST_INTERVAL_MINUTES` a 10 y declarar la configuracion minima del catch-up.
- [ ] `src/sfa/celery_app.py` - mantener `ingest_today` cada 10 minutos y registrar el catch-up diario posterior al reset UTC.
- [ ] `src/sfa/domain/ingestion_ports.py` - declarar la excepcion tipada de cuota diaria de proveedor.
- [ ] `src/sfa/infrastructure/providers/api_football.py` - clasificar limite diario como no reintentable y preservar retries transitorios.
- [ ] `src/sfa/tasks/ingest_today_task.py` - lock no bloqueante, cierre por cuota y una sola recalculacion por lote.
- [ ] `src/sfa/tasks/ingestion_tasks.py` - permitir diferir recalculacion y reutilizar un unico helper de cierre de lote.
- [ ] `src/sfa/tasks/__init__.py` - registrar/exportar la task de catch-up conforme al patron actual.
- [ ] `src/sfa/infrastructure/repositories/player_event_score_repository.py` - limitar eventos recalculables a fixtures `FT/AET/PEN`.
- [ ] `tests/providers/test_api_football_rate_limits.py` - diferenciar cuota diaria de errores transitorios.
- [ ] `tests/test_ingest_today_task.py` - frecuencia logica, lock, lote, cuota y recalculacion unica.
- [ ] `tests/use_cases/test_team_snapshot_repositories.py` - filtro final y validacion estricta de snapshots.
- [ ] `docker-compose-prod.yml` o environment productivo documentado - fijar `INGEST_INTERVAL_MINUTES=10` sin incluir secretos.

## Checklist de implementacion

### A. Baseline y contrato de fallos

- [ ] Ejecutar `pytest tests/` antes de modificar codigo y registrar cualquier fallo preexistente.
- [ ] Definir una excepcion explicita para cuota diaria agotada sin referencias a `httpx`, Redis o Celery.
- [ ] Hacer que API-Football detecte la cuota diaria antes de la rama generica de rate limit.
- [ ] Verificar que una respuesta HTTP 200 con error de cuota diaria hace una sola solicitud y eleva la excepcion tipada.
- [ ] Verificar que timeout, 429 de ventana corta y error HTTP transitorio conservan el retry acotado actual.

### B. Frecuencia y proteccion del ciclo

- [ ] Cambiar el default de `INGEST_INTERVAL_MINUTES` de 2 a 10.
- [ ] Configurar produccion explicitamente con `INGEST_INTERVAL_MINUTES=10`.
- [ ] Incorporar un lock no bloqueante estable por season/tipo de ciclo.
- [ ] Retornar un resultado observable `already_running` cuando otro ciclo conserva el lock, sin retry.
- [ ] Liberar el lock en exito, cuota agotada y excepcion transitoria.

### C. Una recalculacion por lote

- [ ] Agregar a `_run_ingest_competition` una opcion interna `enqueue_recalculation` con default `True`.
- [ ] Mantener sin cambios el efecto de los callers manuales que omitan la nueva opcion.
- [ ] Hacer que `ingest_today` invoque cada competencia con recalculacion diferida.
- [ ] Acumular solo pools correspondientes a ingestas completadas.
- [ ] Extraer/reutilizar un helper que resuelva version activa y encole un unico `apply_elo_pools_then_recalculate_task` para el lote.
- [ ] Encolar cero recalculos cuando ninguna competencia fue ingerida.
- [ ] Encolar exactamente un recalculo cuando una o varias competencias fueron ingeridas.
- [ ] Si la cuota diaria se agota a mitad del lote, detener llamadas nuevas, encolar una sola recalculacion por el progreso confirmado y terminar sin `self.retry`.
- [ ] Mantener retry Celery solo para excepciones transitorias no clasificadas como cuota diaria.

### D. Scoring de fixtures finales

- [ ] Centralizar o reutilizar la constante de estados finales `FT/AET/PEN` para evitar divergencia entre ELO y scoring.
- [ ] Aplicar el filtro de status en la consulta principal de `get_events_for_recalc`, antes de detectar snapshots faltantes.
- [ ] Confirmar que eventos `1H`, `HT`, `2H`, `ET`, `LIVE` y otros no finales no se puntuan ni bloquean el recalculo.
- [ ] Confirmar que un fixture `FT/AET/PEN` sin cualquiera de sus dos snapshots sigue fallando con `Missing temporal ELO snapshot`.
- [ ] Confirmar que un fixture pasa a ser puntuable en la primera ejecucion posterior a su transicion a estado final.
- [ ] Confirmar que el bulk rebuild conserva scores finales previos mientras excluye eventos vivos aun no puntuados.

### E. Catch-up idempotente

- [ ] Crear una task diaria de reconciliacion con ventana default de tres dias UTC.
- [ ] Programarla una vez al dia despues del reset UTC de API-Football y fuera del minuto de `ingest_today`.
- [ ] Reutilizar whitelist, seleccion dirigida e ingesta secuencial; no crear un segundo pipeline de ingestion.
- [ ] Diferir recalculacion por competencia y ejecutar el mismo cierre unico de lote.
- [ ] Aplicar la misma politica no-retry ante cuota diaria y la misma liberacion de lock.
- [ ] Permitir invocacion manual con fechas/lookback explicitos para recuperar el rango 20-23.
- [ ] Probar que ejecutar dos veces el mismo catch-up produce los mismos fixtures, eventos, snapshots, event scores y season totals.
- [ ] Registrar en el resultado fechas consultadas, competencias completadas, fixtures objetivo, estado de cuota y si se encolo recalculacion.

### F. Pruebas y calidad

- [ ] Cubrir `ingest_today` sin fixtures relevantes: cero ingestas y cero recalculos.
- [ ] Cubrir dos competencias exitosas: dos ingestas secuenciales y un solo recalculo.
- [ ] Cubrir limite diario en la primera competencia: cero retry Celery y cero recalculos.
- [ ] Cubrir limite diario despues de una competencia exitosa: cierre inmediato y un solo recalculo.
- [ ] Cubrir ciclo solapado: resultado `already_running` sin llamadas externas.
- [ ] Cubrir eventos vivos sin snapshot junto a eventos finales con snapshot: solo los finales se devuelven.
- [ ] Cubrir fixture final sin snapshot: error estricto y rollback del recalculo.
- [ ] Actualizar todos los Fakes afectados para implementar los Protocols completos; no usar `MagicMock`.
- [ ] Ejecutar tests focalizados de provider, tasks, ELO y scoring.
- [ ] Ejecutar `pytest tests/` y verificar coverage global >=80%.
- [ ] Ejecutar `flake8 src/ tests/` sin errores.
- [ ] Ejecutar `isort --check-only src/ tests/` sin errores.
- [ ] Ejecutar `git diff --check`.

## Runbook de produccion

1. Mantener `celery_beat` detenido y confirmar que no hay tasks antiguas de ingesta/recalculo activas o reservadas.
2. Desplegar API, worker y Beat con `INGEST_INTERVAL_MINUTES=10`, dejando Beat aun detenido.
3. Verificar health de API, ping del worker y presencia de las tasks nuevas en el registry.
4. Ejecutar dry-run/seleccion del catch-up para las fechas UTC 20-23 y registrar competencias y fixtures objetivo.
5. Ejecutar el catch-up manual una vez y comprobar que encola exactamente un `apply_elo_pools_then_recalculate_task`.
6. Esperar `DONE` del replay ELO y del full recalculation; no iniciar un segundo proceso en paralelo.
7. Auditar en DB que fixtures finales del 20-23 tienen dos snapshots temporales, eventos puntuados para la version activa y season totals reconstruidos.
8. Auditar que fixtures aun vivos no tienen nuevos `player_event_scores` y no aparecen en la lista de snapshots faltantes.
9. Repetir el catch-up sobre el mismo rango y comparar conteos/totales para demostrar idempotencia.
10. Iniciar `celery_beat` y confirmar durante al menos dos intervalos que envia una task cada 10 minutos, sin overlap ni retry por cuota diaria.
11. Confirmar en logs que un lote con varias competencias genera una sola linea de enqueue ELO/scoring.
12. Si aparece cuota diaria, verificar resultado `quota_exhausted`, ausencia de retry y ausencia de nuevas llamadas del mismo lote; Beat puede detenerse otra vez sin perder la recuperacion pendiente.

## Rollback operativo

- Detener `celery_beat` si se observa consumo anomalo, overlap o mas de una recalculacion por lote.
- Mantener API y worker activos para permitir auditoria y una recuperacion manual controlada.
- No revertir snapshots ni scores mediante SQL manual. Cualquier recuperacion usa el replay ELO y full recalculation idempotentes.
- Conservar IDs de tasks, rango del catch-up, rules version, conteos antes/despues y causa de cuota en el registro del incidente.

## Verificacion

1. Beat ejecuta como maximo seis ciclos por hora con intervalo configurado de 10 minutos.
2. Una senal de cuota diaria no genera sleeps de 65 segundos, retries HTTP ni retry Celery.
3. Un ciclo con N competencias completadas genera N ingestas y exactamente una recalculacion de pools.
4. Un evento de fixture `2H` no se puntua y no bloquea; tras cambiar el fixture a `FT`, recibe score con snapshots temporales validos.
5. Un fixture final sin snapshot sigue haciendo fallar el recalculo y conserva el estado previamente confirmado.
6. El catch-up del 20-23 completa los `player_event_scores` pendientes y una segunda ejecucion no cambia conteos ni totales.
7. Los rankings y detalles de partido reflejan los nuevos puntos solo despues del cierre final y del recalculo exitoso.

## Agent Routing Brief

**DDD Designer needed:** no

No se agregan entidades de negocio, aggregates, acciones, multiplicadores ni formulas. El trabajo
modifica politicas tecnicas de integracion, orquestacion Celery y el alcance de lectura de un
repositorio existente. La implementacion debe mantener el orden: excepcion/port, provider,
orquestacion de lote, filtro repository, catch-up, tests y runbook productivo.

El implementador no puede resolver snapshots faltantes con valores neutrales ni mover logica de
scoring a las tasks. Si se propone cambiar M1, ELO, K factors o la semantica futbolistica de un
partido final, debe detenerse y volver a Architecture Engineer con DDD Designer.
