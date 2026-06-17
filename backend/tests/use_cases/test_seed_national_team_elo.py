from __future__ import annotations

import pytest

from sfa.application.use_cases.seed_national_team_elo import (
    NATIONAL_ELO_SOURCE,
    SeedNationalTeamEloUseCase,
)
from sfa.domain.scoring_ports import (
    FixtureEloRow,
    NationalTeamEloEntry,
    TeamCompetitionRow,
    TeamEloRow,
    TeamStandingRow,
    TeamStrengthCoverageRow,
    TeamStrengthRepositoryPort,
)
from sfa.infrastructure.services.elo_calculator import EloCalculatorService


class FakeTeamStrengthRepository(TeamStrengthRepositoryPort):
    def __init__(
        self,
        teams: list[TeamCompetitionRow] | None = None,
        competition_id: int | None = 1,
    ) -> None:
        self.teams = teams or [
            TeamCompetitionRow(team_id=10, team_name="Brazil", competition_id=1),
            TeamCompetitionRow(team_id=20, team_name="Argentina", competition_id=1),
        ]
        self.competition_id = competition_id
        self.upserted_elos: list[dict] = []

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
        self.upserted_elos.append({
            "team_id": team_id,
            "season": season,
            "elo_raw": elo_raw,
            "strength_normalized": strength_normalized,
            "source": source,
            "competition_ids": competition_ids,
        })

    async def get_all_teams_with_elo(self, season) -> list[TeamEloRow]:
        return []

    async def get_fixtures_for_elo_recalc(self, season, competition_ids) -> list[FixtureEloRow]:
        return []

    async def get_team_name_id_map(self, season):
        return {}

    async def get_active_competition_ids_for_team(self, team_id, season):
        return [1]

    async def get_competition_id_by_name(self, name):
        return self.competition_id

    async def get_teams_for_competition_season(self, competition_id, season) -> list[TeamCompetitionRow]:
        return self.teams

    async def get_team_strength_coverage(self, competition_id, season) -> list[TeamStrengthCoverageRow]:
        return []


class FakeNationalTeamEloProvider:
    def __init__(self, entries: list[NationalTeamEloEntry]) -> None:
        self.entries = entries

    async def fetch_snapshot(self, source_url, manual_entries=None):
        return manual_entries if manual_entries is not None else self.entries

    def resolve_team_name(self, source_name, sfa_team_names):
        return source_name if source_name in sfa_team_names else None


def _entry(name: str, elo: float) -> NationalTeamEloEntry:
    return NationalTeamEloEntry(
        country_name=name,
        elo_raw=elo,
        rank=None,
        source_date="manual",
    )


@pytest.mark.anyio
async def test_seed_writes_national_team_elo_entries() -> None:
    repo = FakeTeamStrengthRepository()
    provider = FakeNationalTeamEloProvider([
        _entry("Brazil", 2100.0),
        _entry("Argentina", 2080.0),
    ])
    use_case = SeedNationalTeamEloUseCase(repo, provider, EloCalculatorService())

    result = await use_case.execute("2026", dry_run=False)

    assert result.status == "completed"
    assert result.coverage_pct == 100.0
    assert len(repo.upserted_elos) == 2
    assert {row["source"] for row in repo.upserted_elos} == {NATIONAL_ELO_SOURCE}
    assert repo.upserted_elos[0]["competition_ids"] == [1]


@pytest.mark.anyio
async def test_dry_run_does_not_write() -> None:
    repo = FakeTeamStrengthRepository()
    provider = FakeNationalTeamEloProvider([
        _entry("Brazil", 2100.0),
        _entry("Argentina", 2080.0),
    ])
    use_case = SeedNationalTeamEloUseCase(repo, provider, EloCalculatorService())

    result = await use_case.execute("2026", dry_run=True)

    assert result.status == "completed"
    assert repo.upserted_elos == []


@pytest.mark.anyio
async def test_unmatched_team_is_reported_and_blocks_when_below_coverage() -> None:
    repo = FakeTeamStrengthRepository()
    provider = FakeNationalTeamEloProvider([_entry("Brazil", 2100.0)])
    use_case = SeedNationalTeamEloUseCase(repo, provider, EloCalculatorService())

    result = await use_case.execute("2026", dry_run=False, min_coverage=100.0)

    assert result.status == "failed"
    assert result.coverage_pct == 50.0
    assert result.unmatched == ["Argentina"]
    assert repo.upserted_elos == []


@pytest.mark.anyio
async def test_manual_entries_are_used_as_fallback_input() -> None:
    repo = FakeTeamStrengthRepository()
    provider = FakeNationalTeamEloProvider([])
    use_case = SeedNationalTeamEloUseCase(repo, provider, EloCalculatorService())

    result = await use_case.execute(
        "2026",
        dry_run=False,
        manual_entries=[_entry("Brazil", 2100.0), _entry("Argentina", 2080.0)],
    )

    assert result.status == "completed"
    assert len(repo.upserted_elos) == 2


@pytest.mark.anyio
async def test_missing_world_cup_competition_returns_failed() -> None:
    repo = FakeTeamStrengthRepository(competition_id=None)
    provider = FakeNationalTeamEloProvider([])
    use_case = SeedNationalTeamEloUseCase(repo, provider, EloCalculatorService())

    result = await use_case.execute("2026")

    assert result.status == "failed"
    assert result.error == "World Cup competition not found"


@pytest.mark.anyio
async def test_no_active_world_cup_teams_does_not_write() -> None:
    repo = FakeTeamStrengthRepository(teams=[])
    provider = FakeNationalTeamEloProvider([_entry("Brazil", 2100.0)])
    use_case = SeedNationalTeamEloUseCase(repo, provider, EloCalculatorService())

    result = await use_case.execute("2026", dry_run=False)

    assert result.status == "failed"
    assert result.error == "No active World Cup teams found for season"
    assert repo.upserted_elos == []
