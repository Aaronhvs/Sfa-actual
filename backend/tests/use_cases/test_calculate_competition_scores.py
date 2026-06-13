import pytest

from sfa.application.use_cases.calculate_competition_scores import CalculateCompetitionScoresUseCase
from sfa.domain.ingestion_ports import PlayerSeasonScoreRow, ScoringRepositoryPort


class FakeScoringRepository(ScoringRepositoryPort):
    def __init__(self, rows: list[PlayerSeasonScoreRow] | None = None):
        self._rows = rows or []
        self.upserted: list[dict] = []

    async def get_competition_ids_with_season(self, season: str) -> list[int]:
        return []

    async def get_player_scores_for_competition(
        self, competition_id: int, season: str,
    ) -> list[PlayerSeasonScoreRow]:
        return self._rows

    async def upsert_season_score(
        self, player_id: int, competition_id: int,
        season: str, total_pts: float,
        matches_played: int, breakdown: dict,
    ) -> None:
        self.upserted.append({
            "player_id": player_id,
            "competition_id": competition_id,
            "season": season,
            "total_pts": total_pts,
            "matches_played": matches_played,
            "breakdown": breakdown,
        })


class TestCalculateCompetitionScoresUseCase:
    @pytest.mark.anyio
    async def test_no_players_returns_empty_result(self):
        repo = FakeScoringRepository(rows=[])
        use_case = CalculateCompetitionScoresUseCase(repo)

        result = await use_case.execute(competition_id=1, season="2024")

        assert result.players_scored == 0
        assert result.status == "completed"
        assert result.error is None
        assert repo.upserted == []

    @pytest.mark.anyio
    async def test_player_below_90_min_threshold_excluded(self):
        rows = [
            PlayerSeasonScoreRow(
                player_id=1, total_pts=500.0, matches_played=3,
                breakdown={"goal": {"count": 1, "pts": 500.0}},
                total_minutes=45,
            )
        ]
        repo = FakeScoringRepository(rows=rows)
        use_case = CalculateCompetitionScoresUseCase(repo)

        result = await use_case.execute(competition_id=1, season="2024")

        assert result.players_scored == 0
        assert result.status == "completed"
        assert repo.upserted == []

    @pytest.mark.anyio
    async def test_player_above_threshold_gets_upserted(self):
        rows = [
            PlayerSeasonScoreRow(
                player_id=7, total_pts=1200.0, matches_played=10,
                breakdown={"goal": {"count": 2, "pts": 1200.0}},
                total_minutes=900,
            )
        ]
        repo = FakeScoringRepository(rows=rows)
        use_case = CalculateCompetitionScoresUseCase(repo)

        result = await use_case.execute(competition_id=5, season="2024")

        assert result.players_scored == 1
        assert result.status == "completed"
        assert len(repo.upserted) == 1
        call = repo.upserted[0]
        assert call["player_id"] == 7
        assert call["competition_id"] == 5
        assert call["season"] == "2024"
        assert call["total_pts"] == 1200.0
        assert call["matches_played"] == 10

    @pytest.mark.anyio
    async def test_breakdown_pct_calculated_correctly(self):
        rows = [
            PlayerSeasonScoreRow(
                player_id=3, total_pts=1000.0, matches_played=8,
                breakdown={
                    "goal":  {"count": 2, "pts": 700.0},
                    "stats": {"count": 8, "pts": 300.0},
                },
                total_minutes=720,
            )
        ]
        repo = FakeScoringRepository(rows=rows)
        use_case = CalculateCompetitionScoresUseCase(repo)

        await use_case.execute(competition_id=1, season="2024")

        breakdown = repo.upserted[0]["breakdown"]
        assert breakdown["goal"]["pct"] == 70.0
        assert breakdown["stats"]["pct"] == 30.0

    @pytest.mark.anyio
    async def test_multiple_players_mixed_threshold(self):
        rows = [
            PlayerSeasonScoreRow(
                player_id=1, total_pts=800.0, matches_played=5,
                breakdown={"stats": {"count": 5, "pts": 800.0}},
                total_minutes=90,
            ),
            PlayerSeasonScoreRow(
                player_id=2, total_pts=400.0, matches_played=2,
                breakdown={"stats": {"count": 2, "pts": 400.0}},
                total_minutes=89,
            ),
            PlayerSeasonScoreRow(
                player_id=3, total_pts=1500.0, matches_played=12,
                breakdown={"goal": {"count": 3, "pts": 1500.0}},
                total_minutes=1080,
            ),
        ]
        repo = FakeScoringRepository(rows=rows)
        use_case = CalculateCompetitionScoresUseCase(repo)

        result = await use_case.execute(competition_id=2, season="2024")

        assert result.players_scored == 2
        upserted_ids = {u["player_id"] for u in repo.upserted}
        assert upserted_ids == {1, 3}
