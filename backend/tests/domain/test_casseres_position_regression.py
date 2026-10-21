from __future__ import annotations

import json
from pathlib import Path

import pytest

from sfa.domain.player_positions.longitudinal import PlayerPositionTimeline
from sfa.domain.player_positions.resolution import PlayerPositionResolver, PositionResolutionQuery
from sfa.domain.player_positions.services import LineupPositionInterpreter, aggregate_position_support
from sfa.domain.player_positions.value_objects import (
    LineupSlot,
    PlayerStartEvidence,
    PositionProfileContext,
    Quality,
    Side,
    StartingLineup,
    TacticalRole,
)

FIXTURE = Path(__file__).parents[1] / "fixtures/player_positions/casseres-five-starts-2026.json"


def corpus():
    return json.loads(FIXTURE.read_text("utf-8"))


def interpret(data, version):
    lineup = StartingLineup(
        fixture_id=version["fixture_external_id"], team_id=data["external_team_id"], season=data["season"],
        competition_id=data["competition_id"], played_at=version["played_at"], formation=version["formation"],
        starters=tuple(LineupSlot(**s) for s in version["starters"]),
        participant_team_ids=tuple(version["participant_team_ids"]),
    )
    result = LineupPositionInterpreter().interpret(lineup)
    assert result.reason is None
    return next(o for o in result.observations if o.external_id == data["external_player_id"])


def requested_observations(data):
    result = []
    for case in data["expected_cases"]:
        version = next(v for v in data["versions"] if v["fixture_external_id"] == case["fixture_external_id"]
                       and v["formation"] == case["formation"]
                       and any(s["external_id"] == data["external_player_id"] and s["grid"] == case["grid"]
                               for s in v["starters"]))
        result.append(interpret(data, version))
    return tuple(result)


def timeline(data, observations):
    context = PositionProfileContext(data["external_player_id"], data["external_team_id"], data["season"],
                                     data["competition_id"], "club")
    return PlayerPositionTimeline(context, tuple(
        PlayerStartEvidence(context, o.fixture_id, o.played_at, observation=o,
                            source_ref="retained-casseres-regression")
        for o in observations
    ))


@pytest.mark.parametrize("fixture_id,role,side,candidates", [
    (1552785, TacticalRole.CM, Side.RIGHT, {TacticalRole.CM}),
    (1552778, TacticalRole.UNKNOWN, Side.RIGHT, {TacticalRole.DM, TacticalRole.CM}),
    (1552772, TacticalRole.CM, Side.LEFT, {TacticalRole.CM}),
    (1552761, TacticalRole.UNKNOWN, Side.RIGHT, {TacticalRole.DM, TacticalRole.CM}),
    (1552754, TacticalRole.UNKNOWN, Side.RIGHT, {TacticalRole.DM, TacticalRole.CM}),
])
def test_casseres_requested_midfield_slots_never_project_to_center_back(fixture_id, role, side, candidates):
    data = corpus()
    observation = next(o for o in requested_observations(data) if o.fixture_id == fixture_id)
    assert observation.sfa_position == "MC"
    assert (observation.role, observation.side, observation.candidates) == (role, side, candidates)
    assert observation.role_quality == (Quality.SPECIFIC if role == TacticalRole.CM else Quality.AMBIGUOUS)


def test_five_requested_starts_support_mc_without_fabricating_a_habitual_dm_or_known_coverage():
    data = corpus()
    observations = requested_observations(data)
    support = aggregate_position_support(observations)
    assert support.observations == 5 and support.projection_distribution == (("MC", 5),)
    assert support.sfa_position == "MC" and support.role == TacticalRole.UNKNOWN
    assert support.side == Side.RIGHT
    assert support.coverage is None and not support.eligible
    assert support.reasons == ("unknown_start_coverage",)
    preview = timeline(data, observations).preview(as_of=data["captured_at"])
    assert preview.recent.primary_position == "MC"
    assert preview.recent.primary_role == TacticalRole.UNKNOWN
    assert preview.recent.primary_side == Side.UNKNOWN
    assert preview.recent.side_reason == "no_dominant_role"
    assert preview.recent.candidate_only and not preview.recent.meets_evidence_gates
    assert preview.recent.reasons == ("unknown_start_coverage",)


@pytest.mark.parametrize("known_starts,eligible", [(5, True), (7, True), (8, True), (9, False)])
def test_casseres_coverage_gate_requires_a_proven_denominator(known_starts, eligible):
    # Hypothetical complete inventories exercise the gate; these counts are not
    # assertions that the real season's starting inventory has been reconciled.
    support = aggregate_position_support(requested_observations(corpus()), known_starts=known_starts,
                                         complete_start_inventory=True)
    assert support.coverage == 5 / known_starts
    assert support.eligible is eligible and support.sfa_position == "MC"


def test_retained_le_mans_versions_conflict_even_though_both_project_to_mc():
    data = corpus()
    observations = tuple(interpret(data, v) for v in data["versions"])
    variants = {o for o in observations if o.fixture_id == 1552785}
    assert len(variants) == 2
    assert {o.sfa_position for o in variants} == {"MC"}
    assert {o.role for o in variants} == {TacticalRole.CM, TacticalRole.UNKNOWN}
    support = aggregate_position_support(observations)
    assert support.observations == 4 and support.conflicting_fixtures == 1
    assert support.sfa_position == "MC" and not support.eligible
    assert set(support.reasons) == {"unknown_start_coverage", "contradictory_duplicate_fixture"}
    # A fully known inventory must not silently make contradictory evidence eligible.
    assert not aggregate_position_support(observations, known_starts=5, complete_start_inventory=True).eligible
    profile = timeline(data, observations).preview(as_of=data["captured_at"]).recent
    assert profile.primary_position == "MC" and profile.observations == 4
    assert profile.conflicting_fixture_ids == (1552785,)
    assert not profile.meets_evidence_gates


def test_observed_mc_profile_does_not_publish_over_legacy_dc_without_an_accepted_decision():
    data = corpus()
    profile = timeline(data, requested_observations(data)).preview(as_of=data["captured_at"]).recent
    query = PositionResolutionQuery(
        player_id=data["player_id"], effective_at=data["captured_at"], team_id=data["team_id"],
        competition_id=data["competition_id"], season=data["season"],
        external_player_id=data["external_player_id"], external_team_id=data["external_team_id"],
    )
    result = PlayerPositionResolver().resolve(query, (), observed_profile=profile, legacy_comparison="DC")
    assert result.status == "unknown" and result.position is None
    assert result.observed_profile.primary_position == "MC"
    assert result.legacy_comparison == "DC" and not result.publication_enabled
