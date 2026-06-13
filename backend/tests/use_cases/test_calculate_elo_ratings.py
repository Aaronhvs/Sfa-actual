from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.calculate_elo_ratings import CalculateEloRatingsUseCase
from sfa.domain.scoring_ports import (
    FixtureEloRow,
    TeamEloRow,
    TeamStandingRow,
    TeamStrengthRepositoryPort,
)
from sfa.infrastructure.services.elo_calculator import ELO_DEFAULT, EloCalculatorService


class FakeTeamStrengthRepository(TeamStrengthRepositoryPort):
    def __init__(self, seeded=None, fixtures=None) -> None:
        self.seeded = seeded or []
        self.fixtures = fixtures or []
        self.active_competitions: dict[int, list[int]] = {}
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
        return self.seeded

    async def get_fixtures_for_elo_recalc(self, season, competition_ids) -> list[FixtureEloRow]:
        return sorted(self.fixtures, key=lambda fixture: fixture.played_at)

    async def get_team_name_id_map(self, season):
        return {}

    async def get_active_competition_ids_for_team(self, team_id, season):
        return self.active_competitions.get(team_id, [1])


def _fixture(fixture_id, home, away, home_goals, away_goals, played_at, competition_id=1):
    return FixtureEloRow(
        fixture_id=fixture_id,
        home_team_id=home,
        away_team_id=away,
        played_at=played_at,
        competition_id=competition_id,
        home_goals=home_goals,
        away_goals=away_goals,
        season="2024",
    )


@pytest.mark.anyio
async def test_single_fixture_updates_both_teams():
    repo = FakeTeamStrengthRepository(fixtures=[
        _fixture(1, 10, 20, 2, 0, datetime(2024, 8, 1, tzinfo=timezone.utc))
    ])
    use_case = CalculateEloRatingsUseCase(repo, EloCalculatorService())

    result = await use_case.execute("2024", [1], {}, 30.0)

    assert result.status == "completed"
    assert result.fixtures_processed == 1
    by_team = {row["team_id"]: row for row in repo.upserted_elos}
    assert by_team[10]["elo_raw"] > ELO_DEFAULT
    assert by_team[20]["elo_raw"] < ELO_DEFAULT


@pytest.mark.anyio
async def test_fixtures_processed_in_chronological_order():
    fixtures = [
        _fixture(2, 20, 10, 2, 0, datetime(2024, 8, 8, tzinfo=timezone.utc)),
        _fixture(1, 10, 20, 2, 0, datetime(2024, 8, 1, tzinfo=timezone.utc)),
    ]
    repo = FakeTeamStrengthRepository(fixtures=fixtures)
    use_case = CalculateEloRatingsUseCase(repo, EloCalculatorService())

    await use_case.execute("2024", [1], {}, 30.0)

    by_team = {row["team_id"]: row["elo_raw"] for row in repo.upserted_elos}
    inverted_home_after_first = EloCalculatorService.update_elo(1500, 1500, 2, 0, True, 30.0)
    inverted_away_after_first = EloCalculatorService.update_elo(1500, 1500, 2, 0, False, 30.0)
    inverted_final_team_10 = EloCalculatorService.update_elo(
        inverted_away_after_first, inverted_home_after_first, 2, 0, False, 30.0
    )
    assert by_team[10] != pytest.approx(inverted_final_team_10)


@pytest.mark.anyio
async def test_team_without_seed_gets_default_elo():
    repo = FakeTeamStrengthRepository(fixtures=[
        _fixture(1, 10, 20, 0, 0, datetime(2024, 8, 1, tzinfo=timezone.utc))
    ])
    use_case = CalculateEloRatingsUseCase(repo, EloCalculatorService())

    await use_case.execute("2024", [1], {}, 30.0)

    assert {row["elo_raw"] for row in repo.upserted_elos} == {ELO_DEFAULT}


@pytest.mark.anyio
async def test_k_factor_applied_per_competition():
    repo = FakeTeamStrengthRepository(fixtures=[
        _fixture(1, 10, 20, 1, 0, datetime(2024, 8, 1, tzinfo=timezone.utc), competition_id=1),
        _fixture(2, 30, 40, 1, 0, datetime(2024, 8, 1, tzinfo=timezone.utc), competition_id=2),
    ])
    use_case = CalculateEloRatingsUseCase(repo, EloCalculatorService())

    await use_case.execute("2024", [1, 2], {1: 10.0, 2: 40.0}, 30.0)

    by_team = {row["team_id"]: row["elo_raw"] for row in repo.upserted_elos}
    assert by_team[30] - ELO_DEFAULT == pytest.approx((by_team[10] - ELO_DEFAULT) * 4)


@pytest.mark.anyio
async def test_elo_written_normalized_and_raw():
    repo = FakeTeamStrengthRepository(seeded=[
        TeamEloRow(team_id=10, season="2024", elo_raw=1950.0, strength=78.57)
    ])
    use_case = CalculateEloRatingsUseCase(repo, EloCalculatorService())

    await use_case.execute("2024", [1], {}, 30.0)

    assert repo.upserted_elos[0]["elo_raw"] == pytest.approx(1950.0)
    assert repo.upserted_elos[0]["strength_normalized"] == pytest.approx(78.57, abs=0.01)
    assert repo.upserted_elos[0]["source"] == "elo_v1"
