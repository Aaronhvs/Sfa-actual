from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from sfa.domain.matchday_mvp import MvpPerformance, group_rounds, select_mvps
from sfa.domain.ports import TournamentFixtureDTO, TournamentTeamDTO

NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)
HOME = TournamentTeamDTO(1, 529, "Barcelona")
AWAY = TournamentTeamDTO(2, 541, "Real Madrid")


def fixture(fid=1, day=1, stage="regular", status="FT", **kwargs):
    return replace(TournamentFixtureDTO(fid, 1000 + fid, 1, stage, day, NOW + timedelta(days=fid),
                                       status, 1, 2, HOME, AWAY), **kwargs)


def performance(pid=1, fid=1, points="1000", **kwargs):
    return replace(MvpPerformance(pid, fid, f"Player {pid}", None, 1, Decimal(points), 0, 0), **kwargs)


def test_single_match_not_sum_of_player_round_performances_and_numeric_order():
    fixtures = [fixture(3, 10), fixture(1, 2), fixture(2, 2)]
    performances = [performance(1, 1, "900"), performance(1, 2, "900"), performance(2, 1, "1200"),
                    performance(3, 3, "-5")]
    items = select_mvps(group_rounds("La Liga", fixtures), performances, {2: "MC"})
    assert [item.round_key for item in items] == ["matchday-2", "matchday-10"]
    assert items[0].player.id == 2 and items[0].sfa_pts == 1200
    assert items[0].player.position == "MC"
    assert items[1].sfa_pts == -5  # No season-ranking eligibility filters on a single performance.


@pytest.mark.parametrize("status,pending", [("FT", 0), ("AET", 0), ("PEN", 0), ("NS", 1), ("PST", 1),
                                          ("CANC", 1), ("AWD", 1), ("2H", 1)])
def test_completion_and_only_finished_candidates(status, pending):
    rounds = group_rounds("La Liga", [fixture(1), fixture(2, status=status)])
    item, = select_mvps(rounds, [performance(1), performance(2, 2, "2000")], {})
    assert item.complete is (pending == 0) and item.pending_fixtures == pending
    assert item.player.id == (1 if pending else 2)


def test_points_tie_breaks_by_contributions_then_player_id_then_fixture_external_id():
    rounds = group_rounds("La Liga", [fixture(1), fixture(2)])
    candidates = [performance(1, goals=1), performance(2, assists=2), performance(3, goals=2)]
    assert select_mvps(rounds, candidates, {})[0].player.id == 2
    candidates.append(performance(2, 2, assists=2))
    assert select_mvps(rounds, list(reversed(candidates)), {})[0].fixture.external_id == 1001


@pytest.mark.parametrize("diff,expected", [(-1, ("big_rival", "behind", "away")),
                                         (0, ("big_rival", "level", "away")),
                                         (1, ("big_rival", "away")), (None, ("big_rival", "away"))])
def test_fixture_and_action_reasons(diff, expected):
    rounds = group_rounds("La Liga", [fixture()])
    item, = select_mvps(rounds, [performance(team_id=2, rival_strength=50, decisive_score_diff=diff)], {})
    assert item.reasons == expected
    assert item.fixture.player_side == "away" and item.player.team == "Real Madrid"


def test_missing_context_and_strength_under_fifty_do_not_invent_reasons():
    rounds = group_rounds("La Liga", [fixture()])
    assert select_mvps(rounds, [performance(rival_strength=49.99)], {})[0].reasons == ()
    assert select_mvps(rounds, [performance(team_id=999)], {}) == ()
    assert select_mvps(rounds, [], {}) == ()


def test_knockout_legs_ignore_polluted_matchday_and_include_scheduled_second_legs():
    first, second = fixture(1, 16, "round_of_16"), fixture(2, 16, "round_of_16", "NS",
                                                               home_team=AWAY, away_team=HOME)
    groups = group_rounds("UEFA Champions League", [second, first])
    assert [g.key for g in groups] == ["round_of_16-leg-1", "round_of_16-leg-2"]
    assert [g.label for g in groups] == ["Octavos · ida", "Octavos · vuelta"]
    assert all(g.matchday is None for g in groups)
    assert select_mvps(groups, [performance()], {})[0].reasons == ("knockout",)
    assert group_rounds("Champions League", [first]) == ()
    assert group_rounds("Champions League", [first, replace(second, home_team=HOME, away_team=AWAY)]) == ()
    assert group_rounds("Champions League", [first, replace(second, played_at=first.played_at)]) == ()
    assert group_rounds("Champions League", [first, second, fixture(3, 16, "round_of_16")]) == ()


def test_explicit_leg_and_known_single_rounds_and_mislabeled_finals():
    group, = group_rounds("Europa League", [fixture(stage="round_of_16-leg-1")])
    assert group.key == "round_of_16-leg-1"
    assert group_rounds("Coppa Italia", [fixture(day=16, stage="round_of_16")])[0].key == "round_of_16-single"
    assert group_rounds("UEFA Super Cup", [fixture(day=None, stage="final")])[0].key == "final-single"
    assert group_rounds("Copa del Rey", [fixture(stage="final"), fixture(2, stage="final")]) == ()
    assert group_rounds("DFB-Pokal", [fixture(day=64)]) == ()


def test_league_phase_excludes_qualifiers_and_old_postponement_does_not_become_latest():
    matches = [fixture(1, 3, "group"), fixture(2, None, "regular"), fixture(3, 1, "group")]
    groups = group_rounds("Conference League", matches)
    assert [g.matchday for g in groups] == [1, 3]
    assert groups[-1].fixtures[0].id == 1
