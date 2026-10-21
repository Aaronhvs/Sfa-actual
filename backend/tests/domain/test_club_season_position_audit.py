import json
from dataclasses import replace
from pathlib import Path

import pytest

from sfa.domain.player_positions.club_season_audit import audit_club_season
from sfa.domain.player_positions.longitudinal import PlayerPositionTimeline
from sfa.domain.player_positions.services import LineupPositionInterpreter
from sfa.domain.player_positions.value_objects import (
    LineupSlot,
    PlayerStartEvidence,
    PositionProfileContext,
    StartingLineup,
)

CORPUS = Path(__file__).parents[1] / "fixtures/player_positions/dembele-five-starts-2026.json"


def dembele_entries():
    data = json.loads(CORPUS.read_text("utf8"))
    entries = []
    for v in data["versions"]:
        lineup = StartingLineup(v["fixture_external_id"], data["external_team_id"], data["season"],
                                v["competition_id"], v["played_at"], v["formation"],
                                tuple(LineupSlot(**p) for p in v["starters"]), tuple(v["participant_team_ids"]))
        result = LineupPositionInterpreter().interpret(lineup)
        assert result.reason is None
        o = next(o for o in result.observations if o.external_id == data["external_player_id"])
        context = PositionProfileContext(o.external_id, o.team_id, o.season, o.competition_id, "club")
        entries.append(PlayerStartEvidence(context, o.fixture_id, o.played_at, o, source_ref=v["payload_sha256"]))
    return data, tuple(entries)


def test_dembele_regression_four_center_forward_starts_and_one_wing_projects_del():
    data, entries = dembele_entries()
    p = audit_club_season(entries, as_of=data["captured_at"])
    assert p.primary_position == "DEL" and p.primary_role.value == "CF" and p.primary_side.value == "CENTER"
    assert [(f.value, f.count) for f in p.position_distribution] == [("DEL", 4), ("EXT", 1)]
    assert p.observations == p.selected_starts == 5 and p.competition_ids == (9, 10)
    assert not p.publishable and not p.inventory_complete and p.reasons == ("unknown_start_coverage",)
    assert {e.observation.competition_id for e in entries} == {9, 10}


def test_cross_competition_votes_do_not_depend_on_choosing_the_larger_league_sample():
    data, entries = dembele_entries()
    subset = tuple(e for e in entries if e.fixture_id != 1552735)
    assert audit_club_season(subset, as_of=data["captured_at"]).primary_position == "DEL"
    for competition in (9, 10):
        group = tuple(e for e in subset if e.context.competition_id == competition)
        assert len(group) == 2
        profile = PlayerPositionTimeline(group[0].context, group).preview(as_of=data["captured_at"]).recent
        assert profile.primary_position is None


def test_duplicate_versions_and_input_order_cannot_inflate_support():
    data, entries = dembele_entries()
    one = audit_club_season(entries, as_of=data["captured_at"])
    repeated = audit_club_season(tuple(reversed(entries * 3)), as_of=data["captured_at"])
    assert repeated == one


@pytest.mark.parametrize("change", [
    {"team_id": 999}, {"season": "2025"}, {"team_kind": "national"}, {"external_id": 999},
])
def test_club_season_union_rejects_context_contamination(change):
    data, entries = dembele_entries()
    bad = replace(entries[0], context=replace(entries[0].context, **change))
    with pytest.raises(ValueError, match="Cannot mix"):
        audit_club_season(entries + (bad,), as_of=data["captured_at"])


def test_conflicting_versions_are_visible_and_receive_no_vote():
    data, entries = dembele_entries()
    bad = replace(entries[0], observation=replace(entries[0].observation, sfa_position="EXT"))
    p = audit_club_season(entries + (bad,), as_of=data["captured_at"])
    assert p.observations == 4 and p.selected_starts == 5
    assert p.conflicting_fixture_ids == (entries[0].fixture_id,)
    assert "contradictory_evidence" in p.reasons


def test_fixture_cannot_receive_two_votes_via_a_fictional_competition():
    data, entries = dembele_entries()
    first = entries[0]
    bad = replace(first, context=replace(first.context, competition_id=123),
                  observation=replace(first.observation, competition_id=123))
    p = audit_club_season(entries + (bad,), as_of=data["captured_at"])
    assert p.observations == 4 and len(p.fixture_ids) == 5
    assert p.conflicting_fixture_ids == (first.fixture_id,)
