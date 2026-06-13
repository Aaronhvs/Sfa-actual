# Plan: Snapshots de equipo por aparicion (v2 post-auditoria)

## Estado de ejecucion - 2026-06-13

- Implementacion de codigo, migraciones y auditoria completada.
- Rama: `refactor/SFA-0028-player-team-snapshots`.
- Commit de implementacion: `0045faa`.
- Suite completa: `293 passed`.
- `0021` validada de forma idempotente sobre una copia de la DB local.
- Totales de `sfa_season_scores` antes/despues: identicos.
- Gate operativo pendiente: quedaron 20.728 `player_stats` y 24.047
  `player_events` sin snapshot en la copia. `0022` no fue ejecutada.
- La DB activa no fue modificada y la ingesta del Mundial debe seguir bloqueada.

## Tareas operativas pendientes

- [ ] 1. Crear una copia actualizada de la DB activa y ejecutar
  `scripts/audit_player_team_snapshots.sql`.
  Salida esperada: conservar los conteos antes de aplicar `0021`.

- [ ] 2. Aplicar `migrations/0021_player_team_snapshots_expand.sql` unicamente sobre
  la copia y volver a ejecutar la auditoria.
  Ultimo resultado conocido: 20.728 `player_stats.team_id IS NULL` y 24.047
  `player_events.team_id IS NULL`; los otros tres contadores criticos dieron cero.

- [ ] 3. Resolver todas las apariciones sin snapshot.
  Orden: reingesta controlada del fixture, correccion manual auditada y, solo como
  ultima fuente, datos de bonos/logros validados contra home/away.

- [ ] 4. Propagar el snapshot resuelto desde `player_stats` hacia `player_events`
  y repetir la auditoria.
  Condicion de salida: los cinco contadores criticos deben ser exactamente cero.

- [ ] 5. Comparar antes/despues en la copia:
  `sfa_season_scores.total_pts`, `achievement_bonus_pts`, top de rankings, ELO de
  clubes y jugadores seleccionados para logros.
  Condicion de salida: ninguna diferencia funcional en datos de clubes.

- [ ] 6. Aplicar `0021` en la DB activa durante una ventana controlada, desplegar el
  codigo nuevo y realizar una reingesta de muestra de La Liga.

- [ ] 7. Ejecutar `migrations/0022_player_team_snapshots_constraints.sql` solamente
  cuando no haya callers antiguos y los cinco contadores sean cero.

- [ ] 8. Habilitar la ingesta y ranking aislado del Mundial solo despues de completar
  `0022`.

### Bloqueos vigentes

- No ejecutar `0022` con snapshots unresolved.
- No ingestar el Mundial ni competiciones `national_team`.
- No recalcular ni modificar formulas, multiplicadores o puntos actuales.
- No mezclar puntos del Mundial con temporadas de clubes.

## Archivos a crear

- [x] `migrations/0021_player_team_snapshots_expand.sql`
- [x] `migrations/0022_player_team_snapshots_constraints.sql`
- [x] `scripts/audit_player_team_snapshots.sql`
- [x] `tests/use_cases/test_ingest_competition_team_snapshot.py`
- [x] `tests/use_cases/test_team_snapshot_repositories.py`

## Archivos a modificar

- [x] `src/sfa/domain/ingestion_ports.py`
- [x] `src/sfa/infrastructure/models/player_stats/models.py`
- [x] `src/sfa/infrastructure/models/events/models.py`
- [x] `src/sfa/infrastructure/models/competitions/models.py`
- [x] `src/sfa/infrastructure/repositories/ingestion_repository.py`
- [x] `src/sfa/application/use_cases/ingest_competition.py`
- [x] `src/sfa/application/use_cases/reingest_player.py`
- [x] `src/sfa/infrastructure/repositories/team_strength_repository.py`
- [x] `src/sfa/infrastructure/repositories/competition_achievement_repository.py`
- [x] `src/sfa/infrastructure/repositories/infer_achievements_repository.py`
- [x] `src/sfa/infrastructure/repositories/player_event_score_repository.py`
- [x] `src/sfa/infrastructure/repositories/player_repository.py`
- [x] `src/sfa/infrastructure/repositories/sfa_score_repository.py`
- [x] `src/sfa/infrastructure/repositories/scoring_repository.py`
- [x] `src/sfa/infrastructure/repositories/enrich_position_repository.py`
- [ ] `tests/use_cases/test_reingest_player.py`
- [ ] `tests/use_cases/test_calculate_achievement_bonuses.py`
- [ ] `tests/use_cases/test_infer_competition_achievements.py`
- [ ] `tests/use_cases/test_calculate_elo_ratings.py`

## Checklist de implementacion

- [ ] 1. Registrar baseline de tests.
  Criterio: ejecutar `pytest tests/ -x` y documentar fallos preexistentes. Ninguno
  nuevo puede aparecer al final del spec.

- [x] 2. Auditar referencias a `Player.team_id`.
  Criterio: `rg "Player\.team_id|players\.team_id|p\.team_id" src/` produce una lista
  completa clasificada por archivo y tipo de lectura. Verificar contra la tabla de la
  seccion "Lecturas a corregir" en decisions.md; identificar si hay adicionales.

- [x] 3. Ejecutar `scripts/audit_player_team_snapshots.sql` en modo diagnostico sobre
  copia de DB.
  Criterio: el script no depende de columnas nuevas. Registra conteos de fixtures,
  candidatos validos, candidatos invalidos y unresolved estimados. Resultado adjunto
  al registro operativo antes de aplicar 0021.

- [x] 4. Crear `migrations/0021_player_team_snapshots_expand.sql`.
  El orden dentro del script es obligatorio segun decisions.md:
  1. `ALTER players.team_id DROP NOT NULL` — primer paso, antes de cualquier otro.
  2. `ALTER competitions ADD participant_kind`.
  3. `ALTER player_stats ADD team_id` nullable + indice.
  4. `ALTER player_events ADD team_id` nullable + indice.
  5. Backfill `player_stats.team_id` con candidato 1 (`players.team_id` validado)
     y candidato 2 (`sfa_season_scores.team_id` validado).
  6. Backfill `player_events.team_id` desde aparicion exacta.
  7. Ejecutar consultas de auditoria post-backfill; mostrar conteos.
  Criterio: el script es idempotente, no bloquea la tabla en un lock prolongado y
  reporta IDs de filas unresolved.

- [x] 5. Crear `scripts/audit_player_team_snapshots.sql`.
  Criterio: reporta los cinco contadores criticos definidos en decisions.md mas:
  - conteo de snapshots resueltos por candidato 1 y candidato 2;
  - IDs de filas unresolved con `player_id` y `fixture_id`;
  - divergencias `player_events.team_id <> player_stats.team_id`;
  - eventos sin `player_stats` correspondiente.
  El script puede ejecutarse antes y despues del backfill.

- [x] 6. Ejecutar `0021` y auditoria sobre copia de DB.
  Criterio: se guardan conteos antes/despues. Si hay unresolved, se identifican por ID
  y se documenta la estrategia de recuperacion (reingesta, correccion manual).
  La ingesta del Mundial queda bloqueada hasta contadores criticos = 0.

- [x] 7. Crear `migrations/0022_player_team_snapshots_constraints.sql`.
  Criterio: solo contiene `ALTER player_stats ALTER team_id SET NOT NULL` y
  `ALTER player_events ALTER team_id SET NOT NULL`. No modifica otras columnas.
  Incluye comentario explicito: "ejecutar solo con contadores criticos = 0".

- [x] 8. Agregar `team_id` al modelo ORM `PlayerStats`.
  Criterio: FK nullable a `teams.id`, indice `(team_id, season)`, comentario de
  snapshot inmutable.

- [x] 9. Agregar `team_id` al modelo ORM `PlayerEvent`.
  Criterio: FK nullable a `teams.id`, indice `(team_id, fixture_id)`.

- [x] 10. Agregar `participant_kind` al modelo ORM `Competition`.
  Criterio: `String(20)` con server_default `club`. El CHECK constraint esta en la
  migracion; el modelo no lo duplica.

- [x] 11. Agregar `participant_kind` a `LeagueConfig`.
  Criterio: campo con default `"club"`. Competiciones existentes no requieren cambio.

- [x] 12. Marcar `players.team_id` como nullable y deprecado en el modelo ORM.
  Criterio: la columna es `nullable=True`; se agrega comentario `# deprecated: do not write`.
  Ningun use case escribe en este campo despues del cutover.

- [x] 13. Actualizar `IngestionRepositoryPort.upsert_player`.
  Criterio: eliminar parametro `team_id` del contrato. Todos los callers actualizados.

- [x] 14. Actualizar `IngestionRepositoryPort.upsert_player_stats`.
  Criterio: agregar `team_id: int` como parametro obligatorio.

- [x] 15. Actualizar `IngestionRepositoryPort.upsert_player_event`.
  Criterio: agregar `team_id: int` como parametro obligatorio.

- [x] 16. Actualizar `IngestionRepository.upsert_player`.
  Criterio: el `ON CONFLICT DO UPDATE` no incluye `team_id`. Solo actualiza nombre,
  foto y posicion.

- [x] 17. Actualizar `IngestionRepository.upsert_player_stats`.
  Criterio: escribe `team_id` en la fila persistida.

- [x] 18. Actualizar `IngestionRepository.upsert_player_event`.
  Criterio: escribe `team_id` en la fila persistida.

- [x] 19. Actualizar `IngestCompetitionUseCase`.
  Criterio: determina `proc_team_db_id` por lado del fixture usando `participant_kind`.
  Valida explicitamente que el equipo sea `home_team_id` o `away_team_id` antes de
  persistir. Lanza `ValueError` con mensaje claro si no coincide.

- [x] 20. Actualizar `ReingestPlayerUseCase` y `get_fixtures_for_player`.
  Criterio: `PlayerFixtureInfoRow.player_team_id` proviene de `PlayerStats.team_id`.
  Local/visitante se calcula con el snapshot. No lee `Player.team_id`.

- [x] 21. Corregir `TeamStrengthRepository.get_fixtures_for_elo_recalc`.
  Criterio: usa el COALESCE validado contra fixture definido en decisions.md. Si el
  resultado es NULL, el fixture se registra en log de auditoria y se excluye del
  calculo. No continua silenciosamente.

- [x] 22. Corregir `CompetitionAchievementRepository.get_team_total_minutes`.
  Criterio: filtra `player_stats.team_id = :team_id`. No usa `Player.team_id`.

- [x] 23. Corregir `CompetitionAchievementRepository.get_players_for_team_season`.
  Criterio: filtra `player_stats.team_id = :team_id`. No usa `Player.team_id`.

- [x] 24. Corregir `CompetitionAchievementRepository.get_player_rank_in_team`.
  Criterio: usa `sfa_season_scores.team_id` del alcance de la competicion para
  determinar el ranking interno. No une `players` para obtener equipo.

- [x] 25. Corregir `InferAchievementsRepository`.
  Criterio: agrupa goles por `player_events.team_id`. No usa `Player.team_id`.

- [x] 26. Corregir `PlayerEventScoreRepository.bulk_rebuild_season_scores`.
  Criterio: el CTE deriva `team_id` representativo desde `player_stats` por
  `(player_id, competition_id, season)` con mayor suma de minutos. No une `players`.

- [x] 27. Corregir `sfa_score_repository.py` (lineas 43, 211, 433).
  Criterio: los tres joins o filtros que usan `Player.team_id` se reemplazan por
  `sfa_season_scores.team_id` o por la logica de resolucion de fallback definida
  en decisions.md. Ningun jugador valido desaparece del ranking si su `players.team_id`
  es NULL.

- [x] 28. Corregir `scoring_repository.py`.
  Criterio: la lectura de equipo para construccion de scores usa snapshot, no
  `Player.team_id`.

- [x] 29. Corregir `enrich_position_repository.py`.
  Criterio: el filtro de contexto de enriquecimiento usa la ultima aparicion en
  `player_stats` para el equipo, no `Player.team_id`.

- [x] 30. Corregir fallback de perfil en `PlayerRepository`.
  Criterio: resuelve equipo desde `player_stats` siguiendo la jerarquia definida en
  decisions.md. No lee `players.team_id` como fuente primaria.

- [x] 31. Test: snapshot correcto en ingestion como local y como visitante.
  Criterio: ingestar un fixture con el jugador en cada lado produce
  `player_stats.team_id` y `player_events.team_id` correctos en ambos casos.

- [x] 32. Test: validacion home/away en ingestion.
  Criterio: `team_id` distinto de `home_team_id` y `away_team_id` produce `ValueError`
  antes de persistir. Ningun dato se escribe en la DB.

- [x] 33. Test: mismo `player_id` con club y seleccion.
  Criterio: mismo `external_id`, primero un fixture de liga, luego uno del Mundial.
  Resultado: un unico `players.id`, dos filas de `player_stats` con `team_id` distinto,
  `players.team_id` sin modificar en ninguno de los dos procesos.

- [x] 34. Test: jugador nuevo durante la transicion (entre 0021 y 0022).
  Criterio: insertar un jugador cuando `players.team_id` es nullable (post-0021, pre-0022)
  no produce error NOT NULL. La fila se crea correctamente sin `team_id`.

- [x] 35. Test: ranking sin `Player.team_id` (columna NULL).
  Criterio: un jugador con `players.team_id = NULL` aparece en el ranking si tiene
  `sfa_season_scores` validos. No desaparece de la respuesta.

- [x] 36. Test: jugador transferido con snapshot historico unresolved.
  Criterio: una fila de `player_stats` con `team_id = NULL` no rompe el calculo de ELO
  ni los logros. El fixture se excluye del ELO con log; los logros usan solo filas con
  snapshot valido.

- [x] 37. Test: COALESCE ELO devuelve NULL cuando `players.team_id` no coincide con fixture.
  Criterio: si `players.team_id` no es home ni away del fixture historico, el fallback
  produce NULL y el fixture se registra en auditoria. No se asigna un equipo arbitrario.

- [x] 38. Test: `get_player_rank_in_team` usa snapshot.
  Criterio: el ranking interno del equipo se calcula con `sfa_season_scores.team_id`,
  no con `Player.team_id`.

- [x] 39. Test: rebuild preserva `team_id` por aparicion.
  Criterio: despues de `bulk_rebuild_season_scores`, `sfa_season_scores.team_id`
  refleja el equipo con mayor suma de minutos segun `player_stats`, no `players.team_id`.

- [x] 40. Actualizar Fakes en tests existentes de reingesta, logros, ELO e inferencia.
  Criterio: todos los Fakes implementan los nuevos parametros `team_id`. Ningun test
  usa `Player.team_id` para logica de negocio.

- [x] 41. Ejecutar busqueda de referencias residuales.
  Criterio: `rg "Player\.team_id|p\.team_id" src/` no encuentra lecturas ni escrituras
  de negocio. Solo quedan modelo ORM, migracion y comentario de deprecacion.
  Resultado: solo queda el fallback transitorio validado de ELO exigido por
  decisions.md; no quedan otras lecturas de negocio.

- [x] 42. Ejecutar calidad estatica.
  Criterio: `flake8 src/ tests/` e `isort --check-only src/ tests/` sin errores nuevos.

- [x] 43. Ejecutar suite completa.
  Criterio: `pytest tests/` pasa o solo conserva fallos preexistentes del item 1.

- [x] 44. Commit en rama `refactor/SFA-0028-player-team-snapshots`.
  Criterio: `git diff main -- src/sfa/domain/scoring/` esta vacio. El diff no incluye
  cambios a `SFAScoringService`, `BASE_POINTS_TABLE` ni multiplicadores.

## Verificacion end-to-end (antes de habilitar Mundial)

1. Ejecutar `0021` sobre copia de DB.
2. Revisar auditoria. Si hay unresolved: reingesta o correccion manual hasta cero.
3. Desplegar codigo nuevo.
4. Verificar que insertar un jugador nuevo no falla.
5. Reingestar un fixture de La Liga de muestra; verificar snapshot correcto.
6. Comparar `sfa_season_scores` antes y despues: `total_pts` identico.
7. Verificar ELO del equipo del fixture: sin cambio.
8. Verificar logros del equipo: mismos jugadores seleccionados.
9. Con contadores criticos = 0: ejecutar `0022`.
10. Solo tras completar paso 9: habilitar ingesta del Mundial.
