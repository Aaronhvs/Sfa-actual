from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from sfa.domain.player_positions.longitudinal import PlayerPositionTimeline
from sfa.domain.player_positions.value_objects import (
    PlayerStartEvidence,
    PositionObservation,
    PositionProfileContext,
    Quality,
    Side,
    TacticalRole,
)

CONTEXT = PositionProfileContext(9001, 10, "2026", 1)
AS_OF = "2026-10-18T12:00:00+00:00"
PROJECTIONS = {"CM": "MC", "DM": "MC", "AM": "MCO", "FB": "LAT", "WB": "LAT",
               "W": "EXT", "CB": "DC", "CF": "DEL", "GK": "GK", "WM": None, "UNKNOWN": None}


def evidence(identity, role="CM", side="CENTER", *, missing=None, context=CONTEXT):
    date = (datetime(2026, 9, 1, tzinfo=timezone.utc) + timedelta(days=identity - 1)).isoformat()
    observation = None if missing else PositionObservation(
        context.external_id, identity, context.team_id, context.season, context.competition_id, date,
        TacticalRole(role), Side(side), frozenset({TacticalRole(role)}),
        Quality.SPECIFIC, Quality.SPECIFIC if side != "UNKNOWN" else Quality.MISSING,
        PROJECTIONS[role], "starting_slot",
    )
    return PlayerStartEvidence(context, identity, date, observation, missing, f"fixture:{identity}")


def timeline(roles, sides=None):
    entries = tuple(evidence(i, role, sides[i - 1] if sides else "CENTER") for i, role in enumerate(roles, 1))
    return PlayerPositionTimeline(CONTEXT, entries)


def preview(roles, sides=None, *, complete=True):
    return timeline(roles, sides).preview(as_of=AS_OF, complete_start_inventory=complete)


def shares(distribution):
    return {item.value: (item.count, item.share) for item in distribution}


def test_eighty_twenty_has_main_and_secondary_without_claiming_minutes():
    result = preview(["CM"] * 8 + ["FB"] * 2, ["RIGHT"] * 8 + ["LEFT"] * 2).recent
    assert result.primary_position == "MC" and result.primary_role == "CM"
    assert result.primary_side == "RIGHT" and "Lateral" not in result.label
    assert shares(result.position_distribution) == {"MC": (8, .8), "LAT": (2, .2)}
    assert shares(result.secondary_positions) == {"LAT": (2, .2)}
    assert [(p.role, p.side, p.count) for p in result.secondary_pairs] == [("FB", "LEFT", 2)]
    assert result.meets_evidence_gates and result.candidate_only


def test_common_projection_never_invents_a_more_specific_tactical_role():
    result = preview(["DM"] * 4 + ["CM"] * 4 + ["FB"] * 2).recent
    assert result.primary_position == "MC" and result.primary_role == "UNKNOWN"
    assert shares(result.role_distribution) == {"CM": (4, .4), "DM": (4, .4), "FB": (2, .2)}
    assert result.primary_side == "UNKNOWN" and result.side_reason == "no_dominant_role"


def test_right_and_left_wing_are_details_of_the_same_sfa_position():
    result = preview(["W"] * 10, ["RIGHT"] * 8 + ["LEFT"] * 2).recent
    assert result.primary_position == "EXT" and result.primary_role == "W" and result.primary_side == "RIGHT"
    assert result.label == "Extremo derecho" and result.secondary_positions == ()
    assert [(p.role, p.side, p.count) for p in result.secondary_pairs] == [("W", "LEFT", 2)]


@pytest.mark.parametrize("role,label", [("W", "Extremo izquierdo"), ("CB", "Defensa central izquierdo"),
                                       ("FB", "Lateral izquierdo"), ("WB", "Carrilero izquierdo")])
def test_role_and_side_labels_are_preserved(role, label):
    result = preview([role] * 5, ["LEFT"] * 5).recent
    assert result.label == label


def test_mixed_centres_and_missing_side_are_different_states():
    mixed = preview(["CB"] * 10, ["LEFT"] * 5 + ["RIGHT"] * 5).recent
    missing = preview(["CB"] * 10, ["UNKNOWN"] * 10).recent
    assert mixed.primary_position == missing.primary_position == "DC"
    assert mixed.primary_side == missing.primary_side == "UNKNOWN"
    assert mixed.side_reason == "no_dominant_side" and missing.side_reason == "insufficient_side_support"
    assert mixed.sides_by_role[0].known_sides == 10 and missing.sides_by_role[0].known_sides == 0


@pytest.mark.parametrize("sides,expected,reason", [
    (["LEFT"] * 3 + ["UNKNOWN"] * 2, "LEFT", "predominant_side"),
    (["LEFT"] * 2 + ["UNKNOWN"] * 3, "UNKNOWN", "insufficient_side_support"),
    (["LEFT"] * 2 + ["RIGHT"] * 2 + ["UNKNOWN"], "UNKNOWN", "no_dominant_side"),
])
def test_side_coverage_and_support_denominators(sides, expected, reason):
    result = preview(["FB"] * 5, sides).recent
    assert result.primary_side == expected and result.side_reason == reason
    detail = result.sides_by_role[0]
    assert detail.observations == 5 and detail.side_coverage == detail.known_sides / 5


def test_secondary_requires_two_votes_even_when_one_vote_has_twenty_five_percent():
    result = preview(["CM"] * 3 + ["FB"]).recent
    assert result.primary_position == "MC" and not result.secondary_positions
    assert shares(result.position_distribution)["LAT"] == (1, .25)


def test_primary_needs_three_observations_but_not_three_votes_for_the_winner():
    result = preview(["CM", "CM", "FB"]).recent
    assert result.primary_position == "MC" and result.meets_evidence_gates
    small = preview(["FB", "FB"]).recent
    assert small.primary_position is None and "insufficient_unique_fixtures" in small.reasons


def test_unknown_candidates_stay_in_the_denominator_and_are_not_split():
    entries = list(timeline(["CM"] * 4 + ["UNKNOWN"] * 2).entries)
    for i in (4, 5):
        entries[i] = replace(entries[i], observation=replace(
            entries[i].observation, candidates=frozenset({TacticalRole.W, TacticalRole.AM}),
            role_quality=Quality.AMBIGUOUS,
        ))
    result = PlayerPositionTimeline(CONTEXT, tuple(entries)).preview(as_of=AS_OF).recent
    assert result.observations == 6 and result.primary_position == "MC"
    assert shares(result.position_distribution)["UNKNOWN"] == (2, 2 / 6)
    assert "EXT" not in shares(result.position_distribution) and "MCO" not in shares(result.position_distribution)


def test_ambiguous_dm_cm_can_support_mc_without_supporting_a_tactical_role():
    entries = tuple(replace(evidence(i, "UNKNOWN"), observation=replace(
        evidence(i, "UNKNOWN").observation, candidates=frozenset({TacticalRole.DM, TacticalRole.CM}),
        sfa_position="MC", role_quality=Quality.AMBIGUOUS,
    )) for i in range(1, 4))
    result = PlayerPositionTimeline(CONTEXT, entries).preview(as_of=AS_OF).recent
    assert result.primary_position == "MC" and result.primary_role == "UNKNOWN" and result.primary_side == "UNKNOWN"


def test_recent_window_selects_known_starts_before_filtering_invalid_lineups():
    entries = tuple(evidence(i, "CM" if i <= 10 else "FB", missing="unsupported_formation" if i >= 18 else None)
                    for i in range(1, 21))
    result = PlayerPositionTimeline(CONTEXT, entries).preview(as_of=AS_OF, complete_start_inventory=True)
    assert result.recent.fixture_ids == tuple(range(11, 21))
    assert result.recent.observations == 7 and result.recent.excluded_starts == 3
    assert result.recent.start_coverage == .7 and result.recent.primary_position == "LAT"
    assert result.season.selected_starts == 20 and result.season.observations == 17
    assert result.season.primary_position is None
    assert result.recent.excluded_reasons == (("unsupported_formation", 3),)


def test_inventory_unknown_stays_unknown_even_when_every_cached_start_is_interpretable():
    result = preview(["FB"] * 7, ["LEFT"] * 7, complete=False).recent
    assert result.primary_position == "LAT" and result.start_coverage is None
    assert result.window_basis == "observed_starts" and not result.meets_evidence_gates
    assert result.reasons == ("unknown_start_coverage",)


def test_low_known_start_coverage_blocks_gate_without_changing_observed_shares():
    entries = tuple(evidence(i, missing="missing_lineup" if i > 3 else None) for i in range(1, 7))
    result = PlayerPositionTimeline(CONTEXT, entries).preview(as_of=AS_OF, complete_start_inventory=True).recent
    assert result.primary_position == "MC" and result.start_coverage == .5
    assert not result.meets_evidence_gates and "insufficient_start_coverage" in result.reasons


def test_date_cutoff_and_age_window_do_not_reclassify_history():
    original = timeline(["CM"] * 3 + ["FB"] * 3)
    earlier = original.preview(as_of="2026-09-03T23:59:00+00:00")
    assert earlier.season.fixture_ids == (1, 2, 3) and earlier.season.primary_position == "MC"
    later = original.preview(as_of="2027-10-18T12:00:00+00:00")
    assert later.recent.observations == 0 and later.recent.position_distribution == ()
    assert later.season.observations == 6 and later.season.freshness == "stale"
    assert not later.season.meets_evidence_gates


def test_empty_timeline_does_not_manufacture_zero_percent_measurements():
    result = PlayerPositionTimeline(CONTEXT).preview(as_of=AS_OF, complete_start_inventory=True)
    assert result.recent.position_distribution == () and result.recent.start_coverage is None
    assert result.recent.freshness == "missing" and result.recent.primary_position is None


def test_invalid_start_does_not_refresh_stale_position_or_role_proposals():
    old = tuple(replace(evidence(i), played_at=f"2026-01-{i:02d}T00:00:00+00:00", observation=replace(
        evidence(i).observation, played_at=f"2026-01-{i:02d}T00:00:00+00:00")) for i in range(1, 4))
    invalid = replace(evidence(4, missing="unsupported_formation"), played_at="2026-10-17T00:00:00+00:00")
    result = PlayerPositionTimeline(CONTEXT, old + (invalid,)).preview(as_of=AS_OF)
    assert result.recent.observations == 0
    assert all(p.state == "stale_evidence" for p in result.proposals)


def test_metadata_versions_and_identical_downloads_never_add_votes_or_false_conflicts():
    original = timeline(["CM"] * 3 + ["FB"] * 7)
    duplicate = replace(original.entries[-1], observation=replace(
        original.entries[-1].observation, reason="new_metadata", template_version="new-template-same-result"))
    repeated = original.update(duplicate).update(duplicate)
    before, after = original.preview(as_of=AS_OF), repeated.preview(as_of=AS_OF)
    assert before.recent.position_distribution == after.recent.position_distribution
    assert after.recent.observations == 10 and not after.recent.conflicting_fixture_ids
    assert before.proposals == after.proposals
    assert len(after.recent.evidence_versions) == 2


def test_real_conflict_is_excluded_until_explicit_replacement_with_history_retained():
    original = timeline(["CM"] * 8 + ["FB"] * 2)
    corrected = replace(evidence(1, "FB"), source_ref="correction:1")
    conflicting = original.update(corrected)
    profile = conflicting.preview(as_of=AS_OF, complete_start_inventory=True).recent
    assert profile.observations == 9 and profile.conflicting_fixture_ids == (1,)
    assert not profile.meets_evidence_gates
    fixed = conflicting.update(corrected, replace_fixture=True)
    assert len(fixed.superseded) == 1 and len(original.entries) == 10
    resolved = fixed.preview(as_of=AS_OF).recent
    assert resolved.observations == 10 and resolved.conflicting_fixture_ids == ()


def test_incremental_updates_and_out_of_order_backfill_equal_full_replay():
    entries = timeline(["CM"] * 3 + ["FB"] * 7).entries
    forward, backward = PlayerPositionTimeline(CONTEXT), PlayerPositionTimeline(CONTEXT)
    for item in entries:
        forward = forward.update(item)
    for item in reversed(entries):
        backward = backward.update(item)
    assert forward.preview(as_of=AS_OF) == backward.preview(as_of=AS_OF)
    assert forward.preview(as_of=AS_OF) == PlayerPositionTimeline(CONTEXT, entries).preview(as_of=AS_OF)
    assert forward.update(entries[-1]) is forward


def test_hysteresis_requires_two_distinct_qualifying_cuts_and_never_publishes():
    source = timeline(["CM"] * 3 + ["FB"] * 7)
    pending = source.preview(as_of="2026-09-09T23:00:00+00:00")
    proposed = source.preview(as_of=AS_OF)
    position_pending = next(p for p in pending.proposals if p.dimension == "position")
    position_final = next(p for p in proposed.proposals if p.dimension == "position")
    assert position_pending.state == "switch_pending" and position_pending.confirmation_fixture_ids == (9,)
    assert position_final.incumbent == "MC" and position_final.candidate == "LAT"
    assert position_final.state == "change_proposed" and position_final.confirmation_fixture_ids == (9, 10)
    assert proposed.recent.candidate_only
    assert source.preview(as_of="2026-10-19T12:00:00+00:00").proposals == proposed.proposals


def test_one_new_role_or_unknown_evidence_cannot_confirm_a_switch():
    one = preview(["CM"] * 7 + ["FB"])
    assert next(p for p in one.proposals if p.dimension == "position").candidate is None
    source = timeline(["CM"] * 3 + ["FB"] * 6 + ["UNKNOWN"])
    result = source.preview(as_of=AS_OF)
    assert next(p for p in result.proposals if p.dimension == "position").state == "stable_observed"


def test_side_switches_are_conditional_on_role_and_do_not_change_sfa_position():
    result = preview(["W"] * 10, ["RIGHT"] * 3 + ["LEFT"] * 7)
    side = next(p for p in result.proposals if p.dimension == "side")
    assert side.role_context == "W" and side.incumbent == "RIGHT" and side.candidate == "LEFT"
    assert side.state == "change_proposed"
    assert next(p for p in result.proposals if p.dimension == "position").candidate is None
    changed_role = preview(["W"] * 3 + ["FB"] * 7, ["RIGHT"] * 3 + ["LEFT"] * 7)
    assert all(p.candidate is None for p in changed_role.proposals if p.dimension == "side")


@pytest.mark.parametrize("changes", [{"external_id": 11}, {"team_id": 20}, {"season": "2025"},
                                    {"competition_id": 2}, {"team_kind": "national"}])
def test_contexts_are_never_mixed(changes):
    other = evidence(1, context=replace(CONTEXT, **changes))
    with pytest.raises(ValueError, match="contexts"):
        PlayerPositionTimeline(CONTEXT).update(other)


def test_timezone_equivalence_is_deduplicated_and_naive_dates_are_rejected():
    first = evidence(1)
    equivalent = replace(first, played_at="2026-08-31T21:00:00-03:00", observation=replace(
        first.observation, played_at="2026-08-31T21:00:00-03:00"))
    result = PlayerPositionTimeline(CONTEXT, (first, equivalent)).preview(as_of=AS_OF)
    assert result.season.observations == 1
    with pytest.raises(ValueError, match="timezone"):
        PlayerPositionTimeline(CONTEXT).preview(as_of="2026-10-18")


def test_invalid_observation_identity_and_conflicting_fixture_dates_are_rejected():
    start = evidence(1)
    with pytest.raises(ValueError, match="identity"):
        PlayerPositionTimeline(CONTEXT).update(replace(start, observation=replace(start.observation, external_id=999)))
    other = replace(evidence(2), fixture_id=1, observation=None)
    with pytest.raises(ValueError, match="Conflicting dates"):
        PlayerPositionTimeline(CONTEXT, (start, other)).preview(as_of=AS_OF)
