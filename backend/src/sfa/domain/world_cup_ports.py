from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sfa.domain.fixture_detail_ports import FixtureDetailDTO as WorldCupFixtureDetailDTO
from sfa.domain.fixture_detail_ports import FixtureLineupPlayerDTO as WorldCupLineupPlayerDTO
from sfa.domain.fixture_detail_ports import FixtureStatisticDTO as WorldCupStatisticDTO
from sfa.domain.fixture_detail_ports import FixtureSummaryDTO as WorldCupFixtureDTO
from sfa.domain.fixture_detail_ports import FixtureTeamDTO as WorldCupTeamDTO
from sfa.domain.fixture_detail_ports import FixtureTeamLineupDTO as WorldCupTeamLineupDTO
from sfa.domain.fixture_detail_ports import FixtureTimelineEventDTO as WorldCupFixtureEventDTO
from sfa.domain.fixture_detail_ports import FixtureVenueDTO as WorldCupVenueDTO
from sfa.domain.ports import RankedPlayerDTO

__all__ = [
    "WorldCupFixtureDetailDTO",
    "WorldCupFixtureDTO",
    "WorldCupFixtureEventDTO",
    "WorldCupLineupPlayerDTO",
    "WorldCupStatisticDTO",
    "WorldCupTeamDTO",
    "WorldCupTeamLineupDTO",
    "WorldCupVenueDTO",
    "WorldCupStandingDTO",
    "WorldCupFixturesResultDTO",
    "WorldCupLiveResultDTO",
    "WorldCupStandingsResultDTO",
    "WcTeamSFARankingDTO",
    "WcTeamProfileDTO",
    "WorldCupRepositoryProtocol",
]


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
