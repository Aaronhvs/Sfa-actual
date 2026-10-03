# Plan: Ranking Read Performance, Stable Refresh and All-Time Explanations

## Archivos a crear

- [x] `backend/tests/repositories/test_season_ranking_display_team.py` - verifica elegibilidad
  de equipo y resolucion limitada a los jugadores paginados.

## Archivos a modificar

- [x] `backend/src/sfa/infrastructure/repositories/sfa_score_repository.py` - unificar puntos y
  mejor competicion, paginar antes de resolver equipo y cargar B1 en bloque.
- [ ] `backend/src/sfa/application/use_cases/generate_ranking_explanations.py` - resolver el
  sentinel historico mediante los metodos all-seasons del port antes de resolver scopes.
- [ ] `backend/src/sfa/application/use_cases/get_ranking_explanations.py` - completar la
  version por defecto y omitir cache editorial para el contexto historico.
- [ ] `backend/src/sfa/infrastructure/repositories/ranking_explanation_repository.py` -
  construir evidencia all-time sin predicados `season = 'all'`.
- [ ] `backend/src/sfa/core/dependencies.py` - inyectar la version activa por defecto al use
  case de explicaciones siguiendo el patron del ranking.
- [ ] `backend/tests/use_cases/test_get_contextual_ranking_explanations.py` - cubrir ranking,
  fallback, filtros y politica de cache para `all`.
- [ ] `frontend/src/api/client.ts` - aceptar `AbortSignal` en ranking y explicaciones y
  propagarlo al `fetch` tipado.
- [ ] `frontend/src/pages/RankingPage.tsx` - separar carga inicial de refresh, conservar el
  arbol montado, proteger estado contra carreras y habilitar narrativas all-time.
- [ ] `frontend/src/index.css` - agregar feedback discreto y accesible de refresh sin cambios
  de layout ni bloqueo de controles.

## Checklist de implementacion

- [ ] Ejecutar `pytest tests/` antes de modificar codigo y documentar fallos preexistentes.
- [ ] Capturar baseline reproducible de `GET /api/v1/ranking` para season fisica, award
  period, `all`, busqueda y filtro de competicion, incluyendo mediana de al menos tres runs.
- [ ] Guardar `EXPLAIN (ANALYZE, BUFFERS)` baseline del caso lento y confirmar el numero de
  loops del agregado `sfa_season_scores`.
- [x] Unificar suma de puntos y mejor competicion en el mismo agregado PostgreSQL.
- [x] Conservar B1, honors, ultima aparicion verificada, filtros, rank global, orden y paginacion.
- [x] Confirmar que `get_ranking_for_scope` reutiliza el mismo camino sin duplicar logica SQL.
- [x] Agregar pruebas de compilacion para elegibilidad y resolucion temporal del equipo.
- [ ] Comparar snapshots de resultados antes/despues para ranking sin filtro, nombre,
  posicion, perfil, competicion, award period y paginas posteriores.
- [x] Repetir `EXPLAIN (ANALYZE, BUFFERS)` e identificar/eliminar el nested loop de 46 millones
  de comparaciones.
- [x] Aceptar la optimizacion tras medir 83-97% de mejora en los casos representativos.
- [x] Sustituir la hipotesis materializada descartada por una lectura en dos fases: ranking
  paginado con elegibilidad verificada y resolucion bulk del ultimo equipo visible.
- [x] Resolver coincidencias de busqueda por ultimo equipo en una consulta previa y aplicar
  esos ids despues del rank global, sin N+1 ni cambio de semantica.
- [ ] Extender `GetRankingExplanationsUseCase` con `default_rules_version_id` sin importar
  repositories de infraestructura en application.
- [ ] Actualizar el factory de `core/dependencies.py` para obtener la version activa y pasar
  su id al use case.
- [ ] Agregar una rama inicial para `season == 'all'` o `scope_key == 'all'` en
  `resolve_explanation_ranking`, normalizando ambos como contexto `all_time`.
- [ ] Llamar `get_ranking_all_seasons` con competition, position, bonus label, limit,
  rules version y `use_total` identicos a la request visible.
- [ ] Garantizar que la rama all-time no llama `SeasonRepository.resolve_scope`.
- [ ] Deshabilitar lectura de cache editorial para all-time y mantener el fallback
  determinista no persistido.
- [ ] Centralizar en `RankingExplanationRepository` la decision de alcance fisico: source
  scope, season concreta o all-time.
- [ ] Aplicar esa decision de forma consistente a score rows, stat profile, top events y
  match summaries; conservar filtros de competicion y rules version.
- [ ] Mantener individual honors vacio en all-time cuando no existe un `scope_key` persistido
  compatible, sin inventar ni duplicar bonus.
- [ ] Extender los Fakes completos de los tests con los metodos all-seasons del protocol.
- [ ] Probar que las explicaciones all-time usan exactamente los tres jugadores devueltos
  por ranking, respetan filtros y no leen cache ni resuelven un award period.
- [ ] Extender el helper `get` del frontend con `AbortSignal` opcional sin cambiar el contrato
  de los consumidores que no lo envian.
- [ ] Extender `fetchRanking` y `fetchRankingExplanations` con signal opcional; mantener las
  claves y TTL del cache existente.
- [ ] Reemplazar el loading unico de `RankingPage` por carga inicial y refresh, conservando
  jugadores y total durante requests posteriores.
- [ ] Crear un `AbortController` y request id monotono por request de ranking; abortar en el
  cleanup y permitir commits de estado solo al request vigente.
- [ ] Ignorar `AbortError` y presentar errores reales de refresh dentro de la seccion sin
  desmontar `FilterBar`, buscador, podio ni resultados validos.
- [ ] Aplicar jugadores y total de una respuesta valida en el mismo commit visual y finalizar
  el indicador sin producir un frame vacio.
- [ ] Exponer `aria-busy` en la region de resultados y agregar un indicador textual discreto
  accesible, sin overlay ni bloqueo de puntero.
- [ ] Mantener el skeleton completo solo cuando aun no existe ningun resultado inicial.
- [ ] Eliminar la exclusion frontend `season !== 'all'` de narrativas y enviar
  `season='all'`, `scope='all_time'`, `scope_key='all'` para el historico.
- [ ] Cancelar tambien requests narrativas obsoletas y no publicar explicaciones cuyos ids no
  coincidan con el Top 3 vigente.
- [ ] Verificar manualmente escritura continua, limpiar busqueda, cambio rapido de filtros,
  paginacion, navegacion y respuesta lenta simulada en desktop y mobile.
- [ ] Verificar que busqueda activa sigue ocultando el layout Top 3 segun la regla existente.
- [ ] Ejecutar las pruebas enfocadas de ranking y explicaciones.
- [ ] Ejecutar `pytest tests/` y verificar coverage global >= 80%.
- [ ] Ejecutar `flake8 src/ tests/` sin errores nuevos.
- [ ] Ejecutar `isort --check-only src/ tests/` sin errores nuevos.
- [ ] Ejecutar `npm run build` en `frontend/` sin errores TypeScript.
- [ ] Ejecutar una comprobacion Playwright en desktop y mobile confirmando foco persistente,
  ausencia de pantalla negra y Top 3 historico con explicaciones.

## Agent Routing Brief

**DDD Designer needed:** no

El refactor no agrega conceptos de negocio, entidades, aggregates, value objects ni reglas de
scoring. La lectura en dos fases es una decision del adaptador PostgreSQL; `all` ya es un sentinel
del read model y los metodos all-seasons ya forman parte de `SFAScoreRepositoryProtocol`; el
frontend solo corrige lifecycle y concurrencia de lectura.

## Verificacion

1. Comparar respuestas JSON completas de los casos baseline antes y despues, normalizando
   solo campos no deterministas si existieran; deben conservar jugadores, posiciones, ranks,
   puntos, equipos, totales y paginacion.
2. Confirmar en PostgreSQL que el plan nuevo elimina el nested loop entre ranking y contexto
   temporal que producia mas de 46 millones de comparaciones.
3. Medir al menos tres ejecuciones calientes y tres frias del endpoint para season, award
   period y all-time; registrar mediana y variacion.
4. Abrir `/ranking`, escribir rapidamente un nombre y cambiar filtros antes de que respondan
   las requests: el input conserva foco y solo la ultima request modifica la lista.
5. Simular error de red durante refresh: filtros y ultimo ranking siguen visibles y utilizables.
6. Seleccionar `Total historico`: podio y carrusel muestran los mismos tres ids, ranks y puntos.
7. Repetir el punto anterior con competicion, posicion y perfil; ranking y narrativa mantienen
   el mismo contexto.
8. Revisar logs/DB y confirmar que el GET all-time no llama al provider IA ni inserta filas en
   `ranking_player_explanations`.
