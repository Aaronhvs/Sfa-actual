from sfa.domain.world_cup_ports import (
    WorldCupFixtureDetailDTO,
    WorldCupFixturesResultDTO,
    WorldCupLiveResultDTO,
    WorldCupRepositoryProtocol,
    WorldCupStandingsResultDTO,
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
        return detail
