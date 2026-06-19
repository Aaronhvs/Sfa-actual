from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

from sfa.domain.ports import RankedPlayerDTO


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
class WorldCupFixtureEventDTO:
    minute: int
    extra_minute: int
    team_external_id: int
    event_type: str
    player_name: str
    assist_name: str | None


@dataclass(frozen=True)
class WorldCupFixtureDetailDTO:
    fixture: WorldCupFixtureDTO
    venue: WorldCupVenueDTO
    referee: str | None
    lineups: list[WorldCupTeamLineupDTO]
    statistics: list[WorldCupStatisticDTO]
    events: list[WorldCupFixtureEventDTO] = field(default_factory=list)


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


@dataclass(frozen=True)
class WcTeamSFARankingDTO:
    rank: int
    team_external_id: int
    team_name: str
    total_sfa_pts: float
    total_goals: int
    player_count: int


@dataclass(frozen=True)
class WcTeamProfileDTO:
    team_external_id: int
    team_name: str
    total_sfa_pts: float
    total_goals: int
    top_players: list[RankedPlayerDTO]


@runtime_checkable
class WorldCupRepositoryProtocol(Protocol):
    async def get_fixtures(self, season: str) -> list[WorldCupFixtureDTO]: ...

    async def get_standings(self, season: str) -> list[WorldCupStandingDTO]: ...

    async def get_fixture_detail(
        self,
        fixture_id: int,
    ) -> WorldCupFixtureDetailDTO | None: ...

    async def get_fixture_events(
        self, fixture_external_id: int,
    ) -> list[WorldCupFixtureEventDTO]: ...

    async def get_wc_team_sfa_ranking(
        self, season: str, rules_version_id: int | None,
    ) -> list[WcTeamSFARankingDTO]: ...

    async def get_wc_team_profile(
        self, team_external_id: int, season: str, rules_version_id: int | None,
    ) -> WcTeamProfileDTO | None: ...
