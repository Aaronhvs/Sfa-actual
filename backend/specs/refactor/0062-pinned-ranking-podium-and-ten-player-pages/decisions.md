# Podio fijo y paginas de diez jugadores en RankingPage

## Contexto

`RankingPage` ya presenta un podio visual para los tres primeros jugadores, pero el podio y
la lista inferior comparten el mismo array `players` y la misma request. La pagina inicial
solicita 15 filas (Top 3 + 12) y, al avanzar, reemplaza ese array por una ventana que ya no
contiene el podio. Como `showHero` depende tambien de `page === 0`, desaparecen el podio y su
narrativa, y el cambio se percibe como una recarga de la pagina completa.

El producto requiere conservar estructura y estetica, con este comportamiento:

- pagina 1: Top 3 fijo y separado, seguido por exactamente 10 jugadores;
- pagina 2: el mismo Top 3 y los siguientes 10 jugadores;
- solo la lista inferior cambia o se anima al paginar;
- encabezado, temporada, filtros, buscador, contexto, podio y narrativa permanecen montados;
- no puede haber jugadores duplicados ni saltos entre ventanas.

## Relacion con specs existentes

Se crea el spec `0062` en lugar de enmendar `0060` o `0061`.

- `0060` conserva su alcance: rendimiento SQL, refresh estable y explicaciones all-time.
- `0061` conserva su alcance: reducir el tiempo de apertura y el waterfall inicial.
- `0062` introduce un contrato nuevo de presentacion y paginacion: un segmento fijo de tres
  filas y un segmento movil de diez.

La implementacion de `0062` depende del refresh estable de `0060` y debe respetar el presupuesto
de carga de `0061`. Puede implementarse en la misma entrega tecnica solo si los commits y la
verificacion permiten atribuir cada comportamiento a su spec.

## Restricciones

- Mantener la estructura visual, textos, componentes y estetica actuales.
- Mantener React 18, estado local, `fetch` y CSS puro.
- Mantener `Router -> Use Case -> Repository`; React no calcula ni corrige ranks.
- No cambiar formulas SFA, ELO, bonos, filtros, perfiles ni reglas de desempate de negocio.
- No crear un endpoint nuevo ni cambiar el payload publico de `GET /ranking`.
- Mantener URLs compartibles mediante el parametro `page`.
- No desmontar controles, podio ni narrativa durante una transicion de pagina.
- La busqueda conserva el comportamiento vigente de lista simple sin podio contextual.
- Las optimizaciones no deben agregar una segunda request al camino normal de apertura de la
  pagina 1.

## Semantica canonica de paginacion

Se definen dos constantes de presentacion:

```text
PODIUM_SIZE = 3
LIST_PAGE_SIZE = 10
```

Para el modo normal, sin busqueda activa, `page` sigue siendo cero-basada dentro de React y
uno-basada en la URL:

```text
list_offset(page) = PODIUM_SIZE + page * LIST_PAGE_SIZE
list_limit = LIST_PAGE_SIZE
```

| Pagina URL | Pagina React | Offset lista | Filas ordinales esperadas |
|---:|---:|---:|---|
| 1 o ausente | 0 | 3 | 4-13 |
| 2 | 1 | 13 | 14-23 |
| 3 | 2 | 23 | 24-33 |

"Ordinal" describe la posicion de la fila dentro del orden total. El campo visible `rank`
puede repetirse cuando dos jugadores empatan; ese empate no autoriza repetir u omitir jugadores
entre paginas.

La cantidad paginable excluye el podio:

```text
list_total = max(total_players - PODIUM_SIZE, 0)
total_pages = ceil(list_total / LIST_PAGE_SIZE)
```

El rango visible usa el universo completo:

```text
range_start = PODIUM_SIZE + page * LIST_PAGE_SIZE + 1
range_end = min(range_start + returned_rows - 1, total_players)
```

Con menos de cuatro jugadores se muestra solo el podio disponible y no aparece paginacion.
Con 13 jugadores se muestra una unica pagina de lista. Con 14 aparece una segunda pagina con
un jugador.

Cuando existe busqueda activa se conserva la semantica actual: no hay podio fijo, cada pagina
contiene hasta 10 resultados y el offset es `page * 10`. Al limpiar la busqueda se restablece
la pagina 1 y reaparece el podio del contexto vigente.

## Decisiones

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Separar estado de `podiumPlayers` y `listPlayers` | Seguir derivando ambos de `players` | La lista puede actualizarse sin invalidar ni desmontar el podio. |
| Separar `podiumContextKey` de `listRequestKey` | Incluir `page` en un unico contexto | La pagina cambia la ventana inferior, no la identidad del podio. |
| Excluir `page` del efecto de podio y explicaciones | Limpiar narrativas al salir de pagina 1 | El Top 3 y su evidencia pertenecen a filtros/scope, no a la pagina inferior. |
| En apertura normal de pagina 1 solicitar `limit=13, offset=0` y dividir la respuesta | Hacer siempre dos requests paralelas de 3 y 10 | Conserva una sola request critica y el presupuesto de `0061`. |
| Tras tener podio confirmado solicitar solo ventanas `limit=10` | Volver a descargar 13 filas al regresar a pagina 1 | Mantiene el podio inmovil y reduce transferencia/trabajo. |
| En una entrada directa a `?page=N`, N > 1, cargar podio y ventana en paralelo | Ocultar podio o forzar al usuario a pagina 1 | Respeta la URL compartible sin serializar dos RTT. |
| Conservar la ultima lista mientras llega la nueva y animar solo el grid | Skeleton o vaciado de toda la seccion | Evita el efecto de recarga y mantiene dimensiones estables. |
| Agregar `player_id ASC` como ultimo criterio de orden exterior | Confiar en el orden accidental de PostgreSQL | Impide swaps, duplicados o saltos entre requests cuando puntos y desempates existentes coinciden. |
| Mantener `rank()` basado en los criterios actuales y usar `player_id` solo para orden estable | Incluir `player_id` dentro de `rank()` | Los empates deben conservar el mismo rank visible. |
| Resetear pagina de forma sincronica al cambiar un filtro de contexto | Esperar un efecto posterior al render | Evita lanzar una request transitoria con filtros nuevos y pagina antigua. |

## Estado y flujo frontend

### Claves de contexto

`podiumContextKey` contiene solamente los valores que pueden cambiar el Top 3:

```text
scope | position | bonus_label | competition_id | use_total
```

No contiene `page`. La busqueda activa selecciona el modo de lista simple y por tanto no usa
el podio. `listRequestKey` contiene el contexto anterior, busqueda y pagina.

### Apertura de pagina 1

1. Solicitar ranking con `limit=13`, `offset=0`.
2. Confirmar que la respuesta corresponde al request id vigente.
3. Dividir atomicamente `ranking[0:3]` y `ranking[3:13]`.
4. Guardar `total`, scope canonico y ambas claves comprometidas.
5. Cargar explicaciones para los ids del podio sin bloquear el primer render util.

### Cambio de pagina

1. Mantener montados podio, narrativa, filtros y lista anterior.
2. Marcar solo la region de lista como `aria-busy=true`.
3. Solicitar `limit=10` con `offset=3 + page * 10`.
4. Aplicar request id y `AbortController` independientes del podio.
5. Reemplazar atomicamente `listPlayers` y animar solo `ranking-cards-grid`.
6. Mantener el foco, la posicion de scroll y la altura minima de la region durante el cambio.

No se aplica `aria-busy` al podio por una transicion de pagina. Un error de pagina mantiene la
lista anterior y muestra el feedback localizado definido en `0060`.

### Entrada directa a una pagina posterior

Si la URL inicial contiene `page=2` o superior y no existe podio confirmado para el contexto:

- iniciar en paralelo `limit=3, offset=0` para el podio y `limit=10` con el offset de la
  pagina solicitada para la lista;
- ambos resultados deben compartir el mismo contexto y scope canonico antes de publicarse;
- la lista puede mostrarse cuando llegue, reservando el espacio estable del podio hasta que
  este se complete;
- el total se acepta de la respuesta de lista; si ambas respuestas informan totales distintos
  por una ingesta concurrente, prevalece la respuesta mas reciente del ciclo y se revalida en
  el siguiente refresh, sin mezclar jugadores de contextos diferentes.

### Cambio de filtros, temporada o perfil

Estos cambios si modifican el podio. Deben resetear la pagina a cero antes de construir la
request. Mientras llega el nuevo contexto puede conservarse la vista anterior como snapshot,
pero el commit del nuevo podio y su primera lista debe ser atomico; nunca se combina un podio
viejo con una lista de filtros nuevos. Las explicaciones anteriores se retiran cuando cambia
el `podiumContextKey`, no cuando cambia `page`.

## Orden determinista y continuidad

El repositorio mantiene los criterios actuales de negocio para score, puntos y `rank()`. Se
agrega un desempate tecnico final por `player_id ASC` a todas las lecturas paginadas equivalentes:

```text
ORDER BY profile_order DESC, contextual_total_pts DESC, player_id ASC
```

El `player_id` no entra en la ventana `rank()`; solo estabiliza el orden entre filas que ya
empatan en todos los criterios visibles. El mismo orden debe usarse en temporada fisica,
award period y total historico.

Las pruebas comparan la concatenacion de varias paginas contra una lectura continua del mismo
contexto y exigen ids unicos, mismo orden y ausencia de huecos.

## Aislamiento visual

El podio permanece en su seccion actual y la lista en `rp-table-section`. El aislamiento se
refuerza sin redisenar:

- espacio vertical consistente entre podio/narrativa y lista;
- limite o banda superior ya compatible con la estetica SFA;
- encabezado de lista fuera del nodo animado;
- dimensiones estables para diez tarjetas durante carga y transicion;
- solamente el grid inferior recibe la animacion direccional.

No se crean cards contenedoras nuevas ni se anidan cards. En mobile el podio puede conservar
su layout responsive actual, pero no desaparece al avanzar de pagina.

## Compatibilidad

- `GET /api/v1/ranking` conserva parametros y payload.
- `offset` sigue siendo absoluto y tiene precedencia sobre el offset derivado de `page`.
- El parametro URL `page=2` significa la segunda ventana inferior, no la segunda pagina nativa
  de trece filas.
- Links de jugador y `returnTo` conservan filtros y pagina.
- Mundial, temporada, award period y total historico usan la misma formula cuando no hay
  busqueda.
- Las explicaciones siguen correspondiendo exactamente a los tres jugadores del podio.

## Riesgos y mitigaciones

| Riesgo | Mitigacion |
|---|---|
| Podio viejo combinado con lista de filtros nuevos | Commit atomico por `podiumContextKey` y request ids separados. |
| Request transitoria al cambiar filtro desde pagina posterior | Reset sincronico de pagina en handlers/wrappers antes de actualizar URL y ejecutar fetch. |
| Duplicados por empate total | Orden exterior determinista por `player_id`, con pruebas multi-pagina. |
| Dos requests degradan la apertura | Una sola request de 13 en pagina 1; doble request solo en deep links posteriores. |
| Explicaciones desaparecen al paginar | Efecto vinculado a `podiumContextKey` e ids, nunca a `page`. |
| Cambio de lista mueve toda la pagina | Altura reservada y animacion limitada al grid inferior. |
| Total cambia durante una ingesta | No mezclar contextos; aceptar snapshot por request y revalidar en el siguiente refresh. |

## Criterios de aceptacion

1. La pagina 1 sin busqueda muestra Top 3 y exactamente 10 jugadores debajo cuando existen al
   menos 13 jugadores.
2. La pagina 1 contiene ordinales 4-13; la pagina 2, 14-23; la pagina 3, 24-33.
3. Concatenar ids del podio y de todas las paginas produce ids unicos y el mismo orden que una
   lectura continua del ranking.
4. Los ranks visibles conservan empates; el desempate tecnico no altera el numero de rank.
5. Cambiar pagina no desmonta ni cambia podio, narrativa, encabezado, filtros o buscador.
6. Durante paginacion solo la region de diez jugadores expone loading/animacion y conserva la
   lista anterior hasta el commit de la nueva.
7. La explicacion del Top 3 no se vuelve a solicitar ni se limpia solo por cambiar pagina.
8. Volver a pagina 1 conserva el podio y solicita/muestra nuevamente ordinales 4-13.
9. Abrir directamente `?page=2` muestra el Top 3 correcto y ordinales 14-23.
10. Cambiar scope o filtro resetea a pagina 1 y publica podio/lista del nuevo contexto sin
    mezclarlos con el anterior.
11. La busqueda muestra paginas de 10 sin podio y al limpiarla vuelve a Top 3 + 10.
12. Con 0, 1, 2, 3, 4, 13 y 14 jugadores, podio, lista, rangos y controles no presentan paginas
    vacias ni conteos incorrectos.
13. La URL y `returnTo` conservan la pagina visible sin navegacion completa del documento.
14. El layout no produce un salto incoherente en desktop o mobile y conserva CLS menor a 0.1.

## Fuera de alcance

- Cambiar el diseno de las tarjetas o el contenido del Top 3.
- Cambiar la formula de ranking o convertir `rank()` en numeracion ordinal.
- Agregar scroll infinito.
- Crear un endpoint compuesto o una sesion de snapshot persistida.
- Redisenar filtros, buscador, narrativa o paginador.
- Implementar las optimizaciones generales de carga de `0061` dentro de este spec.

## Domain Model

No se agregan entidades, aggregates, value objects ni reglas de dominio. El cambio pertenece
a la composicion read-side, estabilidad del orden del adaptador SQL y estado de presentacion.
No requiere DDD Designer.

