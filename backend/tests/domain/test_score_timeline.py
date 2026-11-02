from __future__ import annotations

from dataclasses import replace

import pytest

from sfa.domain.ingestion_ports import FixtureEventRawDTO
from sfa.domain.scoring.services import ScoreTimeline, ShootoutDecider


@pytest.mark.parametrize("detail", ["Penalty", "Missed Penalty"])
def test_explicit_shootout_comment_is_not_a_match_goal(detail):
    from sfa.domain.scoring.services import is_shootout_attempt_event

    ordinary = _goal(40, 1)
    kick = replace(_goal(91, 2, detail=detail), comments="Penalty Shootout")
    timeline = ScoreTimeline.build(1, 2, [ordinary, kick])
    assert is_shootout_attempt_event(kick)
    assert timeline.transition_for(ordinary).home_after == 1
    with pytest.raises(ValueError, match="not a scored regulation goal"):
        timeline.transition_for(kick)


def test_extra_time_penalty_without_shootout_evidence_stays_a_match_goal():
    from sfa.domain.scoring.services import is_shootout_attempt_event

    kick = _goal(95, 1, detail="Penalty")
    assert not is_shootout_attempt_event(kick)
    assert ScoreTimeline.build(1, 2, [kick]).transition_for(kick).home_after == 1


def _goal(
    minute: int,
    team_external_id: int,
    detail: str = "Normal Goal",
    source_sequence: int = 0,
    extra_minute: int = 0,
) -> FixtureEventRawDTO:
    return FixtureEventRawDTO(
        type="Goal",
        detail=detail,
        player_name="Player",
        assist_name=None,
        team_external_id=team_external_id,
        minute=minute,
        extra_minute=extra_minute,
        source_sequence=source_sequence,
    )


def test_own_goal_credits_api_football_beneficiary_team() -> None:
    own_goal = _goal(7, 2384, detail="Own Goal", source_sequence=0)
    mauricio_goal = _goal(73, 2380, source_sequence=3)
    events = [
        own_goal,
        _goal(31, 2384, source_sequence=1),
        _goal(45, 2384, source_sequence=2),
        mauricio_goal,
        _goal(90, 2384, source_sequence=4),
    ]

    timeline = ScoreTimeline.build(2384, 2380, events)

    own_goal_transition = timeline.transition_for(own_goal)
    assert (own_goal_transition.home_after, own_goal_transition.away_after) == (1, 0)

    mauricio_transition = timeline.transition_for(mauricio_goal)
    assert (mauricio_transition.home_before, mauricio_transition.away_before) == (3, 0)
    assert mauricio_transition.score_diff_before(2380, 2384) == -3
    assert (mauricio_transition.home_after, mauricio_transition.away_after) == (3, 1)


def test_shootout_decider_marks_the_closing_penalty() -> None:
    events = [
        _goal(120, 1, detail="Penalty", source_sequence=0, extra_minute=1),
        _goal(120, 2, detail="Missed Penalty", source_sequence=1, extra_minute=1),
        _goal(120, 1, detail="Penalty", source_sequence=2, extra_minute=2),
        _goal(120, 2, detail="Penalty", source_sequence=3, extra_minute=2),
        _goal(120, 1, detail="Penalty", source_sequence=4, extra_minute=3),
        _goal(120, 2, detail="Missed Penalty", source_sequence=5, extra_minute=3),
        _goal(120, 1, detail="Missed Penalty", source_sequence=6, extra_minute=4),
        _goal(120, 2, detail="Penalty", source_sequence=7, extra_minute=4),
        _goal(120, 1, detail="Penalty", source_sequence=8, extra_minute=5),
    ]

    decisive = ShootoutDecider.decisive_event_ids(1, 2, events)

    assert decisive == {id(events[-1])}


def test_shootout_decider_accepts_provider_detail_variants() -> None:
    events = [
        _goal(120, 1, detail="Penalty Shootout", source_sequence=0, extra_minute=1),
        _goal(120, 2, detail="Missed Penalty Shootout", source_sequence=1, extra_minute=1),
        _goal(120, 1, detail="Penalty Shootout", source_sequence=2, extra_minute=2),
        _goal(120, 2, detail="Missed Penalty Shootout", source_sequence=3, extra_minute=2),
        _goal(120, 1, detail="Penalty Shootout", source_sequence=4, extra_minute=3),
        _goal(120, 2, detail="Missed Penalty Shootout", source_sequence=5, extra_minute=3),
    ]

    decisive = ShootoutDecider.decisive_event_ids(1, 2, events)

    assert decisive == {id(events[-1])}


def test_shootout_decider_does_not_close_recoverable_three_nil_lead() -> None:
    events = [
        _goal(120, 1, detail="Penalty Shootout", source_sequence=0, extra_minute=1),
        _goal(120, 2, detail="Missed Penalty Shootout", source_sequence=1, extra_minute=1),
        _goal(120, 1, detail="Penalty Shootout", source_sequence=2, extra_minute=2),
        _goal(120, 2, detail="Missed Penalty Shootout", source_sequence=3, extra_minute=2),
        _goal(120, 1, detail="Penalty Shootout", source_sequence=4, extra_minute=3),
    ]

    decisive = ShootoutDecider.decisive_event_ids(1, 2, events)

    assert decisive == set()


def test_shootout_decider_marks_sudden_death_miss_as_decisive() -> None:
    events = [
        _goal(121, 1, detail="Penalty", source_sequence=0),
        _goal(121, 2, detail="Penalty", source_sequence=1),
        _goal(122, 1, detail="Penalty", source_sequence=2),
        _goal(122, 2, detail="Penalty", source_sequence=3),
        _goal(123, 1, detail="Penalty", source_sequence=4),
        _goal(123, 2, detail="Penalty", source_sequence=5),
        _goal(124, 1, detail="Penalty", source_sequence=6),
        _goal(124, 2, detail="Penalty", source_sequence=7),
        _goal(125, 1, detail="Penalty", source_sequence=8),
        _goal(125, 2, detail="Penalty", source_sequence=9),
        _goal(126, 1, detail="Penalty", source_sequence=10),
        _goal(126, 2, detail="Missed Penalty", source_sequence=11),
    ]

    decisive = ShootoutDecider.decisive_event_ids(1, 2, events)

    assert decisive == {id(events[-1])}
