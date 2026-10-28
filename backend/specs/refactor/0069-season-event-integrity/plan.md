# Plan: integridad de eventos del periodo 2025/2026

## Estado de entrega

Reparación, recálculo y publicación completados el 28 de octubre de 2026. Véase `runbook.md`, sección Cierre productivo, para resultado, hashes, journals y límites. Suite completa del runtime: 1.253 passed, 43 skipped; cobertura nueva 89,65 %. Replay sin revisiones nuevas; promoción y reversión completas ensayadas en la copia. HTTPS y SQL productivos verifican el corte v4 íntegro, sin eventos elegibles sin puntuar ni descuadres. Las incidencias de proveedor se conservan explícitas en `pending-evidence.csv`.

El checklist siguiente conserva el contrato y las comprobaciones de diseño; el registro de ejecución y las pruebas concretamente realizadas están en el runbook y artefactos, sin afirmar cobertura exhaustiva de todas las combinaciones negativas enumeradas.

La revisión vigente autoriza reparar los datos y recalcular **todo season-2025 con v4 actual**. La reproducción histórica de v3 y cualquier M1override quedan fuera; prevalece esta revisión sobre restricciones de versiones anteriores.

## Archivos a crear

- [ ] `src/sfa/domain/event_integrity.py` y `event_integrity_ports.py`: contratos frozen, identidad/revisión/cobertura y puertos completos, sin dependencias de infraestructura.
- [ ] `src/sfa/application/use_cases/prepare_season_event_integrity.py` y `apply_season_event_integrity.py`: preparación pura respecto a escrituras y aplicación con CAS.
- [ ] `src/sfa/infrastructure/repositories/season_event_integrity_repository.py` y adaptador de journal de archivos: snapshots, diff SQL acotado e imágenes verificadas; sin commits internos.
- [ ] `scripts/reconcile_season_event_integrity.py`: CLI prepare/apply/verify/revert y reanudación, con commit en adaptador de entrada. No HTTP al aplicar.
- [ ] Tests de dominio/use cases con Fakes completos, pruebas PostgreSQL de integración y runbook operativo con artefactos por fixture/componente.

## Archivos a modificar

- [ ] `core/dependencies.py`: factories y composición de adaptadores y callable port del scorer existente (`_score_event` y helper B1); sin importar EventScoringEngine inexistente en main, extracción masiva ni wiring en dominio/use cases.
- [ ] `ingest_competition.py`, `reingest_player.py` y `ingestion_repository.py`: corregir la ruta autorizada de IDs/equipo/asistencias/GK y evitar reemplazo destructivo de fixtures reparados; conservar comportamiento ajeno al scope y explicitar las rutas legacy bloqueadas.
- [ ] Reutilizar CalculateScoresForRulesVersionUseCase y use cases de bonos/honores existentes para el cierre completo v4 de los pares exactos del periodo; archivar y retirar la proyección v3 de ese scope. No endpoint, nueva task, migración ni motor alternativo salvo bloqueo técnico demostrado y documentado antes de ampliar el contrato.

## Checklist de implementación

1. [ ] Documentar baseline del worktree (reportado: 785 passed, 25 skipped), fuente/runtime productivo real y extras que deben preservarse. Resolver scope exacto season-2025 y guardar sus pares; verificar que season-2026 no entra por el Mundial físico 2026.
2. [ ] [DDD] Implementar identidad/revisión/cobertura conforme al dictamen DDD recibido. Criterio: sin fuente completa o correspondencia inequívoca no se genera una operación aplicable; minuto/nombre no son una clave global.
3. [ ] Importar el archivo adquirido secuencialmente sin nuevas llamadas en el replay; ampliar adquisición a todos los fixtures del scope (corte: 2.840), aunque sus conteos coincidan. Validar envelopes, IDs de fixture, hashes y errores de parser; contabilizar por separado consultas de jugadores sin Stats (corte: 123) contra cuota disponible. Producir inventario completo con omisiones, sobreconteos, identidades erróneas y exclusiones GK separadas.
4. [ ] Preparar diff por fixture: insertar faltantes verificadas, corregir sobre el mismo PE.id y retirar únicamente ocurrencias inequívocamente erróneas con dependencias explícitas. Mostrar before/after de actor, equipo, contexto y referencias de todas las versiones. Antes de alterar raw, archivar proyecciones antiguas completas, verificadas y restaurables.
   - [ ] Separar componentes actor/rol con timeline de goles/marcador validado. Contrastar API players fresco y timeline para modificar solo contadores/minutos/apariciones sustentados, preservando campos controvertidos. Clasificar warnings y bloqueos; no retirar IDs no resueltos ni interpretar `[]` como cero sin prueba. Una asistencia conflictiva del mismo gol protege el conjunto e impide duplicarla.
5. [ ] Inventariar v3/v4 y otras versiones encontradas, sus detalles/journals y contextos. Documentar divergencia histórica v3 sin reproducirla ni introducir historical_m1. Verificar backup y exportación completa v3 del periodo; preparar retiro reversible de esa proyección del serving, sin falsificarla como v4 ni dejar rankings parciales v3.
6. [ ] Simular el recálculo completo v4 del scope: todas las acciones elegibles, STATS/B1, rollups, bonos dependientes y ranking; usar configuración v4 actual, posición publicada actual resuelta y contexto temporal existente. Reutilizar UCs existentes. Demostrar invariancia de ELO, reglas, posiciones, Stats/psxg válidos y datos fuera de scope; identificar pendientes reales sin inventar contexto.
7. [ ] Implementar journal durable before/after, fingerprints y recuperación de caídas antes/después del commit; adquirir exclusión try-only, revalidar CAS y verificar las filas reales antes de commit. Criterio: failpoint no deja una unidad parcialmente publicada ni autoriza reaplicar un estado indeterminado.
8. [ ] Implementar reversión CAS exacta sin borrar cambios posteriores y probar idempotencia de apply/replay con la misma fuente. Las retiradas no usan borrado en cascada de versiones no inventariadas.
9. [ ] Corregir preventivamente la ruta de ingestión autorizada: IDs/equipo, asistencia sin nombre, raw de porteros y verificación de completitud; probar que rutas antiguas no destruyen fixtures reparados. No lanzar ingestas ni habilitar reparación de otro scope.
10. [ ] Probar regresiones de Mbappé/identidad García junto a IDs arbitrarios; dos acciones en el mismo minuto, extra-time, penalti fallado, tanda, autogol, VAR/cancelación, actor sin ID, Stats contradictorias y respuesta parcial. El componente ambiguo queda pendiente sin modificarlo; los componentes independientes acreditados pueden repararse.
   - [ ] Probar reparación parcial: asistencia Trincão/Vagiannidis preservada con warning y goles/asistencia concordante Dembélé 79 recuperables solo si independientes; marcador inconsistente bloquea contexto, doble asistente del mismo gol bloquea el conjunto, Stats se actualiza por campos y `[]` no borra acciones positivas. Declarar el resultado v4 con incidencias pendientes cuando corresponda.
11. [ ] Probar archivo/restauración v3 con identidad y procedencia originales, sin gate de paridad antigua; conservación PE.id/psxg/STATS, GK raw sin PES esperado, recálculo completo v4/B1/bonos, contexto ausente, guardas OLD/NEW, CAS, repetición y rollback con nueva referencia posterior.
12. [ ] Restaurar backup en clon compatible con producción, aplicar reparación y recalcular todo el scope con v4, incluyendo bonos y ranking; repetir sin diferencias y revertir. Probar el corte final sin mezcla de proyecciones parciales y la indisponibilidad explícita v3 archivada. SQL demuestra que pares fuera del scope, ELO/reglas/posiciones y otras temporadas no cambiaron.
13. [ ] Ejecutar suite completa, flake8 e isort; documentar cobertura y cumplir el gate de CI ≥80% sin ocultar deuda baseline. Adjuntar pruebas de PostgreSQL reales y hashes de fuente/plan/resultado.
14. [ ] Entregar manifiesto verificable y reporte de reparables/aplicadas/pendientes, archivo v3 y resultado completo v4 antes/después. En operación, mantener exclusión de escritores y serving anterior/indisponible hasta cerrar todo el periodo; publicar solo el corte coherente o restaurar before. La autorización vigente permite ejecutar reparación y recálculo tras los gates, sin pedir aprobación repetida; este spec no declara esas acciones ya realizadas.

## Verificación

### Incremento de promoción y reversión del corte preparado

- [ ] Crear Promote/RevertSeasonIntegrityProjectionUseCase, port de publicación y adaptador SQL con DTOs frozen y DI; reutilizar journal. El apply raw por fixture actual sigue siendo una herramienta de preparación del clon, no el publicador completo.
- [ ] Preparar staging before/after con esquema validado, manifiesto exacto de filas/ausencias y dependencias (posición publicada, fuerzas, etapas, reglas); verificar backup restaurado y hashes antes del cutover.
- [ ] Si solo difiere last_updated de los rollups Mundial 350/2026/v4 inventariados, conservar before original inmutable y adoptar únicamente esa metadata en copia operativa bajo exclusivo, tras igualdad de conjuntos y JSON de filas excluyendo solo ese campo. Registrar delta/hashes, repetir CAS íntegro y usar la imagen operativa para revert. Probar que puntos, nuevas filas u otra columna distinta abortan sin adopción material.
- [ ] Para el refresco físico CA/PAB del Mundial, probar correspondencias naturales únicas/biyectivas y equivalencia de todas las columnas salvo IDs/created_at expresamente permitidos. Conservar initial, registrar mapas, renovar solo staging before y dependencias after, remapear FK de after.PAB sin cambiar números, cerrar referencias FK/JSON y repetir CAS completo bajo el mismo exclusivo. Probar rechazo de puntos/participación/detalles distintos, clave nueva, duplicada o referencia externa; promote/revert conserva los padres live adoptados y restaura before operativo.
- [ ] Admitir renovación privada de players.name solo con restantes campos del CAS iguales y cero diferencias del resolver efectivo desplegado en todos los contextos de actores before/after. Registrar mapa/contextos/hashes y repetir CAS; probar que un nombre que activa otro override, otra posición/DOB/external_id o una asignación distinta aborta. No alterar nombres live ni evidencias históricas, y conservar nombres adoptados al revertir scores.
- [ ] Implementar CAS bajo exclusivo try-only adquirido antes de leer live y transacción única sin recálculo. Probar Busy, inserción concurrente y cambio de dependencia sin escrituras parciales.
- [ ] Reutilizar GUC de publicación existente mediante set_config LOCAL solo tras lock/CAS/journal, restablecer off antes de verificar y probar limpieza tras commit/rollback en conexión reutilizada. Mantener todos los triggers, incluida la protección DELETE de rollups; ninguna fila preservada puede pasar la comparación after. Medir promote/revert completo con guardas productivas en clon antes del cutover.
- [ ] Implementar remapeo de PE nuevas con secuencia productiva y referencias completas; actualizar PES/rollups/bonos por claves lógicas, conservar IDs existentes y generar nuevos IDs localmente. Probar colisiones entre IDs nuevos del clon y actividad 2026, JSON con event_id, FKs fuera del cierre y huecos de secuencia tras rollback.
- [ ] Verificar before/after real y mapa durable antes del commit; probar failpoints antes/tras commit, triggers que ignoran escrituras y lectura consistente del corte. Las caches se invalidan tras commit con recuperación explícita si falla.
- [ ] Ensayar promote/revert en clon con actividad 2026 ajena simulada, conservarla exactamente y rechazar revert con referencias/cambios posteriores. Documentar pausa/drenaje, reanudación y health checks sin operaciones ELO ni API durante publicación.

El criterio no es igualar todos los totales de PlayerStats. Cada cambio debe tener una acción fuente identificable, actor y contexto demostrables; cada diferencia restante queda clasificada. La evidencia archivada reproduce el resultado v4 sin HTTP. El clon demuestra archivo histórico restaurable, resultado completo v4, conservación fuera de scope, segunda ejecución vacía y reversión íntegra. No se exige paridad histórica v3. La publicación final no puede confundir una ejecución parcial con el cierre del periodo.

## Agent Routing Brief

**DDD Designer needed:** yes.

DDD-Designer ya fue consultado para esta solicitud: identidad de acción frente a ocurrencia, revisiones y cobertura de timeline. Implementar esos invariantes mínimos mediante DTOs/VO; reutilizar scoring y concepto de manifiesto existente, sin crear otra plataforma. Si aparecen cambios en metodología o nuevas entidades adicionales, volver a consultar antes de ampliar el alcance. El resto corresponde a use cases, adaptadores SQL/archivo y pruebas siguiendo las skills de implementación aplicables.
