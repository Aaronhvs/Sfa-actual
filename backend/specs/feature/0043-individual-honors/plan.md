# Plan: Palmares individual

## Archivos a crear

- [x] `backend/migrations/0046_create_individual_honors.sql` - tabla, constraints e indices.
- [x] `backend/src/sfa/domain/individual_honors.py` - entidad, value objects, DTOs y port. [DDD]
- [x] `backend/src/sfa/infrastructure/models/individual_honors/models.py` - modelo SQLAlchemy.
- [x] `backend/src/sfa/infrastructure/repositories/individual_honor_repository.py` - adapter PostgreSQL.
- [x] `backend/src/sfa/application/use_cases/infer_individual_honors.py` - motor de seleccion y puntos.
- [x] `backend/src/sfa/application/use_cases/get_player_individual_honors.py` - lectura contextual.
- [x] `backend/src/sfa/tasks/infer_individual_honors_task.py` - ejecucion administrativa Celery.
- [x] `backend/tests/domain/test_individual_honors.py` - invariantes del dominio.
- [x] `backend/tests/use_cases/test_infer_individual_honors.py` - ganadores, umbrales, cap e idempotencia.
- [x] `backend/tests/use_cases/test_get_player_individual_honors.py` - resolucion de scope y version.
- [x] `backend/http/individual_honors.http` - recalculo y lectura.
- [x] `frontend/src/components/player/IndividualHonors.tsx` - bloque visual debajo de Palmares.

## Archivos a modificar

- [x] `backend/src/sfa/domain/scoring/value_objects.py` - puntos, umbrales y limite versionados.
- [x] `backend/src/sfa/infrastructure/models/__init__.py` - registrar modelo nuevo.
- [x] `backend/src/sfa/infrastructure/repositories/__init__.py` - exportar repository.
- [x] `backend/src/sfa/infrastructure/repositories/sfa_score_repository.py` - sumar honores al total contextual.
- [x] `backend/src/sfa/infrastructure/repositories/ranking_explanation_repository.py` - evidencia de puntos de honor.
- [x] `backend/src/sfa/tasks/recalculate_award_period_task.py` - inferir honores antes de explicaciones.
- [x] `backend/src/sfa/tasks/__init__.py` - registrar la task para autodiscovery de Celery.
- [x] `backend/src/sfa/core/dependencies.py` - wiring de repository y use cases.
- [x] `backend/src/sfa/api/v1/players.py` - endpoint de lectura.
- [x] `backend/src/sfa/api/v1/admin.py` - endpoint protegido de inferencia.
- [x] `backend/src/sfa/api/v1/schemas/players.py` - schema de honor individual.
- [x] `frontend/src/types/index.ts` - contrato TypeScript.
- [x] `frontend/src/api/client.ts` - cliente cacheado de honores.
- [x] `frontend/src/pages/PlayerPage.tsx` - carga por scope y ubicacion debajo de Palmares.
- [x] `frontend/src/index.css` - layout responsive, jerarquia y estados.

No fue necesario modificar `scores/models.py`, `get_player_detail.py` ni `celery_app.py`: el
read-side contextual ya vive en `SFAScoreRepository` y el registro se completa en `tasks/__init__.py`.

## Checklist de implementacion

- [x] Ejecutar la suite backend antes de editar y registrar el baseline.
- [x] [DDD] Implementar `IndividualHonor`, tipos, candidatos e invariantes sin dependencias de infra.
- [x] Extender `ScoringConfig` con defaults retrocompatibles, `from_dict` y `to_dict`.
- [x] Crear migracion idempotente con FK, check constraints e indice unico por contexto.
- [x] Implementar el port completo y un repository que retorne DTOs, nunca ORM models.
- [x] Agregar agregacion de candidatos por pares `(season, competition_id)` sin duplicar fixtures.
- [x] Clasificar solo Mundial, Champions y ligas nacionales elegibles.
- [x] Implementar los cuatro desempates y omitir premios sin produccion estadistica.
- [x] Aplicar umbrales de minutos/intentos para regates y duelos segun categoria.
- [x] Aplicar el limite de 8000 por jugador y scope de forma determinista.
- [x] Reemplazar resultados de scope/version dentro de una sola transaccion.
- [x] Integrar `awarded_bonus_pts` en ranking general, ranking filtrado y detalle del jugador.
- [x] Mantener sin honores los endpoints legacy que no resuelven un scope canonico.
- [x] Incluir puntos de honores en evidencia de explicaciones contextuales.
- [x] Crear task con late imports y endpoint admin protegido.
- [x] Inferir honores antes de encolar explicaciones al recalcular un award period.
- [x] Crear endpoint read-side de jugador con `scope` y `season` mutuamente excluyentes.
- [x] Agregar factory exclusivamente en `core/dependencies.py`.
- [x] Documentar casos happy path, scope inexistente y autorizacion admin en `.http`.
- [x] Cargar el contexto de las skills de frontend antes de editar la UI.
- [x] Construir `Palmares individual` inmediatamente debajo de `CompetitionJourney`.
- [x] Mostrar titulo, contexto, evidencia estadistica y puntos sin truncamiento.
- [x] Resolver loading, vacio, cambio de temporada e historial sin contenido stale.
- [x] Validar accesibilidad, contraste y responsive en movil y escritorio.
- [x] Ejecutar pruebas enfocadas y suite completa backend.
- [x] Verificar `flake8` e `isort --check-only` en archivos modificados.
- [x] Verificar `npm run build` sin errores TypeScript.
- [x] Verificar visualmente con Playwright en desktop y movil.

## Agent Routing Brief

**DDD Designer needed:** yes

La feature introduce `IndividualHonor`, cuatro tipos de reconocimiento, invariantes de muestra,
desempates y puntos derivados que no son `ActionType`. El DDD Designer define el nuevo bounded
context y protege la separacion entre acciones de partido, logros colectivos y honores individuales.

## Verificacion

1. Recalcular `season-2025` crea honores globales, Mundial, Champions y ligas incluidas.
2. El maximo goleador/asistidor coincide con la suma de `player_stats` del contexto.
3. El mejor regateador cumple intentos y minutos minimos y muestra porcentaje mas fraccion.
4. El rey de los duelos muestra total ganado y porcentaje de exito.
5. Repetir la task no duplica filas ni puntos.
6. El ranking general suma honores globales y de competicion hasta el limite de 8000.
7. El filtro Champions suma solo honores Champions.
8. La ficha muestra `Palmares individual` debajo de `Palmares` para el scope elegido.
9. Los puntos y la evidencia se mantienen al recargar y cambian al seleccionar otro scope.
