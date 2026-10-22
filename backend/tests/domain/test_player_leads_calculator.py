import pytest

from sfa.domain.player_leads import (
    LeadGroup,
    LeadGroupKind,
    LeadMetric,
    LeadSample,
    PlayerLeadsCalculator,
)
from sfa.domain.player_leads.policy import CATALOG
from sfa.domain.season_scope import ScopeKind

CALC = PlayerLeadsCalculator()
CONVERSION = CATALOG[0]
GOALS = CATALOG[1]
BIG = CATALOG[-1]


def sample(player_id, *, competition_id=140, name="La Liga", kind="club", position="EXT", season="2025",
           minutes=900, **counters):
    return LeadSample(player_id, season, competition_id, name, kind, position, minutes=minutes, **counters)


def league(count=12, start=100, **kwargs):
    """Filler players that qualify for goals_per90 with a modest rate."""
    return [sample(start + index, goals=3, np_goals=3, np_shots_on=12, **kwargs) for index in range(count)]


def calculate(samples, *, scope_kind=ScopeKind.AWARD_PERIOD, positions=None, sfa=True):
    return CALC.calculate(scope_key="season-2025", scope_kind=scope_kind, samples=samples,
                          scope_positions=positions or {}, rules_version_id=4 if sfa else None,
                          sfa_available=sfa)


class TestGroups:
    def test_single_competition_award_period_has_no_scope_group(self):
        groups = CALC.build_groups(league(), {}, tournament=False)
        kinds = {group.kind for group, _ in groups}
        assert kinds == {LeadGroupKind.COMPETITION, LeadGroupKind.COMPETITION_POSITION}

    def test_two_club_competitions_add_scope_groups_without_national_teams(self):
        samples = (league(competition_id=140) + league(competition_id=2, name="Champions League")
                   + league(competition_id=350, name="World Cup", kind="national_team"))
        groups = CALC.build_groups(samples, {100: "DEL"}, tournament=False)
        scope = [members for group, members in groups if group.kind == LeadGroupKind.SCOPE]
        assert len(scope) == 1
        merged = {member.player_id: member for member in scope[0]}
        assert merged[100].minutes == 1800  # league + Champions, never the World Cup
        assert merged[100].position == "DEL"
        assert any(group.kind == LeadGroupKind.SCOPE_POSITION and group.position == "DEL" for group, _ in groups)

    def test_tournament_has_no_scope_group(self):
        groups = CALC.build_groups(league(competition_id=350, kind="national_team"), {}, tournament=True)
        assert all(not group.kind.name.startswith("SCOPE") for group, _ in groups)

    def test_short_competition_is_ignored(self):
        groups = CALC.build_groups(league(minutes=180, competition_id=143), {}, tournament=False)
        assert groups == []

    def test_players_without_position_skip_position_groups(self):
        groups = CALC.build_groups(league(position=None), {}, tournament=False)
        assert [group.kind for group, _ in groups] == [LeadGroupKind.COMPETITION]


class TestRanking:
    def test_volume_leader_wins_conversion_and_tiny_sample_does_not_qualify(self):
        star = sample(1, goals=14, np_goals=14, np_shots_on=19, shots_on=19)
        perfect = sample(2, goals=5, np_goals=5, np_shots_on=5, shots_on=5)
        snapshot = calculate([star, perfect, *league()])
        conversion = [lead for lead in snapshot.for_player(1) if lead.metric == LeadMetric.SHOT_CONVERSION]
        assert conversion and conversion[0].rank == 1
        assert conversion[0].numerator == 14 and conversion[0].denominator == 19
        assert conversion[0].value == pytest.approx(14 / 19)
        assert all(lead.metric != LeadMetric.SHOT_CONVERSION for lead in snapshot.for_player(2))

    def test_minimum_minutes_is_set_by_the_whole_population(self):
        # The minutes leader has no goals (does not qualify) but still fixes the 30 % threshold.
        workhorse = sample(1, minutes=3000)
        cameo = sample(2, minutes=600, goals=9)  # needs 900' (30 % of 3000)
        snapshot = calculate([workhorse, cameo, *league(minutes=1000)])
        assert all(lead.metric != LeadMetric.GOALS_PER90 for lead in snapshot.for_player(2))
        lead = next(lead for lead in snapshot.for_player(100) if lead.metric == LeadMetric.GOALS_PER90)
        assert lead.threshold.min_minutes == 900

    def test_small_groups_produce_no_leads(self):
        rank = CALC.rank_group(GOALS, _group(), league(count=9), tournament=False)
        assert rank == []
        position_group = _group(LeadGroupKind.COMPETITION_POSITION, "EXT")
        assert CALC.rank_group(GOALS, position_group, league(count=6), tournament=False)

    def test_ties_share_rank(self):
        population = [sample(1, goals=9), sample(2, goals=9), *league()]
        leads = CALC.rank_group(GOALS, _group(), population, tournament=False)
        ranks = {player_id: lead for player_id, lead in leads}
        assert ranks[1].rank == ranks[2].rank == 1 and ranks[1].tied
        assert all(lead.rank == 3 for player_id, lead in leads if player_id >= 100)

    def test_only_podium_is_kept(self):
        population = [sample(index, goals=20 - index) for index in range(1, 13)]
        leads = CALC.rank_group(GOALS, _group(), population, tournament=False)
        assert [lead.rank for _, lead in leads] == [1, 2, 3]

    def test_empty_population(self):
        assert CALC.rank_group(GOALS, _group(), [], tournament=False) == []

    def test_attempts_minimum_scales_with_group(self):
        dribbler = sample(1, dribbles_won=30, dribbles_attempts=40)
        low_volume = sample(2, dribbles_won=9, dribbles_attempts=9)  # 25 % of 40 = 10 attempts needed
        others = [sample(index, dribbles_won=10, dribbles_attempts=20) for index in range(100, 112)]
        leads = dict(CALC.rank_group(CATALOG[4], _group(), [dribbler, low_volume, *others], tournament=False))
        assert leads[1].rank == 1 and leads[1].threshold.min_attempts == 15
        assert 2 not in leads


class TestSfaMetric:
    def _big(self, player_id, points, *, big_minutes=400, big_matches=4):
        return sample(player_id, big_points=points, big_minutes=big_minutes, big_matches=big_matches)

    def test_big_game_metric_ranks_points_per90(self):
        population = [self._big(1, 900), *[self._big(index, 100) for index in range(100, 112)]]
        leads = dict(CALC.rank_group(BIG, _group(), population, tournament=False))
        assert leads[1].rank == 1 and leads[1].value == pytest.approx(900 * 90 / 400)
        assert leads[1].details["big_points"] == 900

    def test_big_game_metric_requires_matches(self):
        population = [self._big(1, 900, big_matches=2), *[self._big(index, 100) for index in range(100, 112)]]
        assert 1 not in dict(CALC.rank_group(BIG, _group(), population, tournament=False))
        tournament = dict(CALC.rank_group(BIG, _group(), population, tournament=True))
        assert tournament[1].rank == 1

    def test_unavailable_sfa_metric_is_skipped(self):
        population = [self._big(1, 900), *[self._big(index, 100) for index in range(100, 112)]]
        snapshot = calculate(population, sfa=False)
        assert all(lead.metric != LeadMetric.BIG_GAME_POINTS_PER90 for lead in snapshot.for_player(1))
        assert snapshot.rules_version_id is None


class TestSnapshot:
    def test_deduplicates_by_metric_keeping_the_broader_group(self):
        star = sample(1, goals=20)
        snapshot = calculate([star, *league(), *league(count=6, start=200, position="DEL")])
        goals = [lead for lead in snapshot.for_player(1) if lead.metric == LeadMetric.GOALS_PER90]
        assert len(goals) == 1 and goals[0].group.kind == LeadGroupKind.COMPETITION

    def test_entries_ordered_by_exceptionality(self):
        star = sample(1, goals=20, assists=10, passes_key=60)
        snapshot = calculate([star, *league()])
        leads = snapshot.for_player(1)
        assert [lead.exceptional_key for lead in leads] == sorted(lead.exceptional_key for lead in leads)
        assert leads[0].metric == LeadMetric.GOALS_PER90  # catalogue order breaks the full tie

    def test_goalkeepers_only_compete_in_save_rate(self):
        keepers = [sample(index, position="GK", saves=40 - index, goals_conceded=10) for index in range(1, 13)]
        snapshot = calculate(keepers)
        metrics = {lead.metric for leads in snapshot.leads_by_player.values() for lead in leads}
        assert metrics == {LeadMetric.SAVE_RATE}


def _group(kind=LeadGroupKind.COMPETITION, position=None):
    return LeadGroup(kind, "2025", 140, "La Liga", position)
