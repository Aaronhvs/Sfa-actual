# Plan: podio fijo y paginas de diez jugadores

## Dependencias

- [ ] Leer y respetar los contratos de `0060-ranking-read-performance-and-refresh`.
- [ ] Verificar que la separacion `initialLoading` / `isRefreshing`, cancelacion y request ids
  de `0060` estan integrados antes de modificar la paginacion.
- [ ] Coordinar con `0061-initial-page-load-performance` para no reintroducir un waterfall ni
  duplicar la request critica de la pagina 1.

## Archivos previstos

### A modificar

- [ ] `frontend/src/pages/RankingPage.tsx` - separar podio/lista, aplicar ventanas de diez,
  conservar podio al paginar y desacoplar narrativas de `page`.
- [ ] `frontend/src/index.css` - aislar visualmente las regiones y limitar loading/animacion
  al grid inferior con dimensiones estables.
- [ ] `backend/src/sfa/infrastructure/repositories/sfa_score_repository.py` - agregar desempate
  tecnico estable por `player_id` sin alterar la ventana `rank()`.
- [ ] `backend/tests/repositories/test_season_ranking_display_team.py` - verificar orden estable
  y continuidad entre offsets en temporada/scope.
- [ ] `backend/tests/use_cases/test_get_ranking.py` - ampliar contrato de offset absoluto y
  limites usados por ventanas separadas si la cobertura actual no es suficiente.
- [ ] `backend/tests/use_cases/test_get_ranking_multi_season.py` - cubrir continuidad all-time.

### A crear solo si el frontend ya dispone de runner compatible

- [ ] Test de lifecycle de `RankingPage` para bootstrap, cambio de pagina, deep link, filtros,
  busqueda y carreras de requests.

No se prevén endpoints, schemas, DTOs, migraciones ni dependencias nuevas.

## Fase 0 - Baseline y contrato

- [ ] Ejecutar `pytest tests/` antes de modificar codigo y documentar fallos preexistentes.
- [ ] Ejecutar `npm run build` antes de modificar codigo.
- [ ] Capturar en desktop y mobile pagina 1 y pagina 2 actuales.
- [ ] Registrar requests, limites y offsets actuales al abrir pagina 1 y cambiar a pagina 2.
- [ ] Confirmar visualmente que hoy el podio desaparece y que se solicitan ventanas de 12.
- [ ] Guardar la secuencia actual de ids/ranks para al menos 33 jugadores en temporada, all-time
  y un filtro con empates.

## Fase 1 - Orden estable del repositorio

- [ ] Identificar todos los statements equivalentes usados por temporada fisica, award period
  y all-time.
- [ ] Mantener `rank()` con los criterios de negocio actuales.
- [ ] Agregar `player_id ASC` solamente como ultimo criterio del orden exterior paginado.
- [ ] Confirmar que busqueda por jugador/equipo y resolucion bulk de equipo de `0060` conservan
  exactamente el mismo orden.
- [ ] Probar que dos filas empatadas conservan el mismo rank visible.
- [ ] Probar que dos lecturas consecutivas con `offset=3/13/23` producen ids disjuntos y orden
  reproducible.
- [ ] Comparar la concatenacion Top 3 + ventanas contra una lectura continua `limit=33`.
- [ ] Repetir las pruebas para season, award period y all-time.

## Fase 2 - Modelo de estado frontend

- [ ] Reemplazar `players` por estados independientes `podiumPlayers` y `listPlayers`.
- [ ] Definir `PODIUM_SIZE = 3` y `LIST_PAGE_SIZE = 10`; retirar `PAGE_SIZE = 12`.
- [ ] Construir `podiumContextKey` sin `page` ni terminos de busqueda.
- [ ] Construir `listRequestKey` con contexto, busqueda y pagina.
- [ ] Mantener request ids y abort controllers separados para bootstrap/podio y lista.
- [ ] Separar `isInitialLoading`, `isContextRefreshing` e `isListRefreshing` sin vaciar datos
  validos.
- [ ] Evitar commits si la respuesta no coincide con la clave vigente.
- [ ] Asegurar que un nuevo contexto publica podio y primera lista atomicamente.

## Fase 3 - Bootstrap y offsets

- [ ] En pagina 1 sin busqueda y sin podio confirmado, solicitar `limit=13, offset=0`.
- [ ] Dividir la respuesta en `ranking.slice(0, 3)` y `ranking.slice(3, 13)`.
- [ ] Con podio confirmado, solicitar todas las ventanas con `limit=10` y
  `offset=3 + page * 10`.
- [ ] Al volver a pagina 1, solicitar `limit=10, offset=3` sin reemplazar el podio.
- [ ] Para deep links `page > 1`, iniciar podio `limit=3, offset=0` y lista `limit=10` en
  paralelo, sin serializar requests.
- [ ] En busqueda usar `limit=10`, `offset=page * 10` y no montar podio.
- [ ] Calcular `listTotal = max(total - 3, 0)` solo en modo podio.
- [ ] Calcular `totalPages = ceil(listTotal / 10)` y rangos desde el offset absoluto.
- [ ] Mantener el parametro URL uno-basado y omitir `page=1` como actualmente.
- [ ] Mantener `returnTo` con scope, filtros, busqueda y pagina.

## Fase 4 - Filtros y narrativas

- [ ] Crear handlers/wrappers de filtros que reseteen pagina antes de comprometer el nuevo
  contexto, evitando un render con filtro nuevo/pagina antigua.
- [ ] Resetear pagina al cambiar scope, position, bonus, competition o search efectiva.
- [ ] Mantener el debounce del buscador de `0060`.
- [ ] Vincular Top 3 narrativo a `podiumContextKey` e ids del podio.
- [ ] Eliminar `page === 0` y `page` como causas de limpieza/refetch de explicaciones.
- [ ] Limpiar explicaciones al cambiar contexto o ids del podio.
- [ ] Mantener explicaciones visibles mientras solo cambia la pagina inferior.
- [ ] Confirmar que all-time conserva sus tres explicaciones en todas las paginas.

## Fase 5 - Aislamiento visual

- [ ] Mantener podio/narrativa fuera de cualquier nodo con `key` dependiente de pagina.
- [ ] Mantener encabezado de clasificacion, filtros, buscador y etiqueta contextual fuera del
  grid animado.
- [ ] Aplicar `aria-busy` de paginacion solo a la region/lista inferior.
- [ ] Conservar lista anterior durante fetch y mostrar feedback discreto localizado.
- [ ] Reservar una altura minima equivalente a diez filas en desktop y al layout responsive
  correspondiente en mobile, sin forzar espacio cuando la ultima pagina tiene menos filas.
- [ ] Animar solamente `ranking-cards-grid` con la direccion actual.
- [ ] Reforzar separacion entre podio y lista mediante espacio/borde/banda compatible con los
  estilos actuales, sin card contenedora nueva ni cambio de paleta.
- [ ] Evitar scroll automatico al inicio de pagina; el viewport debe permanecer estable.
- [ ] Respetar `prefers-reduced-motion` para la transicion de lista.

## Fase 6 - Casos limite

- [ ] Total 0: estado vacio sin podio ni paginador.
- [ ] Total 1-3: podio parcial, lista vacia, sin paginador.
- [ ] Total 4: Top 3 + una fila.
- [ ] Total 13: Top 3 + diez filas, una sola pagina.
- [ ] Total 14: pagina 1 con diez y pagina 2 con una.
- [ ] Total 23: dos paginas completas de diez.
- [ ] Empates en frontera 3/4, 13/14 y 23/24: mismo rank permitido, ids unicos.
- [ ] Busqueda con menos/más de diez resultados y limpieza de busqueda.
- [ ] Cambio rapido pagina 1 -> 2 -> 3: solo la ultima respuesta puede hacer commit.
- [ ] Cambio de filtro durante request de pagina: abortar/ignorar lista obsoleta.
- [ ] Error en lista: conservar podio y ultima lista util.
- [ ] Error en podio de deep link: no presentar la lista como contexto completo; ofrecer el
  estado de error sin mezclar snapshots.

## Verificacion funcional

- [ ] Confirmar pagina 1: Top 3 y ordinales 4-13.
- [ ] Confirmar pagina 2: mismo Top 3 y ordinales 14-23.
- [ ] Confirmar pagina 3: mismo Top 3 y ordinales 24-33.
- [ ] Confirmar que podio, fotos, puntos, explicaciones y links no cambian al paginar.
- [ ] Confirmar que solo las diez tarjetas inferiores reciben transicion/loading.
- [ ] Confirmar que header, controles y filtros no pierden foco ni se desmontan.
- [ ] Confirmar navegacion anterior/siguiente, numeros, progreso y rango textual.
- [ ] Confirmar deep link `/ranking?...&page=2` y back/forward del navegador.
- [ ] Confirmar `returnTo` desde un jugador de pagina 2.
- [ ] Confirmar paridad en temporada actual, total historico, Mundial y filtros principales.

## Verificacion de rendimiento

- [ ] En apertura normal de pagina 1 confirmar una sola request de ranking antes de las
  explicaciones, con `limit=13&offset=0`.
- [ ] Al paginar confirmar una sola request nueva con `limit=10` y offset esperado.
- [ ] Confirmar que una pagina posterior no vuelve a solicitar Top 3 ni explicaciones.
- [ ] En deep link posterior confirmar exactamente dos requests paralelas, no secuenciales.
- [ ] Medir que la transicion de pagina no empeora el presupuesto P95 de `0061`.
- [ ] Confirmar CLS menor a 0.1 y ausencia de flash/skeleton de pagina completa.

## Gates de calidad

- [ ] Ejecutar tests enfocados de repositorio y use case.
- [ ] Ejecutar `pytest tests/` y confirmar coverage global >= 80%.
- [ ] Ejecutar `flake8 src/ tests/` sin errores nuevos.
- [ ] Ejecutar `isort --check-only src/ tests/` sin errores nuevos.
- [ ] Ejecutar `npm run build` sin errores TypeScript.
- [ ] Ejecutar Playwright desktop y mobile con screenshots de pagina 1, transicion y pagina 2.
- [ ] Inspeccionar Network para limites, offsets, paralelismo y ausencia de requests duplicadas.
- [ ] Ejecutar `git diff --check`.

## Agent Routing Brief

**DDD Designer needed:** no

No se agregan conceptos de negocio. El trabajo modifica composicion read-side, orden tecnico
estable y lifecycle de presentacion sobre contratos existentes.

