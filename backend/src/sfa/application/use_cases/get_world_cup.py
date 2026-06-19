from dataclasses import replace

from sfa.domain.world_cup_ports import (
    WorldCupFixtureDetailDTO,
    WorldCupFixturesResultDTO,
    WorldCupLiveResultDTO,
    WorldCupRepositoryProtocol,
    WorldCupStandingsResultDTO,
    WcTeamProfileDTO,
    WcTeamSFARankingDTO,
)

WORLD_CUP_SEASON = "2026"
LIVE_STATUSES = {"1H", "HT", "2H", "ET", "BT", "P", "SUSP", "INT", "LIVE"}


class GetWorldCupFixturesUseCase:
    def __init__(self, repository: WorldCupRepositoryProtocol) -> None:
        self._repository = repository

    async def execute(
        self,
        season: str = WORLD_CUP_SEASON,
    ) -> WorldCupFixturesResultDTO:
        fixtures = await self._repository.get_fixtures(season)
        return WorldCupFixturesResultDTO(season=season, fixtures=fixtures)


class GetWorldCupLiveUseCase:
    def __init__(self, repository: WorldCupRepositoryProtocol) -> None:
        self._repository = repository

    async def execute(
        self,
        season: str = WORLD_CUP_SEASON,
    ) -> WorldCupLiveResultDTO:
        fixtures = await self._repository.get_fixtures(season)
        live = [fixture for fixture in fixtures if fixture.status in LIVE_STATUSES]
        return WorldCupLiveResultDTO(live=live, has_live=bool(live))


class GetWorldCupStandingsUseCase:
    def __init__(self, repository: WorldCupRepositoryProtocol) -> None:
        self._repository = repository

    async def execute(
        self,
        season: str = WORLD_CUP_SEASON,
    ) -> WorldCupStandingsResultDTO:
        standings = await self._repository.get_standings(season)
        return WorldCupStandingsResultDTO(season=season, standings=standings)


class GetWorldCupFixtureDetailUseCase:
    def __init__(self, repository: WorldCupRepositoryProtocol) -> None:
        self._repository = repository

    async def execute(self, fixture_id: int) -> WorldCupFixtureDetailDTO:
        detail = await self._repository.get_fixture_detail(fixture_id)
        if detail is None:
            raise ValueError(f"World Cup fixture {fixture_id} not found")
        events = await self._repository.get_fixture_events(fixture_id)
        return replace(detail, events=events)


class GetWcTeamSFARankingUseCase:
    def __init__(
        self,
        repository: WorldCupRepositoryProtocol,
        default_rules_version_id: int | None = None,
    ) -> None:
        self._repository = repository
        self._default_rules_version_id = default_rules_version_id

    async def execute(
        self,
        season: str = WORLD_CUP_SEASON,
        rules_version_id: int | None = None,
    ) -> list[WcTeamSFARankingDTO]:
        if rules_version_id is None:
            rules_version_id = self._default_rules_version_id
        return await self._repository.get_wc_team_sfa_ranking(season, rules_version_id)


class GetWcTeamProfileUseCase:
    def __init__(
        self,
        repository: WorldCupRepositoryProtocol,
        default_rules_version_id: int | None = None,
    ) -> None:
        self._repository = repository
        self._default_rules_version_id = default_rules_version_id

    async def execute(
        self,
        team_external_id: int,
        season: str = WORLD_CUP_SEASON,
        rules_version_id: int | None = None,
    ) -> WcTeamProfileDTO:
        if rules_version_id is None:
            rules_version_id = self._default_rules_version_id
        profile = await self._repository.get_wc_team_profile(team_external_id, season, rules_version_id)
        if profile is None:
            raise ValueError(f"World Cup team {team_external_id} not found or has no SFA data")
        return profile
