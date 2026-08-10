# Comparador analitico de jugadores

## Contexto de negocio

El comparador existente esta deshabilitado y su endpoint solo devuelve el detalle basico de dos
jugadores. El producto necesita comparar el rendimiento completo que ya alimenta el motor SFA:
volumen, eficiencia, contexto, disciplina y produccion por posicion. Tambien necesita mostrar en
que tramos del partido aparece el impacto decisivo de cada jugador.

## Restricciones

- Se mantiene Router -> Use Case -> Ports -> Repositories.
- No se agregan tablas, migraciones ni proveedores externos.
- El comparador debe respetar los mismos award period scopes y rules versions que ranking y
  perfiles.
- Los campos `player_a` y `player_b` actuales se conservan para no romper consumidores.
- La respuesta analitica se agrega de forma aditiva bajo `player_a_analytics` y
  `player_b_analytics`.
- Precision, conversion y tasas por 90 se derivan de estadisticas persistidas; no modifican el
  scoring.
- La grafica temporal solo usa eventos con minuto real y puntos positivos. Los eventos `stats`
  agregados no se distribuyen artificialmente por minuto.
- La interfaz sigue PRODUCT.md, DESIGN.md y el sistema visual SFA: dark-only, alta densidad,
  radios de 4 a 6 px y oro reservado a puntos y ranking.

## Decisiones tomadas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Ampliar `GET /compare` | Hacer ocho llamadas desde React | Un unico contrato evita estados parciales y centraliza el scope. |
| Orquestar use cases existentes desde `ComparePlayersUseCase` | Consultar ORM desde el router | Conserva arquitectura hexagonal y reutiliza reglas de scope/rules version. |
| Mantener detalles existentes y agregar analytics por jugador | Reemplazar `player_a` y `player_b` | El cambio queda backward compatible. |
| Calcular eficiencias en presentacion desde totales crudos | Persistir columnas derivadas | Evita duplicacion y mantiene auditables numerador y denominador. |
| Usar tramos de cinco minutos en una grafica espejo | Inventar minutos para stats agregadas | La curva representa solo impacto SFA temporal verificable. |
| Separar estadisticas por familias funcionales | Una tabla plana de decenas de filas | Facilita comparar ataque, pase, duelos, defensa y disciplina. |

## Contrato de analytics

Cada lado devuelve:

- `stats`: totales de temporada o scope, incluyendo minutos, remates, pases, regates, duelos,
  defensa, disciplina, porteria y rating.
- `events`: eventos SFA con minuto y multiplicadores contextuales.
- `fixtures`: actuaciones por partido, sin breakdown adicional innecesario.

El frontend deriva:

- precision de tiro = remates a puerta / remates totales;
- conversion = goles / remates totales;
- precision de pase ponderada;
- exito de regate y duelo;
- volumen por 90 minutos;
- impacto temprano (0-45) y tardio (46-90+) desde eventos minutados.

## Domain Model

No se agregan entidades ni value objects. `ComparePlayerAnalytics` y `CompareResult` son DTOs de
aplicacion de solo lectura.

## Integraciones externas

Ninguna nueva.
