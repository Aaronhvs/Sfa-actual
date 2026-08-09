# Normalizacion del valor de las fases de Champions

## Contexto de negocio

El motor combina la fuerza del rival (M1), la fase de la competicion (M2) y bonos por el
palmares alcanzado. En Champions League, los factores M2 historicos (1.5 a 2.8) y los bonos
altos desde octavos vuelven a premiar varias veces el mismo contexto competitivo que M1 ya
captura mediante ELO. Esto eleva demasiado a jugadores con una buena campana europea aunque
no alcancen la final ni ganen un titulo.

El subcampeonato si debe otorgar puntos: llegar a la final es un logro relevante. Debe quedar
claramente por debajo del campeonato y por encima de la semifinal.

## Restricciones

- Se mantiene Router -> Use Case -> Port -> Repository.
- La rules version continua siendo la fuente de los bonos de palmares.
- `competition_stages` continua siendo la fuente de M2 por partido.
- No se agregan endpoints, entidades ni tablas.
- La migracion debe ser idempotente y actualizar la rules version activa de produccion, id 4.
- Los defaults de codigo, el seed operativo, la base de datos y la pagina de metodologia deben
  comunicar los mismos valores.
- El ajuste exige recalcular el periodo `season-2025` completo porque modifica puntos ya
  materializados.

## Decisiones tomadas

| Decision | Alternativa descartada | Razon |
|---|---|---|
| Reducir M2 de Champions a 1.15, 1.30, 1.45, 1.65 y 1.90 | Mantener 1.5 a 2.8 | M1 ya recompensa la dificultad del rival; M2 debe medir trascendencia sin duplicarla. |
| Mantener atenuacion de estadisticas M2 en 0.5 | Crear una excepcion exclusiva para Champions | La regla existente ya reduce de forma coherente el efecto sobre estadisticas agregadas. |
| Usar bonos 1000, 2000, 3500, 6500, 11000 y 15000 | Eliminar puntos de subcampeon | Conserva una progresion visible y reconoce llegar a la final. |
| Actualizar la version 4 mediante migracion SQL | Crear una rules version sin activacion automatica | El recalculo solicitado ya esta ligado a la version 4 y debe ser reproducible en produccion. |
| Recalcular todo `season-2025` | Corregir solo a jugadores auditados | M2 afecta todos los eventos de Champions y el palmares afecta todos los participantes elegibles. |

## Valores canonicos

### M2 Champions League

| Fase | M2 acciones | M2 efectivo para estadisticas con atenuacion 0.5 |
|---|---:|---:|
| Grupos | 1.15 | 1.075 |
| Octavos | 1.30 | 1.15 |
| Cuartos | 1.45 | 1.225 |
| Semifinal | 1.65 | 1.325 |
| Final | 1.90 | 1.45 |

### Bonos base de palmares Champions League

| Fase | Puntos base |
|---|---:|
| Clasificacion a eliminatorias | 1000 |
| Octavos | 2000 |
| Cuartos | 3500 |
| Semifinal | 6500 |
| Subcampeon | 11000 |
| Campeon | 15000 |

El bono final de cada jugador sigue aplicando participacion, peso de competicion y factor de
rendimiento. Los importes de la tabla son la base, no una asignacion plana por futbolista.

## Domain Model

No se agregan entidades ni value objects. Se modifican valores de configuracion de scoring ya
existentes y datos de referencia persistidos.

## Flujo de despliegue

1. Desplegar codigo y worker con los nuevos defaults.
2. Ejecutar la migracion que actualiza M2 y la configuracion de la rules version 4.
3. Ejecutar `recalculate_award_period_task` para `season-2025`, version 4, con `force` e
   inferencia habilitados.
4. Verificar fases, bonos, totales y ranking una vez finalice la tarea.

## Integraciones externas

Ninguna nueva.
