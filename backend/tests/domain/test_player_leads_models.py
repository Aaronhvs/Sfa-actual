import pytest

from sfa.domain.player_leads import (
    LeadGroup,
    LeadGroupKind,
    LeadMethod,
    LeadMetric,
    LeadSample,
    LeadThreshold,
    PlayerLead,
    PlayerLeadsSnapshot,
    RateCount,
)


def _sample(**counters):
    base = dict(player_id=1, season="2025", competition_id=140, competition_name="La Liga",
                participant_kind="club", position="EXT")
    base.update(counters)
    return LeadSample(**base)


def _lead(rank=1, qualified=10, kind=LeadGroupKind.COMPETITION, metric=LeadMetric.GOALS_PER90):
    return PlayerLead(metric, LeadGroup(kind), rank, False, qualified, 1.0, 1.0, LeadMethod.PER90, 1, 90,
                      LeadThreshold())


class TestLeadMetric:
    def test_catalog_keys_and_order(self):
        assert [metric.value for metric in LeadMetric] == [
            "shot_conversion", "goals_per90", "goal_contributions_per90", "key_passes_per90",
            "dribbles_per90", "defensive_actions_per90", "duel_win_rate", "save_rate", "big_game_points_per90",
        ]
        assert LeadMetric.SHOT_CONVERSION.catalog_index == 0

    def test_group_kind_priority(self):
        ordered = sorted(LeadGroupKind, key=lambda kind: kind.priority)
        assert ordered == [LeadGroupKind.SCOPE, LeadGroupKind.COMPETITION,
                           LeadGroupKind.SCOPE_POSITION, LeadGroupKind.COMPETITION_POSITION]
        assert LeadGroupKind.SCOPE_POSITION.is_position and not LeadGroupKind.SCOPE.is_position


class TestRateCount:
    @pytest.mark.parametrize("successes,attempts,expected", [
        (14, 19, 0.512), (6, 7, 0.487), (3, 3, 0.439), (1, 1, 0.207),
    ])
    def test_wilson_lower_bound_reference_values(self, successes, attempts, expected):
        assert RateCount(successes, attempts).wilson_lower_bound() == pytest.approx(expected, abs=0.001)

    def test_volume_beats_tiny_perfect_samples(self):
        assert RateCount(14, 19).wilson_lower_bound() > RateCount(6, 7).wilson_lower_bound()
        assert RateCount(6, 7).wilson_lower_bound() > RateCount(3, 3).wilson_lower_bound()

    def test_edges(self):
        assert RateCount(0, 10).wilson_lower_bound() == 0
        assert RateCount(10, 10).wilson_lower_bound() < 1
        assert RateCount(0, 0).rate is None
        assert RateCount(0, 0).wilson_lower_bound() == 0
        assert RateCount(3, 4).rate == 0.75

    @pytest.mark.parametrize("successes,attempts", [(-1, 3), (1, -3), (4, 3)])
    def test_invalid_counts_raise(self, successes, attempts):
        with pytest.raises(ValueError):
            RateCount(successes, attempts)


class TestLeadSample:
    @pytest.mark.parametrize("counters", [
        {"minutes": -1},
        {"np_goals": 3, "np_shots_on": 2},
        {"dribbles_won": 5, "dribbles_attempts": 4},
        {"duels_won": 5, "duels_total": 4},
        {"minutes": 90, "big_minutes": 91},
    ])
    def test_invariants(self, counters):
        with pytest.raises(ValueError):
            _sample(**counters)

    def test_big_points_may_be_negative(self):
        assert _sample(big_points=-12.5).big_points == -12.5

    def test_combine_sums_counters_and_drops_source(self):
        merged = _sample(minutes=90, goals=1, big_points=10.5).combine(_sample(minutes=80, goals=2, big_points=4))
        assert merged.minutes == 170 and merged.goals == 3 and merged.big_points == 14.5
        assert merged.competition_id is None and merged.season is None and merged.position == "EXT"

    def test_combine_other_player_raises(self):
        with pytest.raises(ValueError):
            _sample().combine(_sample(player_id=2))

    def test_with_position(self):
        assert _sample(minutes=10).with_position("DEL").position == "DEL"


class TestPlayerLead:
    def test_rank_bounds(self):
        with pytest.raises(ValueError):
            _lead(rank=0)
        with pytest.raises(ValueError):
            _lead(rank=11, qualified=10)

    def test_percentile(self):
        assert _lead(rank=1, qualified=10).percentile == 1
        assert _lead(rank=3, qualified=10).percentile == pytest.approx(0.8)

    def test_exceptional_key_prefers_rank_then_group_breadth(self):
        competition = _lead(rank=1, kind=LeadGroupKind.COMPETITION)
        position = _lead(rank=1, kind=LeadGroupKind.COMPETITION_POSITION)
        second = _lead(rank=2, kind=LeadGroupKind.SCOPE)
        assert sorted([second, position, competition], key=lambda lead: lead.exceptional_key) == [
            competition, position, second,
        ]

    def test_snapshot_for_player(self):
        lead = _lead()
        snapshot = PlayerLeadsSnapshot("leads-v2", "season-2025", 4, {7: (lead,)})
        assert snapshot.for_player(7) == (lead,)
        assert snapshot.for_player(8) == ()
