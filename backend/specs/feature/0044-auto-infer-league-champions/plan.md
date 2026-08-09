# Plan: Inferencia automatica de campeones de liga

## Archivos a crear

- [x] `src/sfa/application/use_cases/infer_league_champions.py` - inferencia versionada desde tablas finales.
- [x] `tests/use_cases/test_infer_league_champions.py` - cobertura con fakes para cierre, config e idempotencia.

## Archivos a modificar

- [x] `src/sfa/domain/scoring_ports.py` - agregar `LeagueChampionCandidateDTO` y operaciones del port.
- [x] `src/sfa/infrastructure/repositories/competition_achievement_repository.py` - consultar campeones finales y reemplazar la fase.
- [x] `src/sfa/application/use_cases/run_full_recalculation.py` - insertar la inferencia antes del refresh y calculo de bonuses.
- [x] `src/sfa/application/use_cases/calculate_achievement_bonuses.py` - reconstruir detalles y totales sin residuos.
- [x] `tests/use_cases/test_run_full_recalculation.py` - verificar que un campeon inferido entra al calculo en la misma corrida.

## Checklist de implementacion

- [x] Ejecutar la suite backend antes de editar y registrar el baseline.
- [x] Agregar el DTO inmutable `LeagueChampionCandidateDTO` al dominio.
- [x] Extender `CompetitionAchievementRepositoryPort` con lectura de candidatos completos y reemplazo de fase.
- [x] Implementar una query sobre el ultimo matchday por liga, incluyendo `team_id`, `team_count`, fixtures regulares totales/pendientes y nombre de competicion.
- [x] Implementar reemplazo de fase que elimine solo campeones stale de la misma competicion/temporada y preserve otras fases.
- [x] Limpiar bonos detallados y totales antes de reconstruir una competicion.
- [x] Implementar `InferLeagueChampionsUseCase` con validacion de matchday, calendario completo sin pendientes, rules version, bonus `domestic_league.champion`, peso por nombre e idempotencia.
- [x] Integrar el use case entre inferencia KO y refresh de logros de liga.
- [x] Agregar logs con candidatos, inferidos, reemplazados y omitidos.
- [x] Cubrir rules version inexistente, config sin champion, tabla incompleta, liga completa y reemplazo de campeon.
- [x] Verificar que la suite enfocada pasa.
- [x] Verificar que la suite backend completa no introduce regresiones.
- [x] Verificar `flake8` en archivos modificados.
- [x] Verificar `isort --check-only` en archivos modificados.

## Agent Routing Brief

**DDD Designer needed:** no

La feature reutiliza `CompetitionAchievement` y sus invariantes. El unico tipo nuevo es un DTO de
lectura para transportar el campeon resuelto por standings; no agrega una entidad, aggregate ni
nuevo concepto de scoring.

## Verificacion

1. Ejecutar el recalculo de `season=2025` con rules version 4.
2. Confirmar en logs que Premier League y Ligue 1 tienen un campeon inferido y no fueron omitidas.
3. Consultar `competition_achievements` y verificar una sola fila `champion` para Arsenal y PSG.
4. Consultar `player_achievement_bonuses` y `sfa_season_scores` para jugadores de ambos equipos.
5. Repetir el recalculo y verificar que filas y puntos no se duplican.
