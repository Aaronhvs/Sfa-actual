from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.get_world_cup import (
    GetWorldCupFixtureDetailUseCase,
    GetWorldCupFixturesUseCase,
    GetWorldCupLiveUseCase,
    GetWorldCupStandingsUseCase,
)
from sfa.domain.world_cup_ports import (
    WorldCupFixtureDetailDTO,
    WorldCupFixtureDTO,
    WorldCupStandingDTO,
    WorldCupTeamDTO,
    WorldCupVenueDTO,
)


class FakeWorldCupRepository:
    def __init__(
        self,
        fixtures: list[WorldCupFixtureDTO] | None = None,
        standings: list[WorldCupStandingDTO] | None = None,
        detail: WorldCupFixtureDetailDTO | None = None,
    ) -> None:
        self.fixtures = fixtures or []
        self.standings = standings or []
        self.detail = detail

    async def get_fixtures(self, season: str) -> list[WorldCupFixtureDTO]:
        return self.fixtures

    async def get_standings(self, season: str) -> list[WorldCupStandingDTO]:
        return self.standings

    async def get_fixture_detail(
        self,
        fixture_id: int,
    ) -> WorldCupFixtureDetailDTO | None:
        return self.detail


def make_fixture(status: str) -> WorldCupFixtureDTO:
    return WorldCupFixtureDTO(
        external_id=1489371,
        stage="Group Stage - 1",
        matchday=1,
        played_at=datetime(2026, 6, 13, 22, tzinfo=timezone.utc),
        status=status,
        status_label="Second Half" if status == "2H" else "Match Finished",
        elapsed=60 if status == "2H" else 90,
        home_team=WorldCupTeamDTO(external_id=6, name="Brazil"),
        away_team=WorldCupTeamDTO(external_id=31, name="Morocco"),
        home_goals=1,
        away_goals=1,
    )


@pytest.mark.anyio
async def test_live_use_case_uses_provider_status_not_time_window() -> None:
    repository = FakeWorldCupRepository(
        fixtures=[make_fixture("2H"), make_fixture("FT")]
    )

    result = await GetWorldCupLiveUseCase(repository).execute()

    assert result.has_live is True
    assert [fixture.status for fixture in result.live] == ["2H"]


@pytest.mark.anyio
async def test_fixtures_use_case_preserves_season_and_results() -> None:
    repository = FakeWorldCupRepository(fixtures=[make_fixture("FT")])

    result = await GetWorldCupFixturesUseCase(repository).execute("2026")

    assert result.season == "2026"
    assert result.fixtures[0].home_goals == 1
    assert result.fixtures[0].away_goals == 1


@pytest.mark.anyio
async def test_standings_use_case_returns_group_rows() -> None:
    row = WorldCupStandingDTO(
        group="Group C",
        position=1,
        team=WorldCupTeamDTO(external_id=6, name="Brazil"),
        played=1,
        won=0,
        drawn=1,
        lost=0,
        goals_for=1,
        goals_against=1,
        goal_difference=0,
        points=1,
        form="D",
    )
    repository = FakeWorldCupRepository(standings=[row])

    result = await GetWorldCupStandingsUseCase(repository).execute()

    assert result.season == "2026"
    assert result.standings == [row]


@pytest.mark.anyio
async def test_fixture_detail_use_case_returns_composed_detail() -> None:
    fixture = make_fixture("FT")
    detail = WorldCupFixtureDetailDTO(
        fixture=fixture,
        venue=WorldCupVenueDTO(name="MetLife Stadium", city="New Jersey"),
        referee="Example Referee",
        lineups=[],
        statistics=[],
    )

    result = await GetWorldCupFixtureDetailUseCase(
        FakeWorldCupRepository(detail=detail)
    ).execute(fixture.external_id)

    assert result == detail


@pytest.mark.anyio
async def test_fixture_detail_use_case_raises_for_unknown_fixture() -> None:
    with pytest.raises(ValueError, match="not found"):
        await GetWorldCupFixtureDetailUseCase(
            FakeWorldCupRepository()
        ).execute(999999999)
