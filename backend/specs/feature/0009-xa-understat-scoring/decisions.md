# Spec 0009 — xa (Understat) como señal de scoring de creatividad ofensiva

## Contexto de negocio

El sistema de scoring actual penaliza a mediocampistas creativos porque
`ActionType.XA_NO_ASSIST` se calcula como `max(0, passes_key - assists)`: un conteo entero
de pases clave que no terminaron en asistencia oficial. Esta métrica captura solo el último
pase antes de un disparo, sin ponderar la calidad esperada del disparo generado.

`player_stats.xa` (columna `Numeric(5,4)`) existe en la DB pero **está a 0 para todos los
jugadores**. La causa raíz es doble:

1. **FBref perdió acceso a su proveedor de datos avanzados en enero 2026.** `xG`, `xA` y
   `progressive passes` ya no existen en FBref. `EnrichWithFBrefUseCase` no puede escribir
   `xa` porque la fuente dejó de existir.

2. **`EnrichWithUnderstatUseCase` tiene `xa` disponible en `UnderstatPlayerDTO` pero nunca
   lo escribe a `player_stats`.** El use case solo guarda `understat_id` y actualiza `psxg`
   por evento. `xa`, `key_passes` y `npxg` de `UnderstatPlayerDTO` se descarten.

Por tanto, este spec tiene dos pasos obligatorios:

- **Paso 1 (Enrich):** Extender `EnrichWithUnderstatUseCase` para que escriba `xa` a
  `player_stats` después del name matching, usando el mismo método
  `update_player_stats_from_fbref` con `CASE WHEN xa = 0 THEN :val ELSE xa END`.
- **Paso 2 (Score):** Conectar ese `xa` al scoring en `recalculate_scores.py`, con fallback
  a `max(0, passes_key - assists)` para jugadores no matcheados y Champions League.

## Restricciones

- **Understat NO cubre Champions League.** El fallback a `passes_key - assists` es
  obligatorio para UCL y para cualquier jugador que no haya sido matcheado en Understat.
- `player_stats.xa` almacena el total de temporada de Understat, escrito en **todas** las
  filas del player-season via `update_player_stats_from_fbref`. No es un valor per-fixture
  real: es el agregado de temporada replicado en cada fila. El mismo patrón que FBref usaba.
- `PlayerStatsEventRecalcRow` no expone `xa` — hay que extender el DTO y la query del
  repositorio.
- `xa = 0.0` puede significar dos cosas distintas: (a) Understat no enriqueció al jugador
  (UCL, no matcheado), o (b) el jugador genuinamente no generó expected assists. Ambos casos
  requieren fallback — no hay manera de distinguirlos en scoring.
- **Solo se escribe `xa`** desde Understat. `npxg` es redundante porque API-Football ya
  provee `xg` por fixture. `key_passes` de Understat es también redundante con
  `passes_key` de API-Football (ya poblado per fixture). Escribir valores de temporada
  encima de datos per-fixture rompería la granularidad.
- El scoring de stats usa `value × base_pts × combined` donde `value` puede ser float.
  `BASE_POINTS_TABLE` y `SFAScoringService` ya aceptan float — no hay cambio de firma.
- No se introducen nuevas entidades de dominio: `ActionType.XA_NO_ASSIST` representa
  semánticamente "creatividad ofensiva no convertida en asistencia", exactamente lo que
  mide `xa`.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Escribir `xa` de Understat a `player_stats` vía `update_player_stats_from_fbref` | Nuevo método `update_player_stats_from_understat` en el Protocol | El método existente ya implementa `CASE WHEN xa = 0 THEN :val ELSE xa END`, semántica idéntica. Añadir un método al Protocol requiere actualizar el Fake en tests y la implementación concreta sin ganancia real |
| Solo escribir `xa`, descartar `key_passes` y `npxg` | Escribir los tres campos | `passes_key` ya viene de API-Football per fixture; sobrescribir con totales de Understat rompería granularidad. `npxg` es redundante con `xg` de API-Football. Solo `xa` llena un gap real |
| Fallback a `max(0, passes_key - assists)` cuando `xa == 0` | Dejar `xa` como único valor | Understat no cubre UCL ni todos los jugadores. El fallback preserva scoring existente para casos no enriquecidos |
| Threshold de fallback: `xa > 0` | Threshold absoluto (ej: xa > 0.1) | El valor `0.0` exacto solo ocurre cuando Understat no escribió el campo (condición `CASE WHEN xa = 0`). Un xa real de 0.05 ya está enriquecido y debe usarse |
| Reutilizar `ActionType.XA_NO_ASSIST` con nueva fuente de valor | Crear `ActionType.XA_UNDERSTAT` separado | No hay distinción semántica: ambos miden creatividad no convertida. Cambiar a nuevo ActionType requeriría DDD Designer + migración de `BASE_POINTS_TABLE` sin ganancia conceptual |
| `xa` como valor float directo (no multiplicador) | Escalar xa por minutos jugados | El scoring ya acepta float. La escala de temporada de Understat es comparable entre jugadores. Normalizar por minutos introduciría complejidad sin evidencia de que mejore el ranking |
| No se requiere migración de DB | Agregar columna nueva | `player_stats.xa` ya existe como `Numeric(5,4)`. El campo está a 0 porque nunca se escribió, no porque no exista |
| No requiere invocar DDD Designer | Invocar @DDD-Designer | `ActionType`, `BASE_POINTS_TABLE` y `SFAScoringService` no cambian |

## Domain Model

No aplica. Esta feature no introduce nuevas entidades de dominio. El único cambio de dominio
sería si se creara un `ActionType` nuevo, lo cual fue descartado.

## Integraciones externas

- **Understat** (ya integrado): fuente de `xa` via `UnderstatProviderPort.fetch_league_players`.
  No hay nuevas llamadas ni cambios en el proveedor.
- No se llama a ninguna API externa durante el recálculo. La columna `player_stats.xa` es
  la única fuente de verdad en Phase 2.
- **Champions League**: Understat no cubre UCL. `EnrichWithUnderstatUseCase` ya tiene el
  early-return para Champions League en la línea 38. El fallback en scoring cubre este caso.
