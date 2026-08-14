# Torneos de temporada y correccion del comparador

## Contexto de negocio

El Mundial 2026 ya termino y no debe ocupar una seccion principal permanente. SFA necesita una
pagina de resultados para seguir la temporada de clubes vigente: competiciones disponibles,
fechas, marcadores, clasificaciones y cruces. En paralelo, el comparador necesita una jerarquia
visual mas legible y corregir los hitos por partido que hoy aparecen siempre en cero.

## Restricciones

- Se mantiene Router -> Use Case -> Port -> Repository para toda lectura nueva.
- La pagina publica consume exclusivamente datos persistidos en SFA; abrirla no llama a
  API-Football.
- La temporada se expresa con el ano inicial usado por `fixtures.season`.
- Solo se listan competiciones con fixtures en la temporada seleccionada.
- Las tablas usan el ultimo `standing_snapshot` disponible. Una competicion sin tabla debe
  devolver una lista vacia, no un error global.
- Los cruces se derivan de fixtures cuya fase no sea regular o de grupos; no se crea persistencia
  paralela para brackets.
- Las rutas antiguas del Mundial se preservan mientras existan enlaces internos o indexados.
- El contrato existente de `GET /compare` se mantiene aditivo y compatible.
- La interfaz conserva el sistema visual SFA. Los colores de jugadores se desaturan, los numeros
  estadisticos se muestran blancos y el oro sigue reservado a ranking y puntos SFA.

## Decisiones tomadas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Crear endpoints genericos de torneos por temporada | Generalizar el repositorio del Mundial | El repositorio del Mundial mezcla cache, proveedor externo y conceptos exclusivos de selecciones. |
| Leer fixtures y standings locales | Consultar API-Football desde React | Evita latencia, limites y resultados inconsistentes con la base usada por SFA. |
| Separar catalogo y detalle de torneo | Devolver toda la temporada en una respuesta | Reduce payload y permite cambiar de competicion sin cargar miles de partidos. |
| Derivar cruces desde `fixture.stage` | Crear una tabla de brackets | Los cruces ya estan representados por fixtures y fase; duplicarlos agregaria sincronizacion. |
| Solicitar breakdown en `ComparePlayersUseCase` | Inferir hitos desde goles totales | Hat-tricks y dobletes requieren conteos por partido, ya disponibles en el repositorio. |
| Derivar el color lateral del equipo y desaturarlo | Mantener colores fijos por lado | Refuerza la identidad de cada jugador sin competir con los valores blancos. |
| Redirigir `/mundial` a `/torneos` | Eliminar las rutas | Conserva enlaces previos y evita errores 404. |

## Contratos de lectura

`GET /tournaments?season=2026` devuelve la temporada resuelta y las competiciones que tienen
fixtures, con conteos de partidos jugados y pendientes.

`GET /tournaments/{competition_id}?season=2026` devuelve metadatos, fixtures ordenados por fecha,
la ultima tabla disponible y los fixtures eliminatorios agrupables por `stage`.

Los equipos incluyen `external_id` para construir sus escudos con el proveedor de medios ya usado
por el frontend. Los fixtures incluyen marcador nullable, estado, fecha, jornada y fase.

## Domain Model

No se agregan entidades ni value objects. Se agregan DTOs de lectura inmutables y un port de
consulta de torneos. No se modifica el dominio de scoring.

## Integraciones externas

Ninguna en tiempo de lectura. La ingestion existente sigue siendo responsable de cargar fixtures,
marcadores y standings desde API-Football.

Los colores del comparador se resuelven localmente a partir del nombre del equipo. Los clubes y
selecciones reconocidos usan su color de marca; los demas reciben un fallback estable derivado del
nombre. La interfaz mezcla el color con gris antes de aplicarlo para evitar saturacion excesiva.
