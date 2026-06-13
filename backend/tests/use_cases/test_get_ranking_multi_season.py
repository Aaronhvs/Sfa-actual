import pytest

from sfa.application.use_cases.get_ranking import GetRankingUseCase
from sfa.domain.ports import RankedPlayerDTO, SFAScoreRepositoryProtocol


def _ranked_player() -> RankedPlayerDTO:
    return RankedPlayerDTO(
        rank=1,
        player_id=1,
        player_name="Player One",
        team_name="Current Team",
        team_logo_url=None,
        position="DEL",
        competition_name="League",
        total_pts=300.0,
        matches_played=20,
        photo_url=None,
    )


class FakeSFAScoreRepository(SFAScoreRepositoryProtocol):
    def __init__(self):
        self.specific_called = False
        self.all_called = False

    async def get_best_score_for_player_season(self, player_id, season, rules_version_id=None):
        return None

    async def get_global_rank(self, player_id, season, total_pts, rules_version_id=None):
        return 1

    async def get_competitions_for_player_season(self, player_id, season, rules_version_id=None):
        return []

    async def get_ranking(self, season, position=None, competition_id=None, limit=50, name=None,
                          rules_version_id=None, use_total=False):
        self.specific_called = True
        return [_ranked_player()]

    async def get_ranking_total(self, season, position=None, competition_id=None, name=None,
                                rules_version_id=None):
        return 1

    async def latest_season(self):
        return "2025"

    async def latest_season_for_player(self, player_id):
        return "2025"

    async def get_total_player_stats(self, player_id, season, rules_version_id=None):
        return (0, 0, 0, 0.0)

    async def get_available_seasons_for_player(self, player_id):
        return ["2025", "2024"]

    async def get_ranking_all_seasons(self, position=None, competition_id=None, limit=50,
                                      name=None, rules_version_id=None, use_total=False):
        self.all_called = True
        return [_ranked_player()]

    async def get_ranking_total_all_seasons(self, position=None, competition_id=None,
                                            name=None, rules_version_id=None):
        return 1

    async def get_total_player_stats_all_seasons(self, player_id, rules_version_id=None):
        return (0, 0, 0, 0.0)

    async def get_global_rank_all_seasons(self, player_id, total_pts, rules_version_id=None):
        return 1


class TestGetRankingMultiSeason:
    @pytest.mark.anyio
    async def test_season_all_calls_all_seasons_methods(self):
        repo = FakeSFAScoreRepository()

        await GetRankingUseCase(repo).execute(season="all")

        assert repo.all_called is True
        assert repo.specific_called is False

    @pytest.mark.anyio
    async def test_season_all_returns_season_all_in_result(self):
        result = await GetRankingUseCase(FakeSFAScoreRepository()).execute(season="all")

        assert result.season == "all"

    @pytest.mark.anyio
    async def test_season_specific_still_works(self):
        repo = FakeSFAScoreRepository()

        result = await GetRankingUseCase(repo).execute(season="2024")

        assert result.season == "2024"
        assert repo.specific_called is True
        assert repo.all_called is False

    @pytest.mark.anyio
    async def test_season_none_resolves_latest(self):
        result = await GetRankingUseCase(FakeSFAScoreRepository()).execute()

        assert result.season == "2025"
