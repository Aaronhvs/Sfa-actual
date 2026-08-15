# Lideres estadisticos en torneos

## Contexto de negocio

La portada de Torneos y el detalle de cada competicion necesitan cerrar con una lectura rapida de
los jugadores que dominan el periodo: maximos goleadores, maximos asistidores y los tres mejores
jugadores SFA de cada posicion. El bloque global usa todas las competiciones del scope de temporada;
el bloque de detalle aplica exactamente la misma lectura limitada a una competicion.

## Restricciones

- Los datos deben provenir del ranking SFA persistido, sin calcular estadisticas en React.
- Goleadores y asistidores deben ordenarse por su estadistica, no por puntos SFA.
- El filtro de competicion debe conservar la misma semantica que el ranking principal.
- La rotacion posicional ocurre cada dos segundos, permite navegacion manual y se detiene durante
  interaccion directa para evitar cambios inesperados.
- El componente debe degradar por columna: un fallo parcial no oculta los otros lideres.
- No se agregan tablas, migraciones, providers ni reglas del motor.

## Decisiones tomadas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Reutilizar `GET /ranking` con `bonus_label=Goleador` y `bonus_label=Asistidor` | Ordenar una pagina del ranking en React | El repository ya ordena por goles o asistencias y conserva filtros y empates de forma canonica. |
| Reutilizar `position` para cada grupo posicional | Crear un endpoint agregado nuevo | Son lecturas pequenas, cacheadas durante 60 segundos, y no aparece logica de negocio nueva. |
| Crear un solo componente `TournamentLeaders` | Implementar dos bloques independientes | Portada y detalle deben tener el mismo contrato visual y solo difieren en `competition_id`. |
| Rotar solo posiciones con resultados | Mostrar estados vacios durante el carrusel | Evita que una competicion sin jugadores de una posicion parezca rota. |
| Mantener tres columnas dentro de una sola banda | Tres tarjetas independientes | Conserva la referencia visual sin convertir la pagina en una grilla de tarjetas anidadas. |

## Contrato de lectura

El componente recibe `season` y opcionalmente `competitionId`. Construye el scope canonico
`season-{season}` y solicita tres jugadores por cada vista:

- `bonus_label=Goleador` para maximos goleadores;
- `bonus_label=Asistidor` para maximos asistidores;
- `position` para `DC`, `LAT`, `MC`, `MCO`, `EXT`, `DEL` y `GK`.

Cuando existe `competitionId`, se envia en todas las consultas. Sin ese valor, las consultas son
globales para el scope de temporada.

## Domain Model

No aplica. Es composicion de read models existentes y no introduce entidades, value objects ni
invariantes nuevas.

## Integraciones externas

Ninguna. Fotos, escudos y estadisticas ya forman parte del contrato de ranking de SFA.
