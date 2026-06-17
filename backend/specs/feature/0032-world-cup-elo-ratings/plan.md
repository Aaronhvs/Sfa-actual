# Plan: World Cup ELO Ratings

## Archivos a crear

- [x] `src/sfa/infrastructure/providers/national_team_elo_provider.py` — Provider para leer ratings de selecciones desde World Football Elo Ratings y resolver nombres SFA.
- [x] `src/sfa/application/use_cases/seed_national_team_elo.py` — Use case que matchea selecciones, normaliza ELO y escribe `team_strengths`.
- [x] `src/sfa/application/use_cases/get_national_team_elo_coverage.py` — Use case de auditoría de coverage de strengths del Mundial.
- [x] `tests/use_cases/test_seed_national_team_elo.py` — Tests del seed con fakes completos.
- [x] `tests/use_cases/test_get_national_team_elo_coverage.py` — Tests de auditoría de coverage.
- [x] `tests/providers/test_national_team_elo_provider.py` — Tests de parsing/matching del provider con fixtures HTML/texto locales.
- [x] `migrations/0032_national_team_elo_source.sql` — Migración para ampliar el `CHECK` de `team_strengths.source`.
- [x] `http/national_team_elo.http` — Casos HTTP para seed, preview/audit y errores.

## Archivos a modificar

- [x] `src/sfa/domain/scoring_ports.py` — Agregar DTOs y métodos del port necesarios para seed/auditoría de ELO de selecciones.
- [x] `src/sfa/infrastructure/repositories/team_strength_repository.py` — Implementar métodos nuevos del port sin retornar ORM models.
- [x] `src/sfa/infrastructure/models/team_strengths/models.py` — Ampliar `ck_team_strength_source` para incluir `national_elo_seed`.
- [x] `src/sfa/api/v1/schemas/elo_schemas.py` — Agregar schemas de request/response para seed/auditoría de selecciones.
- [x] `src/sfa/api/v1/elo_router.py` — Agregar endpoints admin para seed de selecciones y auditoría de coverage.
- [x] `src/sfa/core/dependencies.py` — Agregar factory para `SeedNationalTeamEloUseCase`.
- [x] `src/sfa/tasks/elo_tasks.py` — Agregar task Celery `seed_national_team_elo_task`.
- [x] `src/sfa/tasks/__init__.py` — Exportar la nueva task si corresponde.
- [x] `src/sfa/main.py` — Sin nuevo router si se extiende `elo_router`; verificar que el router admin sigue registrado.
- [ ] `docker-compose-prod.yml` / configuración de VPS — Verificar que variables/API keys no son necesarias para `eloratings.net`.

## Checklist de implementación

- [ ] Ejecutar diagnóstico inicial en backend antes de tocar código: `pytest tests/` y documentar fallos preexistentes si los hay. Bloqueado localmente: Windows Python no tiene `pytest`.
- [ ] Auditar el estado local/producción-like de `team_strengths` para `season='2026'` y World Cup: conteo total, `source`, min/max/avg strength y equipos sin fila.
- [ ] Confirmar el `competition_id` real de World Cup en la DB mediante `competitions.name` y no hardcodearlo en código.
- [x] Crear migración `0032_national_team_elo_source.sql` que reemplace `ck_team_strength_source` incluyendo `national_elo_seed`.
- [x] La migración debe ser idempotente o tener instrucciones claras de rollback para restaurar el CHECK anterior.
- [x] Actualizar `TeamStrength` model para aceptar `national_elo_seed` en el CheckConstraint.
- [x] Agregar `NationalTeamEloEntry` como frozen dataclass en `domain/scoring_ports.py`.
- [x] Extender `TeamStrengthRepositoryPort` con método para listar equipos activos de una competición-temporada.
- [x] Extender `TeamStrengthRepositoryPort` con método para auditar strengths faltantes por competición-temporada.
- [x] Implementar los métodos nuevos en `TeamStrengthRepository` usando SQLAlchemy async y DTOs/dicts simples, nunca ORM models.
- [x] Crear `NationalTeamEloProvider` con método `fetch_snapshot(source_url: str | None)` que lea ranking de selecciones desde `eloratings.net`.
- [x] El provider debe incluir mapping explícito para diferencias conocidas entre nombres de `eloratings.net`, API-Football y SFA.
- [x] El provider debe usar fuzzy matching solo como fallback y devolver unmatched para revisión humana.
- [x] El provider debe soportar una entrada manual/importable de ratings para producción si la fuente externa falla.
- [x] Crear `SeedNationalTeamEloResult` con season, competition_id, matched, unmatched, source_date, status y error.
- [x] Crear `SeedNationalTeamEloUseCase` que obtiene equipos activos del Mundial, resuelve ratings, normaliza ELO y llama `upsert_team_elo` con `source='national_elo_seed'`.
- [x] El use case debe fallar o retornar status no-completed si `matched` no cubre el umbral configurado para producción.
- [x] El use case debe permitir `dry_run=True` para auditar matching sin escribir en DB.
- [x] Agregar schemas Pydantic para seed nacional: season, competition_id opcional, source_url opcional, dry_run, min_coverage.
- [x] Agregar response schema con matched, unmatched, coverage_pct y status.
- [x] Agregar endpoint `POST /api/v1/admin/elo/national-teams/seed`.
- [x] Agregar endpoint o modo `dry_run` para preview de matching antes de escribir en producción.
- [x] Agregar factory `get_seed_national_team_elo_use_case` en `core/dependencies.py`.
- [x] Agregar `seed_national_team_elo_task` en `tasks/elo_tasks.py` con late imports, commit/rollback y logs `[seed_national_team_elo_task]`.
- [x] Agregar tests de provider para parsing de una muestra de ranking y para mapping de nombres comunes del Mundial.
- [x] Agregar fake repository completo para tests de `SeedNationalTeamEloUseCase`.
- [x] Testear happy path: todos los equipos tienen ELO, se llama `upsert_team_elo` con `source='national_elo_seed'`.
- [x] Testear unmatched: el resultado lista equipos sin match y no oculta el problema.
- [x] Testear `dry_run=True`: no escribe en repositorio.
- [x] Testear coverage mínimo: si el coverage es menor al umbral, el resultado no permite producción.
- [x] Testear que equipos sin competición activa no escriben strengths.
- [x] Actualizar `http/national_team_elo.http` con dry run, seed real y caso de coverage insuficiente.
- [ ] Ejecutar `pytest tests/use_cases/test_seed_national_team_elo.py tests/providers/test_national_team_elo_provider.py`. Bloqueado localmente: no está instalado `pytest`.
- [ ] Ejecutar suite relevante de ELO/scoring: `pytest tests/use_cases/test_calculate_elo_ratings.py tests/domain/test_scoring_v2_value_objects.py`. Bloqueado localmente: no está instalado `pytest`.
- [ ] Ejecutar `pytest tests/` y registrar cualquier deuda preexistente. Bloqueado localmente: no está instalado `pytest`.
- [ ] Ejecutar `flake8 src/ tests/` y registrar deuda preexistente si bloquea. Bloqueado localmente: no está instalado `flake8`.
- [ ] Ejecutar `isort --check-only src/ tests/`. Bloqueado localmente: no está instalado `isort`.

## Plan de rollout en producción

- [ ] Antes del deploy, crear backup de DB del VPS y registrar commit/tag del backend actualmente desplegado.
- [ ] Ejecutar auditoría previa en producción: World Cup competition id, equipos activos, filas existentes en `team_strengths`, y sample de `player_event_scores.calculation_details` para `m1_source`.
- [ ] Desplegar código sin ejecutar recálculo todavía.
- [ ] Aplicar migración `0032_national_team_elo_source.sql` y verificar que el CHECK acepta `national_elo_seed`.
- [ ] Ejecutar `dry_run` del seed nacional en el VPS y revisar `unmatched`; no continuar si hay equipos mundialistas sin match no justificado.
- [ ] Ejecutar seed real con coverage esperado de 100% para equipos activos del Mundial.
- [ ] Auditar `team_strengths` post-seed: count por source, min/max/avg, top/bottom teams, y cero missing para World Cup 2026.
- [ ] Lanzar recálculo de scoring para `season='2026'` y `competition_id=World Cup` usando el pipeline existente.
- [ ] Auditar post-recálculo: eventos con `strength_used=true` o `m1_source='team_strength'`, distribución de M1, ranking top 20 y player detail sample.
- [ ] Comparar puntos/ranking antes vs después y guardar evidencia del cambio esperado.
- [ ] Invalidar caches relacionados si el VPS usa Redis/cache para endpoints de ranking o player detail.
- [ ] Verificar en la página pública `/mundial`, ranking y detalle de jugador que los datos cargan sin errores.
- [ ] Mantener rollback listo: restaurar backup DB o revertir strengths `national_elo_seed` + volver a recalcular si el resultado es anómalo.

## Agent Routing Brief

**DDD Designer needed:** no

La feature no introduce nuevas reglas de scoring, value objects ni aggregates. El concepto de
fuerza de equipo ya existe como `team_strengths.strength`, y M1 ya consume strengths de ambos
equipos. El trabajo es de integración, persistencia, matching, endpoint admin y operación de
rollout.

## Verificación

1. `SELECT COUNT(*) FROM team_strengths ts JOIN competitions c ON c.id = ts.competition_id WHERE ts.season='2026' AND c.name='World Cup' AND ts.source='national_elo_seed';` devuelve una fila por selección mundialista activa.
2. La auditoría de missing strengths para World Cup 2026 devuelve cero equipos sin strength.
3. Un recálculo de scoring para World Cup 2026 produce eventos con `calculation_details.strength_used = true` o `m1_source = 'team_strength'`.
4. La distribución de `m1` para Mundial tiene valores distintos de 1.0 y dentro del clamp configurado.
5. `/api/v1/ranking?season=2026` y detalle de jugadores mundialistas cargan correctamente tras el recálculo.
6. La página pública `/mundial` del VPS sigue operativa después del deploy y recálculo.
