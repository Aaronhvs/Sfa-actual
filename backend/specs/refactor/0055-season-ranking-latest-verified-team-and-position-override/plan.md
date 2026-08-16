# Plan: 0055 - Latest Verified Team In Season Rankings

## Archivos a crear

- [x] `tests/repositories/test_season_ranking_display_team.py` - alcance, cronologia,
  validacion, fallback, filtros y no mutacion.
- [x] `tests/repositories/test_latest_appearance_ordering.py` - orden cronologico de
  perfil y enriquecimiento.

## Archivos a modificar

- [x] `src/sfa/infrastructure/repositories/sfa_score_repository.py` - proyeccion de
  ultimo equipo verificado y uso consistente en ranking/perfil por season/scope.
- [x] `src/sfa/infrastructure/repositories/player_repository.py` - ordenar la ultima
  aparicion global por fecha real.
- [x] `src/sfa/infrastructure/repositories/enrich_position_repository.py` - ordenar la
  ultima aparicion global o estacional por fecha real.
- [x] `src/sfa/infrastructure/repositories/player_event_repository.py` - conservar el
  equipo exacto del fixture y eliminar el fallback al score estacional.
- [x] `src/sfa/domain/player_position_overrides.py` - overrides de Fermín López a `MCO`
  y Martín Zubimendi a `MC`.
- [x] `tests/domain/test_player_position_overrides.py` - normalizacion y clasificacion
  de Fermín López y Martín Zubimendi.

## Checklist de implementacion

- [x] 1. Registrar baseline antes de editar codigo.
  Criterio: ejecutar `pytest tests/`, anotar total y fallos preexistentes; no intentar
  corregir fallos ajenos.

- [ ] 2. Capturar invariantes de datos para una muestra con transferencia.
  Criterio: guardar `player_stats.team_id`, `player_events.team_id`,
  `SFASeasonScore.team_id`, puntos y bonuses antes del cambio para comparacion read-only.

- [x] 3. Crear un helper privado de alcance de apariciones en
  `sfa_score_repository.py`.
  Criterio: traduce season fisica, `AwardPeriodScope` y `competition_id` a filtros sobre
  `Fixture.season`/`Fixture.competition_id`; award periods no filtrados usan solo clubs y
  tournament scopes conservan su participante.

- [x] 4. Crear el subquery `latest_verified_team`.
  Criterio: une `PlayerStats` con `Fixture`, exige `team_id` home/away y asigna
  `row_number()` por jugador con orden
  `Fixture.played_at DESC, Fixture.id DESC, PlayerStats.id DESC`.

- [x] 5. Separar equipo visible y score representativo en `get_ranking`.
  Criterio: `team_name`/logo salen de `latest_verified_team`; puntos, rank, partidos,
  breakdown, bonus y competicion representativa conservan la logica actual.

- [x] 6. Reutilizar la misma seleccion en `get_ranking_total`.
  Criterio: listado y total incluyen exactamente los mismos jugadores validos para los
  mismos filtros; buscar por club consulta el equipo visible, no el snapshot del score.

- [x] 7. Aplicar la proyeccion a encabezados por temporada/scope.
  Criterio: `get_best_score_for_player_season` y `get_player_detail_for_scope` muestran
  el ultimo equipo verificado de su alcance sin consultar otra season ni
  `players.team_id`.

- [x] 8. Eliminar fallbacks historicamente imposibles de estas lecturas.
  Criterio: sin candidato verificado no se usa una aparicion global, `players.team_id` ni
  `SFASeasonScore.team_id` para inventar el club visible; ranking y total tratan el caso
  de forma consistente y el historial por fixture conserva solo snapshots exactos.

- [x] 9. Corregir las otras resoluciones de ultima aparicion introducidas por 0028.
  Criterio: `PlayerRepository` y `EnrichPositionRepository` unen `Fixture` y ordenan por
  `played_at`; `fixture_id` queda solo como desempate determinista.

- [x] 10. Agregar los overrides de Fermín López y Martín Zubimendi.
  Criterio: el registro de terminos y `position_for_context()` resuelven las variantes
  con/sin acentos como `MCO` y `MC`; no se modifica `position_mapping.py` ni frontend.

- [x] 11. Test: transferencia y orden no correlacionado de IDs.
  Criterio: un fixture mas nuevo con ID menor gana sobre uno antiguo con ID mayor y el
  ranking muestra el club nuevo.

- [x] 12. Test: limites de season, scope y competicion.
  Criterio: fixtures posteriores fuera del par permitido no participan; award period
  compuesto elige el ultimo club y tournament scope elige la seleccion.

- [x] 13. Test: snapshot invalido y ausencia de candidato.
  Criterio: un equipo fuera de home/away se ignora; no aparece ningun fallback de otra
  season, `players.team_id` o score representativo; listado y total coinciden.

- [x] 14. Test: busqueda, posicion y paginacion.
  Criterio: buscar el club nuevo encuentra al jugador y buscar el antiguo no; los filtros
  conservan total y pagina coherentes.

- [x] 15. Test: Fermín López y Martín Zubimendi.
  Criterio: `position_for_context("EXT", player_name="Fermin Lopez", ...) == "MCO"`
  y `position_for_context("DC", player_name="Martin Zubimendi", ...) == "MC"` con y sin
  acentos; ranking/count los incluyen en la posicion corregida y los excluyen de la
  posicion almacenada incorrectamente.

- [x] 16. Test: no mutacion.
  Criterio: ejecutar ranking/perfil no emite `UPDATE`/`INSERT`/`DELETE` y deja iguales
  snapshots de stats/eventos, `SFASeasonScore.team_id`, puntos y bonuses.

- [x] 17. Test: orden de perfil y enriquecimiento.
  Criterio: ambas queries usan `Fixture.played_at DESC` y resuelven empates con IDs; la
  variante de enriquecimiento respeta el filtro de season.

- [x] 18. Ejecutar verificacion enfocada.
  Criterio: pasan tests de overrides, repositories de ranking, multi-season, award scope
  y snapshots de equipo.

- [x] 19. Ejecutar calidad y suite completa.
  Criterio: `flake8 src/ tests/`, `isort --check-only src/ tests/` y `pytest tests/` no
  introducen fallos nuevos.

- [x] 20. Verificar el diff final.
  Criterio: no hay cambios en scoring, logros, ELO, migrations, modelos, schemas, frontend
  ni productores de `SFASeasonScore`; no se incluyen archivos ajenos.

## Secuencia recomendada

1. Escribir primero los tests de cronologia, scope y no-fallback.
2. Implementar el helper/subquery una sola vez y conectarlo a listado, total y perfil.
3. Corregir el orden cronologico de perfil/enriquecimiento.
4. Agregar el override y sus tests de filtro.
5. Comparar invariantes, correr checks enfocados y luego la suite completa.

## Agent Routing Brief

**DDD Designer needed:** no

La implementacion modifica una proyeccion read-only y una politica de override existente.
No introduce entidades, aggregates, persistencia ni reglas nuevas de scoring.

## Verificacion manual

1. Abrir una season con un jugador transferido y confirmar club/escudo del ultimo partido
   valido de esa season.
2. Cambiar a una season anterior y confirmar que no aparece el club futuro.
3. Aplicar un filtro de competicion y confirmar que el club sale de esa interseccion.
4. Abrir el award period compuesto y el Mundial aislado: club en el primero, seleccion en
   el segundo.
5. Filtrar `MCO` y buscar Fermín López; no debe aparecer bajo `EXT`.
6. Filtrar `MC` y buscar Martín Zubimendi; no debe aparecer bajo `DC`.
7. Comparar hashes/conteos de scores, bonos, stats y eventos antes/despues.
