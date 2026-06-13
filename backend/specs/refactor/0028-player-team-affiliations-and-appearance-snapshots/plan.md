# Plan: Afiliaciones de jugador y snapshots de equipo por aparicion

## Archivos a crear

- [ ] `migrations/0021_player_team_affiliations_expand_and_backfill.sql`
- [ ] `migrations/0022_player_team_affiliations_constraints.sql`
- [ ] `scripts/audit_player_team_snapshots.sql`
- [ ] `src/sfa/domain/participation/__init__.py`
- [ ] `src/sfa/domain/participation/entities.py` [DDD]
- [ ] `src/sfa/domain/participation/value_objects.py` [DDD]
- [ ] `src/sfa/domain/participation_ports.py` [DDD]
- [ ] `src/sfa/infrastructure/models/player_team_affiliations/__init__.py`
- [ ] `src/sfa/infrastructure/models/player_team_affiliations/models.py`
- [ ] `src/sfa/infrastructure/repositories/player_team_affiliation_repository.py`
- [ ] `tests/domain/participation/test_entities.py`
- [ ] `tests/use_cases/test_ingest_competition_player_affiliations.py`
- [ ] `tests/repositories/test_player_team_affiliation_repository.py`
- [ ] `tests/repositories/test_player_team_attribution.py`
- [ ] `tests/repositories/test_player_team_dual_read.py`
- [ ] `tests/repositories/test_global_ranking_representative_team.py`
- [ ] `tests/integration/conftest.py` solo si no existe soporte PostgreSQL equivalente

## Archivos a modificar

- [ ] `src/sfa/domain/ingestion_ports.py`
- [ ] `src/sfa/domain/ports.py`
- [ ] `src/sfa/domain/scoring_ports.py`
- [ ] `src/sfa/application/use_cases/ingest_competition.py`
- [ ] `src/sfa/application/use_cases/reingest_player.py`
- [ ] `src/sfa/application/use_cases/calculate_elo_ratings.py`
- [ ] `src/sfa/infrastructure/models/enums.py`
- [ ] `src/sfa/infrastructure/models/competitions/models.py`
- [ ] `src/sfa/infrastructure/models/players/models.py`
- [ ] `src/sfa/infrastructure/models/player_stats/models.py`
- [ ] `src/sfa/infrastructure/models/events/models.py`
- [ ] `src/sfa/infrastructure/models/__init__.py`
- [ ] `src/sfa/infrastructure/repositories/__init__.py`
- [ ] `src/sfa/infrastructure/repositories/ingestion_repository.py`
- [ ] `src/sfa/infrastructure/repositories/scoring_repository.py`
- [ ] `src/sfa/infrastructure/repositories/player_event_score_repository.py`
- [ ] `src/sfa/infrastructure/repositories/team_strength_repository.py`
- [ ] `src/sfa/infrastructure/repositories/competition_achievement_repository.py`
- [ ] `src/sfa/infrastructure/repositories/infer_achievements_repository.py`
- [ ] `src/sfa/infrastructure/repositories/sfa_score_repository.py`
- [ ] `src/sfa/infrastructure/repositories/player_repository.py`
- [ ] `src/sfa/infrastructure/repositories/enrich_position_repository.py`
- [ ] `src/sfa/core/dependencies.py`
- [ ] tests focalizados de ingestion, reingesta, scoring, ELO, logros, ranking y perfil

## Checklist de implementacion

- [ ] 1. Registrar el baseline completo de tests.
  Criterio: `pytest tests/ -x` queda documentado con fallos preexistentes identificados.

- [ ] 2. Verificar infraestructura de tests de repositorio.
  Criterio: se confirma si existe fixture async PostgreSQL; si no, se planifica
  `tests/integration/conftest.py` contra PostgreSQL 16 y no SQLite.

- [ ] 3. Auditar todas las referencias a `Player.team_id`.
  Criterio: cada lectura/escritura de `src/` y `tests/` queda clasificada por ingestion,
  scoring, ELO, logros o presentacion.

- [ ] 4. Verificar numeracion de migraciones inmediatamente antes de crear SQL.
  Criterio: se lista `migrations/`; si `0020` sigue siendo la ultima se usan `0021` y
  `0022`, de lo contrario se renumeran ambos scripts consecutivamente.

- [ ] 5. Ejecutar auditoria diagnostica previa sobre una copia actual.
  Criterio: se guardan conteos totales, resolubles, conflictos y unresolved con IDs.

- [ ] 6. Clasificar los contadores de auditoria.
  Criterio: divergencia evento-stats, NULL, equipo fuera de fixture, evento sin aparicion,
  score sin resolver y semantica invalida quedan marcados como criticos.

- [ ] 7. Establecer el criterio de rollout.
  Criterio: se documenta que constraints, cutover y Mundial requieren cero criticos, sin
  umbral parcial.

- [ ] 8. Implementar `AffiliationKind`. [DDD]
  Criterio: Value Object frozen que acepta solo `club` y `national_team`.

- [ ] 9. Implementar `PlayerTeamAffiliation`. [DDD]
  Criterio: valida identidad, temporada, intervalo, source `fixture` e idempotencia.

- [ ] 10. Implementar `PlayerFixtureAppearance` como concepto de dominio. [DDD]
  Criterio: identidad `(player_id, fixture_id)`, equipo del fixture y persistencia en
  `player_stats`, sin tabla ni aggregate adicional.

- [ ] 11. Confirmar ausencia de `PlayerParticipation`. [DDD]
  Criterio: no se crea una raiz artificial; el use case coordina ports en una transaccion.

- [ ] 12. Escribir tests unitarios del dominio.
  Criterio: cubren tipos invalidos, intervalos invertidos, coexistencia y extensiones
  idempotentes.

- [ ] 13. Agregar `participant_kind` persistido a Competition.
  Criterio: default `club`, check de valores y compatibilidad con competiciones existentes.

- [ ] 14. Extender `LeagueConfig` con `participant_kind`.
  Criterio: default `club` y valor persistido al crear o actualizar Competition.

- [ ] 15. Validar semantica `national_team`.
  Criterio: una afiliacion solo adopta el kind persistido de la competicion del fixture;
  no puede marcarse Bayern como seleccion por un parametro discordante.

- [ ] 16. Crear modelo ORM de afiliaciones.
  Criterio: FKs, unique, indices, timestamps y check `source='fixture'`.

- [ ] 17. Agregar snapshots nullable en la fase expand.
  Criterio: `player_stats.team_id` y `player_events.team_id` aceptan filas legacy.

- [ ] 18. Hacer `players.team_id` nullable y deprecado.
  Criterio: comentario de modelo prohibe nuevas escrituras y uso autoritativo.

- [ ] 19. Implementar backfill de `player_stats.team_id`.
  Criterio: aplica prioridades formales, valida home/away y reporta conflictos/unresolved.

- [ ] 20. Implementar backfill de `player_events.team_id`.
  Criterio: copia por `(player_id, fixture_id)` desde la aparicion exacta.

- [ ] 21. Implementar backfill de afiliaciones.
  Criterio: agrupa apariciones por jugador-equipo-temporada-kind y deriva intervalos.

- [ ] 22. Reparar `sfa_season_scores.team_id`.
  Criterio: mayor suma de minutos, luego aparicion mas reciente y luego menor `team_id`.

- [ ] 23. Hacer el backfill idempotente y por lotes.
  Criterio: admite reejecucion, checkpoints y pausa sin una transaccion de larga duracion.

- [ ] 24. Completar el script de auditoria reutilizable.
  Criterio: funciona en modo pre-expand y post-backfill y lista IDs de filas problematicas.

- [ ] 25. Auditar divergencia critica evento-aparicion.
  Criterio: cuenta `player_events.team_id <> player_stats.team_id` para el mismo
  `(player_id, fixture_id)` y bloquea el rollout si es mayor que cero.

- [ ] 26. Auditar pertenencia al fixture.
  Criterio: stats y eventos solo contienen home o away del fixture.

- [ ] 27. Auditar coherencia semantica de afiliaciones.
  Criterio: cada afiliacion tiene una aparicion de respaldo y su `kind` coincide con
  `competitions.participant_kind`.

- [ ] 28. Mantener separados los scripts operativos.
  Criterio: expand/backfill queda en la primera migracion; constraints en la segunda.

- [ ] 29. Implementar dual-read temporal para apariciones.
  Criterio: usa snapshot y luego `players.team_id` solo si pertenece al fixture; de otro
  modo devuelve unresolved con telemetria.

- [ ] 30. Implementar dual-read temporal para eventos.
  Criterio: orden evento, stats y fallback legacy validado; nunca inventa home/away.

- [ ] 31. Encapsular dual-read en infraestructura.
  Criterio: routers y use cases no contienen `COALESCE` ni logica legacy.

- [ ] 32. Cambiar `upsert_player` en port y adapter.
  Criterio: no acepta ni escribe `team_id`.

- [ ] 33. Agregar `team_id` a contratos de stats y eventos.
  Criterio: ports, adapters y callers coinciden.

- [ ] 34. Actualizar ingestion.
  Criterio: escribe snapshots y observa afiliacion con el kind persistido.

- [ ] 35. Validar equipo antes de persistir.
  Criterio: equipo fuera del fixture aborta la transaccion con error explicito.

- [ ] 36. Probar ingestion idempotente de club.
  Criterio: no duplica identidad, afiliacion, stats ni eventos.

- [ ] 37. Probar club y seleccion secuenciales.
  Criterio: un `players.id`, dos afiliaciones y snapshots contextuales.

- [ ] 38. Cubrir Pedri `external_id=133609`.
  Criterio: Barcelona y Espana comparten identidad sin sobrescribir equipo global.

- [ ] 39. Probar transferencia dentro de una temporada.
  Criterio: dos afiliaciones club permitidas y cada aparicion mantiene su equipo.

- [ ] 40. Actualizar reingesta dirigida.
  Criterio: obtiene local/visitante y recrea eventos desde el snapshot de aparicion.

- [ ] 41. Crear resolver compartido de equipo representativo.
  Criterio: implementa exactamente minutos, fecha y `team_id` de P1.

- [ ] 42. Aplicar resolver al score por competicion.
  Criterio: `SFASeasonScore.team_id` no lee `Player.team_id`.

- [ ] 43. Aplicar resolver al ranking global de temporada.
  Criterio: agrega todas las competiciones del scope y devuelve un equipo determinista.

- [ ] 44. Aplicar resolver al ranking historico.
  Criterio: elige primero la temporada de aparicion mas reciente y luego aplica P1.

- [ ] 45. Aplicar fallback formal al perfil.
  Criterio: competicion, temporada, ultima temporada con aparicion o valores de equipo NULL;
  nunca afiliacion nacional generica ni club inventado.

- [ ] 46. Corregir enriquecimiento de posiciones.
  Criterio: solo usa contexto club demostrable y omite jugadores sin aparicion club.

- [ ] 47. Corregir ELO para usar `PlayerStats.team_id`.
  Criterio: goles local/visitante no unen `Player.team_id`.

- [ ] 48. Determinar temporadas afectadas para rebuild ELO.
  Criterio: lista derivada de snapshots creados o corregidos y guardada en reporte.

- [ ] 49. Generar baseline ELO reproducible.
  Criterio: artefacto versionado por temporada, equipo, fecha, elo y source; ClubElo usa
  fecha anterior al primer fixture y faltantes quedan explicitamente en 1500.

- [ ] 50. Validar cobertura del baseline ELO.
  Criterio: todos los equipos del replay tienen seed o default documentado; de lo contrario
  se bloquea cutover.

- [ ] 51. Implementar modo rebuild ELO.
  Criterio: reemplaza solo resultados `elo_v1` y no arranca desde el ELO final preexistente.

- [ ] 52. Reproducir ELO completo post-backfill.
  Criterio: procesa `played_at ASC, fixture_id ASC` y compara fixtures, goles y equipos.

- [ ] 53. Recalcular scoring dependiente de M1.
  Criterio: versiones activas afectadas se recalculan despues del rebuild ELO.

- [ ] 54. Corregir minutos y seleccion para logros.
  Criterio: consultas filtran `PlayerStats.team_id`.

- [ ] 55. Corregir ranking interno y bonuses.
  Criterio: el scope usa score/apariciones contextuales, no jugador global.

- [ ] 56. Corregir inferencia de goles y tandas.
  Criterio: usa `PlayerEvent.team_id`.

- [ ] 57. Probar bonus de club y seleccion.
  Criterio: Barcelona y Espana seleccionan minutos propios del mismo jugador.

- [ ] 58. Ejecutar auditoria post-backfill.
  Criterio: todos los contadores criticos son cero.

- [ ] 59. Eliminar dual-read en cutover.
  Criterio: se eliminan resolvers legacy y un snapshot NULL pasa a ser error de integridad.

- [ ] 60. Buscar referencias residuales.
  Criterio: `rg` solo encuentra `players.team_id` en modelo, migraciones y comentario de
  deprecacion.

- [ ] 61. Desplegar binario sin dual-read.
  Criterio: opera con clubes, reingesta controlada y rankings correctos antes de constraints.

- [ ] 62. Aplicar migracion de constraints.
  Criterio: FKs, checks, indices y `NOT NULL` se aplican con auditoria cero.

- [ ] 63. Probar constraints en PostgreSQL 16.
  Criterio: rechazan NULL, kind/source invalido y FKs inexistentes.

- [ ] 64. Probar consistencia transaccional evento-aparicion.
  Criterio: ingestion normal escribe ambos snapshots iguales y rollback evita estados
  parciales.

- [ ] 65. Comparar scoring antes y despues.
  Criterio: mismas formulas y eventos producen mismos puntos salvo cambios explicados por
  ELO o atribucion previamente incorrecta.

- [ ] 66. Comparar logros y bonuses.
  Criterio: diferencias quedan explicadas por correcciones de equipo.

- [ ] 67. Mantener compatibilidad HTTP.
  Criterio: schemas, tipos y codigos existentes no cambian.

- [ ] 68. Ejecutar tests focalizados.
  Criterio: dominio, SQL, ingestion, reingesta, ELO, scoring, logros, ranking y perfil pasan.

- [ ] 69. Ejecutar suite y calidad estatica.
  Criterio: no aparecen regresiones nuevas; deuda previa queda documentada.

- [ ] 70. Habilitar gate del futuro Mundial.
  Criterio: Pedri, transferencias, ELO rebuild, logros, ranking global, perfil y auditoria
  pasan end-to-end con cero criticos.

- [ ] 71. Registrar eliminacion fisica de `players.team_id`.
  Criterio: existe deuda/spec posterior condicionado a despliegue estable y cero referencias.

## Verificacion

1. Pedri conserva un unico `players.id`.
2. Barcelona/club y Espana/national_team coexisten.
3. Stats y eventos de cada fixture tienen el mismo equipo.
4. Ranking global aplica minutos, fecha y `team_id` sin "competicion principal".
5. Perfil sin apariciones devuelve equipo NULL.
6. ELO se reconstruye desde baseline reproducible y no desde el resultado anterior.
7. Scoring dependiente de M1 se recalcula despues del ELO.
8. Auditoria reporta cero divergencias evento-aparicion y cero unresolved.
9. No hay lecturas de negocio de `players.team_id` tras cutover.
10. No se habilita el Mundial antes de completar el gate.

## Agent Routing Brief

**DDD Designer needed:** yes

La revision del criterio local de DDD concluye que `PlayerTeamAffiliation` es Entity,
`PlayerFixtureAppearance` es un concepto con identidad compuesta persistido en
`player_stats`, y `AffiliationKind` es Value Object. No se crea `PlayerParticipation`
porque no protege una invariante agregada real. El use case coordina aparicion y afiliacion
dentro de una transaccion. `source=squad` queda fuera hasta que exista un flujo de
plantillas. No cambia el dominio matematico de scoring.
