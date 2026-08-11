# Plan: ELO temporal y baseline autoritativo para M1

## Archivos a crear

- [ ] `migrations/0048_temporal_elo_m1.sql` - crea seeds y snapshots temporales, agrega marcador oficial y sus indices/constraints.
- [ ] `src/sfa/infrastructure/models/team_elo_seeds/__init__.py` - export del modelo de baseline.
- [ ] `src/sfa/infrastructure/models/team_elo_seeds/models.py` - persistencia canonica y auditable del seed.
- [ ] `src/sfa/infrastructure/models/fixture_team_strengths/__init__.py` - export del modelo temporal.
- [ ] `src/sfa/infrastructure/models/fixture_team_strengths/models.py` - snapshots ELO pre/post por fixture y equipo.
- [ ] `src/sfa/application/use_cases/rebuild_elo_timeline.py` - valida coverage, reproduce el pool y persiste snapshots y estado terminal.
- [ ] `tests/use_cases/test_rebuild_elo_timeline.py` - reglas de temporalidad, coverage, orden e idempotencia con Fake completo.
- [ ] `tests/repositories/test_elo_timeline_repository.py` - joins, reemplazo atomico, constraints y lectura temporal.
- [ ] `tests/tasks/test_elo_timeline_tasks.py` - orden ELO -> commit -> scoring y exclusividad del lock.
- [x] `specs/refactor/0048-temporal-elo-m1/decisions.md` - auditoria y decisiones arquitectonicas.
- [x] `specs/refactor/0048-temporal-elo-m1/plan.md` - contrato exhaustivo de implementacion.

## Archivos a modificar

- [ ] `src/sfa/domain/ingestion_ports.py` - extender el upsert de fixture con marcador oficial y source.
- [ ] `src/sfa/domain/scoring_ports.py` - agregar DTOs y un port dedicado para seed/timeline ELO.
- [ ] `src/sfa/infrastructure/models/fixtures/models.py` - agregar `home_goals`, `away_goals` y `score_source`.
- [ ] `src/sfa/infrastructure/models/__init__.py` - registrar los dos modelos nuevos.
- [ ] `src/sfa/application/use_cases/ingest_competition.py` - pasar marcador oficial al repositorio.
- [ ] `src/sfa/application/use_cases/seed_clubelo.py` - sembrar todos los equipos activos requeridos y escribir provenance canonica.
- [ ] `src/sfa/application/use_cases/seed_national_team_elo.py` - escribir el mismo contrato de seed para selecciones.
- [ ] `src/sfa/application/use_cases/calculate_elo_ratings.py` - retirar la responsabilidad de replay terminal o dejar un wrapper compatible que delegue al timeline.
- [ ] `src/sfa/infrastructure/providers/clubelo_provider.py` - soportar resolucion del scope activo sin excluir equipos por `level`.
- [ ] `src/sfa/infrastructure/repositories/ingestion_repository.py` - persistir y actualizar marcador/source de fixture.
- [ ] `src/sfa/infrastructure/repositories/team_strength_repository.py` - implementar seed/timeline, official score reads y proyeccion terminal sin `MAX` incoherente.
- [ ] `src/sfa/infrastructure/repositories/player_event_score_repository.py` - leer strengths pre-match por fixture y fallar si falta coverage.
- [ ] `src/sfa/tasks/elo_tasks.py` - coordinar replay completo, transaccion, lock comun y recalc posterior.
- [ ] `src/sfa/tasks/ingestion_tasks.py` - disparar el coordinador por pool sin carreras ni replay parcial.
- [ ] `src/sfa/tasks/recalculate_award_period_task.py` - usar timeline de clubes/selecciones antes del full recalculation.
- [ ] `src/sfa/api/v1/elo_router.py` - enrutar el recalc admin existente al flujo temporal y exponer coverage en su respuesta.
- [ ] `src/sfa/api/v1/schemas/elo_schemas.py` - agregar coverage, snapshots y blockers al contrato admin existente.
- [ ] `src/sfa/core/dependencies.py` - wiring exclusivo del use case y repository nuevos.
- [ ] `tests/use_cases/test_calculate_elo_ratings.py` - eliminar la expectativa de default silencioso y cubrir compatibilidad del wrapper.
- [ ] `tests/use_cases/test_seed_clubelo.py` - cubrir ascendidos, niveles inferiores activos, provenance y unmatched bloqueante.
- [ ] `tests/use_cases/test_seed_national_team_elo.py` - cubrir el contrato comun de seed.
- [ ] `tests/use_cases/test_team_snapshot_repositories.py` - comprobar que scoring usa fixture snapshots, no terminal season strength.
- [ ] `tests/use_cases/test_calculate_scores_for_rules_version.py` - comprobar M1 temporal y calculation details auditables.
- [ ] `http/elo.http` - documentar seed, coverage, dry-run/replay y errores bloqueantes del endpoint existente.

## Checklist de implementacion

### Fase 0 - Baseline y auditoria operativa

- [ ] Ejecutar `pytest tests/` con un entorno valido y registrar fallos preexistentes antes de editar.
- [ ] Registrar como baseline enfocado que las 50 pruebas actuales de ELO/M1 pasan con `DEBUG=false`.
- [ ] Consultar 2025 para Liverpool, Bournemouth y Leeds: `elo_raw`, `elo_seed_raw`, `strength`, `source` y replicas por competicion.
- [ ] Verificar si sus `elo_seed_raw` son exactamente 1500 y documentar cuales fueron inicializados por `club_elo_v2`.
- [ ] Comparar los marcadores reconstruidos desde `PlayerStats` con API-Football/eventos para todos los fixtures ELO.
- [ ] Inventariar fixtures `FT/AET/PEN` sin score oficial, con stats incompletas o excluidos por team snapshot.
- [ ] Confirmar la fecha de corte ClubElo usada para 2025 y producir lista de equipos activos matched/unmatched.
- [ ] Guardar un backup operativo de `team_strengths`, `player_event_scores` y `sfa_season_scores` antes del rollout; el backup no forma parte del commit.

### Fase 1 - Migracion y modelos

- [ ] Crear `team_elo_seeds` con FKs, provenance, unique por equipo/temporada/pool e indices de cobertura.
- [ ] Crear `fixture_team_strengths` con pre/post ELO, pre/post strength, model version, seed source y unique por fixture/equipo.
- [ ] Agregar checks de strength 0-100, ELO positivo y `participant_kind IN ('club', 'national_team')`.
- [ ] Agregar `fixtures.home_goals`, `fixtures.away_goals` y `fixtures.score_source` como nullable para expand seguro.
- [ ] No backfillear null scores como 0-0 en la migracion.
- [ ] Registrar los modelos nuevos en infrastructure sin exponer ORM al dominio.
- [ ] Definir rollback documentado que elimina primero snapshots/seeds y luego columnas de fixture.

### Fase 2 - Marcador oficial

- [ ] Extender `IngestionRepositoryPort.upsert_fixture` de forma aditiva con goles y source.
- [ ] Pasar `FixtureRawDTO.home_goals/away_goals` desde `IngestCompetitionUseCase`.
- [ ] Hacer upsert del marcador aunque el fixture ya estuviera marcado como completado.
- [ ] Preservar null para fixtures programados y aceptar 0 como resultado real, sin usar `or 0` sobre null prematuro.
- [ ] Definir source `api_football`, `manual` o `verified_backfill` para cada score persistido.
- [ ] Cambiar la lectura ELO para usar solo `Fixture.home_goals/away_goals` oficiales.
- [ ] Rechazar antes de escribir cualquier snapshot si un fixture finalizado del scope no tiene ambos goles.
- [ ] Cubrir own goals y partidos 0-0 para demostrar que ELO no depende de stats individuales.

### Fase 3 - Baseline canonico

- [ ] Agregar `TeamEloSeedDTO` frozen y metodos de seed al port de dominio.
- [ ] Implementar upsert y lectura exacta de seeds sin agregaciones `MAX` entre replicas.
- [ ] Resolver el conjunto requerido desde fixtures del pool, no desde `ClubElo.level`.
- [ ] Remover el filtro `entry.level != 1` para equipos activos requeridos.
- [ ] Persistir fecha efectiva, provider, referencia de source y nombre resuelto.
- [ ] Fallar el seed si cualquier equipo requerido queda unmatched o sin ELO.
- [ ] Permitir override solo mediante operacion explicita con source, razon y valor auditables.
- [ ] Eliminar `initialize_missing_seed_baseline=True` de todos los callers de clubes.
- [ ] Impedir que `require_seed_baseline=True` pueda ser neutralizado por inicializacion previa.
- [ ] Mantener `elo_seed_raw` legacy durante compatibilidad, pero no usarlo como fuente del nuevo replay.
- [ ] Agregar test de regresion: Liverpool, Bournemouth y Leeds no reciben automaticamente el mismo 1500.

### Fase 4 - Replay temporal

- [ ] Implementar `EloTimelineRepositoryPort` con lectura de seeds/fixtures, reemplazo de snapshots y escritura terminal.
- [ ] Crear `RebuildEloTimelineUseCase` sin imports de SQLAlchemy ni manejo de commit.
- [ ] Validar cobertura total de equipos y scores antes de iniciar escrituras.
- [ ] Separar pools por `participant_kind` y no mezclar clubes con selecciones.
- [ ] Cargar todos los fixtures finalizados del pool de clubes, incluyendo liga y copas.
- [ ] Ordenar de forma estable por `(played_at ASC, fixture_id ASC)`.
- [ ] Para cada fixture, capturar los ELO/strength de ambos equipos antes de aplicar el resultado.
- [ ] Aplicar el K factor correspondiente y completar ELO/strength post-match.
- [ ] Mantener el K nacional configurable y documentar el K de clubes vigente; no cambiar valores en este spec sin calibracion separada.
- [ ] Reemplazar todos los snapshots del scope y la proyeccion terminal dentro de una sola unidad de trabajo.
- [ ] Actualizar `team_strengths` con el ultimo estado de cada equipo solo como proyeccion vigente.
- [ ] No replicar baseline mediante `MAX`; cada equipo debe tener un unico seed canonico.
- [ ] Retornar coverage, blockers, fixtures, snapshots y equipos actualizados en el result.
- [ ] Probar idempotencia comparando todos los snapshots de dos replays iguales.
- [ ] Probar no-leakage: modificar un resultado y confirmar que no cambia ningun pre-match anterior.
- [ ] Probar que el pre-match del propio fixture tampoco incorpora su resultado.

### Fase 5 - M1 temporal

- [ ] Cambiar `PlayerEventScoreRepository.get_events_for_recalc` para unir dos aliases de `fixture_team_strengths` por `fixture_id` y team_id.
- [ ] Asignar player/rival strength conservando la logica home/away actual.
- [ ] Dejar de unir `team_strengths` terminal en el hot path de eventos.
- [ ] Tras el cutover, fallar el recalculo si cualquiera de los dos snapshots del fixture falta.
- [ ] No caer silenciosamente a standings o ELO terminal cuando falta timeline.
- [ ] Mantener sin cambios la formula, divisor y clamps de `M1RivalDifficulty`.
- [ ] Agregar a `calculation_details`: model version, seed source, player/rival pre-match ELO y strengths.
- [ ] Testear que dos fixtures del mismo equipo pueden producir M1 distintos por progresion temporal.
- [ ] Testear que todos los eventos de un mismo fixture comparten exactamente los mismos inputs M1.
- [ ] Testear Bournemouth-Liverpool y Leeds-Liverpool con seeds/fixtures controlados y verificar que M1 coincide con la formula, sin hardcodear jerarquias de clubes.

### Fase 6 - Orquestacion y concurrencia

- [ ] Construir use case/repository solo en `core/dependencies.py` para HTTP.
- [ ] Mantener late imports y session ownership en las tasks Celery.
- [ ] Unificar advisory lock por `(participant_kind, season)` para ingestion, admin y award-period recalc.
- [ ] Ejecutar seed coverage/replay y commit antes del full scoring recalculation.
- [ ] No disparar scoring si timeline retorna failed o coverage incompleta.
- [ ] Evitar locks 40/41 divergentes que permitan dos reconstrucciones del mismo pool.
- [ ] Hacer que `recalculate_award_period_task` reconstruya una vez cada pool/season, no una vez por source duplicado.
- [ ] Hacer que ingestion agrupe competition ids y reproduzca siempre el pool completo.
- [ ] Mantener clubs y national teams como pasos separados bajo el mismo contrato temporal.
- [ ] Actualizar el endpoint admin ELO existente; no crear un router paralelo.
- [ ] Incluir dry-run/coverage para ver blockers sin modificar scores.
- [ ] Invalidar caches y regenerar explicaciones solo despues de un recalc exitoso.

### Fase 7 - Backfill y cutover 2025

- [ ] Completar marcadores oficiales 2025 desde API-Football o carga manual autoritativa.
- [ ] Marcar la provenance de cada score backfilleado y revisar todos los ambiguos.
- [ ] Re-seedear todos los clubes activos desde ClubElo a una fecha anterior al primer fixture 2025.
- [ ] No copiar como canonicos los `elo_seed_raw=1500` ambiguos creados por 0045.
- [ ] Resolver explicitamente unmatched y aprobar cualquier override antes de continuar.
- [ ] Ejecutar dry-run y exigir 100% de coverage de equipos, fixtures y scores.
- [ ] Construir snapshots sin recalcular puntos y auditar la progresion de Liverpool, Bournemouth y Leeds.
- [ ] Verificar que el ELO terminal coincide con el ultimo post-match de cada equipo.
- [ ] Ejecutar el recalculo completo de `season-2025` solo despues de aprobar la auditoria.
- [ ] Reconstruir season scores, logros, honores, ranking explanations y caches por el flujo existente.
- [ ] Comparar el total de Szoboszlai antes/despues y explicar la diferencia por fixtures y M1.
- [ ] Mantener un reporte de rollback con IDs de task, fecha de seed, model version y conteos.

### Fase 8 - Tests y calidad

- [ ] Actualizar todos los Fakes para implementar los ports completos; no usar `MagicMock`.
- [ ] Cubrir seed incompleto, score faltante, unmatched, override explicito y transaccion fallida.
- [ ] Cubrir orden estable cuando dos fixtures tienen el mismo `played_at`.
- [ ] Cubrir un equipo en varias competiciones sin duplicar ni mezclar el timeline.
- [ ] Cubrir pools club/national aislados en la misma season.
- [ ] Cubrir que una falla de replay conserva snapshots y scores anteriores.
- [ ] Ejecutar pruebas enfocadas de ELO, repositories, tasks y scoring M1.
- [ ] Ejecutar `pytest tests/` y verificar coverage global >=80%.
- [ ] Ejecutar `flake8 src/ tests/`.
- [ ] Ejecutar `isort --check-only src/ tests/`.
- [ ] Ejecutar `git diff --check`.

## Agent Routing Brief

**DDD Designer needed:** no

No se agrega una entidad de negocio, aggregate, accion ni multiplicador. Los nuevos conceptos son
DTOs frozen y read models tecnicos para preservar la temporalidad de un calculo existente. La
formula ELO y `M1RivalDifficulty` no cambian; el trabajo corresponde a ports, use cases,
repositories, persistencia y orquestacion. Si durante implementacion se propone cambiar la
formula M1, K factors o introducir un nuevo criterio futbolistico de fuerza, ese cambio queda
fuera de 0048 y requiere una nueva decision de dominio.

## Verificacion

1. Ejecutar coverage para club/2025 y obtener 100% de equipos con seed autoritativo y 100% de
   fixtures ELO con marcador oficial.
2. Ejecutar dos replays consecutivos y comparar hashes/conteos de `fixture_team_strengths` y
   valores terminales; deben ser identicos.
3. Consultar dos filas por fixture y confirmar que el pre-match de cada equipo coincide con el
   post-match de su fixture cronologico anterior, o con el seed si es su debut.
4. Confirmar que Bournemouth-Liverpool y Leeds-Liverpool leen sus snapshots por fixture y que
   el M1 almacenado coincide con `1 + (rival_strength - player_strength) / 200`, sujeto al clamp.
5. Confirmar que un resultado posterior no cambia el M1 de un partido anterior.
6. Ejecutar recalc de `season-2025` y auditar el desglose de Szoboszlai, incluyendo ELO pre-match,
   model version y diferencia de puntos por fixture.
7. Verificar que Mundial 2026 usa el mismo contrato temporal con su seed y K nacional, sin filas
   de clubes dentro del pool.
8. Forzar un seed o score faltante en test/staging y confirmar que ELO y scoring fallan antes de
   reemplazar datos previos.

## Criterios de aceptacion

- Ningun evento recalculado usa el ELO terminal de temporada como contexto historico.
- Ningun club requerido recibe 1500 por omision silenciosa.
- Ningun fixture ELO deriva su resultado desde la suma de goles de jugadores.
- Cada M1 puede rastrearse a dos snapshots pre-match, un seed y un marcador oficial.
- El replay completo es atomico, determinista e idempotente.
- El detalle de jugador muestra valores coherentes con la linea temporal persistida.
