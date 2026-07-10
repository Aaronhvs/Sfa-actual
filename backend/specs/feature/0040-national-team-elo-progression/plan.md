# Plan: National Team ELO Progression

## Archivos a crear

- [ ] `migrations/0040_team_strength_elo_seed_raw.sql` - Agrega `elo_seed_raw` a `team_strengths` y amplia el CHECK de `source` para `national_elo_v1`.
- [ ] `tests/tasks/test_national_team_elo_recalculation_task.py` - Tests de orquestacion Celery para asegurar ELO antes de recalc y lock.

## Archivos a modificar

- [ ] `src/sfa/domain/scoring_ports.py` - Agregar `elo_seed_raw` a `TeamEloRow` y extender firmas del port de strengths.
- [ ] `src/sfa/infrastructure/models/team_strengths/models.py` - Agregar columna `elo_seed_raw` y permitir `national_elo_v1` en el constraint de source.
- [ ] `src/sfa/infrastructure/repositories/team_strength_repository.py` - Implementar lectura baseline filtrada por competicion y upsert que preserve seed.
- [ ] `src/sfa/application/use_cases/seed_national_team_elo.py` - Escribir `elo_seed_raw` durante el seed nacional real.
- [ ] `src/sfa/application/use_cases/seed_clubelo.py` - Escribir `elo_seed_raw` durante el seed de clubes sin cambiar comportamiento publico.
- [ ] `src/sfa/application/use_cases/calculate_elo_ratings.py` - Permitir source configurable y recalculo desde `elo_seed_raw`.
- [ ] `src/sfa/core/config.py` - Agregar K-factor configurable para ELO nacional si no existe.
- [ ] `src/sfa/tasks/elo_tasks.py` - Agregar coordinador nacional ELO + full recalculation con late imports, commit/rollback y lock.
- [ ] `src/sfa/tasks/ingestion_tasks.py` - Enrutar competiciones `national_team` al coordinador nacional en vez de saltar ELO.
- [ ] `src/sfa/tasks/__init__.py` - Exportar la nueva tarea coordinadora si corresponde.
- [ ] `tests/use_cases/test_calculate_elo_ratings.py` - Cubrir baseline por seed, source configurable y filtro por competicion.
- [ ] `tests/use_cases/test_seed_national_team_elo.py` - Cubrir escritura de `elo_seed_raw`.
- [ ] `tests/use_cases/test_seed_clubelo.py` - Cubrir escritura de `elo_seed_raw` si existe suite para club seed.
- [ ] `tests/repositories/test_team_strength_repository.py` - Cubrir preservacion de seed y lectura filtrada si existe suite de repositorio.

## Checklist de implementacion

- [ ] Revisar el working tree antes de implementar y reconciliar los cambios parciales existentes contra este spec; no asumir que el intento previo es correcto.
- [ ] Confirmar que el schema actual de DB no tiene `elo_seed_raw` y que `ck_team_strength_source` no permite `national_elo_v1`.
- [ ] Crear migracion idempotente para `elo_seed_raw NUMERIC(7,2) NULL`.
- [ ] La migracion debe backfillear `elo_seed_raw = elo_raw` solo para filas seed existentes (`clubelo_seed`, `national_elo_seed`) donde `elo_seed_raw IS NULL`.
- [ ] La migracion debe reemplazar el CHECK de source incluyendo `national_elo_v1`.
- [ ] Agregar rollback claro en comentarios SQL para restaurar el CHECK anterior y remover columna solo si no hay dependencia operativa.
- [ ] Actualizar el modelo `TeamStrength` con `elo_seed_raw` y el source nuevo.
- [ ] Actualizar `TeamEloRow` como frozen dataclass con `elo_seed_raw: float | None`.
- [ ] Extender `TeamStrengthRepositoryPort.upsert_team_elo` con `elo_seed_raw: float | None = None`.
- [ ] Extender `TeamStrengthRepositoryPort.get_all_teams_with_elo` con `competition_ids: list[int] | None = None`.
- [ ] Implementar `upsert_team_elo` para que `elo_seed_raw` solo se escriba cuando el caller lo pasa explicitamente.
- [ ] Implementar `get_all_teams_with_elo(season, competition_ids)` filtrando por competicion cuando se provee.
- [ ] En `SeedNationalTeamEloUseCase`, pasar `elo_seed_raw=entry.elo_raw` al upsert real.
- [ ] En `SeedClubEloUseCase`, pasar `elo_seed_raw=entry.elo` al upsert real para mantener semantica consistente.
- [ ] En `CalculateEloRatingsUseCase.execute`, aceptar `source` con default compatible `elo_v1`.
- [ ] En `CalculateEloRatingsUseCase.execute`, aceptar `use_seed_baseline` con default `False`.
- [ ] Cuando `use_seed_baseline=True`, inicializar `elo_by_team` con `row.elo_seed_raw` si existe; si no existe, usar `row.elo_raw`.
- [ ] Cuando `use_seed_baseline=True` y el caller marca modo nacional estricto, fallar si algun equipo del scope no tiene seed; no usar `ELO_DEFAULT=1500` silenciosamente.
- [ ] Al pedir baseline en `CalculateEloRatingsUseCase`, pasar `competition_ids` para evitar contaminacion cruzada.
- [ ] Mantener fixtures procesados en orden cronologico por repository o use case; testearlo explicitamente.
- [ ] Auditar si `get_fixtures_for_elo_recalc` puede usar marcador oficial del fixture; si hoy deriva goles desde `PlayerStats`, agregar validacion contra fixture score o documentar el bloqueo si el modelo aun no lo persiste.
- [ ] Agregar `NATIONAL_TEAM_ELO_DEFAULT_K` a settings con valor inicial conservador y documentado.
- [ ] Crear tarea Celery coordinadora `apply_elo_update_then_recalculate_task`.
- [ ] La tarea coordinadora debe ejecutar update ELO nacional con `source='national_elo_v1'` y `use_seed_baseline=True`.
- [ ] La tarea coordinadora debe esperar el resultado del update antes de llamar el full recalculation, no encolar ambas cosas de forma independiente.
- [ ] La tarea coordinadora debe usar late imports como el patron existente de `tasks/`.
- [ ] La tarea coordinadora debe usar commit/rollback por unidad de trabajo y logs claros con season, competition_ids y rules_version_id.
- [ ] Agregar advisory lock para impedir dos secuencias nacionales ELO + recalc simultaneas para la misma season/competition.
- [ ] Si no hay seed nacional o el coverage no esta completo, fallar con error visible antes de recalcular scores.
- [ ] En `ingestion_tasks.py`, para `participant_kind == "national_team"`, resolver active rules version y encolar solo la tarea coordinadora nacional.
- [ ] En `ingest_all_competitions_task`, agrupar competition_ids nacionales y llamar el coordinador una sola vez despues de commits de ingestion.
- [ ] Mantener comportamiento existente de clubes: update ELO club y recalc sin cambiar contratos publicos.
- [ ] Actualizar fakes de tests para las nuevas firmas del port.
- [ ] Testear idempotencia: dos ejecuciones del update nacional con mismos fixtures producen el mismo `elo_raw`.
- [ ] Testear que `upsert_team_elo` no borra ni nullifica `elo_seed_raw` cuando actualiza `source='national_elo_v1'`.
- [ ] Testear que `get_all_teams_with_elo(..., competition_ids=[world_cup_id])` no devuelve equipos de otra competicion.
- [ ] Testear que la tarea coordinadora llama update ELO antes del full recalculation.
- [ ] Testear que ingestion de World Cup no llama el recalc directo viejo.
- [ ] Testear que seed incompleto o ELO fallido no dispara `run_full_recalculation_task`.
- [ ] Testear que si active rules version no existe, ingestion registra error y no encola coordinador.
- [ ] Ejecutar `pytest tests/use_cases/test_calculate_elo_ratings.py tests/use_cases/test_seed_national_team_elo.py`.
- [ ] Ejecutar tests de tasks/repository agregados para este spec.
- [ ] Ejecutar suite relevante de scoring: `pytest tests/use_cases/test_calculate_scores_for_rules_version.py tests/domain/test_scoring_v2_value_objects.py` si existen.
- [ ] Ejecutar `flake8 src/ tests/` y registrar deuda preexistente si bloquea.
- [ ] Ejecutar `isort --check-only src/ tests/`.

## Agent Routing Brief

**DDD Designer needed:** no

Este cambio no introduce nuevas entidades de futbol, nuevos value objects, nuevos aggregates ni
nuevos multiplicadores. La feature reusa el dominio existente de ELO/team strength y cambia la
persistencia/orquestacion para que M1 consuma strengths actualizadas. El trabajo debe hacerlo un
agente de implementacion backend siguiendo ports, use cases, repositories y Celery tasks.

## Verificacion

1. Ejecutar seed nacional real o fixture local y confirmar que `team_strengths.elo_seed_raw`
   queda poblado para World Cup 2026 con `source='national_elo_seed'`.
2. Ejecutar la tarea nacional coordinadora dos veces para la misma season/competition y verificar
   que los `elo_raw` finales no cambian entre ejecuciones.
3. Confirmar que despues de la tarea hay filas `source='national_elo_v1'` para World Cup 2026.
4. Confirmar que `run_full_recalculation_task` corre despues del update ELO, no antes.
5. Auditar un fixture Francia-Marruecos o similar: M1 debe usar `team_strengths` vigentes y no
   fallback de standings.
6. Verificar ranking y detalle del Mundial para `season=2026` sin errores.
7. Rollback operacional: revertir filas `source IN ('national_elo_seed', 'national_elo_v1')`
   desde backup o script controlado, recalcular scoring, e invalidar caches si el ranking queda
   anomalo.
