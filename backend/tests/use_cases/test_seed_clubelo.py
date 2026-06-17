import pytest

from sfa.application.use_cases.seed_clubelo import SeedClubEloUseCase
from sfa.domain.scoring_ports import (
    FixtureEloRow,
    TeamCompetitionRow,
    TeamEloRow,
    TeamStandingRow,
    TeamStrengthCoverageRow,
    TeamStrengthRepositoryPort,
)
from sfa.infrastructure.providers.clubelo_provider import ClubEloEntry
from sfa.infrastructure.services.elo_calculator import EloCalculatorService


class FakeTeamStrengthRepository(TeamStrengthRepositoryPort):
    def __init__(self) -> None:
        self.team_name_id_map = {"Manchester City": 10}
        self.active_competitions = {10: [3]}
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
        return self.team_name_id_map

    async def get_active_competition_ids_for_team(self, team_id, season):
        return self.active_competitions.get(team_id, [])

    async def get_competition_id_by_name(self, name):
        return None

    async def get_teams_for_competition_season(self, competition_id, season) -> list[TeamCompetitionRow]:
        return []

    async def get_team_strength_coverage(self, competition_id, season) -> list[TeamStrengthCoverageRow]:
        return []


class FakeClubEloProvider:
    def __init__(self, entries=None, error: Exception | None = None) -> None:
        self.entries = entries or []
        self.error = error

    async def fetch_snapshot(self, date_str):
        if self.error is not None:
            raise self.error
        return self.entries

    def resolve_team_name(self, clubelo_name, sfa_team_names):
        if clubelo_name == "Man City" and "Manchester City" in sfa_team_names:
            return "Manchester City"
        return clubelo_name if clubelo_name in sfa_team_names else None


@pytest.mark.anyio
async def test_seed_known_team_writes_elo_entry():
    repo = FakeTeamStrengthRepository()
    provider = FakeClubEloProvider([
        ClubEloEntry(club_name="Man City", country="ENG", level=1, elo=1950.0)
    ])
    use_case = SeedClubEloUseCase(repo, provider, EloCalculatorService())

    result = await use_case.execute("2024-08-01", "2024")

    assert result.status == "completed"
    assert result.matched == 1
    assert repo.upserted_elos[0]["elo_raw"] == pytest.approx(1950.0)
    assert repo.upserted_elos[0]["strength_normalized"] == pytest.approx(78.57, abs=0.01)
    assert repo.upserted_elos[0]["source"] == "clubelo_seed"
    assert repo.upserted_elos[0]["competition_ids"] == [3]


@pytest.mark.anyio
async def test_seed_unknown_team_reported_as_unmatched():
    repo = FakeTeamStrengthRepository()
    provider = FakeClubEloProvider([
        ClubEloEntry(club_name="Unknown FC", country="ENG", level=1, elo=1700.0)
    ])
    use_case = SeedClubEloUseCase(repo, provider, EloCalculatorService())

    result = await use_case.execute("2024-08-01", "2024")

    assert result.matched == 0
    assert result.unmatched == ["Unknown FC"]
    assert repo.upserted_elos == []


@pytest.mark.anyio
async def test_seed_only_processes_level_1_entries():
    repo = FakeTeamStrengthRepository()
    provider = FakeClubEloProvider([
        ClubEloEntry(club_name="Man City", country="ENG", level=1, elo=1950.0),
        ClubEloEntry(club_name="Unknown B", country="ENG", level=2, elo=1600.0),
    ])
    use_case = SeedClubEloUseCase(repo, provider, EloCalculatorService())

    result = await use_case.execute("2024-08-01", "2024")

    assert result.matched == 1
    assert result.unmatched == []
    assert len(repo.upserted_elos) == 1


@pytest.mark.anyio
async def test_seed_provider_error_returns_failed_result():
    repo = FakeTeamStrengthRepository()
    provider = FakeClubEloProvider(error=RuntimeError("clubelo down"))
    use_case = SeedClubEloUseCase(repo, provider, EloCalculatorService())

    result = await use_case.execute("2024-08-01", "2024")

    assert result.status == "failed"
    assert result.error == "clubelo down"
