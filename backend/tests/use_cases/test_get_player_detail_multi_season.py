import pytest

from sfa.api.v1.schemas.players import PlayerDetailSchema
from sfa.application.use_cases.get_player_detail import GetPlayerDetailUseCase
from sfa.domain.ports import PlayerScoreDTO, SFAScoreRepositoryProtocol


def _score() -> PlayerScoreDTO:
    return PlayerScoreDTO(
        player_id=1,
        player_name="Player One",
        team_name="Latest Team",
        position="DEL",
        competition_name="League",
        competition_id=1,
        total_pts=100.0,
        matches_played=10,
        photo_url=None,
        breakdown={"goal": {"count": 2, "pts": 20.0}},
    )


class FakeSFAScoreRepository(SFAScoreRepositoryProtocol):
    async def get_best_score_for_player_season(self, player_id, season, rules_version_id=None):
        return _score()

    async def get_global_rank(self, player_id, season, total_pts, rules_version_id=None):
        return 2

    async def get_competitions_for_player_season(self, player_id, season, rules_version_id=None):
        return ["League"]

    async def get_ranking(self, season, position=None, competition_id=None, limit=50, name=None,
                          rules_version_id=None, use_total=False):
        return []

    async def get_ranking_total(self, season, position=None, competition_id=None, name=None,
                                rules_version_id=None):
        return 0

    async def latest_season(self):
        return "2025"

    async def latest_season_for_player(self, player_id):
        return "2025"

    async def get_total_player_stats(self, player_id, season, rules_version_id=None):
        return (10, 2, 3, 100.0)

    async def get_available_seasons_for_player(self, player_id):
        return ["2025", "2024"]

    async def get_ranking_all_seasons(self, position=None, competition_id=None, limit=50,
                                      name=None, rules_version_id=None, use_total=False):
        return []

    async def get_ranking_total_all_seasons(self, position=None, competition_id=None,
                                            name=None, rules_version_id=None):
        return 0

    async def get_total_player_stats_all_seasons(self, player_id, rules_version_id=None):
        return (25, 7, 9, 275.5)

    async def get_global_rank_all_seasons(self, player_id, total_pts, rules_version_id=None):
        return 3


class TestGetPlayerDetailMultiSeason:
    @pytest.mark.anyio
    async def test_season_all_returns_aggregated_stats(self):
        result = await GetPlayerDetailUseCase(FakeSFAScoreRepository()).execute(1, "all")

        assert result.matches == 25
        assert result.total_goals == 7
        assert result.total_assists == 9
        assert result.sfa_pts == 275.5
        assert result.global_rank == 3

    @pytest.mark.anyio
    async def test_season_all_result_has_season_all(self):
        result = await GetPlayerDetailUseCase(FakeSFAScoreRepository()).execute(1, "all")

        assert result.season == "all"

    @pytest.mark.anyio
    async def test_available_seasons_populated(self):
        result = await GetPlayerDetailUseCase(FakeSFAScoreRepository()).execute(1, "all")

        assert result.available_seasons == ["2025", "2024"]

    def test_available_seasons_in_schema(self):
        schema = PlayerDetailSchema(
            id=1,
            name="Player One",
            team="Team",
            position="DEL",
            competition="League",
            sfa_pts=1.0,
            matches=1,
            total_goals=0,
            total_assists=0,
            photo_url=None,
            global_rank=1,
            season="all",
            breakdown=None,
            competitions=[],
            available_seasons=["2025"],
        )

        assert schema.available_seasons == ["2025"]

    @pytest.mark.anyio
    async def test_specific_season_still_returns_available_seasons(self):
        result = await GetPlayerDetailUseCase(FakeSFAScoreRepository()).execute(1, "2024")

        assert result.season == "2024"
        assert result.available_seasons == ["2025", "2024"]
