from dataclasses import replace

import pytest

from sfa.domain.event_integrity import Appearance, FixtureSnapshot, StoredAction, normalize_context_plan, prepare_plan


def source(events, fixture=123):
    return {"parameters": {"fixture": str(fixture)}, "errors": [], "results": len(events), "response": events}


def goal(actor=278, minute=29, detail="Penalty", assistant=None, team=541, extra=None):
    return {
        "time": {"elapsed": minute, "extra": extra},
        "team": {"id": team},
        "player": {"id": actor, "name": "Different abbreviated name"},
        "assist": {"id": assistant, "name": None},
        "type": "Goal",
        "detail": detail,
    }


def snapshot(goals=1, assists=0, actions=(), actors=None, home=1, away=0):
    actors = actors or (Appearance(888, 278, 2, 541, goals, assists, 90),)
    return FixtureSnapshot(1, 123, 10, "2025", 541, 81, home, away, actors, actions, "baseline")


def test_mbappe_penalties_are_recovered_by_provider_id():
    plan = prepare_plan(snapshot(goals=2, home=2), source([goal(), goal(minute=81)]))
    assert not plan.pending
    assert len(plan.changes) == 2
    assert [c.after.player_id for c in plan.changes] == [888, 888]
    assert [c.after.score_before for c in plan.changes] == ["0:0", "1:0"]
    assert all(c.after.event_type == "GOAL_PENALTY" for c in plan.changes)


def test_garcia_wrong_actor_is_corrected_preserving_event_id():
    old = StoredAction(45, 804, 2, 15, "GOAL", "0:0", 0, False)
    real = Appearance(2039, 146751, 2, 541, 1, 0, 90)
    wrong = Appearance(804, 46658, 2, 541, 0, 0, 30)
    plan = prepare_plan(snapshot(actions=(old,), actors=(real, wrong)), source([goal(146751, 15, "Normal Goal")]))
    assert not plan.pending
    assert len(plan.changes) == 1
    assert plan.changes[0].before.event_id == 45
    assert plan.changes[0].after.player_id == 2039


def test_assist_id_does_not_require_a_name():
    actors = (Appearance(888, 278, 2, 541, 1, 0, 90), Appearance(99, 909, 2, 541, 0, 1, 45))
    plan = prepare_plan(snapshot(actors=actors), source([goal(assistant=909)]))
    assert not plan.pending
    assert {r.after.event_type for r in plan.changes} == {"GOAL_PENALTY", "ASSIST"}


@pytest.mark.parametrize(
    "payload,reason",
    [
        (source([goal()], fixture=999), "mismatched fixture identity"),
        ({**source([goal()]), "errors": {"rateLimit": "failed"}}, "Provider errors"),
        ({**source([goal()]), "results": 2}, "Incomplete provider envelope"),
        (source([goal(actor=None)]), "unresolved_actor_identity"),
        (source([goal(team=999)]), "does not belong to fixture"),
        (source([goal(detail="Goal Disallowed")]), "unrecognized_goal_detail"),
        (source([]), "timeline_final_score_conflict"),
    ],
)
def test_unverifiable_evidence_never_produces_writes(payload, reason):
    plan = prepare_plan(snapshot(), payload)
    assert any(reason in item for item in (*plan.pending, *plan.warnings))
    assert not plan.changes


def test_stats_disagreement_is_pending_not_a_synthetic_goal():
    plan = prepare_plan(snapshot(goals=2), source([goal()]))
    assert plan.warnings == ("provider_goal_counts_conflict:888",)
    assert not plan.changes


def test_shootout_and_missed_penalty_are_not_ordinary_goals():
    plan = prepare_plan(
        snapshot(goals=0, home=0),
        source(
            [
                goal(minute=50, detail="Missed Penalty"),
                goal(minute=120, extra=1),
            ]
        ),
    )
    assert not plan.pending
    assert len(plan.changes) == 1
    assert plan.changes[0].after.event_type == "GOAL_SHOOTOUT"
    assert plan.changes[0].after.score_diff == 0


def test_own_goal_changes_score_but_does_not_credit_an_attacker():
    plan = prepare_plan(snapshot(goals=0), source([goal(actor=None, detail="Own Goal")]))
    assert not plan.pending
    assert not plan.changes


def test_two_goals_in_same_minute_are_distinct_occurrences():
    plan = prepare_plan(snapshot(goals=2, home=2), source([goal(), goal()]))
    assert not plan.pending
    assert len(plan.changes) == 2
    assert plan.changes[0].after.source_sequence != plan.changes[1].after.source_sequence
    assert plan.changes[0].after.score_before != plan.changes[1].after.score_before


def test_ambiguous_existing_occurrences_are_pending():
    old = StoredAction(45, 888, 2, 29, "GOAL_PENALTY", "0:0", 0, False)
    plan = prepare_plan(snapshot(actions=(old, replace(old, event_id=46))), source([goal()]))
    assert plan.pending == ("ambiguous_occurrence_correspondence",)


def test_verified_existing_action_is_unchanged_and_replay_is_deterministic():
    old = StoredAction(45, 888, 2, 29, "GOAL_PENALTY", "0:0", 0, False)
    first = prepare_plan(snapshot(actions=(old,)), source([goal()]))
    second = prepare_plan(snapshot(actions=(old,)), source([goal()]))
    assert first == second
    assert not first.changes
    assert not first.pending


def test_wrong_extra_event_is_retired_from_complete_source():
    old = StoredAction(45, 888, 2, 29, "GOAL", "0:0", 0, False)
    plan = prepare_plan(snapshot(goals=0, home=0, actions=(old,)), source([]))
    assert not plan.pending
    assert plan.changes[0].before == old
    assert plan.changes[0].after is None


def test_missing_stats_remains_explicitly_pending():
    plan = prepare_plan(replace(snapshot(), appearances=()), source([goal()]))
    assert plan.pending == ("missing_player_stats",)


def test_existing_appearance_restores_missing_stats_event_without_new_statistics():
    data = replace(snapshot(goals=0, home=0), missing_stats_player_ids=(888,))
    plan = prepare_plan(data, source([]))
    assert not plan.pending
    assert len(plan.changes) == 1
    assert plan.changes[0].after.event_type == "STATS"
    assert plan.changes[0].after.score_diff is None


def player_source(rows):
    teams = {}
    for actor in rows:
        teams.setdefault(actor.team_external_id, []).append(
            {
                "player": {"id": actor.external_id},
                "statistics": [
                    {"goals": {"total": actor.goals, "assists": actor.assists}, "games": {"minutes": actor.minutes}}
                ],
            }
        )
    return {
        "parameters": {"fixture": "123"},
        "errors": [],
        "response": [{"team": {"id": team}, "players": players} for team, players in teams.items()],
    }


def test_counter_changes_require_agreement_between_both_fresh_provider_endpoints():
    before = snapshot(goals=1, home=2)
    fresh = replace(before.appearances[0], goals=2)
    plan = prepare_plan(before, source([goal(), goal(minute=81)]), player_source([fresh]))
    assert not plan.pending
    assert not plan.warnings
    assert len(plan.changes) == 2
    assert plan.appearance_changes[0].before.goals == 1
    assert plan.appearance_changes[0].after.goals == 2


def test_conflicting_assist_does_not_block_other_goals_or_dembele_assist():
    suarez = Appearance(1, 47237, 2, 541, 2, 0, 90)
    trincao = Appearance(2, 41112, 2, 541, 0, 0, 90)
    vagiannidis = Appearance(3, 135839, 2, 541, 0, 1, 45)
    dembele = Appearance(4, 153, 9, 81, 0, 1, 60)
    kvaratskhelia = Appearance(5, 483, 9, 81, 1, 0, 30)
    actors = (suarez, trincao, vagiannidis, dembele, kvaratskhelia)
    disputed = StoredAction(90, 3, 2, 90, "ASSIST", "1:1", 0, False)
    data = snapshot(actors=actors, actions=(disputed,), home=2, away=1)
    events = source(
        [goal(47237, 74, "Normal Goal"), goal(483, 79, "Normal Goal", 153, 81), goal(47237, 90, "Normal Goal", 41112)]
    )
    plan = prepare_plan(data, events, player_source(actors))
    assert not plan.pending
    assert len(plan.warnings) == 2
    assert {r.after.player_id for r in plan.changes} == {1, 4, 5}
    assert all(r.before is None for r in plan.changes)
    assert sum(r.after.event_type == "ASSIST" for r in plan.changes) == 1
    assert not plan.appearance_changes


def test_unresolved_assist_preserves_existing_same_goal_assistant():
    actor = Appearance(888, 278, 2, 541, 1, 0, 90)
    assistant = Appearance(99, 909, 2, 541, 0, 1, 90)
    old = StoredAction(2, 99, 2, 29, "ASSIST", "0:0", 0, False)
    event = goal()
    event["assist"] = {"id": None, "name": "Unknown assistant"}
    plan = prepare_plan(snapshot(actors=(actor, assistant), actions=(old,)), source([event]))
    assert not plan.pending
    assert plan.warnings
    assert len(plan.changes) == 1
    assert plan.changes[0].after.player_id == 888
    assert plan.changes[0].before is None


def test_missing_appearance_minutes_are_restored_only_from_verified_source_team():
    actor = Appearance(888, 278, 2, 541, 1, 0, 0)
    current = snapshot(actors=(actor,))
    plan = prepare_plan(current, source([goal()]), player_source([replace(actor, minutes=20)]))
    assert not plan.pending
    assert not plan.warnings
    assert plan.appearance_changes[0].after.minutes == 20
    assert len(plan.changes) == 1


def test_invalid_statistics_source_blocks_all_counter_updates():
    data = player_source(snapshot().appearances)
    data["parameters"]["fixture"] = "999"
    plan = prepare_plan(snapshot(), source([goal()]), data)
    assert plan.pending
    assert not plan.changes
    assert not plan.appearance_changes


def test_unknown_source_actor_does_not_authorize_zeroing_a_counter():
    actor = Appearance(888, 278, 2, 541, 1, 0, 90)
    assistant = Appearance(99, 909, 2, 541, 0, 1, 90)
    old = StoredAction(2, 99, 2, 29, "ASSIST", "0:0", 0, False)
    event = goal()
    event["assist"] = {"id": None, "name": "Unknown assistant"}
    plan = prepare_plan(
        snapshot(actors=(actor, assistant), actions=(old,)),
        source([event]),
        player_source([actor, replace(assistant, assists=0)]),
    )
    assert not plan.appearance_changes
    assert len(plan.changes) == 1
    assert plan.changes[0].after.player_id == 888


def test_retained_context_uses_fixture_teams_for_side_and_score_difference():
    old = StoredAction(45, 888, 2, 29, "GOAL", "0:1", 1, True)
    stats = StoredAction(46, 888, 2, 90, "STATS", None, None, True)
    data = replace(snapshot(actions=(old,)), stats_actions=(stats,), home_team_id=2, away_team_id=9)
    plan = normalize_context_plan(data)
    assert len(plan.changes) == 2
    assert all(not change.after.is_away for change in plan.changes)
    assert plan.changes[0].after.score_diff == -1
    assert plan.changes[1].after.score_diff is None


def fixture_source(status="PEN"):
    return {
        "parameters": {"id": "123"},
        "errors": [],
        "response": [
            {
                "fixture": {"id": 123, "status": {"short": status, "elapsed": 120}},
                "teams": {"home": {"id": 541}, "away": {"id": 81}},
                "goals": {"home": 0, "away": 0},
                "score": {"fulltime": {"home": 0, "away": 0}, "extratime": {"home": None, "away": None}},
            }
        ],
    }


def test_penalty_match_summary_without_extra_time_is_normalized_from_two_sources():
    home = Appearance(1, 278, 2, 541, 1, 0, 120)
    away = Appearance(2, 153, 9, 81, 1, 0, 120)
    data = replace(snapshot(actors=(home, away), home=0, away=0), status="PEN")
    events = source([goal(278, 100, "Normal Goal"), goal(153, 110, "Normal Goal", team=81)])
    plan = prepare_plan(data, events, player_source([home, away]), fixture_source())
    assert not plan.pending
    assert plan.fixture_goals == (1, 1)
    assert len(plan.changes) == 2


def test_extra_time_score_requires_player_statistics_confirmation():
    home = Appearance(1, 278, 2, 541, 0, 0, 120)
    away = Appearance(2, 153, 9, 81, 0, 0, 120)
    data = replace(snapshot(actors=(home, away), home=0, away=0), status="PEN")
    events = source([goal(278, 100, "Normal Goal"), goal(153, 110, "Normal Goal", team=81)])
    plan = prepare_plan(data, events, player_source([home, away]), fixture_source())
    assert plan.pending == ("timeline_final_score_conflict",)
    assert not plan.fixture_goals
    assert not plan.changes


def test_stoppage_time_is_not_reclassified_as_extra_time():
    home = Appearance(1, 278, 2, 541, 1, 0, 120)
    away = Appearance(2, 153, 9, 81, 1, 0, 120)
    data = replace(snapshot(actors=(home, away), home=0, away=0), status="PEN")
    events = source([goal(278, 90, "Normal Goal", extra=12), goal(153, 90, "Normal Goal", team=81, extra=15)])
    plan = prepare_plan(data, events, player_source([home, away]), fixture_source())
    assert plan.pending == ("timeline_final_score_conflict",)


def test_duplicate_irrelevant_player_source_rows_do_not_block_verified_goals():
    data = player_source(snapshot().appearances)
    data["response"][0]["players"].extend(
        [
            {"player": {"id": 999}, "statistics": [{}]},
            {"player": {"id": 999}, "statistics": [{}]},
        ]
    )
    plan = prepare_plan(snapshot(), source([goal()]), data)
    assert not plan.pending
    assert "ambiguous_player_source:999" in plan.warnings
    assert len(plan.changes) == 1


def test_empty_player_response_with_provider_error_is_not_valid_evidence():
    data = player_source([])
    data["errors"] = {"requests": "Limit reached"}
    plan = prepare_plan(snapshot(), source([goal()]), data)
    assert plan.pending
    assert not plan.changes


def test_own_goal_extra_time_beneficiary_is_not_credited_as_attacker_goal():
    home = Appearance(1, 278, 2, 541, 0, 0, 120)
    away = Appearance(2, 153, 9, 81, 1, 0, 120)
    data = replace(snapshot(actors=(home, away), home=0, away=0), status="PEN")
    events = source([goal(153, 100, "Own Goal"), goal(153, 110, "Normal Goal", team=81)])
    plan = prepare_plan(data, events, player_source([home, away]), fixture_source())
    assert not plan.pending
    assert plan.fixture_goals == (1, 1)
    assert len(plan.changes) == 1
    assert plan.changes[0].after.player_id == 2
