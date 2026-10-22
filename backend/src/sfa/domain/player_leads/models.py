from __future__ import annotations

import math
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Mapping


class LeadMetric(str, Enum):
    """Catalogue keys of `leads-v1`. Declaration order is the final tie-break between metrics."""

    SHOT_CONVERSION = "shot_conversion"
    GOALS_PER90 = "goals_per90"
    GOAL_CONTRIBUTIONS_PER90 = "goal_contributions_per90"
    KEY_PASSES_PER90 = "key_passes_per90"
    DRIBBLES_PER90 = "dribbles_per90"
    DEFENSIVE_ACTIONS_PER90 = "defensive_actions_per90"
    DUEL_WIN_RATE = "duel_win_rate"
    SAVE_RATE = "save_rate"
    BIG_GAME_POINTS_PER90 = "big_game_points_per90"

    @property
    def catalog_index(self) -> int:
        return list(LeadMetric).index(self)


class LeadGroupKind(str, Enum):
    SCOPE = "scope"
    COMPETITION = "competition"
    SCOPE_POSITION = "scope_position"
    COMPETITION_POSITION = "competition_position"

    @property
    def priority(self) -> int:
        """Lower is more exceptional: leading a whole season beats leading one position in one league."""
        return _GROUP_PRIORITY[self]

    @property
    def is_position(self) -> bool:
        return self in (LeadGroupKind.SCOPE_POSITION, LeadGroupKind.COMPETITION_POSITION)


_GROUP_PRIORITY = {
    LeadGroupKind.SCOPE: 0,
    LeadGroupKind.COMPETITION: 1,
    LeadGroupKind.SCOPE_POSITION: 2,
    LeadGroupKind.COMPETITION_POSITION: 3,
}


class LeadMethod(str, Enum):
    PER90 = "per90"
    WILSON_LOWER_BOUND = "wilson_lower_bound"


WILSON_Z = 1.96


@dataclass(frozen=True)
class RateCount:
    """Successes over attempts, ranked by the Wilson lower bound so volume beats tiny perfect samples."""

    successes: int
    attempts: int

    def __post_init__(self) -> None:
        if self.successes < 0 or self.attempts < 0:
            raise ValueError("RateCount values cannot be negative")
        if self.successes > self.attempts:
            raise ValueError("RateCount successes cannot exceed attempts")

    @property
    def rate(self) -> float | None:
        if self.attempts == 0:
            return None
        return self.successes / self.attempts

    def wilson_lower_bound(self, z: float = WILSON_Z) -> float:
        if self.attempts == 0:
            return 0.0
        n = self.attempts
        p = self.successes / n
        z2 = z * z
        centre = p + z2 / (2 * n)
        margin = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
        return max(0.0, min(1.0, (centre - margin) / (1 + z2 / n)))


_SUMMABLE_COUNTERS = (
    "minutes", "matches", "goals", "assists", "np_goals", "np_shots_on", "penalty_goals", "shots_on",
    "shots_total", "passes_key", "dribbles_won", "dribbles_attempts", "duels_won", "duels_total", "tackles",
    "interceptions", "saves", "goals_conceded", "big_minutes", "big_matches", "elite_matches",
)


@dataclass(frozen=True)
class LeadSample:
    """Aggregated counters of one player in one source (season + competition) or in a whole scope."""

    player_id: int
    season: str | None
    competition_id: int | None
    competition_name: str | None
    participant_kind: str | None
    position: str | None
    minutes: int = 0
    matches: int = 0
    goals: int = 0
    assists: int = 0
    np_goals: int = 0
    np_shots_on: int = 0
    penalty_goals: int = 0
    shots_on: int = 0
    shots_total: int = 0
    passes_key: int = 0
    dribbles_won: int = 0
    dribbles_attempts: int = 0
    duels_won: int = 0
    duels_total: int = 0
    tackles: int = 0
    interceptions: int = 0
    saves: int = 0
    goals_conceded: int = 0
    big_points: float = 0.0
    big_minutes: int = 0
    big_matches: int = 0
    elite_matches: int = 0

    def __post_init__(self) -> None:
        for name in _SUMMABLE_COUNTERS:
            if getattr(self, name) < 0:
                raise ValueError(f"LeadSample.{name} cannot be negative")
        if self.np_goals > self.np_shots_on:
            raise ValueError("LeadSample np_goals cannot exceed np_shots_on")
        if self.dribbles_won > self.dribbles_attempts:
            raise ValueError("LeadSample dribbles_won cannot exceed dribbles_attempts")
        if self.duels_won > self.duels_total:
            raise ValueError("LeadSample duels_won cannot exceed duels_total")
        if self.big_minutes > self.minutes:
            raise ValueError("LeadSample big_minutes cannot exceed minutes")

    def combine(self, other: LeadSample) -> LeadSample:
        """Sum two samples of the same player into a scope-wide sample (source fields are dropped)."""
        if other.player_id != self.player_id:
            raise ValueError("Only samples of the same player can be combined")
        values = {name: getattr(self, name) + getattr(other, name) for name in _SUMMABLE_COUNTERS}
        return LeadSample(
            player_id=self.player_id, season=None, competition_id=None, competition_name=None,
            participant_kind=None, position=self.position,
            big_points=self.big_points + other.big_points, **values,
        )

    def with_position(self, position: str | None) -> LeadSample:
        values = {item.name: getattr(self, item.name) for item in fields(self)}
        values["position"] = position
        return LeadSample(**values)


@dataclass(frozen=True)
class LeadThreshold:
    min_minutes: int | None = None
    min_attempts: int | None = None
    attempts_kind: str | None = None
    min_events: int | None = None


@dataclass(frozen=True)
class LeadGroup:
    kind: LeadGroupKind
    season: str | None = None
    competition_id: int | None = None
    competition_name: str | None = None
    position: str | None = None


@dataclass(frozen=True)
class PlayerLead:
    metric: LeadMetric
    group: LeadGroup
    rank: int
    tied: bool
    qualified_count: int
    value: float
    ranking_value: float
    method: LeadMethod
    numerator: float
    denominator: float
    threshold: LeadThreshold
    details: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.rank < 1 or self.rank > self.qualified_count:
            raise ValueError("PlayerLead rank must be between 1 and qualified_count")

    @property
    def percentile(self) -> float:
        return 1 - (self.rank - 1) / self.qualified_count

    @property
    def exceptional_key(self) -> tuple[int, int, float, int, int]:
        """Sort key, most exceptional first: rank, group breadth, percentile, field size, catalogue order."""
        return (self.rank, self.group.kind.priority, -self.percentile, -self.qualified_count,
                self.metric.catalog_index)


@dataclass(frozen=True)
class PlayerLeadsSnapshot:
    policy_version: str
    scope_key: str
    rules_version_id: int | None
    leads_by_player: Mapping[int, tuple[PlayerLead, ...]]

    def for_player(self, player_id: int) -> tuple[PlayerLead, ...]:
        return self.leads_by_player.get(player_id, ())
