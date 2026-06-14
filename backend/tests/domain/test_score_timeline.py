from __future__ import annotations

from sfa.domain.ingestion_ports import FixtureEventRawDTO
from sfa.domain.scoring.services import ScoreTimeline


def _goal(
    minute: int,
    team_external_id: int,
    detail: str = "Normal Goal",
    source_sequence: int = 0,
) -> FixtureEventRawDTO:
    return FixtureEventRawDTO(
        type="Goal",
        detail=detail,
        player_name="Player",
        assist_name=None,
        team_external_id=team_external_id,
        minute=minute,
        extra_minute=0,
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
