from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.ensure_late_team_elo_seeds import (
    LATE_ENTRY_DEFAULT_ELO,
    EnsureLateTeamEloSeedsUseCase,
)
from sfa.domain.scoring_ports import FixtureEloRow, TeamEloRow, TeamEloSeedDTO


class FakeTeamStrengthRepository:
    def __init__(self) -> None:
        self.fixtures = [
            FixtureEloRow(
                fixture_id=1,
                home_team_id=10,
                away_team_id=20,
                played_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
                competition_id=9,
                home_goals=2,
                away_goals=1,
                season="2026",
            ),
            FixtureEloRow(
                fixture_id=2,
                home_team_id=20,
                away_team_id=30,
                played_at=datetime(2026, 8, 8, tzinfo=timezone.utc),
                competition_id=9,
                home_goals=0,
                away_goals=0,
                season="2026",
            ),
        ]
        self.seeds = [
            TeamEloSeedDTO(
                team_id=10,
                season="2026",
                participant_kind="club",
                elo_raw=1900.0,
                effective_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
                source="clubelo_snapshot",
            )
        ]
        self.previous_rows = [
            TeamEloRow(
                team_id=20,
                season="2025",
                elo_raw=1775.0,
                strength=53.0,
                elo_seed_raw=1700.0,
            )
        ]
        self.requested_previous_season = None

    async def get_fixtures_for_elo_recalc(self, season, competition_ids):
        return self.fixtures

    async def get_team_elo_seeds(self, season, participant_kind):
        return self.seeds

    async def get_all_teams_with_elo(self, season, competition_ids=None):
        self.requested_previous_season = season
        return self.previous_rows

    async def upsert_team_elo_seed(self, seed):
        self.seeds.append(seed)


@pytest.mark.asyncio
async def test_creates_rollover_and_default_seeds_for_late_entrants() -> None:
    repo = FakeTeamStrengthRepository()

    result = await EnsureLateTeamEloSeedsUseCase(repo).execute(
        season="2026",
        participant_kind="club",
        competition_ids=[9],
    )

    assert result.status == "completed"
    assert result.rollover_created == 1
    assert result.default_created == 1
    assert repo.requested_previous_season == "2025"
    new_seeds = {seed.team_id: seed for seed in repo.seeds if seed.team_id != 10}
    assert new_seeds[20].elo_raw == 1775.0
    assert new_seeds[20].source == "season_rollover"
    assert new_seeds[30].elo_raw == LATE_ENTRY_DEFAULT_ELO
    assert new_seeds[30].source == "manual_override"
    assert all(
        seed.effective_at == datetime(2026, 8, 1, tzinfo=timezone.utc)
        for seed in new_seeds.values()
    )


@pytest.mark.asyncio
async def test_is_idempotent_after_missing_seeds_are_created() -> None:
    repo = FakeTeamStrengthRepository()
    use_case = EnsureLateTeamEloSeedsUseCase(repo)

    first = await use_case.execute("2026", "club", [9])
    second = await use_case.execute("2026", "club", [9])

    assert first.rollover_created == 1
    assert first.default_created == 1
    assert second.rollover_created == 0
    assert second.default_created == 0
    assert len(repo.seeds) == 3
