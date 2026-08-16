# 0055 - Latest Verified Team In Season Rankings

## Contexto

Los specs 0028 y 0029 establecieron que `player_stats.team_id` y
`player_events.team_id` son snapshots exactos por partido. Sin embargo, el ranking
por temporada todavia obtiene el equipo visible desde el `team_id` representativo de
`SFASeasonScore`, elegido por competicion y puntos. En una transferencia dentro de la
misma temporada puede mostrar el club anterior aunque ya exista una aparicion posterior
verificada con el club nuevo.

Ademas, dos lecturas que buscan la ultima aparicion (`PlayerRepository` y
`EnrichPositionRepository`) ordenan por `player_stats.fixture_id DESC`. El ID interno
no es una fecha y puede quedar fuera de orden por backfills o ingestas tardias.

La jerarquia de presentacion documentada en 0028 tambien permite caer a una aparicion
de otra temporada o a `players.team_id`. Ese fallback puede atribuir a una vista
historica un club en el que el jugador no participo dentro del alcance consultado.

Por separado, Fermín López esta almacenado como `EXT`, pero debe resolverse como `MCO`,
y Martín Zubimendi aparece como `DC`, pero debe resolverse como `MC`. Ambos casos usan
`domain/player_position_overrides.py`, que ya centraliza estas correcciones.

## Objetivo

1. Mostrar en rankings y encabezados de jugador acotados por temporada/scope el ultimo
   equipo cronologico con una aparicion verificada dentro del alcance efectivo.
2. Mantener intactos los snapshots exactos de cada partido y el equipo representativo
   persistido en `SFASeasonScore`.
3. Dejar de tratar `fixture_id` como reloj donde se resuelve la ultima aparicion.
4. Resolver a Fermín López como `MCO` y a Martín Zubimendi como `MC` usando el mecanismo
   de overrides de dominio y no una condicion en frontend o schemas HTTP.

## Restricciones

- No se actualizan `player_stats.team_id` ni `player_events.team_id`.
- No se cambia como ingestion, rebuild o scoring eligen y persisten
  `SFASeasonScore.team_id` (equipo de mayor suma de minutos por
  jugador/competicion/temporada).
- No se modifican puntos, breakdowns, formulas, ELO, bonos ni logros y no se dispara un
  recalculo.
- No se agregan migraciones, columnas, tablas, endpoints ni campos HTTP.
- `team_name` y `team_logo_url` conservan su contrato; cambia unicamente la fuente del
  equipo visible en lecturas con temporada/scope.
- El historico `all` queda fuera de alcance: no tiene un limite temporal unico al cual
  aplicar esta politica.
- La vista exclusiva de un torneo de selecciones conserva su seleccion visible. La
  preferencia por club aplica a temporadas de premio o temporadas fisicas no filtradas.

## Definiciones

### Aparicion verificada

Una fila de `player_stats` es candidata solo cuando:

- `player_stats.team_id IS NOT NULL`;
- esta unida al fixture exacto por `player_stats.fixture_id = fixtures.id`;
- `player_stats.team_id` coincide con `fixtures.home_team_id` o
  `fixtures.away_team_id`; y
- el par `(fixtures.season, fixtures.competition_id)` pertenece al alcance efectivo.

No se exige un evento: un partido valido puede no tener `player_events`. Tampoco se usa
`player_events` para inferir el club visible; su snapshot permanece como evidencia del
evento exacto.

### Alcance efectivo

| Consulta | Apariciones candidatas |
|---|---|
| `season=<fisica>` sin competicion | Fixtures de esa season en competiciones `club` |
| `scope=<award_period>` sin competicion | Fuentes del scope cuya competicion es `club` |
| `competition_id=<id>` | Interseccion exacta del season/scope con esa competicion |
| `scope=<tournament>` | Fuente unica del torneo, incluso si es `national_team` |

El filtro de competicion siempre prevalece sobre la preferencia general por club. Asi,
un ranking del Mundial muestra la seleccion y un award period compuesto muestra el
ultimo club de su componente regular.

## Decisiones

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Crear una proyeccion SQL read-only de ultima aparicion verificada | Reescribir `SFASeasonScore.team_id` al transferirse | Separa presentacion cronologica de la representacion interna usada por scoring y logros |
| Ordenar por `Fixture.played_at DESC`, `Fixture.id DESC`, `PlayerStats.id DESC` | Ordenar solo por `fixture_id DESC` | La fecha es la cronologia; IDs solo resuelven empates de forma determinista |
| Aplicar exactamente los pares del season/scope y el filtro de competicion | Buscar la ultima aparicion global | Impide mostrar un club futuro o ajeno al periodo historico |
| Validar el equipo contra home/away del fixture | Aceptar cualquier `player_stats.team_id` no nulo | Reutiliza la invariante auditable de 0028/0029 |
| No usar `players.team_id` ni apariciones fuera del scope como fallback | Garantizar siempre un club aunque sea historicamente imposible | Es preferible excluir una fila inconsistente y hacer visible el problema de datos |
| Reutilizar la misma proyeccion en listado, total y busqueda por equipo | Cambiar solo el nombre mostrado | Mantiene coherencia de filtros, conteo y paginacion |
| Conservar la seleccion de competicion representativa actual | Hacer que el ultimo fixture decida tambien la competicion representativa | El pedido cambia el club visible, no la agregacion ni la representacion interna del score |
| Agregar Fermín López y Martín Zubimendi al registro y resolverlos globalmente como `MCO` y `MC` | Regla condicional en React o en el schema | Los overrides quedan normalizados, testeables y compartidos por los consumidores existentes |

## Read model propuesto

`SFAScoreRepository` construira un subquery reutilizable con una fila por jugador:

```text
latest_verified_team(
    player_id,
    display_team_id,
    display_competition_id,
    played_at,
    fixture_id
)
```

La fila `rn = 1` se obtiene con `row_number()` particionado por `player_id` y ordenado
por fecha descendente. `Team` se une mediante `display_team_id`; el subquery existente
de score representativo puede seguir determinando `competition_name` y el contexto de
agregacion, pero su `team_id` deja de alimentar `team_name` y `team_logo_url`.

Las consultas afectadas son:

- `get_ranking` y su wrapper `get_ranking_for_scope`;
- `get_ranking_total` y su wrapper `get_ranking_total_for_scope`;
- `get_best_score_for_player_season`;
- `get_player_detail_for_scope`.

Listado y total deben exigir la misma aparicion verificada. Si un score no tiene ninguna
candidata, no se le asigna otro club: queda fuera de esa respuesta y del total, y el test
de integridad documenta el caso. No se altera ni elimina su fila de score.

La busqueda por nombre de equipo se aplica al equipo visible resuelto, no al
`SFASeasonScore.team_id` representativo. El ranking por puntos, sus desempates y sus
bonos permanecen iguales para el conjunto valido.

## Orden cronologico fuera del ranking

Las lecturas ya introducidas por 0028 que significan literalmente "ultima aparicion"
deben usar el mismo orden cronologico:

- `PlayerRepository.get_by_id`: ultima aparicion verificada global;
- `EnrichPositionRepository.get_players_without_tm_source`: ultima aparicion verificada
  global o de la season solicitada.

En ambos casos `Fixture.played_at` es la clave primaria de orden y `Fixture.id`/
`PlayerStats.id` son desempates. No se amplian sus fallbacks ni se modifica ningun dato.

## Override de posicion

`domain/player_position_overrides.py` incorporara las variantes normalizadas `fermin`
y `fermin lopez` en los terminos de `MCO`, y `zubimendi` y `martin zubimendi` en los
terminos de `MC`. `position_for_context()` devolvera `MCO` para Fermín López y `MC`
para Martín Zubimendi independientemente del club. La normalizacion existente debe
resolver los nombres con y sin acentos.

El filtro de ranking por `MCO`, el total y la posicion mostrada deben incluirlo; el filtro
`EXT` debe excluirlo aunque `players.position` siga almacenado como `EXT`. No se agrega
ninguna regla de UI y no se cambia `domain/position_mapping.py` en este fix.

## Compatibilidad con 0028 y 0029

Este spec no reemplaza la fuente de verdad por partido de 0028/0029. Solo reemplaza, para
lecturas historicas acotadas, la jerarquia de presentacion de 0028 que permitia salir del
scope. El repair de 0029 sigue siendo el mecanismo para resolver snapshots nulos; este
fix no los rellena ni los oculta con datos de otra temporada.

## Fuera de alcance

- Cambiar el equipo representativo de `SFASeasonScore`.
- Recalcular scores historicos por el override de posicion.
- Modificar logros, scoring, ELO, ingestion o repair de snapshots.
- Corregir todos los mappings de posicion existentes.
- Cambiar el ranking historico de todas las temporadas.
- Agregar una tabla de afiliaciones de jugadores.

## Domain model

No se agregan entidades, aggregates ni persistencia. Es una correccion del read model y
una extension de una politica de posicion existente. No requiere `@DDD-Designer`.

## Criterios de aceptacion

1. Con dos equipos validos en la misma season, el ranking muestra el del fixture con
   `played_at` mas reciente aunque su `fixture_id` sea menor.
2. Una aparicion posterior fuera del season/scope o de la competicion filtrada no cambia
   el equipo visible.
3. Un `team_id` que no sea home/away se ignora y nunca se presenta.
4. Sin aparicion verificada en el alcance no se usa otra season, `players.team_id` ni el
   equipo representativo del score como fallback.
5. Listado, total y busqueda por club usan el mismo equipo visible.
6. Los snapshots por fixture y todos los valores de `SFASeasonScore` quedan byte a byte
   iguales antes y despues de ejecutar las lecturas.
7. Fermín López se muestra y filtra como `MCO`, no como `EXT`, sin codigo frontend.
8. Martín Zubimendi se muestra y filtra como `MC`, no como `DC`, sin codigo frontend.
9. El ranking Mundial aislado sigue mostrando la seleccion del jugador.
