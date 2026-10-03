# Ranking Read Performance, Stable Refresh and All-Time Explanations

## Contexto de negocio

La pagina principal de ranking presenta tres fallos relacionados pero con limites distintos:

1. El ranking de una temporada fisica tarda entre 5.6 y 7 segundos. Un `EXPLAIN ANALYZE`
   sobre el dataset productivo mostro que PostgreSQL parametriza el agregado de
   `sfa_season_scores` y lo ejecuta aproximadamente una vez por cada uno de los 5,791
   jugadores candidatos. El costo dominante no esta en el conteo, el payload HTTP ni el
   bundle del frontend.
2. `RankingPage` sustituye todo el arbol de resultados por skeletons durante cualquier
   request. El buscador y los filtros se desmontan, el input pierde foco y la pantalla
   parece recargarse al escribir.
3. El selector `all` conserva el podio calculado, pero desactiva deliberadamente las
   explicaciones del Top 3. Si se habilita solo en frontend, el backend intenta resolver
   `all` como un scope persistido o aplica `season = 'all'` a tablas que almacenan seasons
   fisicas, por lo que no puede construir evidencia correcta.

Este refactor corrige el read path sin modificar puntos, ranking, scoring, ELO, ingestion
ni la forma en que se persisten resultados.

## Restricciones

- Se mantiene arquitectura hexagonal: Router -> Use Case -> Repository.
- El router HTTP solo valida y traduce la request; no construye SQL ni resuelve el ranking.
- `SFAScoreRepositoryProtocol` y los DTOs publicos no cambian por la optimizacion SQL.
- La semantica de filtros, orden, desempates, paginacion, equipo visible, posicion corregida,
  `use_total` y award periods debe permanecer identica.
- `get_ranking_for_scope` debe beneficiarse de la misma correccion porque delega en
  `get_ranking`; el ranking historico existente no debe degradarse.
- No se crean tablas, columnas, indices, migraciones, endpoints ni dependencias nuevas.
- El frontend sigue usando React 18, estado local, `fetch` y CSS puro.
- Una lectura publica de explicaciones no puede escribir en DB ni llamar al provider de IA.
- Las explicaciones historicas deben corresponder exactamente al Top 3 y a los filtros del
  ranking visible.
- La busqueda sigue usando el debounce actual; cambiar su umbral o agregar trigramas queda
  fuera de este refactor hasta medir el read path corregido.

## Decisiones tomadas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Convertir el agregado principal de `get_ranking` en un CTE `MATERIALIZED` de PostgreSQL | Agregar indices a ciegas o cachear la respuesta lenta | El plan observado demuestra reevaluacion parametrizada del agregado. Materializarlo fija una sola evaluacion dentro de la consulta y ataca el costo dominante. |
| Encapsular la construccion del agregado en un helper privado del repositorio | Introducir SQL en el use case | Es una decision del adaptador PostgreSQL/SQLAlchemy y no cambia el contrato del dominio. |
| Validar SQL compilado y `EXPLAIN (ANALYZE, BUFFERS)` antes/despues | Dar por exitosa la propuesta solo porque compila | `MATERIALIZED` es una hipotesis respaldada por el plan, pero su beneficio debe demostrarse con el dataset representativo. |
| Mantener `get_ranking_total` separado | Combinar listado y total en una consulta nueva | El conteo medido ronda 0.1 segundos; mezclarlo amplia el cambio y altera contratos sin atacar el cuello de botella. |
| Separar carga inicial de refresh en `RankingPage` | Reutilizar un unico `loadingRanking` para desmontar toda la vista | El usuario debe conservar foco, filtros, podio y resultados anteriores mientras llega la siguiente pagina o busqueda. |
| Cancelar transporte con `AbortController` y proteger commits con un request id monotono | Solo usar un booleano `cancelled` | El abort reduce trabajo inutil; el id tambien protege respuestas de cache o carreras que ya alcanzaron resolucion. |
| Mantener el ultimo resultado valido durante refresh y aplicar la nueva respuesta atomicamente | Vaciar jugadores al iniciar cada request | Evita pantalla negra, saltos de layout y estados parciales. |
| Mostrar errores de refresh dentro de la seccion de resultados sin desmontar controles | Reemplazar toda la pagina por el error | Un fallo transitorio no debe borrar una vista util ni impedir corregir los filtros. |
| Tratar `all` como sentinel historico explicito en el use case de explicaciones antes de resolver scopes | Registrar `all` como un `AwardPeriodScope` artificial | El historico es abierto y atraviesa todas las seasons; no es un periodo cerrado con fuentes finitas. |
| Reutilizar `get_ranking_all_seasons` para obtener el Top 3 historico | Llamar `get_ranking(season='all')` | Mantiene la misma semantica que el endpoint de ranking y evita un predicado imposible. |
| Construir evidencia historica omitiendo filtros de season, pero conservando competicion y version de reglas | Crear un scope con todos los pares season/competicion en application | El repositorio ya es responsable de traducir el sentinel a filtros de persistencia y puede hacerlo sin filtrar fuentes validas. |
| Resolver la version por defecto para explicaciones en el factory de DI y entregarla al use case | Consultar infraestructura desde application o decidir la version en React | Replica el patron existente de `GetRankingUseCase` y conserva dependencias dirigidas hacia adentro. |
| No reutilizar ni persistir cache editorial para `all` en esta iteracion | Guardar explicaciones historicas bajo una clave que envejece en cada temporada | El fallback determinista es barato, no escribe y siempre refleja el ranking historico actual. |
| Usar `scope='all_time'`, `season='all'` y `scope_key='all'` como contexto HTTP canonico | Disfrazar el historico como `award_period` | Hace explicita la intencion y permite que el use case intercepte el sentinel antes de `SeasonRepository.resolve_scope`. |

## Limites arquitectonicos

### Ranking optimizado

El flujo publico permanece:

1. `api/v1/ranking.py` recibe filtros.
2. `GetRankingUseCase` resuelve season o scope y llama el port existente.
3. `SFAScoreRepository.get_ranking` crea una sola relacion materializada con una fila por
   jugador para puntos, partidos, goles, asistencias, regates y duelos.
4. El statement exterior une esa relacion con B1, mejor competicion, ultima aparicion
   verificada, jugador y equipo.
5. Filtros de posicion, perfil y nombre, ranking window, orden, limit y offset conservan
   su comportamiento actual.

El CTE materializado se aplica al camino de season fisica y al camino de
`get_ranking_for_scope`, que utiliza el mismo metodo con `_scope`. No se reescriben en esta
fase `b1_agg`, `best_comp` ni `latest_verified_team`: sus costos medidos son secundarios y
cambiarlos simultaneamente dificultaria atribuir la mejora.

### Refresh estable en frontend

`RankingPage` tendra dos estados operacionales:

- `initialLoading`: no existe aun un resultado valido para el contexto inicial; puede usar
  el skeleton completo existente.
- `isRefreshing`: ya existe un resultado valido; buscador, filtros, podio y lista siguen
  montados. La zona de resultados expone `aria-busy` y un indicador discreto sin bloquear
  escritura, foco, scroll ni navegacion.

Cada ejecucion del efecto de ranking crea un `AbortController` y un id creciente. El cleanup
aborta la request. Solo el id vigente puede actualizar jugadores, total, loading o error.
`AbortError` no se presenta al usuario. El cliente acepta un `AbortSignal` opcional sin
romper consumidores existentes ni cache hits.

El carrusel narrativo tiene lifecycle independiente. Nunca muestra texto de jugadores de un
contexto anterior: conserva su contenedor solo cuando corresponda, cancela la request obsoleta
y publica explicaciones cuando coinciden con el Top 3 vigente.

### Explicaciones historicas Top 3

El flujo sera:

1. `RankingPage` permite narrativas para `all` cuando esta en pagina inicial, sin busqueda y
   con al menos tres jugadores, igual que otros contextos.
2. `fetchRankingExplanations` envia el contexto canonico historico y soporta cancelacion.
3. El router crea `RankingExplanationRequestDTO` sin interpretar `all`.
4. `GetRankingExplanationsUseCase`/`resolve_explanation_ranking` detecta el sentinel antes de
   `SeasonRepository.resolve_scope`, completa la version de reglas por defecto y llama
   `SFAScoreRepositoryProtocol.get_ranking_all_seasons` con los mismos filtros y `use_total`.
5. `RankingExplanationRepository` construye score rows, estadisticas, eventos y resumenes de
   todas las seasons para esos jugadores. Mantiene filtros de competicion y version.
6. `DeterministicRankingExplanationWriter` produce tres resultados no persistidos.

La condicion de cache del use case excluye `all_time`. Los rankings de award period,
temporada fisica y torneo conservan cache editorial y fallback actuales.

## Domain Model

No se agregan entidades, aggregates, value objects ni reglas de scoring. Se reutilizan
`RankingExplanationRequestDTO`, `RankedPlayerDTO`, `SFAScoreRepositoryProtocol` y el sentinel
`all`. El cambio es read-side y no requiere DDD Designer.

## Compatibilidad

- El JSON de `GET /api/v1/ranking` no cambia.
- El JSON y los parametros de `GET /api/v1/ranking/explanations` no cambian; se habilita una
  combinacion ya representable por el contrato.
- Las explicaciones cacheadas de temporadas, torneos y award periods siguen siendo validas.
- El cache de modulo de 60 segundos del frontend se conserva.
- No se recalculan scores ni se altera informacion historica.

## Riesgos y mitigaciones

| Riesgo | Mitigacion |
|---|---|
| El CTE materializado reduce la libertad del optimizador y empeora datasets pequenos | Comparar planes y tiempos para season, award period y filtros antes de aceptar el cambio. |
| Una respuesta abortada intenta actualizar estado | Combinar abort con request id y comprobar ambos caminos en navegador. |
| La evidencia historica mezcla versiones de reglas | Aplicar la misma version por defecto que el ranking visible y filtrar todas las fuentes versionadas. |
| Se muestra una narrativa vieja durante el refresh | Vincular la publicacion al contexto y a los ids del Top 3 vigente; limpiar solo la narrativa local, no todo el ranking. |
| `all` genera consultas de evidencia amplias | Limitar el trabajo a tres jugadores y conservar limites actuales de top events y match summaries. |

## Criterios de aceptacion

1. El ranking agrega puntos y selecciona la competicion representativa en una sola pasada por
   `sfa_season_scores`, sin cruzar dos proyecciones completas por jugador.
2. El equipo visible y los bonos B1 se resuelven en bloque despues de paginar; no existen
   consultas N+1 ni un cruce global de contexto antes del `LIMIT`.
3. Con datos y parametros equivalentes, filas, orden, ranks, totales y paginacion son iguales
   antes y despues del refactor.
4. La lectura de temporada medida con dataset productivo mejora al menos 70% respecto a la
   mediana baseline documentada, sin regresion funcional en filtros ni paginacion.
5. Escribir de forma continua en el buscador no desmonta el input, no pierde foco y no deja
   que una respuesta anterior reemplace la busqueda actual.
6. Cambiar posicion, perfil, competicion o pagina conserva el ultimo resultado hasta que el
   nuevo se aplica de forma atomica.
7. Un fallo de refresh deja utilizables los controles y los ultimos resultados validos.
8. `scope=all` mantiene el podio y muestra tres explicaciones cuyos ids, ranks y puntos
   coinciden con el Top 3 historico visible.
9. Los filtros de competicion, posicion y perfil producen el mismo Top 3 en ranking y
   explicaciones historicas.
10. El modo historico no llama a IA, no inserta explicaciones y no intenta resolver `all`
    mediante `SeasonRepository.resolve_scope`.

## Fuera de alcance

- Cambiar formulas, puntos, bonus, logros, ELO o posiciones.
- Agregar Redis/server cache, una tabla de proyeccion o una materialized view persistente.
- Agregar `pg_trgm`, columnas normalizadas o un minimo obligatorio de caracteres.
- Combinar listado y conteo en una sola consulta.
- Precalcular o persistir explicaciones historicas.
- Redisenar visualmente el ranking fuera del feedback de refresh localizado.

## Integraciones externas

No se agregan integraciones externas. El provider de IA existente queda excluido del GET
historico; se utiliza exclusivamente el writer determinista ya conectado.

## Enmienda de implementacion: benchmark productivo

La hipotesis inicial del CTE `MATERIALIZED` fue probada contra la base productiva y
descartada antes de integrar codigo:

| Variante | Mediana | Resultado |
|---|---:|---|
| Repositorio vigente | 1.93-2.03 s | baseline actual |
| Solo agregado materializado | 2.04 s | sin mejora |
| Agregado y mejor competicion materializados | 2.66 s | 34% peor |
| Agregado, joins directos y ultimo equipo reescrito | 2.82-3.01 s | 46-49% peor |

Todas las variantes devolvieron filas identicas. El plan actualizado ubico el costo en el
cruce previo al `LIMIT` entre aproximadamente 6,342 filas del ranking y 5,961 filas del
ultimo equipo verificado, mediante `Nested Loop` + `Materialize`.

La implementacion definitiva usa una lectura en dos fases dentro del mismo repositorio:

1. La consulta de ranking conserva agregado, ranking global, filtros y paginacion, pero une
   solo un conjunto `DISTINCT player_id` de jugadores con aparicion de equipo verificada.
2. Una segunda consulta en bloque resuelve el ultimo equipo de los ids de la pagina. Nunca
   se ejecuta una consulta por jugador.
3. Cuando existe busqueda, los ids cuyo ultimo equipo coincide se resuelven en una consulta
   previa; el filtro se aplica despues de calcular el rank, junto con el nombre del jugador.

Esto conserva la exclusion de jugadores sin equipo verificado, la busqueda por equipo, el
rank global y el equipo temporal correcto, evitando cruzar todas las filas de contexto con
todo el ranking antes de paginar.

### Resultado medido

| Caso | Antes | Despues | Mejora | Equivalencia |
|---|---:|---:|---:|---|
| Temporada fisica | 3.96 s | 0.28 s | 92.9% | filas identicas |
| Busqueda por jugador | 4.01 s | 0.49 s | 87.7% | filas identicas |
| Busqueda por equipo | 2.64 s | 0.45 s | 83.2% | filas identicas |
| Filtro de posicion | 2.31 s | 0.38 s | 83.8% | filas identicas |
| Perfil goleador | 11.29 s | 0.35 s | 96.9% | filas identicas |
| Segunda pagina | 2.66 s | 0.37 s | 86.1% | filas identicas |
| Award period `season-2025` | 4.35 s | 0.29 s | 93.3% | filas identicas |
