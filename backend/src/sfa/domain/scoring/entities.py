from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sfa.infrastructure.models.enums import Position

from .value_objects import (
    ActionType,
    CombinedMultiplier,
    M1RivalDifficulty,
    M2CompetitionStage,
    M3MinuteScore,
    M4ShotDifficulty,
    MvisitFactor,
    PositionGroup,
    SFAScore,
    ScoringConfig,
    position_to_group,
)


@dataclass(frozen=True)
class Player:
    id: int
    name: str
    position: Position
    group: PositionGroup

    @classmethod
    def from_position(cls, id: int, name: str, position: Position) -> "Player":
        """Factory that derives the scoring group from the player's position.

        Raises ValueError if position is GK (no scoring group defined).
        """
        group = position_to_group(position)
        return cls(id=id, name=name, position=position, group=group)


@dataclass(frozen=True)
class ScoredEvent:
    """
    Immutable record of a single scored action within a fixture.

    Represents the historical fact that an action occurred in a specific
    context and produced a concrete SFA score.
    """

    fixture_id: int
    minute: int
    action: ActionType
    base_pts: float
    m1: M1RivalDifficulty
    m2: M2CompetitionStage
    m3: M3MinuteScore
    m4: M4ShotDifficulty
    mvisit: MvisitFactor
    combined: CombinedMultiplier
    score: SFAScore


@dataclass
class PlayerSeasonScore:
    """
    Aggregate root that accumulates scored events for a player across a season.

    total_pts is always derived from the stored events — it can never be set
    directly and cannot get out of sync.
    """

    player: Player
    competition_id: int
    season: str
    _events: list[ScoredEvent] = field(default_factory=list, repr=False)

    @property
    def total_pts(self) -> float:
        return sum(e.score.total for e in self._events)

    @property
    def matches_played(self) -> int:
        return len({e.fixture_id for e in self._events})

    def add_events(self, events: list[ScoredEvent]) -> None:
        """Append new events to this season score."""
        self._events.extend(events)

    def replace_fixture_events(
        self, fixture_id: int, events: list[ScoredEvent]
    ) -> None:
        """Replace all events for a given fixture (idempotent re-ingestion)."""
        self._events = [e for e in self._events if e.fixture_id != fixture_id]
        self._events.extend(events)

    def remove_fixture_events(self, fixture_id: int) -> None:
        """Remove all events for a given fixture."""
        self._events = [e for e in self._events if e.fixture_id != fixture_id]


@dataclass(frozen=True)
class ScoringRulesVersion:
    """A named, immutable snapshot of scoring rules.

    Only one version may be active at a time; that invariant is enforced
    by the repository (set_active_version uses a transaction).
    """

    id: int
    name: str
    version: str
    description: str
    is_active: bool
    config: ScoringConfig
    created_at: datetime


@dataclass(frozen=True)
class PlayerEventScore:
    """Result of scoring a single PlayerEvent under a specific ScoringRulesVersion.

    One PlayerEvent can have multiple PlayerEventScores — one per rules version.
    calculation_details holds all intermediate values for audit/debug purposes.
    """

    id: int | None
    event_id: int
    player_id: int
    fixture_id: int
    season: str
    competition_id: int
    rules_version_id: int
    action_type: str
    position: str
    base_points: float
    m1: float
    m2: float
    m3: float
    m4: float
    mvisit: float
    mrating: float
    combined_before_clamp: float
    combined_after_clamp: float
    final_points: float
    calculation_details: dict
    created_at: datetime | None


@dataclass(frozen=True)
class CompetitionAchievement:
    """A competitive milestone reached by a team in a competition season.

    Registered manually (or via admin process). Drives the bonus calculation.

    Invariants:
      - bonus_points >= 0
      - 0 < weight <= 1.0
    """

    id: int | None
    competition_id: int
    team_id: int
    season: str
    phase: str          # e.g. "winner", "semi_final", "quarter_final"
    bonus_points: int
    weight: float       # competition_bonus_weights value
    created_at: datetime | None

    def __post_init__(self) -> None:
        if self.bonus_points < 0:
            raise ValueError(f"bonus_points must be >= 0, got {self.bonus_points}")
        if not (0.0 < self.weight <= 1.0):
            raise ValueError(f"weight must be in (0, 1.0], got {self.weight}")


@dataclass(frozen=True)
class PlayerAchievementBonus:
    """Bonus points awarded to a player for their team's competitive achievement.

    final_bonus = bonus_points * weight * participation_ratio

    Invariants:
      - 0 <= participation_ratio <= 1.0
      - final_bonus >= 0
    """

    id: int | None
    player_id: int
    team_id: int
    competition_id: int
    season: str
    rules_version_id: int
    achievement_id: int
    participation_ratio: float
    final_bonus: float
    calculation_details: dict
    created_at: datetime | None

    def __post_init__(self) -> None:
        if not (0.0 <= self.participation_ratio <= 1.0):
            raise ValueError(
                f"participation_ratio must be in [0, 1], got {self.participation_ratio}"
            )
        if self.final_bonus < 0:
            raise ValueError(f"final_bonus must be >= 0, got {self.final_bonus}")
