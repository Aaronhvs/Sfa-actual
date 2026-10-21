from __future__ import annotations

from itertools import permutations

import pytest

from sfa.domain.player_positions.resolution import (
    HabitualPositionAssignment,
    HabitualPositionCandidate,
    PlayerPositionResolver,
    PositionAssignmentScope,
    PositionResolutionQuery,
)
from sfa.domain.player_positions.value_objects import (
    PlayerStartEvidence,
    PositionObservation,
    PositionProfileContext,
    Quality,
    Side,
    TacticalRole,
)

GLOBAL = PositionAssignmentScope(None, None, None, frozenset({"team_id", "competition_id", "season"}))
CONTEXT = PositionAssignmentScope(10, 20, "2026", frozenset())


def assignment(**changes):
    return HabitualPositionAssignment(**{
        "assignment_id": 1, "revision_id": "revision-a", "player_id": 123, "position": "MCO",
        "scope": GLOBAL, "effective_from": "2026-10-18T12:00:00+00:00", "effective_until": None,
        "status": "accepted", "assertion_kind": "habitual_football_role", "evidence_ids": (987,),
        "source_ref": "curated:reference", "decision_policy": "explicit-current-reference-v1", **changes,
    })


def query(**changes):
    return PositionResolutionQuery(**{
        "player_id": 123, "effective_at": "2026-10-18T13:00:00+00:00", "team_id": 10,
        "competition_id": 20, "season": "2026", **changes,
    })


def candidate(**changes):
    return HabitualPositionCandidate(**{
        "evidence_id": 456, "player_id": 123, "position": "MC", "assertion_kind": "starting_slot",
        "source_ref": "fixture:433-cm", "scope": CONTEXT, "effective_from": "2026-10-18T12:00:00+00:00",
        "effective_until": None, "identity_verified": True, "specific_role_verified": True, **changes,
    })


def test_specific_accepted_position_is_preserved_despite_a_different_433_starting_slot():
    result = PlayerPositionResolver().resolve(query(), (assignment(),), (candidate(),), legacy_comparison="MCO")
    assert result.position == "MCO"
    assert result.status == "resolved"
    assert result.basis == "accepted_habitual_role"
    assert not result.publication_enabled
    assert result.evidence_ids == (987,)


@pytest.mark.parametrize("kind,verified,specific,review", [
    ("habitual_football_role", True, True, "open"),
    ("habitual_football_role", False, True, "none"),
    ("habitual_football_role", True, False, "none"),
    ("starting_slot", True, True, "none"),
])
def test_only_a_verified_specific_habitual_discrepancy_opens_review_without_overwrite(kind, verified, specific, review):
    incoming = candidate(assertion_kind=kind, identity_verified=verified, specific_role_verified=specific)
    result = PlayerPositionResolver().resolve(query(), (assignment(),), (incoming,))
    assert result.position == "MCO" and result.status == "resolved"
    assert result.review_status == review


@pytest.mark.parametrize("effective_at,expected", [
    ("2026-10-18T11:59:59+00:00", "unknown"), ("2026-10-18T12:00:00+00:00", "resolved"),
    ("2026-10-19T11:59:59+00:00", "resolved"), ("2026-10-19T12:00:00+00:00", "unknown"),
])
def test_intervals_are_half_open_and_current_confirmation_never_changes_prior_fixtures(effective_at, expected):
    resolved = PlayerPositionResolver().resolve(query(effective_at=effective_at), (
        assignment(effective_until="2026-10-19T12:00:00+00:00"),
    ))
    assert resolved.status == expected


@pytest.mark.parametrize("change", [{"player_id": 999}, {"team_id": 11}, {"competition_id": 21},
                                    {"season": "2025"}, {"team_id": None}])
def test_context_and_identity_constraints_cannot_be_bypassed(change):
    result = PlayerPositionResolver().resolve(query(**change), (assignment(scope=CONTEXT),))
    assert result.status == "unknown" and result.position is None


@pytest.mark.parametrize("status", ["draft", "legacy", "superseded"])
def test_unaccepted_records_and_legacy_labels_are_not_sporting_truth(status):
    result = PlayerPositionResolver().resolve(query(), (assignment(status=status),), legacy_comparison="MC")
    assert result.status == "unknown"
    assert result.position is None
    assert result.legacy_comparison == "MC"


def test_conflicting_accepted_global_and_contextual_roles_do_not_choose_latest_or_most_specific():
    records = (assignment(), assignment(assignment_id=2, revision_id="revision-z", position="MC", scope=CONTEXT))
    results = [PlayerPositionResolver().resolve(query(), tuple(order)) for order in permutations(records)]
    assert results[0] == results[1]
    assert results[0].position is None and results[0].status == "conflicted"
    assert results[0].review_status == "open"


def test_source_precision_can_preserve_detail_without_combining_unproven_role_side_pairs():
    records = (assignment(), assignment(assignment_id=2, revision_id="b", tactical_role=TacticalRole.AM),
               assignment(assignment_id=3, revision_id="c", side=Side.LEFT))
    result = PlayerPositionResolver().resolve(query(), records)
    assert result.position == "MCO"
    assert result.tactical_role == TacticalRole.AM
    assert result.side == Side.UNKNOWN  # AM + LEFT was never a joint accepted assertion.


def test_duplicate_inputs_do_not_inflate_resolution_and_reused_conflicting_identity_is_rejected():
    resolver = PlayerPositionResolver()
    single = resolver.resolve(query(), (assignment(),))
    assert single == resolver.resolve(query(), (assignment(), assignment()))
    with pytest.raises(ValueError, match="reuse"):
        resolver.resolve(query(), (assignment(), assignment(position="MC")))


def test_resolution_revision_uses_equivalent_instants_and_changes_with_evidence():
    resolver = PlayerPositionResolver()
    original = resolver.resolve(query(), (assignment(),))
    equivalent = resolver.resolve(query(effective_at="2026-10-18T10:00:00-03:00"), (
        assignment(effective_from="2026-10-18T09:00:00-03:00"),
    ))
    assert original.resolution_revision == equivalent.resolution_revision
    with_candidate = resolver.resolve(query(), (assignment(),), (candidate(),))
    assert original.resolution_revision != with_candidate.resolution_revision


@pytest.mark.parametrize("change", [
    {"assertion_kind": "starting_slot"}, {"evidence_ids": ()}, {"evidence_ids": (1, 1)},
    {"effective_until": "2026-10-18T12:00:00+00:00"}, {"source_ref": " "},
    {"position": "LAT", "tactical_role": TacticalRole.WM}, {"secondaries": ("MCO",)},
    {"player_id": 0}, {"assignment_id": True},
])
def test_invalid_or_semantically_inconsistent_accepted_assignments_cannot_be_constructed(change):
    with pytest.raises(ValueError):
        assignment(**change)


def test_scope_wildcards_and_historical_queries_require_explicit_meaning():
    with pytest.raises(ValueError, match="explicit"):
        PositionAssignmentScope(None, None, None, frozenset())
    with pytest.raises(ValueError):
        query(purpose="historical_habitual", team_id=None)
    with pytest.raises(ValueError):
        query(effective_at="2026-10-18T12:00:00")


def test_a_specific_candidate_alone_still_requires_an_acceptance_decision():
    result = PlayerPositionResolver().resolve(query(), (), (
        candidate(assertion_kind="habitual_football_role", position="DEL"),
    ))
    assert result.status == "unknown" and result.position is None
    assert result.basis == "candidate_only"
    assert not result.publication_enabled


def test_absence_of_evidence_is_not_presented_as_a_legacy_decision():
    result = PlayerPositionResolver().resolve(query(), ())
    assert result.status == "unknown" and result.position is None
    assert result.basis == "no_evidence"


def test_competing_specific_habitual_candidates_are_visible_to_triage_without_accepting_either():
    candidates = (candidate(assertion_kind="habitual_football_role", source_ref="profile:mc"),
                  candidate(evidence_id=457, assertion_kind="habitual_football_role", position="DEL",
                            source_ref="profile:del"))
    result = PlayerPositionResolver().resolve(query(), (), candidates)
    assert result.status == "unknown" and result.position is None
    assert result.basis == "candidate_only"
    assert result.review_status == "open"
    assert result.conflict_references == ("profile:del", "profile:mc")
    assert "incompatible_specific_habitual_candidates" in result.pending_reasons
from sfa.domain.player_positions.longitudinal import PlayerPositionTimeline


def observed_eighty_twenty():
    context = PositionProfileContext(9001, 1001, "2026", 20)
    entries = []
    for i in range(1, 11):
        played_at = f"2026-09-{i:02d}T12:00:00+00:00"
        role, side, position = (TacticalRole.CM, Side.RIGHT, "MC") if i <= 8 else (TacticalRole.FB, Side.LEFT, "LAT")
        observation = PositionObservation(
            9001, i, 1001, "2026", 20, played_at, role, side, frozenset({role}),
            Quality.SPECIFIC, Quality.SPECIFIC, position, "synthetic_starting_slot",
        )
        entries.append(PlayerStartEvidence(context, i, played_at, observation, source_ref=f"fixture:{i}"))
    return PlayerPositionTimeline(context, tuple(entries)).preview(
        as_of="2026-10-18T12:00:00+00:00", complete_start_inventory=True,
    ).recent


def test_eighty_twenty_observed_profile_is_preserved_without_overwriting_accepted_habitual_mco():
    profile = observed_eighty_twenty()
    result = PlayerPositionResolver().resolve(
        query(external_player_id=9001, external_team_id=1001), (assignment(),), observed_profile=profile,
    )
    assert result.position == "MCO"
    assert result.observed_profile.primary_position == "MC"
    assert result.observed_profile.secondary_positions[0].value == "LAT"
    assert result.observed_profile.secondary_positions[0].share == .2
    assert result.side == Side.UNKNOWN
    assert result.review_status == "none"


@pytest.mark.parametrize("change", [
    {"external_player_id": 9002}, {"external_team_id": 1002}, {"competition_id": 21},
    {"season": "2025"}, {"effective_at": "2026-10-18T11:59:00+00:00"},
])
def test_observed_profile_cannot_be_attached_to_wrong_identity_context_or_a_past_query(change):
    parameters = {"external_player_id": 9001, "external_team_id": 1001, **change}
    with pytest.raises(ValueError, match="crosswalk"):
        PlayerPositionResolver().resolve(query(**parameters), (), observed_profile=observed_eighty_twenty())


def test_fixture_allowlist_resolves_only_named_internal_fixtures():
    resolver = PlayerPositionResolver()
    restricted = assignment(scope=CONTEXT, applicable_fixture_ids=frozenset({101, 102}))
    for fixture_id in (101, 102):
        result = resolver.resolve(query(purpose="historical_habitual", fixture_id=fixture_id), (restricted,))
        assert result.status == "resolved" and result.position == "MCO"
    for purpose in ("current_habitual", "historical_habitual"):
        for fixture_id in (None, 103):
            result = resolver.resolve(query(purpose=purpose, fixture_id=fixture_id), (restricted,))
            assert result.status == "unknown" and result.assignment_ids == ()


@pytest.mark.parametrize("change", [
    {"player_id": 999}, {"team_id": 11}, {"competition_id": 21}, {"season": "2025"},
    {"effective_at": "2026-10-18T11:59:59+00:00"},
    {"effective_at": "2026-10-19T12:00:00+00:00"},
])
def test_fixture_membership_never_bypasses_identity_context_or_interval(change):
    restricted = assignment(scope=CONTEXT, applicable_fixture_ids=frozenset({101}),
                            effective_until="2026-10-19T12:00:00+00:00")
    result = PlayerPositionResolver().resolve(
        query(purpose="historical_habitual", fixture_id=101, **change), (restricted,),
    )
    assert result.status == "unknown" and result.position is None


@pytest.mark.parametrize("fixture_ids", [
    frozenset(), frozenset({0}), frozenset({-1}), frozenset({True}), frozenset({False}),
    frozenset({"101"}), frozenset({1.5}), {101}, [101], (101,),
])
def test_fixture_allowlists_require_immutable_nonempty_positive_internal_ids(fixture_ids):
    with pytest.raises(ValueError, match="Fixture allowlist"):
        assignment(applicable_fixture_ids=fixture_ids)


@pytest.mark.parametrize("fixture_id", [0, -1, True, False, "101", 1.5])
def test_query_fixture_id_must_be_a_positive_integer_when_supplied(fixture_id):
    with pytest.raises(ValueError, match="positive integer IDs"):
        query(fixture_id=fixture_id)


def test_unrestricted_legacy_assignments_do_not_require_a_fixture_id():
    resolver = PlayerPositionResolver()
    for purpose in ("current_habitual", "historical_habitual"):
        result = resolver.resolve(query(purpose=purpose), (assignment(),))
        assert result.status == "resolved" and result.position == "MCO"


def test_allowlist_revision_is_deterministic_and_records_the_exact_fixture_scope():
    resolver = PlayerPositionResolver()
    first = assignment(applicable_fixture_ids=frozenset([101, 102]))
    equivalent = assignment(applicable_fixture_ids=frozenset([102, 101]))
    selected = query(purpose="historical_habitual", fixture_id=101)
    result = resolver.resolve(selected, (first,))
    assert result == resolver.resolve(selected, (equivalent,))
    narrower = resolver.resolve(selected, (assignment(applicable_fixture_ids=frozenset({101})),))
    other_fixture = resolver.resolve(query(purpose="historical_habitual", fixture_id=102), (first,))
    assert result.resolution_revision != narrower.resolution_revision
    assert result.resolution_revision != other_fixture.resolution_revision
    second = assignment(assignment_id=2, revision_id="revision-b", applicable_fixture_ids=frozenset({101}))
    assert resolver.resolve(selected, (first, second)) == resolver.resolve(selected, (second, first))


def test_current_confirmation_and_fixture_corrections_do_not_reclassify_an_unlisted_bench_fixture():
    resolver = PlayerPositionResolver()
    historical = assignment(
        scope=CONTEXT, position="DEL", applicable_fixture_ids=frozenset({101, 102}),
        effective_from="2026-08-23T00:00:00+00:00", effective_until="2026-09-20T00:00:00+00:00",
    )
    current = assignment(
        assignment_id=2, revision_id="current-confirmation", scope=CONTEXT, position="DEL",
        effective_from="2026-10-19T12:00:00+00:00",
    )
    records = (historical, current)
    corrected = resolver.resolve(query(purpose="historical_habitual", fixture_id=101,
                                       effective_at="2026-08-23T12:00:00+00:00"), records)
    assert corrected.position == "DEL" and corrected.assignment_ids == (1,)
    bench = resolver.resolve(query(purpose="historical_habitual", fixture_id=103,
                                   effective_at="2026-10-17T12:00:00+00:00"), records, legacy_comparison="EXT")
    assert bench.status == "unknown" and bench.position is None and bench.legacy_comparison == "EXT"
    now = resolver.resolve(query(effective_at="2026-10-19T12:00:00+00:00"), records)
    assert now.position == "DEL" and now.assignment_ids == (2,)
    assert not now.publication_enabled and not corrected.publication_enabled
