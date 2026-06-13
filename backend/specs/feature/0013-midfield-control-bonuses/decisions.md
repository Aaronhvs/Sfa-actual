# Midfield Control Bonuses — Decisiones arquitectónicas

## Contexto de negocio

El scoring v2 ya premia acciones atómicas (pases, tackles, intercepciones…) pero no
captura el valor compuesto de un mediocampista que domina el partido en múltiples
dimensiones simultáneamente.

Se requieren tres bonuses derivados para posición MC:

| Bonus | Base pts | Condiciones |
|---|---|---|
| CONTROL_MIDFIELD_BONUS | 120 | MC, min ≥ 60, rating ≥ 7.6, passes_completed ≥ 65, passes_accuracy ≥ 90 |
| TWO_WAY_MIDFIELD_BONUS | 100 | MC, min ≥ 60, rating ≥ 7.4, passes_completed ≥ 50, tackles + interceptions ≥ 3 |
| CREATIVE_CONTROL_BONUS | 100 | MC, min ≥ 60, rating ≥ 7.5, passes_completed ≥ 50, passes_key ≥ 2 |

Fórmula de aplicación:

```
mc_bonus_total_base = min(sum(bonuses_earned), 220)   # cap por partido
mc_bonus_final      = mc_bonus_total_base × M2 × Mrating
final_points (stats event) += mc_bonus_final
```

Los tres bonuses son aditivos dentro del cap. El cap es de 220 puntos base.
Solo se aplican multiplicadores M2 (competition stage) y Mrating (rating factor).
M1, M3, M4 y Mvisit NO se aplican sobre estos bonuses.

---

## Restricciones

- Solo aplican a `position_group = PositionGroup.MF` (position `MC`).
- Requieren `rules_version_id != NULL` (flujo versionado). Legacy (NULL) no cambia.
- Configurable vía `ScoringConfig`: nuevo campo booleano `enable_midfield_control_bonuses`
  con default `False` para backward compat.
- `passes_completed` se calcula como `int(passes_total * passes_accuracy / 100)` —
  igual que ya hace `_score_stats_event`. No se almacena como campo derivado en DB.
- No crean un `PlayerEventScore` separado: se suman al `final_points` del evento STATS
  existente y se documentan en `calculation_details`.
- Los bonuses NO son `ActionType` nuevos en el enum: son bonuses derivados calculados
  condicionalmente dentro de `_score_stats_event`, no eventos atómicos ingresados desde
  la API.

---

## Decisiones tomadas

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Bonuses como campos en `ScoringConfig`, no como `ActionType` | Añadir 3 entradas al enum `ActionType` | `ActionType` modela eventos atómicos de partido (goal, assist, tackle…). Los bonuses derivados son lógica de scoring condicional, no eventos. Añadirlos al enum contaminaría `BASE_POINTS_TABLE` con entradas que nunca vienen de la ingesta. |
| Campo único `enable_midfield_control_bonuses: bool = False` | Campos separados por bonus | Granularidad innecesaria para la v2. La activación es todo-o-nada; los umbrales son constantes de negocio, no configurables por ahora. |
| Umbrales hardcoded en `_score_stats_event` (constantes de módulo) | Umbrales como campos de `ScoringConfig` | Los umbrales no varían entre versiones actualmente. Extraerlos a `ScoringConfig` es premature generalization. Se pueden promover en un spec futuro si se necesitan. |
| Cap de 220 pts hardcoded como constante de módulo | Campo `mc_bonus_cap` en `ScoringConfig` | Misma razón. El cap es una constante de negocio estable. |
| Solo M2 × Mrating sobre el bonus | Aplicar el combined completo (M1×M2×M3×M4×Mvisit×Mrating) | El spec lo especifica explícitamente. M1/M3/M4/Mvisit no aplican: el bonus mide el rendimiento global del partido, no el contexto de una acción puntual. |
| La lógica vive en `_score_stats_event` DESPUÉS del cálculo normal | Use case separado / servicio de dominio propio | La cohesión con el cálculo existente de stats es alta. Extraer un método privado `_apply_midfield_bonuses` dentro del mismo use case mantiene el código legible sin crear complejidad estructural nueva. |
| Trazabilidad en `calculation_details` JSONB del mismo `PlayerEventScore` | Campo nuevo en la tabla | La tabla `player_event_scores` ya tiene `calculation_details JSONB`. No se justifica una columna nueva para datos de auditoría. |
| `_score_stats_event` pasa `m2` y `mrating` al método de bonuses | Recalcular M2/Mrating dentro del método | Evitar recalcular value objects que ya existen. Se pasan por referencia (frozen dataclasses, inmutables). |

---

## Domain model — impacto

### `src/sfa/domain/scoring/value_objects.py`

**Cambio:** Añadir campo opcional en `ScoringConfig`:

```python
# En la sección "Optional v2 fields"
enable_midfield_control_bonuses: bool = False
```

**`__post_init__`:** sin cambios (bool no requiere validación adicional).

**`default_v2()`:** añadir `enable_midfield_control_bonuses=True` para activar en v2.

**`default()`:** no cambia (v1 legacy, default del campo = False).

**`from_dict()`:** leer con `bool(d.get("enable_midfield_control_bonuses", False))`.

**`to_dict()`:** añadir `"enable_midfield_control_bonuses": self.enable_midfield_control_bonuses`.

### `src/sfa/application/use_cases/calculate_scores_for_rules_version.py`

**Cambio:** Extraer método privado `_apply_midfield_bonuses` y llamarlo al final de
`_score_stats_event`.

El método privado:
1. Verifica `config.enable_midfield_control_bonuses` — si False, retorna 0.0 y dict vacío.
2. Verifica `group == PositionGroup.MF` — si no, retorna 0.0 y dict vacío.
3. Verifica `minutes >= 60` — si no, retorna 0.0 y dict vacío.
4. Calcula `passes_completed_raw = int((passes_total or 0) * (passes_accuracy or 0) / 100)`.
5. Evalúa los 3 bonuses por sus condiciones (rating, passes_completed, etc.).
6. Suma los bonuses ganados, aplica cap de 220.
7. Aplica `mc_bonus_final = mc_bonus_total_base * m2.value * mrating.value`.
8. Retorna `(mc_bonus_final, audit_dict)`.

El resultado se suma a `final_points` y se añade al `calculation_details` bajo la clave
`"midfield_bonuses"`.

**Firma del método privado:**

```python
def _apply_midfield_bonuses(
    self,
    event: PlayerEventRawContextDTO,
    group: PositionGroup,
    m2: M2CompetitionStage,
    mrating: MratingFactor,
    config: ScoringConfig,
) -> tuple[float, dict]:
    ...
```

### Constantes de módulo en `calculate_scores_for_rules_version.py`

```python
_MC_BONUS_CAP = 220

_MC_BONUS_CONTROL = 120      # CONTROL_MIDFIELD_BONUS
_MC_BONUS_TWO_WAY = 100      # TWO_WAY_MIDFIELD_BONUS
_MC_BONUS_CREATIVE = 100     # CREATIVE_CONTROL_BONUS

_MC_CONTROL_MIN_RATING        = 7.6
_MC_CONTROL_MIN_PASSES        = 65
_MC_CONTROL_MIN_ACCURACY      = 90.0

_MC_TWO_WAY_MIN_RATING        = 7.4
_MC_TWO_WAY_MIN_PASSES        = 50
_MC_TWO_WAY_MIN_DEFENSIVE     = 3    # tackles + interceptions

_MC_CREATIVE_MIN_RATING       = 7.5
_MC_CREATIVE_MIN_PASSES       = 50
_MC_CREATIVE_MIN_PASSES_KEY   = 2

_MC_BONUS_MIN_MINUTES         = 60
```

### Formato de auditoría en `calculation_details`

La clave `"midfield_bonuses"` se añade al dict de `calculation_details`:

```json
{
  "midfield_bonuses": {
    "enabled": true,
    "position_group": "MF",
    "minutes": 72,
    "passes_completed": 68,
    "passes_accuracy": 91.0,
    "rating": 7.8,
    "tackles_won": 2,
    "interceptions": 1,
    "passes_key": 3,
    "control_midfield_bonus_earned": true,
    "two_way_midfield_bonus_earned": false,
    "creative_control_bonus_earned": true,
    "mc_bonus_total_base": 220,
    "mc_bonus_capped": true,
    "M2": 1.0,
    "Mrating": 1.0,
    "mc_bonus_final": 220.0
  }
}
```

Si `enabled = false` o `position_group != MF`, el dict es:

```json
{
  "midfield_bonuses": {
    "enabled": false
  }
}
```

---

## No-changes explícitos

- `ActionType` enum: **no se modifica**. Los bonuses derivados no son eventos atómicos.
- `BASE_POINTS_TABLE` / `BASE_POINTS_TABLE_V2`: **no se modifica**.
- `PlayerEventScore` entity: **no se modifica** (structure unchanged, `calculation_details` es JSONB flexible).
- `PlayerEventRawContextDTO`: **no se modifica** (todos los campos necesarios ya existen).
- `SFAScoringService`: **no se modifica** (los bonuses viven en el use case, no en el service).
- Ninguna migración de DB requerida.
- Ningún endpoint nuevo requerido.
- `ScoringConfig.default()` (v1): **no activa bonuses** (`enable_midfield_control_bonuses=False`).
