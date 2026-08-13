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
- [x] `src/sfa/application/use_cases/backfill_fixture_scores.py` - valida cobertura y marcador oficial antes de cualquier escritura.
- [x] `src/sfa/infrastructure/repositories/fixture_score_backfill_repository.py` - limita el backfill a fixtures finalizados sin score autoritativo.
- [x] `scripts/backfill_fixture_scores.py` - operacion idempotente con dry-run por defecto y apply transaccional.
- [x] `tests/use_cases/test_backfill_fixture_scores.py` - cobertura, blockers, batches e idempotencia.
- [x] `tests/providers/test_api_football_fixture_scores.py` - contrato del batch oficial y separacion de tanda.
- [x] `tests/repositories/test_fixture_score_backfill_repository.py` - seleccion y escritura aislada de marcadores.
- [x] `specs/refactor/0048-temporal-elo-m1/decisions.md` - auditoria y decisiones arquitectonicas.
- [x] `specs/refactor/0048-temporal-elo-m1/plan.md` - contrato exhaustivo de implementacion.
- [ ] `migrations/0049_clubelo_historical_seed_provenance.sql` - agrega provenance JSONB sin reescribir la migracion 0048 ya desplegada.
- [ ] `tests/repositories/test_team_elo_seed_provenance_repository.py` - round-trip y validacion de evidencia estructurada.
- [ ] `tests/api/test_elo_router.py` - contrato dry-run/apply, reportes y traduccion 422/503 del seed de clubes.

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

## Extension 0048-A - Historial individual de ClubElo

### Fase A0 - Contrato y baseline verificable

- [ ] Registrar como baseline operativo el dry-run 2025 con 356 equipos requeridos, 258 resueltos por snapshot y 98 unmatched; completado cuando el artefacto conserva fecha, cutoff y lista completa.
- [ ] Confirmar desde fixtures que el cutoff club/2025 es exactamente el dia UTC anterior al primer fixture del pool; completado cuando la consulta y el valor esperado quedan en el reporte de rollout.
- [ ] Capturar ejemplos reales de CSV diario e individual con columnas `Rank,Club,Country,Level,Elo,From,To`; completado cuando los fixtures de test no inventan un contrato distinto al provider.
- [ ] Clasificar los 98 equipos como alias verificado, historial ausente, historial stale, identidad ambigua o manual requerido; completado cuando ninguno queda solo bajo la etiqueta generica `unmatched`.
- [ ] Registrar el riesgo de transporte HTTP de ClubElo y confirmar que no existe HTTPS funcional en el entorno de rollout; completado cuando la decision operativa referencia allowlist y checksum.

### Fase A1 - Port y DTOs de integracion

- [ ] Agregar `ClubEloRatingDTO` frozen con club, country, level, elo, valid_from y valid_to; completado cuando application no importa `ClubEloEntry` desde infrastructure.
- [ ] Agregar `ClubEloSourceDTO` frozen con source reference, fetched_at, payload SHA-256 y ratings; completado cuando snapshot e historial usan el mismo envelope.
- [ ] Agregar `ClubEloIdentityDTO` frozen con nombre SFA, identificador ClubElo y pais esperado; completado cuando una identidad individual no se representa con un dict unidireccional.
- [ ] Agregar `EloSeedProvenanceDTO` frozen con resolution method, identidad, intervalo, age, locator y checksum; completado cuando `TeamEloSeedDTO` transporta evidencia sin JSON infra-specific.
- [ ] Agregar `ClubEloSeedResolutionDTO` frozen con status y blocker por equipo; completado cuando el use case puede reportar snapshot/history/manual/unresolved/stale/ambiguous/provider_error.
- [ ] Definir `ClubEloProviderPort` con operaciones de snapshot e historiales individuales; completado cuando `SeedClubEloUseCase` recibe el Protocol tipado y no una dependencia sin tipo.
- [ ] Mantener HTTP, CSV y retry semantics fuera de application; completado cuando el port no expone `httpx.Response`, texto CSV ni excepciones de la libreria HTTP.
- [ ] Actualizar todos los Fakes que implementan los ports completos; completado cuando `isinstance(fake, ClubEloProviderPort)` es valido donde se use runtime checking.

### Fase A2 - Identidad autoritativa

- [ ] Reemplazar el mapa unidireccional por registros bidireccionales univocos con `sfa_team_name`, `clubelo_identifier` y `expected_country`; completado cuando cada identificador registrado apunta a un solo equipo SFA.
- [ ] Migrar aliases actuales comprobados al catalogo sin agregar similitudes especulativas; completado cuando cada alta tiene fixture de test con pais esperado.
- [ ] Resolver snapshot por exact match, normalizacion unica o alias verificado; completado cuando dos candidatos normalizados iguales producen `ambiguous` y no el primero de la lista.
- [ ] Exigir identificador explicito y pais para abrir un historial individual; completado cuando nombres ambiguos como `Lincoln` no generan request automatico sin registro.
- [ ] Convertir fuzzy matching en sugerencia de auditoria solamente; completado cuando ningun resultado fuzzy incrementa matched ni crea un seed.
- [ ] Validar que club y country de la respuesta individual coinciden con la identidad registrada; completado cuando un country mismatch genera blocker.
- [ ] Rechazar redirects fuera de `api.clubelo.com` y percent-encodear el path; completado con tests de URL y redirect hostil.

### Fase A3 - Seleccion historica y antiguedad

- [ ] Parsear `From` y `To` del snapshot y del historial como fechas obligatorias; completado cuando una fecha invalida clasifica el payload como provider-invalid.
- [ ] Filtrar filas a ELO positivo, `From <= To` y `From <= cutoff`; completado cuando una fila futura nunca es candidata.
- [ ] Elegir deterministicamente la fila con mayor `From`; completado cuando el orden del CSV no altera el resultado.
- [ ] Deduplicar filas con el mismo `From` solo si identidad, country, ELO y `To` son identicos; completado cuando valores conflictivos retornan `ambiguous`.
- [ ] Calcular `history_age_days = max(0, cutoff - To)`; completado con casos de intervalo vigente, fila anterior y fecha limite.
- [ ] Aceptar `exact_at_cutoff` cuando `From <= cutoff <= To`; completado cuando queda source `clubelo_history` y age 0.
- [ ] Aceptar `prior_carry_forward` entre 1 y 365 dias; completado cuando queda source `clubelo_history_prior` y el age exacto persiste.
- [ ] Aceptar exactamente 365 dias y bloquear 366; completado con dos tests de frontera independientes.
- [ ] Fijar `max_staleness_days=365` como constante inclusiva de application; completado cuando no existe override por request, settings o environment.
- [ ] Cubrir el corte operativo 2025-07-07: Cardiff, Eldense y Regensburg con gap 2 aceptados; completado cuando quedan `clubelo_history_prior`.
- [ ] Cubrir el corte operativo 2025-07-07: Concarneau, Rostock, Huddersfield y Wehen con gap 367 rechazados; completado cuando quedan `stale` y cero writes.
- [ ] Cubrir el corte operativo 2025-07-07: Sochaux, Wigan y Sandhausen con gap 737 rechazados; completado cuando quedan `stale` y cero writes.
- [ ] Rechazar un historial vacio o sin fila elegible como `no_history`; completado cuando puede pasar al fallback manual sin inventar ELO.
- [ ] Mantener el limite 365 dentro de la policy de application y fuera del request/settings; completado cuando el caller no puede ampliarlo.
- [ ] Probar no-future-leakage agregando filas posteriores al mismo historial; completado cuando el seed para el cutoff permanece identico.

### Fase A4 - Fallback manual auditable

- [ ] Extender `ManualClubEloEntry` y schema con `source_reference`, `source_date` y `approved_by`; completado cuando los cinco campos de evidencia son validados antes de provider writes.
- [ ] Rechazar source_date posterior al cutoff, team_name ajeno al pool, valor no positivo y evidencia vacia; completado con un test por blocker.
- [ ] Rechazar manual entries duplicadas para el mismo equipo; completado cuando el resultado es determinista e independiente del orden.
- [ ] Aplicar manual entries solo a equipos aun irresueltos; completado cuando un manual no reemplaza snapshot ni historial.
- [ ] Etiquetar siempre la procedencia manual como `manual_override`; completado cuando no existe ruta que la persista como `clubelo_snapshot` o `clubelo_history`.
- [ ] Incluir reason, source_reference, source_date y approved_by en provenance; completado con round-trip repository.

### Fase A5 - Persistencia de provenance

- [ ] Crear migracion 0049 aditiva con `team_elo_seeds.provenance_json JSONB NOT NULL DEFAULT '{}'`; completado cuando aplica sobre una DB que ya tiene 0048 y preserva filas existentes.
- [ ] Agregar check DB `jsonb_typeof(provenance_json) = 'object'`; completado cuando un valor no objeto es rechazado.
- [ ] Actualizar modelo SQLAlchemy y DTO de seed sin exponer JSONB a application; completado cuando repository serializa y reconstruye `EloSeedProvenanceDTO`.
- [ ] Persistir para ClubElo resolution method, entity, country, valid interval, age, cutoff, locator y SHA-256; completado cuando ninguna clave requerida falta en un seed nuevo.
- [ ] Mantener `effective_at` como cutoff y no sustituirlo por `From` o `To`; completado con test de persistencia.
- [ ] Mantener `source_reference` como locator corto y provenance como evidencia estructurada; completado cuando ambos valores coinciden con el mismo recurso.
- [ ] Considerar invalido para el nuevo gate todo seed de club legacy con provenance vacia; completado cuando coverage lo reporta y obliga a re-seed.
- [ ] No aplicar requisitos ClubElo a seeds `national_team`; completado cuando las pruebas nacionales existentes siguen pasando sin metadata de club.
- [ ] Documentar rollback de 0049 como drop exclusivo de la nueva columna/check; completado sin alterar seeds, snapshots ni columnas de fixture de 0048.

### Fase A6 - Orquestacion fail-closed

- [ ] Agregar al repository port la lectura de la fecha del primer fixture por season/participant_kind; completado cuando el use case deriva el cutoff sin ORM.
- [ ] Exigir que `date_str` coincida con `first_fixture_date - 1 day`; completado cuando un cutoff distinto retorna blocker con expected/received.
- [ ] Validar request, cutoff y manual manifest antes de la primera llamada externa; completado cuando input invalido realiza cero requests.
- [ ] Resolver primero el snapshot y consultar historial solo para ausentes con identidad verificada; completado cuando un match diario realiza cero history requests.
- [ ] Deduplicar history requests por identificador y limitar concurrencia a 5; completado cuando el fake registra max concurrency <=5 y una llamada por identifier.
- [ ] Permitir un retry acotado para timeout, 429 y 5xx, respetando `Retry-After` acotado; completado cuando el segundo fallo retorna provider_error sin loop adicional.
- [ ] No reintentar 404 ni CSV vacio; completado cuando ambos se clasifican no_history en una sola llamada.
- [ ] Completar todas las lecturas y validaciones antes del primer upsert; completado cuando un blocker tardio deja `upserted_seeds` y `upserted_elos` vacios.
- [ ] Exigir cero blockers y 100% coverage para apply; completado cuando 355/356 no escribe ninguna fila.
- [ ] Mantener commit/rollback exclusivamente en router/task; completado cuando el use case no importa session ni llama commit.
- [ ] Verificar que una excepcion durante persistencia revierte seeds y proyecciones en integration test; completado cuando el estado anterior permanece intacto.

### Fase A7 - Contrato admin y observabilidad

- [ ] Agregar `dry_run: bool = True` a `SeedClubEloRequest`; completado cuando omitir el campo realiza cero escrituras.
- [ ] Exigir `dry_run=false` explicito para apply; completado cuando el caso HTTP apply persiste solo con cobertura completa.
- [ ] Extender response con cutoff, total, coverage_pct, counts por source, history_requests, blockers y resolutions; completado cuando los 98 ausentes pueden diagnosticarse sin logs internos.
- [ ] Traducir coverage/manual/stale/ambiguous a HTTP 422; completado con tests parametrizados del router.
- [ ] Traducir timeout/429/5xx/payload invalido a HTTP 503; completado sin perder el blocker report.
- [ ] Mantener log resumen sin payloads completos: season, cutoff, dry_run, totals por source y blockers; completado cuando no se imprimen manual evidence ni CSV completos.
- [ ] Actualizar `http/elo.http` con dry-run, apply, history, stale, no-history y manual evidence; completado cuando cada caso declara el resultado esperado.
- [ ] Conservar el endpoint existente `/api/v1/admin/elo/seed`; completado cuando no aparece un router paralelo para history.

### Fase A8 - Tests y gates de calidad

- [ ] Extender `tests/providers/test_clubelo_provider.py` con parsing de intervalos, checksum, URL encoding, pais, redirects y errores HTTP; completado cuando no requiere red real.
- [ ] Extender `tests/use_cases/test_seed_clubelo.py` con precedencia snapshot/history/manual y todos los estados de resolution; completado usando Fakes completos, no MagicMock.
- [ ] Agregar test de snapshot valido que gana sobre history y manual; completado cuando el ELO diario es el unico persistido.
- [ ] Agregar test de history exact-at-cutoff y prior de 365 dias; completado cuando source y provenance difieren correctamente.
- [ ] Agregar tests de 366 dias, future-only, country mismatch, duplicate conflict y no-history; completado cuando todos bloquean apply sin writes.
- [ ] Agregar test de provider failure despues de varios history successes; completado cuando no queda seed parcial.
- [ ] Agregar test de dry-run con 100% coverage; completado cuando reporta completed/dry-run y realiza cero writes.
- [ ] Agregar test repository de round-trip para provenance ClubElo y manual; completado cuando todos los campos sobreviven escritura/lectura.
- [ ] Ejecutar pruebas enfocadas de provider, seed use case, repository y router; completado con todos los casos nuevos en verde.
- [ ] Ejecutar `pytest tests/`; completado sin regresiones, incluidas las pruebas de national-team ELO.
- [ ] Ejecutar `flake8 src/ tests/`, `isort --check-only src/ tests/` y `git diff --check`; completado con exit code 0 en los tres gates.

### Fase A9 - Rollout 2025

- [ ] Desplegar 0049 y el nuevo flujo sin ejecutar replay; completado cuando schema y API health estan verificados.
- [ ] Ejecutar dry-run club/2025 sin manual manifest; completado cuando el reporte suma exactamente 356 resolutions.
- [ ] Revisar cada history match con identifier, country, From, To, age y ELO; completado cuando todos tienen aprobacion o vuelven a blocker.
- [ ] Promover al catalogo solo aliases comprobados y repetir dry-run; completado cuando no quedan fuzzy matches tratados como autoridad.
- [ ] Preparar manifest manual para no-history/stale restantes con evidencia y aprobador; completado cuando cada entry satisface el schema nuevo.
- [ ] Ejecutar dry-run con manifest y exigir 356/356, 100% coverage y cero blockers; completado antes de cualquier apply.
- [ ] Ejecutar apply una sola vez con el mismo cutoff y manifest aprobados; completado cuando la respuesta conserva los mismos hashes y conteos del dry-run.
- [ ] Consultar `team_elo_seeds` y verificar 356 seeds club con provenance no vacia; completado cuando el total por source coincide con la respuesta apply.
- [ ] Auditar ELO min/max, histories de mayor age y todos los manual overrides; completado cuando no hay outlier sin evidencia.
- [ ] Ejecutar dos dry-runs posteriores y comparar seeds propuestos; completado cuando valores, source y provenance son deterministas.
- [ ] Continuar con replay temporal y recalc de 0048 solo despues de cerrar los gates anteriores; completado cuando no existe ejecucion ELO anticipada.

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

## Domain routing assessment

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

## Agent Routing Brief

**DDD Designer needed:** no

La extension no agrega una entidad futbolistica, aggregate, multiplicador ni formula. Formaliza
el port de ClubElo, DTOs frozen de integracion, una policy temporal de seed y provenance tecnica.
El implementador principal debe trabajar en este orden: domain ports/DTOs, provider, use case,
repository/migration, router/schemas y tests. Ningun paso puede introducir acceso HTTP en
application ni SQLAlchemy fuera de infrastructure.

**Routing recomendado:**

- Backend/hexagonal: fases A1, A3, A4 y A6.
- Infrastructure/provider: fase A2 y limites HTTP de A6.
- Database/repository: fase A5.
- API/admin: fase A7.
- QA/operations: fases A0, A8 y A9.

Si durante implementacion se propone estimar ELO por liga, pais, rival, division o promedio de
otros clubes, detener el trabajo: eso introduce una nueva politica futbolistica de baseline,
queda fuera de 0048-A y requiere Architecture Engineer mas DDD Designer. El unico fallback
permitido aqui es el manifest manual explicito con evidencia.
