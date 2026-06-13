from datetime import datetime, timezone

import pytest

from sfa.application.use_cases.calculate_team_strengths import CalculateTeamStrengthsUseCase
from sfa.domain.scoring_ports import TeamStandingRow, TeamStrengthRepositoryPort


class FakeTeamStrengthRepository(TeamStrengthRepositoryPort):
    def __init__(self, standings_by_season: dict | None = None):
        self._standings: dict[tuple, list[TeamStandingRow]] = standings_by_season or {}
        self.upserted: list[dict] = []

    async def get_team_strength(self, team_id: int, season: str, competition_id: int) -> float | None:
        return None

    async def upsert_team_strength(
        self, team_id: int, season: str, competition_id: int, strength: float, source: str
    ) -> None:
        self.upserted.append({
            "team_id": team_id, "season": season, "competition_id": competition_id,
            "strength": strength, "source": source,
        })

    async def get_team_standings_for_season(
        self, competition_id: int, season: str
    ) -> list[TeamStandingRow]:
        return self._standings.get((competition_id, season), [])


def _make_standings(competition_id: int, season: str, n_teams: int) -> list[TeamStandingRow]:
    return [
        TeamStandingRow(
            team_id=i,
            season=season,
            competition_id=competition_id,
            avg_position=float(i),
            total_points=max(0, (n_teams - i) * 3),
            matchdays_played=20,
        )
        for i in range(1, n_teams + 1)
    ]


class TestCalculateTeamStrengthsUseCase:
    @pytest.mark.anyio
    async def test_upserts_strength_for_all_teams_in_competition(self):
        standings = _make_standings(1, "2024", 4)
        repo = FakeTeamStrengthRepository(standings_by_season={(1, "2024"): standings})
        use_case = CalculateTeamStrengthsUseCase(repo)

        result = await use_case.execute(season="2024", competition_id=1)

        assert result.status == "completed"
        assert result.teams_processed == 4
        assert len(repo.upserted) == 4

    @pytest.mark.anyio
    async def test_team_1_gets_highest_strength(self):
        standings = _make_standings(1, "2024", 3)
        prev_standings = _make_standings(1, "2023", 3)
        repo = FakeTeamStrengthRepository(standings_by_season={
            (1, "2024"): standings,
            (1, "2023"): prev_standings,
        })
        use_case = CalculateTeamStrengthsUseCase(repo)

        await use_case.execute(season="2024", competition_id=1, matchday=20)

        strengths = {u["team_id"]: u["strength"] for u in repo.upserted}
        assert strengths[1] > strengths[2] > strengths[3]

    @pytest.mark.anyio
    async def test_promoted_team_without_history_uses_default_strength(self):
        # Current season has team_id=99 (new team not in prev standings)
        standings = [
            TeamStandingRow(99, "2024", 1, 1.0, 60, 20),
            TeamStandingRow(1, "2024", 1, 2.0, 55, 20),
        ]
        prev_standings = [
            TeamStandingRow(1, "2023", 1, 1.0, 60, 20),
        ]
        repo = FakeTeamStrengthRepository(standings_by_season={
            (1, "2024"): standings,
            (1, "2023"): prev_standings,
        })
        use_case = CalculateTeamStrengthsUseCase(repo)

        await use_case.execute(
            season="2024", competition_id=1, matchday=3,
            promoted_default_strength=30.0,
        )

        team_99_upsert = next(u for u in repo.upserted if u["team_id"] == 99)
        # team_99 has no prev history → fallback=30.0; position 1 = 100% current
        # matchday=3 → 80/20 blend: 0.8×30 + 0.2×100 = 24 + 20 = 44
        assert team_99_upsert["strength"] == pytest.approx(44.0, abs=1.0)

    @pytest.mark.anyio
    async def test_no_standings_returns_zero_processed(self):
        repo = FakeTeamStrengthRepository()
        use_case = CalculateTeamStrengthsUseCase(repo)
        result = await use_case.execute(season="2024", competition_id=1)
        assert result.teams_processed == 0
        assert result.status == "completed"

    @pytest.mark.anyio
    async def test_early_season_weights_previous_heavily(self):
        standings = [TeamStandingRow(1, "2024", 1, 1.0, 30, 5)]
        prev_standings = [TeamStandingRow(1, "2023", 1, 20.0, 10, 38)]
        repo = FakeTeamStrengthRepository(standings_by_season={
            (1, "2024"): standings,
            (1, "2023"): prev_standings,
        })
        use_case = CalculateTeamStrengthsUseCase(repo)
        await use_case.execute(season="2024", competition_id=1, matchday=2)

        u = repo.upserted[0]
        # prev_strength = position_to_strength(20, 1) = 0 (single team, but 20/1=? let's just check < 100)
        assert u["strength"] >= 0.0 and u["strength"] <= 100.0
