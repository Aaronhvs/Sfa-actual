# Plan: Scoring Balance v2

## Archivos a modificar

- `src/sfa/domain/scoring/services.py`
- `src/sfa/domain/scoring/value_objects.py`
- `src/sfa/domain/scoring_ports.py`
- `src/sfa/application/use_cases/calculate_scores_for_rules_version.py`
- `src/sfa/application/use_cases/calculate_achievement_bonuses.py`
- `src/sfa/application/use_cases/register_competition_achievement.py`
- `src/sfa/infrastructure/repositories/player_event_score_repository.py`
- `src/sfa/infrastructure/repositories/competition_achievement_repository.py`

## Archivos a crear

- `tests/use_cases/test_scoring_balance_v2.py`

---

## Checklist de implementacion

### Fase 1 — BASE_POINTS_TABLE_V2 (services.py)

- [ ] **1.1** En `src/sfa/domain/scoring/services.py`, en `BASE_POINTS_TABLE_V2[PositionGroup.MF]`,
  cambiar los siguientes valores (5 cambios, nada mas):
  ```python
  ActionType.XA_NO_ASSIST: 85,      # era 100
  ActionType.FOULS_DRAWN: 25,       # era 35
  ActionType.DUELS_WON: 12,         # era 15
  ActionType.TACKLES: 70,           # era 75
  ActionType.INTERCEPTIONS: 95,     # era 100
  ```
  Los otros 14 ActionType de MF no cambian.

---

### Fase 2 — ScoringConfig: nuevos defaults y nuevo flag (value_objects.py)

- [ ] **2.1** En `src/sfa/domain/scoring/value_objects.py`, reemplazar el dict completo
  `_DEFAULT_ACHIEVEMENT_PHASE_BONUSES` con:
  ```python
  _DEFAULT_ACHIEVEMENT_PHASE_BONUSES: dict[str, dict[str, int]] = {
      "champions_league": {
          "qualify_ko": 1000, "round_of_16": 1500, "quarter_final": 2200,
          "semi_final": 3000, "winner": 5000,
      },
      "europa_league": {
          "qualify_ko": 700, "round_of_16": 1000, "quarter_final": 1500,
          "semi_final": 2000, "winner": 3500,
      },
      "conference_league": {
          "qualify_ko": 500, "round_of_16": 700, "quarter_final": 1000,
          "semi_final": 1400, "winner": 2500,
      },
      "domestic_league": {
          "champion": 7000, "runner_up": 2500, "top_4": 1000,
      },
      "domestic_cup_major": {
          "semi_final": 800, "runner_up": 1200, "winner": 3000,
      },
      "domestic_cup_minor": {
          "runner_up": 300, "winner": 1000,
      },
  }
  ```
  Notas: se elimina la clave `"runner_up"` de los tres europeos. Se elimina `"quarter_final"`
  de `domestic_cup_major`. Se añade la clave `"domestic_league"` nueva.

- [ ] **2.2** En la seccion `# ── Optional v2 fields` del dataclass `ScoringConfig`, anadir
  al final del bloque (despues de `midfield_control_bonus_cap_per_match`):
  ```python
  enable_performance_based_achievement_bonus: bool = False
  ```

- [ ] **2.3** En `ScoringConfig.default_v2()`, dentro del `return cls(...)`, cambiar:
  ```python
  midfield_control_bonus_cap_per_match=180,          # era 220
  enable_performance_based_achievement_bonus=True,   # nuevo
  ```

- [ ] **2.4** En `ScoringConfig.from_dict()`, dentro del `return cls(...)`, anadir:
  ```python
  midfield_control_bonus_cap_per_match=int(d.get("midfield_control_bonus_cap_per_match", 180)),
  enable_performance_based_achievement_bonus=bool(
      d.get("enable_performance_based_achievement_bonus", False)
  ),
  ```
  IMPORTANTE: el default del fallback de `midfield_control_bonus_cap_per_match` cambia de
  220 a 180. Las configs v1 ya guardadas en DB no tienen esta clave, por lo que usaran 180
  — esto es correcto porque v1 no activa los bonuses (`enable_midfield_control_bonuses=False`),
  por lo que el cap nunca se usa.

- [ ] **2.5** En `ScoringConfig.to_dict()`, anadir al final del dict:
  ```python
  "enable_performance_based_achievement_bonus": self.enable_performance_based_achievement_bonus,
  ```

---

### Fase 3 — Ports: nuevos metodos (scoring_ports.py)

- [ ] **3.1** En `src/sfa/domain/scoring_ports.py`, en el Protocol
  `PlayerEventScoreRepositoryPort`, anadir metodo al final del bloque:
  ```python
  async def get_competition_name_map(self) -> dict[int, str]: ...
  ```

- [ ] **3.2** En el Protocol `CompetitionAchievementRepositoryPort`, anadir dos metodos al
  final del bloque:
  ```python
  async def get_player_rank_in_team(
      self,
      player_id: int,
      team_id: int,
      competition_id: int,
      season: str,
      rules_version_id: int,
  ) -> int: ...

  async def get_player_avg_rating(
      self,
      player_id: int,
      competition_id: int,
      season: str,
  ) -> float | None: ...
  ```

---

### Fase 4 — Repositorios: implementar nuevos metodos

- [ ] **4.1** En `src/sfa/infrastructure/repositories/player_event_score_repository.py`,
  anadir el metodo `get_competition_name_map`:
  ```python
  async def get_competition_name_map(self) -> dict[int, str]:
      from sfa.infrastructure.models.competitions.models import Competition
      stmt = select(Competition.id, Competition.name)
      result = await self._session.execute(stmt)
      return {row.id: row.name for row in result.all()}
  ```
  Verificar que `Competition` no este ya importado en el archivo — si no, importarlo localmente
  dentro del metodo para evitar circular imports.

- [ ] **4.2** En `src/sfa/infrastructure/repositories/competition_achievement_repository.py`,
  anadir el metodo `get_player_rank_in_team`:
  ```python
  async def get_player_rank_in_team(
      self,
      player_id: int,
      team_id: int,
      competition_id: int,
      season: str,
      rules_version_id: int,
  ) -> int:
      from sfa.infrastructure.models.players.models import Player as PlayerModel
      ranked = (
          select(
              SFASeasonScore.player_id,
              func.rank().over(
                  order_by=SFASeasonScore.total_pts.desc()
              ).label("rn"),
          )
          .join(PlayerModel, SFASeasonScore.player_id == PlayerModel.id)
          .where(
              PlayerModel.team_id == team_id,
              SFASeasonScore.competition_id == competition_id,
              SFASeasonScore.season == season,
              SFASeasonScore.rules_version_id == rules_version_id,
          )
          .subquery()
      )
      stmt = select(ranked.c.rn).where(ranked.c.player_id == player_id)
      result = await self._session.execute(stmt)
      row = result.scalar_one_or_none()
      return int(row) if row is not None else 12   # default fuera del top 11 si no hay score
  ```

- [ ] **4.3** En el mismo archivo, anadir el metodo `get_player_avg_rating`:
  ```python
  async def get_player_avg_rating(
      self,
      player_id: int,
      competition_id: int,
      season: str,
  ) -> float | None:
      stmt = (
          select(func.avg(PlayerStats.rating))
          .join(Fixture, PlayerStats.fixture_id == Fixture.id)
          .where(
              PlayerStats.player_id == player_id,
              Fixture.competition_id == competition_id,
              Fixture.season == season,
              PlayerStats.rating.is_not(None),
          )
      )
      result = await self._session.execute(stmt)
      val = result.scalar_one_or_none()
      return float(val) if val is not None else None
  ```
  Verificar que `PlayerStats` y `Fixture` ya estan importados en el archivo (si estan en
  los imports existentes, no añadir duplicados).

---

### Fase 5 — Use case de scoring: competition_weight en midfield bonuses

- [ ] **5.1** En `src/sfa/application/use_cases/calculate_scores_for_rules_version.py`,
  actualizar las constantes de modulo:
  ```python
  # Valores actualizados spec 0014
  _MC_BONUS_CONTROL = 140          # era 120
  _MC_BONUS_TWO_WAY = 90           # era 100
  _MC_BONUS_CREATIVE = 70          # era 100
  _MC_CREATIVE_MIN_RATING = 7.7    # era 7.5
  _MC_CREATIVE_MIN_PASSES = 55     # era 50
  _MC_CREATIVE_MIN_PASSES_ACCURACY = 85.0   # nueva constante
  ```
  Mantener las otras constantes sin cambio (`_MC_CONTROL_MIN_RATING=7.6`,
  `_MC_CONTROL_MIN_PASSES=65`, `_MC_CONTROL_MIN_ACCURACY=90.0`,
  `_MC_TWO_WAY_MIN_RATING=7.4`, `_MC_TWO_WAY_MIN_PASSES=50`,
  `_MC_TWO_WAY_MIN_DEFENSIVE=3`, `_MC_BONUS_MIN_MINUTES=60`).

  Eliminar la constante `_MC_BONUS_CAP = 220` del modulo — el cap se lee siempre
  de `config.midfield_control_bonus_cap_per_match`.

- [ ] **5.2** En el metodo `execute()`, ANTES del loop `for event in events:`, anadir:
  ```python
  # Preload competition name map for midfield bonus competition_weight lookup (spec 0014)
  competition_name_map: dict[int, str] = {}
  if rules_version.config.enable_midfield_control_bonuses:
      competition_name_map = await self._event_score_repo.get_competition_name_map()
  ```

- [ ] **5.3** En el metodo `_score_event`, pasar `competition_name_map` a
  `_score_stats_event`. Actualizar la llamada:
  ```python
  return self._score_stats_event(
      event, service, group, position, rules_version_id, competition_name_map
  )
  ```
  Actualizar la firma del metodo `_score_event` para recibir y repasar el parametro:
  ```python
  def _score_event(
      self,
      event: PlayerEventRawContextDTO,
      service: SFAScoringService,
      rules_version_id: int,
      competition_name_map: dict[int, str],
  ) -> PlayerEventScore | None:
  ```
  Actualizar la llamada en `execute()`:
  ```python
  score = self._score_event(event, service, rules_version_id, competition_name_map)
  ```

- [ ] **5.4** En `_score_stats_event`, actualizar la firma para recibir
  `competition_name_map: dict[int, str]`. Anadir antes de la llamada a
  `_apply_midfield_bonuses`:
  ```python
  comp_name = competition_name_map.get(event.competition_id, "")
  competition_weight = config.competition_bonus_weights.get(comp_name, 1.0)
  mc_bonus, mc_audit = self._apply_midfield_bonuses(
      event, group, m2, mrating, config, competition_weight
  )
  ```
  Actualizar la llamada existente eliminando la version sin `competition_weight`.

- [ ] **5.5** En `_apply_midfield_bonuses`:
  - Anadir parametro `competition_weight: float` a la firma (antes del `->`)
  - Actualizar la formula: `mc_bonus_final = mc_bonus_total_base * m2.value * mrating.value * competition_weight`
  - Anadir `"competition_weight": competition_weight` al dict `audit`
  - Actualizar la condicion `creative_earned`:
    ```python
    creative_earned = (
        rating is not None
        and rating >= _MC_CREATIVE_MIN_RATING
        and passes_completed >= _MC_CREATIVE_MIN_PASSES
        and passes_accuracy >= _MC_CREATIVE_MIN_PASSES_ACCURACY
        and passes_key >= _MC_CREATIVE_MIN_PASSES_KEY
    )
    ```
  - Cambiar la linea `cap = config.midfield_control_bonus_cap_per_match` — ya existe, no
    cambia. Confirmar que `_MC_BONUS_CAP` ya no se referencia en el metodo (fue eliminado
    en 5.1).

---

### Fase 6 — Fix bug competition_weight en register_competition_achievement.py

- [ ] **6.1** En `src/sfa/application/use_cases/register_competition_achievement.py`,
  actualizar la firma de `execute()`:
  ```python
  async def execute(
      self,
      competition_id: int,
      team_id: int,
      season: str,
      phase: str,
      rules_version_id: int,
      competition_name: str = "",   # nuevo parametro con default retrocompatible
  ) -> RegisterAchievementResult:
  ```

- [ ] **6.2** En el cuerpo de `execute()`, reemplazar la linea 69:
  ```python
  # ANTES (bug):
  weight = config.competition_bonus_weights.get(str(competition_id), 1.0)
  # DESPUES (fix):
  weight = config.competition_bonus_weights.get(competition_name, 1.0)
  ```

- [ ] **6.3** Verificar que el router/endpoint que llama a este use case ya pase el nombre
  de la competicion. Buscar en `src/sfa/api/v1/` el router que llama a
  `RegisterCompetitionAchievementUseCase.execute()`. Si el router usa `competition_id` pero
  no `competition_name`, debe resolverse el nombre (via `CompetitionRepository.get_by_id`)
  antes de llamar al use case. Si el router ya recibe el nombre como parametro de la request,
  usarlo directamente.

---

### Fase 7 — Use case de achievement bonuses: performance_factor

- [ ] **7.1** En `src/sfa/application/use_cases/calculate_achievement_bonuses.py`, anadir
  dos funciones helpers de modulo (fuera de la clase):

  ```python
  def _compute_rank_factor(rank_in_team: int, participation_ratio: float) -> float:
      """Calcula rank_factor basado en posicion en el equipo y participation_ratio."""
      if participation_ratio < 0.20:
          return 0.50
      if rank_in_team <= 3:
          return 1.20
      if rank_in_team <= 7:
          return 1.10
      if rank_in_team <= 11:
          return 1.00
      return 0.85


  def _compute_rating_factor(avg_rating: float | None) -> float:
      """Calcula rating_factor basado en avg_rating de la competicion."""
      if avg_rating is None:
          return 1.00
      if avg_rating >= 8.0:
          return 1.20
      if avg_rating >= 7.5:
          return 1.10
      if avg_rating >= 7.0:
          return 1.00
      if avg_rating >= 6.5:
          return 0.90
      return 0.75
  ```

- [ ] **7.2** En el loop del metodo `execute()`, dentro del bloque `for player_id in
  player_ids:`, reemplazar el calculo de `final_bonus`:

  ```python
  # Formula base (retrocompatible)
  participation_ratio = min(1.0, player_minutes / team_total_minutes)

  if config.enable_performance_based_achievement_bonus:
      rank_in_team = await self._achievement_repo.get_player_rank_in_team(
          player_id, achievement.team_id,
          competition_id, season, rules_version_id,
      )
      avg_rating = await self._achievement_repo.get_player_avg_rating(
          player_id, competition_id, season
      )
      rank_factor = _compute_rank_factor(rank_in_team, participation_ratio)
      rating_factor = _compute_rating_factor(avg_rating)
      performance_factor = max(0.50, min(1.35, rank_factor * rating_factor))
      final_bonus = round(
          achievement.bonus_points * achievement.weight
          * participation_ratio * performance_factor, 2
      )
      details = {
          "phase": achievement.phase,
          "bonus_points": achievement.bonus_points,
          "competition_weight": achievement.weight,
          "player_minutes": player_minutes,
          "team_total_minutes": team_total_minutes,
          "participation_ratio": round(participation_ratio, 4),
          "rank_in_team": rank_in_team,
          "rank_factor": rank_factor,
          "avg_rating": avg_rating,
          "rating_factor": rating_factor,
          "performance_factor": round(performance_factor, 4),
          "final_bonus": final_bonus,
      }
  else:
      final_bonus = round(
          achievement.bonus_points * achievement.weight * participation_ratio, 2
      )
      details = {
          "phase": achievement.phase,
          "bonus_points": achievement.bonus_points,
          "weight": achievement.weight,
          "player_minutes": player_minutes,
          "team_total_minutes": team_total_minutes,
          "participation_ratio": round(participation_ratio, 4),
          "final_bonus": final_bonus,
      }
  ```

  El bloque `else` es identico al codigo actual con el renombramiento de "weight" por
  "weight" — no hay cambio funcional en ese branch.

- [ ] **7.3** El segundo loop (reconstruccion de `update_season_score_bonus`) tambien debe
  recalcular correctamente con performance_factor. Refactorizar la logica de calculo de
  `total_bonus` para evitar duplicacion: extraer un metodo privado
  `_compute_player_achievement_bonus(player_id, ach, team_total, competition_id, season,
  rules_version_id, config) -> float` que encapsula toda la logica de calculo (participation
  + performance_factor si aplica). Usar este metodo en ambos loops.

  La firma del metodo privado:
  ```python
  async def _compute_player_bonus(
      self,
      player_id: int,
      player_minutes: int,
      achievement: "CompetitionAchievement",
      team_total_minutes: int,
      competition_id: int,
      season: str,
      rules_version_id: int,
      config: "ScoringConfig",
  ) -> float:
      ...
  ```

- [ ] **7.4** Actualizar los imports en `calculate_achievement_bonuses.py`:
  Anadir al import de `scoring_ports`:
  ```python
  from sfa.domain.scoring.value_objects import ScoringConfig
  ```
  (Si ya esta importado a traves de otro path, no duplicar.)

---

### Fase 8 — Tests

Archivo: `tests/use_cases/test_scoring_balance_v2.py`

Los Fakes deben implementar completamente los Protocols. Importar los Fakes existentes de
`test_calculate_scores_for_rules_version.py` y `test_register_competition_achievement.py`
si estan disponibles, o reimplementarlos.

**Fake nuevos necesarios:**
- `FakePlayerEventScoreRepository` debe implementar `get_competition_name_map`
- `FakeCompetitionAchievementRepository` debe implementar `get_player_rank_in_team` y
  `get_player_avg_rating`

- [ ] **8.1** `test_mc_bonus_control_new_value_140`
  - Config v2 con bonuses activados, MC event cumple solo CONTROL.
  - Assert: `mc_bonus_total_base == 140` (no 120).

- [ ] **8.2** `test_mc_bonus_two_way_new_value_90`
  - Config v2, MC event cumple solo TWO_WAY.
  - Assert: `mc_bonus_total_base == 90` (no 100).

- [ ] **8.3** `test_mc_bonus_creative_new_value_70`
  - Config v2, MC event cumple solo CREATIVE (rating >= 7.7, passes >= 55, accuracy >= 85, key >= 2).
  - Assert: `mc_bonus_total_base == 70` (no 100).

- [ ] **8.4** `test_mc_creative_not_applied_when_accuracy_below_85`
  - MC event: rating=7.8, passes=57, accuracy=83.0 (< 85), passes_key=3.
  - Assert: `creative_control_bonus_earned=False`.

- [ ] **8.5** `test_mc_creative_not_applied_when_rating_below_7_7`
  - MC event: rating=7.6 (< 7.7), passes=60, accuracy=88, key=3.
  - Assert: `creative_control_bonus_earned=False`.

- [ ] **8.6** `test_mc_cap_new_value_180`
  - Config v2 (midfield_control_bonus_cap_per_match=180), MC event cumple los tres bonuses
    (140+90+70=300 > 180).
  - Assert: `mc_bonus_capped=True`, `mc_bonus_total_base=180`.

- [ ] **8.7** `test_mc_bonus_includes_competition_weight`
  - competition_name_map = {1: "Champions League"}, competition_weight para CL = 1.0.
  - MC event cumple CREATIVE, M2=1.0, Mrating=1.0.
  - Assert: `mc_bonus_final = 70 * 1.0 * 1.0 * 1.0 = 70.0`.
  - competition_name_map = {1: "Premier League"}, competition_weight = 0.95.
  - Assert: `mc_bonus_final = 70 * 1.0 * 1.0 * 0.95 = 66.5`.

- [ ] **8.8** `test_mc_bonus_defaults_weight_1_when_competition_unknown`
  - competition_name_map = {} (vacio), event.competition_id = 99.
  - Assert: `competition_weight` en audit es 1.0 (default).
  - Assert: no lanza excepcion.

- [ ] **8.9** `test_base_points_mf_xa_no_assist_85`
  - `ScoringConfig.default_v2().base_points[PositionGroup.MF][ActionType.XA_NO_ASSIST] == 85`.

- [ ] **8.10** `test_base_points_mf_fouls_drawn_25`
  - `ScoringConfig.default_v2().base_points[PositionGroup.MF][ActionType.FOULS_DRAWN] == 25`.

- [ ] **8.11** `test_base_points_mf_duels_won_12`
  - `ScoringConfig.default_v2().base_points[PositionGroup.MF][ActionType.DUELS_WON] == 12`.

- [ ] **8.12** `test_achievement_phase_bonuses_domestic_league_exists`
  - `ScoringConfig.default_v2().achievement_phase_bonuses["domestic_league"]["champion"] == 7000`.

- [ ] **8.13** `test_achievement_phase_bonuses_champions_league_winner_5000`
  - `ScoringConfig.default_v2().achievement_phase_bonuses["champions_league"]["winner"] == 5000`.

- [ ] **8.14** `test_achievement_phase_bonuses_runner_up_removed_from_ucl`
  - Assert: `"runner_up" not in ScoringConfig.default_v2().achievement_phase_bonuses["champions_league"]`.

- [ ] **8.15** `test_performance_factor_top3_high_rating`
  - rank_in_team=2, participation_ratio=0.50, avg_rating=8.2.
  - rank_factor=1.20, rating_factor=1.20, performance_factor=clamp(1.44, 0.50, 1.35)=1.35.
  - Assert: `_compute_rank_factor(2, 0.50) == 1.20`.
  - Assert: `_compute_rating_factor(8.2) == 1.20`.
  - Assert: `max(0.50, min(1.35, 1.20 * 1.20)) == 1.35`.

- [ ] **8.16** `test_performance_factor_low_participation_override`
  - rank_in_team=1, participation_ratio=0.15 (< 0.20).
  - Assert: `_compute_rank_factor(1, 0.15) == 0.50` (override, ignora rank=1).

- [ ] **8.17** `test_performance_factor_no_rating`
  - avg_rating=None.
  - Assert: `_compute_rating_factor(None) == 1.00`.

- [ ] **8.18** `test_achievement_bonus_uses_performance_factor_when_enabled`
  - Config v2 (`enable_performance_based_achievement_bonus=True`).
  - Jugador: player_minutes=2000, team_total_minutes=8000, rank_in_team=3, avg_rating=7.8.
  - Achievement: bonus_points=5000, weight=1.0.
  - participation_ratio=0.25, rank_factor=1.20, rating_factor=1.10,
    performance_factor=min(1.35, 1.20*1.10)=1.32.
  - expected = 5000 * 1.0 * 0.25 * 1.32 = 1650.0.
  - Assert: `bonus.final_bonus == 1650.0`.

- [ ] **8.19** `test_achievement_bonus_retrocompat_when_flag_disabled`
  - Config v2 con `enable_performance_based_achievement_bonus=False`.
  - Mismo jugador del test anterior.
  - expected = 5000 * 1.0 * 0.25 = 1250.0 (formula original).
  - Assert: `bonus.final_bonus == 1250.0`.

- [ ] **8.20** `test_register_achievement_uses_competition_name_not_id`
  - `RegisterCompetitionAchievementUseCase.execute(...)` con `competition_name="Champions League"`.
  - Config con `competition_bonus_weights = {"Champions League": 1.0}`.
  - Assert: `achievement.weight == 1.0`.
  - Llamar con `competition_name="99"` (antes el bug usaba str(competition_id)).
  - Assert: `achievement.weight == 1.0` (default) — no falla.

- [ ] **8.21** `test_scoring_config_round_trip_preserves_new_flag`
  - `ScoringConfig.default_v2()` → `to_dict()` → `from_dict()` → verificar que
    `enable_performance_based_achievement_bonus=True` se preserva.

- [ ] **8.22** `test_scoring_config_v1_default_false_for_new_flag`
  - `ScoringConfig.default()` (v1) → verificar `enable_performance_based_achievement_bonus=False`.
  - `from_dict` de un dict sin la clave → `enable_performance_based_achievement_bonus=False`.

---

### Fase 9 — Calidad

- [ ] **9.1** Ejecutar `pytest tests/` antes de escribir codigo nuevo; documentar fallos
  preexistentes.

- [ ] **9.2** Ejecutar `pytest tests/use_cases/test_scoring_balance_v2.py -v` — todos los
  22 tests deben pasar.

- [ ] **9.3** Ejecutar `pytest tests/ -v --tb=short` — tests anteriores no deben regresar.

- [ ] **9.4** Ejecutar `flake8` en los 8 archivos modificados + el nuevo test — cero errores.

- [ ] **9.5** Ejecutar `isort --check-only` en los mismos archivos — cero errores.

- [ ] **9.6** Verificar manualmente que `ScoringConfig.default_v2().midfield_control_bonus_cap_per_match == 180`.

- [ ] **9.7** Verificar que `ScoringConfig.default_v2().to_dict()["enable_performance_based_achievement_bonus"] == True`.

---

## Orden recomendado de implementacion

1. Fase 1 (services.py — bajo riesgo, solo 5 valores).
2. Fase 2 (value_objects.py — campo nuevo + nuevos defaults, cambio aditivo).
3. Fase 3 (scoring_ports.py — solo firmas, sin logica).
4. Fase 9.1 (ejecutar tests existentes, documentar estado).
5. Fase 8 (escribir los 22 tests ANTES de tocar los use cases — TDD).
6. Fase 4 (implementar nuevos metodos de repositorio).
7. Fase 5 (use case scoring — constantes + competition_weight).
8. Fase 6 (fix bug register_competition_achievement).
9. Fase 7 (use case achievement bonuses — performance_factor).
10. Fase 8: re-ejecutar tests — deben pasar.
11. Fase 9 completa.

---

## Agent Routing Brief

**@DDD-Designer needed: NO**

Justificacion:

- No se crean nuevas entidades de dominio ni nuevos agregados. `CompetitionAchievement` y
  `PlayerAchievementBonus` no cambian estructuralmente.
- Los cambios a `ScoringConfig` son aditivos: un nuevo campo booleano con default `False`.
- `_compute_rank_factor` y `_compute_rating_factor` son funciones de calculo puro (sin
  invariantes de dominio complejos) — viven en el use case, no en el dominio.
- Los nuevos metodos de repositorio son queries SQL estandar, no modelado de dominio nuevo.
- Ningun nuevo `ActionType`, ninguna nueva entidad, ninguna nueva tabla.

El implementador puede ejecutar este spec completo sin intervencion de @DDD-Designer.
