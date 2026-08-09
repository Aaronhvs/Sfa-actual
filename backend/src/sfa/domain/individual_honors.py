from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from sfa.domain.season_scope import AwardPeriodScope


class IndividualHonorType(str, Enum):
    TOP_SCORER = "top_scorer"
    TOP_ASSISTER = "top_assister"
    BEST_DRIBBLER = "best_dribbler"
    DUEL_KING = "duel_king"


class HonorScopeCategory(str, Enum):
    AWARD_PERIOD = "award_period"
    WORLD_CUP = "world_cup"
    CHAMPIONS_LEAGUE = "champions_league"
    DOMESTIC_LEAGUE = "domestic_league"


@dataclass(frozen=True)
class HonorCandidateStats:
    player_id: int
    goals: int
    assists: int
    minutes: int
    dribbles_won: int
    dribbles_attempts: int
    duels_won: int
    duels_total: int

    def __post_init__(self) -> None:
        values = (
            self.player_id,
            self.goals,
            self.assists,
            self.minutes,
            self.dribbles_won,
            self.dribbles_attempts,
            self.duels_won,
            self.duels_total,
        )
        if self.player_id <= 0 or any(value < 0 for value in values[1:]):
            raise ValueError("Honor candidate values must be non-negative and player_id positive")

    @property
    def dribble_rate(self) -> float | None:
        if self.dribbles_attempts == 0:
            return None
        return self.dribbles_won / self.dribbles_attempts

    @property
    def duel_rate(self) -> float | None:
        if self.duels_total == 0:
            return None
        return self.duels_won / self.duels_total


@dataclass(frozen=True)
class HonorCompetitionDTO:
    competition_id: int
    competition_name: str
    season: str


@dataclass(frozen=True)
class IndividualHonor:
    id: int | None
    player_id: int
    scope_key: str
    scope_label: str
    context_key: str
    context_label: str
    scope_category: HonorScopeCategory
    honor_type: IndividualHonorType
    source_season: str
    competition_id: int | None
    rules_version_id: int
    metric_value: float
    metric_total: int | None
    metric_rate: float | None
    raw_bonus_pts: int
    awarded_bonus_pts: int
    calculation_details: dict

    def __post_init__(self) -> None:
        if self.player_id <= 0 or self.rules_version_id <= 0:
            raise ValueError("Honor player and rules version IDs must be positive")
        if not self.scope_key.strip() or not self.context_key.strip():
            raise ValueError("Honor scope and context keys cannot be empty")
        if not self.scope_label.strip() or not self.context_label.strip():
            raise ValueError("Honor scope and context labels cannot be empty")
        if not self.source_season.strip():
            raise ValueError("Honor source season cannot be empty")
        if self.metric_value < 0 or (self.metric_total is not None and self.metric_total < 0):
            raise ValueError("Honor metrics cannot be negative")
        if self.metric_rate is not None and not 0 <= self.metric_rate <= 1:
            raise ValueError("Honor metric rate must be between 0 and 1")
        if self.metric_rate is not None and self.metric_total is None:
            raise ValueError("A rate-based honor requires a metric total")
        if self.raw_bonus_pts < 0 or not 0 <= self.awarded_bonus_pts <= self.raw_bonus_pts:
            raise ValueError("Awarded honor points must be between zero and raw points")


@dataclass(frozen=True)
class PlayerIndividualHonorDTO:
    honor_id: int
    honor_type: str
    scope_key: str
    scope_label: str
    context_label: str
    source_season: str
    competition_id: int | None
    metric_value: float
    metric_total: int | None
    metric_rate: float | None
    bonus_pts: int


@dataclass(frozen=True)
class InferIndividualHonorsResult:
    scope_key: str
    honors_created: int
    players_awarded: int


@runtime_checkable
class IndividualHonorRepositoryPort(Protocol):
    async def get_competitions_for_scope(
        self, scope: AwardPeriodScope
    ) -> list[HonorCompetitionDTO]: ...

    async def get_candidate_stats(
        self,
        scope: AwardPeriodScope,
        competition_id: int | None = None,
    ) -> list[HonorCandidateStats]: ...

    async def replace_scope_honors(
        self,
        scope_key: str,
        rules_version_id: int,
        honors: list[IndividualHonor],
    ) -> None: ...

    async def get_player_honors(
        self,
        player_id: int,
        rules_version_id: int,
        scope_key: str | None = None,
    ) -> list[PlayerIndividualHonorDTO]: ...
