from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class WorldCupTeamDTO:
    external_id: int
    name: str


@dataclass(frozen=True)
class WorldCupFixtureDTO:
    external_id: int
    stage: str
    matchday: int | None
    played_at: datetime
    status: str
    status_label: str
    elapsed: int | None
    home_team: WorldCupTeamDTO
    away_team: WorldCupTeamDTO
    home_goals: int | None
    away_goals: int | None


@dataclass(frozen=True)
class WorldCupStandingDTO:
    group: str
    position: int
    team: WorldCupTeamDTO
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int
    form: str | None


@dataclass(frozen=True)
class WorldCupVenueDTO:
    name: str | None
    city: str | None


@dataclass(frozen=True)
class WorldCupLineupPlayerDTO:
    external_id: int | None
    name: str
    number: int | None
    position: str | None
    grid: str | None
    player_id: int | None = None
    sfa_points: float | None = None


@dataclass(frozen=True)
class WorldCupTeamLineupDTO:
    team: WorldCupTeamDTO
    formation: str | None
    coach_name: str | None
    coach_photo: str | None
    start_xi: list[WorldCupLineupPlayerDTO]
    substitutes: list[WorldCupLineupPlayerDTO]


@dataclass(frozen=True)
class WorldCupStatisticDTO:
    label: str
    home_value: str | None
    away_value: str | None
    home_numeric: float | None
    away_numeric: float | None


@dataclass(frozen=True)
class WorldCupFixtureDetailDTO:
    fixture: WorldCupFixtureDTO
    venue: WorldCupVenueDTO
    referee: str | None
    lineups: list[WorldCupTeamLineupDTO]
    statistics: list[WorldCupStatisticDTO]


@dataclass(frozen=True)
class WorldCupFixturesResultDTO:
    season: str
    fixtures: list[WorldCupFixtureDTO]


@dataclass(frozen=True)
class WorldCupLiveResultDTO:
    live: list[WorldCupFixtureDTO]
    has_live: bool


@dataclass(frozen=True)
class WorldCupStandingsResultDTO:
    season: str
    standings: list[WorldCupStandingDTO]


@runtime_checkable
class WorldCupRepositoryProtocol(Protocol):
    async def get_fixtures(self, season: str) -> list[WorldCupFixtureDTO]: ...

    async def get_standings(self, season: str) -> list[WorldCupStandingDTO]: ...

    async def get_fixture_detail(
        self,
        fixture_id: int,
    ) -> WorldCupFixtureDetailDTO | None: ...
