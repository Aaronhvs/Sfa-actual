# Plan: Midfield Control Bonuses

## Archivos a crear

- [ ] `tests/use_cases/test_midfield_control_bonuses.py` — 16 tests (ver Fase 3)

## Archivos a modificar

- [ ] `src/sfa/domain/scoring/value_objects.py` — añadir `enable_midfield_control_bonuses` a `ScoringConfig`
- [ ] `src/sfa/application/use_cases/calculate_scores_for_rules_version.py` — constantes de módulo + `_apply_midfield_bonuses` + integración en `_score_stats_event`

---

## Checklist de implementación

### Fase 1 — ScoringConfig: nuevo campo opcional

- [ ] **1.1** En `src/sfa/domain/scoring/value_objects.py`, localizar la sección
  `# ── Optional v2 fields` del dataclass `ScoringConfig` y añadir al final del bloque:

  ```python
  enable_midfield_control_bonuses: bool = False
  ```

  Posición: después de `competition_bonus_weights` (último campo actual). No requiere
  cambio en `__post_init__` (bool sin invariante adicional).

- [ ] **1.2** En `ScoringConfig.default_v2()`, añadir el kwarg antes del cierre del `return cls(...)`:

  ```python
  enable_midfield_control_bonuses=True,
  ```

  `default()` (v1) no se toca — el default del campo (`False`) ya desactiva los bonuses.

- [ ] **1.3** En `ScoringConfig.from_dict()`, dentro del bloque `return cls(...)`, añadir:

  ```python
  enable_midfield_control_bonuses=bool(d.get("enable_midfield_control_bonuses", False)),
  ```

  Ubicación: junto a los otros campos opcionales v2 que usan `.get(..., default)`.

- [ ] **1.4** En `ScoringConfig.to_dict()`, añadir al dict retornado:

  ```python
  "enable_midfield_control_bonuses": self.enable_midfield_control_bonuses,
  ```

  Ubicación: al final del dict, después de `"competition_bonus_weights"`.

---

### Fase 2 — Use Case: constantes + método privado + integración

- [ ] **2.1** En `src/sfa/application/use_cases/calculate_scores_for_rules_version.py`,
  añadir las constantes de módulo DESPUÉS de `_STATS_EVENT_TYPE = EventType.STATS.value`:

  ```python
  # ── Midfield control bonus constants ────────────────────────────────────────
  _MC_BONUS_CAP = 220

  _MC_BONUS_CONTROL = 120      # CONTROL_MIDFIELD_BONUS base pts
  _MC_BONUS_TWO_WAY = 100      # TWO_WAY_MIDFIELD_BONUS base pts
  _MC_BONUS_CREATIVE = 100     # CREATIVE_CONTROL_BONUS base pts

  _MC_BONUS_MIN_MINUTES         = 60

  _MC_CONTROL_MIN_RATING        = 7.6
  _MC_CONTROL_MIN_PASSES        = 65
  _MC_CONTROL_MIN_ACCURACY      = 90.0

  _MC_TWO_WAY_MIN_RATING        = 7.4
  _MC_TWO_WAY_MIN_PASSES        = 50
  _MC_TWO_WAY_MIN_DEFENSIVE     = 3   # tackles_won + interceptions

  _MC_CREATIVE_MIN_RATING       = 7.5
  _MC_CREATIVE_MIN_PASSES       = 50
  _MC_CREATIVE_MIN_PASSES_KEY   = 2
  ```

- [ ] **2.2** Añadir `PositionGroup` al import de `value_objects` en el use case
  (ya se importa `position_to_group`; verificar si `PositionGroup` ya está en scope —
  en `_score_stats_event` se usa via `from sfa.domain.scoring.value_objects import ...`
  dentro de la función. Moverlo al import del módulo o verificar que la importación local
  en la función ya lo incluye). El método `_apply_midfield_bonuses` necesita `PositionGroup`
  en su signature. Asegurarse de que el import de `PositionGroup` esté disponible a nivel
  de módulo (ya está en el `from sfa.domain.scoring.value_objects import ...` del bloque de
  imports del archivo — si no, añadirlo).

  Verificar que los siguientes nombres estén importados a nivel de módulo:
  `M2CompetitionStage`, `MratingFactor`, `PositionGroup` (además de los ya presentes).

- [ ] **2.3** Añadir el método privado `_apply_midfield_bonuses` a la clase
  `CalculateScoresForRulesVersionUseCase`. Colocarlo DESPUÉS de `_score_stats_event` y
  ANTES de `_score_individual_event` (o al final de la clase, lo que mantenga mejor la
  lectura). Implementación completa:

  ```python
  def _apply_midfield_bonuses(
      self,
      event: PlayerEventRawContextDTO,
      group: PositionGroup,
      m2: M2CompetitionStage,
      mrating: MratingFactor,
      config: ScoringConfig,
  ) -> tuple[float, dict]:
      """Compute and return MC derived bonuses and their audit dict.

      Returns (0.0, {"enabled": False}) when bonuses are disabled or
      the player is not MF, so callers can always unpack safely.
      """
      if not config.enable_midfield_control_bonuses:
          return 0.0, {"enabled": False}

      if group != PositionGroup.MF:
          return 0.0, {"enabled": False}

      minutes = getattr(event, "minutes", None) or 0
      if minutes < _MC_BONUS_MIN_MINUTES:
          return 0.0, {"enabled": False}

      rating = event.rating  # may be None
      passes_total = event.passes_total or 0
      passes_accuracy = event.passes_accuracy or 0.0
      passes_key = event.passes_key or 0
      tackles_won = event.tackles_won or 0
      interceptions = event.interceptions or 0

      passes_completed = int(passes_total * passes_accuracy / 100)
      defensive_actions = tackles_won + interceptions

      # Evaluate each bonus independently
      control_earned = (
          rating is not None
          and rating >= _MC_CONTROL_MIN_RATING
          and passes_completed >= _MC_CONTROL_MIN_PASSES
          and passes_accuracy >= _MC_CONTROL_MIN_ACCURACY
      )
      two_way_earned = (
          rating is not None
          and rating >= _MC_TWO_WAY_MIN_RATING
          and passes_completed >= _MC_TWO_WAY_MIN_PASSES
          and defensive_actions >= _MC_TWO_WAY_MIN_DEFENSIVE
      )
      creative_earned = (
          rating is not None
          and rating >= _MC_CREATIVE_MIN_RATING
          and passes_completed >= _MC_CREATIVE_MIN_PASSES
          and passes_key >= _MC_CREATIVE_MIN_PASSES_KEY
      )

      total_base = (
          (_MC_BONUS_CONTROL if control_earned else 0)
          + (_MC_BONUS_TWO_WAY if two_way_earned else 0)
          + (_MC_BONUS_CREATIVE if creative_earned else 0)
      )

      capped = total_base > _MC_BONUS_CAP
      mc_bonus_total_base = min(total_base, _MC_BONUS_CAP)
      mc_bonus_final = mc_bonus_total_base * m2.value * mrating.value

      audit: dict = {
          "enabled": True,
          "position_group": group.value,
          "minutes": minutes,
          "passes_completed": passes_completed,
          "passes_accuracy": passes_accuracy,
          "rating": rating,
          "tackles_won": tackles_won,
          "interceptions": interceptions,
          "passes_key": passes_key,
          "control_midfield_bonus_earned": control_earned,
          "two_way_midfield_bonus_earned": two_way_earned,
          "creative_control_bonus_earned": creative_earned,
          "mc_bonus_total_base": mc_bonus_total_base,
          "mc_bonus_capped": capped,
          "M2": round(m2.value, 3),
          "Mrating": round(mrating.value, 3),
          "mc_bonus_final": round(mc_bonus_final, 2),
      }
      return mc_bonus_final, audit
  ```

- [ ] **2.4** En `_score_stats_event`, localizar la línea donde se calcula `final`:

  ```python
  base_total *= minutes_scale
  final = round(base_total * combined, 2)
  ```

  Modificar para que:
  1. Se calculen los bonuses MC DESPUÉS de `final`.
  2. Se sume el bonus al `final` ya calculado.
  3. Se añada la clave `"midfield_bonuses"` al dict `details`.

  Código a insertar DESPUÉS de `final = round(base_total * combined, 2)`:

  ```python
  # v2: MC derived bonuses (CONTROL_MIDFIELD, TWO_WAY, CREATIVE_CONTROL)
  mc_bonus, mc_audit = self._apply_midfield_bonuses(event, group, m2, mrating, config)
  if mc_bonus > 0:
      final = round(final + mc_bonus, 2)
  ```

  Y en el dict `details`, añadir la clave al final (antes del `return`):

  ```python
  details["midfield_bonuses"] = mc_audit
  ```

  También actualizar el campo `final_points` en el dict `details` para que refleje el
  valor actualizado. Localizar la línea:
  ```python
  "final_points": final,
  ```
  Este campo en `details` se construye ANTES de calcular el bonus, por lo que deberá
  actualizarse. La solución más limpia: construir el dict `details` con `"final_points"`
  DESPUÉS de aplicar el bonus. Reestructurar el orden de construcción del dict:

  - Construir todos los campos del dict `details` excepto `"final_points"` y
    `"midfield_bonuses"`.
  - Calcular bonus y actualizar `final`.
  - Añadir `"final_points": final` y `"midfield_bonuses": mc_audit` al dict.

  Alternativamente (más simple): añadir `"final_points"` al final después de calcular
  el bonus y eliminar la entrada `"final_points"` de la posición actual. Elegir la
  forma que produzca código más limpio sin alterar las otras claves.

- [ ] **2.5** Actualizar el campo `base_points` del `PlayerEventScore` retornado. Actualmente
  se asigna `base_points=round(base_total, 2)`. Este campo representa el "base antes del
  multiplicador". El bonus no es `base_total` sino que ya lleva M2×Mrating aplicado.
  Por tanto `base_points` en el `PlayerEventScore` permanece igual (`round(base_total, 2)`).
  Solo `final_points` aumenta. Confirmar que el código no cambia `base_points`.

---

### Fase 3 — Tests (16 tests obligatorios)

Archivo a crear: `tests/use_cases/test_midfield_control_bonuses.py`

Los helpers `FakeScoringRulesVersionRepository`, `FakePlayerEventScoreRepository` y
`FakeScoringRepository` deben copiarse/importarse del test existente
`test_calculate_scores_for_rules_version.py`. Preferiblemente importarlos para no
duplicar código.

- [ ] **3.0** Añadir helper `_make_mc_stats_event(...)` que produce un
  `PlayerEventRawContextDTO` con:
  - `event_type="stats"`, `player_position="MC"`
  - `minutes=75`, `rating=7.8`, `passes_total=80`, `passes_accuracy=91.0`
  - `passes_key=3`, `tackles_won=2`, `interceptions=2`
  - `stage_factor=1.0`, todos los demás campos con valores válidos no nulos.
  - El helper acepta kwargs para sobreescribir campos individuales.

  Y helper `_make_v2_rules_version(version_id=3)` que usa `ScoringConfig.default_v2()`.

- [ ] **3.1** `test_bonus_not_applied_when_position_not_mc`
  - Evento con `player_position="DC"`, config con bonuses activados.
  - Assert: `calculation_details["midfield_bonuses"]["enabled"] == False`.
  - Assert: `final_points` igual al calculado sin bonuses (no aumenta).

- [ ] **3.2** `test_bonus_not_applied_when_flag_disabled`
  - Evento MC válido, config v2 con `enable_midfield_control_bonuses=False`.
  - Assert: `calculation_details["midfield_bonuses"]["enabled"] == False`.

- [ ] **3.3** `test_bonus_not_applied_on_legacy_config_without_field`
  - Crear `ScoringConfig` usando `ScoringConfig.default()` (v1). El campo
    `enable_midfield_control_bonuses` existe en Python con `False` por default.
  - Verificar que `from_dict(to_dict())` round-trip de una config v1 que no tenga la
    clave produce `enable_midfield_control_bonuses=False`.
  - Assert: bonuses no se aplican aunque el evento sea MC con stats altas.

- [ ] **3.4** `test_control_midfield_bonus_applied_when_all_conditions_met`
  - rating=7.8, passes_completed=70 (passes_total=80, accuracy=87.5 → int=70),
    passes_accuracy=91.0, minutes=75. Solo cumple CONTROL.
  - Assert: `control_midfield_bonus_earned=True`, `mc_bonus_total_base=120`.
  - Assert: `final_points > final_sin_bonuses` (calcular expected con M2=1.0, Mrating de v2).

- [ ] **3.5** `test_two_way_midfield_bonus_applied_when_all_conditions_met`
  - rating=7.5, passes_completed=55 (passes_total=65, accuracy=84.6 → int=55),
    passes_accuracy=85.0, tackles_won=2, interceptions=2, minutes=70.
    Solo cumple TWO_WAY (rating < 7.6 → no CONTROL, passes_accuracy < 90 → no CONTROL).
  - Assert: `two_way_midfield_bonus_earned=True`, `mc_bonus_total_base=100`.

- [ ] **3.6** `test_creative_control_bonus_applied_when_all_conditions_met`
  - rating=7.6, passes_completed=52, passes_accuracy=86.7, passes_key=3,
    tackles_won=0, interceptions=0, minutes=65.
    Solo cumple CREATIVE (interceptions+tackles=0 < 3 → no TWO_WAY; accuracy < 90 → no CONTROL).
  - Assert: `creative_control_bonus_earned=True`, `mc_bonus_total_base=100`.

- [ ] **3.7** `test_cap_applied_when_all_three_bonuses_earned`
  - rating=7.8, passes_completed=70, passes_accuracy=91.0, passes_key=3,
    tackles_won=2, interceptions=2, minutes=80. Cumple los tres.
  - Assert: `mc_bonus_capped=True`, `mc_bonus_total_base=220` (no 320 = 120+100+100).

- [ ] **3.8** `test_bonus_not_applied_when_rating_below_minimum`
  - rating=7.3 (por debajo de todos los mínimos: 7.4, 7.5, 7.6).
  - Assert: ningún bonus earned, `mc_bonus_total_base=0`, `final_points` sin bonus.

- [ ] **3.9** `test_bonus_not_applied_when_minutes_below_60`
  - minutes=45, rating=8.0, resto de stats perfectas.
  - Assert: `calculation_details["midfield_bonuses"]["enabled"] == False`.

- [ ] **3.10** `test_bonus_not_applied_when_passes_completed_below_minimum`
  - passes_total=60, passes_accuracy=80.0 → passes_completed=48 (< 50).
  - Assert: ningún bonus earned (todos requieren ≥ 50 o ≥ 65).

- [ ] **3.11** `test_control_bonus_not_applied_when_passes_accuracy_below_90`
  - rating=7.8, passes_completed=70, passes_accuracy=88.0, tackles_won=0, interceptions=0.
  - Assert: `control_midfield_bonus_earned=False`.
  - Verificar que si además tackles+interceptions < 3 y passes_key < 2, ningún bonus aplica.

- [ ] **3.12** `test_no_crash_when_duels_total_zero`
  - El campo `duels_total` (si existiera) es 0. El cálculo de bonuses no usa `duels_total`
    directamente, pero `tackles_won=0` y `interceptions=0` deben manejarse sin división
    por cero. Este test verifica que `event.tackles_won=0` y `event.interceptions=0`
    producen `defensive_actions=0` sin excepción.
  - Assert: `two_way_midfield_bonus_earned=False`, sin excepción.

- [ ] **3.13** `test_m2_and_mrating_applied_correctly_to_bonus`
  - Configurar `stage_factor=1.5` (M2=1.5) y rating=8.5 (Mrating en v2 = 1.30).
  - Evento que gana solo CREATIVE_CONTROL_BONUS (100 pts base).
  - Expected `mc_bonus_final` = 100 × 1.5 × 1.30 = 195.0.
  - Assert: `round(mc_bonus_final, 2) == 195.0`.

- [ ] **3.14** `test_m1_m3_m4_mvisit_not_applied_to_bonus`
  - Configurar evento con `is_away=True` (activaría Mvisit), `rival_team_pos=1` (activaría M1
    alto), `minute=88`, `score_diff=0` (activaría M3=2.5).
  - La fórmula del bonus usa solo M2×Mrating.
  - Calcular `mc_bonus_final` manualmente con M2=1.0, Mrating conocido.
  - Assert: `mc_bonus_final == expected` (no inflado por M1/M3/M4/Mvisit).

- [ ] **3.15** `test_calculation_details_includes_midfield_bonuses_audit`
  - Evento MC v2 que gana al menos un bonus.
  - Assert: `calculation_details` contiene clave `"midfield_bonuses"`.
  - Assert: `midfield_bonuses` contiene las claves obligatorias:
    `"enabled"`, `"passes_completed"`, `"passes_accuracy"`, `"rating"`,
    `"control_midfield_bonus_earned"`, `"two_way_midfield_bonus_earned"`,
    `"creative_control_bonus_earned"`, `"mc_bonus_total_base"`, `"mc_bonus_capped"`,
    `"M2"`, `"Mrating"`, `"mc_bonus_final"`.
  - Assert: `calculation_details["final_points"]` coincide con `score.final_points`.

- [ ] **3.16** `test_legacy_rules_version_null_not_affected`
  - Crear evento MC con stats perfectas y usar `ScoringConfig.default()` (v1).
  - `enable_midfield_control_bonuses` es `False` en v1 config.
  - Assert: `final_points` igual al calculado por la lógica v1 sin bonuses.
  - Assert: `calculation_details["midfield_bonuses"]["enabled"] == False`.
  - Esto simula el comportamiento cuando `rules_version_id=NULL` (se usaría `default()`).

---

### Fase 4 — Calidad y validación

- [ ] **4.1** Ejecutar `pytest tests/` antes de escribir código nuevo; documentar fallos
  preexistentes (si los hay).

- [ ] **4.2** Ejecutar `pytest tests/use_cases/test_midfield_control_bonuses.py -v` y
  confirmar que los 16 tests pasan.

- [ ] **4.3** Ejecutar `pytest tests/ -v --tb=short` y confirmar que los tests previos
  (`test_calculate_scores_for_rules_version.py`, etc.) siguen pasando. No se permite
  regresión.

- [ ] **4.4** Ejecutar `flake8 src/sfa/domain/scoring/value_objects.py
  src/sfa/application/use_cases/calculate_scores_for_rules_version.py
  tests/use_cases/test_midfield_control_bonuses.py` — cero errores.

- [ ] **4.5** Ejecutar `isort --check-only src/sfa/domain/scoring/value_objects.py
  src/sfa/application/use_cases/calculate_scores_for_rules_version.py
  tests/use_cases/test_midfield_control_bonuses.py` — cero errores.

- [ ] **4.6** Verificar que `ScoringConfig.default_v2().to_dict()` incluye
  `"enable_midfield_control_bonuses": true` (test manual o assert inline).

- [ ] **4.7** Verificar round-trip de `from_dict(to_dict())` preserva el campo booleano
  para configs v1 (sin la clave → `False`) y v2 (con la clave → `True`).

---

## Orden recomendado de implementación

1. Fase 1 completa (value_objects.py — bajo riesgo, cambio aditivo).
2. Fase 2.1–2.3 (constantes + método `_apply_midfield_bonuses` — sin tocar flujo existente).
3. Fase 3 parcial: escribir los 16 tests ANTES de integrar el método en el flujo. Todos
   deben fallar en este punto (TDD).
4. Fase 2.4–2.5 (integración en `_score_stats_event`).
5. Fase 3: re-ejecutar — deben pasar los 16 tests.
6. Fase 4 completa.

---

## Agent Routing Brief

**@DDD-Designer needed: NO**

Justificación:

- No se crean nuevas entidades de dominio, agregados ni invariantes complejos.
- `ScoringConfig` es un value object existente al que se añade un campo booleano opcional.
- Los bonuses son lógica de scoring derivada (condicional, calculada en tiempo de ejecución)
  que encaja en el use case existente — no requieren modelado de dominio nuevo.
- Todos los value objects necesarios (`M2CompetitionStage`, `MratingFactor`, `PositionGroup`)
  ya existen y no se modifican.
- No hay nuevas tablas, columnas, ni modelos ORM.

El implementador puede ejecutar este spec sin intervención de @DDD-Designer.
