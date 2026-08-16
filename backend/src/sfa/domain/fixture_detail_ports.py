from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class FixtureTeamDTO:
    external_id: int
    name: str


@dataclass(frozen=True)
class FixtureSummaryDTO:
    external_id: int
    stage: str
    matchday: int | None
    played_at: datetime
    status: str
    status_label: str
    elapsed: int | None
    home_team: FixtureTeamDTO
    away_team: FixtureTeamDTO
    home_goals: int | None
    away_goals: int | None
    home_winner: bool | None = None
    away_winner: bool | None = None
    competition_id: int | None = None
    competition_name: str | None = None


@dataclass(frozen=True)
class FixtureVenueDTO:
    name: str | None
    city: str | None


@dataclass(frozen=True)
class FixtureLineupPlayerDTO:
    external_id: int | None
    name: str
    number: int | None
    position: str | None
    grid: str | None
    player_id: int | None = None
    sfa_points: float | None = None


@dataclass(frozen=True)
class FixtureTeamLineupDTO:
    team: FixtureTeamDTO
    formation: str | None
    coach_name: str | None
    coach_photo: str | None
    start_xi: list[FixtureLineupPlayerDTO]
    substitutes: list[FixtureLineupPlayerDTO]


@dataclass(frozen=True)
class FixtureStatisticDTO:
    label: str
    home_value: str | None
    away_value: str | None
    home_numeric: float | None
    away_numeric: float | None


@dataclass(frozen=True)
class FixtureTimelineEventDTO:
    minute: int
    extra_minute: int
    team_external_id: int
    event_type: str
    player_name: str
    assist_name: str | None


@dataclass(frozen=True)
class FixtureSFAMomentumBucketDTO:
    minute_start: int
    minute_end: int
    home_points: float
    away_points: float


@dataclass(frozen=True)
class FixtureDetailDTO:
    fixture: FixtureSummaryDTO
    venue: FixtureVenueDTO
    referee: str | None
    lineups: list[FixtureTeamLineupDTO]
    statistics: list[FixtureStatisticDTO]
    events: list[FixtureTimelineEventDTO] = field(default_factory=list)
    sfa_momentum: list[FixtureSFAMomentumBucketDTO] = field(default_factory=list)


@runtime_checkable
class FixtureDetailRepositoryProtocol(Protocol):
    async def get_fixture_detail(
        self, fixture_external_id: int,
    ) -> FixtureDetailDTO | None: ...

    async def get_fixture_events(
        self, fixture_external_id: int,
    ) -> list[FixtureTimelineEventDTO]: ...

    async def get_fixture_sfa_momentum(
        self,
        fixture_id: int,
        home_team_id: int,
        away_team_id: int,
    ) -> list[FixtureSFAMomentumBucketDTO]: ...
