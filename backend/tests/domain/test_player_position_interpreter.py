from dataclasses import replace

import pytest

from sfa.domain.player_positions.services import TEMPLATES, LineupPositionInterpreter, aggregate_position_support
from sfa.domain.player_positions.value_objects import LineupSlot, Quality, Side, StartingLineup, TacticalRole


def make_lineup(formation="4-3-3", fixture_id=100):
    starters = [LineupSlot(1, "1:1", "G")]
    for row, slots in enumerate(TEMPLATES[formation], 2):
        first_id = len(starters)
        starters.extend(LineupSlot(first_id + col, f"{row}:{col}", None) for col in range(1, len(slots) + 1))
    return StartingLineup(fixture_id, 10, "2026", 140, "2026-10-01T12:00:00+00:00", formation,
                         tuple(starters), (10, 20))


def slot(formation, grid):
    lineup = make_lineup(formation)
    identity = next(p.external_id for p in lineup.starters if p.grid == grid)
    return next(o for o in LineupPositionInterpreter().interpret(lineup).observations if o.external_id == identity)


@pytest.mark.parametrize("formation", tuple(TEMPLATES))
def test_all_template_slots_are_deterministic_and_order_independent(formation):
    lineup = make_lineup(formation)
    interpreter = LineupPositionInterpreter()
    result = interpreter.interpret(lineup)
    assert result.reason is None
    assert len(result.observations) == 11
    assert result == interpreter.interpret(replace(lineup, starters=tuple(reversed(lineup.starters))))
    assert result == interpreter.interpret(replace(lineup, participant_team_ids=(20, 10)))
    assert all(o.external_id > 0 and o.candidates and o.side != Side.UNKNOWN for o in result.observations)


@pytest.mark.parametrize("formation,grid,role,side,projection", [
    ("4-3-3", "2:1", "FB", "LEFT", "LAT"),
    ("4-3-3", "2:4", "FB", "RIGHT", "LAT"),
    ("4-3-3", "2:2", "CB", "LEFT", "DC"),
    ("4-3-3", "4:2", "CF", "CENTER", "DEL"),
    ("4-2-3-1", "4:2", "AM", "CENTER", "MCO"),
    ("4-2-3-1", "5:1", "CF", "CENTER", "DEL"),
    ("4-4-2", "3:1", "WM", "LEFT", None),
    ("4-1-4-1", "3:1", "DM", "CENTER", "MC"),
    ("3-5-2", "2:2", "CB", "CENTER", "DC"),
    ("3-4-1-2", "4:1", "AM", "CENTER", "MCO"),
    ("3-4-2-1", "4:2", "AM", "RIGHT", "MCO"),
    ("4-3-1-2", "4:1", "AM", "CENTER", "MCO"),
    ("4-1-2-1-2", "5:1", "AM", "CENTER", "MCO"),
])
def test_sporting_role_side_and_projection(formation, grid, role, side, projection):
    result = slot(formation, grid)
    assert (result.role, result.side, result.sfa_position) == (role, side, projection)
    assert result.role_quality == Quality.SPECIFIC


@pytest.mark.parametrize("formation,grid,candidates,projection", [
    ("4-2-3-1", "3:1", {"DM", "CM"}, "MC"),
    ("4-2-3-1", "4:1", {"W", "AM"}, None),
    ("3-5-2", "3:1", {"WB", "WM"}, None),
    ("3-4-3", "3:4", {"WB", "WM"}, None),
    ("5-3-2", "2:1", {"FB", "WB"}, "LAT"),
    ("4-2-2-2", "4:1", {"AM", "WM"}, None),
])
def test_preserves_candidates_without_inverting_sfa_projection(formation, grid, candidates, projection):
    result = slot(formation, grid)
    assert result.candidates == candidates
    assert result.role == TacticalRole.UNKNOWN
    assert result.role_quality == Quality.AMBIGUOUS
    assert result.sfa_position == projection
    assert result.side_quality == Quality.SPECIFIC


def test_unrecognized_orientation_keeps_role_but_never_assigns_left_or_right():
    result = LineupPositionInterpreter().interpret(replace(make_lineup(), orientation="unverified"))
    assert len(result.observations) == 11
    assert all(o.side == Side.UNKNOWN and o.side_quality == Quality.MISSING for o in result.observations)
    assert any(o.role == TacticalRole.FB and o.sfa_position == "LAT" for o in result.observations)


@pytest.mark.parametrize("changes,reason", [
    ({"schema": "other-provider"}, "unknown_schema"),
    ({"formation": None}, "unsupported_formation"),
    ({"formation": "5-4-1"}, "unsupported_formation"),
    ({"participant_team_ids": (20, 30)}, "team_not_in_fixture"),
    ({"participant_team_ids": (10, 10)}, "team_not_in_fixture"),
])
def test_rejects_unknown_contract_context_or_formation(changes, reason):
    result = LineupPositionInterpreter().interpret(replace(make_lineup(), **changes))
    assert result.reason == reason
    assert not result.observations


@pytest.mark.parametrize("change,reason", [
    (lambda s: s[:-1], "expected_eleven_starters"),
    (lambda s: s + (s[-1],), "expected_eleven_starters"),
    (lambda s: (replace(s[0], external_id=None),) + s[1:], "missing_player_identity"),
    (lambda s: (replace(s[0], external_id=True),) + s[1:], "missing_player_identity"),
    (lambda s: (replace(s[0], external_id=0),) + s[1:], "missing_player_identity"),
    (lambda s: (replace(s[0], external_id=s[1].external_id),) + s[1:], "duplicate_player_identity"),
    (lambda s: (replace(s[0], grid=None),) + s[1:], "missing_or_malformed_grid"),
    (lambda s: (replace(s[0], grid="0:1"),) + s[1:], "missing_or_malformed_grid"),
    (lambda s: (replace(s[0], grid="1:1 "),) + s[1:], "missing_or_malformed_grid"),
    (lambda s: (replace(s[0], grid=s[1].grid),) + s[1:], "duplicate_grid"),
    (lambda s: (replace(s[0], grid="9:1"),) + s[1:], "grid_formation_mismatch"),
    (lambda s: (replace(s[0], coarse_position=None),) + s[1:], "invalid_goalkeeper"),
    (lambda s: s[:1] + (replace(s[1], coarse_position="G"),) + s[2:], "invalid_goalkeeper"),
    (lambda s: s[:1] + (replace(s[1], coarse_position="F"),) + s[2:], "coarse_position_inconsistent"),
    (lambda s: s[:1] + (replace(s[1], coarse_position="unknown"),) + s[2:], "coarse_position_inconsistent"),
])
def test_rejects_malformed_or_contradictory_lineup_as_a_unit(change, reason):
    lineup = make_lineup()
    result = LineupPositionInterpreter().interpret(replace(lineup, starters=change(lineup.starters)))
    assert result.reason == reason
    assert result.observations == ()


def observations(count=3):
    original = slot("4-3-3", "2:1")
    return tuple(replace(original, fixture_id=100 + i, played_at=f"2026-10-{i + 1:02d}") for i in range(count))


def test_unique_fixtures_support_coverage_and_idempotence():
    values = observations()
    result = aggregate_position_support(values, known_starts=5, complete_start_inventory=True)
    assert result.eligible and result.coverage == 0.6
    assert (result.role, result.side, result.sfa_position) == ("FB", "LEFT", "LAT")
    assert result == aggregate_position_support(values + values, known_starts=5, complete_start_inventory=True)
    assert result == aggregate_position_support(tuple(reversed(values)), known_starts=5, complete_start_inventory=True)


def test_no_known_coverage_means_no_eligibility_even_with_three_observations():
    result = aggregate_position_support(observations(), known_starts=3)
    assert not result.eligible and result.coverage is None
    assert result.reasons == ("unknown_start_coverage",)


@pytest.mark.parametrize("count,known,complete,reason", [
    (2, 2, True, "insufficient_unique_fixtures"),
    (3, 6, True, "insufficient_start_coverage"),
    (3, 2, True, "unknown_start_coverage"),
    (3, 0, True, "unknown_start_coverage"),
    (0, 0, True, "unknown_start_coverage"),
])
def test_support_gate_boundaries(count, known, complete, reason):
    result = aggregate_position_support(observations(count), known_starts=known, complete_start_inventory=complete)
    assert not result.eligible and reason in result.reasons


def test_two_thirds_support_includes_unknown_side_and_projection_in_denominators():
    values = observations()
    changed = replace(values[2], role=TacticalRole.UNKNOWN, side=Side.UNKNOWN, sfa_position=None,
                      candidates=frozenset({TacticalRole.FB, TacticalRole.WM}), role_quality=Quality.AMBIGUOUS)
    result = aggregate_position_support(values[:2] + (changed,), known_starts=3, complete_start_inventory=True)
    assert result.eligible and result.role == "FB" and result.side == "LEFT"
    assert ("UNKNOWN", 1) in result.side_distribution
    assert ("UNKNOWN", 1) in result.projection_distribution
    failed = aggregate_position_support((values[0], changed, replace(changed, fixture_id=999)),
                                        known_starts=3, complete_start_inventory=True)
    assert not failed.eligible and failed.side == Side.UNKNOWN and failed.sfa_position is None


def test_common_projection_does_not_invent_specific_role():
    values = tuple(replace(slot("4-2-3-1", "3:1"), fixture_id=i) for i in range(3))
    result = aggregate_position_support(values, known_starts=3, complete_start_inventory=True)
    assert result.eligible and result.sfa_position == "MC" and result.role == TacticalRole.UNKNOWN


def test_conflicting_duplicate_is_excluded_and_blocks_eligibility():
    values = observations(4)
    conflict = replace(values[0], side=Side.RIGHT)
    result = aggregate_position_support(values + (conflict,), known_starts=4, complete_start_inventory=True)
    assert result.observations == 3 and result.conflicting_fixtures == 1
    assert not result.eligible and "contradictory_duplicate_fixture" in result.reasons


def test_independent_modals_cannot_fabricate_a_right_back():
    values = observations()
    right_back = replace(values[1], side=Side.RIGHT)
    right_midfielder = replace(values[2], role=TacticalRole.CM, side=Side.RIGHT,
                               candidates=frozenset({TacticalRole.CM}), sfa_position="MC")
    result = aggregate_position_support((values[0], right_back, right_midfielder),
                                        known_starts=3, complete_start_inventory=True)
    assert result.role == TacticalRole.FB and result.sfa_position == "LAT"
    assert result.side == Side.UNKNOWN
    assert ("FB", "RIGHT", 1) in result.role_side_distribution


@pytest.mark.parametrize("changes", [{"team_id": 99}, {"season": "2025"}, {"competition_id": 9}, {"external_id": 888}])
def test_never_combines_different_player_or_temporal_contexts(changes):
    values = observations()
    with pytest.raises(ValueError, match="contexts"):
        aggregate_position_support(values + (replace(values[0], **changes),))
