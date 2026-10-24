from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from sfa.domain.player_leads.models import LeadMethod, LeadMetric, LeadSample, RateCount

FIELD_POSITIONS = frozenset({"DC", "LAT", "MC", "MCO", "EXT", "DEL"})
DEFENSIVE_POSITIONS = frozenset({"DC", "LAT", "MC"})
GOALKEEPER_POSITIONS = frozenset({"GK"})


@dataclass(frozen=True)
class LeadPolicy:
    """Constants of `leads-v2`. Minimums scale with how far the period has progressed (same idea as 0066)."""

    policy_version: str = "leads-v2"
    award_minutes_floor: int = 270
    tournament_minutes_floor: int = 180
    minutes_fraction: float = 0.30
    attempts_fraction: float = 0.25
    award_competition_min_minutes: int = 450
    tournament_competition_min_minutes: int = 270
    min_group_size_all: int = 10
    min_group_size_position: int = 6
    big_strength: float = 50.0
    elite_strength: float = 70.0
    award_big_matches: int = 3
    tournament_big_matches: int = 2
    max_rank_limit: int = 3
    max_items_limit: int = 5
    default_max_rank: int = 3
    default_limit: int = 3

    def minutes_floor(self, tournament: bool) -> int:
        return self.tournament_minutes_floor if tournament else self.award_minutes_floor

    def min_minutes(self, group_max_minutes: int, tournament: bool) -> int:
        return max(self.minutes_floor(tournament), math.ceil(self.minutes_fraction * group_max_minutes))

    def min_attempts(self, group_max_attempts: int, floor: int) -> int:
        return max(floor, math.ceil(self.attempts_fraction * group_max_attempts))

    def competition_qualifies(self, competition_max_minutes: int, tournament: bool) -> bool:
        limit = self.tournament_competition_min_minutes if tournament else self.award_competition_min_minutes
        return competition_max_minutes >= limit

    def min_group_size(self, by_position: bool) -> int:
        return self.min_group_size_position if by_position else self.min_group_size_all

    def min_big_matches(self, tournament: bool) -> int:
        return self.tournament_big_matches if tournament else self.award_big_matches

    def validate_request(self, max_rank: int, limit: int) -> None:
        if not 1 <= max_rank <= self.max_rank_limit:
            raise ValueError(f"max_rank must be between 1 and {self.max_rank_limit}")
        if not 1 <= limit <= self.max_items_limit:
            raise ValueError(f"limit must be between 1 and {self.max_items_limit}")


Counter = Callable[[LeadSample], float]


@dataclass(frozen=True)
class MetricDefinition:
    metric: LeadMetric
    positions: frozenset[str]
    method: LeadMethod
    numerator: Counter
    denominator: Counter
    min_events: int | None = None
    events: Counter | None = None
    attempts: Counter | None = None
    attempts_floor: int | None = None
    attempts_kind: str | None = None
    is_sfa: bool = False
    details: Callable[[LeadSample], dict[str, float]] = lambda sample: {}

    @property
    def splits_by_position(self) -> bool:
        return len(self.positions) > 1

    def value(self, sample: LeadSample) -> float:
        """Display figure: raw rate for proportions, amount per 90' otherwise."""
        numerator, denominator = self.numerator(sample), self.denominator(sample)
        if denominator <= 0:
            return 0.0
        return numerator / denominator if self.method == LeadMethod.WILSON_LOWER_BOUND else numerator * 90 / denominator

    def ranking_value(self, sample: LeadSample) -> float:
        if self.method == LeadMethod.WILSON_LOWER_BOUND:
            return RateCount(int(self.numerator(sample)), int(self.denominator(sample))).wilson_lower_bound()
        return self.value(sample)


def _minutes(sample: LeadSample) -> float:
    return sample.minutes


CATALOG: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        LeadMetric.SHOT_CONVERSION, FIELD_POSITIONS, LeadMethod.WILSON_LOWER_BOUND,
        numerator=lambda s: s.np_goals, denominator=lambda s: s.np_shots_on,
        min_events=3, events=lambda s: s.np_goals,
        attempts=lambda s: s.np_shots_on, attempts_floor=8, attempts_kind="shots_on_target",
        details=lambda s: {
            "goals": s.goals, "shots_on": s.shots_on, "shots_total": s.shots_total,
            "penalty_goals_excluded": s.penalty_goals,
        },
    ),
    MetricDefinition(
        LeadMetric.GOALS_PER90, FIELD_POSITIONS, LeadMethod.PER90,
        numerator=lambda s: s.goals, denominator=_minutes, min_events=3, events=lambda s: s.goals,
        details=lambda s: {"goals": s.goals, "minutes": s.minutes},
    ),
    MetricDefinition(
        LeadMetric.GOAL_CONTRIBUTIONS_PER90, FIELD_POSITIONS, LeadMethod.PER90,
        numerator=lambda s: s.goals + s.assists, denominator=_minutes,
        min_events=4, events=lambda s: s.goals + s.assists,
        details=lambda s: {"goals": s.goals, "assists": s.assists, "minutes": s.minutes},
    ),
    MetricDefinition(
        LeadMetric.KEY_PASSES_PER90, FIELD_POSITIONS, LeadMethod.PER90,
        numerator=lambda s: s.passes_key, denominator=_minutes, min_events=10, events=lambda s: s.passes_key,
        details=lambda s: {"key_passes": s.passes_key, "minutes": s.minutes},
    ),
    MetricDefinition(
        LeadMetric.DRIBBLES_PER90, FIELD_POSITIONS, LeadMethod.PER90,
        numerator=lambda s: s.dribbles_won, denominator=_minutes,
        attempts=lambda s: s.dribbles_attempts, attempts_floor=15, attempts_kind="dribble_attempts",
        details=lambda s: {
            "dribbles_won": s.dribbles_won, "dribbles_attempts": s.dribbles_attempts,
            "success_rate": (s.dribbles_won / s.dribbles_attempts) if s.dribbles_attempts else 0.0,
            "minutes": s.minutes,
        },
    ),
    MetricDefinition(
        LeadMetric.DEFENSIVE_ACTIONS_PER90, DEFENSIVE_POSITIONS, LeadMethod.PER90,
        numerator=lambda s: s.tackles + s.interceptions, denominator=_minutes,
        details=lambda s: {"tackles": s.tackles, "interceptions": s.interceptions, "minutes": s.minutes},
    ),
    MetricDefinition(
        LeadMetric.DUEL_WIN_RATE, DEFENSIVE_POSITIONS, LeadMethod.WILSON_LOWER_BOUND,
        numerator=lambda s: s.duels_won, denominator=lambda s: s.duels_total,
        attempts=lambda s: s.duels_total, attempts_floor=40, attempts_kind="duels",
        details=lambda s: {"duels_won": s.duels_won, "duels_total": s.duels_total},
    ),
    MetricDefinition(
        LeadMetric.SAVE_RATE, GOALKEEPER_POSITIONS, LeadMethod.WILSON_LOWER_BOUND,
        numerator=lambda s: s.saves, denominator=lambda s: s.saves + s.goals_conceded,
        attempts=lambda s: s.saves + s.goals_conceded, attempts_floor=15, attempts_kind="shots_faced",
        details=lambda s: {"saves": s.saves, "goals_conceded": s.goals_conceded},
    ),
    MetricDefinition(
        LeadMetric.BIG_GAME_POINTS_PER90, FIELD_POSITIONS, LeadMethod.PER90,
        numerator=lambda s: s.big_points, denominator=lambda s: s.big_minutes, is_sfa=True,
        details=lambda s: {
            "big_points": round(s.big_points, 2), "big_matches": s.big_matches,
            "elite_matches": s.elite_matches, "big_minutes": s.big_minutes,
        },
    ),
)
