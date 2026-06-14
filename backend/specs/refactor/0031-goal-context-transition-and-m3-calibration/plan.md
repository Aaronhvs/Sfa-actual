# Plan: Contexto de goles por transición y calibración versionada de M3/M4

## Archivos a crear

- [ ] `migrations/0023_goal_context_transition_expand.sql` — columnas e índices expand-only
  para transición, clave de fuente, estado de verificación y procedencia de dificultad.
- [ ] `src/sfa/application/use_cases/repair_goal_contexts.py` — dry-run y reparación histórica
  idempotente por fixture, competición, temporada o lote.
- [ ] `src/sfa/tasks/repair_goal_contexts_task.py` — ejecución Celery reanudable de la reparación.
- [ ] `tests/domain/test_score_timeline.py` — invariantes de línea de marcador y autogoles.
- [ ] `tests/domain/test_m3_goal_transition.py` — clasificación y calibración versionada.
- [ ] `tests/use_cases/test_repair_goal_contexts.py` — dry-run, escritura, ambigüedad y rollback.
- [ ] `tests/fixtures/api_football_fixture_1489370_events.json` — fixture contractual mínimo
  anonimizado desde la respuesta verificada de API-Football.

## Archivos a modificar

- [ ] `src/sfa/domain/scoring/value_objects.py` — nuevos value objects y campos versionables de
  `ScoringConfig`.
- [ ] `src/sfa/domain/scoring/services.py` — servicio puro `ScoreTimeline`.
- [ ] `src/sfa/domain/ingestion_ports.py` — secuencia/clave raw, external IDs del fixture y
  parámetros de transición/procedencia en el repositorio.
- [ ] `src/sfa/domain/scoring_ports.py` — ampliar `PlayerEventRawContextDTO` y port de consulta
  para recálculo.
- [ ] `src/sfa/infrastructure/providers/api_football.py` — normalizar secuencia y semántica de
  equipo beneficiado; eliminar reconstrucción de marcador del adapter.
- [ ] `src/sfa/infrastructure/models/events/models.py` — mapear columnas nuevas.
- [ ] `src/sfa/infrastructure/repositories/ingestion_repository.py` — persistir contexto nuevo y
  exponer scopes de reparación usando IDs externos.
- [ ] `src/sfa/infrastructure/repositories/player_event_score_repository.py` — cargar transición,
  estado y procedencia para scoring versionado.
- [ ] `src/sfa/application/use_cases/ingest_competition.py` — consumir `ScoreTimeline` y dejar
  PSxG ausente como NULL.
- [ ] `src/sfa/application/use_cases/reingest_player.py` — eliminar helper duplicado, usar IDs
  externos y `ScoreTimeline`, sin borrar eventos históricos antes de validar.
- [ ] `src/sfa/application/use_cases/calculate_scores_for_rules_version.py` — seleccionar M3
  legacy o transición por config; neutralizar M4 sin evidencia real.
- [ ] `src/sfa/application/use_cases/enrich_with_fbref.py` — marcar PSxG agregado como estimado,
  no como evidencia real para M4.
- [ ] `src/sfa/application/use_cases/enrich_with_understat.py` — marcar xG/estimación como
  estimado, no como PSxG real.
- [ ] `src/sfa/api/v1/admin.py` — endpoint admin para dry-run/reparación y consulta de contadores.
- [ ] `src/sfa/core/dependencies.py` — factories del use case y repositorio requeridos.
- [ ] `src/sfa/tasks/__init__.py` — registrar la task de reparación.
- [ ] `src/sfa/celery_app.py` — incluir task si el registro no es autodiscovery.
- [ ] `http/admin_repair_goal_contexts.http` — operaciones dry-run, lote y fixture 1489370.
- [ ] `tests/providers/test_api_football.py` — semántica de `Own Goal`, secuencia y IDs externos.
- [ ] `tests/use_cases/test_ingest_competition.py` — contexto canónico y M4 neutral.
- [ ] `tests/use_cases/test_reingest_player.py` — no mezcla de IDs, contexto canónico e
  idempotencia.
- [ ] `tests/use_cases/test_calculate_scores_for_rules_version.py` — compatibilidad legacy,
  transición nueva y exclusión de unresolved.
- [ ] `tests/domain/test_scoring_config.py` — round-trip y validación de configuración M3 nueva.

## Checklist de implementación

### Fase 1 — Baseline y contrato factual

- [ ] **1.1** Capturar antes de cualquier escritura los conteos y sumas de
  `player_events`, `player_event_scores` y `sfa_season_scores` agrupados por temporada,
  competición y `rules_version_id`; guardar el procedimiento de auditoría en el spec/runbook.
  Criterio: existe una consulta reproducible y su salida identifica la versión activa.

- [ ] **1.2** Crear el fixture contractual `1489370` con todos los goles en orden de respuesta,
  incluyendo autogol de D. Bobadilla al 7' con `team_external_id=2384` y gol de Mauricio al 73'.
  Criterio: el JSON no contiene secretos y permite reconstruir el 4-1.

- [ ] **1.3** Documentar en el test contractual que `team.id` en eventos Goal representa al
  equipo beneficiado, también para `Own Goal`. Criterio: el test falla si alguien vuelve a
  invertir el autogol.

### Fase 2 — Domain model [DDD]

- [ ] **2.1 [DDD]** Implementar `ScoreState` como frozen value object con goles no negativos y
  cálculo de diferencia únicamente tras validar el external ID contra home/away.

- [ ] **2.2 [DDD]** Implementar `GoalTimelineEvent` y `ScoreTransition` con las invariantes de
  `decisions.md`; excluir shootouts del marcador reglamentario.

- [ ] **2.3 [DDD]** Implementar `ScoreTimeline.build(home_team_external_id,
  away_team_external_id, events)`:
  - ordenar por `(minute, extra_minute, source_sequence)`;
  - ignorar eventos no Goal y `Missed Penalty`;
  - acreditar el gol al `team_external_id` recibido, incluido `Own Goal`;
  - producir transición indexada por `source_event_key`;
  - rechazar equipos fuera del fixture y claves duplicadas.
  Criterio: es un servicio puro sin imports de infraestructura.

- [ ] **2.4 [DDD]** Implementar `GoalImpactClass` desde `score_diff_before`; verificar que cada
  gol reglamentario avanza exactamente una unidad la diferencia del beneficiado.

- [ ] **2.5 [DDD]** Implementar `M3GoalTransition` con las cuatro bandas y tabla inicial de
  `decisions.md`; penalty=0.6 y shootout=1.5 configurables.

- [ ] **2.6 [DDD]** Implementar `ShotDifficultyEvidence`; únicamente `actual_psxg` entrega un
  valor a `M4ShotDifficulty`. El resto entrega `None`.

- [ ] **2.7 [DDD]** Extender `ScoringConfig` con campos M3 opcionales:
  `m3_transition_factors`, `m3_penalty_factor`, `m3_shootout_factor`,
  `m3_transition_clamp`. Criterio: una config antigua deserializa y conserva algoritmo legacy.

- [ ] **2.8 [DDD]** Validar en `ScoringConfig.__post_init__` que estén presentes las seis clases,
  las cuatro bandas, factores positivos dentro del clamp y claves desconocidas rechazadas.

- [ ] **2.9 [DDD]** Actualizar `to_dict/from_dict` y probar round-trip exacto tanto para config
  legacy como para config de transición.

### Fase 3 — Expand migration y modelos

- [ ] **3.1** Crear `0023_goal_context_transition_expand.sql` de forma idempotente con las seis
  columnas e índices definidos en `decisions.md`. Criterio: puede ejecutarse dos veces sin error.

- [ ] **3.2** Agregar checks no destructivos:
  `source_sequence >= 0`, valores permitidos de `context_status` y
  `shot_difficulty_source`. No aplicar NOT NULL a transición.

- [ ] **3.3** Actualizar `PlayerEvent` ORM con defaults compatibles. Criterio: el backend inicia
  con datos legacy y no requiere backfill inmediato.

- [ ] **3.4** Verificar la migración sobre una copia de DB y registrar conteos pre/post.
  Criterio: no cambia ninguna fila de scores ni total visible.

### Fase 4 — Contratos y adapter de API-Football

- [ ] **4.1** Extender `FixtureEventRawDTO` con `source_sequence` y `source_event_key`; aclarar que
  `team_external_id` es el beneficiado. Criterio: todos los fakes implementan el nuevo contrato.

- [ ] **4.2** En `fetch_fixture_events`, asignar secuencia desde el índice original y construir
  una clave determinista. Criterio: dos fetches idénticos producen las mismas claves.

- [ ] **4.3** Eliminar `APIFootballProvider.get_score_at_minute`. Criterio: no queda lógica de
  marcador en infraestructura ni referencias a ese método.

- [ ] **4.4** Extender `PlayerFixtureInfoRow` con
  `home_team_external_id`, `away_team_external_id` y `player_team_external_id`, obtenidos con
  aliases separados de `Team`. Mantener IDs internos solo para FKs.

- [ ] **4.5** Validar en repositorio que el equipo externo de aparición coincide con uno de los
  dos externos del fixture. Criterio: mismatch produce resultado unresolved, nunca fallback.

### Fase 5 — Persistencia canónica en ingesta y reingesta

- [ ] **5.1** Extender `IngestionRepositoryPort.upsert_player_event` y su adapter con
  `source_event_key`, `source_sequence`, `score_after`, `score_diff_after`,
  `context_status` y `shot_difficulty_source`.

- [ ] **5.2** En `IngestCompetitionUseCase`, construir una sola `ScoreTimeline` por fixture y
  reutilizar la misma transición para scorer y assist del mismo gol.

- [ ] **5.3** Guardar contexto desde la perspectiva del equipo del jugador:
  `score_before/after` siempre en orientación home:away; `score_diff/diff_after` desde el equipo
  del jugador. Criterio: un gol puntuable cumple `score_diff_after=score_diff+1`.

- [ ] **5.4** Para goles y penales sin PSxG real, guardar `psxg=NULL` y
  `shot_difficulty_source='missing'`. Eliminar defaults 0.32 y 0.75, incluido shootout.

- [ ] **5.5** En `ReingestPlayerUseCase`, eliminar `_get_score_at_minute` y consumir el mismo
  `ScoreTimeline` del dominio.

- [ ] **5.6** Corregir la mezcla de namespaces en reingesta: timeline y comparación usan solo
  external IDs; FKs de `player_events.team_id` usan únicamente IDs internos.

- [ ] **5.7** Cambiar reingesta a validate-before-write. Criterio: si timeline o asociación del
  jugador falla, no se borran eventos existentes del fixture.

- [ ] **5.8** Conservar evento STATS y contexto de aparición durante reingesta. Criterio: una
  segunda ejecución no cambia conteos ni IDs de eventos ya asociados.

### Fase 6 — Reparación histórica segura

- [ ] **6.1** Definir en `IngestionRepositoryPort` DTOs frozen y métodos para:
  listar fixtures por scope/estado, cargar eventos puntuables existentes, actualizar hechos en
  sitio, marcar unresolved y obtener contadores.

- [ ] **6.2** Implementar `RepairGoalContextsUseCase.execute(scope, dry_run, batch_size,
  resume_after_fixture_id)` con resultados:
  fixtures analizados/verificados/reparados/unresolved, eventos actualizados, PSxG sintéticos
  neutralizados y errores.

- [ ] **6.3** Para cada fixture, reconstruir timeline y compararlo con resultado final de API.
  Criterio: cualquier diferencia marca fixture unresolved y evita escrituras parciales.

- [ ] **6.4** Asociar cada GOAL/ASSIST existente a `source_event_key` usando fixture, equipo,
  jugador/assist normalizado, tipo y minuto. Criterio: exactamente un candidato; cero o más de
  uno es unresolved.

- [ ] **6.5** Actualizar filas inequívocas en sitio conservando `player_events.id`. Criterio:
  ninguna fila de `player_event_scores` de versiones antiguas se elimina por cascade.

- [ ] **6.6** Copiar idéntica transición a scorer y assist del mismo gol y marcar
  `context_status='verified'`.

- [ ] **6.7** Neutralizar valores sintéticos conocidos solo cuando su procedencia pueda
  demostrarse mediante reingesta: guardar NULL/missing. Valores históricos no demostrables
  quedan `legacy_unknown`, que también produce M4=1.0 en la versión nueva.

- [ ] **6.8** Hacer el use case idempotente: fixtures ya verified con la misma clave/hash se
  omiten; fixtures unresolved pueden reintentarse.

- [ ] **6.9** Implementar task Celery con lotes, logs estructurados y reintento desde el último
  fixture confirmado. Criterio: un fallo no revierte lotes anteriores ni salta pendientes.

- [ ] **6.10** Agregar endpoint admin protegido:
  `POST /admin/scoring/goal-context-repair` con `dry_run=true` por defecto y filtros
  fixture/season/competition.

- [ ] **6.11** Agregar endpoint admin de estado/contadores. Criterio: muestra por scope
  `legacy_unverified`, `verified`, `unresolved` y divergencias de marcador.

### Fase 7 — Scoring versionado

- [ ] **7.1** Ampliar `PlayerEventRawContextDTO` y query de
  `PlayerEventScoreRepository.get_events_for_recalc` con transición, status y fuente PSxG.

- [ ] **7.2** En `CalculateScoresForRulesVersionUseCase`, si config no contiene tabla de
  transición, usar `M3MinuteScore` legacy exactamente como hoy.

- [ ] **7.3** Si config contiene tabla de transición, requerir `context_status='verified'` y
  construir `M3GoalTransition`. Criterio: unresolved se omite, cuenta y loguea; no usa empate
  neutral.

- [ ] **7.4** Aplicar la misma M3 al gol y su asistencia porque ambos participan en la misma
  transición; mantener puntos base diferentes por acción/posición.

- [ ] **7.5** Construir M4 mediante `ShotDifficultyEvidence`. Criterio: missing, estimated y
  legacy_unknown producen 1.0; solo actual_psxg usa fórmula.

- [ ] **7.6** Ampliar `calculation_details` con marcador antes/después, diff antes/después,
  clase de impacto, banda de minuto, algoritmo M3 (`legacy|transition`), fuente de dificultad y
  motivo de M4 neutral.

- [ ] **7.7** Incluir contadores `events_skipped_unresolved_context` y
  `events_m4_neutral_missing_evidence` en el resultado/log del recálculo.

### Fase 8 — Nueva versión y shadow recalculation

- [ ] **8.1** Crear una nueva versión inactiva copiando la config activa y añadiendo únicamente
  la tabla M3 y campos nuevos. No editar `config_json` de versiones existentes.

- [ ] **8.2** Ejecutar recálculo en sombra por temporada y competición, con
  `force_recalculate=True`, después de reparación.

- [ ] **8.3** Generar reporte comparativo por versión:
  top 50, mediana/percentiles de puntos por gol, distribución M3/M4, máximos, jugadores que
  cambian más y número de eventos omitidos.

- [ ] **8.4** Verificar específicamente fixture 1489370:
  Mauricio minuto 73, 3:0 -> 3:1, -3 -> -2, clase FAR_DEFICIT_REDUCTION, M3=0.75, M4=1.0
  salvo evidencia actual_psxg.

- [ ] **8.5** Confirmar que los totales y rankings de todas las versiones anteriores son
  idénticos al baseline.

- [ ] **8.6** Activar la versión nueva solo si todos los gates de `decisions.md` están en cero y
  existe aprobación explícita del reporte comparativo.

### Fase 9 — Tests de dominio

- [ ] **9.1** `test_own_goal_credits_api_beneficiary_team` con el autogol del fixture 1489370.
- [ ] **9.2** `test_fixture_1489370_reconstructs_real_score_sequence`.
- [ ] **9.3** `test_mauricio_transition_is_three_nil_to_three_one`.
- [ ] **9.4** `test_same_minute_events_follow_source_sequence`.
- [ ] **9.5** `test_unknown_team_external_id_is_rejected`.
- [ ] **9.6** `test_missed_penalty_does_not_change_score`.
- [ ] **9.7** `test_shootout_goal_does_not_change_regulation_score`.
- [ ] **9.8** Tests parametrizados de las 24 celdas de la tabla M3.
- [ ] **9.9** `test_transition_m3_never_reads_final_score`.
- [ ] **9.10** `test_missing_psxg_is_m4_one`.
- [ ] **9.11** `test_estimated_psxg_is_m4_one`.
- [ ] **9.12** `test_actual_psxg_uses_formula`.
- [ ] **9.13** `test_legacy_config_preserves_legacy_m3_results`.

### Fase 10 — Tests de flujos

- [ ] **10.1** Ingesta completa: scorer y assist comparten source key y transición.
- [ ] **10.2** Ingesta completa: Own Goal afecta timeline pero no crea GOAL puntuable.
- [ ] **10.3** Reingesta: usa external IDs aunque IDs internos sean distintos.
- [ ] **10.4** Reingesta: fixture inválido no borra eventos previos.
- [ ] **10.5** Reingesta repetida conserva conteos e IDs.
- [ ] **10.6** Reparación dry-run no escribe.
- [ ] **10.7** Reparación conserva scores históricos y event IDs.
- [ ] **10.8** Reparación ambigua marca unresolved sin escritura parcial.
- [ ] **10.9** Reparación reanudada omite verified y procesa pendientes.
- [ ] **10.10** Recálculo legacy no exige transición y reproduce resultado anterior.
- [ ] **10.11** Recálculo nuevo excluye unresolved y reporta contador.
- [ ] **10.12** Recálculo nuevo genera M3=0.75/M4=1.0 para Mauricio.
- [ ] **10.13** Bulk rebuild afecta solo la nueva rules version.
- [ ] **10.14** Activación de versión conserva posibilidad de reactivar la anterior.

### Fase 11 — Verificación técnica

- [ ] **11.1** Ejecutar tests focalizados de dominio, provider, ingesta, reingesta, reparación y
  scoring versionado.
- [ ] **11.2** Ejecutar `pytest tests/` y documentar deuda preexistente si impide el gate global;
  todos los tests nuevos y afectados deben pasar.
- [ ] **11.3** Ejecutar `flake8` sobre archivos creados/modificados sin errores.
- [ ] **11.4** Ejecutar `isort --check-only` sobre archivos creados/modificados sin errores.
- [ ] **11.5** Ejecutar migración dos veces sobre DB efímera/copia y verificar idempotencia.
- [ ] **11.6** Ejecutar dry-run del fixture 1489370 y adjuntar los valores esperados al reporte.
- [ ] **11.7** Ejecutar auditoría histórica sobre copia reciente antes de producción.

## Agent Routing Brief

**DDD Designer needed:** yes

Los ítems 2.1 a 2.9 requieren modelado de dominio porque introducen value objects con
invariantes futbolísticas y una nueva semántica versionada de M3. `ScoreTransition` debe
garantizar que un gol avance exactamente una unidad al equipo beneficiado; `GoalImpactClass`
representa el impacto causal sin mirar el resultado final; `M3GoalTransition` transforma esa
clasificación en factores configurables y reproducibles; `ShotDifficultyEvidence` impide que
estimaciones se presenten como PSxG real.

El DDD Designer debe completar primero la Fase 2. Después:

- Architecture/Backend implementa ports, migración, repositorios y use cases.
- Scoring specialist revisa la tabla inicial y el reporte de shadow recalculation.
- QA/Data ejecuta reparación y gates sobre copia de DB.
- Operaciones activa la nueva versión solo tras aprobación explícita.

## Verificación

1. Consultar fixture 1489370 en dry-run. Debe reconstruir 4-1 y la transición de Mauricio
   exactamente como 3:0 -> 3:1, `-3 -> -2`.
2. Verificar que la nueva versión calcula M3=0.75 para ese gol y no usa el resultado final.
3. Verificar que M4=1.0 cuando no existe `actual_psxg`.
4. Comparar checksums/conteos de versiones antiguas antes y después de la reparación.
5. Ejecutar reparación histórica hasta:
   - final-score mismatches = 0;
   - invalid-team transitions = 0;
   - new-version unresolved scored = 0;
   - scorer/assist context mismatches = 0.
6. Ejecutar shadow recalculation y revisar top 50 y outliers antes de activar.
7. Activar la nueva versión en una transacción; comprobar ranking y detalle de Mauricio.
8. Probar rollback reactivando la versión anterior sin modificar hechos ni eliminar scores.
