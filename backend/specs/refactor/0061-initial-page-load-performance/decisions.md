# Initial Page Load Performance

## Contexto de negocio

La apertura inicial de SFA se percibe lenta aunque la estructura visual ya incluye skeletons y
las rutas React estan separadas con `lazy`. La auditoria distingue cuatro costos que hoy se
acumulan antes de que el ranking sea util:

1. La pagina raiz hace un redirect cliente a `/ranking` y carga el chunk de `RankingPage`.
2. `RankingPage` inicializa `season` vacio y no solicita el ranking hasta que termina
   `GET /api/v1/seasons`. Esto crea un waterfall obligatorio `seasons -> ranking`.
3. El ranking resuelve version activa, scope, filas y total mediante varios accesos a DB. El
   costo dominante del repositorio ya fue medido y corregido localmente en el spec `0060`, pero
   ese trabajo sigue siendo un prerequisito de despliegue.
4. CSS, fuentes, logos y llamadas auxiliares compiten con la ruta critica. El CSS global mide
   362.89 kB sin comprimir y 60.23 kB gzip; `logo.png` y `logo_sfa_maestro.png` suman 253,926
   bytes. El documento tambien abre una hoja de Google Fonts con once combinaciones de peso y
   familia declaradas.

La meta es mejorar el tiempo hasta ranking visible sin alterar la arquitectura hexagonal, el
contrato visual, el orden del ranking, los puntos SFA ni la frecuencia de actualizacion.

## Evidencia observable

### Bundle local de produccion

`npm run build` sobre el estado auditado produce:

| Recurso | Raw | Gzip | Papel en carga inicial |
|---|---:|---:|---|
| `index-*.css` | 362.89 kB | 60.23 kB | Bloqueante para todas las rutas |
| `index-*.js` | 178.74 kB | 58.36 kB | Runtime React, router y shell |
| `RankingPage-*.js` | 31.27 kB | 9.30 kB | Chunk de la pagina inicial |
| `client-*.js` | 5.36 kB | 1.34 kB | Cliente HTTP compartido |
| `logo.png` | 79,112 B | n/a | Logo de navbar en primer viewport |
| `logo_sfa_maestro.png` | 174,814 B | n/a | Marca del hero en primer viewport |

El JS inicial no es el principal problema. El CSS monolitico y los bitmaps son oportunidades
secundarias despues de retirar la espera de datos.

### Ranking productivo ya medido

El benchmark documentado en `0060-ranking-read-performance-and-refresh` encontro:

| Caso | Antes | Repositorio optimizado local |
|---|---:|---:|
| Temporada fisica | 3.96 s | 0.28 s |
| Award period `season-2025` | 4.35 s | 0.29 s |
| Busqueda por jugador | 4.01 s | 0.49 s |
| Perfil goleador | 11.29 s | 0.35 s |

Por tanto, desplegar y verificar `0060` es P0. Agregar cache delante del SQL anterior ocultaria
el problema en hits, pero conservaria una penalizacion de varios segundos en cada miss.

### Waterfall de frontend

El flujo actual es:

```text
HTML -> CSS + main JS -> RankingPage JS
                         |-> GET /seasons
                         |-> GET /competitions
                         |-> GET /wc/live [-> GET /wc/fixtures si no hay vivo]
                         |
                         `-> cuando /seasons termina: GET /ranking
                                                     `-> GET /ranking/explanations
```

Referencias concretas:

- `frontend/src/pages/RankingPage.tsx:67`: `season` comienza en cadena vacia cuando no hay
  `scope` en la URL.
- `frontend/src/pages/RankingPage.tsx:114`: inicia `fetchSeasons`.
- `frontend/src/pages/RankingPage.tsx:204`: el efecto de ranking retorna mientras `season` sea
  vacio.
- `frontend/src/pages/RankingPage.tsx:262`: explicaciones esperan un ranking confirmado.
- `frontend/src/components/shared/WcLiveChip.tsx:13`: el chip consulta estado mundial al montar
  y puede encadenar la lista completa de fixtures.
- `frontend/src/pages/RankingPage.tsx:402` y `:454`: en modo Mundial existen dos instancias del
  chip; el cache actual no comparte promesas en vuelo y puede duplicar requests concurrentes.

### Flujo API y repositorio

La arquitectura vigente es correcta y se conserva:

```text
GET /api/v1/ranking
  -> api/v1/ranking.py
  -> GetRankingUseCase
  -> SFAScoreRepositoryProtocol
  -> SFAScoreRepository + PostgreSQL
```

En una request por scope, antes de responder se ejecutan de forma secuencial:

1. `ScoringRulesVersionRepository.get_active_version()` desde el factory de DI.
2. `SeasonRepository.resolve_scope()`, que reconstruye scopes con un `SELECT DISTINCT` sobre
   `sfa_season_scores JOIN competitions`.
3. `resolve_rules_version_id_for_scope()`.
4. `get_ranking_for_scope()`.
5. `get_ranking_total_for_scope()`.

La consulta de filas es el costo dominante conocido y pertenece a `0060`. Scope y metadata son
datos pequenos, repetidos y apropiados para cache corta despues de medirlos por separado.

## Restricciones

- Mantener `Router -> Use Case -> Repository`; no ejecutar SQL desde routers ni React.
- Mantener React 18, estado local, `fetch` y CSS puro; no agregar React Query, SWR o Zustand.
- No cambiar estructura, textos, jerarquia visual, animaciones ni dimensiones de skeletons.
- No cambiar formulas SFA, ELO, bonus, posiciones, ranking, paginacion ni payloads existentes.
- No combinar esta ejecucion con el trabajo incompleto del spec `0060`; debe integrarse y
  desplegarse primero para obtener un baseline limpio.
- Las optimizaciones de cache deben tolerar una ingesta cada diez minutos y nunca servir una
  version indefinidamente.
- No depender de Service Worker en esta fase.

## Decisiones tomadas

| Prioridad | Decision | Alternativa descartada | Razon |
|---|---|---|---|
| P0 | Completar, integrar y desplegar `0060` antes de este spec | Cachear la consulta lenta | La mejora medida de 83-97% ataca el costo real y evita misses de varios segundos |
| P1 | Permitir que la primera llamada de ranking use el scope por defecto que el backend ya resuelve cuando no recibe `scope` | Esperar `/seasons` o fijar `season-2026` en React | Elimina un RTT sin hardcodear la temporada futura |
| P1 | Separar `requestedScope` de `resolvedScope` durante bootstrap y canonizar la respuesta sin disparar una segunda llamada equivalente | Mutar el estado `season` actual y confiar en el cache | Las claves `scope=` y `scope=season-2026` son distintas y producirian un refetch |
| P1 | Agregar deduplicacion de promesas en vuelo al cliente HTTP | Solo cache post-respuesta | Evita requests identicas concurrentes, incluidas las dos instancias de `WcLiveChip` en modo Mundial |
| P1 | Montar una sola instancia de `WcLiveChip` y adaptar su ubicacion con CSS existente | Mantener dos componentes ocultando uno por breakpoint | Un elemento oculto sigue montando efectos y consumiendo red/polling |
| P1 | Definir cache HTTP corta y explicita para metadata estable y lecturas publicas | Confiar solo en el `Map` de 60 s | El cache de modulo desaparece al recargar y no beneficia una apertura nueva |
| P2 | Optimizar los dos PNG de primer viewport y declarar dimensiones/fetch priority | Cambiar logos o estetica | Reduce bytes y layout work sin variar el aspecto |
| P2 | Extraer CSS por ruta solo despues de generar coverage y mapa de dependencias | Dividir `index.css` por intuicion | El archivo contiene cascadas historicas; mover reglas sin evidencia tiene riesgo visual alto |
| P3 | Considerar cache Redis de ranking solo si P0-P2 no cumplen el presupuesto | Introducirlo de entrada | Exige invalidacion por scope, reglas y filtros; aumenta complejidad operacional |

## Limites arquitectonicos

### Bootstrap del ranking

No se crea un endpoint compuesto. `GET /api/v1/ranking` ya admite ausencia de `scope` y
`GetRankingUseCase` resuelve el scope vigente mediante `SeasonRepository.resolve_scope(None)`.
El frontend puede iniciar en paralelo:

```text
GET /seasons
GET /competitions
GET /ranking?limit=15&offset=0&use_total=true
```

La respuesta de ranking ya contiene `scope`. Ese valor se convierte en el scope canonico para
el selector y la URL. La reconciliacion debe marcar la respuesta inicial como equivalente para
que actualizar la URL no lance otro ranking.

Si la URL trae `scope`, se conserva la conducta actual y se solicita ese scope directamente.

### Cache y freshness

Se proponen presupuestos iniciales, sujetos a validacion:

- `/seasons`: `max-age=60`, `stale-while-revalidate=300`.
- `/competitions`: `max-age=300`, `stale-while-revalidate=1800`.
- `/ranking`: `max-age=30`, `stale-while-revalidate=60`, con clave completa por query string.
- `/ranking/explanations`: `max-age=60`, `stale-while-revalidate=300`.
- `/wc/live`: no almacenar respuesta viva mas de 10 s.

Los headers se deciden en el adaptador HTTP; la cache distribuida, si se adopta despues, debe
entrar mediante un port o un decorador de repositorio/read model conectado en
`core/dependencies.py`, nunca desde el use case mediante una importacion de Redis.

### Recursos estaticos

Los assets con hash de Vite deben servirse como `public, max-age=31536000, immutable`. El HTML
debe seguir con revalidacion para descubrir hashes nuevos. Los logos publicos sin hash requieren
revalidacion o nombres versionados antes de usar cache immutable.

La division de CSS no forma parte de la primera entrega. Antes se debe medir coverage de
`/ranking`, `/player/:id`, `/torneos` y `/compare`, identificar reglas realmente compartidas y
mantener el orden de cascada. La estetica actual es un criterio de compatibilidad, no una
oportunidad de rediseño.

## Consultas y mediciones requeridas

### Tiempos HTTP

Registrar al menos cinco cargas frias y cinco calientes con cache deshabilitado/habilitado:

```bash
curl -o /dev/null -sS -w '%{time_starttransfer} %{time_total}\n' \
  'https://<host>/api/v1/seasons'

curl -o /dev/null -sS -w '%{time_starttransfer} %{time_total}\n' \
  'https://<host>/api/v1/ranking?scope=season-2026&limit=15&offset=0&use_total=true'
```

### SQL de metadata

Capturar `EXPLAIN (ANALYZE, BUFFERS)` de la consulta generada por
`SeasonRepository._get_scopes()`:

```sql
SELECT DISTINCT
    sfa_season_scores.season,
    sfa_season_scores.competition_id,
    competitions.name,
    competitions.participant_kind
FROM sfa_season_scores
JOIN competitions
  ON competitions.id = sfa_season_scores.competition_id;
```

El objetivo no es agregar indices sin evidencia, sino confirmar si esta llamada merece cache
de metadata o si su costo es despreciable frente al RTT.

### Navegador

Usar Performance/Network con una carga limpia de `/ranking` y conservar:

- waterfall HAR o trace;
- TTFB del documento, `/seasons`, `/ranking` y `/ranking/explanations`;
- FCP, LCP, CLS e INP/TBT de laboratorio;
- bytes transferidos por JS, CSS, fonts e imagenes;
- numero de requests antes del primer ranking visible.

## Criterios de aceptacion

1. La primera request de ranking comienza sin esperar la respuesta de `/seasons` cuando la URL
   no contiene scope.
2. Resolver el scope por defecto actualiza selector y URL sin una segunda request de ranking
   equivalente.
3. `GET /ranking` P50 caliente permanece por debajo de 500 ms en el dataset productivo tras
   desplegar `0060`; P95 debe quedar debajo de 800 ms.
4. El ranking util aparece en menos de 1.5 s P50 y 2.5 s P75 en perfil movil Fast 4G de
   laboratorio, medido desde navegacion hasta render de las tres primeras tarjetas.
5. Una carga de modo Mundial produce una sola request en vuelo por clave para `/wc/live` y
   `/wc/fixtures`, y conserva un solo intervalo de polling.
6. Recargar dentro del TTL usa cache HTTP observable (`memory cache`, `disk cache`, `304` o
   `Age`) y no retorna datos con mas antiguedad que la politica definida.
7. FCP/LCP no esperan `/ranking/explanations`; el carrusel puede completar despues sin mover el
   layout.
8. CLS se mantiene menor a 0.1 y no cambia la geometria del header, filtros, podio o tabla.
9. Los assets estaticos con hash reciben cache immutable; `index.html` se revalida.
10. Capturas desktop y mobile son visualmente equivalentes antes/despues salvo por una carga mas
    temprana del contenido.

## Riesgos y mitigaciones

| Riesgo | Mitigacion |
|---|---|
| La reconciliacion de scope dispara dos rankings | Prueba de red que cuente requests y test de lifecycle con URL sin scope |
| Cache HTTP muestra datos anteriores a una ingesta | TTL corto, `stale-while-revalidate` acotado y prueba posterior a recalculo |
| Deduplicar promesas comparte un abort entre consumidores | La promesa en vuelo no debe estar ligada al `AbortSignal` de un solo consumidor; definir ownership y tests |
| Optimizar PNG cambia transparencia o nitidez | Comparacion pixel/screenshot en fondos y viewports actuales |
| Separar CSS rompe cascada | Dejarlo en P2, exigir coverage y regresion visual antes de mover reglas |
| Redis agrega claves obsoletas por filtros/version | No implementarlo en primera entrega; definir key completa e invalidacion si P3 se justifica |

## Fuera de alcance

- Rediseñar la pagina o cambiar la estetica.
- Cambiar formulas, puntos, ELO, ingestion o frecuencia de Celery.
- Reescribir el frontend con SSR, Next.js u otro framework.
- Crear una materialized view o read model persistente en esta fase.
- Reemplazar las fuentes de marca.
- Optimizar paginas internas antes de cerrar el camino inicial de `/ranking`.

## Domain Model

No se agregan entidades, aggregates, value objects ni reglas de dominio. El trabajo afecta
orquestacion de lectura, adaptadores HTTP, cache de transporte y assets estaticos. No requiere
DDD Designer.

