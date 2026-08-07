# Plan: Temporada de premio compuesta con Mundial 2026

## Estado de ejecucion (2026-08-06)

Implementado el read model de scopes, ranking y detalle compuesto, selector frontend,
replay ELO determinista por pool, coordinacion ELO -> scoring, proteccion admin y task de
recalculo del periodo. La migracion `0045_normalize_club_elo_progression.sql` habilita el
source auditable `club_elo_v2`.

Verificacion local completada: 63 pruebas enfocadas, flake8 e isort de archivos tocados,
compileall, import de API, TypeScript y build Vite pasan. La suite completa queda en 436
pruebas aprobadas y 3 fallos preexistentes no relacionados: dos de `ShootoutDecider` y uno
del fallback de explicaciones. El replay real, reconciliacion de puntos y activacion de la
version siguen siendo gates de despliegue porque requieren PostgreSQL y Celery del VPS.

## Archivos a crear

- [ ] `backend/src/sfa/domain/season_scope.py` - value objects y errores del scope compuesto.
- [ ] `backend/src/sfa/application/use_cases/recalculate_award_period.py` - orquestacion versionada de todos los componentes del periodo.
- [ ] `backend/src/sfa/tasks/recalculate_award_period_task.py` - wrapper Celery con advisory lock y late imports.
- [ ] `backend/migrations/0045_normalize_club_elo_progression.sql` - habilitar source progresivo de clubes.
- [ ] `backend/tests/domain/test_season_scope.py` - invariantes de `ScoreSource` y `AwardPeriodScope`.
- [ ] `backend/tests/use_cases/test_recalculate_award_period.py` - Fake completo y casos de recalculo/sombra/fallo parcial.
- [ ] `backend/tests/use_cases/test_award_period_reads.py` - ranking y perfil compuestos con una sola version.
- [ ] `backend/tests/repositories/test_award_period_scope_filters.py` - compilacion y no solapamiento de filtros SQL.
- [ ] `backend/tests/tasks/test_club_elo_progression.py` - idempotencia, alcance global y orden ELO -> scoring.
- [ ] `backend/http/award_periods.http` - ejemplos de scopes, ranking, perfiles, auditoria y recalculo admin.

## Archivos a modificar

- [ ] `backend/src/sfa/domain/ports.py` - metadata de opciones y contratos read-side basados en scope.
- [ ] `backend/src/sfa/domain/scoring_ports.py` - contratos necesarios para recalculo y cobertura por componente.
- [ ] `backend/src/sfa/infrastructure/repositories/season_repository.py` - catalogo, latest de clubes y resolucion de scopes.
- [ ] `backend/src/sfa/infrastructure/repositories/sfa_score_repository.py` - ranking, totales, breakdown y version comun del scope.
- [ ] `backend/src/sfa/infrastructure/repositories/player_event_repository.py` - eventos, fixtures y stats filtrados por varias fuentes.
- [ ] `backend/src/sfa/infrastructure/repositories/competition_achievement_repository.py` - logros y bonuses de todas las fuentes del scope.
- [ ] `backend/src/sfa/infrastructure/repositories/ranking_explanation_repository.py` - evidencia compuesta y persistencia bajo scope `award_period`.
- [ ] `backend/src/sfa/infrastructure/repositories/__init__.py` - exportar cualquier adaptador nuevo si la implementacion lo requiere.
- [ ] `backend/src/sfa/application/use_cases/get_seasons.py` - devolver opciones canonicas ordenadas.
- [ ] `backend/src/sfa/application/use_cases/get_ranking.py` - resolver latest/scope y exigir version comun.
- [ ] `backend/src/sfa/application/use_cases/get_player_detail.py` - total, rango, club representativo y scopes disponibles.
- [ ] `backend/src/sfa/application/use_cases/get_player_events.py` - detalle compuesto con rules version comun.
- [ ] `backend/src/sfa/application/use_cases/get_player_fixtures.py` - historial compuesto sin duplicados.
- [ ] `backend/src/sfa/application/use_cases/get_player_season_stats.py` - estadisticas de todas las fuentes.
- [ ] `backend/src/sfa/application/use_cases/get_player_achievements.py` - logros de club y Mundial.
- [ ] `backend/src/sfa/application/use_cases/get_ranking_explanations.py` - lectura por scope canonico.
- [ ] `backend/src/sfa/application/use_cases/get_player_ranking_explanation.py` - explicacion individual compuesta.
- [ ] `backend/src/sfa/application/use_cases/generate_ranking_explanations.py` - evidencia del award period.
- [ ] `backend/src/sfa/application/use_cases/run_full_recalculation.py` - permitir scope de competicion sin alterar el flujo fisico existente.
- [ ] `backend/src/sfa/api/v1/schemas/seasons.py` - `key`, `label`, `kind`, `includes_world_cup` y compatibilidad.
- [ ] `backend/src/sfa/api/v1/schemas/ranking.py` - identificar el scope resuelto en la respuesta.
- [ ] `backend/src/sfa/api/v1/schemas/players.py` - exponer scopes disponibles del jugador.
- [ ] `backend/src/sfa/api/v1/schemas/full_recalculation_schemas.py` - request/response de recalculo de periodo.
- [ ] `backend/src/sfa/api/v1/seasons.py` - serializar el catalogo sin logica de resolucion.
- [ ] `backend/src/sfa/api/v1/ranking.py` - aceptar `scope` y validar exclusion mutua con `season`.
- [ ] `backend/src/sfa/api/v1/players.py` - propagar `scope` en todos los endpoints de detalle.
- [ ] `backend/src/sfa/api/v1/ranking_explanations.py` - aceptar scope canonico.
- [ ] `backend/src/sfa/api/v1/scoring_rules_router.py` - endpoint admin para recalculo del award period.
- [ ] `backend/src/sfa/core/dependencies.py` - wiring unico de repositorios y use cases modificados.
- [ ] `backend/src/sfa/tasks/__init__.py` - exportar la nueva task.
- [ ] `backend/src/sfa/tasks/run_full_recalculation_task.py` - propagar filtro de competicion y evitar explicaciones parciales incorrectas.
- [ ] `backend/src/sfa/tasks/elo_tasks.py` - coordinador comun y replay de clubes desde seed.
- [ ] `backend/src/sfa/tasks/ingestion_tasks.py` - resolver el pool completo de clubes y eliminar la carrera ELO/scoring.
- [ ] `backend/src/sfa/infrastructure/repositories/team_strength_repository.py` - fixtures finalizados y baseline ELO coherente.
- [ ] `backend/src/sfa/api/v1/elo_router.py` - proteger todos los endpoints mutadores con admin key.
- [ ] `backend/src/sfa/tasks/generate_ranking_explanations_task.py` - propagar `scope_key`.
- [ ] `backend/http/ranking.http` - ejemplos canonicos y casos legacy.
- [ ] `backend/http/players.http` - ejemplos de perfil compuesto y Mundial aislado.
- [ ] `backend/tests/use_cases/test_get_seasons.py` - opciones, orden y latest basado en clubes.
- [ ] `backend/tests/use_cases/test_get_ranking.py` - default latest y error de version inconsistente.
- [ ] `backend/tests/use_cases/test_get_ranking_multi_season.py` - garantizar que `all` no suma rollups.
- [ ] `backend/tests/use_cases/test_get_player_detail_multi_season.py` - club + Mundial y scopes disponibles.
- [ ] `frontend/src/types/index.ts` - contrato de `SeasonItem` con key/kind/flags.
- [ ] `frontend/src/api/client.ts` - enviar `scope` en ranking y todos los recursos del jugador.
- [ ] `frontend/src/utils/season.ts` - labels y deteccion por kind, sin inferir Mundial desde el numero 2026.
- [ ] `frontend/src/components/shared/SeasonDropdown.tsx` - seleccionar por key unica.
- [ ] `frontend/src/components/shared/SeasonSelector.tsx` - seleccionar por key unica y mantener accesibilidad.
- [ ] `frontend/src/pages/RankingPage.tsx` - default latest 2025/2026 y banner hacia `world-cup-2026`.
- [ ] `frontend/src/pages/PlayerPage.tsx` - cargar total y detalle usando el mismo scope.
- [ ] `frontend/src/pages/ComparePage.tsx` - eliminar `SEASON='2024'` y usar el scope latest.
- [ ] `frontend/src/pages/MundialPage.tsx` - enlaces canonicos al ranking Mundial.
- [ ] `frontend/src/pages/MundialMatchPage.tsx` - enlaces de jugadores con scope Mundial.
- [ ] `frontend/src/pages/MundialTeamPage.tsx` - enlaces de jugadores con scope Mundial.
- [ ] `frontend/src/components/shared/WorldCupBanner.tsx` - navegar por scope, no por raw season.

## Checklist de implementacion

### 1. Baseline y proteccion del trabajo existente

- [ ] Registrar `git status --short` y no tocar cambios ajenos en `frontend/BRAND.md`, `frontend/CLAUDE.md`, `frontend/.ui-ux-skill` ni archivos eliminados por el usuario.
- [ ] Ejecutar el baseline backend disponible; si Docker sigue ausente, documentar el bloqueo exacto y ejecutar al menos `py_compile` sobre los modulos afectados.
- [ ] Ejecutar `npm run build` antes de cambios y registrar cualquier fallo preexistente.
- [ ] Consultar en el VPS las versiones de reglas, el ID usado por scores del Mundial y los conteos por source sin modificar datos.

### 2. Modelo de dominio [DDD]

- [ ] Implementar `ScopeKind`, `ScoreSource` y `AwardPeriodScope` como dataclasses frozen en `domain/season_scope.py`.
- [ ] Validar fuentes no vacias, competition IDs positivos/unicos y ausencia de pares solapados.
- [ ] Implementar `InconsistentScopeRulesVersionError` con scope, version solicitada y fuentes faltantes.
- [ ] Probar award period valido, torneo valido, all-time valido y cada invariante fallida.

### 2A. Normalizacion operacional del ELO

- [ ] Mantener pools separados `club` y `national_team` con una politica K explicita.
- [ ] Ejecutar clubes con `use_seed_baseline=True` y `require_seed_baseline=True`.
- [ ] Resolver todas las competition IDs de clubes con fixtures en la season antes del replay.
- [ ] Filtrar fixtures ELO a estados finalizados y excluir visiblemente resultados incompletos.
- [ ] Conservar una sola normalizacion fija 1400-2100 -> 0-100 para todos los sources ELO.
- [ ] Reemplazar las tasks paralelas de clubes por coordinador ELO -> full scoring.
- [ ] Aplicar el mismo coordinador al camino `ingest_all_competitions_task` una sola vez por pool.
- [ ] Impedir que `calculate_team_strengths_task` sobrescriba filas con source ELO.
- [ ] Proteger seed/recalculate de clubes con `require_admin_key`.
- [ ] Probar que dos replays de clubes desde el mismo seed producen el mismo output.
- [ ] Probar que liga y copa participan en una unica cronologia y que no se replica un subset.
- [ ] Probar que scoring no se encola hasta que el commit ELO termina.

### 3. Contratos read-side

- [ ] Extender `SeasonDTO` con `key`, `label`, `kind`, `includes_world_cup` y campos legacy necesarios.
- [ ] Extender `SeasonRepositoryProtocol` con resolucion de scope global y scopes disponibles por jugador.
- [ ] Agregar metodos scope-aware a `SFAScoreRepositoryProtocol` para ranking, count, detalle, stats, breakdown, rank y version comun.
- [ ] Agregar soporte de `AwardPeriodScope` a `PlayerEventRepositoryProtocol` y al port de logros.
- [ ] Actualizar todos los Fakes existentes para implementar el Protocol completo; no usar mocks.

### 4. Catalogo y resolucion de scopes

- [ ] Derivar award periods solo desde competiciones `participant_kind='club'` con datos disponibles.
- [ ] Derivar la opcion Mundial desde la competicion nacional y season fisica correspondiente.
- [ ] Vincular World Cup 2026 exclusivamente con `season-2025`; no aplicar una regla generica que absorba el Mundial en `season-2026`.
- [ ] Marcar latest usando la mayor season de clubes con scores, no `MAX(season)` global.
- [ ] Crear keys estables `season-{year}` y `world-cup-{year}` con labels en espanol.
- [ ] Ordenar opciones cronologicamente y mantener `all` como opcion virtual del frontend.
- [ ] Resolver scopes por jugador sin ofrecer una vista Mundial cuando el jugador no tenga scores alli.
- [ ] Probar que clubes 2026 crean `season-2026` sin colision con `world-cup-2026`.

### 5. Version comun y agregacion de ranking

- [ ] Implementar resolucion de `rules_version_id` comun a todas las fuentes; preferir el solicitado solo si tiene cobertura completa.
- [ ] Fallar con error de dominio cuando una fuente tenga scores en una version distinta o falte cobertura.
- [ ] Construir un filtro SQL de sources mediante OR de pares season/competition, generado desde el value object.
- [ ] Agregar por `player_id` puntos de eventos, bonuses, partidos y breakdown sin insertar filas nuevas.
- [ ] Calcular goles, asistencias, regates, duelos y B1 sobre todas las fuentes del scope.
- [ ] Conservar `use_total=true` como orden oficial del premio.
- [ ] Aplicar `competition_id` como interseccion del scope y no como adicion paralela.
- [ ] Seleccionar club representativo para award periods y seleccion para tournament scopes.
- [ ] Mantener busqueda, perfiles, posiciones, rank window, offset y total count consistentes.
- [ ] Probar explicitamente `award_total == club_total + world_cup_total` con y sin bonuses.
- [ ] Probar que `all` suma fuentes fisicas una vez y no suma el award period como otra fuente.

### 6. Perfil y trazabilidad del jugador

- [ ] Resolver el mismo scope y rules version en detail, events, fixtures, stats y achievements.
- [ ] Mezclar breakdowns por action type sumando count/pts y recalculando porcentajes sobre el total compuesto.
- [ ] Unir fixtures/eventos por IDs fisicos y ordenarlos por fecha sin duplicados.
- [ ] Sumar stats y conservar precision de pase ponderada por pases intentados/completados.
- [ ] Combinar logros de club 2025 y Mundial 2026 sin volver a calcular el bonus en lectura.
- [ ] Retornar `available_scopes` sin retirar `available_seasons` durante compatibilidad.
- [ ] Mostrar club/escudo del componente regular en el perfil del award period.
- [ ] Probar jugador con club+Mundial, solo club, solo Mundial y ninguna fuente.

### 7. Explicaciones del ranking

- [ ] Construir evidencia de ranking desde el scope resuelto y la version comun.
- [ ] Persistir explicaciones compuestas con scope `award_period`, separadas de `world_cup` y `ranking` legacy.
- [ ] Incluir contribuciones por competicion para que el texto pueda distinguir club y Mundial.
- [ ] Evitar reutilizar una explicacion cuyo source hash corresponda a una sola fuente.
- [ ] Regenerar explicaciones del top N solo despues de completar el recalculo de todo el scope.

### 8. Orquestador de recalculo

- [ ] Implementar `RecalculateAwardPeriodUseCase` reutilizando los use cases versionados existentes por cada source/competition.
- [ ] Validar que la version existe y que el scope es `award_period` antes de escribir.
- [ ] Recalcular scoring, inferir logros, refrescar bonuses y reconstruir season scores para cada componente.
- [ ] No sembrar ni progresar ELO nacional dentro del orquestador; exigir el gate ELO de clubes.
- [ ] No activar automaticamente la version al finalizar.
- [ ] Implementar task Celery sync-to-async con late imports, logs START/DONE y un advisory lock por scope/version.
- [ ] Hacer el proceso idempotente y reintentable; un rerun con la misma version debe producir los mismos totales.
- [ ] No generar explicaciones parciales desde `run_full_recalculation_task`; encolar una sola generacion al cerrar el award period.
- [ ] Exponer endpoint admin `POST /api/v1/scoring/recalculate-award-period` con `scope_key`, `rules_version_id`, `force_recalculate` e `infer_achievements`.
- [ ] Agregar ejemplos HTTP happy path, scope inexistente, scope tournament rechazado y version faltante.

### 9. API canonica y compatibilidad

- [ ] Extender `/seasons` con keys y metadata sin eliminar campos actuales.
- [ ] Agregar `scope` a ranking y endpoints de jugador.
- [ ] Responder 422 cuando una request incluya a la vez `scope` y `season`.
- [ ] Sin ambos parametros, resolver latest award period.
- [ ] Con solo `season`, conservar exactamente la semantica fisica previa.
- [ ] Incluir la key resuelta en responses de ranking/player para enlaces canonicos.
- [ ] Actualizar `.http` con `scope=season-2025`, `scope=world-cup-2026`, legacy `season=2025` y `all`.

### 10. Frontend

- [ ] Cambiar el valor interno del selector de `season` a `key` sin alterar el aspecto visual existente.
- [ ] Usar labels entregados por API y eliminar inferencias `value === '2026'`.
- [ ] Resolver la portada desde `is_latest`; con los datos actuales debe navegar a `scope=season-2025`.
- [ ] Mostrar `2025/2026` como actual y mantener `Mundial 2026` como opcion distinta.
- [ ] Mostrar `2026/2027` cuando el backend publique `season-2026`.
- [ ] Mantener `Total historico` y asegurar que no duplica rollups.
- [ ] Enviar scope en ranking, perfil, eventos, fixtures, stats, achievements y explicaciones.
- [ ] Actualizar todos los enlaces del modulo Mundial a `scope=world-cup-2026`.
- [ ] Migrar enlaces legacy `?season=2026` del frontend a la URL canonica del Mundial.
- [ ] Eliminar el hardcode `SEASON='2024'` de ComparePage y usar el scope latest/seleccionado.
- [ ] Mantener estados loading, empty y error durante cambios de scope.
- [ ] Verificar teclado, foco, `aria-checked`, responsive y que los labels no desborden.

### 11. Tests y calidad

- [ ] Ejecutar tests de dominio y use cases nuevos con Fakes completos.
- [ ] Ejecutar tests de repositorios/filtros del ranking.
- [ ] Ejecutar regresiones de multi-season, ranking, player detail, events, fixtures, achievements y explanations.
- [ ] Ejecutar `pytest tests/ --cov=src/sfa --cov-report=term-missing` con cobertura global >=80%.
- [ ] Ejecutar `flake8 src/ tests/` sin errores.
- [ ] Ejecutar `isort --check-only src/ tests/` sin errores.
- [ ] Ejecutar `npm run build` sin errores TypeScript.
- [ ] Levantar backend/frontend y verificar con Playwright desktop y mobile el selector, portada, Mundial y perfil compuesto.

### 12. Rollout en VPS

- [ ] Hacer backup de PostgreSQL antes de cualquier recalculo.
- [ ] Aplicar y auditar las migraciones existentes del motor final del Mundial antes de crear el snapshot.
- [ ] Consultar la configuracion final usada por el Mundial y crear una nueva version inactiva; no asumir IDs 4 o 5.
- [ ] Verificar cobertura de `team_strengths` de clubes 2025 y ELO nacional de Mundial 2026.
- [ ] Ejecutar el recalculo del scope `season-2025` en la version sombra.
- [ ] Verificar eventos, players, bonuses y logs DONE para cada componente.
- [ ] Ejecutar gates SQL de version comun, no duplicacion y reconciliacion club+Mundial.
- [ ] Comparar top 20 fisico de clubes, Mundial aislado y award period compuesto.
- [ ] Confirmar manualmente al menos cinco jugadores presentes en club y seleccion.
- [ ] Activar la version solo tras aprobar todos los gates.
- [ ] Verificar en produccion que `/ranking` sin parametros resuelve `season-2025` y que Mundial sigue seleccionable.
- [ ] Conservar comandos de reactivacion de la version anterior como rollback inmediato.

## Agent Routing Brief

**DDD Designer needed:** yes

El concepto `AwardPeriodScope` tiene invariantes de composicion, no solapamiento y version comun.
El DDD Designer debe validar el modelado del paso 2 antes de implementar repositories o use cases.
No se modifican ActionType, BASE_POINTS_TABLE ni multiplicadores; el resto de la implementacion
continua con los patrones normales de use case, repository, router, task y Fake definidos por SFA.

## Verificacion

1. `GET /api/v1/seasons` marca `season-2025` como latest y devuelve aparte `world-cup-2026`.
2. `GET /api/v1/ranking?scope=season-2025&use_total=true` suma clubes 2025 y Mundial 2026 bajo una sola version.
3. `GET /api/v1/ranking?scope=world-cup-2026&use_total=true` conserva el ranking aislado del Mundial.
4. Para un jugador presente en ambos scopes, detail, fixtures, events, stats y achievements reconcilian con las fuentes.
5. `GET /api/v1/ranking?season=2025` mantiene el resultado fisico legacy sin sumar el Mundial.
6. Al insertar scores de clubes 2026 en un entorno de prueba aparecen `season-2026` y `world-cup-2026` sin colision.
7. El recalculo repetido con la misma version produce los mismos hashes/totales y no modifica ELO.
8. `pytest`, coverage, flake8, isort, build frontend y Playwright desktop/mobile pasan antes del despliegue.
