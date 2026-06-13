# Plan: Recuperacion auditable de snapshots de equipo unresolved

## Archivos a crear

- [ ] `migrations/0023_team_snapshot_repair_audit.sql`
- [x] `scripts/diagnose_unresolved_team_snapshots.sql`
- [ ] `src/sfa/domain/team_snapshot_repair_ports.py`
- [ ] `src/sfa/application/use_cases/repair_player_team_snapshots.py`
- [ ] `src/sfa/infrastructure/models/team_snapshot_repair/models.py`
- [ ] `src/sfa/infrastructure/models/team_snapshot_repair/__init__.py`
- [ ] `src/sfa/infrastructure/repositories/team_snapshot_repair_repository.py`
- [ ] `src/sfa/tasks/team_snapshot_repair_task.py`
- [ ] `src/sfa/api/v1/schemas/team_snapshot_repair_schemas.py`
- [ ] `http/team_snapshot_repair.http`
- [ ] `tests/use_cases/test_repair_player_team_snapshots.py`
- [ ] `tests/repositories/test_team_snapshot_repair_repository.py`

## Archivos a modificar

- [ ] `src/sfa/domain/ingestion_ports.py`
- [ ] `src/sfa/infrastructure/providers/api_football.py`
- [ ] `src/sfa/infrastructure/models/__init__.py`
- [ ] `src/sfa/infrastructure/repositories/__init__.py`
- [ ] `src/sfa/tasks/__init__.py`
- [ ] `src/sfa/api/v1/admin.py`
- [ ] `src/sfa/api/v1/schemas/__init__.py`
- [ ] `src/sfa/core/dependencies.py`

## Checklist de implementacion

- [x] 0. Diagnosticar la causa del residual.
  Criterio: el script read-only reproduce 21.711 candidatos iniciales, 983 resueltos
  por season score y 20.728 unresolved finales. Identifica por separado cualquier
  `external_id` nulo o no positivo.

- [ ] 1. Registrar baseline.
  Criterio: ejecutar suite completa, guardar total de tests y documentar fallos
  preexistentes. Capturar tambien los cinco contadores criticos sobre una copia con 0021.

- [ ] 2. Capturar baseline funcional de la copia.
  Criterio: persistir conteos y sumas de scores, bonos, eventos y stats; generar hash
  estable por score para comparacion posterior.

- [ ] 2a. Corregir la identidad invalida conocida.
  Criterio: reconstruir por fixture las diez apariciones asociadas a
  `players.id=202854`, `external_id=0`; siete pertenecen al residual. La correccion es
  manual, auditada y validada contra API-Football.

- [ ] 2b. Bloquear nuevos external IDs invalidos.
  Criterio: provider, use case y repositorio rechazan IDs no positivos. Tras limpiar el
  dato existente se valida el check DB
  `players.external_id IS NULL OR players.external_id > 0`.

- [ ] 3. Crear migracion 0023 para auditoria de repair.
  Criterio: crea `team_snapshot_repair_runs` y `team_snapshot_repair_items`, enums o
  checks de estado, FKs, indices y unicidad `(run_id, player_stats_id)`.

- [ ] 4. Definir concurrencia de runs apply.
  Criterio: la migracion o el repositorio impide mas de un run apply activo y documenta
  el advisory lock utilizado.

- [ ] 5. Crear modelos ORM de repair.
  Criterio: reflejan exactamente la migracion; no agregan relaciones ORM innecesarias.

- [ ] 6. Crear DTOs frozen de repair.
  Criterio: incluye fixture unresolved, aparicion unresolved, jugador del provider,
  decision, contadores de auditoria y resultado final.

- [ ] 7. Crear `TeamSnapshotRepairRepositoryPort`.
  Criterio: contiene solo operaciones necesarias para runs, lotes, decisiones,
  actualizacion de snapshots, propagacion a eventos, auditoria y rollback.

- [ ] 8. Ampliar `FootballDataProviderPort`.
  Criterio: nueva operacion retorna la asociacion exacta
  `(fixture_external_id, team_external_id, player_external_id)` sin modificar
  `fetch_all_fixture_players()`.

- [ ] 9. Implementar el adaptador API-Football.
  Criterio: conserva team external ID por jugador, deduplica respuestas y detecta un
  jugador asociado a mas de un equipo en el mismo fixture.

- [ ] 10. Implementar repositorio: crear y consultar runs.
  Criterio: soporta dry-run, apply, resume y estados terminales; nunca retorna ORM.

- [ ] 11. Implementar repositorio: adquirir fixtures unresolved por lote.
  Criterio: selecciona fixtures distintos, orden estable por ID, filtros de temporada y
  competicion, cursor reanudable y limite obligatorio.

- [ ] 12. Implementar repositorio: mapa local del fixture.
  Criterio: retorna home/away local y external IDs de ambos equipos junto con las
  apariciones unresolved y external ID exacto de cada jugador.

- [ ] 13. Implementar repositorio: aplicar snapshot.
  Criterio: actualiza `player_stats.team_id` solo si sigue NULL y el candidato pertenece
  al fixture. Retorna si la fila fue realmente modificada.

- [ ] 14. Implementar repositorio: propagar snapshot.
  Criterio: actualiza `player_events.team_id` del mismo `(player_id, fixture_id)` solo
  despues de resolver la aparicion.

- [ ] 15. Implementar repositorio: registrar decisiones.
  Criterio: conserva estado, razon, IDs externos, equipo anterior, candidato y evidencia
  minima. La escritura es idempotente.

- [ ] 16. Implementar repositorio: cinco contadores criticos.
  Criterio: usa exactamente las definiciones de 0028 y permite comparacion por run.

- [ ] 17. Implementar `RepairPlayerTeamSnapshotsUseCase`.
  Criterio: procesa por fixture, consulta una vez al proveedor, valida coincidencias
  exactas, clasifica cada aparicion y no modifica datos en dry-run.

- [ ] 18. Implementar validaciones de entrada.
  Criterio: dry-run por defecto, `max_fixtures` obligatorio y acotado, batch positivo,
  apply con confirmacion explicita y rechazo de competiciones `national_team`.

- [ ] 19. Implementar manejo de cuota y errores.
  Criterio: 429, timeout o error transitorio deja el run partial, conserva cursor y no
  revierte lotes confirmados.

- [ ] 20. Implementar reanudacion.
  Criterio: `resume_run_id` continua desde el cursor y omite items ya registrados sin
  volver a consultar fixtures completados.

- [ ] 21. Implementar rollback auditado.
  Criterio: restaura solo valores aplicados por el run cuando no han sido reemplazados
  posteriormente y genera evidencia nueva; nunca borra items anteriores.

- [ ] 22. Crear Celery task.
  Criterio: wrapper sync/async con imports tardios, una transaccion por lote, retries
  solo para errores transitorios y logs con prefijo.

- [ ] 23. Registrar task.
  Criterio: exportada en `tasks/__init__.py` y descubrible por el worker.

- [ ] 24. Agregar wiring en `core/dependencies.py`.
  Criterio: repositorio, provider y use case se construyen unicamente en DI.

- [ ] 25. Crear schemas administrativos.
  Criterio: request de dry-run/apply, respuesta con task ID, detalle de run, contadores
  y pagina de items unresolved.

- [ ] 26. Crear endpoint para iniciar repair.
  Criterio: enqueue Celery; apply exige confirmacion; no ejecuta trabajo pesado en HTTP.

- [ ] 27. Crear endpoints de lectura.
  Criterio: consultar run, contadores e items por estado sin exponer payloads completos
  del proveedor.

- [ ] 28. Documentar seguridad administrativa.
  Criterio: el spec de despliegue VPS debe proteger estos endpoints; en desarrollo se
  conserva compatibilidad con el mecanismo actual.

- [ ] 29. Crear archivo HTTP.
  Criterio: incluye dry-run, apply confirmado, resume, consulta de estado, filtros y
  errores de validacion.

- [ ] 30. Test: dry-run no escribe snapshots.
  Criterio: produce decisiones resolved potenciales, pero no llama apply ni propagacion.

- [ ] 31. Test: resolucion exacta home y away.
  Criterio: external IDs exactos generan el equipo local correcto.

- [ ] 32. Test: rechazo por equipo fuera del fixture.
  Criterio: queda unresolved con razon `team_not_in_fixture`.

- [ ] 33. Test: jugador ambiguo.
  Criterio: el mismo external ID bajo dos equipos no se actualiza.

- [ ] 34. Test: jugador sin external ID o ausente en provider.
  Criterio: se registra la razon y se mantiene NULL.

- [ ] 35. Test: idempotencia.
  Criterio: reejecutar o reanudar no duplica items ni sobrescribe snapshots resueltos.

- [ ] 36. Test: error del proveedor.
  Criterio: conserva cursor, marca partial y permite resume.

- [ ] 37. Test: propagacion a eventos.
  Criterio: todos los eventos del jugador/fixture reciben el mismo equipo que stats.

- [ ] 38. Test: rollback.
  Criterio: revierte solo valores aplicados por el run que no cambiaron posteriormente.

- [ ] 39. Test: competicion nacional bloqueada.
  Criterio: el repair historico de clubes rechaza `participant_kind=national_team`.

- [ ] 40. Test de repositorio sobre PostgreSQL.
  Criterio: valida locks, cursor, unicidad, transacciones por lote y queries de auditoria.

- [ ] 41. Ejecutar dry-run sobre copia actualizada.
  Criterio: reporta resolved potenciales por fixture, consumo estimado de requests y
  unresolved finales por razon sin modificar snapshots.

- [ ] 42. Ejecutar apply sobre copia.
  Criterio: solo cambian snapshots y tablas de repair; scores, bonos, eventos de scoring
  y stats numericas permanecen identicos.

- [ ] 43. Verificar gate posterior.
  Criterio: registrar cinco contadores, hashes antes/despues y lista residual para
  correccion manual.

- [ ] 44. Probar rollback completo sobre copia.
  Criterio: restaura contadores y snapshots previos sin alterar otras columnas.

- [ ] 45. Ejecutar calidad estatica y suite completa.
  Criterio: no aparecen errores nuevos y cobertura de la nueva logica es suficiente.

- [ ] 46. Actualizar el plan 0028.
  Criterio: enlaza este spec como mecanismo oficial de recuperacion y conserva bloqueado
  0022 hasta completar el gate.

- [ ] 47. Commit.
  Criterio: rama dedicada; diff del dominio de scoring vacio; no incluye cambios de
  formulas, puntos ni multiplicadores.

## Secuencia operativa recomendada

1. Crear copia reciente de DB.
2. Aplicar 0021 en la copia.
3. Aplicar 0023.
4. Ejecutar dry-run con limite pequeño.
5. Comparar decisiones con fixtures de muestra.
6. Ejecutar apply por lotes y reanudar segun cuota.
7. Corregir manualmente el residual documentado.
8. Obtener los cinco contadores en cero.
9. Comparar hashes, rankings, ELO y logros.
10. Repetir controladamente en la DB activa.
11. Ejecutar 0022.
12. Habilitar despues la ingesta aislada del Mundial.

## Agent Routing Brief

- Implementacion general: agente backend con experiencia en FastAPI, SQLAlchemy async,
  PostgreSQL y Celery.
- Revision de migraciones, locks y rollback: `@Database-Engineer` si esta disponible.
- Cambios en scoring: no autorizados; si aparecen como necesarios, detener la
  implementacion y volver a `@Architecture-Engineer`.
- No se requiere `@DDD-Designer`: las nuevas estructuras son DTOs y persistencia
  operacional, no entidades ni aggregates del dominio de scoring.
