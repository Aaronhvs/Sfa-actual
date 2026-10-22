import pytest

from sfa.domain.player_leads import CATALOG, LeadMethod, LeadMetric, LeadPolicy, LeadSample
from sfa.domain.player_leads.policy import DEFENSIVE_POSITIONS, FIELD_POSITIONS, GOALKEEPER_POSITIONS

POLICY = LeadPolicy()


class TestLeadPolicy:
    @pytest.mark.parametrize("m_max,tournament,expected", [
        (0, False, 270), (3420, False, 1026), (600, False, 270), (450, True, 180), (1000, True, 300),
    ])
    def test_min_minutes_scales_with_the_period(self, m_max, tournament, expected):
        assert POLICY.min_minutes(m_max, tournament) == expected

    @pytest.mark.parametrize("group_max,floor,expected", [(60, 8, 15), (10, 8, 8), (0, 40, 40)])
    def test_min_attempts(self, group_max, floor, expected):
        assert POLICY.min_attempts(group_max, floor) == expected

    def test_competition_minimum_excludes_short_competitions(self):
        assert not POLICY.competition_qualifies(180, tournament=False)
        assert POLICY.competition_qualifies(450, tournament=False)
        assert POLICY.competition_qualifies(270, tournament=True)
        assert not POLICY.competition_qualifies(269, tournament=True)

    def test_group_sizes_and_big_matches(self):
        assert POLICY.min_group_size(by_position=False) == 10
        assert POLICY.min_group_size(by_position=True) == 6
        assert POLICY.min_big_matches(tournament=False) == 3
        assert POLICY.min_big_matches(tournament=True) == 2
        assert POLICY.policy_version == "leads-v1"

    @pytest.mark.parametrize("max_rank,limit", [(0, 3), (4, 3), (3, 0), (3, 6)])
    def test_validate_request_rejects_out_of_range(self, max_rank, limit):
        with pytest.raises(ValueError):
            POLICY.validate_request(max_rank, limit)

    def test_validate_request_accepts_defaults(self):
        POLICY.validate_request(POLICY.default_max_rank, POLICY.default_limit)


class TestCatalog:
    def test_catalog_matches_metric_enum(self):
        assert [definition.metric for definition in CATALOG] == list(LeadMetric)

    @pytest.mark.parametrize("metric,positions,method,attempts_floor,min_events", [
        (LeadMetric.SHOT_CONVERSION, FIELD_POSITIONS, LeadMethod.WILSON_LOWER_BOUND, 8, 3),
        (LeadMetric.GOALS_PER90, FIELD_POSITIONS, LeadMethod.PER90, None, 3),
        (LeadMetric.GOAL_CONTRIBUTIONS_PER90, FIELD_POSITIONS, LeadMethod.PER90, None, 4),
        (LeadMetric.KEY_PASSES_PER90, FIELD_POSITIONS, LeadMethod.PER90, None, 10),
        (LeadMetric.DRIBBLES_PER90, FIELD_POSITIONS, LeadMethod.PER90, 15, None),
        (LeadMetric.DEFENSIVE_ACTIONS_PER90, DEFENSIVE_POSITIONS, LeadMethod.PER90, None, None),
        (LeadMetric.DUEL_WIN_RATE, DEFENSIVE_POSITIONS, LeadMethod.WILSON_LOWER_BOUND, 40, None),
        (LeadMetric.SAVE_RATE, GOALKEEPER_POSITIONS, LeadMethod.WILSON_LOWER_BOUND, 15, None),
        (LeadMetric.BIG_GAME_POINTS_PER90, FIELD_POSITIONS, LeadMethod.PER90, None, None),
    ])
    def test_metric_definition(self, metric, positions, method, attempts_floor, min_events):
        definition = next(item for item in CATALOG if item.metric == metric)
        assert definition.positions == positions
        assert definition.method == method
        assert definition.attempts_floor == attempts_floor
        assert definition.min_events == min_events
        assert definition.is_sfa == (metric == LeadMetric.BIG_GAME_POINTS_PER90)
        assert "GK" not in positions or positions == GOALKEEPER_POSITIONS

    def test_values(self):
        sample = LeadSample(1, "2025", 140, "La Liga", "club", "EXT", minutes=900, goals=10, np_goals=8,
                            np_shots_on=10, shots_on=12, penalty_goals=2, dribbles_won=0, dribbles_attempts=0)
        conversion = CATALOG[0]
        assert conversion.value(sample) == pytest.approx(0.8)
        assert conversion.ranking_value(sample) < 0.8
        assert conversion.details(sample)["penalty_goals_excluded"] == 2
        goals = CATALOG[1]
        assert goals.value(sample) == pytest.approx(1.0)
        assert goals.ranking_value(sample) == pytest.approx(1.0)
        assert CATALOG[4].details(sample)["success_rate"] == 0.0
        empty = LeadSample(2, "2025", 140, "La Liga", "club", "EXT")
        assert goals.value(empty) == 0.0
