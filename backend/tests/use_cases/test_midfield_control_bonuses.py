from __future__ import annotations

import pytest

from sfa.application.use_cases.calculate_scores_for_rules_version import (
    CalculateScoresForRulesVersionUseCase,
    _MC_BONUS_CONTROL,
    _MC_BONUS_CREATIVE,
    _MC_BONUS_TWO_WAY,
)
from sfa.domain.scoring.value_objects import ScoringConfig
from sfa.domain.scoring_ports import PlayerEventRawContextDTO

from tests.use_cases.test_calculate_scores_for_rules_version import (
    FakePlayerEventScoreRepository,
    FakeScoringRulesVersionRepository,
    _make_rules_version,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_mc_stats_event(**overrides) -> PlayerEventRawContextDTO:
    """MC stats event with conditions that satisfy all three bonuses by default."""
    defaults = dict(
        event_id=10,
        player_id=99,
        fixture_id=500,
        competition_id=1,
        season="2024",
        event_type="stats",
        minute=90,
        score_diff=0,
        psxg=None,
        player_team_pos=5,
        rival_team_pos=8,
        is_away=False,
        stage_factor=1.0,
        goals=0,
        assists=0,
        shots_on=0,
        passes_key=3,
        passes_total=80,
        passes_accuracy=73,     # 73 completed / 80 = 91.25% accuracy
        dribbles_won=1,
        duels_won=3,
        tackles_won=2,
        interceptions=2,
        blocks=0,
        fouls_drawn=1,
        fouls_committed=0,
        cards_yellow=0,
        cards_red=0,
        penalty_won=0,
        dribbles_past=0,
        rating=7.8,
        player_position="MC",
        minutes=75,
        player_team_strength=None,
        rival_team_strength=None,
    )
    defaults.update(overrides)
    return PlayerEventRawContextDTO(**defaults)


def _make_v2_rules_version(version_id: int = 3):
    return _make_rules_version(version_id=version_id, config=ScoringConfig.default_v2())


async def _run_use_case(events, rules_version):
    """Run the use case and return upserted scores."""
    event_repo = FakePlayerEventScoreRepository(events=events)
    rules_repo = FakeScoringRulesVersionRepository(version=rules_version)
    use_case = CalculateScoresForRulesVersionUseCase(
        rules_version_repo=rules_repo,
        event_score_repo=event_repo,
    )
    await use_case.execute(
        rules_version_id=rules_version.id,
        season="2024",
        force_recalculate=True,
    )
    return event_repo.upserted


# ─── Tests ───────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_bonus_not_applied_when_position_not_mc():
    """Bonuses do not apply to non-MC positions."""
    event = _make_mc_stats_event(player_position="DC")
    scores = await _run_use_case([event], _make_v2_rules_version())
    assert scores
    score = scores[0]
    mb = score.calculation_details["midfield_bonuses"]
    assert mb["enabled"] is False


@pytest.mark.anyio
async def test_bonus_not_applied_when_flag_disabled():
    """Bonuses do not apply when enable_midfield_control_bonuses=False."""
    config = ScoringConfig.default_v2()
    import dataclasses
    config_off = dataclasses.replace(config, enable_midfield_control_bonuses=False)
    rv = _make_rules_version(version_id=3, config=config_off)
    event = _make_mc_stats_event()
    scores = await _run_use_case([event], rv)
    assert scores
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["enabled"] is False


@pytest.mark.anyio
async def test_bonus_not_applied_on_legacy_config_without_field():
    """ScoringConfig.default() (v1) has enable_midfield_control_bonuses=False."""
    config_v1 = ScoringConfig.default()
    assert config_v1.enable_midfield_control_bonuses is False
    rv = _make_rules_version(version_id=1, config=config_v1)
    event = _make_mc_stats_event()
    scores = await _run_use_case([event], rv)
    assert scores
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["enabled"] is False


@pytest.mark.anyio
async def test_from_dict_without_key_defaults_to_false():
    """from_dict on a v1-like dict without the key produces enable=False."""
    base = ScoringConfig.default_v2().to_dict()
    del base["enable_midfield_control_bonuses"]
    del base["midfield_control_bonus_cap_per_match"]
    recovered = ScoringConfig.from_dict(base)
    assert recovered.enable_midfield_control_bonuses is False
    assert recovered.midfield_control_bonus_cap_per_match == 180


@pytest.mark.anyio
async def test_control_midfield_bonus_applied():
    """CONTROL_MIDFIELD_BONUS applies when all conditions are met."""
    # passes_completed = int(80 * 91 / 100) = 72 >= 65; accuracy=91 >= 90; rating=7.8 >= 7.6
    # Two-way: defensive_actions = 0 < 3 → NOT earned; Creative: passes_key=0 < 2 → NOT earned
    event = _make_mc_stats_event(
        passes_total=80, passes_accuracy=91.0, passes_key=0,
        tackles_won=0, interceptions=0, rating=7.8,
    )
    scores = await _run_use_case([event], _make_v2_rules_version())
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["enabled"] is True
    assert mb["control_midfield_bonus_earned"] is True
    assert mb["two_way_midfield_bonus_earned"] is False
    assert mb["creative_control_bonus_earned"] is False
    assert mb["mc_bonus_total_base"] == _MC_BONUS_CONTROL


@pytest.mark.anyio
async def test_two_way_midfield_bonus_applied():
    """TWO_WAY_MIDFIELD_BONUS applies when conditions are met (not CONTROL)."""
    # passes_accuracy=55 (55/65=84.6% < 90%→no CONTROL); defensive=4≥3→TWO_WAY; key=1<2→no CREATIVE
    event = _make_mc_stats_event(
        passes_total=65, passes_accuracy=55, passes_key=1,
        tackles_won=2, interceptions=2, rating=7.5,
    )
    scores = await _run_use_case([event], _make_v2_rules_version())
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["enabled"] is True
    assert mb["control_midfield_bonus_earned"] is False
    assert mb["two_way_midfield_bonus_earned"] is True
    assert mb["creative_control_bonus_earned"] is False
    assert mb["mc_bonus_total_base"] == _MC_BONUS_TWO_WAY


@pytest.mark.anyio
async def test_creative_control_bonus_applied():
    """CREATIVE_CONTROL_BONUS applies when conditions are met (not CONTROL, not TWO_WAY)."""
    # passes_accuracy=57 (57/65=87.7%≥85%); 57≥55; key=3≥2; rating=7.7≥7.7 → CREATIVE
    # CONTROL: 57<65 → NO; TWO_WAY: defensive=0<3 → NO
    event = _make_mc_stats_event(
        passes_total=65, passes_accuracy=57, passes_key=3,
        tackles_won=0, interceptions=0, rating=7.7,
    )
    scores = await _run_use_case([event], _make_v2_rules_version())
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["enabled"] is True
    assert mb["control_midfield_bonus_earned"] is False
    assert mb["two_way_midfield_bonus_earned"] is False
    assert mb["creative_control_bonus_earned"] is True
    assert mb["mc_bonus_total_base"] == _MC_BONUS_CREATIVE


@pytest.mark.anyio
async def test_cap_applied_when_all_three_bonuses_earned():
    """Cap of 180 is applied when all three bonuses are earned (300 → 180)."""
    # CONTROL: passes_completed=72>=65, accuracy=91>=90, rating=7.8>=7.6 ✓
    # TWO_WAY: passes_completed=72>=50, rating=7.8>=7.4, defensive=4>=3 ✓
    # CREATIVE: passes_completed=72>=55, accuracy=91>=85, rating=7.8>=7.7, key=3>=2 ✓
    event = _make_mc_stats_event(
        passes_total=80, passes_accuracy=91.0, passes_key=3,
        tackles_won=2, interceptions=2, rating=7.8,
    )
    scores = await _run_use_case([event], _make_v2_rules_version())
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["control_midfield_bonus_earned"] is True
    assert mb["two_way_midfield_bonus_earned"] is True
    assert mb["creative_control_bonus_earned"] is True
    assert mb["mc_bonus_total_before_cap"] == _MC_BONUS_CONTROL + _MC_BONUS_TWO_WAY + _MC_BONUS_CREATIVE
    assert mb["mc_bonus_capped"] is True
    assert mb["mc_bonus_total_base"] == 180


@pytest.mark.anyio
async def test_bonus_not_applied_when_rating_below_all_minimums():
    """No bonus when rating is below all minimums (7.4, 7.5, 7.6)."""
    event = _make_mc_stats_event(rating=7.3)
    scores = await _run_use_case([event], _make_v2_rules_version())
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["enabled"] is True  # enabled but no bonus earned
    assert mb["control_midfield_bonus_earned"] is False
    assert mb["two_way_midfield_bonus_earned"] is False
    assert mb["creative_control_bonus_earned"] is False
    assert mb["mc_bonus_total_base"] == 0


@pytest.mark.anyio
async def test_bonus_not_applied_when_minutes_below_60():
    """No bonus when minutes < 60."""
    event = _make_mc_stats_event(minutes=45)
    scores = await _run_use_case([event], _make_v2_rules_version())
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["enabled"] is False


@pytest.mark.anyio
async def test_bonus_not_applied_when_passes_completed_too_low():
    """No bonus when passes_completed < 50 (all three require >= 50 or >= 65)."""
    # passes_accuracy=40 = 40 completed / 50 total = 80% — 40 < 50 (all thresholds fail)
    event = _make_mc_stats_event(passes_total=50, passes_accuracy=40, rating=8.0)
    scores = await _run_use_case([event], _make_v2_rules_version())
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["enabled"] is True
    assert mb["control_midfield_bonus_earned"] is False
    assert mb["two_way_midfield_bonus_earned"] is False
    assert mb["creative_control_bonus_earned"] is False


@pytest.mark.anyio
async def test_control_bonus_not_applied_when_accuracy_below_90():
    """CONTROL requires passes_accuracy >= 90; below that it does not fire."""
    # passes_accuracy=66 (66/75=88% < 90% → CONTROL not earned); 66≥65 ✓
    event = _make_mc_stats_event(
        passes_total=75, passes_accuracy=66,
        tackles_won=0, interceptions=0, passes_key=0, rating=7.8,
    )
    scores = await _run_use_case([event], _make_v2_rules_version())
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["control_midfield_bonus_earned"] is False


@pytest.mark.anyio
async def test_no_crash_when_tackles_and_interceptions_are_zero():
    """tackles_won=0 and interceptions=0 → defensive_actions=0 → no TWO_WAY, no crash."""
    event = _make_mc_stats_event(tackles_won=0, interceptions=0, rating=7.8)
    scores = await _run_use_case([event], _make_v2_rules_version())
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["two_way_midfield_bonus_earned"] is False


@pytest.mark.anyio
async def test_m2_and_mrating_applied_correctly():
    """mc_bonus_final = mc_bonus_total_base × M2_attenuated × Mrating.

    stage_factor=1.5, stats_m2_attenuation=0.5 → effective M2 = 1.0 + (1.5-1.0)*0.5 = 1.25
    rating=8.5 → Mrating in v2 = 1.30 (top_value)
    """
    # passes_accuracy=57 (57/65=87.7%≥85%); 57≥55; key=3≥2; rating=8.5≥7.7 → CREATIVE
    # CONTROL: 57<65 → NO; TWO_WAY: defensive=0<3 → NO
    event = _make_mc_stats_event(
        stage_factor=1.5,
        passes_total=65, passes_accuracy=57, passes_key=3,
        tackles_won=0, interceptions=0, rating=8.5,
    )
    scores = await _run_use_case([event], _make_v2_rules_version())
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["creative_control_bonus_earned"] is True
    assert mb["mc_bonus_total_base"] == _MC_BONUS_CREATIVE
    # M2 is attenuated: 1.0 + (1.5 - 1.0) * 0.5 = 1.25
    effective_m2 = 1.0 + (1.5 - 1.0) * 0.5
    expected_final = round(_MC_BONUS_CREATIVE * effective_m2 * 1.30, 2)
    assert mb["mc_bonus_final"] == expected_final


@pytest.mark.anyio
async def test_m1_m3_m4_mvisit_not_applied_to_bonus():
    """M1/M3/M4/Mvisit do NOT affect the bonus calculation."""
    # is_away=True (would activate Mvisit), rival_team_pos=1 (high M1)
    # stage_factor=1.0, rating=7.8 → Mrating=1.15 in v2 ([8.0,8.5)→1.15)...
    # rating=7.8 → in v2 thresholds: [7.5,8.0)→1.00
    # passes_accuracy=73 (73/80=91.25%≥90%); CONTROL(140)+CREATIVE(70)=210>cap(180)→capped
    event = _make_mc_stats_event(
        is_away=True,
        player_team_pos=15, rival_team_pos=1,  # high M1
        stage_factor=1.0,
        passes_total=80, passes_accuracy=73, passes_key=3,
        tackles_won=0, interceptions=0, rating=7.8,
    )
    scores = await _run_use_case([event], _make_v2_rules_version())
    mb = scores[0].calculation_details["midfield_bonuses"]
    # Mrating for rating=7.8 in v2: [7.5,8.0) → 1.00
    # CONTROL(140)+CREATIVE(70)=210 > cap(180) → capped at 180
    # mc_bonus_final = 180 × M2(1.0) × Mrating(1.00) = 180.0
    # M1, M3, M4, Mvisit are NOT in the bonus formula
    assert mb["M2"] == 1.0
    expected = round(mb["mc_bonus_total_base"] * mb["M2"] * mb["Mrating"], 2)
    assert mb["mc_bonus_final"] == expected


@pytest.mark.anyio
async def test_calculation_details_contains_audit_keys():
    """calculation_details includes all required midfield_bonuses audit keys."""
    event = _make_mc_stats_event()
    scores = await _run_use_case([event], _make_v2_rules_version())
    mb = scores[0].calculation_details["midfield_bonuses"]
    required_keys = {
        "enabled", "passes_completed", "passes_accuracy", "rating", "minutes",
        "control_midfield_bonus_earned", "two_way_midfield_bonus_earned",
        "creative_control_bonus_earned", "mc_bonus_total_base", "mc_bonus_capped",
        "M2", "Mrating", "mc_bonus_final",
    }
    assert required_keys.issubset(mb.keys())
    assert scores[0].calculation_details["final_points"] == scores[0].final_points


@pytest.mark.anyio
async def test_legacy_v1_config_not_affected():
    """V1 config (default()) never applies midfield bonuses."""
    rv = _make_rules_version(version_id=1, config=ScoringConfig.default())
    event = _make_mc_stats_event()
    scores = await _run_use_case([event], rv)
    assert scores
    mb = scores[0].calculation_details["midfield_bonuses"]
    assert mb["enabled"] is False
