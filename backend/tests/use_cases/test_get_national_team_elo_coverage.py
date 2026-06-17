from __future__ import annotations

import pytest

from sfa.application.use_cases.get_national_team_elo_coverage import (
    GetNationalTeamEloCoverageUseCase,
)
from sfa.domain.scoring_ports import (
    FixtureEloRow,
    TeamCompetitionRow,
    TeamEloRow,
    TeamStandingRow,
    TeamStrengthCoverageRow,
    TeamStrengthRepositoryPort,
)


class FakeTeamStrengthRepository(TeamStrengthRepositoryPort):
    def __init__(self, competition_id: int | None = 1) -> None:
        self.competition_id = competition_id
        self.coverage = [
            TeamStrengthCoverageRow(10, "Brazil", 1, 80.0, 1960.0, "national_elo_seed"),
            TeamStrengthCoverageRow(20, "Argentina", 1, None, None, None),
        ]

    async def get_team_strength(self, team_id, season, competition_id):
        return None

    async def upsert_team_strength(self, team_id, season, competition_id, strength, source):
        pass

    async def get_team_standings_for_season(self, competition_id, season) -> list[TeamStandingRow]:
        return []

    async def get_team_strength_with_elo(self, team_id, season, competition_id):
        return None, None

    async def upsert_team_elo(
        self, team_id, season, elo_raw, strength_normalized, source, competition_ids
    ) -> None:
        pass

    async def get_all_teams_with_elo(self, season) -> list[TeamEloRow]:
        return []

    async def get_fixtures_for_elo_recalc(self, season, competition_ids) -> list[FixtureEloRow]:
        return []

    async def get_team_name_id_map(self, season):
        return {}

    async def get_active_competition_ids_for_team(self, team_id, season):
        return []

    async def get_competition_id_by_name(self, name):
        return self.competition_id

    async def get_teams_for_competition_season(self, competition_id, season) -> list[TeamCompetitionRow]:
        return []

    async def get_team_strength_coverage(self, competition_id, season) -> list[TeamStrengthCoverageRow]:
        return self.coverage


@pytest.mark.anyio
async def test_coverage_reports_missing_teams() -> None:
    repo = FakeTeamStrengthRepository()
    use_case = GetNationalTeamEloCoverageUseCase(repo)

    result = await use_case.execute("2026")

    assert result.status == "completed"
    assert result.total_teams == 2
    assert result.teams_with_strength == 1
    assert result.coverage_pct == 50.0
    assert result.missing == ["Argentina"]


@pytest.mark.anyio
async def test_coverage_fails_when_world_cup_not_found() -> None:
    repo = FakeTeamStrengthRepository(competition_id=None)
    use_case = GetNationalTeamEloCoverageUseCase(repo)

    result = await use_case.execute("2026")

    assert result.status == "failed"
    assert result.error == "World Cup competition not found"
