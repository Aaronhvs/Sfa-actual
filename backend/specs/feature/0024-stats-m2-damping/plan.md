# Plan: Stats M2 Damping — Reduce stage_factor inflation on STATS events

## Archivos a crear

Ninguno. Solo se modifican archivos existentes.

## Archivos a modificar

- [ ] `src/sfa/domain/scoring/value_objects.py` — añadir campo `stats_m2_attenuation` a `ScoringConfig`
- [ ] `src/sfa/application/use_cases/calculate_scores_for_rules_version.py` — aplicar atenuación en `_score_stats_event()`
- [ ] `tests/use_cases/test_calculate_scores_for_rules_version.py` — añadir tests de la nueva lógica

## Checklist de implementación

### Paso 1 — Extender `ScoringConfig` con `stats_m2_attenuation`

Archivo: `src/sfa/domain/scoring/value_objects.py`

- [ ] Añadir campo opcional al dataclass `ScoringConfig` (sección "Optional v2 fields"):
  ```python
  stats_m2_attenuation: float = 1.0
  ```
  Ubicar después de `m1_stats_clamp` para mantener coherencia temática.

- [ ] Añadir validación en `__post_init__`:
  ```python
  if not (0.0 < self.stats_m2_attenuation <= 1.0):
      raise ValueError(
          f"stats_m2_attenuation must be in (0, 1], got {self.stats_m2_attenuation}"
      )
  ```

- [ ] Actualizar `default()` (v1): no añadir el campo — el default `1.0` aplica automáticamente.

- [ ] Actualizar `default_v2()`: añadir `stats_m2_attenuation=0.5` en el bloque de parámetros opcionales de la llamada a `cls(...)`.

- [ ] Actualizar `from_dict()`: añadir lectura con default:
  ```python
  stats_m2_attenuation=float(d.get("stats_m2_attenuation", 1.0)),
  ```
  Ubicar junto a los demás campos opcionales v2.

- [ ] Actualizar `to_dict()`: añadir serialización:
  ```python
  "stats_m2_attenuation": self.stats_m2_attenuation,
  ```

### Paso 2 — Aplicar atenuación en `_score_stats_event()`

Archivo: `src/sfa/application/use_cases/calculate_scores_for_rules_version.py`

- [ ] Al inicio de `_score_stats_event()`, después de obtener `config = service._config`, calcular el `stage_factor` efectivo:
  ```python
  attenuation = config.stats_m2_attenuation  # 1.0 = no change (v1), 0.5 = halved bonus (v2)
  effective_sf = 1.0 + (event.stage_factor - 1.0) * attenuation
  m2 = M2CompetitionStage(effective_sf)
  ```
  Reemplazar la línea existente `m2 = M2CompetitionStage(event.stage_factor)`.

- [ ] Verificar que `m2` (ya atenuado) se propaga correctamente a:
  - `combined_decisive` — ya usa `m2.value`
  - `combined_accum` — ya usa `m2.value`
  - `_apply_midfield_bonuses(event, group, m2, mrating, config, competition_weight)` — ya recibe `m2` por parámetro

  No se necesita ningún otro cambio en estos cálculos; todos usan `m2` como variable local.

- [ ] Enriquecer `calculation_details` con audit de atenuación. En el dict `details`, añadir las claves:
  ```python
  "stats_m2_attenuation": attenuation,
  "stage_factor_original": event.stage_factor,
  "stage_factor_effective": round(effective_sf, 4),
  ```
  Añadir junto a la clave `"M2"` existente (que ya almacena `round(m2.value, 3)`).

  El campo `"M2"` en `details` ya mostrará el valor efectivo (atenuado), que es el comportamiento correcto. Las claves nuevas permiten auditar la reducción aplicada.

- [ ] Actualizar también el campo `m2` del `PlayerEventScore` retornado — ya usa `round(m2.value, 3)` que será el valor efectivo. Sin cambio de código adicional.

### Paso 3 — Actualizar la rules_version activa en DB

Este paso es operacional (no código), pero se documenta aquí para que Chat 2 lo ejecute al final.

- [ ] Ejecutar SQL para actualizar `config_json` de la version activa:
  ```sql
  UPDATE scoring_rules_versions
  SET config_json = config_json || '{"stats_m2_attenuation": 0.5}'::jsonb
  WHERE is_active = true;
  ```
  Verificar con `SELECT name, config_json->>'stats_m2_attenuation' FROM scoring_rules_versions WHERE is_active = true;`

### Paso 4 — Tests

Archivo: `tests/use_cases/test_calculate_scores_for_rules_version.py`

- [ ] Verificar qué tests ya existen en este archivo antes de añadir nuevos (ejecutar `pytest tests/` primero).

- [ ] Implementar los 7 tests obligatorios (todos con `@pytest.mark.anyio`):

  **Tests de `ScoringConfig`** (pueden ser síncronos, no necesitan Fake):

  1. `test_default_v2_config_has_attenuation_0_5`
     — `ScoringConfig.default_v2().stats_m2_attenuation == 0.5`

  2. `test_default_v1_config_has_attenuation_1_0`
     — `ScoringConfig.default().stats_m2_attenuation == 1.0`

  3. `test_from_dict_backward_compat_missing_key_defaults_1_0`
     — construir un dict de config v2 válido SIN la clave `stats_m2_attenuation`, llamar a `ScoringConfig.from_dict(d)`, verificar que el campo vale `1.0`

  4. `test_scoring_config_validates_attenuation_out_of_range`
     — construir `ScoringConfig.default_v2()` con `stats_m2_attenuation=0.0` levanta `ValueError`
     — construir con `stats_m2_attenuation=1.5` levanta `ValueError`

  **Tests de `_score_stats_event()` via use case** (async, usan Fakes):

  El Fake de `PlayerEventScoreRepositoryPort` y `ScoringRulesVersionRepositoryPort` ya debe existir o se crea para estos tests. Ver patrón en otros tests del directorio.

  5. `test_stats_m2_attenuation_0_5_reduces_effective_m2`
     — Crear evento STATS con `stage_factor=2.0`, config con `stats_m2_attenuation=0.5`
     — Llamar `_score_stats_event()` directamente (método interno del use case)
     — Verificar en `calculation_details`: `stage_factor_effective == 1.5`, `M2 == 1.5`

  6. `test_stats_m2_attenuation_1_0_preserves_full_m2`
     — Mismo evento con `stats_m2_attenuation=1.0`
     — Verificar `stage_factor_effective == 2.0`, `M2 == 2.0`

  7. `test_individual_events_not_affected_by_attenuation`
     — Crear evento de GOAL con `stage_factor=2.0`, config con `stats_m2_attenuation=0.5`
     — Llamar `_score_individual_event()` directamente
     — Verificar `M2 == 2.0` en `calculation_details` (atenuación no aplica)

  8. `test_calculation_details_include_attenuation_audit`
     — Evento STATS, `stats_m2_attenuation=0.5`, `stage_factor=2.0`
     — Verificar que `calculation_details` contiene las tres claves nuevas:
       `stats_m2_attenuation`, `stage_factor_original`, `stage_factor_effective`

- [ ] Verificar `pytest tests/` pasa con coverage ≥80%
- [ ] Verificar `flake8 src/ tests/` sin errores
- [ ] Verificar `isort --check-only src/ tests/` sin errores

### Paso 5 — Recálculo completo (operacional)

- [ ] Reiniciar Celery worker si está corriendo.
- [ ] Disparar recálculo `force_recalculate=True` para temporada `2024` con la rules_version activa.
- [ ] Disparar recálculo `force_recalculate=True` para temporada `2025` con la rules_version activa.
- [ ] Verificar que Elliot Anderson (caso real) ya no supera 3411 pts de STATS puro en el partido EL semi.

## Agent Routing Brief

**DDD Designer needed:** no

Este spec no requiere nuevas entidades de dominio. `ScoringConfig` es un dataclass de configuración ya existente — se extiende con un campo `float` nuevo. La lógica de cálculo vive completamente en `_score_stats_event()` del use case existente. No hay nuevas entidades, agregados, value objects de dominio ni invariantes de negocio que requieran modelado DDD.

## Verificación

1. **Verificar el campo en config:**
   ```python
   from sfa.domain.scoring.value_objects import ScoringConfig
   cfg = ScoringConfig.default_v2()
   assert cfg.stats_m2_attenuation == 0.5
   ```

2. **Verificar la fórmula en un cálculo real:**
   Consultar `player_event_scores` de Elliot Anderson tras el recálculo:
   ```sql
   SELECT calculation_details->>'M2' AS m2_used,
          calculation_details->>'stage_factor_original' AS sf_original,
          calculation_details->>'stage_factor_effective' AS sf_effective,
          final_points
   FROM player_event_scores
   WHERE player_id = <elliot_anderson_id>
     AND action_type = 'stats'
   ORDER BY final_points DESC
   LIMIT 5;
   ```
   Esperado: `sf_effective = 1.5`, `m2_used = 1.5`, `final_points` significativamente menor que 3411.

3. **Verificar backward-compat v1:**
   ```python
   cfg_v1 = ScoringConfig.default()
   assert cfg_v1.stats_m2_attenuation == 1.0
   ```

4. **Verificar serialización round-trip:**
   ```python
   cfg = ScoringConfig.default_v2()
   d = cfg.to_dict()
   assert d["stats_m2_attenuation"] == 0.5
   cfg2 = ScoringConfig.from_dict(d)
   assert cfg2.stats_m2_attenuation == 0.5
   ```

5. **Verificar que goles no cambian:**
   Buscar un evento GOAL del mismo partido en `player_event_scores`. El campo `M2` debe seguir siendo `2.0`.
