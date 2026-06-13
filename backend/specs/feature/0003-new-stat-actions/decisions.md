# 0003 — Nuevas acciones de stat: BLOCKS, XA_NO_ASSIST, XG_NO_GOAL, FOULS_DRAWN, CLEARANCES

## Contexto de negocio

Seis campos ya almacenados en `player_stats` no generan puntos SFA porque o bien sus `base_pts` son 0 en `BASE_POINTS_TABLE`, o bien no están conectados al dict `stats_for_scoring` en `ingest_competition.py`. Este spec activa los cinco `ActionType` relevantes para que contribuyan al puntaje de cada jugador por partido.

Los seis campos raw y su mapeo:

| Campo raw en `player_stats` | Cálculo para scoring | ActionType |
|-----------------------------|----------------------|------------|
| `blocks` | `ps.blocks` | `BLOCKS` |
| `passes_key - assists` | `ps.passes_key - ps.assists` | `XA_NO_ASSIST` |
| `shots_on - goals` | `ps.shots_on - ps.goals` | `XG_NO_GOAL` |
| `dribbles_success - goals` | `ps.dribbles_success - ps.goals` | `XG_NO_GOAL` (fusionado, ver D6) |
| `fouls_drawn` | `ps.fouls_drawn` | `FOULS_DRAWN` (nuevo) |
| `clearances` | `ps.clearances` | `CLEARANCES` (nuevo) |

---

## Decisiones

| ID | Decisión | Valor |
|----|----------|-------|
| D1 | ActionType nuevos requeridos | `FOULS_DRAWN` y `CLEARANCES` no existen en el enum — se deben añadir. `BLOCKS`, `XA_NO_ASSIST` y `XG_NO_GOAL` ya existen |
| D2 | @DDD-Designer requerido | Sí, para los 2 ActionType nuevos (`FOULS_DRAWN`, `CLEARANCES`). Son value objects del dominio de scoring; su adición debe ser aprobada por DDD-Designer antes de implementarlos |
| D3 | Proxy de XG_NO_GOAL | Se usa `shots_on - goals` como proxy de xG no convertido. Es la señal más directa disponible desde API-Football. Cuando Understat proporcione xG real, se reemplazará este cálculo; el `ActionType` ya está definido, solo cambiará el input |
| D4 | XG_NO_GOAL: fusión de proxies | El spec original mencionaba dos fuentes (`dribbles_success - goals` y `shots_on - goals`). Se usa solo `shots_on - goals` porque es la definición correcta de xG no convertido. Los regates exitosos sin gol no son un proxy razonable de xG. `dribbles_success` ya puntúa como `DRIBBLES_WON` y no debe contar doble |
| D5 | XA_NO_ASSIST: cálculo | `passes_key - assists`. Un pase clave es un pase que resulta en remate; si no termina en gol, es un "xA sin asistencia real". Se resta `assists` para evitar doble-conteo con `ActionType.ASSIST` ya puntuado vía `score_event()` |
| D6 | Floor de valores derivados | Los valores calculados (`shots_on - goals`, `passes_key - assists`) se clampean a `max(0, valor)` antes de entrar a `stats_for_scoring`. Un resultado negativo sería error de datos del provider; no debe producir puntos negativos |
| D7 | `BASE_POINTS_TABLE`: valores acordados | Ver tabla completa abajo. Los valores con 0 significan "no aplica para ese grupo posicional" (la lógica de `score_match_stats` ya los salta silenciosamente) |
| D8 | `CLEARANCES` con FW=0 | Un delantero no debería recibir puntos por despejes — es estadísticamente raro y semánticamente incorrecto. `base_pts=0` en FW hace que `score_match_stats` lo omita |
| D9 | Path de scoring | Todos estos ActionType usan el path `score_match_stats()` (M1×M2 solamente), igual que `DUELS_WON`, `TACKLES_INTERCEPTIONS`, `BLOCKS` y `DRIBBLES_WON`. No se necesita `score_event()` |
| D10 | No hay cambio de schema en BD | `fouls_drawn` y `clearances` ya existen en `player_stats` (añadidos en 0002). No hay migración Alembic |
| D11 | No hay cambio en el provider | `ps.fouls_drawn` y `ps.clearances` ya se extraen de API-Football y se pasan a `upsert_player_stats` (wired en 0002). El DTO `PlayerStatsRawDTO` ya los tiene |
| D12 | Idempotencia | Sin cambio — `delete_player_events_for_fixture` borra todos los eventos del player-fixture antes de reescribir. El row STATS agregado incluirá los nuevos puntos automáticamente |
| D13 | Breakdowns | Los puntos de los 5 ActionType se acumulan en el mismo bucket `"stats"` del breakdown. No se necesitan buckets separados; la granularidad por acción no está expuesta en el API actual |

---

## BASE_POINTS_TABLE acordada

| ActionType | FW | MF | DF |
|------------|----|----|----|
| `BLOCKS` | 150 | 100 | 70 |
| `XA_NO_ASSIST` | 150 | 120 | 180 |
| `XG_NO_GOAL` | 70 | 50 | 30 |
| `FOULS_DRAWN` | 50 | 35 | 20 |
| `CLEARANCES` | 0 | 20 | 25 |

Los valores actuales (pre-0003) en la tabla son 0 para todos. Este spec los reemplaza por los valores de arriba.

---

## Impacto en el modelo de dominio

### Cambios que requieren @DDD-Designer

- `ActionType.FOULS_DRAWN` — nuevo miembro del enum (value objects de dominio)
- `ActionType.CLEARANCES` — nuevo miembro del enum (value objects de dominio)

### Cambios que NO requieren @DDD-Designer

- `BASE_POINTS_TABLE` en `services.py` — tabla de configuración, no nuevo comportamiento de dominio
- `stats_for_scoring` dict en `ingest_competition.py` — wiring de aplicación
- Entradas de 0 → valor real en `BASE_POINTS_TABLE` para `BLOCKS`, `XA_NO_ASSIST`, `XG_NO_GOAL` — no hay nuevo concepto de dominio, solo activación de entradas ya definidas

---

## Modelo de dominio — cambios mínimos

No se crean nuevas entidades ni value objects de tipo compuesto. No se modifica `EventType`. No se modifica el schema de BD. No se añaden nuevos multiplicadores. El motor de `score_match_stats()` no cambia su lógica — solo recibe más entradas.
