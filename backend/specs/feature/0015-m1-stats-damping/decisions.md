# M1 Stats Damping — Suavizado de M1 para acciones acumulativas

## Contexto de negocio

Bruno Fernandes (Manchester United, MC) aparece #4 global en la temporada 2024 debido a una
inflación sistemática de M1. Man United terminó 15° en la Premier League, lo que produce
`avg_m1 ≈ 1.182` para todos sus eventos. Arsenal, por contraste, tiene `avg_m1 ≈ 0.708`.

El problema raíz es que M1 fue diseñado como multiplicador de **contexto puntual** (¿qué
tan difícil es marcar/asistir contra ese rival hoy?), pero al aplicarse igual sobre acciones
acumulativas de stats (pases completados, duelos ganados, intercepciones…) se convierte en
un **multiplicador permanente de equipo** que premia indiscriminadamente a jugadores de
equipos malos.

Acciones decisivas (gol, asistencia, penalti ganado) sí merecen M1 completo: hacer un gol
contra el City desde el United es genuinamente más difícil. Pero completar 70 pases en un
partido no se vuelve más difícil porque tu equipo quede 15°.

Este fix preserva la semántica correcta de M1 para acciones decisivas y lo amortigua para
stats acumulativas mediante un nuevo parámetro configurable en `ScoringConfig`.

## Restricciones

- Backward compatibility: `ScoringConfig.default()` (v1) debe seguir funcionando sin cambios
  de comportamiento. Los nuevos campos tienen `default=1.0` (sin amortiguación = sin cambio).
- `ScoringConfig` es un `frozen dataclass` — no se puede mutar. Los nuevos campos son
  adicionales con valores por defecto.
- `ScoringConfig.from_dict()` y `to_dict()` deben soportar los nuevos campos con fallback
  a sus defaults para configs antiguas almacenadas en DB (retrocompatibilidad de JSONB).
- No se añaden migraciones de DB: los nuevos parámetros viven solo en `config_json` JSONB.
- El recálculo no es automático: quien implemente deberá disparar
  `CalculateScoresForRulesVersionUseCase` con `force_recalculate=True` tras actualizar la
  config de la rules version.

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Nuevo campo `m1_stats_weight: float` en `ScoringConfig` con default=1.0 | Hardcodear 0.35 | Configurable por versión de reglas; permite A/B testing |
| Nuevo campo `m1_stats_clamp: tuple[float, float]` con default=(0.85, 1.20) | Usar m1_clamp existente | Las stats necesitan un rango más estrecho que acciones decisivas (0.6–1.8) |
| Aplicar amortiguación solo en `_score_stats_event` | Crear un nuevo value object M1Stats | Menos superficie de código; la lógica es `clamp(1.0 + (M1-1.0)*weight)`, no justifica VO |
| `default_v2` usa `m1_stats_weight=0.35`, `m1_stats_clamp=(0.85, 1.20)` | weight=0.5 | Con 0.35: MU (M1=1.182) → M1_stats=1.064; Arsenal (M1=0.708) → M1_stats=0.901. Rango reducido de ±50% a ±15% |
| Acciones decisivas: GOAL, GOAL_PENALTY, GOAL_SHOOTOUT, ASSIST, CORNER_ASSIST, PENALTY_WON usan M1 completo | PENALTY_WON en stats | PENALTY_WON ya se registra en el STATS event como campo; sí merece M1 completo dentro de stats |
| M1 se calcula una sola vez y se ramifica en `_score_stats_event` | Calcular M1_stats como VO separado | Eficiencia; el M1 original ya existe como `m1.value` |
| Midfield bonuses NO usan M1 (confirmado) | Aplicar M1_stats a mc_bonus | Ya calculados como `base × M2 × Mrating × competition_weight`. Documentado como intencional |
| `calculation_details` de stats recibe 4 campos nuevos de trazabilidad | Campos separados en DB | JSONB ya absorbe campos adicionales sin migración |
| `m1_source` se determina en el use case (ya tiene `strength_used` bool) | En el VO | El use case es quien tiene el contexto completo del evento |
| Diagnóstico de `team_strengths` poblado para season=2024 se hace en plan.md como paso 0 | Dentro del spec | Es una verificación operacional, no una decisión de diseño |

## Domain Model

No se requieren nuevas entidades de dominio. Los cambios son:

1. **`ScoringConfig` (value object existente):** dos campos nuevos opcionales.
2. **`_score_stats_event` (use case existente):** bifurca el M1 en decisivas vs acumulativas.
3. **`calculation_details` (dict JSONB):** 4 campos de trazabilidad adicionales.

### Campos nuevos en `ScoringConfig`

```python
# En ScoringConfig (frozen dataclass)
m1_stats_weight: float = 1.0          # factor de amortiguación [0.0, 1.0]. 1.0 = sin cambio (v1 compat)
m1_stats_clamp: tuple[float, float] = (0.85, 1.20)  # rango del M1 suavizado para stats
```

**Fórmula de amortiguación:**
```
M1_stats = clamp(
    1.0 + (M1_original - 1.0) * m1_stats_weight,
    m1_stats_clamp[0],
    m1_stats_clamp[1]
)
```

**Ejemplos con default_v2 (weight=0.35, clamp=(0.85, 1.20)):**
- Man United (M1=1.182): `1.0 + 0.182 * 0.35 = 1.064` → dentro de clamp
- Arsenal (M1=0.708): `1.0 + (-0.292) * 0.35 = 0.898` → dentro de clamp
- Extremo bajo (M1=0.60): `1.0 + (-0.40) * 0.35 = 0.860` → clamp a 0.85
- Extremo alto (M1=1.80): `1.0 + 0.80 * 0.35 = 1.28` → clamp a 1.20

### Clasificación de acciones en `_score_stats_event`

El evento STATS agrega en un solo registro todas las stats del partido. Dentro del loop
`for action, count in raw_stats.items()` se necesita saber qué multiplicador M1 usar
por acción:

**Acciones decisivas en stats (usan M1 completo):**
```python
_M1_DECISIVE_STATS_ACTIONS = frozenset({
    ActionType.PENALTY_WON,   # penalti ganado — mérito directo contra el rival
})
```

Nota: GOAL y ASSIST dentro del STATS event se usan solo como sustracción para calcular
XG_NO_GOAL y XA_NO_ASSIST; los puntos de GOAL/ASSIST se registran en individual events.
Por eso `_M1_DECISIVE_STATS_ACTIONS` solo contiene PENALTY_WON.

**Acciones acumulativas (usan M1_stats):** el resto — PASSES_COMPLETED, XA_NO_ASSIST,
XG_NO_GOAL, DUELS_WON, TACKLES, INTERCEPTIONS, BLOCKS, FOULS_DRAWN, DRIBBLES_WON,
FOULS_COMMITTED, YELLOW_CARD, RED_CARD, DRIBBLES_PAST.

**Estrategia de implementación:** calcular `base_total` con dos acumuladores separados
(`decisive_base` y `accumulative_base`), multiplicar cada uno por su M1 correspondiente,
luego aplicar M2 × Mrating × minutes_scale al resultado combinado.

### Campos de trazabilidad nuevos en `calculation_details` (stats events)

```python
{
    ...campos existentes...,
    "m1_source": "team_strength" | "legacy_position",  # cómo se calculó M1
    "m1_original": 1.182,      # M1 antes de amortiguación
    "m1_stats_weight": 0.35,   # weight usado (de config)
    "m1_stats_applied": 1.064, # M1 efectivo usado para stats acumulativas
}
```

## Integraciones externas

Ninguna. Este spec es puramente interno al motor de scoring.
