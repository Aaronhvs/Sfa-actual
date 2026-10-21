# Plan: 0065 — Sistema global y continuo de posiciones verificables

## Hotfix prioritario ELO/live sin perder el piloto publicado

- [ ] Correlacionar PID/consulta/CPU y plan del replay con los triggers activos; capturar backlog/propietario y hashes del batch publicado antes de remediar. No desactivar guardas ni usar privilegio publisher para ingestas.
- [ ] Añadir migración compatible que reemplace el escaneo DISTINCT de manifest por lookups específicos OLD/NEW y proyección mínima; verificar índice parcial de fixture allowlist con EXPLAIN real. No editar únicamente 0053 ya aplicada.
- [ ] En 0055 proyectar rules_version_id e IDs completos de bonos/rollups del journal en columnas STORED generadas con helper IMMUTABLE puro; validar equivalencia con manifest/after_image de batches v1/v2 antes/después. Reemplazar todos los hotloops JSON por columnas pequeñas, nunca b.*; conservar status publicado, OLD/NEW y bypass exclusivo, sin omitir imágenes malformadas.
- [ ] Hacer replace_fixture_team_strengths diferencial por claves con upsert condicional de campos semánticos, timestamps estables y eliminación solo de claves obsoletas; conservar rechazos/candidates de inputs protegidos diferentes.
- [ ] Validar replay idéntico sin churn/candidates técnicos, fixture nuevo con dos snapshots reales, OLD/NEW protegido y candidate idempotente; hashes de scores/bonos/etiquetas y rollback del piloto siguen correctos.
- [ ] Benchmark en clon representativo con triggers activos, suite relevante y SQL real; medir ELO seguido de scoring/bonos y demostrar eliminación de lecturas por fila del manifest/after_image bulk. DDL con writers drenados; replay/cierre compatible con ciclo diez minutos antes de reactivar scheduler. Coordinar try-lock/retry acotado y catch-up de 0057.

## Prioridad vigente: aplicar piloto real exclusivamente season-2026

Usuario autoriza cambiar posiciones y recalcular, limitado a temporada 2026/27. Esta etapa sustituye la pausa anterior dentro del alcance; no pedir otro opt-in por jugador/SHA. Conservar el ranking 0066 ya desplegado y no tocar otros periodos.

- [ ] Congelar captura fresca completa de los pares ScoreSource de season-2026 y versión activa; excluir Mundial y otras temporadas. Inventariar scores aunque API 0066 los oculte. Registrar backup restaurado/clon y baseline exacto de scores/detalles/rollups/bonos/honors/ranking.
- [ ] Materializar cohorte revisada por IDs: no GK, ≥6 XI recientes válidos, soporte ≥75 %, primaria temporada igual, sin conflictos/referencias protegidas; corte actual 261/67 top 300. Revisar cada decisión y exportar exclusiones, sin convertir los umbrales en certeza habitual ni hardcodear nombres.
- [ ] Importar de forma idempotente evidencia archivada y arbitraje durable de versiones activas; conservar superseded originales/proofs y usar misma selección en SQL/capture/replay. Confirmar Cásseres 1552785 desbloqueado por autoridad real, no por omitir evidencia conflictiva.
- [ ] Extender request/manifest versionado: decisiones `curated_fixture_scoring_role` por allowlist y referencia habitual actual opcional independiente, default conservar. Resolver histórico admite el tipo curado solo para fixture/contexto; habitual actual nunca lo consume. Preservar lectura de manifests antiguos. [DDD]
- [ ] Incluir `scope_scoring_classification` por jugador/scope/conjunto de competiciones/revisión en manifiesto/journal; proyección reconstruible solo desde batches publicados/no revertidos. Cambiar etiquetas/filtros/count de season-2026 con misma proyección antes de paginar, sin Player.position global ni falsa referencia habitual. Las actuaciones conservan su posición propia y fuera del alcance no cambia la lectura. [DDD]
- [ ] Generar allowlists con XI específico compatible; excluir minoritarios distintos/ambiguos/suplentes/faltantes. Fermín/Olmo MCO protegidos. Actual habitual solo si tiene decisión/evidencia propia; no insertarla automáticamente al corregir historia.
- [ ] Adaptar cierre puro bulk existente a la cohorte aceptada: paridad completa, todos los eventos/STATS elegibles, bonos rank-in-team y pares no reclasificados, agregados/honors y etiquetas. Deduplicar filas compartidas; no quitar el guard achievements del publisher individual sin cierre de reemplazo probado.
- [ ] Extender plan/ports/repositorio/journal before/after y CAS para bonos de compañeros, rollups, decisiones y categorías del scope. Seleccionar componentes de dependencia cerrados y reanudables; si varios commits, recapturar siguiente plan sobre baseline posterior. No encadenar aprobaciones independientes stale de 261 jugadores.
- [ ] Corregir IngestCompetitionUseCase mediante port de categoría aceptada por fixture/contexto antes de GK/grupo/scoring; SQL adapter y loader de recálculo comparten resolución. No aplicar categoría representativa del scope como posición automática de toda actuación futura. Tests reingesta muestran mismos scores corregidos y ledger para cambio upstream incompatible.
- [ ] Integrar source/base af3a4a0 del worktree limpio con phase1.1 y soporte mínimo de posiciones. Preservar todos los filtros/queries metadata de 0066 al introducir proyección; verificar min_matches, positivos, name y count en SQL real. No sustituir repo completo desde root dirty.
- [ ] Validar 0053 y source final en clon fresco: bulk apply atómico, failpoint, duplicado idempotente, CAS contra cambios, revert exacto incluyendo bonos/categorías y rechazo de revert tras cambios posteriores; snapshots de otros scopes/periodos intactos.
- [ ] Verificar todos los writers con shared desde primera lectura; deploy de resolver/protocolo también a workers que lo necesitan antes de reanudar. Prueba outer-shared→exclusive Busy→child-shared completa, luego retry nuevo; publisher misma sesión sin upgrade/hijas. Guardas SQL/conservación cubren filas de bonos/categorías y permiten partido nuevo legítimo.
- [ ] Suite completa sin fallos, ≥80 % módulos nuevos/líneas cambiadas e integración PostgreSQL/clon/HTTP de rutas afectadas; documentar cobertura global heredada sin inflarla ni cambiar CI. Distinguir readiness real del incremento de deuda global no atribuible.
- [ ] Operar ventana coordinada con backup/source/imágenes/flags previos: suspender beat, drenar y detener writers incompatibles, aplicar migración comprobada y soporte mínimo manteniendo 0066. Capturar/revalidar manifiesto definitivo; exclusivo try-only, CAS y commit bulk. Busy/source stale se remedia con rollback/nueva captura, no forzando aprobación.
- [ ] Smoke real de etiquetas del scope y scores/bonos/rollups/filtros/count: IDs Cásseres/Dembélé/Raphinha/Camello y MCO protegido como regresiones, más jugadores arbitrarios; exclusión Mundial/otras temporadas. Restaurar servicios compatibles y programación en finally, comprobar reingesta controlada y pendientes.
- [ ] Entregar evidencia de publicación efectiva: batch/hash, scope, cambios reales de categorías/actuaciones/bonos/rollups y delta/ranking, pendientes y rollback preparado. No llamar aplicado a preview; continuar remediando componentes retenidos sin cambiar metodología ni extender scope.

## Orden vigente 2026-10-20: posiciones local → filtro ranking → despliegue solo ranking

La autorización de producción se reabre únicamente para el spec 0066. No commitear/desplegar este spec, código, migraciones o datos de posiciones junto con ranking. Mantener phase1.1 del VPS y su configuración exacta.

- [ ] Congelar inventario y contar apariciones distintas de club/temporada con minutos positivos. Excluir de solicitudes motivadas por jugador a quienes tengan <3; conservar filas/motivos y evidencia incidental de fixtures compartidos.
- [ ] Materializar dos tramos por IDs: ambiguos/insuficientes top 300 (captura: 80+12), luego insuficientes con ≥6 apariciones (captura: 205). Ordenar por puntos/ID, deduplicar fixtures, conservar checkpoint y reportar pendientes 3–5 fuera del primer tramo sin declarar completitud global.
- [ ] Inventariar y drenar consumidores upstream; coordinar ventana de tandas sin ingestas/collector paralelos y registrar/restaurar cualquier suspensión operativa de dispatch. Consultar status/headers, conservar reserva 100 y caps; 7.500/día no es saldo disponible garantizado. No iniciar GET si no puede asegurar esa ventana.
- [ ] Registrar estado previo beat/worker, suspender beat, drenar y comprobar active/reserved/scheduled/cola; pausar worker solo idle durante GET secuenciales. Restaurar worker→beat en finally según estado inicial y verificar salud, sin builds/flags nuevos. Si hay tareas activas que no drenan, no matarlas: restaurar y posponer HTTP. Registrar que API fallback puede consumir cuota y no hay exclusión global absoluta de la cuenta.
- [ ] Separar familia raw G/D/M/F y equivalentes de roles específicos: GK/DC/MC/DEL genéricos `unverified`, ausencia UNKNOWN sin default, legacy sin payload `legacy_unverified`. Pruebas de M genérico que no rebaja MCO, F que no demuestra CF y ausencia que no genera MC.
- [ ] Retirar invocaciones programadas/legacy de clasificadores estadísticos; entrada obsoleta falla explícitamente sin escritura. Verificar que números de saves/interceptions/goals no alteran ninguna resolución. No incluir estos cambios en commit/despliegue ranking.
- [ ] Documentar precedencia de la versión definitiva más reciente de 1552785 con hashes/origen/fecha/equipo y supersedes; construir conjunto activo derivado sin borrar originales. Regresiones: conflicto sin arbitraje permanece; precedencia comprobada desbloquea; latest cache no autoritativo no desbloquea; misma política con IDs arbitrarios.
- [ ] Reconciliar cantidades reales (197 insuficientes ≥6 matches frente a 185 por apariciones club; 4.193 con 1–2 matches) y exportar diferencias por ID, sin hardcodear recuentos viejos. Separar missing/stale_or_invalid/intrinsic_ambiguity/insufficient_starts; no reintentar automáticamente el intento incierto 1556502.
- [ ] Ejecutar refresh autoritativo acotado solo por motivo stale/invalid/conflicto, empezando 1552785; conservar received_at/fetched_at reales y comparar endpoint/identidad/XI completo. Un GET por fixture/revisión, no refetch masivo de ambiguos válidos; empate de autoridad permanece desconocido. Regenerar replay sobre conjunto activo con manifiesto de supersedes.
- [ ] Repetir replay/matriz/paridad/impacto offline con el conjunto activo y tramos actualizados; entregar pendientes/exclusiones y estado preciso de muestra. No recalcular ni publicar posiciones/puntos en producción.
- [ ] Terminar esta etapa y entregar su evidencia antes de implementar 0066; separar por completo archivos de posiciones del índice/commit, worktree/build y despliegue ranking. Verificar el diff de release y su manifiesto de archivos, no confiar en git add del repositorio compartido.

## Prioridad vigente: auditoría completa y simulación offline, sin aplicación

Esta ampliación autoriza captura de solo lectura y GET acotados del proveedor existente. No habilita publicación, migraciones, despliegue, flags ni escrituras de posiciones/puntos en producción. Las tareas históricas de publicación de abajo siguen suspendidas.

- [x] Congelar export READ ONLY/REPEATABLE READ de `season-2026` (2026/27), pares ScoreSource, versión activa resuelta, ranking completo `use_total=true`, configuración/motor y corte UTC. Contrastar con SFAScoreRepository/API; excluir Mundial físico 2026 perteneciente a otro award. Conservar jugadores con cero/negativos y todos los componentes del total; no limitar al top 50.
- [x] Exportar raws, scores persistidos, ELO/configuración, bonos/honores, inventario de fixtures y XI disponibles sin getters que capturen datos ni loaders que excluyan silenciosamente por ELO faltante. Guardar manifiesto y hashes locales; registrar entradas no reproducibles.
- [x] Producir matriz para todos los IDs puntuados: posición almacenada, efectiva, referencias aceptadas, propuesta/estado, soporte y faltantes. Añadir agregación pura `club_season` por jugador/equipo/temporada con competition_set, procedencia y desglose por competición; deduplicar fixtures sin mezclar selección u otro club. No modificar PositionContext ni simular un competition_id artificial. Proteger MCO aceptado de Fermín/Olmo frente a slots CM.
- [x] Construir cola por puntos baseline y desempate estable; recuperar fixtures faltantes compartidos una sola vez, primero reutilizando archivos. Tandas secuenciales de máximo 10 GET lineups + 1 status, concurrencia 1, máximo un request por segundo y headers/cuota/reserva 100. Checkpoint local antes/después de cada intento; detener ante 429/error/cuota desconocida. Sin collector, Redis SET o ledger de producción. Reanudar tandas distintas mientras exista presupuesto y pendientes; no confundir TTL vencido con ingesta fallida.
- [x] Validar Dembélé 7571 y su quinto fixture: la captura inicial tiene tres CF y un W en cuatro XI. Confirmar o refutar DEL 4/5 en club_season con evidencia, no asumirlo. Exponer perfiles por competición y cobertura desconocida cuando falte calendario/titularidades. W/AM ambiguo no recibe votos 50/50 ni downgrade de referencias.
- [x] Probar paridad offline usando posición realmente persistida de cada event score y motor puro: base/final/factores/STATS/B1/redondeos. Congelar heurísticas estadísticas/nombres/fallback MC fuera de este clasificador en diseño; no ejecutar repair ni recálculo persistido. Falta de ELO/paridad produce exclusión explicada, nunca números inventados.
- [x] Ejecutar hipótesis `fixture_backed_starting_slot` solo donde XI específico, válido y compatible justifique la propuesta, incluyendo todas las acciones/STATS del fixture. Mantener baseline exacto en faltantes/ambiguos/protegidos. No aplicar la primaria actual retroactivamente a toda la temporada; no transformar simulación en asignación aceptada.
- [x] Cerrar en memoria bonos dependientes de rank-in-team/performance_factor para todos los compañeros/alcances afectados, con helpers puros o use case y fake repository. Verificar supercopas/achievements y paridad de bonos; demostrar honors raw invariantes. Si la dependencia no cierra, conservar ese ámbito y marcar dependency_unresolved; no anunciar movimientos finales exactos con deltas parciales.
- [x] Reordenar el universo entero con totales y desempates de referencia; exportar top 50 antes/después, unión, entradas desde fuera, salidas, deltas por jugador/fixture y cobertura/exclusiones. Validar caso sintético fuera-del-top-50 que entra, ceros/negativos, empate, exclusión Mundial, agregación multicompetición, referencias protegidas, XI faltante y error de ELO. Entregar manifest/paridad/matriz/adquisición/simulación/CSV/summary en `output/audits/positions-2026-10-19/active-season-impact/<run-id>/`.

Gate del informe numérico: baseline y cierre de dependencias reproducidos para el ámbito anunciado. Lo no simulable sigue visible en la matriz; remediar sin presentarlo como posición correcta ni como delta cero demostrado. No se crea aggregate ni nueva invariante de scoring; se reutiliza el modelo revisado por DDD. Este incremento termina en evidencia e informe, no en publicación.

Resultado de la auditoría local (2026-10-19 Chile): 6.698 jugadores, 751 candidatos,
495 coincidencias, 379 dudosos, 5.071 insuficientes y 2 referencias protegidas.
Se recuperaron 376 fixtures en 39 tandas; el intento incierto 1556502 permanece en
cuarentena sin repetición. Una segunda corrida de la cola actualizada no hizo GET.
Se reprodujeron exactamente 24.339 scores, 8.637 rollups, 1.161 bonos y el ranking.
La hipótesis calculable modifica puntos de 701 jugadores y produce cuatro entradas
y cuatro salidas del top 50. Los 52 candidatos GK conservan baseline por falta de
grupo de scoring; no se les asigna un cero. Dembélé confirma DEL en cuatro de cinco
XI reales; Cásseres observa MC pero conserva un conflicto. Fermín/Olmo siguen MCO.
Pasan 1.017 pruebas, con 15 omitidas; cobertura global 70,91 %, sin aprobación de
release. Arquitectura cerró la revisión de la cola y de conflictos entre equipos.
La repetición conserva ocho hashes; los hashes de posiciones y puntos de producción
siguen idénticos. Informe y CSV en
`output/audits/positions-2026-10-19/active-season-impact/20261019-catalog/`.
No se aplicaron posiciones/puntos ni se desplegó; cero casos publicables por
inventario completo de titularidades no demostrado.

## Restricción vigente y QA de concurrencia

El usuario revocó cualquier paso a producción: **solo implementación y QA local/clon**. No desplegar código, migraciones o configuración, ni publicar posiciones/puntos en producción. Los planes y autorizaciones anteriores quedan suspendidos para ese entorno. Cobertura ≥80 % y automatización global siguen sin aprobar; no declarar release-ready.

- [ ] Sustituir adquisición exclusiva bloqueante por pg_try_advisory_xact_lock en publicación y compensación; false genera PublicationBusy antes de inputs/CAS y no deja marca de lock adquirido.
- [ ] Reintentos solo después de rollback, en sesión/transacción nueva, sin polling ni espera exclusiva encolada; no exceptuar lecturas ni cambiar orquestadores para eludir shared.
- [ ] Prueba clon outer-shared → exclusive-Busy → child-shared-completa → outer-cierra → nuevo-exclusive-adquiere; Busy no realiza lecturas de negocio ni escrituras.
- [ ] Prueba clon exclusive-adquirido bloquea writer nuevo hasta commit/rollback; verificar errores/cancelación y rechazo de cambio de modo dentro de la misma transacción.
- [ ] Verificar DI de publicador/compensador: todos los repositorios y revalidación usan la misma sesión exclusiva, sin await a hijas que abran shared; no quedan llamadas exclusivas bloqueantes.
- [ ] Conservar evidencia de las ocho comprobaciones de conservación SQL en clon y suite informada 966 pass / 15 skip; registrar skips reales y deuda del source-hash de explicaciones inestable por orden, sin modificar números por ese diagnóstico.

Estas comprobaciones completan QA del borrador, no autorizan producción. No marcar los gates de cobertura/paridad global o release como cumplidos solo por completar este ajuste.

## Prioridad inmediata: publicación curada real de Raphinha

Actualización2026-10-19: adquisición funciona en producción; resolver puro local tiene40tests y suite documentada920. El usuario autoriza empezar a aplicar. Este incremento culmina en publicación limitada cuando pasen gates; no otro preview. La muestra100jugadores/todasplantillas evalúa autoaceptación global, no un caso curado. Paridad, integridad, concurrencia, reversión y checks exigidos no se reducen.

- [ ] Registrar decisión por player_id35/API1496 y team_id1/API529/season2026: habitual actualDEL desde confirmación y decisión histórica separada restringida a ocho fixtures tabulados en decisions.md; revalidar evidencias/fechas/contexto y excluir77802/1570413, Mundial y otros periodos. [DDD]
- [ ] Extender scope/query/loader con applicable_fixture_ids y fixture_id internos; validar lista no vacía y pertenencia, adaptar solapamientos para ámbitos disjuntos sin tolerar conflicto aplicable. Pruebas con IDs arbitrarios, sin ramas por nombre. [DDD]
- [ ] Integrar resolver y proyecciónSQL de lectura/count/filtros/ficha/scoring: current_habitual evalúa as_of actual delscopeactivo y los eventos sufecha/fixture. DELactual puede coexistir con EXT histórico explícito, sin retrofechar la decisión.
- [ ] Extraer motor puro idéntico y simular usando posición realmente puntuada enbaseline; incluir acciones/STATS de ocho fixtures, cierre de bonos/ranks/honores derivados yrollups1/10/scopes. Obtener informe/hash aprobado sin mutar producción.
- [ ] Implementar journal/publicador/compensación; clon restaurado prueba CAS de inputs/conjuntofilas, atomicidad, idempotencia, failpoints y rollback que no pisa cambios posteriores. No rebuildmasivo fuera del manifiesto. [DDD]
- [ ] Verificar exclusión completa read→compute→write: triggers BEFORESTATEMENT compartidos son defensa adicional, no bastan contra lectura previa al commit. Adquirir shared alinicio o rechazar scorestale porCAS/revisión; publicador exclusivo antesdelectura y sinupgrade accidental. Probar intercalado scorerlee→publish→scorerwrite.
- [ ] Si es necesario, pausar/drenar writerslegacy en ventana delpiloto y completar integración/protección antes de reanudarlos. Cumplir checks requeridos sin llamar80 % a la cobertura70,39 % actual; desplegar soporte y aplicar solo batchcurado ID/hash aprobado con autoaceptaciónglobaloff.
- [ ] Verificar API, filtrosDEL/EXT, totales/históricos, hashes ajenos, journal y reingesta controlada despuésdelcommit. Si algún gate falla, remediar y continuar; no declarar publicación sin evidencia ni pedir de nuevo autorización rutinaria.

Salida revisable: decisión/fecha/allowlistfixture, comparativa numérica real, reglas/inputs hash, exclusión y prueba de reversión, estado efectivo de publicación. Nada autorizaDELpara toda la carrera ni heredarCFdesdebanquillo. El mismo publicador sirve cualquier batchcurado; Raphinha es un manifiesto de datos.

Estado: adquisición durable y preservación de referencias desplegadas el 2026-10-18 (Chile),
2026-10-19 UTC. Publicación de posiciones y puntos desactivada. Las etapas siguientes siguen pendientes.

### Evidencia de ejecución operativa

- Producción: imagen `sfa-positions:20261018-phase1.1` en API, worker y beat; migración 0052 aplicada.
- Backup de 44.364.586 bytes, SHA256 `db73a356f00e6466d529ee1981acd9060d36e85dddfe947bde309ed2fd2fb934`,
  restaurado en `sfa_positions_validation_20261018`. Integración real de PostgreSQL y Redis: idempotencia,
  rollback, protección de referencias y CAS del lease comprobados.
- Importación inicial: 26 XI, 558 evidencias, 2 referencias habituales por pareja de IDs. Los MD5 de
  13.185 jugadores, 213.668 eventos, 384.365 event scores, 57.813 season scores y 3 versiones de reglas
  permanecieron idénticos durante la importación.
- Manifiesto stored/effective/scored por ID: 13.185 jugadores, 51.610 contextos de scoring. Es comparación
  legacy, no verificación deportiva ni autorización de intervalos históricos.
- Dos ciclos reales acotados: 20 partidos nuevos, 26 HTTP totales (22 de lineups/status y 4 de
  calendar/status), cero errores. Total: 66 XI, 1.378 evidencias (649 starting_slot,
  75 starting_participation, 652 bench_membership y 2 habitual_football_role).
- Reconciliados calendarios Liga 140 y Premier 39; faltan XI, estado parcial explícito.
- Collector cada 15 minutos, cap de 10 partidos por ciclo y 1 calendario, pacing de al menos 1 segundo,
  lease global entre collectors, checkpoint antes de HTTP, reserva diaria 100 y parada ante 429.
  Otros consumidores comparten cuenta upstream, pero no un presupuesto Redis común; la reserva no
  garantiza saldo frente a ellos.
- `POSITION_ACQUISITION_ENABLED=true`; shadow, publication y automatic_refresh desactivados.
  HTTP health 200; Fermín 52 y Olmo 517 siguen MCO; no se ejecutó recálculo.
- Suite de 880 pruebas pasa para esta entrega; cobertura global previa 70 %, inferior al gate final 80 %.
- Evidencia local: `output/audits/positions-2026-10-18/release/`; runbook actualizado.
  Resolver puro siguiente en desarrollo local, todavía sin integración de lecturas ni puntuación.
  Tiene 40 regresiones para contexto, intervalos, 80/20 observado, conflictos y ausencia de evidencia;
  revisión DDD cerrada tras visibilizar candidatas habituales incompatibles. No está desplegado.

## Orden de ejecución autorizado para culminar

El usuario autoriza implementar y llevar este camino a producción cuando pasen sus gates. Esta sección prioriza el inventario exhaustivo que sigue abajo; no lo reemplaza por otro preview ni pide nuevas confirmaciones rutinarias. Conservar los hitos cumplidos y cambios ajenos. Los gates fallidos se remedian con pruebas/evidencia, reteniendo solamente el alcance inseguro mientras continúa la adquisición independiente.

### 1. Hoy: persistencia durable, cobertura y protección por ID

- [ ] Reservar la siguiente migración real (actuales 0051 / previstas 0052), verificar archivos ignorados que deben incluirse en el release y preparar clon/backup; añadir fixture_lineup_snapshots, position_source_coverage, player_position_evidence y player_position_assignments con FK/índices/idempotencia.
- [ ] Implementar repos/Protocols extendiendo el contexto player_positions actual; importar corpus local recuperado por hashes, mantener versiones y consultar ledger sin depender de Redis. Prueba: reinicio/cache vacía de prueba conserva todos los XI y no duplica titularidades.
- [ ] Generar manifiesto stored/effective/scored por ID y migrar únicamente paridad efectiva aceptada; Fermín52/external340626 yOlmo517/external1323 mantienen MCO, sin ejecución de KNOWN_POSITIONS por nombre. Decisiones nuevas permanecen draft hasta gatesdepublicación. [DDD]
- [ ] Proteger asignaciones aceptadas frente a upsert_player/enrichment/repair; conservar raw y candidatos sin sobrescribir. Pruebas incluyen fuente TM/manual, 4-3-3 CM y Midfielder, no solo display; desactivar endpoints repair mutadores.
- [ ] Capturar cada alineación ya recibida antes del TTL e implementar fetch directo en backend sin SSH para tarea de faltantes; status/headers/caps/checkpoint y cuota compartida; hook en ingesta y tarea Celery no dependientes de visitas web. No tocar puntos en este despliegue.
- [ ] Reconciliar calendario paginado del proveedor por competición/temporada y ambos XI por fixture; ledger distingue completo/parcial/no cobertura y titular/suplente sin inventar minutos. Publicar reporte de alcance inicial y cola reanudable.

Gate 1: integración real contra PostgreSQL/worker en clon, baseline de scores/config intacto, recuperación tras crash idempotente, cuota/lease correctos y pruebas de preservación MCO. Desplegar migración compatible y adquisición con position_publication_enabled=false; verificación en producción es de evidencia durable y decisiones preservadas, no de puntos nuevos. La deuda de cobertura global del70 % se registra y se trabaja en paralelo; no llamar a esto aprobación del gate final de publicación numérica.

### 2. Posición habitual aceptada y evidencia adicional

- [ ] Implementar assertion_kind y política de puente semántico: starting_slot no equivale a habitual_football_role; evidencia específica/curada porID/periodo, primarias/secundarias/lados y decisiones auditables reutilizan longitudinal.py. [DDD]
- [ ] Incorporar perfiles específicos existentes/decisiones documentadas para MC/MCO y otros ambiguos con identidad validada; conservar periodos/referencias; fuentescoarse no degradan y contraaceptada solo abren discrepancia. Resolver cola empezando por alcance activo, sin whitelist de jugadores ni contratar proveedor nuevo por defecto.

Gate 2: muestra contrastada de≥100jugadores y cada plantilla habilitada, con nuevos/legacy/polivalentes/clubselección; casos sin prueba quedan explícitos. Fermín/OlmoMCO,80/20MC/LAT, lados y contradicciones preservados. Ningún nombre ni mayoría de 4-3-3 CM cambia habitual automáticamente.

### 3. Resolver único en lecturas y scoring, primero shadow

- [ ] Implementar snapshots/resolución por fecha/fixture/equipo y proyecciónSQL compartida; integrar ranking,count/paginación,ficha,compare,torneos,Inicio,desglose y DTOs/API/cliente nullable; eliminar nombreoverrides solo tras paridad porID.
- [ ] En modo shadow comparar contrato/etiquetas/filtros/totales con baseline, registrar discrepancias preexistentes y conservar resultados aceptados; scoring/ingesta usan resolución temporal protegida, sin recalcular históricos por perfil actual.

Gate 3: pruebas HTTP y repos con DB muestran misma revisión en listado/count/ficha/snapshot; LAT/MCO sin postfiltrado ni huecos; fixture pasado mantiene rol aceptado del periodo. No activar una etiqueta con impacto numérico dejando sus puntos antiguos.

### 4. Paridad y simulación por actuación con reglas idénticas

- [ ] Extraer operación pura del motor actual y capturar raws/config/motor hash; baseline replay usa la posición efectivamente persistida en cada evento, no Player.position actual. Comparar eventos, STATS, bonos y rollups con redondeo DB y explicar cualquier deriva antes de simular cambios.
- [ ] Simular nuevas posiciones aceptadas porfecha/contexto y cerrar dependencias de todos los afectados; reporte before/afterporfixture/jugador/competición/scope/rank/líderes con base/factores/bonos. Incluir caso realMC↔DEL deCamello sin extrapolar un porcentaje de gol al total.

Gate 4: paridad exacta del baseline o causa remediada/preservada explícitamente para alcance pendiente; configuración/rules_version iguales y diferencias solo posicionales/dependencias. Aprobar manifiesto/hash por política autorizada o revisión de excepción, sin llamar al execute(force_recalculate)mutador para«simular».

### 5. Publicación reversible y operación completa

- [ ] Implementar CorrectionBatch/journal pre/postimages y commits conjuntos de asignaciones/snapshots/scores/bonos/rollups; hacer ingesta, repair, re-score, bonos y honores participar del mismo lock DB compartido/exclusivo y CAS de conjuntos/inputs. [DDD]
- [ ] Probar en clon failpoint a mitad, reintento, escrituras concurrentes, restore de backup y compensación; ninguna mezcla label/puntos/epoch y ningúnhistorical fuera delperiodo cambia.
- [ ] Completar suites/lint/imports requeridos y pruebas significativas hasta cumplir cobertura≥80 %; construir release limitado a este alcance y confirmar migraciones/código realmente presentes en imagen (backend ejecuta imagen en /code, sin bind automático delworkspace).
- [ ] Desplegar con flags acquisition_enabled/position_shadow_read/position_publication_enabled/automatic_refresh_enabled, activar cohortes 10/25/50/100 % elegibles cuando pasen gates, verificar tras cada commit y dos ciclos de operación; revertir lote ante inconsistencia preservando journal.
- [ ] Activar renovación automática y recuperación de faltantes con cuota/presupuesto/alertas; garantizar resultado o razón/next_action para 100 % de IDs. Documentar fuentes/alcances que siguen pendientes sin llamarlos corregidos ni detener trabajos seguros.

Gate final: backuprestaurable,paridad,participacióndetodos escritores,rollback,API/UI y pruebas exigidas; reporte de evidencia aceptada,cambiosnuméricospublicados,catálogopendiente,calls/costes y ciclos observados. Si un gate falla, mantener flagdepublicaciónoff en esealcance, corregir y repetir; la autorizaciónpersistente cubre continuar la implementación hasta culminar. No declarar deploy ni recálculo si no ocurrió.

Archivos mínimos inmediatos: migración0052 y modelos/reposdealineaciones/evidencia/asignación, portsactuales, ingest_competition/provider/fixture_detail_repository, enrich_position_repository, tareas y celery_app.py, core/dependencies.py y tests/runbook. Después completar resolución/journal/API sobre los mismos módulos; no crear ports duplicados ni otra arquitectura. La sección«Archivos a crear»posterior es inventario histórico: value_objects/services/longitudinal ya existen y se **extienden**, y player_positions_ports.py queda sustituido por domain/player_positions/ports.py.

## Hito ejecutado: clasificador y simulación de solo lectura

Alcance acordado antes de implementar: interpretar nuestras alineaciones existentes y medir discrepancias,
sin cambiar posiciones, fórmulas, puntos ni publicación. DDD volvió a revisar este límite y la implementación.
Las casillas posteriores describen el sistema completo y no se dan por cumplidas parcialmente.

- [x] Consultar DDD y las skills backend sfa-use-case/sfa-repository/sfa-test; baseline: 661 tests pasan.
- [x] Implementar VO inmutables, 12 plantillas, rol/lado/candidatos/calidad y proyección SFA versionados.
- [x] Rechazar identidades, grids, porteros, equipos y contratos inconsistentes, sin default MC.
- [x] Agregar soporte por contexto y fixture único, denominadores desconocidos y soporte conjunto rol/lado.
- [x] Capturar catálogo y caché mediante SQL READ ONLY y Redis SCAN/GET, sin proveedor ni escritura remota.
- [x] Implementar use case async, port, Fake completo, fuente offline, factory y CLI reproducible.
- [x] Conservar seis XI reales de tres partidos como regresión; cinco interpretables y 5-4-1 excluido.
- [x] Ejecutar censo offline de 13.180 jugadores y generar JSON, CSV de catálogo/observaciones y resumen.
- [x] Corregir hallazgos DDD sobre duplicados, pertenencia a ambos equipos y combinación ficticia de rol/lado.
- [x] Verificar 744 tests (83 nuevos); cobertura del código nuevo en src 90,91 %, núcleo/use case 100 %.
- [x] Verificar lint e imports de archivos nuevos sin errores y documentar deuda global ajena al hito.
- [ ] Alcanzar cobertura global ≥80 %: suite actual 69 %, requisito global todavía incumplido.
- [ ] Validar exactitud deportiva en muestra independiente ≥100 jugadores y todas las plantillas.
- [ ] Implementar conservación continua de alineaciones e inventario fiable de titularidades.
- [ ] Implementar perfiles verificados, migraciones, scheduler, integración de lectura y publicación del resto del plan.

Resultado: 46 jugadores con evidencia utilizable, 55 observaciones, 26 discrepancias de casilla sobre 21 jugadores.
Ningún contexto es publicable: faltan denominadores fiables y evidencia suficiente. No se recalcó ningún punto.
Evidencia y comandos: `docs/runbooks/player-position-simulation.md`; informe local:
`output/audits/positions-2026-10-18/simulation/position-summary.md` (desde la raíz del repositorio).

Resultado requerido: mantener automáticamente posiciones por ID/periodo/contexto de todo el catálogo mediante bootstrap reanudable y refresh incremental. La revisión humana atiende excepciones; los nombres conocidos son regresiones y no una whitelist. Cumplir las etapas operativas y métricas globales del decisions.md antes de afirmar que la solución está completa.

## Hito siguiente ejecutable: recuperación acotada de alineaciones

Esta sección delimita el incremento implementable ahora, sin exigir el resto del sistema global. Reutiliza el hito cache-only ya existente; no publica posiciones, recalcula puntos, despliega, escribe SQL/Redis ni crea scheduler/migraciones. El proveedor existente solo se consulta mediante GET acotados y la evidencia durable se guarda localmente.

- [x] Registrar baseline del hito actual y ejecutar tests existentes antes de escribir nuevos; preservar snapshot original y todos los cambios ajenos.
- [x] Añadir `RecoverMissingLineupsUseCase` y ports/DTOs simples en `domain/player_positions/ports.py`; Fakes completos prueban selección, presupuesto, reanudación y cero operaciones de publicación/scoring.
- [x] Añadir LineupEvidenceProvider status()/fetch_lineups(fixture_id) con adaptador SSH HTTP acotado y archivo local content-addressed; credencial permanece en VPS y factories solo en core/dependencies.py, sin deploy/router/Celery/modelo DB.
- [x] Crear CLI separado de recuperación con snapshot/season/team_external_id/output; manifiesto previo selecciona hasta10 fixtures conocidos FT/AET/PEN más recientes faltantes de un equipo, sin filtros por nombre.
- [x] Capturar `/status` y headers por respuesta: cap11 intentos=1status+10lineups, reserva diaria100, margen por minuto y concurrencia1; cuota desconocida/agota margen termina sin seguir solicitando.
- [x] Pedir únicamente fixtures/lineups por ID, concurrencia1; tests confirman ausencia de llamadas a fixture detail/statistics/events y a repositorios que escriben Redis.
- [x] Persistir payload bruto/versionado+SHA y metadatos redacted localmente mediante escritura atómica; classify cache ausente/expirada demostrada/empty/error/esquema no soportado sin atribuir ingesta fallida sin evidencia.
- [x] Probar reanudación idempotente sin retries automáticos: cualquier HTTP/API error/429/timeout detiene,200vacío se conserva como missing; responses repetidas no aumentan soporte y la reanudación no consume GET para respuestas ya conservadas.
- [x] Derivar recovered-snapshot compatible sin modificar original; mantener denominador de titularidades unknown salvo prueba real, preservar contradicciones/versiones sin elegir por conveniencia.
- [x] Separar acquisition(status/lineup/errores/fecha/SHA) del replay(provider_calls0); mode offline-enriched-candidate-simulation y resumen no afirman que toda la adquisición fue cache-only.
- [x] Repetir auditor offline y emitir consumo/evidencia/roles/lados/soporte/exclusiones antes-después; no comparar ni alterar puntos y no declarar asignaciones publicables por tener más fixtures.
- [x] Ejecutar piloto autorizado genérico team_external_id529/season2026 con diez faltantes del snapshot y1570413 ya conservado: no pedir ese fixture otra vez; conservar localmente y comprobar segunda ejecución sin GET de respuestas archivadas. Acceso en VPS solo HTTP read-only/redacted sin archivos remotos/despliegue.
- [x] Adjuntar verificación tests/lint del incremento y resumen de fixtures recuperados/no intentados, hash original idéntico y ausencia de writes SQL/Redis/puntuación; documentar cualquier bloqueo real sin pedir permisos rutinarios para GET ya autorizados.

Archivos de este incremento: nuevo `application/use_cases/recover_missing_lineups.py`, adaptadores HTTP/local bajo infrastructure, `scripts/recover_position_lineups.py` y tests de use case/adaptadores; modificar ports existentes, core/dependencies.py y runbook de simulación. No es requisito crear los archivos pendientes del sistema completo que figuran abajo. El use case adicional es específico del hito; no modifica los diez use cases globales ya planificados.

Resultado ejecutado: diez fixtures recuperados, un status, cero errores; dos reanudaciones con cero HTTP. Espart pasa de una a siete observaciones FB/LEFT/LAT. Corpus ampliado a 114 jugadores y 231 slots; cobertura de titularidades desconocida y cero contextos publicables. 39 pruebas nuevas y 783 tests pasan; cobertura global 70 % todav?a inferior al objetivo 80 %. Revisi?n del arquitecto cerrada, incluidos lock exclusivo y parciales compatibles/contradictorios.

## Extensión ejecutada: preview longitudinal de posiciones

Implementada y ejecutada localmente el 2026-10-18; no activa autoaceptación/publicación. Reutiliza snapshots locales, intérprete, agregador y CLI de auditoría, sin nuevas llamadas API, tablas o scheduler. El resto del sistema continuo sigue pendiente.

- [x] Extender DTOs frozen y agregación pura con histogramas SFA/rol/(rol,lado), principal y secundarias. 8 MC + 2 LAT conserva 80/20; 4 DM + 4 CM + 2 FB no inventa CM 80 %. [DDD]
- [x] Secundarias con ≥2 fixtures y ≥20 % del mismo N; UNKNOWN conserva su denominador y los gates base ≥3 / 2⁄3 / 60 % permanecen versionados.
- [x] Lado condicionado al rol; ED/EI, centrales mixtos y 8 CM derecha + 2 FB izquierda conservan pares reales y distinguen falta de predominio de falta de datos. [DDD]
- [x] Cortes reproducibles de temporada y recientes: diez titularidades observadas/conocidas en 180 días, seleccionadas antes de excluir inválidas; cobertura desconocida explícita en el corpus actual.
- [x] Propuestas cronológicas: buffer ocho, mínimo seis válidas, ≥75 %, margen ≥20 puntos y dos fixtures distintos. Sin overwrite ni recálculo; un XI inválido no refresca evidencia antigua. [DDD]
- [x] PlayerPositionTimeline inmutable con update/reemplazo explícito e historial superseded; orden de descarga y metadatos no añaden votos, contradicciones se excluyen, contexto no se mezcla.
- [x] Reporte JSON, Markdown y CSV con dos ventanas, distribuciones, pares, cobertura, frescura, propuestas, baseline efectivo y titular/suplente sin herencia de rol.
- [x] Replay offline y escenarios sintéticos; hashes idénticos de las dos entradas y de JSON/Markdown/CSV al repetir. Sin API, publicación ni escritura de puntos.

Archivos previstos: value_objects.py/services.py del contexto player_positions, application/use_cases/audit_player_positions.py, scripts/audit_player_positions.py y sus tests/runbook existentes. No crear un contexto nuevo ni implementar ahora características futuras desconocidas.

El módulo puro nuevo es `domain/player_positions/longitudinal.py`, separado del intérprete geométrico según revisión DDD. Baseline 783 tests; después 823 pasan (40 nuevos), dominio/use case 99 %, DTOs 100 %. Cobertura global 70 %, todavía inferior al objetivo 80 %. Lint/imports del incremento pasan.

Ejecución real: 184 contextos con titularidades conservadas, 19 principales recientes observadas, nueve candidatos distintos de la etiqueta efectiva legacy y cero propuestas estabilizadas de cambio. Espart 7/7 FB/LEFT/LAT; Camello 3/3 CF/DEL. Fermín Liga 4 CM + 2 AM produce candidato MC 2/3 y MCO secundaria 1/3, preservando MCO efectivo y marcando discrepancia. Nada se publica. Artefactos: `output/audits/positions-2026-10-18/longitudinal-preview/` desde raíz; comandos y límites en el runbook existente.

## Archivos a crear

- [ ] `src/sfa/domain/player_positions/entities.py` — PositionEvidence, PlayerPositionProfile y PositionCorrectionBatch con invariantes documentadas. [DDD]
- [ ] `src/sfa/domain/player_positions/value_objects.py` — periodo/contexto, granularidad, TacticalRole/TacticalSide/TacticalResolution, EvidenceCompatibility, revisión/snapshot y CorrectionImage inmutables. [DDD]
- [ ] `src/sfa/domain/player_positions/services.py` — PositionResolver, LineupPositionInterpreter y agregación temporal puros/deterministas, sin nuevo aggregate. [DDD]
- [ ] `src/sfa/domain/player_positions_ports.py` — ports de perfiles/correcciones/proyección/fuente/mantenimiento y DTOs frozen; sin imports de infraestructura.
- [ ] `src/sfa/infrastructure/models/player_positions/models.py` — cinco tablas de evidencia/publicación, estado operativo de refresh y constraints del decisions.md.
- [ ] `migrations/0052_evidence_based_player_positions.sql` — expansión y backfill legacy; reservar siguiente número libre al implementar, sin colisionar con migraciones nuevas ajenas.
- [ ] `src/sfa/infrastructure/repositories/player_position_repository.py` — evidencia/asignaciones y resolución materializada conforme al port completo.
- [ ] `src/sfa/infrastructure/repositories/position_correction_repository.py` — estados, imágenes, CAS, bloqueo y journal append-only.
- [ ] `src/sfa/infrastructure/repositories/position_correction_projection.py` — relación publicada reusable e informes por alcance.
- [ ] `src/sfa/application/use_cases/record_position_evidence.py` — ingesta de evidencia sin publicación implícita de cambios existentes.
- [ ] `src/sfa/application/use_cases/review_position_assignment.py` — aceptación documentada o conflicto; sin SQL.
- [ ] `src/sfa/application/use_cases/simulate_position_correction.py` — cálculo reproducible y reporte sin cambiar publicación.
- [ ] `src/sfa/application/use_cases/publish_position_correction.py` — aplicar exclusivamente informe aprobado y vigente.
- [ ] `src/sfa/application/use_cases/revert_position_correction.py` — lote compensatorio, CAS de postimages y restauración conjunta.
- [ ] `src/sfa/application/use_cases/get_position_correction.py` — consulta del lote/impacto/journal por DTOs.
- [ ] `src/sfa/application/use_cases/get_player_position_history.py` — trazabilidad temporal de evidencias y cambios.
- [ ] `src/sfa/application/use_cases/get_player_position_coverage.py` — reporte de cobertura por ID/alcance con denominadores, sin búsquedas externas ni mutaciones.
- [ ] `src/sfa/application/use_cases/schedule_player_position_refresh.py` y `refresh_player_positions.py` — dispatcher y worker por lotes, policy decisions y reutilización del flujo transaccional existente.
- [ ] `src/sfa/infrastructure/repositories/position_maintenance_repository.py` — inventario keyset/checkpoint, leases, vencimientos, idempotencia y excepciones operativas sin otro aggregate.
- [ ] `src/sfa/api/v1/position_corrections.py`, `schemas/position_corrections.py` y `http/position_corrections.http` — admin autenticado y casos HTTP completos.
- [ ] `src/sfa/tasks/position_correction_tasks.py` — simulación, dispatcher periódico y worker con estado durable e imports tardíos.
- [ ] `tests/domain/test_player_position_resolution.py` — identidad, temporalidad, precedencia y conflictos.
- [ ] `tests/use_cases/test_position_corrections.py` — Fakes completos para los diez use cases, mantenimiento global, cobertura y fallos/idempotencia.
- [ ] `tests/repositories/test_position_corrections.py` — atomicidad, constraints, CAS y concurrencia con PostgreSQL aislado.
- [ ] `docs/runbooks/player-position-corrections.md` — backup, manifiesto, simulación, revisión, publicación, invalidación y reversión.

## Archivos a modificar

- [ ] `domain/ingestion_ports.py`, `scoring_ports.py`, `transfermarkt_ports.py`, `ports.py` — raw nullable, snapshot fijo y metadatos públicos sin depender de ORM.
- [ ] `domain/position_mapping.py` y `domain/player_position_overrides.py` — retirar resolución runtime por nombres/default MC tras migración explícita a candidatos legacy.
- [ ] `domain/scoring/entities.py` y cálculo versionado — snapshot de posición sin cambiar fórmula, grupos ni pesos.
- [ ] `infrastructure/providers/api_football.py`, `transfermarkt_scraper.py` — conservar ausencia/texto original/familias; no enriquecer precisión ficticia.
- [ ] Adaptador de posiciones y `infrastructure/repositories/fixture_detail_repository.py` — reutilizar DTOs de alineación y preservar evidencia antes de caducar cache; exponer lectura cache-only que nunca invoque fallback HTTP en dry-run.
- [ ] `infrastructure/models/players/models.py` — nullable/caché y procedencia legacy explícita; deja de ser fuente de puntuación temporal.
- [ ] `infrastructure/models/__init__.py` y exports de repositorios — registrar nuevos modelos/repositorios conforme al patrón actual.
- [ ] `infrastructure/repositories/ingestion_repository.py`, `enrich_position_repository.py` — evidencia y protección de revisiones en vez de escritura ciega.
- [ ] `infrastructure/repositories/player_event_score_repository.py`, `sfa_score_repository.py`, `player_repository.py`, `player_event_repository.py` — resolver por snapshots publicados y proyección común SQL.
- [ ] Repositorios de torneos, comparación y ranking explanations — eliminar cualquier lectura temporal alternativa de Player.position/nombres detectada en inventario.
- [ ] `application/use_cases/ingest_competition.py`, `enrich_player_positions.py`, `fix_player_positions.py` — preservar crudos; tomar posición aceptada; retirar repair mutador.
- [ ] `application/use_cases/calculate_scores_for_rules_version.py`, `calculate_competition_scores.py`, `recalculate_scores.py`, `backfill_fixture_scores.py`, `run_full_recalculation.py` — resolver y bloquear de forma coherente; no recalcular contra etiqueta global.
- [ ] `core/dependencies.py` — factories y composición de todos los ports/use cases; único wiring.
- [ ] `api/v1/admin.py`, schemas públicos ranking/players/compare/tournaments y `main.py` — 410 repairs, nuevo router admin y contrato nullable por etapas.
- [ ] Tareas de ingesta/enriquecimiento/re-score/rebuild existentes — mismo bloqueo de publicación y estados de cobertura.
- [ ] Config/settings y Celery Beat existentes — contratos versionados, dispatcher/TTL/presupuesto/retry/concurrencia, habilitación de autoaceptación por cohorte y métricas.
- [ ] `frontend/src/types/index.ts` y consumidores de position — tolerar null/legacy/pending antes de emisión del nuevo contrato; sin rediseñar la interfaz.
- [ ] `frontend/src/components/HomeDiscoverSections.tsx` — eliminar escaneo de páginas workaround solo después de demostrar filtro/paginación correctos en backend.
- [ ] Tests existentes de ingesta, posiciones, reglas, ranking/scopes, torneos y compare — ajustar a evidencia/snapshots, conservando casos de equipo 0028/0029/0055.

## Checklist de implementación

### A. Preparación y contrato

- [ ] Leer decisiones y este plan completos; registrar revisión de código vigente y todos los cambios ajenos que deben preservarse.
- [ ] Ejecutar `pytest tests/` antes de escribir tests nuevos; registrar fallos previos, entorno y cobertura inicial sin atribuirlos al cambio.
- [ ] Inventariar todos los escritores y lectores de posición/puntos, incluyendo tareas live, backfills, targeted reingest y dependencias de bonos/honores; criterio: ningún escritor queda sin política de bloqueo.
- [ ] Inventariar por ID/contexto posición almacenada, efectiva de overrides/filtros y snapshots utilizados por scoring; distinguir discrepancias preexistentes y preservar los tres valores reales.
- [ ] Consultar DDD-Designer para validar los aggregates/VOs contra esta decisión de journal, sin clonar ScoringRulesVersion. [DDD]
- [ ] Congelar contrato de metadatos y migración nullable; prueba de cliente antiguo/nuevo antes de habilitar respuesta nullable.
- [ ] Validar PositionSourceContract contra muestra y permiso real: primaria/secundarias, granularidad, IDs/crosswalk, vigencia/cobertura/licencia/límites; fuente no capaz no se habilita para autoaceptación. [DDD]
- [ ] Definir política automática pura versionada para nuevos, legacy, compatibles y nuevos contextos; tabla de decisión del spec cubierta sin nombres especiales y sin verificador humano obligatorio por entrada. [DDD]
- [ ] Medir primero alineaciones existentes/cache/payloads sin tráfico externo; inventariar cobertura por fixture/equipo/formación/ID y distinguir disponible en API de conservado duraderamente, antes de evaluar otro feed.

### B. Dominio y persistencia

- [ ] Implementar periodo/contexto y resolución; pruebas de intervalos solapados, fecha límite exclusiva, club/selección y empates conflictivos. [DDD]
- [ ] Modelar granularidad y EvidenceCompatibility por taxonomía/campo/versión: familia compatible no asigna rol y taxonomía desconocida devuelve indeterminate. [DDD]
- [ ] Modelar observación de rol inicial y soporte temporal como DTOs/VO del contexto existente; invariantes de fixtures únicos, denominadores fiables y separación de rol inicial/representativo/minutos. [DDD]
- [ ] Implementar taxonomía táctica/proyección exhaustiva versionada y labels role+side: LD/LI distintos conservan LAT, centrales lateralizados siguen DC, WM/SS no fuerzan grupo y proyección común mantiene ambigüedad explícita. [DDD]
- [ ] Separar resolución, verificación, revisión candidata y cobertura; probar asignación verified con candidato conflictivo abierto sin sustituir publicación. [DDD]
- [ ] Implementar revisión/evidencia append-only y supersesión explícita; modificar nombre no cambia identidad ni asignación. [DDD]
- [ ] Implementar aggregate CorrectionBatch, imágenes canónicas y transiciones; published no admite edición ni borrado y reversión crea otro lote. [DDD]
- [ ] Crear migración expand nullable/indexada; ejecutar ida y restauración en base aislada sin perder filas ni alterar puntos.
- [ ] Crear baseline legacy exacto sin payload inventado; comparar conteos y hashes de scores antes/después de migración: deben coincidir.
- [ ] Capturar snapshot legacy desde PlayerEventScore.position y detectar discrepancia con caché de jugador sin corregirla automáticamente.
- [ ] Materializar resoluciones efectivas antes de retirar overrides; test DB EXT/efectivo MCO en Fermín y DB DC/efectivo MC en Zubimendi conserva lectura/filtros/puntos e identifica legacy_position_score_mismatch.
- [ ] Implementar ports/repos completos y bloqueo canónico compartido; pruebas de constraints y dos publicaciones concurrentes no producen estado mixto.

### C. Ingesta, scoring y lectura

- [ ] Quitar fallback Midfielder/MC y mappings de familias ambiguas; null/valor desconocido producen incidencia y conservan raw.
- [ ] Migrar registries por IDs: preservar asignaciones efectivas ya validadas con referencias reales, capturar las no documentadas como baseline legacy revisable y retirar nombres runtime solo tras paridad; no blindar Ceballos EXT ni Quinten LAT por origen manual.
- [ ] Retirar inferencias automáticas DC/GK como mutadores; ambos endpoints repair devuelven 410 y ninguna tarea bypass puede ejecutarlos.
- [ ] Hacer enrichment no destructivo y proteger toda asignación aceptada cualquiera fuente; identidad verificada sola no autoriza overwrite y match dudoso queda candidato.
- [ ] Probar Fermín MCO ante Midfielder, null, taxonomía desconocida y reingesta/enrichment: mantiene MCO; una primaria MC específica comparable solo abre revisión, sin alterar puntos.
- [ ] Probar matrices completas de familias y roles híbridos, incluyendo EXT dependiente de taxonomía y Forward que no prueba DEL; conjuntos posibles no fuerzan una primaria.
- [ ] Implementar plantillas genéricas formation+row+column del esquema validado: mismo 4:2→MCO en 4-2-3-1 y →DEL en 4-3-3, con IDs arbitrarios, espejo local/visitante y sin leer players.position/CSS/dorsal.
- [ ] Implementar árbol de líneas/slots de las12 formaciones del decisions.md con variantes explícitas: banda de medio no implica W/WB, trío CM no crea AM, y falso nueve/SS no se derivan de grid; aliases/offsets sin contrato quedan indeterminados.
- [ ] Versionar orientación APIfootball contra ejemplos oficiales/fixtures retenidos: columna1izquierda/Nderecha solo con esquema validado; otro esquema devuelve sideUNKNOWN sin perder rol/LAT conocido. Testar LD/LI contra evidencia independiente, no nombres hardcoded en producción.
- [ ] Validar XI completo, casillas, IDs/equipo/orientación; nulos, suplentes, duplicados, incoherencia, plantilla no soportada y denominador desconocido devuelven indeterminate, sin MC ni herencia de casilla del sustituido.
- [ ] Agregar varios fixtures por periodo/contexto: piloto ≥3 observaciones, soporte ≥2/3 y cobertura ≥60 % de titularidades fiables más ingesta conocida; tests de límites enteros/duplicados/polivalencia, sin convertir umbrales en certeza ni ampliar al pasado.
- [ ] Agregar role y side por separado con soporte/cobertura, incluyendo ladosunknown en denominador; primaria/secundarias detalladas no atribuyen minutos. Publicación de solo detalle compatible no recalcula puntos, lado contradictorio sí abre revisión.
- [ ] Probar fuente específica incompatible en mismo periodo frente a otra selección/periodo: solo la primera abre revisión comparable y ninguna sobreescribe automáticamente.
- [ ] Implementar evidencia mínima y aceptación automática trazable para contratos habilitados; corroboración/evaluación humana solo en excepciones, sin asumir que dos redistribuidores son independientes.
- [ ] Preservar raw events antes de exclusiones de scoring; desconocido o GK no provoca pérdida de evidencia del partido.
- [ ] Extraer operación de cálculo pura reutilizable entre simulación y scoring; golden tests reproducen los mismos resultados con inputs/config idénticos.
- [ ] Hacer todos los recálculos consumir snapshot de fixture/revisión; calcular grupo por mapping actual, sin crear pesos nuevos.
- [ ] Registrar basis=accepted_period_role para clasificación habitual sustentada; rol inicial aislado no cambia scoring de todo el partido ni de toda la temporada, y ningún minuto se atribuye a una posición táctica no observada.
- [ ] Implementar unknown/pending sin cero artificial; probar mantenimiento de último total y cobertura incompleta, sin publicación parcial del jugador.
- [ ] Implementar proyección publicada común antes de filtros/count/LIMIT/OFFSET; probar LAT/MCO con más de una página, huecos y desempates.
- [ ] Verificar ranking, ficha, compare, torneos, Inicio y desglose usan misma revisión; varias posiciones históricas no se sustituyen por la representativa.
- [ ] Implementar cache por revisión y estado durable de invalidación; una invalidación fallida no sirve datos de otra publicación.
- [ ] Actualizar clientes para mostrar posición pendiente/cobertura; habilitar null solo tras comprobación de todos los consumidores.

### D. Simulación y publicación controlada

- [ ] Implementar diez use cases con Fakes completos y tests anyio; errores traducidos únicamente en router.
- [ ] Registrar factories, router admin, autorización existente, schemas y archivo .http con happy path, 403/404/409/422.
- [ ] Agregar GET admin/player-position-coverage con filtros, paginación/exportación acotada y tests sin llamadas externas.
- [ ] Generar censo del 100 % con cursor/watermark y reconciliación frente a players, incluyendo altas durante el barrido; reporte distingue activos, actuales inactivos, historia, desconocidos sin ranking y no appearances.
- [ ] Implementar bootstrap reanudable y refresh incremental por alta, observación, equipo/contexto y TTL; crash/retry/reingesta idéntica no duplican evidencia, decisiones ni puntos.
- [ ] Implementar dispatcher/leases, token bucket compartido, presupuesto diario, cache, backoff/Retry-After y pausa de contrato inválido; tests con reloj/fuente fake verifican no starvation ni loops sin progreso.
- [ ] Implementar autoaceptación nuevos/legacy elegibles y no-op compatibles usando lote existente con actor policy y gates; solo excepciones deportivas/identidad/deriva requieren revisor.
- [ ] Reconciliar por jugador apariciones requeridas/verificadas/legacy/pendientes, porcentaje con denominador real y estados independientes; una verificación actual no cubre históricos sin evidencia temporal.
- [ ] Ejecutar shadow sin mutaciones sobre cohorte representativa de al menos 100 IDs, varias ligas y todos los tipos de estado/contexto; incluir regresiones nominadas como parte, no como selección exhaustiva.
- [ ] Ejecutar baseline cache-only y validación retenida de plantillas con nuestras alineaciones antes de comprar/feed adicional; informe de soporte/cobertura/exclusiones/contradicciones y hashes de posiciones/puntos sin cambio.
- [ ] Documentar evaluación de granularidad/identidad/licencia/cobertura de terceros solo si se necesita fuente adicional; ninguna contratación, integración o scraping masivo entra por defecto en el alcance.
- [ ] Implementar tarea de simulación y resultados durables; ningún endpoint de simulate llama a recálculo mutador contra filas publicadas.
- [ ] Generar manifiestos de la cohorte desde la política por IDs arbitrarios, con contratos/evidencias/periodos; Camello solo es una regresión, ningún nombre concede elegibilidad.
- [ ] Capturar inputs/config/motor/preimages; reproducir baseline almacenado antes de aceptar comparativa. Si difiere, lote bloqueado con diagnóstico.
- [ ] Expandir dependencias hasta cierre de scores, bonos, honores derivados y rollups; informe incluye compañeros y filas insertadas/eliminadas.
- [ ] Obtener antes/después por evento, fixture, jugador, competición y scope, con líderes/rankings/cobertura; toda variación tiene causa posicional comprobable.
- [ ] Implementar aprobación ligada a hash exacto; input/config/estado cambiado provoca stale/409, sin escritura parcial.
- [ ] Probar publicación atómica e idempotencia; fallo inducido entre posición y puntos deja ambos exactamente como antes.
- [ ] Probar concurrencia con reingesta/rebuild, incluyendo preservación de IDs de eventos auditados; ningún proceso pisa la revisión aceptada.
- [ ] Probar compensación completa y CAS de postimages; una corrección posterior impide restauración ciega.
- [ ] Restaurar backup en clon y medir ventana del lote piloto; documentar límites operativos y criterios de detenerse.
- [ ] Habilitar rollout futuro por cohortes 10/25/50/100 % elegibles con checkpoint y dos ciclos estables por etapa; gates del decisions.md exigen reconciliación/invariantes/presupuesto/capacidad real de fuente antes de avanzar.
- [ ] Verificar catálogo entero con resultado o motivo/next_action por ID/contexto, y métricas de autoaceptación/excepciones; ninguna deuda se oculta excluyendo casos pendientes ni transfiriendo toda revisión al usuario.
- [ ] Registrar hashes antes/después, revisión, operador, alcance y rollback probado; históricos fuera del periodo permanecen iguales.

### E. Verificación final

- [ ] `pytest tests/` pasa con cobertura global ≥80 %, o documentar y resolver bloqueos previos según contrato del proyecto.
- [ ] `flake8 src/ tests/` sin errores y `isort --check-only src/ tests/` sin errores.
- [ ] Compilación frontend y comprobación ranking/ficha/Inicio con null/legacy/pending/resolved, sin cambios visuales ajenos.
- [ ] Ensayo de ambos endpoints antiguos, tareas, nueva API admin, cache y regresiones 0028/0029/0055; no se pierde equipo histórico.
- [ ] Comparar reglas/config y datos no posicionales del piloto byte a byte; diferencias fuera del cierre aprobado bloquean release.
- [ ] Tests de propiedades sobre IDs/nombres arbitrarios: determinismo temporal, idempotencia, coarse no degrada específico, cambios de orden de evidencia no alteran resultado y homónimos no se unen; dataset sintético recorre bootstrap→incremental→UI/filtros/snapshot de scoring bajo concurrencia.
- [ ] Tests paramétricos/generativos recorren todas las casillas y plantillas:11IDs únicos/filas exactas/GK, duplicados/nulos/offsets, permutación de arrays y cambiohomeaway/rotación visual conservan role+side; misma grid distintaformation cambia rol cuando procede y sideUNKNOWN nunca se etiqueta LD/LI.
- [ ] Métricas/alertas operativas verificadas: cobertura por estado/contexto, freshness, atraso, límites y coste separados de exactitud muestreada; mismatch de revisión, downgrade o taxonomía desconocida pausa autopublicación.
- [ ] Adjuntar evidencias de simulación, atomicidad, concurrencia, backup/restauración y reversión al runbook.

## Verificación end-to-end

1. En clon con fixture/evento Camello 1844535, baseline rules_version_id=4 conserva 720 y 1015,64. Simular DEL con mismos inputs muestra base 665 y resultado calculado, no una cifra final prefijada; filas publicadas quedan intactas.
2. Aprobar hash exacto y publicar en clon: filtro DEL incluye a Camello, MC lo excluye, ficha/Inicio/desglose usan la revisión y totales nuevos. Nombre homónimo ajeno permanece igual.
3. Reingestar y enriquecer con Midfielder/ausencia: no cambia la decisión verificada; raw se conserva. Cásseres/Barrios con intercepciones elevadas no se convierten en DC.
4. Sembrar conflicto EXT/MCO, club/selección y nueva posición sin fecha histórica: no se cambia una temporada anterior. Nuevo jugador desconocido no aparece como MC ni con cero fabricado.
5. Recorrer páginas LAT/MCO: concatenación sin duplicados ni pérdidas, total igual al count de la relación filtrada y líder igual al primer resultado; no se escanean páginas para encontrar un rol.
6. Introducir escritura concurrente tras simulación: publicación 409/stale sin mutaciones. Introducir fallo a mitad de transacción: rollback completo. Repetir publicación: idempotente.
7. Compensar el lote: restaurar todos los hashes de preimages sin borrar ninguno de los dos journals; revertir contra datos modificados después debe bloquear.
8. Migrar Fermín desde DB EXT + override MCO + respuesta Midfielder: lectura y filtros siguen en MCO; ni EXT ni MC reaparecen. Preservar score original y reportar cualquier diferencia histórica con el rol efectivo hasta simulación/publicación explícita; repetir Zubimendi DB DC/efectivo MC.
9. Aportar candidato MC específico con mismo contexto/periodo: abre revisión, mantiene MCO/puntos. Otra selección o intervalo no solapado no genera conflicto falso. La categoría amplia no convierte cobertura pendiente en verified.
10. Leer informe de cobertura sobre IDs sin ranking y con posiciones legacy, verificadas y candidatas: totales reconciliados, cero apariciones no significa 100 %, sin llamadas a proveedores ni modificaciones. Un registro manual legacy incorrecto puede corregirse con evidencia; no queda blindado por el origen.
11. Sembrar catálogo sintético con IDs arbitrarios, alta durante barrido, homónimos, nuevos contextos, fuente capaz/coarse y fallos 429/crash: reanudar inventario cubre todos una vez lógicamente; refresco compatible no recalcula; nuevos/legacy específicos se aceptan sin clic humano; excepciones quedan con razón/next_action.
12. Forzar renovación por TTL/cambio de equipo y publicación concurrente con ingesta: evidencia actual no reescribe el pasado, mismo fixture/revisión produce mismo rol en desglose/filtros, CAS impide mezcla y presupuesto/cache/retry mantienen límites. Alterar taxonomía suspende esa fuente y preserva aceptadas.
13. Reproducir fixtures 1570413/1570391/1570399 y permutar nombres/IDs manteniendo formación/grid: obtener candidatos genéricos MCO/DEL/DEL sin circularidad. Local y visitante conservan rol tras reflejar su presentación; formación distinta con grid4:2 produce otro candidato.
14. Retener fixtures de validación, agregar tres observaciones únicas, repetir payload, omitir formación y sustituir titular: soporte/cobertura no se inflan; suplente no hereda rol; desconocidos no puntúan como MC. Evidencia alineación incompatible no sobreescribe una aceptada y dry-run no hace HTTP ni publica puntos.
15. Dry-run cache-only entrega por jugador/fixture role, side, candidatos/quality, plantilla/orientación/proyección y soporte; mostrar LD≠LI con ambosLAT, carrilero≠extremo, CB lateralizadoDC y WMindeterminado. Comparar lateralidad con evidencias retenidas oficiales, no la etiqueta SFA usada como entrada; si falta evidencia de orientación, emitir LAT+sideUNKNOWN sin inventar lado.

## Cierre local priorizado ?2026-10-20

279 jugadores elegibles en los dos tramos, barrera<3 prevalente.5 requestssecuenciales (status+4fixtures) con ventana worker/beat drenada y restaurada, originales/SHA/checkpoints preservados. C?sseres:MCcandidato7/7 sin conflicto tras revisi?n directa1552785.143 pendientes por pocos inicios,75 por evidencia inv?lida/formaci?n sin plantilla,59 por ambig?edad t?ctica,1 intento incierto1556502 sin reintento. No afirmar cobertura global completada. Familia originalgen?rica/unverified, ausencianull, nunca fallbackMC. FixPlayerPositionsUseCase retirado localmente sinSQL. Suite local1027passed/15skip.

Baseline24339scores/8637rollups/1161bonos reproducidoexactamente; escenario offline704jugadores,4057eventos,4entradas/salidas top50. Matriz y CSV completos en output/audits/positions-2026-10-20/. Ning?n c?digo/dato0065 desplegado. Solo0066 pas? aproducci?n.

## Agent Routing Brief

**DDD Designer needed:** yes.

DDD consultado para piloto curado: allowlistfixture es adicional a ID/contexto/intervalo; decisionesactual y retrospectiva separadas, fixture_id histórico y rechazo de lista vacía. El gate poblacional corresponde a automatización global. Conservar paridad/exclusión/CAS/backup/reversión y no convertir slots en90minutos de función habitual. La publicación curada real queda autorizada únicamente tras esos gates.

El hito acotado de recuperar alineaciones no añade invariantes futbolísticas ni nuevos aggregates/VO: reutiliza el modelo/mapper actual y requiere solo DTOs, ports y adaptadores de cuota/HTTP/archivo. No necesita nueva invocación DDD para implementar ese incremento, ni ejecutar la arquitectura global pendiente antes de poder recuperar evidencia.

Ya invocado durante el diseño. Antes de implementar los ítems [DDD], volver a consultar `backend/.claude/agents/DDD-Designer.md`: PositionEvidence, PlayerPositionProfile, PositionCorrectionBatch y sus VO protegen identidad, precisión temporal, conflictos, snapshots y publicación consistente. Architecture-Engineer decide journal independiente de metodología; no implementar la alternativa de clonar ScoringRulesVersion sugerida inicialmente por DDD. No se agregan acciones, grupos ni multiplicadores. Mantener las fronteras hexagonales y no convertir el spec en un repair por nombres.

DDD-Designer volvió a ser consultado al refinar la verificación por jugador: su addendum valida granularidad por taxonomía, compatibilidad distinta de precisión, protección de decisiones específicas aceptadas, estados independientes y cobertura temporal. Implementar las regresiones de Fermín/Zubimendi y no convertir los registries legacy en evidencia verificada ficticia.

Consulta adicional DDD para sistema continuo: no se requieren nuevos aggregates. PositionSourceContract es configuración/DTO inmutable; el resultado automático es decisión de política auditable. Inventario, scheduler, leases, cache y presupuesto pertenecen a operación/adaptadores. La autoaceptación específica sustentada de nuevos/legacy es válida; se conservan asignaciones aceptadas ante candidatas incompatibles y se derivan solo excepciones.

DDD consultado para evidencia de alineaciones: reutilizar PositionEvidence, mapper puro y soporte agregado. Es obligatorio separar rol inicial de posición representativa y scoring, medir denominadores/ingesta y no heredar posiciones a suplentes. Los umbrales 3/2⁄3/60 % son política piloto contrastable, no confianza estadística. No nuevo aggregate ni proveedor requerido para comenzar con datos existentes.

DDD consultado para clasificación táctica/lateralidad universal: nuevos VO mínimos TacticalRole/Side/Resolution, sin aggregate/acciones/pesos adicionales. Conservar detalle y ambigüedad, no invertir la proyección desde LAT/MC, separar cobertura de lado frente a rol y no confundir slot inicial con función avanzada o minutos reales. Las12 plantillas son reglas genéricas versionadas y se habilitan con datos contrastados.

DDD consultado para perfil longitudinal: separar observado/propuesto/aceptado; mantener gatesbase3/2⁄3/60 %, secundarios2/20 % y propuestas con histéresis piloto75 % sobre8observaciones y2fixtures de confirmación. No sumar DM+CM como si fuera CM, no ensamblar rol y lado de marginales distintas y no retroaplicar el perfil actual al scoring. Reutilizar VO/DTO existentes, sin aggregate nuevo.

DDD volvió a validar el camino completo autorizado: evidencia durable, asignaciones aceptadas y snapshots temporales reutilizan los aggregates de este spec. Exige distinguir starting_slot de habitual_football_role, prueba de calendario/ambos XI para cobertura y paridad del motor antes de corrección. El gate decisivo de producción es que todos los escritores participen en exclusión/CAS; el journal por sí solo no garantiza consistencia. No clonar reglas, cambiar pesos ni retroaplicar el perfil actual. Architecture-Engineer prioriza las cinco entregas al principio del plan; se implementan hasta publicación y operación cuando pasen sus gates, no hasta otro preview.

DDD reconsultado para el piloto 2026: curated_fixture_scoring_role solo resuelve historia con fixture/contexto; scope_scoring_classification es categoria SFA representativa del alcance publicada en el batch, no habitual verificado. Referencia actual opcional independiente; v1 no se reinterpreta. La clave incluye jugador/scope/conjunto explicito de competiciones/revision; lecturas y filtros comparten proyeccion del journal y compensacion coherente. No nuevo aggregate; materializaciones reconstruibles.
