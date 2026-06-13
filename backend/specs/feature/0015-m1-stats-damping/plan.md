# Plan: M1 Stats Damping

## Paso 0 — Diagnóstico previo (operacional, no código)

Antes de implementar, verificar en DB si `team_strengths` está poblado para `season='2024'`:

```sql
SELECT COUNT(*), MIN(strength), MAX(strength), AVG(strength)
FROM team_strengths
WHERE season = '2024';
```

- Si `COUNT > 0`: M1 ya usa `team_strength` (modo v2). El fix reduce la inflación de equipo.
- Si `COUNT = 0`: M1 cae al fallback legacy por posición. El fix aplica igual; documentar en
  el commit que `team_strengths` está vacío para 2024.

Resultado esperado del diagnóstico: **registrar si `strength_used=True` o `False` domina
en los calculation_details actuales** para saber el impacto real del fix.

---

## Archivos a modificar

- [ ] `src/sfa/domain/scoring/value_objects.py` — agregar campos `m1_stats_weight` y
  `m1_stats_clamp` a `ScoringConfig`; actualizar `default_v2()`, `from_dict()`, `to_dict()`
  y `__post_init__`
- [ ] `src/sfa/application/use_cases/calculate_scores_for_rules_version.py` — modificar
  `_score_stats_event` para bifurcar M1 entre decisivas y acumulativas; agregar constante
  `_M1_DECISIVE_STATS_ACTIONS`; actualizar `calculation_details`

## Archivos a crear

- [ ] `tests/use_cases/test_m1_stats_damping.py` — 10+ tests de la lógica de amortiguación

---

## Checklist de implementación

### 1. `ScoringConfig` — campos nuevos

- [ ] Agregar al `frozen dataclass ScoringConfig` dos campos opcionales con defaults:
  ```python
  m1_stats_weight: float = 1.0
  m1_stats_clamp: tuple[float, float] = (0.85, 1.20)
  ```
  Ubicarlos al final del bloque "Optional v2 fields", después de
  `enable_performance_based_achievement_bonus`.

- [ ] En `__post_init__`: agregar validaciones:
  ```python
  if not (0.0 <= self.m1_stats_weight <= 1.0):
      raise ValueError(f"m1_stats_weight must be in [0, 1], got {self.m1_stats_weight}")
  if self.m1_stats_clamp[0] >= self.m1_stats_clamp[1]:
      raise ValueError(f"m1_stats_clamp min must be < max, got {self.m1_stats_clamp}")
  if self.m1_stats_clamp[0] <= 0:
      raise ValueError(f"m1_stats_clamp values must be positive, got {self.m1_stats_clamp}")
  ```

- [ ] En `default_v2()`: añadir `m1_stats_weight=0.35, m1_stats_clamp=(0.85, 1.20)` en
  la llamada a `cls(...)`.

- [ ] En `from_dict()`: añadir en el `return cls(...)`:
  ```python
  m1_stats_weight=float(d.get("m1_stats_weight", 1.0)),
  m1_stats_clamp=tuple(d.get("m1_stats_clamp", [0.85, 1.20])),
  ```

- [ ] En `to_dict()`: añadir:
  ```python
  "m1_stats_weight": self.m1_stats_weight,
  "m1_stats_clamp": list(self.m1_stats_clamp),
  ```

### 2. Use case — bifurcación de M1 en `_score_stats_event`

- [ ] Añadir constante de módulo en `calculate_scores_for_rules_version.py`:
  ```python
  _M1_DECISIVE_STATS_ACTIONS: frozenset[ActionType] = frozenset({
      ActionType.PENALTY_WON,
  })
  ```

- [ ] En `_score_stats_event`, después de calcular `m1 = M1RivalDifficulty(...)`,
  calcular el M1 amortiguado para stats acumulativas:
  ```python
  m1_original = m1.value
  weight = config.m1_stats_weight
  clamp_min, clamp_max = config.m1_stats_clamp
  m1_stats_applied = max(clamp_min, min(clamp_max, 1.0 + (m1_original - 1.0) * weight))
  ```

- [ ] Refactorizar el loop `for action, count in raw_stats.items()` para acumular
  por separado `decisive_base` y `accumulative_base`:
  ```python
  decisive_base = 0.0
  accumulative_base = 0.0
  for action, count in raw_stats.items():
      base_per_unit = config.base_points[group][action]
      if base_per_unit == 0 or count == 0:
          continue
      if action in dr_map:
          pts = DiminishingReturnsConfig.apply(count, float(base_per_unit), dr_map[action])
          dr_applied[action.value] = {...}
      else:
          pts = float(base_per_unit) * count
      if action in _M1_DECISIVE_STATS_ACTIONS:
          decisive_base += pts
      else:
          accumulative_base += pts
  ```

- [ ] Combinar con multiplicadores:
  ```python
  # M2, Mrating, minutes_scale se aplican igual a ambos
  # M1 se bifurca
  base_total = (
      decisive_base * m1_original * m2.value * mrating.value
      + accumulative_base * m1_stats_applied * m2.value * mrating.value
  ) * minutes_scale
  final = round(base_total, 2)
  ```

  **Nota:** `combined_before_clamp` y `combined_after_clamp` en el DTO heredado
  (`PlayerEventScore`) no tienen semántica clara para stats bifurcadas. Mantener
  `combined_before_clamp = m1_original * m2.value * mrating.value` (M1 sin suavizar)
  y `combined_after_clamp = m1_stats_applied * m2.value * mrating.value` (M1 suavizado)
  para coherencia con el campo legacy. Esto se documenta en `calculation_details`.

- [ ] Actualizar `calculation_details` añadiendo los 4 campos nuevos:
  ```python
  details = {
      ...campos existentes...,
      "m1_source": "team_strength" if strength_used else "legacy_position",
      "m1_original": round(m1_original, 3),
      "m1_stats_weight": weight,
      "m1_stats_applied": round(m1_stats_applied, 3),
  }
  ```

- [ ] Confirmar en `_apply_midfield_bonuses` que NO recibe M1 de ningún tipo — ya es así
  (`mc_bonus_final = mc_bonus_total_base * m2.value * mrating.value * competition_weight`).
  Agregar un comentario explícito: `# Intentional: midfield bonuses do not use M1`.

### 3. Tests

- [ ] Crear `tests/use_cases/test_m1_stats_damping.py` con los siguientes tests:

  **Tests de `ScoringConfig`:**
  - [ ] `test_default_v1_has_no_damping` — `ScoringConfig.default()` tiene
    `m1_stats_weight=1.0`, `m1_stats_clamp=(0.85, 1.20)` (defaults sin efecto).
  - [ ] `test_default_v2_has_damping` — `ScoringConfig.default_v2()` tiene
    `m1_stats_weight=0.35`.
  - [ ] `test_from_dict_roundtrip_preserves_new_fields` — serializar con `to_dict()` y
    deserializar con `from_dict()` produce los mismos valores.
  - [ ] `test_from_dict_old_config_uses_defaults` — dict sin `m1_stats_weight` ni
    `m1_stats_clamp` produce `weight=1.0` y `clamp=(0.85, 1.20)`.
  - [ ] `test_post_init_rejects_invalid_weight` — `m1_stats_weight=1.5` lanza `ValueError`.
  - [ ] `test_post_init_rejects_invalid_clamp` — `m1_stats_clamp=(1.0, 0.5)` lanza
    `ValueError`.

  **Tests de `_score_stats_event` (via use case con Fake):**
  - [ ] `test_high_m1_team_stats_are_damped` — player en equipo malo (M1=1.18),
    stats acumulativas: `m1_stats_applied` ≈ 1.063, `final_points` significativamente
    menor que si M1=1.18 completo.
  - [ ] `test_low_m1_team_stats_are_damped` — player en equipo fuerte (M1=0.70),
    stats acumulativas: `m1_stats_applied` ≈ 0.895, `final_points` mayor que si M1=0.70
    completo.
  - [ ] `test_penalty_won_uses_full_m1` — cuando `penalty_won=1`, su contribución al
    `base_total` usa `m1_original`, no `m1_stats_applied`. Verificar a través de
    `calculation_details["m1_original"]` vs `m1_stats_applied`.
  - [ ] `test_m1_weight_zero_flattens_stats_m1` — `m1_stats_weight=0.0` produce
    `m1_stats_applied=1.0` para cualquier M1 (acumulativas completamente neutralizadas).
  - [ ] `test_m1_weight_one_preserves_full_m1` — `m1_stats_weight=1.0` produce
    `m1_stats_applied == m1_original` (clampeado por `m1_stats_clamp`).
  - [ ] `test_calculation_details_has_new_fields` — `calculation_details` contiene
    `m1_source`, `m1_original`, `m1_stats_weight`, `m1_stats_applied`.
  - [ ] `test_m1_source_team_strength_when_strengths_available` — cuando
    `player_team_strength` y `rival_team_strength` están en el evento, `m1_source` es
    `"team_strength"`.
  - [ ] `test_m1_source_legacy_when_no_strengths` — cuando strengths son None, `m1_source`
    es `"legacy_position"`.
  - [ ] `test_midfield_bonus_not_affected_by_m1` — mc_bonus_final es idéntico con
    M1=1.18 y M1=0.70 cuando todos los demás parámetros son iguales.

- [ ] Verificar `pytest tests/` pasa con coverage ≥80%
- [ ] Verificar `flake8 src/ tests/` sin errores
- [ ] Verificar `isort --check-only src/ tests/` sin errores

---

## Agent Routing Brief

**DDD Designer needed:** no

Este spec modifica un value object existente (`ScoringConfig`) con dos campos adicionales
opcionales y ajusta la lógica de un use case existente (`_score_stats_event`). No se crean
nuevas entidades de dominio, nuevos agregados, ni nuevos puertos. El cambio es contenido
dentro de los límites del subdomain de scoring ya establecido.

---

## Verificación

1. **Diagnóstico previo:** ejecutar la query SQL del Paso 0 y registrar si `team_strengths`
   está poblado para 2024.

2. **Recálculo:** tras actualizar `default_v2()` en el codebase, disparar recálculo con:
   ```
   POST /api/v1/scoring/calculate
   { "rules_version_id": <v2_id>, "season": "2024", "force_recalculate": true }
   ```

3. **Verificar Bruno Fernandes:** consultar ranking global. Debe bajar de #4 a una posición
   más representativa de su temporada real.

4. **Comparar M1 antes/después en `calculation_details`:**
   - `m1_original`: ~1.182 (Man United)
   - `m1_stats_applied`: ~1.064 (con weight=0.35)
   - Los goles/asistencias de Fernandes mantienen M1=1.182 (individual events no cambian)

5. **Verificar Arsenal no sufre injusticia inversa:** Saka/Odegaard deben mantener o mejorar
   posición (M1_stats de ~0.898 en vez de 0.708 para stats acumulativas).

6. **Smoke test de backward compat:**
   - Crear un `ScoringConfig` desde un dict v1 (sin `m1_stats_weight`) → no debe lanzar error.
   - Los scores calculados con config v1 deben ser idénticos a antes (weight=1.0 = sin cambio).
